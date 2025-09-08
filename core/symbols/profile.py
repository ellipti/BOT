"""
Symbol Profile Management System (Prompt-30)
============================================

Asset-specific trading parameters, session guards, and holiday handling.
Provides symbol-specific tick sizes, values, volume constraints, and trading hours.

Features:
- Multi-asset support (forex/metal/index/crypto)
- Session/holiday guards with timezone support
- Symbol-specific sizing parameters
- MT5 info fallback with configurable priority
- Comprehensive session validation
"""

import logging
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Dict, List, Literal, Optional, Union
from zoneinfo import ZoneInfo

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

AssetType = Literal["forex", "metal", "index", "crypto", "unknown"]
SessionType = Literal["24x5", "24x7", "RTH"]


class SymbolProfile(BaseModel):
    """Trading profile for a specific symbol"""
    asset: AssetType = Field(description="Asset class")
    tick_size: float = Field(gt=0, description="Minimum price increment")
    tick_value: float = Field(gt=0, description="USD value per tick per lot")
    volume_min: float = Field(gt=0, description="Minimum trade volume")
    volume_max: float = Field(gt=0, description="Maximum trade volume")
    volume_step: float = Field(gt=0, description="Volume increment step")
    tz: str = Field(description="Timezone identifier")
    session: SessionType = Field(description="Trading session type")
    spread_typical: float = Field(default=1.0, ge=0, description="Typical spread")


class SessionDefinition(BaseModel):
    """Trading session definition"""
    days: List[int] = Field(description="Trading days (0=Monday, 6=Sunday)")
    start_time: str = Field(description="Session start time (HH:MM)")
    end_time: str = Field(description="Session end time (HH:MM)")
    breaks: List[Dict[str, str]] = Field(default=[], description="Intraday breaks")


class ProfileSettings(BaseModel):
    """Profile system configuration"""
    prefer_profile: bool = Field(default=True, description="Prefer profile over MT5 info")
    strict_session: bool = Field(default=True, description="Block trades outside sessions")
    check_holidays: bool = Field(default=False, description="Enable holiday checking")
    override_sizing: bool = Field(default=True, description="Override sizing with profiles")


class ProfileConfig(BaseModel):
    """Complete symbol profiles configuration"""
    profiles: Dict[str, SymbolProfile] = Field(default={})
    sessions: Dict[SessionType, SessionDefinition] = Field(default={})
    default: SymbolProfile = Field(description="Default fallback profile")
    settings: ProfileSettings = Field(default_factory=ProfileSettings)


