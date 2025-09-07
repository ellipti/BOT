from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # MT5
    MT5_TERMINAL_PATH: str | None = None
    MT5_LOGIN: int | None = None 
    MT5_PASSWORD: str | None = None
    MT5_SERVER: str | None = None
    ATTACH_MODE: bool = True  # Default: attach to running terminal

    # SYMBOL / STRATEGY
    SYMBOL: str = "XAUUSD"
    TF_MIN: int = 30
    RISK_PCT: float = 0.01
    SESSION: str = "ANY"      # TOKYO | LDN_NY | ANY
    COOLDOWN_MULT: float = 1.0  # Reduced for more frequent testing
    MIN_ATR: float = 1.2     # Reduced from 2.0
    SL_MULT: float = 1.5
    TP_MULT: float = 3.0
    DRY_RUN: bool = True

    # INTEGRATIONS
    TE_API_KEY: str = ""
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""           # хуучин ганц chat-ийн fallback
    TELEGRAM_CHAT_IDS: str = ""          # олон chat (comma-separated)

    # --- Limits / Overtrade guard ---
    LIMITS_ENABLED: bool = True
    MAX_TRADES_PER_DAY: int = 8
    MAX_DAILY_LOSS_PCT: float = 3.0      # %
    MAX_OPEN_POSITIONS: int = 1          # нэг симбол дээр зэрэг

    # --- Audit / Alerts ---
    TRADE_LOG_ENABLED: bool = True
    TELEGRAM_ERROR_ALERTS: bool = True

    # PnL коэффициент 
    USD_PER_LOT_PER_USD_MOVE: float = 100.0

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",        # ← Ignore unknown keys
        case_sensitive=False   # ← Case insensitive
    )

settings = Settings()
