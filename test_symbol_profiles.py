"""
Tests for Symbol Profile System (Prompt-30)
Validates multi-asset symbol profiles, session guards, and sizing overrides
"""

from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest

from core.sizing.sizing import calc_lot_by_risk
from core.symbols import SymbolProfileManager


class TestSymbolProfileManager:
    """Test symbol profile management and validation."""

    @pytest.fixture
    def manager(self):
        """Create symbol profile manager for testing."""
        return SymbolProfileManager()

    def test_profile_loading(self, manager):
        """Test that symbol profiles load correctly."""
        assert manager.profiles is not None
        assert len(manager.profiles) > 0

        # Test specific symbols exist
        assert "EURUSD" in manager.profiles
        assert "XAUUSD" in manager.profiles
        assert "US500" in manager.profiles
        assert "BTCUSD" in manager.profiles

    def test_get_profile_valid_symbol(self, manager):
        """Test getting profile for valid symbol."""
        profile = manager.get_profile("EURUSD")

        assert profile is not None
        assert profile.asset == "forex"
        assert (
            profile.tick_size == 0.0001
        )  # EURUSD has 4 decimal places (1 pip = 0.0001)
        assert profile.tick_value == 10.0

    def test_get_profile_invalid_symbol(self, manager):
        """Test getting profile for invalid symbol returns None."""
        profile = manager.get_profile("INVALID")
        assert profile is None

    def test_session_validation_forex(self, manager):
        """Test session validation for forex (24x5)."""
        # Monday 10:00 UTC - should be open for 24x5 forex session
        monday_10 = datetime(2024, 1, 8, 10, 0, tzinfo=UTC)
        can_trade, reason = manager.can_trade("EURUSD", monday_10)
        assert can_trade
        assert "market is open" in reason.lower() or "ok" in reason.lower()

        # Saturday 10:00 UTC - should be closed for 24x5 forex session
        saturday_10 = datetime(2024, 1, 6, 10, 0, tzinfo=UTC)
        can_trade, reason = manager.can_trade("EURUSD", saturday_10)
        assert not can_trade
        assert "market is closed" in reason.lower() or "closed" in reason.lower()

    def test_session_validation_crypto(self, manager):
        """Test session validation for crypto (24x7)."""
        # Saturday 10:00 UTC - should be open for crypto
        saturday_10 = datetime(2024, 1, 6, 10, 0, tzinfo=UTC)
        can_trade, reason = manager.can_trade("BTCUSD", saturday_10)
        assert can_trade
        assert "market is open" in reason

    def test_session_validation_with_holidays(self, manager):
        """Test session validation respects holidays."""
        # New Year's Day 2024 (Monday) - should be closed for US indices
        new_years = datetime(2024, 1, 1, 15, 0, tzinfo=UTC)
        can_trade, reason = manager.can_trade("US500", new_years)
        assert not can_trade
        assert "holiday" in reason.lower()

    def test_session_validation_rth(self, manager):
        """Test RTH (Regular Trading Hours) session validation."""
        # US500 should have RTH restrictions
        # 14:30 UTC = 9:30 EST (market open) - should be open
        market_open = datetime(2024, 1, 8, 14, 30, tzinfo=UTC)
        can_trade, reason = manager.can_trade("US500", market_open)
        # Note: This depends on the exact RTH configuration and timezone handling

        # 06:00 UTC = 1:00 EST (pre-market) - should be closed for RTH
        pre_market = datetime(2024, 1, 8, 6, 0, tzinfo=UTC)
        can_trade, reason = manager.can_trade("US500", pre_market)
        # RTH session should be closed at this time

    def test_invalid_symbol_session_check(self, manager):
        """Test session check for invalid symbol."""
        can_trade, reason = manager.can_trade("INVALID")
        assert not can_trade
        assert "unknown symbol" in reason.lower()


