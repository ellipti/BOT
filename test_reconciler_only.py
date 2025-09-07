#!/usr/bin/env python3
"""
Test just the reconciler functionality with mock MT5 - skip broker integration for now.
"""

import os
import sys
import time
from unittest.mock import Mock, patch

# Add the project root to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from core.executor.reconciler import (
    get_current_tick_price,
    get_deal_price,
    wait_for_fill,
)


class MockDeal:
    def __init__(
        self, ticket, comment="", symbol="XAUUSD", type=1, volume=0.1, price=2500.0
    ):
        self.ticket = ticket
        self.comment = comment
        self.symbol = symbol
        self.type = type
        self.volume = volume
        self.price = price


def test_reconciler_core():
    """Test core reconciliation functionality"""
    print("🔄 Testing Core Reconciliation...")

    # Create mock MT5
    mock_mt5 = Mock()

    # Test 1: Immediate fill
    print("\n1️⃣ Testing immediate fill...")
    mock_mt5.history_deals_get.return_value = [MockDeal(12345, "test_order_123")]

    start = time.time()
    found, ticket = wait_for_fill(mock_mt5, "test_order_123", "XAUUSD", timeout_sec=1.0)
    elapsed = time.time() - start

    print(f"   Debug: found={found}, ticket={ticket}, ticket_type={type(ticket)}")
    assert found, "Should find deal immediately"
    assert (
        ticket == "12345"
    ), f"Should return correct ticket as string, got {ticket} (type: {type(ticket)})"
    assert elapsed < 0.1, f"Should be fast: {elapsed:.3f}s"
    print(f"   ✅ Found deal {ticket} in {elapsed:.3f}s")

    # Test 2: Delayed fill
    print("\n2️⃣ Testing delayed fill...")
    mock_mt5.reset_mock()
    mock_mt5.history_deals_get.side_effect = [
        [],  # First call: no deals
        [],  # Second call: no deals
        [MockDeal(12346, "test_order_456")],  # Third call: deal appears
    ]

    start = time.time()
    found, ticket = wait_for_fill(
        mock_mt5, "test_order_456", "XAUUSD", timeout_sec=2.0, poll=0.1
    )
    elapsed = time.time() - start

    assert found, "Should find deal after delay"
    assert ticket == "12346", "Should return correct ticket"
    assert 0.15 < elapsed < 0.5, f"Should take ~0.2s: {elapsed:.3f}s"
    print(
        f"   ✅ Found deal {ticket} in {elapsed:.3f}s after {mock_mt5.history_deals_get.call_count} polls"
    )

    # Test 3: Timeout
    print("\n3️⃣ Testing timeout...")
    mock_mt5.reset_mock()
    mock_mt5.history_deals_get.return_value = []  # Never returns deals

    start = time.time()
    found, ticket = wait_for_fill(
        mock_mt5, "test_order_timeout", "XAUUSD", timeout_sec=0.3, poll=0.05
    )
    elapsed = time.time() - start

    assert not found, "Should timeout"
    assert ticket is None, "Should return None ticket on timeout"
    assert 0.25 < elapsed < 0.4, f"Should timeout at ~0.3s: {elapsed:.3f}s"
    print(
        f"   ✅ Timeout after {elapsed:.3f}s with {mock_mt5.history_deals_get.call_count} polls"
    )


def test_utility_functions():
    """Test utility functions"""
    print("\n🔧 Testing Utility Functions...")

    # Test get_deal_price
    mock_mt5 = Mock()
    deal = MockDeal(12345, "test", price=2500.75)
    mock_mt5.history_deals_get.return_value = [deal]

    price = get_deal_price(mock_mt5, "12345", "XAUUSD")
    assert price == 2500.75, f"Expected 2500.75, got {price}"
    print(f"   ✅ get_deal_price: {price}")

    # Test get_current_tick_price
    mock_mt5.reset_mock()
    mock_tick = Mock()
    mock_tick.bid = 2499.50
    mock_tick.ask = 2500.50
    mock_mt5.symbol_info_tick.return_value = mock_tick

    mid_price = get_current_tick_price(mock_mt5, "XAUUSD", "BUY")
    expected = 2500.50  # Should return ask price for BUY side
    assert mid_price == expected, f"Expected {expected}, got {mid_price}"
    print(f"   ✅ get_current_tick_price: {mid_price} (BUY side, ask={mock_tick.ask})")


if __name__ == "__main__":
    print("=" * 60)
    print("🚀 RECONCILER CORE TESTS")
    print("=" * 60)

    try:
        test_reconciler_core()
        test_utility_functions()

        print("\n" + "=" * 60)
        print("✅ ALL RECONCILER TESTS PASSED!")
        print("📊 Summary:")
        print("   • Immediate fill: < 0.1s")
        print("   • Delayed fill: ~0.2s")
        print("   • Timeout: ~0.3s")
        print("   • Utility functions: Working")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
