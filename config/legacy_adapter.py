"""
Legacy settings adapter for backward compatibility
Provides the old-style attribute access patterns
"""

from .settings import get_settings as _get_settings


class LegacySettingsAdapter:
    """Adapter to provide legacy-style attribute access to new settings"""

    def __init__(self):
        self._settings = _get_settings()

    # MT5 settings with legacy names
    @property
    def ATTACH_MODE(self) -> bool:
        return self._settings.mt5.attach_mode

    @property
    def MT5_TERMINAL_PATH(self) -> str:
        return self._settings.mt5.terminal_path

    @property
    def MT5_LOGIN(self) -> int:
        return self._settings.mt5.login

    @property
    def MT5_PASSWORD(self) -> str:
        return self._settings.mt5.password

    @property
    def MT5_SERVER(self) -> str:
        return self._settings.mt5.server

    # Trading settings with legacy names
    @property
    def SYMBOL(self) -> str:
        return self._settings.trading.symbol

    @property
    def TF_MIN(self) -> int:
        return self._settings.trading.timeframe_minutes

    @property
    def RISK_PCT(self) -> float:
        return self._settings.trading.risk_percentage

    @property
    def SESSION(self) -> str:
        return str(self._settings.trading.session.value)

    @property
    def COOLDOWN_MULT(self) -> float:
        return self._settings.trading.cooldown_multiplier

    @property
    def MIN_ATR(self) -> float:
        return self._settings.trading.min_atr

    @property
    def SL_MULT(self) -> float:
        return self._settings.trading.stop_loss_multiplier

    @property
    def TP_MULT(self) -> float:
        return self._settings.trading.take_profit_multiplier

    # Safety settings with legacy names
    @property
    def LIMITS_ENABLED(self) -> bool:
        return self._settings.safety.limits_enabled

    @property
    def MAX_TRADES_PER_DAY(self) -> int:
        return self._settings.safety.max_trades_per_day

    @property
    def MAX_DAILY_LOSS_PCT(self) -> float:
        return self._settings.safety.max_daily_loss_percentage

    @property
    def MAX_OPEN_POSITIONS(self) -> int:
        return self._settings.safety.max_open_positions

    # Telegram settings with legacy names
    @property
    def TELEGRAM_BOT_TOKEN(self) -> str:
        return self._settings.telegram.bot_token

    @property
    def TELEGRAM_CHAT_ID(self) -> str:
        return self._settings.telegram.chat_id

    @property
    def TELEGRAM_CHAT_IDS(self) -> str:
        return self._settings.telegram.chat_ids

    @property
    def TELEGRAM_ERROR_ALERTS(self) -> bool:
        return self._settings.telegram.error_alerts

    # Other settings
    @property
    def DRY_RUN(self) -> bool:
        return self._settings.dry_run

    @property
    def TRADE_LOG_ENABLED(self) -> bool:
        return self._settings.logging.trade_log_enabled


# Legacy compatibility function
def get_legacy_settings() -> LegacySettingsAdapter:
    """Get legacy-style settings adapter"""
    return LegacySettingsAdapter()
