"""
Test broker factory and PaperBroker functionality.
Validates swap-ability between MT5 and Paper brokers.
"""

import time
from unittest.mock import Mock, patch

import pytest

from adapters import MT5Broker, PaperBroker, create_broker
from core.broker import OrderRequest, Side


class MockSettings:
    """Mock settings for testing"""

    def __init__(self, broker_kind="paper"):
        self.BROKER_KIND = broker_kind
        self.broker_kind = broker_kind
        self.INITIAL_BALANCE = 10000.0
        self.COMMISSION_PER_LOT = 5.0
        self.SLIPPAGE_PIPS = 0.2

        # MT5 settings for fallback testing
        self.mt5 = Mock()
        self.mt5.attach_mode = True
        self.mt5.terminal_path = None


class TestBrokerFactory:
    """Test broker factory creation and swap-ability"""

    def test_create_paper_broker(self):
        """Test creating paper broker via factory"""
        settings = MockSettings(broker_kind="paper")

        broker = create_broker(settings)

        assert isinstance(broker, PaperBroker)
        assert broker.settings == settings
        assert not broker.is_connected()

    def test_create_mt5_broker_fallback(self):
        """Test MT5 broker creation - can create broker even if connection fails"""
        settings = MockSettings(broker_kind="mt5")

        # MT5Broker can be created if MetaTrader5 module is available
        # (even if actual connection to MT5 terminal will fail)
        broker = create_broker(settings)

        # Should get MT5Broker if module available, PaperBroker if not
        assert isinstance(broker, (MT5Broker, PaperBroker))

        # Test that the broker has the expected interface
        assert hasattr(broker, "connect")
        assert hasattr(broker, "is_connected")
        assert hasattr(broker, "place_order")
        assert hasattr(broker, "positions")

        # Broker should not be connected initially
        assert not broker.is_connected()

    def test_unsupported_broker_kind(self):
        """Test error for unsupported broker type"""
        settings = MockSettings(broker_kind="unsupported")

        with pytest.raises(ValueError, match="Unsupported broker kind: unsupported"):
            create_broker(settings)

    def test_broker_swap_compatibility(self):
        """Test that both brokers implement the same interface"""
        paper_settings = MockSettings(broker_kind="paper")

        # Create paper broker
        paper_broker = create_broker(paper_settings)

        # Test interface compatibility
        assert hasattr(paper_broker, "connect")
        assert hasattr(paper_broker, "is_connected")
        assert hasattr(paper_broker, "place_order")
        assert hasattr(paper_broker, "cancel")
        assert hasattr(paper_broker, "positions")

        # Test that interface works
        paper_broker.connect()
        assert paper_broker.is_connected()

        positions = paper_broker.positions()
        assert isinstance(positions, list)


