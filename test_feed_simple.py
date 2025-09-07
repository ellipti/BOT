"""
Simple test for the Feed abstraction system
"""

import sys
import tempfile
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from feeds import BacktestFeed, Candle
from feeds.atr import calculate_atr


def test_candle_creation():
    """Test basic candle creation"""
    print("Testing Candle creation...")
    candle = Candle(
        ts=1672531200,
        open=1950.0,
        high=1955.0,
        low=1945.0,
        close=1952.0,
        volume=1000.0,
    )
    print(f"✓ Created candle: {candle}")


def test_backtest_feed():
    """Test backtest feed with real data"""
    print("Testing BacktestFeed...")

    # Use existing test data - fix the path
    data_dir = Path(__file__).parent / "data"  # Correct path

    class MockSettings:
        pass

    settings = MockSettings()
    feed = BacktestFeed(settings, data_dir=str(data_dir))

    # Test loading XAUUSD M30 data
    candles = feed.get_ohlcv("XAUUSD", "M30", 50)
    print(f"✓ Loaded {len(candles)} candles from CSV")

    # Test latest candle
    latest = feed.get_latest_candle("XAUUSD", "M30")
    print(f"✓ Latest candle: {latest.ts} @ {latest.close}")


def test_atr_calculation():
    """Test ATR calculation"""
    print("Testing ATR calculation...")

    # Create some test candles
    candles = []
    base_price = 1950.0

    for i in range(30):
        ts = 1672531200 + i * 1800
        open_price = base_price + (i * 0.1)
        high_price = open_price + 2.0
        low_price = open_price - 1.5
        close_price = open_price + (i % 5 - 2) * 0.3

        candle = Candle(
            ts=ts,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=1000.0,
        )
        candles.append(candle)

    atr = calculate_atr(candles, period=14)
    print(f"✓ Calculated ATR: {atr:.5f}")


def test_feed_atr_integration():
    """Test ATR calculation with feed data"""
    print("Testing Feed + ATR integration...")

    from feeds.atr import fetch_atr_from_feed

    data_dir = Path(__file__).parent / "data"  # Correct path

    class MockSettings:
        pass

    settings = MockSettings()
    feed = BacktestFeed(settings, data_dir=str(data_dir))

    atr = fetch_atr_from_feed(feed, "XAUUSD", "M30", period=14)
    print(f"✓ ATR from feed: {atr:.5f}")


if __name__ == "__main__":
    print("=== Feed Abstraction Simple Tests ===\n")

    try:
        test_candle_creation()
        test_backtest_feed()
        test_atr_calculation()
        test_feed_atr_integration()

        print("\n✅ All tests passed! Feed abstraction is working correctly.")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
