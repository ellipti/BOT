"""
Comprehensive tests for Feed abstraction system

Tests feed implementations, slippage models, and parity between live/backtest
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

from config.settings import ApplicationSettings, FeedKind, SlippageKind
from feeds import BacktestFeed, Candle, FeedWithSlippage, LiveMT5Feed, create_feed
from feeds.atr import calculate_atr, fetch_atr_from_feed
from models.slippage import FixedPipsSlippage, PercentOfATRSlippage


class TestCandle(unittest.TestCase):
    """Test Candle data model"""

    def test_candle_creation(self):
        """Test valid candle creation"""
        candle = Candle(
            ts=1672531200,  # 2023-01-01 00:00:00 UTC
            open=1950.0,
            high=1955.0,
            low=1945.0,
            close=1952.0,
            volume=1000.0,
        )

        self.assertEqual(candle.ts, 1672531200)
        self.assertEqual(candle.open, 1950.0)
        self.assertEqual(candle.high, 1955.0)
        self.assertEqual(candle.low, 1945.0)
        self.assertEqual(candle.close, 1952.0)
        self.assertEqual(candle.volume, 1000.0)

    def test_candle_immutability(self):
        """Test that candles are immutable"""
        candle = Candle(
            ts=1672531200,
            open=1950.0,
            high=1955.0,
            low=1945.0,
            close=1952.0,
            volume=1000.0,
        )

        with self.assertRaises(AttributeError):  # dataclasses.FrozenInstanceError in Python >= 3.11
            candle.close = 1960.0  # Should fail due to frozen=True


class TestSlippageModels(unittest.TestCase):
    """Test slippage model implementations"""

    def test_fixed_pips_slippage_buy(self):
        """Test fixed pips slippage for BUY orders"""
        slippage = FixedPipsSlippage(pips=2.0, pip_size=0.1)

        original_price = 1950.0
        slipped_price = slippage.apply("BUY", original_price)

        expected_price = 1950.0 + (2.0 * 0.1)  # 1950.2
        self.assertEqual(slipped_price, expected_price)

    def test_fixed_pips_slippage_sell(self):
        """Test fixed pips slippage for SELL orders"""
        slippage = FixedPipsSlippage(pips=2.0, pip_size=0.1)

        original_price = 1950.0
        slipped_price = slippage.apply("SELL", original_price)

        expected_price = 1950.0 - (2.0 * 0.1)  # 1949.8
        self.assertEqual(slipped_price, expected_price)

    def test_atr_slippage_buy(self):
        """Test ATR-based slippage for BUY orders"""
        slippage = PercentOfATRSlippage(atr_percentage=5.0)

        original_price = 1950.0
        atr = 10.0
        slipped_price = slippage.apply("BUY", original_price, atr)

        expected_price = 1950.0 + (10.0 * 0.05)  # 1950.5
        self.assertEqual(slipped_price, expected_price)

    def test_atr_slippage_sell(self):
        """Test ATR-based slippage for SELL orders"""
        slippage = PercentOfATRSlippage(atr_percentage=5.0)

        original_price = 1950.0
        atr = 10.0
        slipped_price = slippage.apply("SELL", original_price, atr)

        expected_price = 1950.0 - (10.0 * 0.05)  # 1949.5
        self.assertEqual(slipped_price, expected_price)

    def test_atr_slippage_requires_atr(self):
        """Test that ATR slippage requires ATR parameter"""
        slippage = PercentOfATRSlippage(atr_percentage=5.0)

        with self.assertRaises(ValueError):
            slippage.apply("BUY", 1950.0, None)

    def test_invalid_side_validation(self):
        """Test validation of order side"""
        slippage = FixedPipsSlippage()

        with self.assertRaises(ValueError):
            slippage.apply("INVALID", 1950.0)


class TestBacktestFeed(unittest.TestCase):
    """Test backtest feed implementation"""

    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_data_dir = Path(self.temp_dir)

        # Create mock settings
        self.settings = MagicMock()
        self.settings.feed.backtest_data_dir = str(self.test_data_dir)

    def tearDown(self):
        """Clean up test environment"""
        import shutil

        shutil.rmtree(self.temp_dir)

    def _create_test_csv(self, filename: str, num_candles: int = 100):
        """Create test CSV file with sample OHLCV data"""
        timestamps = [
            1672531200 + i * 1800 for i in range(num_candles)
        ]  # 30-min intervals

        data = []
        base_price = 1950.0

        for i, ts in enumerate(timestamps):
            # Generate realistic OHLCV data
            open_price = base_price + (i * 0.1) + (i % 10 - 5)
            high_price = open_price + abs((i % 7) * 0.5)
            low_price = open_price - abs((i % 5) * 0.3)
            close_price = open_price + ((i % 11) - 5) * 0.2
            volume = 1000 + (i % 500)

            data.append(
                {
                    "ts": ts,
                    "open": open_price,
                    "high": high_price,
                    "low": low_price,
                    "close": close_price,
                    "volume": volume,
                }
            )

        df = pd.DataFrame(data)
        csv_path = self.test_data_dir / filename
        df.to_csv(csv_path, index=False)

        return csv_path

    def test_backtest_feed_initialization(self):
        """Test backtest feed initialization"""
        feed = BacktestFeed(self.settings, data_dir=str(self.test_data_dir))

        self.assertEqual(feed.data_dir, self.test_data_dir)
        self.assertEqual(feed.settings, self.settings)

    def test_csv_loading_and_caching(self):
        """Test CSV loading and caching mechanism"""
        self._create_test_csv("XAUUSD_M30.csv", 50)

        feed = BacktestFeed(self.settings, data_dir=str(self.test_data_dir))

        # First load should read from file
        candles1 = feed.get_ohlcv("XAUUSD", "M30", 10)
        self.assertEqual(len(candles1), 10)

        # Second load should use cache
        candles2 = feed.get_ohlcv("XAUUSD", "M30", 20)
        self.assertEqual(len(candles2), 20)

        # Verify cache is working
        self.assertIn("XAUUSD_M30", feed._cache)

    def test_get_latest_candle(self):
        """Test getting latest candle"""
        self._create_test_csv("XAUUSD_M30.csv", 50)

        feed = BacktestFeed(self.settings, data_dir=str(self.test_data_dir))
        latest = feed.get_latest_candle("XAUUSD", "M30")

        self.assertIsInstance(latest, Candle)

    def test_file_not_found_error(self):
        """Test error handling for missing CSV files"""
        feed = BacktestFeed(self.settings, data_dir=str(self.test_data_dir))

        with self.assertRaises(RuntimeError):
            feed.get_ohlcv("NONEXISTENT", "M30", 10)


@patch("MetaTrader5.initialize")
@patch("MetaTrader5.copy_rates_from_pos")
class TestLiveMT5Feed(unittest.TestCase):
    """Test live MT5 feed implementation"""

    def setUp(self):
        """Set up test environment"""
        self.settings = MagicMock()

    def test_mt5_feed_initialization(self, mock_copy_rates, mock_initialize):
        """Test MT5 feed initialization"""
        mock_initialize.return_value = True

        feed = LiveMT5Feed(self.settings)

        self.assertEqual(feed.settings, self.settings)
        mock_initialize.assert_called_once()

    def test_mt5_initialization_failure(self, mock_copy_rates, mock_initialize):
        """Test MT5 initialization failure handling"""
        mock_initialize.return_value = False

        with self.assertRaises(RuntimeError):
            LiveMT5Feed(self.settings)

    def test_get_ohlcv_success(self, mock_copy_rates, mock_initialize):
        """Test successful OHLCV data fetch"""
        mock_initialize.return_value = True

        # Mock MT5 rates data
        mock_rates = [
            {
                "time": 1672531200,
                "open": 1950.0,
                "high": 1955.0,
                "low": 1945.0,
                "close": 1952.0,
                "tick_volume": 1000,
            },
            {
                "time": 1672533000,
                "open": 1952.0,
                "high": 1957.0,
                "low": 1948.0,
                "close": 1954.0,
                "tick_volume": 1200,
            },
        ]
        mock_copy_rates.return_value = mock_rates

        feed = LiveMT5Feed(self.settings)
        candles = feed.get_ohlcv("XAUUSD", "M30", 2)

        self.assertEqual(len(candles), 2)
        self.assertIsInstance(candles[0], Candle)
        self.assertEqual(candles[0].ts, 1672531200)
        self.assertEqual(candles[0].close, 1952.0)

    def test_get_ohlcv_failure(self, mock_copy_rates, mock_initialize):
        """Test OHLCV data fetch failure"""
        mock_initialize.return_value = True
        mock_copy_rates.return_value = None

        feed = LiveMT5Feed(self.settings)

        with self.assertRaises(RuntimeError):
            feed.get_ohlcv("INVALID", "M30", 10)

    def test_unsupported_timeframe(self, mock_copy_rates, mock_initialize):
        """Test unsupported timeframe error"""
        mock_initialize.return_value = True

        feed = LiveMT5Feed(self.settings)

        with self.assertRaises(ValueError):
            feed.get_ohlcv("XAUUSD", "INVALID", 10)


class TestATRCalculation(unittest.TestCase):
    """Test ATR calculation functions"""

    def _create_test_candles(self, num_candles: int = 50) -> list[Candle]:
        """Create test candle data"""
        candles = []
        base_price = 1950.0

        for i in range(num_candles):
            ts = 1672531200 + i * 1800  # 30-min intervals
            open_price = base_price + (i * 0.1)
            high_price = open_price + 2.0 + (i % 5)
            low_price = open_price - 1.5 - (i % 3)
            close_price = open_price + ((i % 7) - 3) * 0.5
            volume = 1000.0

            candles.append(
                Candle(
                    ts=ts,
                    open=open_price,
                    high=high_price,
                    low=low_price,
                    close=close_price,
                    volume=volume,
                )
            )

        return candles

    def test_atr_calculation_success(self):
        """Test successful ATR calculation"""
        candles = self._create_test_candles(30)
        atr = calculate_atr(candles, period=14)

        self.assertIsNotNone(atr)
        self.assertGreater(atr, 0)
        self.assertIsInstance(atr, float)

    def test_atr_insufficient_data(self):
        """Test ATR calculation with insufficient data"""
        candles = self._create_test_candles(10)
        atr = calculate_atr(candles, period=14)

        self.assertIsNone(atr)

    def test_fetch_atr_from_feed(self):
        """Test fetching ATR using feed abstraction"""
        candles = self._create_test_candles(50)

        # Mock feed
        mock_feed = MagicMock()
        mock_feed.get_ohlcv.return_value = candles

        atr = fetch_atr_from_feed(mock_feed, "XAUUSD", "M30", period=14)

        self.assertIsNotNone(atr)
        self.assertGreater(atr, 0)
        mock_feed.get_ohlcv.assert_called_once_with("XAUUSD", "M30", 34)  # period + 20


class TestFeedFactory(unittest.TestCase):
    """Test feed factory functions"""

    def test_create_live_feed(self):
        """Test creating live feed"""
        settings = MagicMock()
        settings.feed.feed_kind = FeedKind.LIVE

        with patch("feeds.factory.LiveMT5Feed") as mock_live_feed:
            create_feed(settings)
            mock_live_feed.assert_called_once_with(settings)

    def test_create_backtest_feed(self):
        """Test creating backtest feed"""
        settings = MagicMock()
        settings.feed.feed_kind = FeedKind.BACKTEST
        settings.feed.backtest_data_dir = "test_data"

        with patch("feeds.factory.BacktestFeed") as mock_backtest_feed:
            create_feed(settings)
            mock_backtest_feed.assert_called_once_with(settings, data_dir="test_data")

    def test_unsupported_feed_kind(self):
        """Test unsupported feed kind error"""
        settings = MagicMock()
        settings.feed.feed_kind = "invalid"

        with self.assertRaises(ValueError):
            create_feed(settings)


class TestFeedWithSlippage(unittest.TestCase):
    """Test integrated feed with slippage functionality"""

    def setUp(self):
        """Set up test environment"""
        self.settings = MagicMock()
        self.settings.feed.feed_kind = FeedKind.BACKTEST
        self.settings.feed.backtest_data_dir = "data"
        self.settings.feed.slippage_kind = SlippageKind.FIXED
        self.settings.feed.fixed_slippage_pips = 1.0
        self.settings.feed.pip_size = 0.1
        self.settings.feed.spread_pips = 5.0
        self.settings.feed.fee_per_lot = 2.0

    @patch("feeds.factory.create_feed")
    @patch("feeds.factory.create_slippage_model")
    def test_feed_with_slippage_initialization(self, mock_slippage, mock_feed):
        """Test FeedWithSlippage initialization"""
        mock_feed_instance = MagicMock()
        mock_slippage_instance = MagicMock()
        mock_feed.return_value = mock_feed_instance
        mock_slippage.return_value = mock_slippage_instance

        feed_wrapper = FeedWithSlippage(self.settings)

        self.assertEqual(feed_wrapper.feed, mock_feed_instance)
        self.assertEqual(feed_wrapper.slippage_model, mock_slippage_instance)

        mock_feed.assert_called_once_with(self.settings)
        mock_slippage.assert_called_once_with(self.settings)

    @patch("feeds.factory.create_feed")
    @patch("feeds.factory.create_slippage_model")
    def test_spread_cost_calculation(self, mock_slippage, mock_feed):
        """Test spread cost calculation"""
        mock_feed.return_value = MagicMock()
        mock_slippage.return_value = MagicMock()

        feed_wrapper = FeedWithSlippage(self.settings)

        # BUY should pay half spread
        buy_cost = feed_wrapper.get_spread_cost("BUY")
        expected_buy_cost = (5.0 / 2) * 0.1  # 0.25
        self.assertEqual(buy_cost, expected_buy_cost)

        # SELL should receive half spread less
        sell_cost = feed_wrapper.get_spread_cost("SELL")
        expected_sell_cost = -expected_buy_cost  # -0.25
        self.assertEqual(sell_cost, expected_sell_cost)

    @patch("feeds.factory.create_feed")
    @patch("feeds.factory.create_slippage_model")
    def test_commission_cost_calculation(self, mock_slippage, mock_feed):
        """Test commission cost calculation"""
        mock_feed.return_value = MagicMock()
        mock_slippage.return_value = MagicMock()

        feed_wrapper = FeedWithSlippage(self.settings)

        # Test commission for different lot sizes
        self.assertEqual(feed_wrapper.get_commission_cost(1.0), 2.0)
        self.assertEqual(feed_wrapper.get_commission_cost(0.5), 1.0)
        self.assertEqual(feed_wrapper.get_commission_cost(-1.5), 3.0)  # Absolute value


if __name__ == "__main__":
    unittest.main()
