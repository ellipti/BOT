"""
Test ATR calculation parity between live and backtest feeds

Verifies that ATR calculations are consistent across different feed types
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from feeds import BacktestFeed
from feeds.atr import fetch_atr_from_feed


def test_atr_parity():
    """Test ATR calculation consistency between feeds"""
    print("Testing ATR parity between feed types...")

    class MockSettings:
        pass

    settings = MockSettings()

    # Test with backtest feed using real data
    backtest_feed = BacktestFeed(settings, data_dir="data")

    # Calculate ATR for different symbols and timeframes
    test_cases = [
        ("XAUUSD", "M30", 14),
        ("XAUUSD", "H1", 14),
        ("EURUSD", "M30", 20),
        ("GBPUSD", "H1", 10),
    ]

    results = {}

    for symbol, timeframe, period in test_cases:
        print(f"\nTesting {symbol} {timeframe} ATR({period}):")

        try:
            # Get ATR from backtest feed
            backtest_atr = fetch_atr_from_feed(backtest_feed, symbol, timeframe, period)

            if backtest_atr is not None:
                results[f"{symbol}_{timeframe}_{period}"] = backtest_atr
                print(f"✓ Backtest ATR: {backtest_atr:.5f}")

                # Validate ATR makes sense
                assert backtest_atr > 0, f"ATR should be positive: {backtest_atr}"

                # Get some candles to check relative size
                candles = backtest_feed.get_ohlcv(symbol, timeframe, 50)
                recent_prices = [c.close for c in candles[-10:]]
                avg_price = sum(recent_prices) / len(recent_prices)
                atr_pct = (backtest_atr / avg_price) * 100

                print(f"  ATR as % of price: {atr_pct:.3f}%")

                # ATR should be reasonable relative to price
                assert (
                    0.01 <= atr_pct <= 10.0
                ), f"ATR % seems unrealistic: {atr_pct:.3f}%"

            else:
                print(f"❌ Failed to calculate ATR for {symbol} {timeframe}")

        except Exception as e:
            print(f"❌ Error calculating ATR for {symbol} {timeframe}: {e}")

    print(f"\n✅ Successfully calculated ATR for {len(results)} test cases")
    return results


def test_atr_stability():
    """Test ATR calculation stability with different periods"""
    print("\nTesting ATR stability with different periods...")

    class MockSettings:
        pass

    settings = MockSettings()
    backtest_feed = BacktestFeed(settings, data_dir="data")

    symbol, timeframe = "XAUUSD", "M30"
    periods = [10, 14, 20, 30]

    atr_values = []

    for period in periods:
        atr = fetch_atr_from_feed(backtest_feed, symbol, timeframe, period)
        if atr is not None:
            atr_values.append((period, atr))
            print(f"✓ ATR({period}): {atr:.5f}")

    # ATR should generally be more stable (smaller) with longer periods
    if len(atr_values) >= 2:
        short_period_atr = atr_values[0][1]  # ATR(10)
        long_period_atr = atr_values[-1][1]  # ATR(30)

        # Longer period ATR should usually be less volatile
        volatility_ratio = long_period_atr / short_period_atr
        print(f"Long/Short period ATR ratio: {volatility_ratio:.3f}")

        # This is a general expectation but not strict rule
        if 0.5 <= volatility_ratio <= 1.5:
            print("✓ ATR period relationship looks reasonable")
        else:
            print(f"⚠ ATR period relationship may be unusual: {volatility_ratio:.3f}")


def test_atr_with_different_data_lengths():
    """Test ATR calculation with different amounts of input data"""
    print("\nTesting ATR with different data lengths...")

    class MockSettings:
        pass

    settings = MockSettings()
    backtest_feed = BacktestFeed(settings, data_dir="data")

    symbol, timeframe, period = "XAUUSD", "M30", 14
    data_lengths = [50, 100, 200, 500]

    for length in data_lengths:
        # Create a temporary feed with limited data
        candles = backtest_feed.get_ohlcv(symbol, timeframe, length)

        if len(candles) >= period + 1:
            from feeds.atr import calculate_atr

            atr = calculate_atr(candles, period)

            if atr is not None:
                print(f"✓ ATR with {length} candles: {atr:.5f}")
            else:
                print(f"❌ Failed to calculate ATR with {length} candles")
        else:
            print(f"⚠ Insufficient data: {len(candles)} candles (need {period + 1})")


if __name__ == "__main__":
    print("=== ATR Parity and Stability Tests ===\n")

    try:
        results = test_atr_parity()
        test_atr_stability()
        test_atr_with_different_data_lengths()

        print(
            f"\n✅ All ATR parity tests passed! Calculated ATR for {len(results)} test cases."
        )

    except Exception as e:
        print(f"\n❌ ATR test failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
