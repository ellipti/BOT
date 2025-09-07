"""
Simple compatibility test for MT5 broker adapter

Updated to use the MT5-less testing strategy with proper skip/mock handling.
"""

import logging
import sys
from unittest.mock import Mock

import pytest

from tests.conftest import mt5_available, skip_if_no_mt5

# Mark this as a unit test that works with mocks
pytestmark = pytest.mark.mt5_unit


# Mock MT5 module
class MockMT5:
    TRADE_ACTION_DEAL = 1
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    ORDER_TIME_GTC = 0
    ORDER_FILLING_FOK = 0
    ORDER_FILLING_IOC = 1
    ORDER_FILLING_RETURN = 2
    POSITION_TYPE_BUY = 0
    POSITION_TYPE_SELL = 1
    TRADE_RETCODE_DONE = 10009
    SYMBOL_TRADE_MODE_DISABLED = 0

    def terminal_info(self):
        return {"connected": True}

    def symbol_info(self, symbol):
        return Mock(
            visible=True,
            trade_mode=1,
            point=0.01,
            trade_stops_level=10,
            digits=2,
            filling_mode=self.ORDER_FILLING_IOC,
        )

    def symbol_select(self, symbol, enable):
        return True

    def symbol_info_tick(self, symbol):
        return Mock(ask=2500.50, bid=2500.30)

    def order_send(self, request):
        return Mock(
            retcode=self.TRADE_RETCODE_DONE,
            deal=12345,
            order=67890,
            volume=request["volume"],
            price=2500.40,
            comment="Test execution",
        )

    def positions_get(self):
        return []


def test_broker_protocol_compliance():
    """Test that MT5Broker implements BrokerGateway protocol"""
    print("🧪 Testing MT5Broker Protocol Compliance\n")

    # Setup mock
    sys.modules["MetaTrader5"] = MockMT5()

    # Import modules
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "mt5_broker", "adapters/mt5_broker.py"
    )
    mt5_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mt5_module)

    from core.broker import (
        BrokerGateway,
        OrderRequest,
        OrderResult,
        OrderType,
        Position,
        Side,
    )

    MT5Broker = mt5_module.MT5Broker

    # Test protocol compliance
    print("1. Testing protocol compliance...")
    assert issubclass(MT5Broker, BrokerGateway)
    print("✅ MT5Broker implements BrokerGateway protocol")

    # Test required methods exist
    broker = MT5Broker(Mock())
    required_methods = ["connect", "is_connected", "place_order", "cancel", "positions"]

    print("\n2. Testing required methods...")
    for method in required_methods:
        assert hasattr(broker, method), f"Missing method: {method}"
        print(f"✅ Method {method} exists")

    # Test order request/result types
    print("\n3. Testing order flow...")
    broker._connected = True  # Simulate connected state

    request = OrderRequest(
        client_order_id="TEST_PROTOCOL",
        symbol="XAUUSD",
        side=Side.BUY,
        qty=0.1,
        order_type=OrderType.MARKET,
    )

    result = broker.place_order(request)
    assert isinstance(result, OrderResult)
    assert result.accepted is True
    assert result.broker_order_id is not None
    print("✅ Order placement returns proper OrderResult")

    # Test positions
    print("\n4. Testing positions...")
    positions = broker.positions()
    assert isinstance(positions, list)
    print("✅ Positions returns list")

    # Test connection methods
    print("\n5. Testing connection methods...")
    connected = broker.is_connected()
    assert isinstance(connected, bool)
    print("✅ is_connected returns bool")

    # Test cancel method
    print("\n6. Testing cancel method...")
    cancel_result = broker.cancel("12345")
    assert isinstance(cancel_result, bool)
    print("✅ cancel returns bool")

    print("\n🎉 All protocol compliance tests passed!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)  # Reduce noise
    test_broker_protocol_compliance()
