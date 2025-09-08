"""
Advanced configuration management using Pydantic Settings v2+
Supports environment-based configuration with validation and type safety
Integrates with OS keyring for secure secret storage
"""

import os
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator, validator
from pydantic.types import PositiveFloat, PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict

# Import keyring secrets management
try:
    from infra.secrets import get_secret
except ImportError:
    # Fallback if secrets module not available
    def get_secret(name: str) -> str | None:
        return os.getenv(name)


# Configuration directory
CONFIG_DIR = Path(__file__).parent / "config"
CONFIG_DIR.mkdir(exist_ok=True)


class Environment(str, Enum):
    """Environment types"""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class SessionType(str, Enum):
    """Trading session types"""

    TOKYO = "TOKYO"
    LONDON_NY = "LDN_NY"
    ANY = "ANY"


class LogLevel(str, Enum):
    """Log levels"""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class BrokerKind(str, Enum):
    """Broker adapter types"""

    MT5 = "mt5"
    PAPER = "paper"


class FeedKind(str, Enum):
    """Feed types for data source"""

    LIVE = "live"
    BACKTEST = "backtest"


class SlippageKind(str, Enum):
    """Slippage model types"""

    FIXED = "fixed"
    ATR = "atr"
    NONE = "none"


class MT5Settings(BaseSettings):
    """MetaTrader 5 connection settings with keyring integration"""

    # Connection modes
    attach_mode: bool = Field(
        default=True,
        description="Use attach mode (connect to running terminal) vs headless login",
    )

    # Connection details (required for headless mode)
    terminal_path: str | None = Field(
        default=None, description="Path to MT5 terminal executable"
    )
    login: int | None = Field(default=None, description="MT5 account login number")
    password: str | None = Field(
        default_factory=lambda: get_secret("MT5_PASSWORD"),
        description="MT5 account password (loaded from keyring)",
    )
    server: str | None = Field(default=None, description="MT5 broker server name")

    # Connection timeout
    connection_timeout: PositiveInt = Field(
        default=30, description="Connection timeout in seconds"
    )

    @model_validator(mode="after")
    def validate_connection_config(self):
        """Validate MT5 connection configuration"""
        attach_mode = self.attach_mode

        if not attach_mode:
            # Headless mode requires all connection details
            required_fields = ["login", "password", "server"]
            missing = [
                field for field in required_fields if not getattr(self, field, None)
            ]

            if missing:
                raise ValueError(
                    f"Headless mode requires: {', '.join(missing)}. "
                    f"Set ATTACH_MODE=true to use attach mode instead."
                )

        return self

    model_config = SettingsConfigDict(env_prefix="MT5_", case_sensitive=False)


class TradingSettings(BaseSettings):
    """Trading strategy and risk management settings"""

    # Symbol and timeframe
    symbol: str = Field(default="XAUUSD", description="Trading symbol")
    timeframe_minutes: PositiveInt = Field(
        default=30, alias="tf_min", description="Timeframe in minutes"
    )

    # Risk management
    risk_percentage: PositiveFloat = Field(
        default=0.01,
        alias="risk_pct",
        ge=0.001,
        le=0.1,
        description="Risk per trade as percentage of balance (0.001-0.1)",
    )

    # Strategy parameters
    session: SessionType = Field(
        default=SessionType.ANY, description="Trading session filter"
    )
    cooldown_multiplier: PositiveFloat = Field(
        default=1.0, alias="cooldown_mult", description="Cooldown period multiplier"
    )

    # ATR Configuration
    atr_period: PositiveInt = Field(
        default=14, description="ATR calculation period (bars)"
    )
    min_atr: PositiveFloat = Field(
        default=1.2, description="Minimum ATR required for trading"
    )
    stop_loss_multiplier: PositiveFloat = Field(
        default=1.5, alias="sl_mult", description="Stop loss ATR multiplier"
    )
    take_profit_multiplier: PositiveFloat = Field(
        default=3.0, alias="tp_mult", description="Take profit ATR multiplier"
    )

    # Trailing Stop Configuration
    trail_use_atr: bool = Field(
        default=True, description="Use ATR-based dynamic trailing buffer"
    )
    trail_atr_mult: PositiveFloat = Field(
        default=1.5, description="ATR multiplier for trailing buffer"
    )
    trail_min_step_pips: PositiveFloat = Field(
        default=8.0, description="Minimum step to move trailing stop (pips)"
    )
    trail_hysteresis_pips: PositiveFloat = Field(
        default=4.0, description="Hysteresis threshold to prevent oscillations (pips)"
    )
    trail_buffer_pips: PositiveFloat = Field(
        default=10.0, description="Fixed trailing buffer when not using ATR (pips)"
    )

    # Break-Even Configuration
    be_trigger_pips: PositiveFloat = Field(
        default=10.0, description="Profit threshold to trigger breakeven (pips)"
    )
    be_buffer_pips: PositiveFloat = Field(
        default=2.0, description="Buffer above/below entry for breakeven SL (pips)"
    )

    # Position Netting Configuration
    netting_mode: Literal["NETTING", "HEDGING"] = Field(
        default="NETTING",
        description="Position netting mode: NETTING reduces opposite positions, HEDGING allows multiple positions",
    )
    reduce_rule: Literal["FIFO", "LIFO", "PROPORTIONAL"] = Field(
        default="FIFO",
        description="Rule for reducing positions: FIFO (oldest first), LIFO (newest first), PROPORTIONAL (across all)",
    )

    # Position sizing
    usd_per_lot_per_usd_move: PositiveFloat = Field(
        default=100.0, description="USD P&L per lot per $1 price move"
    )

    # Economic Calendar Integration
    trading_economics_api_key: str | None = Field(
        default_factory=lambda: get_secret("TE_API_KEY"),
        description="Trading Economics API key for calendar events (loaded from keyring)",
    )
    calendar_enabled: bool = Field(
        default=False, description="Enable economic calendar blackout periods"
    )

    model_config = SettingsConfigDict(env_prefix="TRADING_", case_sensitive=False)


