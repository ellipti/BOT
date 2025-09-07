"""
Test slippage models functionality
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from models.slippage import FixedPipsSlippage, NoSlippage, PercentOfATRSlippage


def test_fixed_pips_slippage():
    """Test fixed pips slippage model"""
    print("Testing FixedPipsSlippage...")

    slippage = FixedPipsSlippage(pips=2.0, pip_size=0.1)

    # Test BUY order (should increase price)
    buy_price = slippage.apply("BUY", 1950.0)
    expected_buy = 1950.0 + (2.0 * 0.1)  # 1950.2
    assert buy_price == expected_buy, f"Expected {expected_buy}, got {buy_price}"
    print(f"✓ BUY slippage: 1950.0 -> {buy_price}")

    # Test SELL order (should decrease price)
    sell_price = slippage.apply("SELL", 1950.0)
    expected_sell = 1950.0 - (2.0 * 0.1)  # 1949.8
    assert sell_price == expected_sell, f"Expected {expected_sell}, got {sell_price}"
    print(f"✓ SELL slippage: 1950.0 -> {sell_price}")


def test_atr_slippage():
    """Test ATR-based slippage model"""
    print("Testing ATR-based slippage...")

    slippage = PercentOfATRSlippage(atr_percentage=5.0)  # 5% of ATR

    atr = 10.0

    # Test BUY order
    buy_price = slippage.apply("BUY", 1950.0, atr=atr)
    expected_buy = 1950.0 + (10.0 * 0.05)  # 1950.5
    assert buy_price == expected_buy, f"Expected {expected_buy}, got {buy_price}"
    print(f"✓ BUY ATR slippage: 1950.0 -> {buy_price} (ATR={atr})")

    # Test SELL order
    sell_price = slippage.apply("SELL", 1950.0, atr=atr)
    expected_sell = 1950.0 - (10.0 * 0.05)  # 1949.5
    assert sell_price == expected_sell, f"Expected {expected_sell}, got {sell_price}"
    print(f"✓ SELL ATR slippage: 1950.0 -> {sell_price} (ATR={atr})")

    # Test that ATR is required
    try:
        slippage.apply("BUY", 1950.0, atr=None)
        raise AssertionError("Should have raised ValueError for missing ATR")
    except ValueError:
        print("✓ ATR requirement validation works")


def test_no_slippage():
    """Test no slippage model"""
    print("Testing NoSlippage...")

    slippage = NoSlippage()

    # Should return original price
    buy_price = slippage.apply("BUY", 1950.0)
    assert buy_price == 1950.0, f"Expected 1950.0, got {buy_price}"

    sell_price = slippage.apply("SELL", 1950.0)
    assert sell_price == 1950.0, f"Expected 1950.0, got {sell_price}"

    print("✓ No slippage model works correctly")


def test_side_validation():
    """Test order side validation"""
    print("Testing order side validation...")

    slippage = FixedPipsSlippage()

    # Valid sides should work
    slippage.apply("BUY", 1950.0)
    slippage.apply("SELL", 1950.0)
    slippage.apply("buy", 1950.0)  # lowercase should work
    slippage.apply("sell", 1950.0)

    # Invalid side should raise error
    try:
        slippage.apply("INVALID", 1950.0)
        raise AssertionError("Should have raised ValueError for invalid side")
    except ValueError:
        print("✓ Side validation works")


if __name__ == "__main__":
    print("=== Slippage Models Tests ===\n")

    try:
        test_fixed_pips_slippage()
        test_atr_slippage()
        test_no_slippage()
        test_side_validation()

        print("\n✅ All slippage model tests passed!")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
