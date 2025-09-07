"""
Demo script showing the event-driven trading pipeline in action
with idempotent order execution
"""

import logging
from pathlib import Path

from app import build_pipeline
from config.settings import get_settings
from core.broker import BrokerGateway, OrderRequest, OrderResult, OrderType, Side
from core.events import EventBus, SignalDetected
from core.executor import IdempotentOrderExecutor, make_coid

# Setup logging to see the flow
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(name)s - %(message)s")


class DemoBroker(BrokerGateway):
    """Demo broker that simulates order execution with logging"""

    def __init__(self):
        self.connected = True
        self.order_counter = 0

    def connect(self) -> None:
        print("🔌 DemoBroker: Connected")
        self.connected = True

    def is_connected(self) -> bool:
        return self.connected

    def place_order(self, request: OrderRequest) -> OrderResult:
        """Simulate order placement with realistic responses"""
        self.order_counter += 1

        print(f"📤 DemoBroker: Received order {request.client_order_id}")
        print(f"   Symbol: {request.symbol}, Side: {request.side}, Qty: {request.qty}")

        # Simulate order acceptance
        broker_order_id = f"DEMO_{self.order_counter:06d}"

        print(f"✅ DemoBroker: Order accepted as {broker_order_id}")

        return OrderResult(
            accepted=True,
            broker_order_id=broker_order_id,
            reason=f"Demo execution #{self.order_counter}",
        )

    def cancel(self, broker_order_id: str) -> bool:
        print(f"❌ DemoBroker: Cancel requested for {broker_order_id}")
        return True

    def positions(self) -> list:
        return []


def demo_event_pipeline():
    """Demonstrate the event-driven trading pipeline with idempotent execution"""
    print("🚀 Event-Driven Trading Pipeline Demo (with Idempotent Execution)\n")

    # Create dependencies
    settings = get_settings()
    bus = EventBus()
    broker = DemoBroker()

    # Create demo database
    demo_db = "demo_idempotent.sqlite"
    Path(demo_db).unlink(missing_ok=True)  # Clean slate

    print(f"💾 Using demo idempotency database: {demo_db}")

    # Build and wire the pipeline
    pipeline = build_pipeline(settings, bus, broker)

    print(f"📊 EventBus stats: {bus.get_stats()}")
    print(f"🔧 Pipeline handlers registered: {len(bus)} total handlers\n")

    # Demonstrate client order ID generation
    print("🔑 Client Order ID Generation:")
    strategy = "demo_strategy"
    timestamp = "20250907_1530"
    coid1 = make_coid("XAUUSD", "BUY", strategy, timestamp)
    coid2 = make_coid("XAUUSD", "BUY", strategy, timestamp)
    coid3 = make_coid("XAUUSD", "BUY", strategy, "20250907_1531")  # Different time
    print(f"   Generated COID (call 1): {coid1}")
    print(f"   Generated COID (call 2): {coid2}")
    print(f"   Generated COID (call 3): {coid3}")
    print(f"   Deterministic (1==2): {'✅' if coid1 == coid2 else '❌'}")
    print(f"   Different (1!=3): {'✅' if coid1 != coid3 else '❌'}\n")

    # Create idempotent executor to demonstrate duplicate detection
    executor = IdempotentOrderExecutor(broker, demo_db)
    print(f"🛡️  IdempotentOrderExecutor created with database: {demo_db}\n")

    # NOTE: For demo purposes, we'll send signals within the same minute
    # so they get the same timestamp bucket and show idempotency in action
    print(
        "⏰ Sending signals within same minute bucket to demonstrate idempotency...\n"
    )

    # First signal - should execute normally
    print("📡 Publishing first SignalDetected event...")
    signal1 = SignalDetected(
        symbol="XAUUSD", side="BUY", strength=0.85, strategy_id=strategy
    )

    bus.publish(signal1)
    print()

    # Second signal with SAME parameters within same minute - should be blocked by idempotency
    print(
        "📡 Publishing DUPLICATE SignalDetected event (same parameters, same minute)..."
    )
    signal2 = SignalDetected(
        symbol="XAUUSD",
        side="BUY",
        strength=0.90,  # Different strength but same key fields
        strategy_id=strategy,  # Same strategy = same COID within same minute
    )

    bus.publish(signal2)
    print()

    # Third signal with different symbol - should execute normally
    print("📡 Publishing NEW SignalDetected event (different symbol)...")
    signal3 = SignalDetected(
        symbol="EURUSD",  # Different symbol = different COID
        side="BUY",
        strength=0.75,
        strategy_id=strategy,
    )

    bus.publish(signal3)
    print()

    # Show sent orders history
    sent_orders = executor.get_sent_orders()
    print(f"📋 Order History ({len(sent_orders)} records):")
    for order in sent_orders:
        print(f"   COID: {order['client_order_id']}")
        print(f"   Broker ID: {order['broker_order_id']}")
        print(f"   Timestamp: {order['ts']}\n")

    # Show final stats
    print(f"📈 Final EventBus stats: {bus.get_stats()}")
    print("✅ Demo completed - check logs above for event flow and idempotency")

    # Cleanup demo database (ignore errors on Windows)
    try:
        Path(demo_db).unlink(missing_ok=True)
        print(f"🧹 Cleaned up demo database: {demo_db}")
    except PermissionError:
        print(f"🧹 Demo database cleanup skipped (file in use): {demo_db}")


if __name__ == "__main__":
    demo_event_pipeline()
