"""
Tests for EventBus implementation - publish/subscribe functionality
"""

from unittest.mock import Mock

import pytest

from core.events import EventBus, RiskApproved, SignalDetected, Validated


class TestEventBus:
    """Test EventBus publish/subscribe functionality"""

    def test_subscribe_and_publish(self):
        """Test basic subscribe/publish flow"""
        bus = EventBus()
        handler_mock = Mock()

        # Subscribe handler
        bus.subscribe(SignalDetected, handler_mock)

        # Publish event
        signal = SignalDetected(
            symbol="XAUUSD", side="BUY", strength=0.85, strategy_id="test"
        )
        bus.publish(signal)

        # Verify handler was called
        handler_mock.assert_called_once_with(signal)

    def test_multiple_handlers_for_same_event(self):
        """Test multiple handlers can subscribe to same event type"""
        bus = EventBus()
        handler1 = Mock()
        handler2 = Mock()
        handler3 = Mock()

        # Subscribe multiple handlers
        bus.subscribe(SignalDetected, handler1)
        bus.subscribe(SignalDetected, handler2)
        bus.subscribe(SignalDetected, handler3)

        # Publish event
        signal = SignalDetected(
            symbol="EURUSD", side="SELL", strength=0.75, strategy_id="test"
        )
        bus.publish(signal)

        # All handlers should be called
        handler1.assert_called_once_with(signal)
        handler2.assert_called_once_with(signal)
        handler3.assert_called_once_with(signal)

    def test_different_event_types(self):
        """Test handlers only receive events of subscribed type"""
        bus = EventBus()
        signal_handler = Mock()
        validated_handler = Mock()
        risk_handler = Mock()

        # Subscribe to different event types
        bus.subscribe(SignalDetected, signal_handler)
        bus.subscribe(Validated, validated_handler)
        bus.subscribe(RiskApproved, risk_handler)

        # Publish SignalDetected
        signal = SignalDetected(
            symbol="GBPUSD", side="BUY", strength=0.9, strategy_id="test"
        )
        bus.publish(signal)

        # Only signal handler should be called
        signal_handler.assert_called_once_with(signal)
        validated_handler.assert_not_called()
        risk_handler.assert_not_called()

        # Reset mocks
        signal_handler.reset_mock()

        # Publish Validated
        validated = Validated(symbol="GBPUSD", side="BUY", reason=None)
        bus.publish(validated)

        # Only validated handler should be called
        signal_handler.assert_not_called()
        validated_handler.assert_called_once_with(validated)
        risk_handler.assert_not_called()

    def test_no_handlers_registered(self):
        """Test publishing to event type with no handlers"""
        bus = EventBus()

        # Publish event with no handlers - should not raise
        signal = SignalDetected(
            symbol="USDJPY", side="SELL", strength=0.6, strategy_id="test"
        )
        bus.publish(signal)  # Should not raise

        # Verify stats
        stats = bus.get_stats()
        assert stats["events_published"] == 1
        assert stats["handlers_called"] == 0
        assert stats["errors"] == 0

    def test_handler_exception_doesnt_stop_others(self):
        """Test that handler exceptions don't stop other handlers"""
        bus = EventBus()

        def failing_handler(event):
            raise ValueError("Handler failed")

        working_handler = Mock()

        # Subscribe handlers
        bus.subscribe(SignalDetected, failing_handler)
        bus.subscribe(SignalDetected, working_handler)

        # Publish event
        signal = SignalDetected(
            symbol="XAUUSD", side="BUY", strength=0.8, strategy_id="test"
        )
        bus.publish(signal)

        # Working handler should still be called despite failing handler
        working_handler.assert_called_once_with(signal)

        # Verify error was recorded
        stats = bus.get_stats()
        assert stats["events_published"] == 1
        assert stats["handlers_called"] == 1  # Only working handler counted
        assert stats["errors"] == 1

    def test_unsubscribe(self):
        """Test handler unsubscription"""
        bus = EventBus()
        handler1 = Mock()
        handler2 = Mock()

        # Subscribe handlers
        bus.subscribe(SignalDetected, handler1)
        bus.subscribe(SignalDetected, handler2)

        # Unsubscribe handler1
        result = bus.unsubscribe(SignalDetected, handler1)
        assert result is True

        # Publish event
        signal = SignalDetected(
            symbol="XAUUSD", side="BUY", strength=0.7, strategy_id="test"
        )
        bus.publish(signal)

        # Only handler2 should be called
        handler1.assert_not_called()
        handler2.assert_called_once_with(signal)

    def test_unsubscribe_nonexistent_handler(self):
        """Test unsubscribing handler that wasn't subscribed"""
        bus = EventBus()
        handler = Mock()

        # Try to unsubscribe without subscribing first
        result = bus.unsubscribe(SignalDetected, handler)
        assert result is False

    def test_get_handlers(self):
        """Test getting handlers for event type"""
        bus = EventBus()
        handler1 = Mock()
        handler2 = Mock()

        # Initially no handlers
        handlers = bus.get_handlers(SignalDetected)
        assert handlers == []

        # Subscribe handlers
        bus.subscribe(SignalDetected, handler1)
        bus.subscribe(SignalDetected, handler2)

        # Get handlers
        handlers = bus.get_handlers(SignalDetected)
        assert len(handlers) == 2
        assert handler1 in handlers
        assert handler2 in handlers

        # Should return copy (safe to modify)
        handlers.clear()
        original_handlers = bus.get_handlers(SignalDetected)
        assert len(original_handlers) == 2  # Original not affected

    def test_clear(self):
        """Test clearing all handlers and stats"""
        bus = EventBus()
        handler = Mock()

        # Subscribe and publish to generate stats
        bus.subscribe(SignalDetected, handler)
        signal = SignalDetected(
            symbol="XAUUSD", side="BUY", strength=0.8, strategy_id="test"
        )
        bus.publish(signal)

        # Verify initial state
        assert len(bus) == 1
        assert bus.get_stats()["events_published"] == 1

        # Clear
        bus.clear()

        # Verify cleared state
        assert len(bus) == 0
        assert bus.get_handlers(SignalDetected) == []
        assert bus.get_stats()["events_published"] == 0

    def test_stats_tracking(self):
        """Test event bus statistics tracking"""
        bus = EventBus()
        handler1 = Mock()
        handler2 = Mock()

        def failing_handler(event):
            raise Exception("Failed")

        # Subscribe handlers
        bus.subscribe(SignalDetected, handler1)
        bus.subscribe(SignalDetected, handler2)
        bus.subscribe(SignalDetected, failing_handler)

        # Publish event
        signal = SignalDetected(
            symbol="XAUUSD", side="BUY", strength=0.8, strategy_id="test"
        )
        bus.publish(signal)

        # Check stats
        stats = bus.get_stats()
        assert stats["events_published"] == 1
        assert stats["handlers_called"] == 2  # Two successful calls
        assert stats["errors"] == 1  # One failed call

    def test_repr(self):
        """Test string representation"""
        bus = EventBus()

        # Empty bus
        assert repr(bus) == "EventBus({})"

        # With handlers
        handler1 = Mock()
        handler2 = Mock()
        bus.subscribe(SignalDetected, handler1)
        bus.subscribe(SignalDetected, handler2)
        bus.subscribe(Validated, handler1)

        repr_str = repr(bus)
        assert "EventBus(" in repr_str
        assert "SignalDetected" in repr_str
        assert "Validated" in repr_str

    def test_len(self):
        """Test length (total handler count)"""
        bus = EventBus()
        assert len(bus) == 0

        handler1 = Mock()
        handler2 = Mock()

        bus.subscribe(SignalDetected, handler1)
        assert len(bus) == 1

        bus.subscribe(SignalDetected, handler2)
        assert len(bus) == 2

        bus.subscribe(Validated, handler1)
        assert len(bus) == 3

    def test_invalid_handler(self):
        """Test subscribing non-callable handler raises error"""
        bus = EventBus()

        with pytest.raises(ValueError, match="Handler must be callable"):
            bus.subscribe(SignalDetected, "not_callable")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
