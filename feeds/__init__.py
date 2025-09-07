"""
Feed abstraction package for unified data access
"""

from .backtest import BacktestFeed
from .base import Candle, Feed
from .factory import FeedWithSlippage, create_feed, create_slippage_model
from .live_mt5 import LiveMT5Feed

__all__ = [
    "Candle",
    "Feed",
    "LiveMT5Feed",
    "BacktestFeed",
    "create_feed",
    "create_slippage_model",
    "FeedWithSlippage",
]
