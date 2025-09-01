import os
from dataclasses import dataclass
from typing import List, Optional

def _to_bool(v: str | None) -> bool:
    if not v: return False
    return v.strip().lower() in ("1","true","yes","y","on")

@dataclass
class Settings:
    # MT5 Connection
    mt5_login: int
    mt5_password: str
    mt5_server: str
    mt5_path: Optional[str]
    symbols: List[str]
    timeframe_str: str
    telegram_token: Optional[str]
    telegram_chat_id: Optional[str]
    
    # Risk Management
    risk_per_trade: float
    atr_period: int
    sl_atr_mult: float
    tp_r_mult: float
    cooldown_minutes: int
    dry_run: bool
    magic_number: int
    order_comment: str
    filling_mode_str: Optional[str]
    attach_mode: bool
    
    # Vision Analysis Settings
    min_confidence: float = 0.60
    min_risk_reward: float = 1.5
    min_confluences: int = 2
    max_spread_atr_ratio: float = 0.1
    min_news_minutes: int = 30
    
    # OpenAI Settings
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4-vision-preview"
    max_tokens: int = 4096
    temperature: float = 0.7

    @property
    def using_attach_mode(self) -> bool:
        """Check if we should use attach mode"""
        return self.attach_mode or not all([self.mt5_login, self.mt5_password, self.mt5_server])

    @property
    def filling_mode(self):
        import MetaTrader5 as mt5
        m = (self.filling_mode_str or "").upper()
        return {
            "IOC": mt5.ORDER_FILLING_IOC,
            "FOK": mt5.ORDER_FILLING_FOK,
            "RETURN": mt5.ORDER_FILLING_RETURN,
        }.get(m, None)
        
    def validate_trade_decision(self, decision: dict) -> tuple[bool, str]:
        """
        Validate if a trade decision meets all requirements for execution
        
        Args:
            decision: Trade decision dict conforming to our schema
            
        Returns:
            tuple[bool, str]: (is_valid, reason)
        """
        # Must be a directional trade
        if decision["decision"] == "WAIT":
            return False, "No trade signal"
            
        # Check confidence
        if decision["confidence"] < self.min_confidence:
            return False, f"Confidence {decision['confidence']:.2f} below minimum {self.min_confidence}"
            
        # Check risk metrics
        risk = decision["risk"]
        if risk["r_multiple"] < self.min_risk_reward:
            return False, f"Risk/Reward {risk['r_multiple']:.2f} below minimum {self.min_risk_reward}"
            
        if risk["sl_distance"] < risk["atr"]:
            return False, "Stop loss too tight (< 1 ATR)"
            
        # Check guards
        guards = decision["guards_ok"]
        if not guards["spread_ok"]:
            return False, "Spread too high"
            
        if not guards["news_ok"]:
            return False, f"High impact news within {self.min_news_minutes} minutes"
            
        if not guards["cooldown_ok"]:
            return False, f"Need {self.cooldown_minutes} minutes between trades"
            
        return True, "Trade validated"

def get_settings() -> Settings:
    return Settings(
        # MT5 connection
        mt5_login=int(os.getenv("MT5_LOGIN", "0")),
        mt5_password=os.getenv("MT5_PASSWORD", ""),
        mt5_server=os.getenv("MT5_SERVER", ""),
        mt5_path=os.getenv("MT5_PATH", "C:\\Program Files\\MetaTrader 5\\terminal64.exe"),
        attach_mode=_to_bool(os.getenv("ATTACH_MODE", "false")),
        
        # Trading parameters
        symbols=[s.strip() for s in os.getenv("SYMBOLS", os.getenv("SYMBOL", "XAUUSD")).split(",") if s.strip()],
        timeframe_str=os.getenv("TIMEFRAME", "M30"),
        
        # Notifications
        telegram_token=os.getenv("TELEGRAM_BOT_TOKEN") or None,
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID") or None,

        # Risk management
        risk_per_trade=float(os.getenv("RISK_PER_TRADE", "0.01")),
        atr_period=int(os.getenv("ATR_PERIOD", "14")),
        sl_atr_mult=float(os.getenv("SL_ATR_MULTIPLIER", "1.5")),
        tp_r_mult=float(os.getenv("TP_R_MULTIPLIER", "2.0")),
        cooldown_minutes=int(os.getenv("COOLDOWN_MINUTES", "60")),
        
        # Execution
        dry_run=_to_bool(os.getenv("DRY_RUN", "true")),
        magic_number=int(os.getenv("MAGIC_NUMBER", "20250831")),
        order_comment=os.getenv("ORDER_COMMENT", "AIVO"),
        filling_mode_str=os.getenv("FILLING_MODE") or None,
        
        # Vision Analysis Settings
        min_confidence=float(os.getenv("MIN_CONFIDENCE", "0.60")),
        min_risk_reward=float(os.getenv("MIN_RISK_REWARD", "1.5")),
        min_confluences=int(os.getenv("MIN_CONFLUENCES", "2")),
        max_spread_atr_ratio=float(os.getenv("MAX_SPREAD_ATR_RATIO", "0.1")),
        min_news_minutes=int(os.getenv("MIN_NEWS_MINUTES", "30")),
        
        # OpenAI Settings
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4-vision-preview"),
        max_tokens=int(os.getenv("MAX_TOKENS", "4096")),
        temperature=float(os.getenv("TEMPERATURE", "0.7"))
    )
