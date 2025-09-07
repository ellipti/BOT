"""
Order Lifecycle V2 Integration Example
Demonstrates the complete order lifecycle system with:
- OrderBook SQLite state management
- ReconciliationEngine background polling
- TrailingStopManager breakeven/trailing logic
- Event-driven lifecycle management
"""

import logging
import threading
import time
from typing import Optional
from unittest.mock import Mock

from core.events.bus import EventBus
from core.events.types import (
    BreakevenTriggered,
    Cancelled,
    Filled,
    PartiallyFilled,
    PendingActivated,
    PendingCreated,
    SignalDetected,
    StopUpdated,
)
from core.executor.order_book import OrderBook, OrderStatus
from core.executor.reconciler import ReconciliationEngine
from risk.trailing import TrailingStopManager

logger = logging.getLogger(__name__)


class OrderLifecycleV2Demo:
    """
    Complete demonstration of Order Lifecycle V2 system

    Shows integration of:
    - Event bus for lifecycle events
    - OrderBook for state persistence
    - ReconciliationEngine for MT5 sync
    - TrailingStopManager for profit protection
    """

    def __init__(self, mt5=None):
        """Initialize the complete order lifecycle system"""
        self.event_bus = EventBus()
        self.order_book = OrderBook("demo_order_lifecycle.sqlite")
        self.mt5 = mt5 or self._create_mock_mt5()

        # Initialize core components
        self.reconciler = ReconciliationEngine(
            self.mt5, self.event_bus, self.order_book, poll_interval=1.0
        )
        self.trailing_manager = TrailingStopManager(self.mt5)

        # Event handlers
        self._setup_event_handlers()

        logger.info("Order Lifecycle V2 system initialized")

    def _create_mock_mt5(self):
        """Create mock MT5 for demonstration"""
        mt5 = Mock()
        mt5.TRADE_ACTION_SLTP = 2
        mt5.TRADE_RETCODE_DONE = 10009

        # Mock symbol info
        def symbol_info(symbol):
            info = Mock()
            info.point = 0.0001 if "JPY" not in symbol else 0.01
            return info

        mt5.symbol_info = symbol_info

        # Mock successful position updates
        def order_send(request):
            result = Mock()
            result.retcode = mt5.TRADE_RETCODE_DONE
            return result

        mt5.order_send = order_send

        # Mock empty positions and orders for reconciler
        mt5.positions_get = Mock(return_value=[])
        mt5.orders_get = Mock(return_value=[])
        mt5.history_deals_get = Mock(return_value=[])

        return mt5

    def _setup_event_handlers(self):
        """Setup event handlers for order lifecycle"""

        def on_signal_detected(event):
            """Handle trading signals by creating pending orders"""
            logger.info(
                f"📊 Signal detected: {event.symbol} {event.side} strength={event.strength}"
            )

            # Create pending order
            coid = f"SIG_{int(time.time()*1000)}"
            self.order_book.create_pending(
                coid=coid,
                symbol=event.symbol,
                side=event.side,
                qty=1.0,  # Fixed size for demo
                sl=event.stop_loss if hasattr(event, "stop_loss") else None,
                tp=event.take_profit if hasattr(event, "take_profit") else None,
            )

            # Emit pending created event
            self.event_bus.publish(
                PendingCreated(
                    client_order_id=coid, symbol=event.symbol, side=event.side, qty=1.0
                )
            )

        def on_pending_activated(event):
            """Handle order activation on broker"""
            logger.info(
                f"✅ Order activated: {event.client_order_id} → {event.broker_order_id}"
            )

        def on_partial_fill(event):
            """Handle partial fills"""
            logger.info(
                f"📈 Partial fill: {event.client_order_id} "
                f"+{event.fill_quantity}@{event.fill_price} "
                f"→ {event.total_filled}/{event.total_filled + event.remaining_quantity}"
            )

        def on_filled(event):
            """Handle complete fills"""
            logger.info(f"🎯 Order filled: {event.client_order_id} @ {event.price}")

            # Trigger breakeven/trailing logic for filled orders
            self._trigger_trailing_management()

        def on_cancelled(event):
            """Handle order cancellations"""
            logger.info(f"❌ Order cancelled: {event.client_order_id} - {event.reason}")

        def on_breakeven_triggered(event):
            """Handle breakeven triggers"""
            logger.info(
                f"🛡️ Breakeven triggered: {event.position_id} @ {event.breakeven_price}"
            )

        def on_stop_updated(event):
            """Handle stop loss updates"""
            logger.info(
                f"🔄 Stop updated: {event.position_id} SL={event.new_sl} TP={event.new_tp}"
            )

        # Subscribe handlers
        self.event_bus.subscribe(SignalDetected, on_signal_detected)
        self.event_bus.subscribe(PendingActivated, on_pending_activated)
        self.event_bus.subscribe(PartiallyFilled, on_partial_fill)
        self.event_bus.subscribe(Filled, on_filled)
        self.event_bus.subscribe(Cancelled, on_cancelled)
        self.event_bus.subscribe(BreakevenTriggered, on_breakeven_triggered)
        self.event_bus.subscribe(StopUpdated, on_stop_updated)

    def _trigger_trailing_management(self):
        """Process trailing stop management for all positions"""
        try:
            actions = self.trailing_manager.process_all_positions(
                breakeven_threshold=10.0,  # 10 pips for breakeven
                breakeven_buffer=2.0,  # 2 pips buffer
                trailing_step=5.0,  # 5 pips minimum step
                trailing_buffer=10.0,  # 10 pips trailing buffer
            )

            # Emit events for trailing actions
            for ticket, action in actions.items():
                if action == "breakeven":
                    self.event_bus.publish(
                        BreakevenTriggered(
                            position_id=ticket,
                            symbol="UNKNOWN",  # Would get from position
                            breakeven_price=0.0,  # Would calculate actual price
                            timestamp=time.time(),
                        )
                    )
                elif action == "trailing":
                    self.event_bus.publish(
                        StopUpdated(
                            position_id=ticket,
                            symbol="UNKNOWN",  # Would get from position
                            new_sl=0.0,  # Would get actual SL
                            new_tp=None,
                            timestamp=time.time(),
                        )
                    )

        except Exception as e:
            logger.error(f"Error in trailing management: {e}")

    def start(self):
        """Start the order lifecycle system"""
        logger.info("🚀 Starting Order Lifecycle V2 system...")

        # Start reconciliation engine
        self.reconciler.start()

        logger.info("✅ Order Lifecycle V2 system started")

    def stop(self):
        """Stop the order lifecycle system"""
        logger.info("🛑 Stopping Order Lifecycle V2 system...")

        # Stop reconciliation engine
        self.reconciler.stop()

        # Cleanup
        self.trailing_manager.cleanup_closed_positions()
        self.order_book.cleanup_old_orders()

        logger.info("✅ Order Lifecycle V2 system stopped")

    def simulate_trading_session(self, duration_seconds: int = 30):
        """Simulate a trading session with various order events"""
        logger.info(f"🎬 Starting trading session simulation ({duration_seconds}s)")

        start_time = time.time()

        # Simulate signals at intervals
        signal_count = 0
        while time.time() - start_time < duration_seconds:
            if signal_count < 3:  # Generate 3 signals
                # Simulate trading signal
                self.event_bus.publish(
                    SignalDetected(
                        symbol="EURUSD",
                        side="BUY",
                        strength=0.85,  # Signal confidence/strength
                        strategy_id="demo_strategy_rsi_macd",
                    )
                )
                signal_count += 1

            time.sleep(5)  # Wait between events

        logger.info("🎬 Trading session simulation completed")

    def get_system_status(self) -> dict:
        """Get current status of all system components"""
        try:
            active_orders = self.order_book.get_active_orders()
            order_counts = self.order_book.get_order_count_by_status()

            return {
                "reconciler_running": self.reconciler._running,
                "active_orders": len(active_orders),
                "order_counts_by_status": order_counts,
                "trailing_positions": len(self.trailing_manager._position_states),
                "processed_deals": len(self.reconciler._processed_deals),
            }
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {"error": str(e)}


def run_demo():
    """Run the complete Order Lifecycle V2 demonstration"""
    print("🎯 Order Lifecycle V2 - Complete Integration Demo")
    print("=" * 60)

    # Create and start the system
    system = OrderLifecycleV2Demo()

    try:
        # Start the system
        system.start()

        # Show initial status
        status = system.get_system_status()
        print(f"📊 Initial Status: {status}")

        # Run simulation
        system.simulate_trading_session(duration_seconds=15)

        # Show final status
        status = system.get_system_status()
        print(f"📊 Final Status: {status}")

        # Show order book contents
        active_orders = system.order_book.get_active_orders()
        print(f"\n📋 Active Orders: {len(active_orders)}")
        for order in active_orders:
            print(
                f"  - {order.coid}: {order.symbol} {order.side} {order.qty} [{order.status}]"
            )

    except Exception as e:
        print(f"❌ Demo failed: {e}")
        logger.exception("Demo exception")

    finally:
        # Clean shutdown
        system.stop()

    print("\n🎉 Order Lifecycle V2 demo completed!")


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S",
    )

    # Run the demonstration
    run_demo()