class FeedSettings(BaseSettings):
    """Feed configuration for data sources and execution simulation"""

    # Feed type selection
    feed_kind: FeedKind = Field(
        default=FeedKind.LIVE, description="Data feed type: live MT5 or backtest CSV"
    )

    # Backtest data configuration
    backtest_data_dir: str = Field(
        default="data", description="Directory containing CSV backtest data files"
    )

    # Slippage model configuration
    slippage_kind: SlippageKind = Field(
        default=SlippageKind.FIXED, description="Slippage model type"
    )

    # Fixed slippage parameters
    fixed_slippage_pips: PositiveFloat = Field(
        default=1.0, description="Fixed slippage in pips"
    )

    pip_size: PositiveFloat = Field(
        default=0.1, description="Pip size for the trading instrument"
    )

    # ATR-based slippage parameters
    atr_slippage_percentage: PositiveFloat = Field(
        default=2.0, description="Slippage as percentage of ATR"
    )

    # Spread and fees
    spread_pips: PositiveFloat = Field(
        default=10.0, description="Bid-ask spread in pips"
    )

    fee_per_lot: float = Field(
        default=0.0, ge=0.0, description="Commission fee per lot traded"
    )

    model_config = SettingsConfigDict(env_prefix="FEED_", case_sensitive=False)


class SafetySettings(BaseSettings):
    """Safety gates and risk controls"""

    # Enable/disable safety features
    limits_enabled: bool = Field(
        default=True, description="Enable daily trading limits"
    )

    # Daily limits
    max_trades_per_day: PositiveInt = Field(
        default=8, description="Maximum trades per day"
    )
    max_daily_loss_percentage: PositiveFloat = Field(
        default=3.0,
        alias="max_daily_loss_pct",
        le=20.0,
        description="Maximum daily loss as percentage (max 20%)",
    )
    max_open_positions: PositiveInt = Field(
        default=1, description="Maximum open positions per symbol"
    )

    # News filtering
    enable_news_filter: bool = Field(
        default=True, description="Enable high-impact news filtering"
    )
    news_window_minutes: PositiveInt = Field(
        default=60, description="Minutes to avoid trading around news"
    )

    model_config = SettingsConfigDict(env_prefix="SAFETY_", case_sensitive=False)


