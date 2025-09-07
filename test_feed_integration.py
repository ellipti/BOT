"""
Test Feed factory and settings integration
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import ApplicationSettings, FeedKind, SlippageKind
from feeds.factory import FeedWithSlippage, create_feed, create_slippage_model
from models.slippage import FixedPipsSlippage, NoSlippage, PercentOfATRSlippage


def test_settings_defaults():
    """Test feed settings default values"""
    print("Testing Feed settings defaults...")

    settings = ApplicationSettings()

    # Check feed defaults
    assert settings.feed.feed_kind == FeedKind.LIVE
    assert settings.feed.slippage_kind == SlippageKind.FIXED
    assert settings.feed.fixed_slippage_pips == 1.0
    assert settings.feed.pip_size == 0.1
    assert settings.feed.spread_pips == 10.0
    assert settings.feed.fee_per_lot == 0.0

    print("✓ Settings defaults are correct")


def test_slippage_model_creation():
    """Test slippage model factory functions"""
    print("Testing slippage model creation...")

    # Test fixed slippage
    settings = ApplicationSettings()
    settings.feed.slippage_kind = SlippageKind.FIXED
    settings.feed.fixed_slippage_pips = 2.0
    settings.feed.pip_size = 0.1

    slippage = create_slippage_model(settings)
    assert isinstance(slippage, FixedPipsSlippage)
    print("✓ Fixed slippage model created")

    # Test ATR slippage
    settings.feed.slippage_kind = SlippageKind.ATR
    settings.feed.atr_slippage_percentage = 3.0

    slippage = create_slippage_model(settings)
    assert isinstance(slippage, PercentOfATRSlippage)
    print("✓ ATR slippage model created")

    # Test no slippage
    settings.feed.slippage_kind = SlippageKind.NONE

    slippage = create_slippage_model(settings)
    assert isinstance(slippage, NoSlippage)
    print("✓ No slippage model created")


def test_backtest_feed_creation():
    """Test backtest feed creation"""
    print("Testing backtest feed creation...")

    settings = ApplicationSettings()
    settings.feed.feed_kind = FeedKind.BACKTEST
    settings.feed.backtest_data_dir = "data"

    feed = create_feed(settings)
    # Should create BacktestFeed
    assert hasattr(feed, "_cache")  # BacktestFeed has cache attribute
    print("✓ Backtest feed created successfully")


def test_feed_with_slippage_integration():
    """Test integrated FeedWithSlippage functionality"""
    print("Testing FeedWithSlippage integration...")

    settings = ApplicationSettings()
    settings.feed.feed_kind = FeedKind.BACKTEST
    settings.feed.slippage_kind = SlippageKind.FIXED
    settings.feed.fixed_slippage_pips = 1.5
    settings.feed.pip_size = 0.1
    settings.feed.spread_pips = 8.0
    settings.feed.fee_per_lot = 3.0

    feed_wrapper = FeedWithSlippage(settings)

    # Test slippage application
    slipped_price = feed_wrapper.apply_slippage("BUY", 1950.0)
    expected = 1950.0 + (1.5 * 0.1)  # 1950.15
    assert slipped_price == expected
    print(f"✓ Slippage applied: 1950.0 -> {slipped_price}")

    # Test spread cost
    buy_spread = feed_wrapper.get_spread_cost("BUY")
    expected_spread = (8.0 / 2) * 0.1  # 0.4
    assert buy_spread == expected_spread
    print(f"✓ BUY spread cost: {buy_spread}")

    sell_spread = feed_wrapper.get_spread_cost("SELL")
    assert sell_spread == -expected_spread
    print(f"✓ SELL spread cost: {sell_spread}")

    # Test commission
    commission = feed_wrapper.get_commission_cost(2.5)
    expected_commission = 3.0 * 2.5  # 7.5
    assert commission == expected_commission
    print(f"✓ Commission cost: {commission}")


def test_environment_variable_override():
    """Test that settings can be overridden via environment variables"""
    print("Testing environment variable overrides...")

    import os

    # Set environment variables
    os.environ["FEED_FEED_KIND"] = "backtest"
    os.environ["FEED_SLIPPAGE_KIND"] = "atr"
    os.environ["FEED_ATR_SLIPPAGE_PERCENTAGE"] = "4.0"
    os.environ["FEED_SPREAD_PIPS"] = "15.0"

    try:
        settings = ApplicationSettings()

        assert settings.feed.feed_kind == FeedKind.BACKTEST
        assert settings.feed.slippage_kind == SlippageKind.ATR
        assert settings.feed.atr_slippage_percentage == 4.0
        assert settings.feed.spread_pips == 15.0

        print("✓ Environment variable overrides work")

    finally:
        # Clean up environment variables
        for key in [
            "FEED_FEED_KIND",
            "FEED_SLIPPAGE_KIND",
            "FEED_ATR_SLIPPAGE_PERCENTAGE",
            "FEED_SPREAD_PIPS",
        ]:
            os.environ.pop(key, None)


if __name__ == "__main__":
    print("=== Feed Factory and Settings Tests ===\n")

    try:
        test_settings_defaults()
        test_slippage_model_creation()
        test_backtest_feed_creation()
        test_feed_with_slippage_integration()
        test_environment_variable_override()

        print("\n✅ All factory and settings tests passed!")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