class TestPaperBroker:
    """Test PaperBroker simulation functionality"""

    def setup_method(self):
        """Setup test fixtures"""
        self.settings = MockSettings()
        self.broker = PaperBroker(self.settings)

    def test_paper_broker_initialization(self):
        """Test paper broker initializes correctly"""
        assert not self.broker.is_connected()
        assert self.broker._balance == 10000.0
        assert self.broker._equity == 10000.0
        assert len(self.broker._positions) == 0
        assert len(self.broker._orders) == 0

    def test_connection_lifecycle(self):
        """Test connection and disconnection"""
        # Initially not connected
        assert not self.broker.is_connected()

        # Connect
        self.broker.connect()
        assert self.broker.is_connected()

    def test_market_order_execution(self):
        """Test market order execution and position tracking"""
        self.broker.connect()

        # Create market order request
        request = OrderRequest(
            client_order_id="test_001",
            symbol="EURUSD",
            side=Side.BUY,
            qty=0.1,
            order_type="MARKET",
            sl=1.0900,
            tp=1.1000,
        )

        # Execute order
        result = self.broker.place_order(request)

        # Validate result
        assert result.accepted is True
        assert result.broker_order_id is not None
        assert "FILLED" in result.reason

        # Check position created
        positions = self.broker.positions()
        assert len(positions) == 1

        position = positions[0]
        assert position.symbol == "EURUSD"
        assert position.qty == 0.1  # Long position
        assert position.avg_price > 0

    def test_order_idempotency(self):
        """Test duplicate order handling"""
        self.broker.connect()

        request = OrderRequest(
            client_order_id="duplicate_test",
            symbol="EURUSD",
            side=Side.BUY,
            qty=0.1,
            order_type="MARKET",
        )

        # Execute same order twice
        result1 = self.broker.place_order(request)
        result2 = self.broker.place_order(request)

        # Should return same broker order ID
        assert result1.accepted is True
        assert result2.accepted is True
        assert result1.broker_order_id == result2.broker_order_id

        # Should only have one position
        positions = self.broker.positions()
        assert len(positions) == 1

    def test_position_updates(self):
        """Test position updates with multiple trades"""
        self.broker.connect()

        # Buy 0.1 lot
        buy_request = OrderRequest(
            client_order_id="buy_001",
            symbol="EURUSD",
            side=Side.BUY,
            qty=0.1,
            order_type="MARKET",
        )
        self.broker.place_order(buy_request)

        # Check position
        positions = self.broker.positions()
        assert len(positions) == 1
        assert positions[0].qty == 0.1

        # Buy another 0.1 lot
        buy_request2 = OrderRequest(
            client_order_id="buy_002",
            symbol="EURUSD",
            side=Side.BUY,
            qty=0.1,
            order_type="MARKET",
        )
        self.broker.place_order(buy_request2)

        # Check updated position
        positions = self.broker.positions()
        assert len(positions) == 1
        assert positions[0].qty == 0.2

        # Sell 0.1 lot (partial close)
        sell_request = OrderRequest(
            client_order_id="sell_001",
            symbol="EURUSD",
            side=Side.SELL,
            qty=0.1,
            order_type="MARKET",
        )
        self.broker.place_order(sell_request)

        # Check reduced position
        positions = self.broker.positions()
        assert len(positions) == 1
        assert positions[0].qty == 0.1

    def test_position_closure(self):
        """Test complete position closure"""
        self.broker.connect()

        # Open position
        buy_request = OrderRequest(
            client_order_id="open_pos",
            symbol="EURUSD",
            side=Side.BUY,
            qty=0.1,
            order_type="MARKET",
        )
        self.broker.place_order(buy_request)

        # Verify position exists
        positions = self.broker.positions()
        assert len(positions) == 1

        # Close position completely
        sell_request = OrderRequest(
            client_order_id="close_pos",
            symbol="EURUSD",
            side=Side.SELL,
            qty=0.1,
            order_type="MARKET",
        )
        self.broker.place_order(sell_request)

        # Verify position closed
        positions = self.broker.positions()
        assert len(positions) == 0

    def test_commission_calculation(self):
        """Test commission deduction from balance"""
        self.broker.connect()
        initial_balance = self.broker._balance

        # Execute order with commission
        request = OrderRequest(
            client_order_id="commission_test",
            symbol="EURUSD",
            side=Side.BUY,
            qty=0.1,
            order_type="MARKET",
        )
        self.broker.place_order(request)

        # Check commission deducted
        expected_commission = 0.1 * 5.0  # 0.1 lot * $5 per lot
        assert self.broker._balance == initial_balance - expected_commission

    def test_account_info(self):
        """Test account information retrieval"""
        self.broker.connect()

        account = self.broker.get_account_info()

        assert account["login"] == 99999999
        assert account["balance"] == 10000.0
        assert account["equity"] == 10000.0
        assert account["currency"] == "USD"
        assert account["trade_allowed"] is True
        assert account["server"] == "PaperBroker-Simulation"
        assert account["positions_count"] == 0

    def test_unsupported_order_types(self):
        """Test handling of unsupported order types"""
        self.broker.connect()

        # Try limit order (not supported)
        request = OrderRequest(
            client_order_id="limit_test",
            symbol="EURUSD",
            side=Side.BUY,
            qty=0.1,
            order_type="LIMIT",
            price=1.0900,
        )

        result = self.broker.place_order(request)
        assert result.accepted is False
        assert "only supports MARKET orders" in result.reason

    def test_order_cancellation(self):
        """Test order cancellation (not supported for market orders)"""
        self.broker.connect()

        result = self.broker.cancel("fake_order_id")
        assert result is False  # Market orders cannot be cancelled

    def test_simulation_reset(self):
        """Test simulation reset functionality"""
        self.broker.connect()

        # Execute some trades
        request = OrderRequest(
            client_order_id="reset_test",
            symbol="EURUSD",
            side=Side.BUY,
            qty=0.1,
            order_type="MARKET",
        )
        self.broker.place_order(request)

        # Verify state changed
        assert len(self.broker._orders) > 0
        assert len(self.broker._positions) > 0
        assert self.broker._balance < 10000.0  # Commission deducted

        # Reset simulation
        self.broker.reset_simulation()

        # Verify state reset
        assert len(self.broker._orders) == 0
        assert len(self.broker._positions) == 0
        assert self.broker._balance == 10000.0

    def test_disconnected_operations(self):
        """Test operations when broker is disconnected"""
        # Don't connect broker
        assert not self.broker.is_connected()

        # Try to place order
        request = OrderRequest(
            client_order_id="disconnected_test",
            symbol="EURUSD",
            side=Side.BUY,
            qty=0.1,
            order_type="MARKET",
        )

        result = self.broker.place_order(request)
        assert result.accepted is False
        assert "not connected" in result.reason

        # Try to get positions
        positions = self.broker.positions()
        assert len(positions) == 0


class TestBrokerIntegration:
    """Test broker integration in event pipeline simulation"""

    def test_event_flow_simulation(self):
        """Test that paper broker works with event flow"""
        settings = MockSettings(broker_kind="paper")
        broker = create_broker(settings)
        broker.connect()

        # Simulate order placement in event flow
        request = OrderRequest(
            client_order_id=f"event_test_{int(time.time())}",
            symbol="XAUUSD",
            side=Side.BUY,
            qty=0.01,
            order_type="MARKET",
            sl=2020.00,
            tp=2030.00,
        )

        result = broker.place_order(request)

        # Validate simulation works in event context
        assert result.accepted is True
        assert result.broker_order_id is not None

        # Check position tracking
        positions = broker.positions()
        assert len(positions) == 1
        assert positions[0].symbol == "XAUUSD"
        assert positions[0].qty == 0.01

    def test_multiple_symbols(self):
        """Test trading multiple symbols simultaneously"""
        settings = MockSettings(broker_kind="paper")
        broker = create_broker(settings)
        broker.connect()

        symbols = ["EURUSD", "GBPUSD", "XAUUSD"]

        # Open positions in multiple symbols
        for i, symbol in enumerate(symbols):
            request = OrderRequest(
                client_order_id=f"multi_{symbol}_{i}",
                symbol=symbol,
                side=Side.BUY,
                qty=0.1,
                order_type="MARKET",
            )
            result = broker.place_order(request)
            assert result.accepted is True

        # Verify all positions created
        positions = broker.positions()
        assert len(positions) == 3

        position_symbols = {pos.symbol for pos in positions}
        assert position_symbols == set(symbols)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
