"""
Feed-compatible ATR calculation utilities

Calculates ATR using Feed abstraction for live/backtest parity
"""

import logging
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from feeds.base import Candle, Feed

logger = logging.getLogger(__name__)


def calculate_atr(candles: list["Candle"], period: int = 14) -> float | None:
    """
    Calculate Average True Range from candle data

    Args:
        candles: List of candles in chronological order (oldest to newest)
        period: ATR calculation period (default: 14)

    Returns:
        ATR value or None if calculation failed

    Note:
        Requires at least period + 1 candles for accurate calculation
    """
    if len(candles) < period + 1:
        logger.warning(
            f"Insufficient candles for ATR calculation: {len(candles)} < {period + 1}"
        )
        return None

    try:
        # Convert candles to DataFrame
        data = []
        for candle in candles:
            data.append(
                {
                    "high": candle.high,
                    "low": candle.low,
                    "close": candle.close,
                }
            )

        df = pd.DataFrame(data)

        # Calculate True Range components
        df["hl"] = df["high"] - df["low"]  # High - Low
        df["hcp"] = abs(df["high"] - df["close"].shift(1))  # |High - Previous Close|
        df["lcp"] = abs(df["low"] - df["close"].shift(1))  # |Low - Previous Close|

        # True Range = max(HL, HCP, LCP)
        df["tr"] = df[["hl", "hcp", "lcp"]].max(axis=1)

        # ATR = EMA of True Range
        atr_series = df["tr"].ewm(span=period, adjust=False).mean()

        # Get the most recent ATR value
        current_atr = atr_series.iloc[-1]

        logger.debug(
            f"Calculated ATR({period}): {current_atr:.5f} from {len(candles)} candles"
        )

        return float(current_atr) if pd.notna(current_atr) else None

    except Exception as e:
        logger.error(f"ATR calculation failed: {e}")
        return None


def fetch_atr_from_feed(
    feed: "Feed", symbol: str, timeframe: str, period: int = 14
) -> float | None:
    """
    Fetch ATR using Feed abstraction

    Args:
        feed: Feed instance (live or backtest)
        symbol: Trading symbol (e.g., 'XAUUSD')
        timeframe: Timeframe string (e.g., 'M30', 'H1')
        period: ATR calculation period (default: 14)

    Returns:
        ATR value or None if calculation failed
    """
    try:
        # Fetch enough candles for ATR calculation
        bars_needed = period + 20  # Extra buffer for accurate calculation
        candles = feed.get_ohlcv(symbol, timeframe, bars_needed)

        if len(candles) < period + 1:
            logger.error(
                f"Insufficient data for ATR calculation: {symbol} {timeframe} "
                f"({len(candles)} candles, need {period + 1})"
            )
            return None

        return calculate_atr(candles, period)

    except Exception as e:
        logger.error(f"Failed to fetch ATR from feed: {e}")
        return None
