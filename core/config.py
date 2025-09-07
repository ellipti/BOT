from settings import settings

def _to_bool(v: str | None) -> bool:
    if not v: return False
    return v.strip().lower() in ("1","true","yes","y","on")

class Strategy:
    def __init__(self):
        # MT5 Connection
        self.mt5_login = int(settings.MT5_LOGIN)
        self.mt5_password = settings.MT5_PASSWORD
        self.mt5_server = settings.MT5_SERVER
        self.mt5_path = settings.MT5_PATH or "C:\\Program Files\\MetaTrader 5\\terminal64.exe"
        self.attach_mode = _to_bool(settings.ATTACH_MODE)
        
        # Trading parameters
        self.symbols = [s.strip() for s in settings.SYMBOLS.split(",") if s.strip()]
        self.timeframe_str = settings.TIMEFRAME
        
        # Notifications
        self.telegram_token = settings.TELEGRAM_BOT_TOKEN or None
        self.telegram_chat_id = settings.TELEGRAM_CHAT_ID or None

        # Risk management
        self.risk_per_trade = float(settings.RISK_PER_TRADE)
        self.atr_period = int(settings.ATR_PERIOD)
        self.sl_atr_mult = float(settings.SL_ATR_MULTIPLIER)
        self.tp_r_mult = float(settings.TP_R_MULTIPLIER)
        self.cooldown_minutes = int(settings.COOLDOWN_MINUTES)
        
        # Execution
        self.dry_run = _to_bool(settings.DRY_RUN)
        self.magic_number = int(settings.MAGIC_NUMBER)
        self.order_comment = settings.ORDER_COMMENT
        self.filling_mode_str = settings.FILLING_MODE or None
        
        # Vision Analysis Settings
        self.min_confidence = float(settings.MIN_CONFIDENCE)
        self.min_risk_reward = float(settings.MIN_RISK_REWARD)
        self.min_confluences = int(settings.MIN_CONFLUENCES)
        self.max_spread_atr_ratio = float(settings.MAX_SPREAD_ATR_RATIO)
        self.min_news_minutes = int(settings.MIN_NEWS_MINUTES)
        
        # OpenAI Settings
        self.openai_api_key = settings.OPENAI_API_KEY
        self.openai_model = settings.OPENAI_MODEL or "gpt-4-vision-preview"
        self.max_tokens = int(settings.MAX_TOKENS)
        self.temperature = float(settings.TEMPERATURE)

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
