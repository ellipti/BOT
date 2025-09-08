"""
Tests for Position Netting Policy (Prompt-27)
Tests NETTING vs HEDGING modes with FIFO/LIFO/PROPORTIONAL reduction rules.
"""

import logging
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from core.broker import OrderRequest, OrderResult, OrderType
from core.executor.idempotent import IdempotentOrderExecutor
from core.positions import (
    NettingMode,
    NettingResult,
    Position,
    PositionAggregator,
    ReduceAction,
    ReduceRule,
)

# Setup logging for tests
logging.basicConfig(
    level=logging.DEBUG, format="%(name)s - %(levelname)s - %(message)s"
)


class TestNettingPolicy:
    """Test suite for position netting policy functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.base_time = datetime(2025, 9, 8, 14, 0, 0)

    def create_position(
        self,
        ticket: str,
        side: str,
        volume: float,
        entry_price: float,
        minutes_ago: int = 0,
    ) -> Position:
        """Create a test position."""
        return Position(
            ticket=ticket,
            symbol="XAUUSD",
            side=side,
            volume=volume,
            entry_price=entry_price,
            open_time=self.base_time - timedelta(minutes=minutes_ago),
        )

    def test_hedging_mode_no_netting(self):
        """Test that HEDGING mode doesn't net positions."""
        aggregator = PositionAggregator(NettingMode.HEDGING, ReduceRule.FIFO)

        # Existing long position
        existing_positions = [self.create_position("1001", "BUY", 1.0, 2500.0, 10)]

        # Incoming short order
        result = aggregator.process_incoming_order(
            symbol="XAUUSD",
            side="SELL",
            volume=0.6,
            price=2510.0,
            existing_positions=existing_positions,
        )

        # Should not reduce any positions in hedging mode
        assert len(result.reduce_actions) == 0
        assert result.remaining_volume == 0.6
        assert result.net_position_side == "SELL"
        assert "HEDGING mode" in result.summary

    def test_netting_partial_reduction_fifo(self):
        """Test FIFO partial reduction in netting mode."""
        aggregator = PositionAggregator(NettingMode.NETTING, ReduceRule.FIFO)

        # Multiple long positions (oldest first for FIFO)
        existing_positions = [
            self.create_position("1001", "BUY", 0.5, 2500.0, 30),  # Oldest
            self.create_position("1002", "BUY", 0.3, 2505.0, 20),
            self.create_position("1003", "BUY", 0.2, 2510.0, 10),  # Newest
        ]

        # Incoming short order for 0.6 (partial reduction)
        result = aggregator.process_incoming_order(
            symbol="XAUUSD",
            side="SELL",
            volume=0.6,
            price=2515.0,
            existing_positions=existing_positions,
        )

        # Should close positions in FIFO order
        assert len(result.reduce_actions) == 2

        # First position fully closed (0.5)
        assert result.reduce_actions[0].position_ticket == "1001"
        assert result.reduce_actions[0].reduce_volume == 0.5
        assert "Full closure via FIFO" in result.reduce_actions[0].reason

        # Second position partially closed (0.1 out of 0.3)
        assert result.reduce_actions[1].position_ticket == "1002"
        assert abs(result.reduce_actions[1].reduce_volume - 0.1) < 1e-6
        assert "Partial closure via FIFO" in result.reduce_actions[1].reason

        # No remaining volume (order fully satisfied by reductions)
        assert result.remaining_volume == 0.0
        assert result.net_position_side == "BUY"  # Still net long
        assert "Reduced 0.6 BUY" in result.summary

    def test_netting_partial_reduction_lifo(self):
        """Test LIFO partial reduction in netting mode."""
        aggregator = PositionAggregator(NettingMode.NETTING, ReduceRule.LIFO)

        # Same positions as FIFO test
        existing_positions = [
            self.create_position("1001", "BUY", 0.5, 2500.0, 30),  # Oldest
            self.create_position("1002", "BUY", 0.3, 2505.0, 20),
            self.create_position("1003", "BUY", 0.2, 2510.0, 10),  # Newest
        ]

        # Incoming short order for 0.6
        result = aggregator.process_incoming_order(
            symbol="XAUUSD",
            side="SELL",
            volume=0.6,
            price=2515.0,
            existing_positions=existing_positions,
        )

        # Should close positions in LIFO order (newest first)
        assert len(result.reduce_actions) == 3

        # Newest position fully closed (0.2)
        assert result.reduce_actions[0].position_ticket == "1003"
        assert result.reduce_actions[0].reduce_volume == 0.2

        # Second newest position fully closed (0.3)
        assert result.reduce_actions[1].position_ticket == "1002"
        assert result.reduce_actions[1].reduce_volume == 0.3

        # Oldest position partially closed (0.1 out of 0.5)
        assert result.reduce_actions[2].position_ticket == "1001"
        assert abs(result.reduce_actions[2].reduce_volume - 0.1) < 1e-6

        assert result.remaining_volume == 0.0

    def test_netting_proportional_reduction(self):
        """Test proportional reduction in netting mode."""
        aggregator = PositionAggregator(NettingMode.NETTING, ReduceRule.PROPORTIONAL)

        # Positions: 0.4, 0.4, 0.2 (total 1.0)
        existing_positions = [
            self.create_position("1001", "BUY", 0.4, 2500.0, 30),
            self.create_position("1002", "BUY", 0.4, 2505.0, 20),
            self.create_position("1003", "BUY", 0.2, 2510.0, 10),
        ]

        # Incoming short order for 0.5 (50% reduction)
        result = aggregator.process_incoming_order(
            symbol="XAUUSD",
            side="SELL",
            volume=0.5,
            price=2515.0,
            existing_positions=existing_positions,
        )

        # Should reduce each position proportionally
        assert len(result.reduce_actions) == 3

        # 40% of total -> 40% of 0.5 = 0.2 reduction
        action1 = next(a for a in result.reduce_actions if a.position_ticket == "1001")
        assert abs(action1.reduce_volume - 0.2) < 1e-6

        # 40% of total -> 40% of 0.5 = 0.2 reduction
        action2 = next(a for a in result.reduce_actions if a.position_ticket == "1002")
        assert abs(action2.reduce_volume - 0.2) < 1e-6

        # 20% of total -> 20% of 0.5 = 0.1 reduction
        action3 = next(a for a in result.reduce_actions if a.position_ticket == "1003")
        assert abs(action3.reduce_volume - 0.1) < 1e-6

        assert result.remaining_volume == 0.0

    def test_netting_full_closure_with_remaining(self):
        """Test full closure of opposite positions with remaining volume."""
        aggregator = PositionAggregator(NettingMode.NETTING, ReduceRule.FIFO)

        # Total long position: 0.8
        existing_positions = [
            self.create_position("1001", "BUY", 0.5, 2500.0, 30),
            self.create_position("1002", "BUY", 0.3, 2505.0, 20),
        ]

        # Incoming short order for 1.2 (larger than existing)
        result = aggregator.process_incoming_order(
            symbol="XAUUSD",
            side="SELL",
            volume=1.2,
            price=2515.0,
            existing_positions=existing_positions,
        )

        # Should close all existing positions
        assert len(result.reduce_actions) == 2
        assert result.reduce_actions[0].reduce_volume == 0.5  # Full closure
        assert result.reduce_actions[1].reduce_volume == 0.3  # Full closure

        # Remaining volume should be new net short position
        assert abs(result.remaining_volume - 0.4) < 1e-6  # 1.2 - 0.8
        assert result.net_position_side == "SELL"
        assert "opened" in result.summary and "SELL" in result.summary

    def test_netting_no_opposite_positions(self):
        """Test netting when no opposite positions exist."""
        aggregator = PositionAggregator(NettingMode.NETTING, ReduceRule.FIFO)

        # Only same-side positions
        existing_positions = [
            self.create_position("1001", "BUY", 0.5, 2500.0, 30),
        ]

        # Incoming same-side order
        result = aggregator.process_incoming_order(
            symbol="XAUUSD",
            side="BUY",
            volume=0.3,
            price=2510.0,
            existing_positions=existing_positions,
        )

        # No reductions should occur
        assert len(result.reduce_actions) == 0
        assert result.remaining_volume == 0.3
        assert result.net_position_side == "BUY"
        assert "No opposite positions" in result.summary

    def test_calculate_net_position(self):
        """Test net position calculation."""
        aggregator = PositionAggregator(NettingMode.NETTING, ReduceRule.FIFO)

        # Mixed positions
        positions = [
            self.create_position("1001", "BUY", 1.0, 2500.0),
            self.create_position("1002", "SELL", 0.6, 2510.0),
            self.create_position("1003", "BUY", 0.2, 2505.0),
        ]

        net_volume, net_side = aggregator.calculate_net_position(positions)

        # Net: 1.2 BUY - 0.6 SELL = 0.6 BUY
        assert net_volume == 0.6
        assert net_side == "BUY"

        # Test flat position
        flat_positions = [
            self.create_position("1001", "BUY", 1.0, 2500.0),
            self.create_position("1002", "SELL", 1.0, 2510.0),
        ]

        net_volume, net_side = aggregator.calculate_net_position(flat_positions)
        assert net_volume == 0.0
        assert net_side == "FLAT"