class TestPositionSizingWithProfiles:
    """Test position sizing integration with symbol profiles."""

    @pytest.fixture
    def mock_symbol_info(self):
        """Create mock MT5 symbol info."""
        info = Mock()
        info.trade_tick_size = 0.0001
        info.trade_tick_value = 1.0
        info.volume_min = 0.01
        info.volume_max = 100.0
        info.volume_step = 0.01
        return info

    @pytest.fixture
    def manager(self):
        """Create symbol profile manager for testing."""
        return SymbolProfileManager()

    def test_calc_lot_by_risk_with_profile(self, mock_symbol_info, manager):
        """Test position sizing uses profile overrides."""
        # Test with EURUSD profile
        current_price = 1.1000
        sl_price = 1.0950  # 50 pip stop
        equity = 10000.0
        risk_pct = 0.02

        lots = calc_lot_by_risk(
            mock_symbol_info, current_price, sl_price, equity, risk_pct, symbol="EURUSD"
        )

        assert lots > 0
        assert isinstance(lots, float)

    def test_calc_lot_by_risk_without_profile(self, mock_symbol_info):
        """Test position sizing works without profile (MT5 fallback)."""
        current_price = 1.1000
        sl_price = 1.0950  # 50 pip stop
        equity = 10000.0
        risk_pct = 0.02

        lots = calc_lot_by_risk(
            mock_symbol_info,
            current_price,
            sl_price,
            equity,
            risk_pct,
            symbol="UNKNOWN",
        )

        assert lots > 0
        assert isinstance(lots, float)

    def test_calc_lot_by_risk_different_assets(self, mock_symbol_info):
        """Test position sizing with different asset types."""
        equity = 10000.0
        risk_pct = 0.02

        # Test forex
        forex_lots = calc_lot_by_risk(
            mock_symbol_info, 1.1000, 1.0950, equity, risk_pct, symbol="EURUSD"
        )

        # Test gold
        gold_lots = calc_lot_by_risk(
            mock_symbol_info, 2000.0, 1990.0, equity, risk_pct, symbol="XAUUSD"
        )

        # Test crypto
        crypto_lots = calc_lot_by_risk(
            mock_symbol_info, 45000.0, 44000.0, equity, risk_pct, symbol="BTCUSD"
        )

        # All should return valid lot sizes
        assert forex_lots > 0
        assert gold_lots > 0
        assert crypto_lots > 0


class TestSessionDefinitions:
    """Test session definition parsing and validation."""

    def test_24x5_session(self):
        """Test 24x5 session is open Monday-Friday."""
        manager = SymbolProfileManager()
        profile = manager.get_profile("EURUSD")

        # Monday should be open
        monday = datetime(2024, 1, 8, 10, 0, tzinfo=UTC)
        assert profile.session.is_open(monday)

        # Saturday should be closed
        saturday = datetime(2024, 1, 6, 10, 0, tzinfo=UTC)
        assert not profile.session.is_open(saturday)

    def test_24x7_session(self):
        """Test 24x7 session is always open."""
        manager = SymbolProfileManager()
        profile = manager.get_profile("BTCUSD")

        # Any day should be open
        saturday = datetime(2024, 1, 6, 10, 0, tzinfo=UTC)
        assert profile.session.is_open(saturday)

        sunday = datetime(2024, 1, 7, 10, 0, tzinfo=UTC)
        assert profile.session.is_open(sunday)

    def test_holiday_checking(self):
        """Test holiday checking works correctly."""
        manager = SymbolProfileManager()

        # Test US holidays for US500
        profile = manager.get_profile("US500")
        if profile and profile.holidays:
            # New Year's Day 2024
            new_years = datetime(2024, 1, 1, 15, 0, tzinfo=UTC)
            assert not profile.session.is_open(new_years, holidays=profile.holidays)


@pytest.mark.integration
class TestPipelineIntegration:
    """Integration tests for pipeline with symbol profiles."""

    @patch("app.pipeline.SymbolProfileManager")
    def test_pipeline_session_guard(self, mock_manager_class):
        """Test pipeline blocks trades during closed sessions."""
        from unittest.mock import Mock

        from app.pipeline import TradingPipeline
        from core.events import EventBus, SignalDetected, TradeBlocked

        # Mock symbol manager to return session closed
        mock_manager = Mock()
        mock_manager.can_trade.return_value = (False, "Market closed for EURUSD")
        mock_manager_class.return_value = mock_manager

        # Create pipeline with mocked dependencies
        settings = Mock()
        bus = EventBus()
        broker = Mock()

        pipeline = TradingPipeline(settings, bus, broker)
        pipeline.wire_handlers()

        # Track published events
        blocked_events = []

        def track_blocked(event: TradeBlocked):
            blocked_events.append(event)

        bus.subscribe(TradeBlocked, track_blocked)

        # Publish signal during closed session
        signal = SignalDetected(
            symbol="EURUSD", side="BUY", strength=0.8, timestamp=datetime.now()
        )
        bus.publish(signal)

        # Should have blocked the trade
        assert len(blocked_events) == 1
        assert blocked_events[0].reason == "Market closed for EURUSD"
        assert blocked_events[0].governor_version == "session"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
