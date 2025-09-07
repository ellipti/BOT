"""
Live MT5 Feed implementation for real-time trading data

Fetches OHLCV data directly from MetaTrader 5 terminal
"""

import logging
from typing import TYPE_CHECKING

import MetaTrader5 as mt5

from .base import BaseFeed, Candle

if TYPE_CHECKING:
    from config.settings import ApplicationSettings

logger = logging.getLogger(__name__)

# MT5 Timeframe mapping
_TIMEFRAME_MAP = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
}


class LiveMT5Feed(BaseFeed):
    """Live MT5 data feed implementation"""

    def __init__(self, settings: "ApplicationSettings"):
        """Initialize MT5 feed with settings"""
        super().__init__(settings)
        self._ensure_mt5_initialized()

    def _ensure_mt5_initialized(self) -> None:
        """Ensure MT5 terminal is connected"""
        if not mt5.initialize():
            error_info = mt5.last_error()
            raise RuntimeError(f"MT5 initialization failed: {error_info}")

        logger.info("MT5 feed initialized successfully")

    def _get_mt5_timeframe(self, timeframe: str) -> int:
        """Convert timeframe string to MT5 constant"""
        if timeframe not in _TIMEFRAME_MAP:
            available = ", ".join(_TIMEFRAME_MAP.keys())
            raise ValueError(
                f"Unsupported timeframe '{timeframe}'. Available: {available}"
            )
        return _TIMEFRAME_MAP[timeframe]

    def get_ohlcv(self, symbol: str, timeframe: str, n: int) -> list[Candle]:
        """
        Get historical OHLCV data from MT5

        Args:
            symbol: Trading symbol (e.g., 'XAUUSD')
            timeframe: Timeframe string (e.g., 'M30', 'H1')
            n: Number of candles to retrieve

        Returns:
            List of candles in chronological order (oldest to newest)

        Raises:
            RuntimeError: If MT5 data fetch fails
        """
        try:
            mt5_timeframe = self._get_mt5_timeframe(timeframe)

            # Fetch rates from MT5 (position 0 = most recent)
            rates = mt5.copy_rates_from_pos(symbol, mt5_timeframe, 0, n)

            if rates is None:
                error_info = mt5.last_error()
                raise RuntimeError(
                    f"MT5 rates fetch failed for {symbol} {timeframe}: {error_info}"
                )

            if len(rates) == 0:
                raise RuntimeError(f"No data returned for {symbol} {timeframe}")

            # Convert to Candle objects (rates come in chronological order)
            candles = []
            for rate in rates:
                candle = Candle(
                    ts=int(rate["time"]),
                    open=float(rate["open"]),
                    high=float(rate["high"]),
                    low=float(rate["low"]),
                    close=float(rate["close"]),
                    volume=float(rate["tick_volume"]),
                )
                candles.append(candle)

            logger.debug(
                f"Fetched {len(candles)} candles for {symbol} {timeframe} from MT5"
            )

            return candles

        except Exception as e:
            logger.error(f"Failed to fetch MT5 data for {symbol} {timeframe}: {e}")
            raise RuntimeError(f"MT5 data fetch error: {e}") from e

    def get_latest_candle(self, symbol: str, timeframe: str) -> Candle:
        """
        Get the most recent completed candle

        Args:
            symbol: Trading symbol (e.g., 'XAUUSD')
            timeframe: Timeframe string (e.g., 'M30', 'H1')

        Returns:
            Latest candle data

        Raises:
            RuntimeError: If MT5 data fetch fails
        """
        candles = self.get_ohlcv(symbol, timeframe, 1)
        return candles[0]
