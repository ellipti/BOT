"""
Test suite for TrailingStopManager
Tests breakeven logic, trailing stops, and position state management.
"""

import time
from unittest.mock import MagicMock, Mock

from risk.trailing import TrailingStopManager


class MockPosition:
    """Mock MT5 position object for testing"""

    def __init__(
        self,
        ticket: int,
        symbol: str,
        position_type: int,
        price_open: float,
        price_current: float,
        volume: float = 1.0,
        sl: float = 0.0,
        tp: float = 0.0,
    ):
        self.ticket = ticket
        self.symbol = symbol
        self.type = position_type  # 0=BUY, 1=SELL
        self.price_open = price_open
        self.price_current = price_current
        self.volume = volume
        self.sl = sl if sl != 0.0 else None
        self.tp = tp if tp != 0.0 else None


class MockSymbolInfo:
    """Mock MT5 symbol info object"""

    def __init__(self, point: float = 0.0001):  # Standard forex point
        self.point = point


class TestTrailingStopManager:
    """Test suite for TrailingStopManager functionality"""

    def test_breakeven_buy_position(self):
        """Test breakeven calculation for BUY position"""
        # Mock MT5
        mt5 = Mock()
        mt5.symbol_info.return_value = MockSymbolInfo(
            point=0.0001
        )  # Standard EURUSD point

        manager = TrailingStopManager(mt5)

        # BUY position: entry 1.10000, current 1.10015 (1.5 pips profit)
        # Note: For EURUSD, 1 pip = 0.0001, so 1.5 pips = 0.00015
        position = MockPosition(
            ticket=12345,
            symbol="EURUSD",
            position_type=0,
            price_open=1.10000,
            price_current=1.10015,
        )

        # Test breakeven trigger (threshold 1.0 pips, buffer 2 pips)
        breakeven_sl = manager.compute_breakeven_sl(position, 1.0, 2.0)

        # Should trigger: profit 1.5 pips > 1.0 pips threshold
        # Breakeven SL = entry + buffer = 1.10000 + (2 * 0.0001) = 1.10020
        expected_sl = 1.10020
        assert breakeven_sl is not None
        assert abs(breakeven_sl - expected_sl) < 1e-9

        # Test no breakeven trigger (threshold 2 pips)
        breakeven_sl = manager.compute_breakeven_sl(position, 2.0, 2.0)
        assert breakeven_sl is None  # 1.5 pips < 2 pips threshold

    def test_breakeven_sell_position(self):
        """Test breakeven calculation for SELL position"""
        mt5 = Mock()
        mt5.symbol_info.return_value = MockSymbolInfo(point=0.0001)

        manager = TrailingStopManager(mt5)

        # SELL position: entry 1.10000, current 1.09985 (1.5 pips profit)
        position = MockPosition(
            ticket=12346,
            symbol="EURUSD",
            position_type=1,
            price_open=1.10000,
            price_current=1.09985,
        )

        # Test breakeven trigger
        breakeven_sl = manager.compute_breakeven_sl(position, 1.0, 2.0)

        # Breakeven SL = entry - buffer = 1.10000 - (2 * 0.0001) = 1.09980
        expected_sl = 1.09980
        assert breakeven_sl is not None
        assert abs(breakeven_sl - expected_sl) < 1e-9

    def test_trailing_stop_buy_position(self):
        """Test trailing stop calculation for BUY position"""
        mt5 = Mock()
        mt5.symbol_info.return_value = MockSymbolInfo(point=0.0001)

        manager = TrailingStopManager(mt5)

        # BUY position with existing SL
        position = MockPosition(
            ticket=12347,
            symbol="EURUSD",
            position_type=0,
            price_open=1.10000,
            price_current=1.10200,
            sl=1.10050,
        )

        # Test trailing stop (step 5 pips, buffer 10 pips)
        trailing_sl = manager.compute_trailing_sl(position, 5.0, 10.0)

        # Proposed SL = current - buffer = 1.10200 - (10 * 0.0001) = 1.10100
        # Current SL = 1.10050, proposed = 1.10100
        # Step = 1.10100 - 1.10050 = 0.0050 = 5 pips >= 5 pips step → OK
        expected_sl = 1.10100
        assert trailing_sl is not None
        assert abs(trailing_sl - expected_sl) < 1e-9

        # Test insufficient step (current price barely moved)
        position.price_current = 1.10130  # Only 3 pips more favorable
        trailing_sl = manager.compute_trailing_sl(position, 5.0, 10.0)

        # Proposed SL = 1.10130 - 0.0010 = 1.10030
        # Step = 1.10030 - 1.10050 = -0.0020 (negative, not favorable) → No update
        assert trailing_sl is None

    def test_trailing_stop_sell_position(self):
        """Test trailing stop calculation for SELL position"""
        mt5 = Mock()
        mt5.symbol_info.return_value = MockSymbolInfo(point=0.0001)

        manager = TrailingStopManager(mt5)

        # SELL position with existing SL
        position = MockPosition(
            ticket=12348,
            symbol="EURUSD",
            position_type=1,
            price_open=1.10000,
            price_current=1.09800,
            sl=1.09950,
        )

        # Test trailing stop
        trailing_sl = manager.compute_trailing_sl(position, 5.0, 10.0)

        # Proposed SL = current + buffer = 1.09800 + (10 * 0.0001) = 1.09900
        # Current SL = 1.09950, proposed = 1.09900 (more favorable for SELL)
        # Step = 1.09950 - 1.09900 = 0.0050 = 5 pips >= 5 pips step → OK
        expected_sl = 1.09900
        assert trailing_sl is not None
        assert abs(trailing_sl - expected_sl) < 1e-9

    def test_position_trailing_workflow(self):
        """Test complete position trailing workflow"""
        # Mock MT5 with successful order modification
        mt5 = Mock()
        mt5.symbol_info.return_value = MockSymbolInfo(point=0.0001)
        mt5.TRADE_ACTION_SLTP = 2
        mt5.TRADE_RETCODE_DONE = 10009

        # Mock successful order_send
        result = Mock()
        result.retcode = mt5.TRADE_RETCODE_DONE
        mt5.order_send.return_value = result

        manager = TrailingStopManager(mt5)

        # BUY position with profit for breakeven
        position = MockPosition(
            ticket=12349,
            symbol="EURUSD",
            position_type=0,
            price_open=1.10000,
            price_current=1.10120,  # 12 pips profit
        )

        # First call should trigger breakeven
        action = manager.process_position_trailing(position, breakeven_threshold=10.0)
        assert action == "breakeven"

        # Verify order_send was called for breakeven
        mt5.order_send.assert_called_once()
        call_args = mt5.order_send.call_args[0][0]
        assert call_args["action"] == mt5.TRADE_ACTION_SLTP
        assert call_args["position"] == 12349
        assert abs(call_args["sl"] - 1.10020) < 1e-9  # Breakeven with 2 pip buffer

        # Reset mock for next test
        mt5.order_send.reset_mock()

        # Move price further and test trailing
        position.price_current = 1.10250  # More favorable
        position.sl = 1.10020  # Breakeven SL now applied

        action = manager.process_position_trailing(position, breakeven_threshold=10.0)
        assert action == "trailing"

        # Verify trailing SL was updated
        mt5.order_send.assert_called_once()
        call_args = mt5.order_send.call_args[0][0]
        assert call_args["position"] == 12349
        assert abs(call_args["sl"] - 1.10150) < 1e-9  # Trail 10 pips behind 1.10250

    def test_process_all_positions(self):
        """Test processing multiple positions"""
        mt5 = Mock()

        # Mock different point sizes for different symbols
        def mock_symbol_info(symbol):
            if symbol in ["EURUSD", "GBPUSD"]:
                return MockSymbolInfo(point=0.0001)
            elif symbol == "USDJPY":
                return MockSymbolInfo(point=0.01)  # JPY pairs have different point size
            return MockSymbolInfo(point=0.0001)

        mt5.symbol_info.side_effect = mock_symbol_info
        mt5.TRADE_ACTION_SLTP = 2
        mt5.TRADE_RETCODE_DONE = 10009

        result = Mock()
        result.retcode = mt5.TRADE_RETCODE_DONE
        mt5.order_send.return_value = result

        # Mock positions_get to return multiple positions
        positions = [
            MockPosition(
                111, "EURUSD", 0, 1.10000, 1.10120
            ),  # BUY, 12 pips profit -> breakeven
            MockPosition(
                222, "GBPUSD", 1, 1.30000, 1.29850
            ),  # SELL, 15 pips profit -> breakeven
            MockPosition(
                333, "USDJPY", 0, 110.00, 110.005, sl=109.95
            ),  # BUY, tiny movement -> no trailing
        ]
        mt5.positions_get.return_value = positions

        manager = TrailingStopManager(mt5)

        actions = manager.process_all_positions(breakeven_threshold=10.0)

        # Should have breakeven actions for positions 111 and 222
        assert "111" in actions
        assert "222" in actions
        assert actions["111"] == "breakeven"
        assert actions["222"] == "breakeven"
        assert "333" not in actions  # No action taken

        # Verify two order_send calls
        assert mt5.order_send.call_count == 2

    def test_cleanup_closed_positions(self):
        """Test cleanup of closed position states"""
        mt5 = Mock()

        manager = TrailingStopManager(mt5)

        # Add some position states manually
        manager._position_states = {
            "111": {"breakeven_applied": True},
            "222": {"last_trailing_sl": 1.10100},
            "333": {"breakeven_applied": False},
        }

        # Mock positions_get to return only position 111 as open
        open_position = MockPosition(111, "EURUSD", 0, 1.10000, 1.10150)
        mt5.positions_get.return_value = [open_position]

        # Clean up
        cleaned_count = manager.cleanup_closed_positions()

        # Should clean up 2 closed positions (222, 333)
        assert cleaned_count == 2
        assert "111" in manager._position_states  # Still open
        assert "222" not in manager._position_states  # Cleaned
        assert "333" not in manager._position_states  # Cleaned

    def test_position_state_management(self):
        """Test position state tracking methods"""
        mt5 = Mock()
        manager = TrailingStopManager(mt5)

        # Test getting empty state
        state = manager.get_position_state("123")
        assert state == {}

        # Add state manually
        manager._position_states["123"] = {"breakeven_applied": True}

        # Get state
        state = manager.get_position_state("123")
        assert state["breakeven_applied"] is True

        # Reset state
        manager.reset_position_state("123")
        state = manager.get_position_state("123")
        assert state == {}

    def test_update_position_stops_failure(self):
        """Test handling of failed stop updates"""
        mt5 = Mock()
        mt5.TRADE_ACTION_SLTP = 2
        mt5.TRADE_RETCODE_DONE = 10009

        # Mock failed order_send
        result = Mock()
        result.retcode = 10004  # TRADE_RETCODE_REQUOTE
        result.comment = "Requote"
        mt5.order_send.return_value = result

        manager = TrailingStopManager(mt5)

        # Try to update stops - should return False
        success = manager.update_position_stops("123", sl=1.10000)
        assert success is False

        # Verify order_send was called
        mt5.order_send.assert_called_once()


if __name__ == "__main__":
    # Run tests
    test = TestTrailingStopManager()

    print("Running TrailingStopManager tests...")

    try:
        test.test_breakeven_buy_position()
        print("✅ Breakeven BUY position test passed")

        test.test_breakeven_sell_position()
        print("✅ Breakeven SELL position test passed")

        test.test_trailing_stop_buy_position()
        print("✅ Trailing stop BUY position test passed")

        test.test_trailing_stop_sell_position()
        print("✅ Trailing stop SELL position test passed")

        test.test_position_trailing_workflow()
        print("✅ Position trailing workflow test passed")

        test.test_process_all_positions()
        print("✅ Process all positions test passed")

        test.test_cleanup_closed_positions()
        print("✅ Cleanup closed positions test passed")

        test.test_position_state_management()
        print("✅ Position state management test passed")

        test.test_update_position_stops_failure()
        print("✅ Update stops failure handling test passed")

        print("\n🎉 All TrailingStopManager tests passed!")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        raise