class RiskSettings(BaseSettings):
    """Risk governance and management settings - Upgrade #07"""

    # Daily limits
    max_daily_loss_percentage: PositiveFloat = Field(
        default=5.0, le=20.0, description="Өдрийн дээд алдагдлын хувь (%)"
    )

    max_daily_trades: PositiveInt = Field(
        default=15, le=100, description="Өдрийн дээд арилжааны тоо"
    )

    # Weekly limits
    max_weekly_loss_percentage: PositiveFloat = Field(
        default=15.0, le=50.0, description="7 хоногийн дээд алдагдлын хувь (%)"
    )

    max_weekly_trades: PositiveInt = Field(
        default=75, le=500, description="7 хоногийн дээд арилжааны тоо"
    )

    # Cooldown
    cooldown_minutes: PositiveInt = Field(
        default=30,
        le=1440,  # 24 hours max
        description="Арилжааны хоорондын хүлээх хугацаа (минут)",
    )

    # Circuit breaker
    circuit_breaker_loss_threshold: PositiveFloat = Field(
        default=8.0, le=25.0, description="Circuit breaker идэвхжих алдагдлын босго (%)"
    )

    circuit_breaker_recovery_hours: PositiveInt = Field(
        default=4, le=24, description="Circuit breaker сэргээх хугацаа (цаг)"
    )

    # Consecutive losses
    max_consecutive_losses: PositiveInt = Field(
        default=5, le=20, description="Дараалсан алдагдлын дээд тоо"
    )

    # V2 Settings for RiskGovernorV2
    max_consecutive_losses_v2: PositiveInt = Field(
        default=3, le=10, description="RiskGovernorV2: Дараалсан алдагдлын дээд тоо"
    )

    max_trades_per_session: PositiveInt = Field(
        default=5,
        le=20,
        description="RiskGovernorV2: Нэг session-д зөвшөөрөгдөх дээд арилжааны тоо",
    )

    cooldown_after_loss_min: PositiveInt = Field(
        default=30,
        le=480,
        description="RiskGovernorV2: Алдагдлын дараах cooldown хугацаа (минут)",
    )

    # News blackout configuration
    news_blackout_map: dict[str, list[int]] = Field(
        default={
            "high": [45, 45],  # [pre_minutes, post_minutes]
            "medium": [20, 20],
            "low": [5, 5],
        },
        description="RiskGovernorV2: Мэдээний impact-аас хамаарсан blackout хугацаа",
    )

    # Risk level thresholds
    medium_risk_threshold: PositiveFloat = Field(
        default=40.0, le=100.0, description="Дунд эрсдэлийн босго (%)"
    )

    high_risk_threshold: PositiveFloat = Field(
        default=70.0, le=100.0, description="Өндөр эрсдэлийн босго (%)"
    )

    critical_risk_threshold: PositiveFloat = Field(
        default=90.0, le=100.0, description="Эгзэгтэй эрсдэлийн босго (%)"
    )

    # Alerts
    enable_telegram_alerts: bool = Field(
        default=True, description="Telegram анхааруулга идэвхжүүлэх"
    )

    alert_on_medium_risk: bool = Field(
        default=True, description="Дунд эрсдэлд анхааруулга илгээх"
    )

    alert_on_high_risk: bool = Field(
        default=True, description="Өндөр эрсдэлд анхааруулга илгээх"
    )

    # Validation
    @validator("max_weekly_loss_percentage")
    def weekly_loss_must_be_higher_than_daily(cls, v, values):
        daily_loss = values.get("max_daily_loss_percentage", 5.0)
        if v <= daily_loss:
            raise ValueError(
                "7 хоногийн дээд алдагдал өдрийн дээд алдагдлаас их байх ёстой"
            )
        return v

    @validator("max_weekly_trades")
    def weekly_trades_must_be_higher_than_daily(cls, v, values):
        daily_trades = values.get("max_daily_trades", 15)
        if v <= daily_trades:
            raise ValueError(
                "7 хоногийн дээд арилжаа өдрийн дээд арилжаанаас их байх ёстой"
            )
        return v

    # Volatility Regime Settings (Prompt-29)
    regime_timeframe: str = Field(
        default="H1", description="Timeframe for regime detection (H1, H4, D1)"
    )

    regime_default: str = Field(
        default="normal", description="Default regime when detection fails"
    )

    regime_enabled: bool = Field(
        default=True, description="Enable volatility regime detection"
    )

    model_config = SettingsConfigDict(env_prefix="RISK_", case_sensitive=False)


