"""
In-process EventBus implementation - Synchronous publish/subscribe pattern
Lightweight event handling for domain events within the trading pipeline.
"""

import logging
from collections import defaultdict
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class EventBus:
    """
    Synchronous in-process event bus using publish/subscribe pattern.

    Handlers are called immediately when events are published.
    Thread-safety is not guaranteed in v1 - designed for single-threaded use.

    Example usage:
        bus = EventBus()

        def handle_signal(event: SignalDetected):
            print(f"Processing signal: {event.symbol}")

        bus.subscribe(SignalDetected, handle_signal)
        bus.publish(SignalDetected(symbol="XAUUSD", side="BUY", strength=0.85))
    """

    def __init__(self):
        """Initialize empty event bus"""
        self._handlers: dict[type, list[Callable[[Any], None]]] = defaultdict(list)
        self._stats = {"events_published": 0, "handlers_called": 0, "errors": 0}

    def subscribe(self, event_type: type, handler: Callable[[Any], None]) -> None:
        """
        Subscribe a handler to events of a specific type.

        Args:
            event_type: The event class to listen for (exact type match)
            handler: Callable that accepts the event as single argument

        Note:
            - Only exact type matches trigger handlers (no inheritance)
            - Multiple handlers can subscribe to the same event type
            - Handler execution order is not guaranteed
        """
        if not callable(handler):
            raise ValueError(f"Handler must be callable, got {type(handler)}")

        self._handlers[event_type].append(handler)
        handler_name = getattr(handler, "__name__", str(handler))
        logger.debug(f"Subscribed handler {handler_name} to {event_type.__name__}")

    def publish(self, event: Any) -> None:
        """
        Publish an event to all registered handlers for its type.

        Args:
            event: Event instance to publish

        Behavior:
            - Calls all handlers registered for the exact event type
            - Handlers are called synchronously in subscription order
            - If a handler raises an exception, it's logged but doesn't stop other handlers
            - No return value - fire-and-forget pattern
        """
        event_type = type(event)
        handlers = self._handlers.get(event_type, [])

        logger.debug(f"Publishing {event_type.__name__} to {len(handlers)} handlers")

        self._stats["events_published"] += 1

        for handler in handlers:
            try:
                handler(event)
                self._stats["handlers_called"] += 1
                handler_name = getattr(handler, "__name__", str(handler))
                logger.debug(f"Called handler {handler_name} for {event_type.__name__}")

            except Exception as e:
                self._stats["errors"] += 1
                handler_name = getattr(handler, "__name__", str(handler))
                logger.error(
                    f"Handler {handler_name} failed for {event_type.__name__}: {e}",
                    exc_info=True,
                )
                # Continue calling other handlers even if one fails

    def unsubscribe(self, event_type: type, handler: Callable[[Any], None]) -> bool:
        """
        Remove a handler from an event type.

        Args:
            event_type: The event class to unsubscribe from
            handler: The specific handler to remove

        Returns:
            bool: True if handler was found and removed, False otherwise
        """
        if event_type not in self._handlers:
            return False

        try:
            self._handlers[event_type].remove(handler)
            handler_name = getattr(handler, "__name__", str(handler))
            logger.debug(
                f"Unsubscribed handler {handler_name} from {event_type.__name__}"
            )
            return True
        except ValueError:
            return False

    def clear(self) -> None:
        """Remove all event handlers and reset statistics"""
        self._handlers.clear()
        self._stats = {"events_published": 0, "handlers_called": 0, "errors": 0}
        logger.debug("Cleared all event handlers")

    def get_handlers(self, event_type: type) -> list[Callable[[Any], None]]:
        """
        Get list of handlers registered for an event type.

        Args:
            event_type: Event class to check

        Returns:
            List of handler functions (copy, safe to modify)
        """
        return self._handlers.get(event_type, []).copy()

    def get_stats(self) -> dict[str, int]:
        """
        Get event bus statistics.

        Returns:
            Dictionary with events_published, handlers_called, errors counts
        """
        return self._stats.copy()

    def __len__(self) -> int:
        """Return total number of registered handlers across all event types"""
        return sum(len(handlers) for handlers in self._handlers.values())

    def __repr__(self) -> str:
        """String representation showing handler counts by event type"""
        handler_counts = {
            event_type.__name__: len(handlers)
            for event_type, handlers in self._handlers.items()
            if handlers
        }
        return f"EventBus({handler_counts})"
