"""
Feed factory for creating appropriate feed instances

Provides unified interface for creating live or backtest feeds based on configuration
"""

import logging
from typing import TYPE_CHECKING

from models.slippage import FixedPipsSlippage, NoSlippage, PercentOfATRSlippage

from .backtest import BacktestFeed
from .base import Feed
from .live_mt5 import LiveMT5Feed

if TYPE_CHECKING:
    from config.settings import ApplicationSettings
    from models.slippage import SlippageModel

logger = logging.getLogger(__name__)


def create_feed(settings: "ApplicationSettings") -> Feed:
    """
    Create appropriate feed instance based on settings

    Args:
        settings: Application settings containing feed configuration

    Returns:
        Feed instance (LiveMT5Feed or BacktestFeed)

    Raises:
        ValueError: If unsupported feed kind specified
    """
    feed_kind = settings.feed.feed_kind

    if feed_kind == "live":
        logger.info("Creating LiveMT5Feed for real-time data")
        return LiveMT5Feed(settings)

    elif feed_kind == "backtest":
        data_dir = settings.feed.backtest_data_dir
        logger.info(f"Creating BacktestFeed with data directory: {data_dir}")
        return BacktestFeed(settings, data_dir=data_dir)

    else:
        raise ValueError(f"Unsupported feed kind: {feed_kind}")


def create_slippage_model(settings: "ApplicationSettings") -> "SlippageModel":
    """
    Create appropriate slippage model based on settings

    Args:
        settings: Application settings containing slippage configuration

    Returns:
        SlippageModel instance

    Raises:
        ValueError: If unsupported slippage kind specified
    """
    slippage_kind = settings.feed.slippage_kind

    if slippage_kind == "fixed":
        pips = settings.feed.fixed_slippage_pips
        pip_size = settings.feed.pip_size
        logger.info(f"Creating FixedPipsSlippage: {pips} pips")
        return FixedPipsSlippage(pips=pips, pip_size=pip_size)

    elif slippage_kind == "atr":
        percentage = settings.feed.atr_slippage_percentage
        logger.info(f"Creating ATR-based slippage: {percentage}% of ATR")
        return PercentOfATRSlippage(atr_percentage=percentage)

    elif slippage_kind == "none":
        logger.info("Creating NoSlippage model (perfect execution)")
        return NoSlippage()

    else:
        raise ValueError(f"Unsupported slippage kind: {slippage_kind}")


class FeedWithSlippage:
    """
    Wrapper that combines feed and slippage model for unified interface

    This class provides a unified interface for accessing market data
    and applying realistic execution models during backtesting.
    """

    def __init__(self, settings: "ApplicationSettings"):
        """
        Initialize feed with slippage model

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.feed = create_feed(settings)
        self.slippage_model = create_slippage_model(settings)

        # Cache feed configuration info
        self.spread_pips = settings.feed.spread_pips
        self.fee_per_lot = settings.feed.fee_per_lot
        self.pip_size = settings.feed.pip_size

        logger.info(
            f"FeedWithSlippage initialized: "
            f"feed={settings.feed.feed_kind}, "
            f"slippage={settings.feed.slippage_kind}, "
            f"spread={self.spread_pips} pips, "
            f"fee={self.fee_per_lot}/lot"
        )

    def get_latest_candle(self, symbol: str, timeframe: str):
        """Get latest candle from underlying feed"""
        return self.feed.get_latest_candle(symbol, timeframe)

    def get_ohlcv(self, symbol: str, timeframe: str, n: int):
        """Get historical candles from underlying feed"""
        return self.feed.get_ohlcv(symbol, timeframe, n)

    def apply_slippage(
        self, side: str, price: float, atr: float | None = None
    ) -> float:
        """
        Apply slippage to order price

        Args:
            side: Order side ('BUY' or 'SELL')
            price: Original order price
            atr: Current ATR (required for ATR-based slippage)

        Returns:
            Price after slippage adjustment
        """
        return self.slippage_model.apply(side, price, atr)

    def get_spread_cost(self, side: str) -> float:
        """
        Get spread cost in price units

        Args:
            side: Order side ('BUY' pays ask, 'SELL' receives bid)

        Returns:
            Spread cost in price units
        """
        spread_cost = (self.spread_pips / 2) * self.pip_size

        if side.upper() == "BUY":
            return spread_cost  # BUY pays half spread above mid
        else:  # SELL
            return -spread_cost  # SELL receives half spread below mid

    def get_commission_cost(self, lot_size: float) -> float:
        """
        Get commission cost for trade

        Args:
            lot_size: Position size in lots

        Returns:
            Commission cost in account currency
        """
        return self.fee_per_lot * abs(lot_size)