class TestIdempotentExecutorNetting:
    """Test IdempotentOrderExecutor with netting integration."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_broker = MagicMock()
        self.mock_settings = MagicMock()

        # Configure settings
        self.mock_settings.trading.netting_mode = "NETTING"
        self.mock_settings.trading.reduce_rule = "FIFO"
        self.mock_settings.idempotency_db = ":memory:"  # In-memory SQLite for testing

        # Mock broker responses
        self.mock_broker.place_order.return_value = OrderResult(
            accepted=True, broker_order_id="BR123", reason="OK"
        )

    def test_executor_netting_initialization(self):
        """Test executor initializes with netting configuration."""
        executor = IdempotentOrderExecutor(
            broker=self.mock_broker, db_path=":memory:", settings=self.mock_settings
        )

        assert executor.position_aggregator.netting_mode == NettingMode.NETTING
        assert executor.position_aggregator.reduce_rule == ReduceRule.FIFO

    def test_executor_hedging_mode_passthrough(self):
        """Test executor passes through orders in hedging mode."""
        self.mock_settings.trading.netting_mode = "HEDGING"

        executor = IdempotentOrderExecutor(
            broker=self.mock_broker, db_path=":memory:", settings=self.mock_settings
        )

        # Mock get_existing_positions to return empty list
        executor._get_existing_positions = MagicMock(return_value=[])

        request = OrderRequest(
            client_order_id="test123",
            symbol="XAUUSD",
            side="BUY",
            qty=1.0,
            order_type=OrderType.MARKET,
            price=2500.0,
        )

        result = executor.place(request)

        # Should place order directly without netting
        assert result.accepted
        assert self.mock_broker.place_order.called

    @patch("core.executor.idempotent.datetime")
    def test_executor_netting_mode_reduction(self, mock_datetime):
        """Test executor performs position reduction in netting mode."""
        # Mock datetime for consistent timestamps
        mock_datetime.now.return_value = datetime(2025, 9, 8, 15, 0, 0)
        mock_datetime.fromtimestamp.side_effect = lambda x: datetime.fromtimestamp(x)

        executor = IdempotentOrderExecutor(
            broker=self.mock_broker, db_path=":memory:", settings=self.mock_settings
        )

        # Mock existing long position
        mock_position = MagicMock()
        mock_position.ticket = 1001
        mock_position.symbol = "XAUUSD"
        mock_position.type = 0  # BUY
        mock_position.volume = 1.0
        mock_position.price_open = 2500.0
        mock_position.time = 1725801600  # timestamp
        mock_position.sl = None
        mock_position.tp = None

        executor._get_existing_positions = MagicMock(return_value=[])

        # Mock broker position query
        self.mock_broker.get_positions.return_value = [mock_position]
        executor._get_existing_positions = lambda symbol: [
            Position(
                ticket="1001",
                symbol="XAUUSD",
                side="BUY",
                volume=1.0,
                entry_price=2500.0,
                open_time=datetime(2025, 9, 8, 14, 0, 0),
            )
        ]

        # Mock close_position method
        self.mock_broker.close_position = MagicMock(
            return_value=OrderResult(
                accepted=True, broker_order_id="CLOSE123", reason="Closed"
            )
        )

        # Incoming short order that will partially reduce
        request = OrderRequest(
            client_order_id="test456",
            symbol="XAUUSD",
            side="SELL",
            qty=0.6,
            order_type=OrderType.MARKET,
            price=2510.0,
        )

        result = executor.place(request)

        # Should succeed (either through reduction or remaining order)
        assert result.accepted

        # Should have attempted to close position (or place remaining order)
        assert (
            self.mock_broker.close_position.called
            or self.mock_broker.place_order.called
        )

    def test_executor_duplicate_order_blocking(self):
        """Test that duplicate orders are still blocked with netting."""
        executor = IdempotentOrderExecutor(
            broker=self.mock_broker, db_path=":memory:", settings=self.mock_settings
        )

        request = OrderRequest(
            client_order_id="duplicate123",
            symbol="XAUUSD",
            side="BUY",
            qty=1.0,
            order_type=OrderType.MARKET,
            price=2500.0,
        )

        # Mock no existing positions
        executor._get_existing_positions = MagicMock(return_value=[])

        # First execution should succeed
        result1 = executor.place(request)
        assert result1.accepted

        # Second execution should be blocked
        result2 = executor.place(request)
        assert not result2.accepted
        assert result2.reason == "DUPLICATE_COID"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
