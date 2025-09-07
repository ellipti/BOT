"""
Test data generator for backtest feed

Creates sample OHLCV CSV files for testing feed abstraction
"""

import logging
import math
import random
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def generate_realistic_ohlcv(
    start_price: float = 1950.0,
    num_candles: int = 1000,
    timeframe_minutes: int = 30,
    volatility: float = 0.5,
    trend: float = 0.02,
) -> pd.DataFrame:
    """
    Generate realistic OHLCV data with trend and volatility

    Args:
        start_price: Starting price
        num_candles: Number of candles to generate
        timeframe_minutes: Timeframe in minutes
        volatility: Volatility factor (higher = more volatile)
        trend: Trend factor (positive = uptrend, negative = downtrend)

    Returns:
        DataFrame with OHLCV data
    """
    data = []
    current_price = start_price

    # Start timestamp (2023-01-01)
    start_ts = 1672531200
    interval_seconds = timeframe_minutes * 60

    for i in range(num_candles):
        timestamp = start_ts + i * interval_seconds

        # Add trend and random walk
        price_change = trend + random.normalvariate(0, volatility)
        current_price = max(
            current_price + price_change, 1.0
        )  # Prevent negative prices

        # Generate OHLC from current price
        open_price = current_price

        # High/Low with realistic behavior
        high_range = random.uniform(0.5, 3.0) * volatility
        low_range = random.uniform(0.5, 3.0) * volatility

        high_price = open_price + high_range
        low_price = max(open_price - low_range, 1.0)

        # Close price within high/low range
        close_price = random.uniform(low_price, high_price)
        current_price = close_price  # Update for next candle

        # Volume with some randomness
        base_volume = 1000
        volume = max(base_volume + random.normalvariate(0, 300), 100)

        data.append(
            {
                "ts": timestamp,
                "open": round(open_price, 2),
                "high": round(high_price, 2),
                "low": round(low_price, 2),
                "close": round(close_price, 2),
                "volume": round(volume),
            }
        )

    return pd.DataFrame(data)


def create_sample_data(data_dir: str = "data"):
    """
    Create sample CSV data files for different symbols and timeframes

    Args:
        data_dir: Directory to save CSV files
    """
    data_path = Path(data_dir)
    data_path.mkdir(exist_ok=True)

    # Configuration for different instruments
    instruments = {
        "XAUUSD": {"start_price": 1950.0, "volatility": 2.0, "trend": 0.05},
        "EURUSD": {"start_price": 1.0850, "volatility": 0.0015, "trend": -0.0002},
        "GBPUSD": {"start_price": 1.2150, "volatility": 0.0018, "trend": 0.0001},
    }

    timeframes = ["M30", "H1", "H4"]
    timeframe_minutes = {"M30": 30, "H1": 60, "H4": 240}

    for symbol, config in instruments.items():
        for tf in timeframes:
            logger.info(f"Generating {symbol}_{tf} data...")

            # Generate more data for smaller timeframes
            num_candles = 2000 if tf == "M30" else 1500 if tf == "H1" else 1000

            df = generate_realistic_ohlcv(
                start_price=config["start_price"],
                num_candles=num_candles,
                timeframe_minutes=timeframe_minutes[tf],
                volatility=config["volatility"],
                trend=config["trend"],
            )

            # Save to CSV
            filename = f"{symbol}_{tf}.csv"
            filepath = data_path / filename
            df.to_csv(filepath, index=False)

            logger.info(f"Saved {len(df)} candles to {filepath}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    create_sample_data()
