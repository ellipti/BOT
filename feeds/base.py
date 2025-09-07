"""
Base feed abstractions and data models

Provides unified interface for live and backtesting data feeds
"""

from abc import ABC, abstractmethod
from typing import Protocol

from pydantic import BaseModel, Field


class Candle(BaseModel):
    """OHLCV candle data model"""

    ts: int = Field(..., description="Unix timestamp (UTC seconds)")
    open: float = Field(..., description="Open price")
    high: float = Field(..., description="High price")
    low: float = Field(..., description="Low price")
    close: float = Field(..., description="Close price")
    volume: float = Field(..., description="Tick volume")

    class Config:
        """Pydantic model configuration"""

        frozen = True  # Immutable candles
        extra = "forbid"  # Strict validation


class Feed(Protocol):
    """Feed protocol for unified data access interface"""

    def get_latest_candle(self, symbol: str, timeframe: str) -> Candle:
        """
        Get the most recent completed candle

        Args:
            symbol: Trading symbol (e.g., 'XAUUSD')
            timeframe: Timeframe string (e.g., 'M30', 'H1')

        Returns:
            Latest candle data

        Raises:
            RuntimeError: If data fetch fails
        """
        ...

    def get_ohlcv(self, symbol: str, timeframe: str, n: int) -> list[Candle]:
        """
        Get historical OHLCV data

        Args:
            symbol: Trading symbol (e.g., 'XAUUSD')
            timeframe: Timeframe string (e.g., 'M30', 'H1')
            n: Number of candles to retrieve (most recent first)

        Returns:
            List of candles in chronological order (oldest to newest)

        Raises:
            RuntimeError: If data fetch fails
        """
        ...


class BaseFeed(ABC):
    """Abstract base class for feed implementations"""

    def __init__(self, settings):
        """Initialize feed with settings"""
        self.settings = settings

    @abstractmethod
    def get_latest_candle(self, symbol: str, timeframe: str) -> Candle:
        """Get latest candle - must be implemented by subclasses"""
        pass

    @abstractmethod
    def get_ohlcv(self, symbol: str, timeframe: str, n: int) -> list[Candle]:
        """Get historical candles - must be implemented by subclasses"""
        pass