class TelegramSettings(BaseSettings):
    """Telegram integration settings with keyring integration"""

    bot_token: str | None = Field(
        default_factory=lambda: get_secret("TELEGRAM_TOKEN"),
        description="Telegram bot token (loaded from keyring)",
    )

    # Multiple recipients support
    chat_ids: str | None = Field(
        default=None, description="Comma-separated list of chat IDs"
    )

    # Legacy single chat ID (fallback)
    chat_id: str | None = Field(
        default=None, description="Single chat ID (legacy fallback)"
    )

    # Error alerts
    error_alerts: bool = Field(
        default=True, description="Send error alerts via Telegram"
    )

    # Notification timeout
    timeout_seconds: PositiveInt = Field(
        default=30, description="Telegram API timeout in seconds"
    )

    @validator("chat_ids", always=True)
    def validate_chat_ids(cls, v, values):
        """Ensure at least one chat ID is provided if bot token exists"""
        try:
            bot_token = values.get("bot_token")
            chat_id = values.get("chat_id")

            # Skip validation if no bot token or it's empty/None
            if not bot_token or len(str(bot_token).strip()) <= 10:
                return v or chat_id

            # Only require chat IDs if we have a real bot token
            if not (v or chat_id):
                raise ValueError(
                    "TELEGRAM_CHAT_IDS or TELEGRAM_CHAT_ID required when bot token is set"
                )

            return v or chat_id
        except Exception:
            # If validation fails for any reason, just return the value
            return v

    model_config = SettingsConfigDict(env_prefix="TELEGRAM_", case_sensitive=False)


class IntegrationSettings(BaseSettings):
    """External API integrations with keyring integration"""

    # Trading Economics
    te_api_key: str | None = Field(
        default_factory=lambda: get_secret("TE_API_KEY"),
        description="Trading Economics API key for news filtering (loaded from keyring)",
    )

    # API timeouts
    api_timeout_seconds: PositiveInt = Field(
        default=10, description="API request timeout in seconds"
    )

    model_config = SettingsConfigDict(env_prefix="API_", case_sensitive=False)


class LoggingSettings(BaseSettings):
    """Logging and audit settings"""

    # Log level
    log_level: LogLevel = Field(
        default=LogLevel.INFO, description="Application log level"
    )

    # Log files
    log_directory: Path = Field(
        default=Path("logs"), description="Directory for log files"
    )

    # Trade audit
    trade_log_enabled: bool = Field(
        default=True, description="Enable trade audit logging to CSV"
    )

    # Log retention
    log_retention_days: PositiveInt = Field(
        default=30, description="Days to retain log files"
    )

    model_config = SettingsConfigDict(env_prefix="LOG_", case_sensitive=False)


class ObservabilitySettings(BaseSettings):
    """Observability, metrics, and monitoring settings"""

    # HTTP metrics server
    enable_http_metrics: bool = Field(
        default=True, description="Enable HTTP metrics endpoint server"
    )

    metrics_port: PositiveInt = Field(
        default=9101, description="Port for HTTP metrics server"
    )

    metrics_host: str = Field(
        default="0.0.0.0", description="Host to bind metrics server"
    )

    # Prometheus integration
    enable_prometheus: bool = Field(
        default=False, description="Enable Prometheus metrics format"
    )

    # Health check settings
    health_check_interval: PositiveInt = Field(
        default=30, description="Health check interval in seconds"
    )

    # Event lag threshold
    event_lag_threshold_seconds: PositiveInt = Field(
        default=60, description="Event lag threshold for health warnings"
    )

    # Dashboard settings
    enable_dash: bool = Field(
        default=True, description="Enable FastAPI dashboard server"
    )

    dash_port: PositiveInt = Field(
        default=8080, description="Port for dashboard server"
    )

    dash_host: str = Field(
        default="127.0.0.1", description="Host to bind dashboard server"
    )

    dash_token: str = Field(
        default_factory=lambda: get_secret("DASH_TOKEN") or "dev-dashboard-token-2025",
        description="Dashboard authentication token (loaded from keyring or default)",
    )

    # JWT Authentication Settings (Prompt-28)
    dash_jwt_secret: str = Field(
        default_factory=lambda: get_secret("DASH_JWT_SECRET") or "dev-jwt-secret-2025",
        description="JWT secret key for dashboard authentication",
    )

    dash_access_ttl_min: PositiveInt = Field(
        default=15,
        description="Access token TTL in minutes",
    )

    dash_refresh_ttl_days: PositiveInt = Field(
        default=7,
        description="Refresh token TTL in days",
    )

    model_config = SettingsConfigDict(env_prefix="METRICS_", case_sensitive=False)


