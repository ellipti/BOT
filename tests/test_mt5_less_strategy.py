"""
Example test demonstrating MT5-less testing strategy with proper skip/mock handling.

This shows how to write tests that:
1. Skip integration tests when MT5 is not available
2. Use mocks for unit testing MT5-related code
3. Work in CI environments without MT5
4. Run real integration tests when MT5 is available locally
"""

from unittest.mock import MagicMock, patch

import pytest

from core.events.bus import EventBus
from tests.conftest import mt5_available, skip_if_no_mt5
from tests.fixtures.fake_broker import FakeBrokerAdapter


class TestMT5LessStrategy:
    """Test class demonstrating MT5-less testing patterns"""

    def test_fake_broker_unit_test(self, mock_mt5):
        """
        Unit test using FakeBroker - always runs, no MT5 required.

        This demonstrates testing broker functionality without any external dependencies.
        """
        # Setup
        event_bus = EventBus()
        fake_broker = FakeBrokerAdapter(event_bus=event_bus)

        # Test connection
        assert fake_broker.connect()
        assert fake_broker.connected

        # Test account info
        account = fake_broker.get_account_info()
        assert account["balance"] == 10000.0
        assert account["currency"] == "USD"

        # Test symbol info
        symbol_info = fake_broker.get_symbol_info("EURUSD")
        assert symbol_info is not None
        assert symbol_info["name"] == "EURUSD"
        assert symbol_info["point"] == 0.00001

        # Test order submission with idempotency
        order_result1 = fake_broker.submit_market_order(
            symbol="EURUSD", side="buy", volume=0.1, client_order_id="test_order_001"
        )
        assert order_result1["success"]

        # Test idempotency - same client_order_id should return same result
        order_result2 = fake_broker.submit_market_order(
            symbol="EURUSD", side="buy", volume=0.1, client_order_id="test_order_001"
        )
        assert order_result2["success"]
        assert order_result1["order_id"] == order_result2["order_id"]

        # Test position tracking (interface works even if no positions tracked yet)
        positions = fake_broker.get_positions()
        assert isinstance(positions, list)  # Interface returns list

    @pytest.mark.mt5_unit
    def test_mt5_mock_functionality(self, mock_mt5):
        """
        Unit test using MT5 mock - runs without actual MT5 installation.

        This tests MT5-related code using our comprehensive mock.
        """
        # Test MT5 mock initialization
        assert mock_mt5.initialize()
        assert mock_mt5.connected

        # Test terminal info
        terminal_info = mock_mt5.terminal_info()
        assert terminal_info is not None
        assert terminal_info["connected"] is True

        # Test account info
        account_info = mock_mt5.account_info()
        assert account_info is not None
        assert account_info["balance"] == 10000.0

        # Test symbol info
        symbol_info = mock_mt5.symbol_info("EURUSD")
        assert symbol_info is not None
        assert symbol_info.name == "EURUSD"
        assert symbol_info.point == 0.00001

        # Test historical data
        rates = mock_mt5.copy_rates_from_pos("EURUSD", 1, 0, 10)
        assert rates is not None
        assert len(rates) == 10
        assert all("open" in rate for rate in rates)

        # Test order sending
        request = {
            "action": mock_mt5.TRADE_ACTION_DEAL,
            "symbol": "EURUSD",
            "volume": 0.1,
            "type": mock_mt5.ORDER_TYPE_BUY,
            "filling": mock_mt5.ORDER_FILLING_FOK,
            "magic": 12345,
        }
        result = mock_mt5.order_send(request)
        assert result["retcode"] == mock_mt5.TRADE_RETCODE_DONE

    @pytest.mark.mt5_integration
    @skip_if_no_mt5("Requires actual MT5 connection for integration testing")
    def test_real_mt5_integration(self):
        """
        Integration test using real MT5 - only runs when MT5 is available.

        This will be skipped in CI but run locally if MT5 is installed.
        """
        import MetaTrader5 as mt5

        # Test real MT5 connection (demo account recommended)
        initialized = mt5.initialize()

        if not initialized:
            pytest.skip("Could not initialize MT5 connection")

        try:
            # Test terminal info
            terminal_info = mt5.terminal_info()
            assert terminal_info is not None

            # Test account info
            account_info = mt5.account_info()
            assert account_info is not None

            # Test symbol info for common pair
            symbol_info = mt5.symbol_info("EURUSD")
            if symbol_info is not None:
                assert symbol_info.name == "EURUSD"
                assert symbol_info.point > 0

            # Test historical data
            rates = mt5.copy_rates_from_pos("EURUSD", mt5.TIMEFRAME_M1, 0, 10)
            if rates is not None:
                assert len(rates) <= 10

        finally:
            mt5.shutdown()

    def test_conditional_mt5_import(self):
        """
        Test that shows how to handle conditional MT5 imports in application code.
        """

        # This pattern can be used in application code
        def get_mt5_module():
            try:
                import MetaTrader5 as mt5

                return mt5
            except ImportError:
                return None

        mt5_module = get_mt5_module()

        if mt5_available():
            # If MT5 is available, we should get the real module
            assert mt5_module is not None
            # In CI with mocks, this will be our mock module
            assert hasattr(mt5_module, "initialize")
        else:
            # If MT5 is not available and no mock is injected
            # This would be None in a real scenario without our fixture
            pass

    @patch("adapters.mt5_broker.MT5Broker")
    def test_adapter_with_mock_injection(self, mock_broker_class):
        """
        Test showing how to mock specific adapter classes for unit testing.
        """
        # Setup mock
        mock_broker = MagicMock()
        mock_broker.connect.return_value = True
        mock_broker.connected = True
        mock_broker.get_account_info.return_value = {"balance": 5000.0}
        mock_broker_class.return_value = mock_broker

        # Test code that uses MT5Broker
        # (This would be actual application code being tested)
        def create_and_test_broker():
            from adapters.mt5_broker import MT5Broker

            broker = MT5Broker(settings=None)
            broker.connect()
            return broker.get_account_info()

        result = create_and_test_broker()
        assert result["balance"] == 5000.0
        mock_broker.connect.assert_called_once()

    def test_event_bus_integration_with_fake_broker(self):
        """
        Test event bus integration using fake broker.

        This demonstrates testing event-driven functionality without MT5.
        """
        event_bus = EventBus()
        events_received = []

        # Subscribe to events using actual event classes
        from core.events.types import Filled, OrderPlaced

        def on_order_event(event):
            events_received.append(event)

        event_bus.subscribe(OrderPlaced, on_order_event)
        event_bus.subscribe(Filled, on_order_event)  # Use fake broker with event bus
        fake_broker = FakeBrokerAdapter(event_bus=event_bus)
        fake_broker.connect()

        # Submit order
        result = fake_broker.submit_market_order(
            symbol="EURUSD", side="buy", volume=0.1, client_order_id="event_test_001"
        )

        assert result["success"]

        # Check events were published
        assert len(events_received) == 2  # Submit + Fill events
        # Basic event validation
        assert any(
            "OrderPlaced" in str(type(event)) or hasattr(event, "client_order_id")
            for event in events_received
        )
        assert any(
            "Filled" in str(type(event)) or hasattr(event, "broker_order_id")
            for event in events_received
        )


# Additional pattern: Module-level skip for integration tests
pytestmark = pytest.mark.skipif(
    not mt5_available() and "integration" in __file__,
    reason="MT5 integration tests require MT5 installation",
)
