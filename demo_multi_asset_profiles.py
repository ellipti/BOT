"""
Integration demonstration of Prompt-30 Multi-Asset Symbol Profiles
Shows complete functionality: session validation, profile loading, and position sizing
"""

from datetime import datetime, timezone
from unittest.mock import Mock

from core.symbols import SymbolProfileManager
from core.sizing.sizing import calc_lot_by_risk


def demo_multi_asset_trading():
    """Demonstrate multi-asset trading capabilities."""
    print("🚀 Prompt-30 Multi-Asset Trading Demo")
    print("=" * 50)
    
    # Initialize symbol profile manager
    manager = SymbolProfileManager()
    print(f"✅ Loaded {len(manager.config.profiles)} symbol profiles")
    
    # Demo symbols from different asset classes
    symbols = ["EURUSD", "XAUUSD", "US500", "BTCUSD"]
    
    print("\n📊 Symbol Profiles:")
    for symbol in symbols:
        profile = manager.get_profile(symbol)
        print(f"  {symbol}: {profile.asset}, tick={profile.tick_size}, vol_range={profile.volume_min}-{profile.volume_max}")
    
    print("\n🕐 Session Validation (Current Time):")
    for symbol in symbols:
        can_trade, reason = manager.can_trade(symbol)
        status = "✅" if can_trade else "❌"
        print(f"  {status} {symbol}: {reason}")
    
    print("\n🕐 Session Validation (Monday 10:00 UTC):")
    monday_10 = datetime(2024, 1, 8, 10, 0, tzinfo=timezone.utc)
    for symbol in symbols:
        can_trade, reason = manager.can_trade(symbol, monday_10)
        status = "✅" if can_trade else "❌"
        print(f"  {status} {symbol}: {reason}")
    
    print("\n🕐 Session Validation (Saturday 10:00 UTC):")
    saturday_10 = datetime(2024, 1, 6, 10, 0, tzinfo=timezone.utc)
    for symbol in symbols:
        can_trade, reason = manager.can_trade(symbol, saturday_10)
        status = "✅" if can_trade else "❌"
        print(f"  {status} {symbol}: {reason}")
    
    # Demo position sizing with profiles
    print("\n💰 Position Sizing with Profile Integration:")
    
    # Mock MT5 symbol info
    mock_info = Mock()
    mock_info.trade_tick_size = 0.0001
    mock_info.trade_tick_value = 1.0
    mock_info.volume_min = 0.01
    mock_info.volume_max = 100.0
    mock_info.volume_step = 0.01
    
    equity = 10000.0
    risk_pct = 0.02
    
    test_cases = [
        ("EURUSD", 1.1000, 1.0950),  # 50 pip stop
        ("XAUUSD", 2000.0, 1990.0),  # $10 stop
        ("US500", 4500.0, 4480.0),   # 20 point stop
        ("BTCUSD", 45000.0, 44000.0), # $1000 stop
    ]
    
    for symbol, current_price, sl_price in test_cases:
        lots = calc_lot_by_risk(
            mock_info, current_price, sl_price, equity, risk_pct, symbol=symbol
        )
        profile = manager.get_profile(symbol)
        risk_amount = equity * risk_pct
        print(f"  📈 {symbol} ({profile.asset}): {lots:.3f} lots (${risk_amount:.0f} risk)")
    
    print("\n🎯 Configuration Summary:")
    settings = manager.config.settings
    print(f"  • Prefer profiles: {settings.prefer_profile}")
    print(f"  • Strict sessions: {settings.strict_session}")
    print(f"  • Check holidays: {settings.check_holidays}")
    print(f"  • Override sizing: {settings.override_sizing}")
    
    print(f"\n✅ Prompt-30 Multi-Asset Trading System Ready!")
    print("   - Symbol-specific parameters loaded")
    print("   - Session validation active")
    print("   - Position sizing enhanced")
    print("   - Multi-asset support: Forex, Metals, Indices, Crypto")


if __name__ == "__main__":
    demo_multi_asset_trading()