class ApplicationSettings(BaseSettings):
    """Main application configuration combining all settings"""

    # Environment
    environment: Environment = Field(
        default=Environment.DEVELOPMENT,
        alias="env",
        description="Application environment",
    )

    # Internationalization and timezone settings
    LOCALE: str = Field(
        default="mn",
        description="Locale for messages and alerts (mn=Mongolian, en=English)",
    )

    TZ: str = Field(
        default="Asia/Ulaanbaatar", description="Timezone for logging and user display"
    )

    # Broker selection
    broker_kind: BrokerKind = Field(
        default=BrokerKind.PAPER,
        alias="BROKER_KIND",
        description="Broker adapter type: mt5 for MetaTrader 5, paper for simulation",
    )

    # Operation mode
    dry_run: bool = Field(
        default=True, description="Run in dry-run mode (no real trades)"
    )

    # Event-driven architecture
    enable_event_bus: bool = Field(
        default=True, description="Enable event-driven pipeline architecture"
    )

    # Performance & Workload Isolation
    workers: int = Field(
        default=2,
        ge=1,
        le=10,
        description="Number of worker threads for async task processing",
    )

    enable_async_charts: bool = Field(
        default=True, description="Enable async chart rendering via WorkQueue"
    )

    enable_async_reports: bool = Field(
        default=True, description="Enable async report generation via WorkQueue"
    )

    enable_scheduler: bool = Field(
        default=True, description="Enable APScheduler for periodic tasks"
    )

    latency_threshold_ms: float = Field(
        default=100.0,
        gt=0,
        description="Trading loop latency threshold for alerts (milliseconds)",
    )

    # Idempotency and reliability
    idempotency_db: str = Field(
        default="infra/id_store.sqlite",
        description="SQLite database path for idempotent order execution",
    )

    # Component settings
    mt5: MT5Settings = Field(default_factory=MT5Settings)
    trading: TradingSettings = Field(default_factory=TradingSettings)
    feed: FeedSettings = Field(default_factory=FeedSettings)
    safety: SafetySettings = Field(default_factory=SafetySettings)
    risk: RiskSettings = Field(default_factory=RiskSettings)  # Upgrade #07
    telegram: TelegramSettings = Field(default_factory=TelegramSettings)
    integrations: IntegrationSettings = Field(default_factory=IntegrationSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)

    # Version info
    version: str = Field(default="1.0.0", description="Application version")

    @property
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.environment == Environment.PRODUCTION

    @property
    def is_development(self) -> bool:
        """Check if running in development"""
        return self.environment == Environment.DEVELOPMENT

    @property
    def is_testing(self) -> bool:
        """Check if running in testing"""
        return self.environment == Environment.TESTING

    @validator("dry_run", always=True)
    def validate_dry_run_in_production(cls, v, values):
        """Ensure dry_run safety in production"""
        env = values.get("environment", Environment.DEVELOPMENT)

        if env == Environment.PRODUCTION and v is False:
            # In production, require explicit confirmation to disable dry_run
            confirm = os.getenv("CONFIRM_LIVE_TRADING", "").lower()
            if confirm != "yes":
                raise ValueError(
                    "Live trading in production requires CONFIRM_LIVE_TRADING=yes"
                )

        return v

    @model_validator(mode="after")
    def validate_configuration(self):
        """Cross-validate configuration"""
        # Ensure required integrations are configured
        if hasattr(self, "telegram") and self.telegram:
            if self.telegram.bot_token and not (
                self.telegram.chat_ids or self.telegram.chat_id
            ):
                raise ValueError("Telegram bot token requires at least one chat ID")

        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        validate_assignment=True,
    )


# Global settings instance
def get_settings() -> ApplicationSettings:
    """Get application settings (cached)"""
    return ApplicationSettings()


