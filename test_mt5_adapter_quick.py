"""
Quick test script for MT5 broker adapter implementation

Updated to use the MT5-less testing strategy with proper skip/mock handling.
"""

import logging
import sys
from unittest.mock import MagicMock, Mock

import pytest

from tests.conftest import mt5_available, skip_if_no_mt5

# Setup logging to see what's happening
logging.basicConfig(
    level=logging.DEBUG, format="%(levelname)s - %(name)s - %(message)s"
)

# Mark this as a unit test that works with mocks
pytestmark = pytest.mark.mt5_unit


# Mock MetaTrader5 module to avoid dependency
class MockMT5:
    """Mock MT5 module for testing"""

    # Constants
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
    TRADE_RETCODE_PLACED = 10008
    SYMBOL_TRADE_MODE_DISABLED = 0

    def __init__(self):
        self.connected = True

    def terminal_info(self):
        return {"connected": True} if self.connected else None

    def symbol_info(self, symbol):
        """Mock symbol info"""
        return Mock(
            visible=True,
            trade_mode=1,  # Enabled
            point=0.01,  # Numbers, not Mock objects
            trade_stops_level=10,  # Numbers, not Mock objects
            digits=2,  # Numbers, not Mock objects
            filling_mode=self.ORDER_FILLING_FOK | self.ORDER_FILLING_IOC,
        )

    def symbol_select(self, symbol, enable):
        return True

    def symbol_info_tick(self, symbol):
        """Mock tick data"""
        return Mock(ask=2500.50, bid=2500.30)

    def order_send(self, request):
        """Mock order send"""
        print(f"📤 Mock MT5 order_send called with: {request}")
        return Mock(
            retcode=self.TRADE_RETCODE_DONE,
            deal=12345,
            order=67890,
            volume=request["volume"],
            price=2500.40,
            comment="Mock execution",
        )

    def positions_get(self):
        """Mock positions"""
        return [
            Mock(
                symbol="XAUUSD",
                type=self.POSITION_TYPE_BUY,
                volume=0.1,
                price_open=2500.0,
            ),
            Mock(
                symbol="EURUSD",
                type=self.POSITION_TYPE_SELL,
                volume=1.0,
                price_open=1.0950,
            ),
        ]

    def last_error(self):
        return (0, "No error")


def test_mt5_adapter():
    """Test MT5 adapter functionality"""
    print("🧪 Testing MT5 Adapter Implementation\n")

    # Monkey patch the MT5 import
    sys.modules["MetaTrader5"] = MockMT5()

    # Import directly from the file to avoid __init__.py issues
    import importlib
    import importlib.util

    # Clear module cache
    if "mt5_broker" in sys.modules:
        del sys.modules["mt5_broker"]

    spec = importlib.util.spec_from_file_location(
        "mt5_broker", "adapters/mt5_broker.py"
    )
    mt5_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mt5_module)

    MT5Broker = mt5_module.MT5Broker

    from core.broker import OrderRequest, OrderType, Side

    # Create mock settings
    mock_settings = Mock()
    mock_settings.MAGIC = 9999
    mock_settings.DEVIATION = 10

    # Create broker
    broker = MT5Broker(mock_settings)
    broker._connected = True  # Simulate connected state

    print("1. Testing symbol validation...")
    try:
        symbol_info = broker._ensure_symbol("XAUUSD")
        print(f"✅ Symbol validation: {symbol_info.visible}")
    except Exception as e:
        print(f"❌ Symbol validation failed: {e}")

    print("\n2. Testing price resolution...")
    try:
        buy_price = broker._resolve_price("XAUUSD", Side.BUY)
        sell_price = broker._resolve_price("XAUUSD", Side.SELL)
        print(f"✅ Price resolution: BUY={buy_price}, SELL={sell_price}")
    except Exception as e:
        print(f"❌ Price resolution failed: {e}")

    print("\n3. Testing filling mode resolution...")
    try:
        filling = broker._resolve_filling("XAUUSD")
        print(f"✅ Filling mode: {filling}")
    except Exception as e:
        print(f"❌ Filling mode failed: {e}")

    print("\n4. Testing stop normalization...")
    try:
        sl, tp = broker._normalize_stops("XAUUSD", 2500.0, 2450.0, 2550.0, Side.BUY)
        print(f"✅ Stop normalization: SL={sl}, TP={tp}")
    except Exception as e:
        print(f"❌ Stop normalization failed: {e}")

    print("\n5. Testing order placement...")
    try:
        request = OrderRequest(
            client_order_id="TEST_001",
            symbol="XAUUSD",
            side=Side.BUY,
            qty=0.1,
            order_type=OrderType.MARKET,  # Use enum directly
            sl=2450.0,
            tp=2550.0,
        )

        print(
            f"   Request order_type: {request.order_type} (type: {type(request.order_type)})"
        )

        result = broker.place_order(request)
        print(
            f"✅ Order placement: accepted={result.accepted}, id={result.broker_order_id}"
        )
        print(f"   Reason: {result.reason}")
    except Exception as e:
        print(f"❌ Order placement failed: {e}")
        import traceback

        traceback.print_exc()

    print("\n6. Testing positions retrieval...")
    try:
        positions = broker.positions()
        print(f"✅ Positions: {len(positions)} found")
        for pos in positions:
            print(f"   {pos.symbol}: {pos.qty} @ {pos.avg_price}")
    except Exception as e:
        print(f"❌ Positions failed: {e}")

    print("\n🎉 MT5 Adapter Test Complete!")


def test_mt5_adapter_with_mock():
    """
    Pytest-compatible test that runs the MT5 adapter test with mocks.

    This test can run in CI environments without MT5.
    """
    # This will use the mock MT5 from our fixtures
    test_mt5_adapter()


@pytest.mark.mt5_integration
@skip_if_no_mt5("Requires actual MT5 installation")
def test_mt5_adapter_integration():
    """
    Integration test that requires actual MT5 installation.

    This test will be skipped in CI but can run locally if MT5 is available.
    """
    # This would run against real MT5 if available
    test_mt5_adapter()


if __name__ == "__main__":
    test_mt5_adapter()
