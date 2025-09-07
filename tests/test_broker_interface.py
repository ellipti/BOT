"""
Smoke tests for BrokerGateway interface using FakeBroker
Tests the interface contract without requiring actual broker connection.
"""

from unittest.mock import Mock

import pytest

from core.broker import (
    BrokerGateway,
    OrderRequest,
    OrderResult,
    OrderType,
    Position,
    Side,
)


class FakeBroker:
    """
    Fake broker implementation for testing BrokerGateway interface.
    Implements the protocol without requiring actual broker connection.
    """

    def __init__(self):
        self._connected = False
        self._positions = []
        self._next_order_id = 1000

    def connect(self) -> None:
        """Simulate broker connection"""
        self._connected = True

    def is_connected(self) -> bool:
        """Return connection status"""
        return self._connected

    def place_order(self, request: OrderRequest) -> OrderResult:
        """Simulate order execution"""
        if not self._connected:
            return OrderResult(accepted=False, reason="Not connected")

        # Simulate successful market order
        if request.order_type == OrderType.MARKET:
            order_id = str(self._next_order_id)
            self._next_order_id += 1

            # Add position for successful market order
            qty = request.qty if request.side == Side.BUY else -request.qty
            position = Position(
                symbol=request.symbol, qty=qty, avg_price=2500.0  # Mock price
            )
            self._positions.append(position)

            return OrderResult(
                accepted=True, broker_order_id=order_id, reason="Simulated execution"
            )
        else:
            return OrderResult(
                accepted=False, reason=f"Order type {request.order_type} not supported"
            )

    def cancel(self, broker_order_id: str) -> bool:
        """Simulate order cancellation (always fails for simplicity)"""
        return False

    def positions(self) -> list[Position]:
        """Return simulated positions"""
        return self._positions.copy()


class TestBrokerGatewayInterface:
    """Test BrokerGateway interface compliance"""

    def test_broker_gateway_protocol_compliance(self):
        """Test that FakeBroker implements BrokerGateway protocol"""
        fake_broker = FakeBroker()

        # Should be recognized as implementing the protocol
        assert isinstance(fake_broker, BrokerGateway)

    def test_connection_methods(self):
        """Test connection-related methods"""
        broker = FakeBroker()

        # Initially not connected
        assert not broker.is_connected()

        # Connect
        broker.connect()
        assert broker.is_connected()

    def test_order_placement(self):
        """Test order placement functionality"""
        broker = FakeBroker()
        broker.connect()

        # Create valid market order request
        request = OrderRequest(
            client_order_id="test-001",
            symbol="XAUUSD",
            side=Side.BUY,
            qty=0.1,
            order_type=OrderType.MARKET,
        )

        # Place order
        result = broker.place_order(request)

        # Verify result structure
        assert isinstance(result, OrderResult)
        assert result.accepted is True
        assert result.broker_order_id is not None
        assert isinstance(result.reason, str)

    def test_order_placement_when_disconnected(self):
        """Test order placement fails when disconnected"""
        broker = FakeBroker()  # Don't connect

        request = OrderRequest(
            client_order_id="test-002",
            symbol="XAUUSD",
            side=Side.SELL,
            qty=0.05,
            order_type=OrderType.MARKET,
        )

        result = broker.place_order(request)

        assert result.accepted is False
        assert "Not connected" in result.reason

    def test_position_retrieval(self):
        """Test position retrieval"""
        broker = FakeBroker()
        broker.connect()

        # Initially no positions
        positions = broker.positions()
        assert isinstance(positions, list)
        assert len(positions) == 0

        # Place an order to create position
        request = OrderRequest(
            client_order_id="test-003",
            symbol="XAUUSD",
            side=Side.BUY,
            qty=0.1,
            order_type=OrderType.MARKET,
        )

        result = broker.place_order(request)
        assert result.accepted

        # Check positions
        positions = broker.positions()
        assert len(positions) == 1

        position = positions[0]
        assert isinstance(position, Position)
        assert position.symbol == "XAUUSD"
        assert position.qty == 0.1  # Long position
        assert position.avg_price > 0

    def test_order_cancellation(self):
        """Test order cancellation (returns False for fake broker)"""
        broker = FakeBroker()
        broker.connect()

        result = broker.cancel("fake-order-id")
        assert isinstance(result, bool)
        assert result is False  # FakeBroker doesn't support cancellation


class TestOrderRequestValidation:
    """Test OrderRequest model validation"""

    def test_valid_market_order(self):
        """Test valid market order creation"""
        request = OrderRequest(
            client_order_id="test-001",
            symbol="EURUSD",
            side=Side.BUY,
            qty=1.0,
            order_type=OrderType.MARKET,
        )

        assert request.client_order_id == "test-001"
        assert request.symbol == "EURUSD"
        assert request.side == Side.BUY
        assert request.qty == 1.0
        assert request.order_type == OrderType.MARKET
        assert request.sl is None
        assert request.tp is None
        assert request.price is None

    def test_limit_order_requires_price(self):
        """Test that LIMIT orders require price"""
        with pytest.raises(ValueError, match="LIMIT orders require a price"):
            OrderRequest(
                client_order_id="test-002",
                symbol="GBPUSD",
                side=Side.SELL,
                qty=0.5,
                order_type=OrderType.LIMIT,
                # Missing price
            )

    def test_stop_order_requires_price(self):
        """Test that STOP orders require price"""
        with pytest.raises(ValueError, match="STOP orders require a price"):
            OrderRequest(
                client_order_id="test-003",
                symbol="USDJPY",
                side=Side.BUY,
                qty=2.0,
                order_type=OrderType.STOP,
                # Missing price
            )

    def test_invalid_quantity(self):
        """Test that quantity must be positive"""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            OrderRequest(
                client_order_id="test-004",
                symbol="XAUUSD",
                side=Side.BUY,
                qty=0.0,  # Invalid quantity
                order_type=OrderType.MARKET,
            )


class TestPositionModel:
    """Test Position model functionality"""

    def test_long_position(self):
        """Test long position properties"""
        position = Position(symbol="XAUUSD", qty=0.5, avg_price=2500.0)

        assert position.is_long is True
        assert position.is_short is False
        assert position.abs_qty == 0.5

    def test_short_position(self):
        """Test short position properties"""
        position = Position(symbol="EURUSD", qty=-1.0, avg_price=1.1000)

        assert position.is_long is False
        assert position.is_short is True
        assert position.abs_qty == 1.0


class TestOrderResultValidation:
    """Test OrderResult model validation"""

    def test_accepted_order_requires_id(self):
        """Test that accepted orders must have broker_order_id"""
        with pytest.raises(
            ValueError, match="Accepted orders must have broker_order_id"
        ):
            OrderResult(
                accepted=True, broker_order_id=None  # Missing for accepted order
            )

    def test_rejected_order_no_id_required(self):
        """Test that rejected orders don't require broker_order_id"""
        result = OrderResult(
            accepted=False, broker_order_id=None, reason="Insufficient margin"
        )

        assert result.accepted is False
        assert result.broker_order_id is None
        assert result.reason == "Insufficient margin"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
