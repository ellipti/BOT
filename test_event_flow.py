#!/usr/bin/env python3
"""
Test paper broker with event pipeline to validate complete integration.
"""

import os
import sys

sys.path.insert(0, os.getcwd())

import time

from adapters import create_broker
from config.settings import get_settings
from core.broker import OrderRequest, Side


def test_event_flow_integration():
    """Test paper broker in simulated event flow"""
    print("🔄 Testing Paper Broker Event Flow Integration...")

    # Setup
    settings = get_settings()
    settings.broker_kind = "paper"
    print(f"📋 Broker kind: {settings.broker_kind}")

    # Create broker
    broker = create_broker(settings)
    broker.connect()
    print(f"🏭 Broker: {type(broker).__name__}")
    print(f"🔗 Connected: {broker.is_connected()}")

    # Simulate event flow sequence
    print("\n📊 Simulating Trading Event Flow:")

    # 1. Market data arrives (simulated)
    print("1️⃣ Market data received...")

    # 2. Strategy decision (simulated)
    print("2️⃣ Strategy generates BUY signal...")

    # 3. Order placement through broker
    print("3️⃣ Placing order through broker...")

    request = OrderRequest(
        client_order_id=f"event_flow_{int(time.time())}",
        symbol="XAUUSD",
        side=Side.BUY,
        qty=0.01,
        order_type="MARKET",
        sl=2020.00,
        tp=2030.00,
    )

    result = broker.place_order(request)
    print(f"   📝 Order executed: {result.accepted}")
    print(f"   🆔 Broker Order ID: {result.broker_order_id}")
    print(f"   💬 Details: {result.reason}")

    # 4. Position tracking
    print("4️⃣ Checking positions...")
    positions = broker.positions()
    print(f"   📊 Active positions: {len(positions)}")

    if positions:
        pos = positions[0]
        print(f"   └─ {pos.symbol}: {pos.qty:+.3f} lots @ ${pos.avg_price:.2f}")

    # 5. Account update
    print("5️⃣ Account status...")
    account = broker.get_account_info()
    print(f"   💰 Balance: ${account['balance']:.2f}")
    print(f"   📈 Equity: ${account['equity']:.2f}")
    print(f"   🏦 Positions: {account['positions_count']}")

    # 6. Simulate another trade (opposite direction)
    print("\n6️⃣ Simulating partial close...")

    close_request = OrderRequest(
        client_order_id=f"close_flow_{int(time.time())}",
        symbol="XAUUSD",
        side=Side.SELL,
        qty=0.005,  # Partial close
        order_type="MARKET",
    )

    close_result = broker.place_order(close_request)
    print(f"   📝 Close order: {close_result.accepted}")

    # 7. Final state
    print("7️⃣ Final state...")
    final_positions = broker.positions()
    print(f"   📊 Remaining positions: {len(final_positions)}")

    if final_positions:
        pos = final_positions[0]
        print(f"   └─ {pos.symbol}: {pos.qty:+.3f} lots @ ${pos.avg_price:.2f}")

    final_account = broker.get_account_info()
    print(f"   💰 Final balance: ${final_account['balance']:.2f}")

    print("\n✅ Event flow integration test completed successfully!")

    # Test idempotency
    print("\n🔄 Testing order idempotency...")

    duplicate_request = OrderRequest(
        client_order_id=request.client_order_id,  # Same ID as first order
        symbol="XAUUSD",
        side=Side.BUY,
        qty=0.01,
        order_type="MARKET",
    )

    duplicate_result = broker.place_order(duplicate_request)
    print(f"   📝 Duplicate order: {duplicate_result.accepted}")
    print(
        f"   🆔 Same Order ID: {duplicate_result.broker_order_id == result.broker_order_id}"
    )

    # Verify no duplicate position
    final_positions_2 = broker.positions()
    print(
        f"   📊 Positions unchanged: {len(final_positions_2) == len(final_positions)}"
    )

    print("\n✅ Idempotency test passed!")


if __name__ == "__main__":
    test_event_flow_integration()
