"""
Test Suite: Order Reconciliation System
Tests for wait_for_fill function with mocked MT5 deal history.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

from core.executor.reconciler import (
    get_current_tick_price,
    get_deal_price,
    wait_for_fill,
)

# Configure logging for tests
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class MockDeal:
    """Mock MT5 deal object"""

    def __init__(
        self, ticket: int, comment: str, price: float = 2500.0, symbol: str = "XAUUSD"
    ):
        self.ticket = ticket
        self.comment = comment
        self.price = price
        self.symbol = symbol


class MockTick:
    """Mock MT5 tick object"""

    def __init__(self, ask: float = 2501.0, bid: float = 2499.0):
        self.ask = ask
        self.bid = bid


def test_wait_for_fill_success_immediate():
    """Test successful fill detection on first poll"""
    # Mock MT5 module
    mock_mt5 = MagicMock()

    client_order_id = "test_coid_12345"
    deal_ticket = 98765432

    # Mock deal found immediately
    mock_deals = [
        MockDeal(ticket=deal_ticket, comment=client_order_id),
    ]
    mock_mt5.history_deals_get.return_value = mock_deals

    # Test
    found, ticket = wait_for_fill(
        mt5=mock_mt5,
        client_order_id=client_order_id,
        symbol="XAUUSD",
        timeout_sec=2.0,
        poll=0.1,
    )

    # Assertions
    assert found is True
    assert ticket == str(deal_ticket)

    # Verify MT5 was called
    mock_mt5.history_deals_get.assert_called()
    call_args = mock_mt5.history_deals_get.call_args
    assert call_args[1]["symbol"] == "XAUUSD"


def test_wait_for_fill_success_second_poll():
    """Test successful fill detection on second poll"""
    mock_mt5 = MagicMock()

    client_order_id = "test_coid_67890"
    deal_ticket = 11223344

    # Mock no deals on first call, deal on second call
    mock_mt5.history_deals_get.side_effect = [
        [],  # First poll: no deals
        [
            MockDeal(ticket=deal_ticket, comment=client_order_id)
        ],  # Second poll: deal found
    ]

    # Test
    found, ticket = wait_for_fill(
        mt5=mock_mt5,
        client_order_id=client_order_id,
        symbol="EURUSD",
        timeout_sec=1.0,
        poll=0.2,
    )

    # Assertions
    assert found is True
    assert ticket == str(deal_ticket)
    assert mock_mt5.history_deals_get.call_count == 2


def test_wait_for_fill_prefix_match():
    """Test fill detection with comment prefix match"""
    mock_mt5 = MagicMock()

    client_order_id = "test_coid_abc"
    deal_ticket = 55667788

    # Mock deal with comment that starts with client_order_id
    mock_deals = [
        MockDeal(ticket=deal_ticket, comment=f"{client_order_id}_extra_info"),
    ]
    mock_mt5.history_deals_get.return_value = mock_deals

    # Test
    found, ticket = wait_for_fill(
        mt5=mock_mt5,
        client_order_id=client_order_id,
        symbol="GBPUSD",
        timeout_sec=1.0,
        poll=0.1,
    )

    # Assertions
    assert found is True
    assert ticket == str(deal_ticket)


def test_wait_for_fill_timeout():
    """Test timeout when deal is never found"""
    mock_mt5 = MagicMock()

    client_order_id = "test_coid_timeout"

    # Mock no deals ever found
    mock_mt5.history_deals_get.return_value = []

    # Test with short timeout
    start_time = time.time()
    found, ticket = wait_for_fill(
        mt5=mock_mt5,
        client_order_id=client_order_id,
        symbol="XAUUSD",
        timeout_sec=0.5,
        poll=0.1,
    )
    elapsed = time.time() - start_time

    # Assertions
    assert found is False
    assert ticket is None
    assert elapsed >= 0.5  # Should respect timeout
    assert elapsed < 1.0  # Should not wait too long

    # Should have made multiple calls
    assert mock_mt5.history_deals_get.call_count >= 2


def test_wait_for_fill_no_matching_comment():
    """Test when deals exist but none match our comment"""
    mock_mt5 = MagicMock()

    client_order_id = "target_coid"

    # Mock deals with different comments
    mock_deals = [
        MockDeal(ticket=11111111, comment="other_coid_1"),
        MockDeal(ticket=22222222, comment="different_comment"),
        MockDeal(ticket=33333333, comment="target_coid_wrong"),  # Close but not exact
    ]
    mock_mt5.history_deals_get.return_value = mock_deals

    # Test with short timeout
    found, ticket = wait_for_fill(
        mt5=mock_mt5,
        client_order_id=client_order_id,
        symbol="XAUUSD",
        timeout_sec=0.3,
        poll=0.1,
    )

    # Assertions
    assert found is False
    assert ticket is None


def test_wait_for_fill_mt5_exception():
    """Test handling of MT5 exception during deal search"""
    mock_mt5 = MagicMock()

    client_order_id = "test_coid_exception"

    # Mock MT5 exception on first call, success on second
    deal_ticket = 99887766
    mock_mt5.history_deals_get.side_effect = [
        Exception("MT5 connection error"),
        [MockDeal(ticket=deal_ticket, comment=client_order_id)],
    ]

    # Test
    found, ticket = wait_for_fill(
        mt5=mock_mt5,
        client_order_id=client_order_id,
        symbol="XAUUSD",
        timeout_sec=1.0,
        poll=0.2,
    )

    # Should still succeed on second attempt
    assert found is True
    assert ticket == str(deal_ticket)


def test_wait_for_fill_none_mt5():
    """Test behavior when MT5 module is None"""
    found, ticket = wait_for_fill(
        mt5=None, client_order_id="test_coid", symbol="XAUUSD", timeout_sec=1.0
    )

    assert found is False
    assert ticket is None


def test_get_deal_price_success():
    """Test successful deal price retrieval"""
    mock_mt5 = MagicMock()

    deal_ticket = "12345678"
    expected_price = 2501.75

    mock_deals = [
        MockDeal(ticket=12345678, comment="test", price=expected_price),
        MockDeal(ticket=87654321, comment="other", price=2500.00),
    ]
    mock_mt5.history_deals_get.return_value = mock_deals

    # Test
    price = get_deal_price(mock_mt5, deal_ticket, "XAUUSD")

    # Assertions
    assert price == expected_price
    mock_mt5.history_deals_get.assert_called_once()


def test_get_deal_price_not_found():
    """Test deal price retrieval when deal not found"""
    mock_mt5 = MagicMock()

    deal_ticket = "99999999"

    mock_deals = [
        MockDeal(ticket=12345678, comment="test", price=2500.00),
    ]
    mock_mt5.history_deals_get.return_value = mock_deals

    # Test
    price = get_deal_price(mock_mt5, deal_ticket, "XAUUSD")

    # Assertions
    assert price is None


def test_get_current_tick_price_buy():
    """Test current tick price retrieval for BUY order"""
    mock_mt5 = MagicMock()

    expected_ask = 2501.25
    mock_tick = MockTick(ask=expected_ask, bid=2499.75)
    mock_mt5.symbol_info_tick.return_value = mock_tick

    # Test
    price = get_current_tick_price(mock_mt5, "XAUUSD", "BUY")

    # Assertions
    assert price == expected_ask
    mock_mt5.symbol_info_tick.assert_called_once_with("XAUUSD")


def test_get_current_tick_price_sell():
    """Test current tick price retrieval for SELL order"""
    mock_mt5 = MagicMock()

    expected_bid = 2499.50
    mock_tick = MockTick(ask=2501.00, bid=expected_bid)
    mock_mt5.symbol_info_tick.return_value = mock_tick

    # Test
    price = get_current_tick_price(mock_mt5, "XAUUSD", "SELL")

    # Assertions
    assert price == expected_bid


def test_get_current_tick_price_no_tick():
    """Test current tick price when tick data unavailable"""
    mock_mt5 = MagicMock()
    mock_mt5.symbol_info_tick.return_value = None

    # Test
    price = get_current_tick_price(mock_mt5, "INVALID_SYMBOL", "BUY")

    # Assertions
    assert price is None


def test_get_current_tick_price_invalid_side():
    """Test current tick price with invalid side"""
    mock_mt5 = MagicMock()
    mock_tick = MockTick(ask=2501.00, bid=2499.00)
    mock_mt5.symbol_info_tick.return_value = mock_tick

    # Test
    price = get_current_tick_price(mock_mt5, "XAUUSD", "INVALID")

    # Assertions
    assert price is None


@pytest.mark.parametrize(
    "timeout,poll,expected_calls",
    [
        (1.0, 0.2, 5),  # 1s timeout, 0.2s poll -> ~5 calls
        (0.5, 0.1, 5),  # 0.5s timeout, 0.1s poll -> ~5 calls
        (2.0, 0.5, 4),  # 2s timeout, 0.5s poll -> ~4 calls
    ],
)
def test_wait_for_fill_polling_behavior(timeout, poll, expected_calls):
    """Test polling behavior with different timeout and poll settings"""
    mock_mt5 = MagicMock()
    mock_mt5.history_deals_get.return_value = []  # Never find the deal

    start_time = time.time()
    found, ticket = wait_for_fill(
        mt5=mock_mt5,
        client_order_id="test_polling",
        symbol="XAUUSD",
        timeout_sec=timeout,
        poll=poll,
    )
    elapsed = time.time() - start_time

    # Assertions
    assert found is False
    assert ticket is None
    assert abs(elapsed - timeout) < 0.2  # Within 200ms of expected timeout

    # Should make approximately expected number of calls (±1)
    actual_calls = mock_mt5.history_deals_get.call_count
    assert abs(actual_calls - expected_calls) <= 1


def test_integration_reconciler_flow():
    """Integration test for complete reconciliation flow"""
    mock_mt5 = MagicMock()

    # Scenario: Order placed, deal appears after short delay
    client_order_id = "integration_test_coid"
    deal_ticket = 12345678
    deal_price = 2502.50
    symbol = "XAUUSD"

    # Mock: no deal on first 2 polls, then deal appears
    mock_mt5.history_deals_get.side_effect = [
        [],  # Poll 1: nothing
        [],  # Poll 2: nothing
        [
            MockDeal(ticket=deal_ticket, comment=client_order_id, price=deal_price)
        ],  # Poll 3: found!
    ]

    # Test reconciliation
    found, ticket = wait_for_fill(
        mt5=mock_mt5,
        client_order_id=client_order_id,
        symbol=symbol,
        timeout_sec=2.0,
        poll=0.2,
    )

    assert found is True
    assert ticket == str(deal_ticket)

    # Test price retrieval for the found deal
    mock_mt5.history_deals_get.return_value = [
        MockDeal(ticket=deal_ticket, comment=client_order_id, price=deal_price)
    ]

    retrieved_price = get_deal_price(mock_mt5, ticket, symbol)
    assert retrieved_price == deal_price

    logger.info(
        f"✅ Integration test passed: found deal #{ticket} @ ${retrieved_price}"
    )


if __name__ == "__main__":
    # Run specific tests for manual verification
    test_wait_for_fill_success_second_poll()
    test_integration_reconciler_flow()
    print("✅ All manual tests passed!")