# Legacy compatibility - maintain old interface
class LegacySettings:
    """Legacy settings interface for backward compatibility"""

    def __init__(self):
        self._settings = get_settings()

    def __getattr__(self, name: str):
        """Map legacy attribute names to new structure"""
        # Map old names to new structure
        legacy_mapping = {
            # Broker
            "BROKER_KIND": lambda: self._settings.broker_kind.value,
            # MT5
            "MT5_TERMINAL_PATH": lambda: self._settings.mt5.terminal_path,
            "MT5_LOGIN": lambda: self._settings.mt5.login,
            "MT5_PASSWORD": lambda: self._settings.mt5.password,
            "MT5_SERVER": lambda: self._settings.mt5.server,
            "ATTACH_MODE": lambda: self._settings.mt5.attach_mode,
            # Trading
            "SYMBOL": lambda: self._settings.trading.symbol,
            "TF_MIN": lambda: self._settings.trading.timeframe_minutes,
            "RISK_PCT": lambda: self._settings.trading.risk_percentage,
            "SESSION": lambda: self._settings.trading.session.value,
            "COOLDOWN_MULT": lambda: self._settings.trading.cooldown_multiplier,
            "ATR_PERIOD": lambda: self._settings.trading.atr_period,
            "MIN_ATR": lambda: self._settings.trading.min_atr,
            "SL_MULT": lambda: self._settings.trading.stop_loss_multiplier,
            "TP_MULT": lambda: self._settings.trading.take_profit_multiplier,
            # Trailing
            "TRAIL_USE_ATR": lambda: self._settings.trading.trail_use_atr,
            "TRAIL_ATR_MULT": lambda: self._settings.trading.trail_atr_mult,
            "TRAIL_MIN_STEP_PIPS": lambda: self._settings.trading.trail_min_step_pips,
            "TRAIL_HYSTERESIS_PIPS": lambda: self._settings.trading.trail_hysteresis_pips,
            "TRAIL_BUFFER_PIPS": lambda: self._settings.trading.trail_buffer_pips,
            "BE_TRIGGER_PIPS": lambda: self._settings.trading.be_trigger_pips,
            "BE_BUFFER_PIPS": lambda: self._settings.trading.be_buffer_pips,
            # Netting
            "NETTING_MODE": lambda: self._settings.trading.netting_mode,
            "REDUCE_RULE": lambda: self._settings.trading.reduce_rule,
            # App
            "DRY_RUN": lambda: self._settings.dry_run,
            "ENVIRONMENT": lambda: self._settings.environment.value,
            # Telegram
            "TELEGRAM_BOT_TOKEN": lambda: self._settings.telegram.bot_token,
            "TELEGRAM_CHAT_ID": lambda: self._settings.telegram.chat_id,
            "TELEGRAM_CHAT_IDS": lambda: self._settings.telegram.chat_ids,
            "TELEGRAM_ERROR_ALERTS": lambda: self._settings.telegram.error_alerts,
            # Safety
            "LIMITS_ENABLED": lambda: self._settings.safety.limits_enabled,
            "MAX_TRADES_PER_DAY": lambda: self._settings.safety.max_trades_per_day,
            "MAX_DAILY_LOSS_PCT": lambda: self._settings.safety.max_daily_loss_percentage,
            "MAX_OPEN_POSITIONS": lambda: self._settings.safety.max_open_positions,
            # Integrations
            "TE_API_KEY": lambda: self._settings.integrations.te_api_key,
            # Logging
            "TRADE_LOG_ENABLED": lambda: self._settings.logging.trade_log_enabled,
            # Observability
            "ENABLE_HTTP_METRICS": lambda: self._settings.observability.enable_http_metrics,
            "METRICS_PORT": lambda: self._settings.observability.metrics_port,
            "ENABLE_PROMETHEUS": lambda: self._settings.observability.enable_prometheus,
            "ENABLE_DASH": lambda: self._settings.observability.enable_dash,
            "DASH_PORT": lambda: self._settings.observability.dash_port,
            "DASH_HOST": lambda: self._settings.observability.dash_host,
            "DASH_TOKEN": lambda: self._settings.observability.dash_token,
            # JWT Authentication (Prompt-28)
            "DASH_JWT_SECRET": lambda: self._settings.observability.dash_jwt_secret,
            "DASH_ACCESS_TTL_MIN": lambda: self._settings.observability.dash_access_ttl_min,
            "DASH_REFRESH_TTL_DAYS": lambda: self._settings.observability.dash_refresh_ttl_days,
            # Localization and timezone
            "LOCALE": lambda: self._settings.LOCALE,
            "TZ": lambda: self._settings.TZ,
            # Other
            "USD_PER_LOT_PER_USD_MOVE": lambda: self._settings.trading.usd_per_lot_per_usd_move,
        }

        if name in legacy_mapping:
            return legacy_mapping[name]()

        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{name}'"
        )


# Create legacy settings instance for backward compatibility
settings = LegacySettings()
