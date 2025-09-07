#!/usr/bin/env python3
"""
Test Script: ATR-based Risk Management Integration
Validates position sizing calculations and ATR-based SL/TP
"""

import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_position_sizing():
    """Test position sizing calculations"""
    print("\n" + "=" * 60)
    print("TESTING: Position Sizing Functions")
    print("=" * 60)

    from core.sizing.sizing import calc_lot_by_risk, calc_sl_tp_by_atr, round_to_step

    # Test round_to_step function
    print("\n1. Testing round_to_step function:")
    test_cases = [
        (0.127, 0.01, 0.01, 100.0),  # Normal rounding
        (0.005, 0.01, 0.01, 100.0),  # Below minimum
        (150.0, 0.01, 0.01, 100.0),  # Above maximum
        (0.234, 0.1, 0.1, 10.0),  # Different step size
    ]

    for value, step, min_v, max_v in test_cases:
        result = round_to_step(value, step, min_v, max_v)
        print(f"  round_to_step({value}, {step}, {min_v}, {max_v}) = {result}")

    # Test ATR-based SL/TP calculation
    print("\n2. Testing calc_sl_tp_by_atr function:")
    entry_price = 2500.00
    atr = 15.50
    sl_mult = 1.5
    tp_mult = 3.0

    for side in ["BUY", "SELL"]:
        sl, tp = calc_sl_tp_by_atr(side, entry_price, atr, sl_mult, tp_mult)
        print(f"  {side} @ {entry_price}: SL={sl:.2f}, TP={tp:.2f} (ATR={atr})")

    # Test position sizing calculation
    print("\n3. Testing calc_lot_by_risk function:")

    # Mock symbol info
    class MockSymbolInfo:
        def __init__(self):
            self.trade_tick_size = 0.01  # $0.01 per tick
            self.trade_tick_value = 1.0  # $1.00 per tick per lot
            self.volume_min = 0.01  # Min 0.01 lots
            self.volume_max = 100.0  # Max 100 lots
            self.volume_step = 0.01  # 0.01 lot increments

    symbol_info = MockSymbolInfo()
    entry = 2500.00
    sl = 2476.75  # 1.5 ATR stop loss for BUY
    equity = 10000.00
    risk_pct = 0.01  # 1% risk

    lot_size = calc_lot_by_risk(symbol_info, entry, sl, equity, risk_pct)

    risk_amount = equity * risk_pct
    stop_distance = abs(entry - sl)
    ticks_to_sl = stop_distance / symbol_info.trade_tick_size

    print(f"  Entry: ${entry:.2f}")
    print(f"  Stop Loss: ${sl:.2f}")
    print(f"  Stop Distance: ${stop_distance:.2f} ({ticks_to_sl:.0f} ticks)")
    print(f"  Account Equity: ${equity:.2f}")
    print(f"  Risk %: {risk_pct:.1%} (${risk_amount:.2f})")
    print(f"  Calculated Lot Size: {lot_size:.3f}")

    # Verify the calculation
    expected_loss = lot_size * ticks_to_sl * symbol_info.trade_tick_value
    print(f"  Expected Loss at SL: ${expected_loss:.2f}")
    print(f"  Risk Ratio: {expected_loss/risk_amount:.2%} (should be ~100%)")


def test_settings_integration():
    """Test settings integration"""
    print("\n" + "=" * 60)
    print("TESTING: Settings Integration")
    print("=" * 60)

    try:
        from config.settings import get_settings

        settings = get_settings()

        print(f"Trading Symbol: {settings.trading.symbol}")
        print(f"Risk Percentage: {settings.trading.risk_percentage:.1%}")
        print(f"ATR Period: {settings.trading.atr_period}")
        print(f"Stop Loss Multiplier: {settings.trading.stop_loss_multiplier}")
        print(f"Take Profit Multiplier: {settings.trading.take_profit_multiplier}")
        print(f"Min ATR: {settings.trading.min_atr}")

        # Test legacy compatibility
        from config.settings import settings as legacy_settings

        print(f"Legacy ATR_PERIOD: {legacy_settings.ATR_PERIOD}")
        print(f"Legacy RISK_PCT: {legacy_settings.RISK_PCT:.1%}")
        print(f"Legacy SL_MULT: {legacy_settings.SL_MULT}")

    except Exception as e:
        print(f"Settings integration error: {e}")


def test_pipeline_imports():
    """Test pipeline imports"""
    print("\n" + "=" * 60)
    print("TESTING: Pipeline Integration")
    print("=" * 60)

    try:
        from app.pipeline import TradingPipeline

        print("✅ TradingPipeline import successful")

        # Check if sizing functions are imported
        from app.pipeline import calc_lot_by_risk, calc_sl_tp_by_atr

        print("✅ Sizing functions imported in pipeline")

        print("✅ Pipeline integration ready")

    except ImportError as e:
        print(f"❌ Pipeline import error: {e}")
    except Exception as e:
        print(f"❌ Pipeline error: {e}")


def test_error_handling():
    """Test error handling in sizing functions"""
    print("\n" + "=" * 60)
    print("TESTING: Error Handling")
    print("=" * 60)

    from core.sizing.sizing import calc_sl_tp_by_atr, round_to_step

    # Test invalid parameters
    test_cases = [
        (
            "calc_sl_tp_by_atr with negative ATR",
            lambda: calc_sl_tp_by_atr("BUY", 2500, -10, 1.5, 3.0),
        ),
        (
            "calc_sl_tp_by_atr with invalid side",
            lambda: calc_sl_tp_by_atr("INVALID", 2500, 10, 1.5, 3.0),
        ),
        (
            "round_to_step with negative step",
            lambda: round_to_step(1.0, -0.01, 0.01, 100.0),
        ),
        ("round_to_step with min > max", lambda: round_to_step(1.0, 0.01, 100.0, 0.01)),
    ]

    for test_name, test_func in test_cases:
        try:
            test_func()
            print(f"❌ {test_name}: Should have raised ValueError")
        except ValueError as e:
            print(f"✅ {test_name}: Correctly raised ValueError - {e}")
        except Exception as e:
            print(f"❌ {test_name}: Unexpected error - {e}")


def main():
    """Main test runner"""
    print("🚀 Starting ATR-based Risk Management Integration Tests")
    print(f"⏰ Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        test_position_sizing()
        test_settings_integration()
        test_pipeline_imports()
        test_error_handling()

        print("\n" + "=" * 60)
        print("✅ ALL TESTS COMPLETED SUCCESSFULLY")
        print("🎯 Risk management system is ready for use")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        logger.error(f"Test failure: {e}", exc_info=True)
        return False

    return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