def load_symbol_profiles(config_path: str = "configs/symbol_profiles.yaml") -> ProfileConfig:
    """
    Load symbol profiles from YAML configuration
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        ProfileConfig: Loaded configuration with validation
    """
    try:
        config_file = Path(config_path)
        if not config_file.exists():
            logger.warning(f"Profile config not found: {config_path}, using defaults")
            return _create_default_config()
        
        with open(config_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        # Extract profiles from top level (excluding sessions, default, settings)
        profiles = {}
        sessions = data.get('sessions', {})
        default = data.get('default', {})
        settings = data.get('settings', {})
        
        # All other top-level keys are symbol profiles
        for key, value in data.items():
            if key not in ['sessions', 'default', 'settings']:
                profiles[key] = SymbolProfile(**value)
        
        # Convert sessions
        parsed_sessions = {}
        for session_name, session_data in sessions.items():
            parsed_sessions[session_name] = SessionDefinition(**session_data)
        
        config = ProfileConfig(
            profiles=profiles,
            sessions=parsed_sessions,
            default=SymbolProfile(**default),
            settings=ProfileSettings(**settings)
        )
        
        logger.info(f"Loaded {len(profiles)} symbol profiles from {config_path}")
        return config
        
    except Exception as e:
        logger.error(f"Failed to load symbol profiles: {e}, using defaults")
        return _create_default_config()


def _create_default_config() -> ProfileConfig:
    """Create default profile configuration"""
    default_profile = SymbolProfile(
        asset="unknown",
        tick_size=0.0001,
        tick_value=1.0,
        volume_min=0.01,
        volume_max=100.0,
        volume_step=0.01,
        tz="UTC",
        session="24x5",
        spread_typical=1.0
    )
    
    return ProfileConfig(
        profiles={},
        sessions={
            "24x5": SessionDefinition(
                days=[0, 1, 2, 3, 4],
                start_time="22:00",
                end_time="22:00",
                breaks=[]
            ),
            "24x7": SessionDefinition(
                days=[0, 1, 2, 3, 4, 5, 6],
                start_time="00:00",
                end_time="23:59",
                breaks=[]
            ),
            "RTH": SessionDefinition(
                days=[0, 1, 2, 3, 4],
                start_time="14:30",
                end_time="21:00",
                breaks=[]
            )
        },
        default=default_profile,
        settings=ProfileSettings()
    )


class SymbolProfileManager:
    """Symbol profile manager with session and holiday validation"""
    
    def __init__(self, config: Optional[ProfileConfig] = None):
        """
        Initialize profile manager
        
        Args:
            config: Profile configuration (loads from file if None)
        """
        self.config = config or load_symbol_profiles()
        logger.info(f"SymbolProfileManager initialized with {len(self.config.profiles)} profiles")
    
    def get_profile(self, symbol: str) -> SymbolProfile:
        """
        Get trading profile for symbol
        
        Args:
            symbol: Trading symbol (e.g., 'XAUUSD')
            
        Returns:
            SymbolProfile: Symbol profile or default if not found
        """
        profile = self.config.profiles.get(symbol)
        if profile:
            logger.debug(f"Profile found for {symbol}: {profile.asset}")
            return profile
        else:
            logger.debug(f"No profile for {symbol}, using default")
            return self.config.default
    
    def get_symbol_info_override(self, symbol: str) -> Dict:
        """
        Get symbol info parameters for sizing override
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Dict: Symbol info compatible parameters
        """
        profile = self.get_profile(symbol)
        
        # Create MT5-compatible symbol info structure
        return {
            "trade_tick_size": profile.tick_size,
            "trade_tick_value": profile.tick_value,
            "volume_min": profile.volume_min,
            "volume_max": profile.volume_max,
            "volume_step": profile.volume_step,
            "asset": profile.asset,
            "spread_typical": profile.spread_typical,
        }
    
    def is_session_open(self, symbol: str, dt: Optional[datetime] = None) -> bool:
        """
        Check if trading session is open for symbol
        
        Args:
            symbol: Trading symbol
            dt: Datetime to check (uses current time if None)
            
        Returns:
            bool: True if session is open
        """
        if not self.config.settings.strict_session:
            logger.debug("Session checking disabled")
            return True
        
        if dt is None:
            dt = datetime.now(ZoneInfo("UTC"))
        
        profile = self.get_profile(symbol)
        session_def = self.config.sessions.get(profile.session)
        
        if not session_def:
            logger.warning(f"Unknown session type: {profile.session} for {symbol}")
            return True  # Default to open if session undefined
        
        try:
            # Convert to symbol's timezone
            symbol_tz = ZoneInfo(profile.tz)
            local_dt = dt.astimezone(symbol_tz)
            
            # Check if current day is a trading day
            weekday = local_dt.weekday()  # 0=Monday, 6=Sunday
            if weekday not in session_def.days:
                logger.debug(f"Session closed: {symbol} not trading on {local_dt.strftime('%A')}")
                return False
            
            # Parse session times
            start_time = time.fromisoformat(session_def.start_time)
            end_time = time.fromisoformat(session_def.end_time)
            current_time = local_dt.time()
            
            # Handle session that spans midnight (e.g., 22:00 to 22:00 next day)
            if start_time > end_time:
                # Session spans midnight
                is_open = current_time >= start_time or current_time <= end_time
            else:
                # Normal session within single day
                is_open = start_time <= current_time <= end_time
            
            # Check for intraday breaks
            if is_open and session_def.breaks:
                for break_period in session_def.breaks:
                    break_start = time.fromisoformat(break_period["start"])
                    break_end = time.fromisoformat(break_period["end"])
                    if break_start <= current_time <= break_end:
                        logger.debug(f"Session closed: {symbol} in break period {break_start}-{break_end}")
                        return False
            
            if not is_open:
                logger.debug(f"Session closed: {symbol} outside {start_time}-{end_time} in {profile.tz}")
            
            return is_open
            
        except Exception as e:
            logger.error(f"Error checking session for {symbol}: {e}")
            return True  # Default to open on error
    
    def is_holiday(self, symbol: str, date: Optional[datetime] = None) -> bool:
        """
        Check if date is a holiday for symbol
        
        Args:
            symbol: Trading symbol
            date: Date to check (uses current date if None)
            
        Returns:
            bool: True if it's a holiday
        """
        if not self.config.settings.check_holidays:
            return False
        
        if date is None:
            date = datetime.now(ZoneInfo("UTC"))
        
        # TODO: Implement holiday calendar loading from configs/holidays.yaml
        # For now, return False (no holidays)
        logger.debug(f"Holiday checking not implemented for {symbol}")
        return False
    
    def can_trade(self, symbol: str, dt: Optional[datetime] = None) -> tuple[bool, str]:
        """
        Check if symbol can be traded at given time
        
        Args:
            symbol: Trading symbol
            dt: Datetime to check (uses current time if None)
            
        Returns:
            tuple: (can_trade, reason)
        """
        if dt is None:
            dt = datetime.now(ZoneInfo("UTC"))
        
        # Check session
        if not self.is_session_open(symbol, dt):
            profile = self.get_profile(symbol)
            return False, f"MARKET_CLOSED: {symbol} session {profile.session} closed"
        
        # Check holidays
        if self.is_holiday(symbol, dt):
            return False, f"MARKET_HOLIDAY: {symbol} holiday"
        
        return True, "OK"
    
    def get_asset_symbols(self, asset_type: AssetType) -> List[str]:
        """
        Get all symbols of specific asset type
        
        Args:
            asset_type: Asset type to filter by
            
        Returns:
            List[str]: List of symbols
        """
        symbols = []
        for symbol, profile in self.config.profiles.items():
            if profile.asset == asset_type:
                symbols.append(symbol)
        return symbols
    
    def get_session_summary(self, symbol: str) -> Dict:
        """
        Get session information summary for symbol
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Dict: Session summary information
        """
        profile = self.get_profile(symbol)
        session_def = self.config.sessions.get(profile.session)
        
        can_trade_now, reason = self.can_trade(symbol)
        
        return {
            "symbol": symbol,
            "asset": profile.asset,
            "session_type": profile.session,
            "timezone": profile.tz,
            "can_trade_now": can_trade_now,
            "status_reason": reason,
            "trading_days": session_def.days if session_def else [],
            "session_hours": f"{session_def.start_time}-{session_def.end_time}" if session_def else "Unknown",
        }


# Singleton instance for global access
_profile_manager: Optional[SymbolProfileManager] = None


def get_profile_manager() -> SymbolProfileManager:
    """Get global symbol profile manager instance"""
    global _profile_manager
    if _profile_manager is None:
        _profile_manager = SymbolProfileManager()
    return _profile_manager


def reload_profiles() -> SymbolProfileManager:
    """Reload symbol profiles from configuration"""
    global _profile_manager
    _profile_manager = SymbolProfileManager()
    return _profile_manager
