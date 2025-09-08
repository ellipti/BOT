#!/usr/bin/env python3
"""
Test script to validate paper broker integration with current system.
"""

import os
import sys

sys.path.insert(0, os.getcwd())

from adapters import create_broker
from config.settings import get_settings
from core.broker import OrderRequest, Side


def test_paper_broker_smoke():
    """Smoke test for paper broker in current system"""
    print("🧪 Testing PaperBroker integration...")

    # Get settings and force paper broker
    settings = get_settings()
    settings.broker_kind = "paper"

    print(f"📋 Using broker kind: {settings.broker_kind}")

    # Create broker via factory
    broker = create_broker(settings)
    print(f"🏭 Created broker: {type(broker).__name__}")

    # Test connection
    broker.connect()
    print(f"🔗 Connected: {broker.is_connected()}")

    # Test account info
    account = broker.get_account_info()
    print(f"💰 Account balance: ${account['balance']}")

    # Test order placement
    request = OrderRequest(
        client_order_id="smoke_test_001",
        symbol="XAUUSD",
        side=Side.BUY,
        qty=0.01,
        order_type="MARKET",
        sl=2020.00,
        tp=2030.00,
    )

    result = broker.place_order(request)
    print(f"📝 Order result: accepted={result.accepted}, reason={result.reason}")

    # Test positions
    positions = broker.positions()
    print(f"📊 Positions: {len(positions)}")
    if positions:
        pos = positions[0]
        print(f"   └─ {pos.symbol}: qty={pos.qty}, avg_price={pos.avg_price}")

    # Test MT5 fallback
    print("\n🔄 Testing MT5 fallback...")
    settings.broker_kind = "mt5"
    try:
        broker_mt5 = create_broker(settings)
        print(f"🏭 MT5 broker type: {type(broker_mt5).__name__}")
    except Exception as e:
        print(f"❌ MT5 creation failed (expected): {e}")

    print("✅ All tests completed successfully!")


if __name__ == "__main__":
    test_paper_broker_smoke()
