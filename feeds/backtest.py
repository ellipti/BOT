"""
Backtest feed implementation for historical data replay

Reads CSV data files exported from MT5 or other sources
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from .base import BaseFeed, Candle

if TYPE_CHECKING:
    from config.settings import ApplicationSettings

logger = logging.getLogger(__name__)


class BacktestFeed(BaseFeed):
    """Backtest feed for historical data replay"""

    def __init__(self, settings: "ApplicationSettings", data_dir: str = "data"):
        """
        Initialize backtest feed

        Args:
            settings: Application settings
            data_dir: Directory containing CSV data files
        """
        super().__init__(settings)
        self.data_dir = Path(data_dir)
        self._cache: dict[str, pd.DataFrame] = {}

        if not self.data_dir.exists():
            self.data_dir.mkdir(parents=True, exist_ok=True)
            logger.warning(f"Data directory created: {self.data_dir}")

    def _load_csv_data(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """
        Load CSV data file for symbol and timeframe

        Expected CSV format (MT5 export format):
        - Columns: Date,Time,Open,High,Low,Close,Tick Volume
        - Or alternatively: timestamp,open,high,low,close,volume

        Args:
            symbol: Trading symbol (e.g., 'XAUUSD')
            timeframe: Timeframe string (e.g., 'M30', 'H1')

        Returns:
            DataFrame with OHLCV data

        Raises:
            RuntimeError: If CSV file not found or invalid format
        """
        cache_key = f"{symbol}_{timeframe}"

        if cache_key in self._cache:
            return self._cache[cache_key]

        # Try multiple file name patterns
        file_patterns = [
            f"{symbol}_{timeframe}.csv",
            f"{symbol.lower()}_{timeframe.lower()}.csv",
            f"{symbol}_{timeframe}_export.csv",
        ]

        csv_file = None
        for pattern in file_patterns:
            potential_file = self.data_dir / pattern
            if potential_file.exists():
                csv_file = potential_file
                break

        if csv_file is None:
            available_files = list(self.data_dir.glob("*.csv"))
            available_names = [f.name for f in available_files]
            raise RuntimeError(
                f"CSV file not found for {symbol}_{timeframe}. "
                f"Looked for: {file_patterns}. "
                f"Available files: {available_names}"
            )

        try:
            df = pd.read_csv(csv_file)

            # Handle different CSV formats
            df = self._normalize_csv_columns(df)

            # Ensure proper data types
            df = self._validate_csv_data(df, symbol, timeframe)

            # Cache the processed data
            self._cache[cache_key] = df

            logger.info(
                f"Loaded {len(df)} candles for {symbol} {timeframe} from {csv_file}"
            )

            return df

        except Exception as e:
            raise RuntimeError(f"Failed to load CSV data from {csv_file}: {e}") from e

    def _normalize_csv_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize CSV column names to standard format

        Handles both MT5 export format and generic OHLCV format
        """
        # Convert column names to lowercase for matching
        columns_lower = [col.lower() for col in df.columns]

        # Map various column name patterns
        column_mapping = {}

        # Handle MT5 export format: Date, Time, Open, High, Low, Close, Tick Volume
        if "date" in columns_lower and "time" in columns_lower:
            date_idx = columns_lower.index("date")
            time_idx = columns_lower.index("time")

            # Combine date and time columns
            df_copy = df.copy()
            df_copy["datetime"] = pd.to_datetime(
                df_copy.iloc[:, date_idx].astype(str)
                + " "
                + df_copy.iloc[:, time_idx].astype(str)
            )
            df_copy["timestamp"] = df_copy["datetime"].astype(int) // 10**9

            # Drop original date/time columns and use the combined timestamp
            df = df_copy.drop(columns=[df.columns[date_idx], df.columns[time_idx]])

        # Standard column mapping
        for i, col in enumerate(columns_lower):
            original_col = df.columns[i]

            if col in ["timestamp", "ts", "time"]:
                column_mapping[original_col] = "ts"
            elif col in ["open", "o"]:
                column_mapping[original_col] = "open"
            elif col in ["high", "h"]:
                column_mapping[original_col] = "high"
            elif col in ["low", "l"]:
                column_mapping[original_col] = "low"
            elif col in ["close", "c"]:
                column_mapping[original_col] = "close"
            elif col in ["volume", "vol", "tick volume", "tick_volume", "v"]:
                column_mapping[original_col] = "volume"

        # Apply column mapping
        df = df.rename(columns=column_mapping)

        return df

    def _validate_csv_data(
        self, df: pd.DataFrame, symbol: str, timeframe: str
    ) -> pd.DataFrame:
        """
        Validate and clean CSV data

        Args:
            df: Raw DataFrame
            symbol: Trading symbol for error context
            timeframe: Timeframe for error context

        Returns:
            Cleaned DataFrame

        Raises:
            RuntimeError: If required columns missing or data invalid
        """
        required_columns = ["ts", "open", "high", "low", "close", "volume"]
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            available = list(df.columns)
            raise RuntimeError(
                f"Missing required columns in {symbol}_{timeframe} CSV: {missing_columns}. "
                f"Available columns: {available}"
            )

        # Convert data types
        try:
            df["ts"] = pd.to_numeric(df["ts"]).astype(int)
            df["open"] = pd.to_numeric(df["open"]).astype(float)
            df["high"] = pd.to_numeric(df["high"]).astype(float)
            df["low"] = pd.to_numeric(df["low"]).astype(float)
            df["close"] = pd.to_numeric(df["close"]).astype(float)
            df["volume"] = pd.to_numeric(df["volume"]).astype(float)
        except Exception as e:
            raise RuntimeError(
                f"Invalid data types in {symbol}_{timeframe} CSV: {e}"
            ) from e

        # Sort by timestamp
        df = df.sort_values("ts").reset_index(drop=True)

        # Remove duplicate timestamps
        before_count = len(df)
        df = df.drop_duplicates(subset=["ts"]).reset_index(drop=True)
        after_count = len(df)

        if before_count != after_count:
            logger.warning(
                f"Removed {before_count - after_count} duplicate timestamps "
                f"from {symbol}_{timeframe}"
            )

        # Basic validation
        if len(df) == 0:
            raise RuntimeError(f"No valid data in {symbol}_{timeframe} CSV")

        return df

    def get_ohlcv(self, symbol: str, timeframe: str, n: int) -> list[Candle]:
        """
        Get historical OHLCV data from CSV

        Args:
            symbol: Trading symbol (e.g., 'XAUUSD')
            timeframe: Timeframe string (e.g., 'M30', 'H1')
            n: Number of candles to retrieve (most recent)

        Returns:
            List of candles in chronological order (oldest to newest)

        Raises:
            RuntimeError: If CSV file not found or data invalid
        """
        try:
            df = self._load_csv_data(symbol, timeframe)

            # Get the most recent n candles
            if n > len(df):
                logger.warning(
                    f"Requested {n} candles but only {len(df)} available "
                    f"for {symbol} {timeframe}"
                )
                n = len(df)

            # Take the last n rows (most recent)
            recent_data = df.tail(n)

            # Convert to Candle objects
            candles = []
            for _, row in recent_data.iterrows():
                candle = Candle(
                    ts=int(row["ts"]),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["volume"]),
                )
                candles.append(candle)

            logger.debug(
                f"Fetched {len(candles)} candles for {symbol} {timeframe} from CSV"
            )

            return candles

        except Exception as e:
            logger.error(f"Failed to fetch CSV data for {symbol} {timeframe}: {e}")
            raise RuntimeError(f"CSV data fetch error: {e}") from e

    def get_latest_candle(self, symbol: str, timeframe: str) -> Candle:
        """
        Get the most recent candle from CSV data

        Args:
            symbol: Trading symbol (e.g., 'XAUUSD')
            timeframe: Timeframe string (e.g., 'M30', 'H1')

        Returns:
            Latest candle data

        Raises:
            RuntimeError: If CSV data not available
        """
        candles = self.get_ohlcv(symbol, timeframe, 1)
        return candles[0]
