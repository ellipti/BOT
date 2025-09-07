"""
Pytest configuration and fixtures for MT5-less testing strategy.

This module provides:
1. MT5 availability detection
2. Conditional test skipping
3. Mock fixtures for unit testing without MT5
4. Integration test markers
"""

import importlib
import sys
from typing import Any, Optional
from unittest.mock import MagicMock, Mock

import pytest


def mt5_available() -> bool:
    """
    Check if MetaTrader5 module is available and functional.

    Returns:
        bool: True if MT5 is available and can be imported, False otherwise
    """
    try:
        mt5_module = importlib.import_module("MetaTrader5")
        return mt5_module is not None
    except ImportError:
        return False
    except Exception:
        # Any other error (e.g., DLL issues on Windows)
        return False


# For true integration modules that require MT5
# This will skip the entire module if MT5 is not available
mt5 = pytest.importorskip("MetaTrader5", reason="MT5 not available in CI")


# Test markers for different categories
def pytest_configure(config):
    """Configure custom pytest markers"""
    config.addinivalue_line(
        "markers", "mt5_integration: marks tests as requiring actual MT5 connection"
    )
    config.addinivalue_line(
        "markers",
        "mt5_unit: marks tests as MT5-related but using mocks (can run without MT5)",
    )
    config.addinivalue_line(
        "markers", "broker_integration: marks tests as requiring broker connectivity"
    )


class MockMT5:
    """
    Comprehensive MT5 mock for unit testing without actual MT5 dependency.

    Provides all necessary constants and methods to test MT5-related code
    without requiring the actual MetaTrader5 package.
    """

    # Trading constants
    TRADE_ACTION_DEAL = 1
    TRADE_ACTION_PENDING = 5

    # Order types
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    ORDER_TYPE_BUY_LIMIT = 2
    ORDER_TYPE_SELL_LIMIT = 3
    ORDER_TYPE_BUY_STOP = 4
    ORDER_TYPE_SELL_STOP = 5
    ORDER_TYPE_BUY_STOP_LIMIT = 6
    ORDER_TYPE_SELL_STOP_LIMIT = 7

    # Order time types
    ORDER_TIME_GTC = 0
    ORDER_TIME_DAY = 1
    ORDER_TIME_SPECIFIED = 2
    ORDER_TIME_SPECIFIED_DAY = 3

    # Order filling modes
    ORDER_FILLING_FOK = 0
    ORDER_FILLING_IOC = 1
    ORDER_FILLING_RETURN = 2

    # Position types
    POSITION_TYPE_BUY = 0
    POSITION_TYPE_SELL = 1

    # Trade return codes
    TRADE_RETCODE_REQUOTE = 10004
    TRADE_RETCODE_REJECT = 10006
    TRADE_RETCODE_CANCEL = 10007
    TRADE_RETCODE_PLACED = 10008
    TRADE_RETCODE_DONE = 10009
    TRADE_RETCODE_TIMEOUT = 10012
    TRADE_RETCODE_INVALID = 10013
    TRADE_RETCODE_INVALID_VOLUME = 10014
    TRADE_RETCODE_INVALID_PRICE = 10015
    TRADE_RETCODE_INVALID_STOPS = 10016
    TRADE_RETCODE_TRADE_DISABLED = 10017
    TRADE_RETCODE_MARKET_CLOSED = 10018
    TRADE_RETCODE_NO_MONEY = 10019
    TRADE_RETCODE_PRICE_CHANGED = 10020
    TRADE_RETCODE_PRICE_OFF = 10021
    TRADE_RETCODE_INVALID_EXPIRATION = 10022
    TRADE_RETCODE_ORDER_CHANGED = 10023
    TRADE_RETCODE_TOO_MANY_REQUESTS = 10024
    TRADE_RETCODE_NO_CHANGES = 10025
    TRADE_RETCODE_SERVER_DISABLES_AT = 10026
    TRADE_RETCODE_CLIENT_DISABLES_AT = 10027
    TRADE_RETCODE_LOCKED = 10028
    TRADE_RETCODE_FROZEN = 10029
    TRADE_RETCODE_INVALID_FILL = 10030
    TRADE_RETCODE_CONNECTION = 10031
    TRADE_RETCODE_ONLY_REAL = 10032
    TRADE_RETCODE_LIMIT_ORDERS = 10033
    TRADE_RETCODE_LIMIT_VOLUME = 10034
    TRADE_RETCODE_INVALID_ORDER = 10035
    TRADE_RETCODE_POSITION_CLOSED = 10036

    # Symbol trade modes
    SYMBOL_TRADE_MODE_DISABLED = 0
    SYMBOL_TRADE_MODE_LONGONLY = 1
    SYMBOL_TRADE_MODE_SHORTONLY = 2
    SYMBOL_TRADE_MODE_CLOSEONLY = 3
    SYMBOL_TRADE_MODE_FULL = 4

    def __init__(self):
        self.initialized = False
        self.connected = False

    def initialize(
        self,
        login: int | None = None,
        password: str | None = None,
        server: str | None = None,
        timeout: int = 60000,
        portable: bool = False,
        path: str | None = None,
    ) -> bool:
        """Mock MT5 initialization"""
        self.initialized = True
        self.connected = True
        return True

    def shutdown(self) -> None:
        """Mock MT5 shutdown"""
        self.initialized = False
        self.connected = False

    def terminal_info(self) -> dict | None:
        """Mock terminal info"""
        if not self.connected:
            return None
        return {
            "community_account": False,
            "community_connection": False,
            "connected": True,
            "dlls_allowed": True,
            "trade_allowed": True,
            "tradeapi_disabled": False,
            "trade_expert": True,
            "email_enabled": False,
            "ftp_enabled": False,
            "notifications_enabled": False,
            "mqid": False,
            "build": 3000,
            "maxbars": 65000,
            "codepage": 1251,
            "cpu_cores": 8,
            "disk_space": 10000000,
            "physical_memory": 16000000,
            "screen_dpi": 96,
            "ping_last": 45,
            "community_balance": 0.0,
            "retransmission": 0.01,
            "company": "Mock Broker LLC",
            "name": "MockTrader 5",
            "language": 1033,
            "path": "C:\\Program Files\\MockTrader 5",
        }

    def account_info(self) -> dict | None:
        """Mock account info"""
        if not self.connected:
            return None
        return {
            "login": 12345678,
            "trade_mode": 0,  # Demo account
            "leverage": 100,
            "limit_orders": 100,
            "margin_so_mode": 0,
            "trade_allowed": True,
            "trade_expert": True,
            "margin_mode": 0,
            "currency_digits": 2,
            "fifo_close": False,
            "balance": 10000.0,
            "credit": 0.0,
            "profit": 0.0,
            "equity": 10000.0,
            "margin": 0.0,
            "margin_free": 10000.0,
            "margin_level": 0.0,
            "margin_so_call": 50.0,
            "margin_so_so": 30.0,
            "margin_initial": 0.0,
            "margin_maintenance": 0.0,
            "assets": 0.0,
            "liabilities": 0.0,
            "commission_blocked": 0.0,
            "name": "Mock Trader",
            "server": "MockServer-Demo",
            "currency": "USD",
            "company": "Mock Broker LLC",
        }

    def symbol_info(self, symbol: str) -> Mock | None:
        """Mock symbol info"""
        if not self.connected:
            return None

        # Return different mock data based on symbol
        base_info = {
            "custom": False,
            "chart_mode": 0,
            "select": True,
            "visible": True,
            "session_deals": 0,
            "session_buy_orders": 0,
            "session_sell_orders": 0,
            "volume": 0,
            "volumehigh": 0,
            "volumelow": 0,
            "time": 1694188800,
            "digits": 5 if "JPY" not in symbol else 3,
            "spread": 2,
            "spread_float": True,
            "trade_calc_mode": 0,
            "trade_mode": self.SYMBOL_TRADE_MODE_FULL,
            "start_time": 0,
            "expiration_time": 0,
            "trade_stops_level": 10,
            "trade_freeze_level": 0,
            "trade_exemode": 0,
            "swap_mode": 0,
            "swap_rollover3days": 3,
            "margin_hedged_use_leg": False,
            "expiration_mode": 15,
            "filling_mode": 7,  # FOK | IOC | Return
            "order_mode": 127,
            "order_gtc_mode": 0,
            "option_mode": 0,
            "option_right": 0,
            "bid": 1.0950,
            "bidhigh": 1.0980,
            "bidlow": 1.0920,
            "ask": 1.0952,
            "askhigh": 1.0982,
            "asklow": 1.0922,
            "last": 1.0951,
            "lasthigh": 1.0981,
            "lastlow": 1.0921,
            "volume_real": 0.0,
            "volumehigh_real": 0.0,
            "volumelow_real": 0.0,
            "option_strike": 0.0,
            "point": 0.00001 if "JPY" not in symbol else 0.001,
            "trade_tick_value": 1.0,
            "trade_tick_value_profit": 1.0,
            "trade_tick_value_loss": 1.0,
            "trade_tick_size": 0.00001 if "JPY" not in symbol else 0.001,
            "trade_contract_size": 100000,
            "trade_accrued_interest": 0.0,
            "trade_face_value": 0.0,
            "trade_liquidity_rate": 0.0,
            "volume_min": 0.01,
            "volume_max": 500.0,
            "volume_step": 0.01,
            "volume_limit": 0.0,
            "swap_long": -0.5,
            "swap_short": 0.2,
            "margin_initial": 0.0,
            "margin_maintenance": 0.0,
            "session_volume": 0,
            "session_turnover": 0.0,
            "session_interest": 0.0,
            "session_buy_orders_volume": 0.0,
            "session_sell_orders_volume": 0.0,
            "session_open": 1.0940,
            "session_close": 1.0951,
            "session_aw": 0.0,
            "session_price_settlement": 0.0,
            "session_price_limit_min": 0.0,
            "session_price_limit_max": 0.0,
            "margin_hedged": 50000.0,
            "price_change": 0.0011,
            "price_volatility": 0.0,
            "price_theoretical": 0.0,
            "price_greeks_delta": 0.0,
            "price_greeks_theta": 0.0,
            "price_greeks_gamma": 0.0,
            "price_greeks_vega": 0.0,
            "price_greeks_rho": 0.0,
            "price_greeks_omega": 0.0,
            "price_sensitivity": 0.0,
            "basis": "",
            "category": "",
            "currency_base": symbol[:3] if len(symbol) >= 6 else "EUR",
            "currency_profit": symbol[3:6] if len(symbol) >= 6 else "USD",
            "currency_margin": symbol[3:6] if len(symbol) >= 6 else "USD",
            "bank": "",
            "description": f"Mock {symbol}",
            "exchange": "",
            "formula": "",
            "isin": "",
            "name": symbol,
            "page": "",
            "path": f"Forex\\Mock\\{symbol}",
        }

        # Create a Mock object with all the attributes
        mock_symbol = Mock()
        for key, value in base_info.items():
            setattr(mock_symbol, key, value)

        return mock_symbol

    def symbol_select(self, symbol: str, enable: bool = True) -> bool:
        """Mock symbol selection"""
        return bool(self.connected)

    def symbols_get(self, group: str = "*") -> tuple | None:
        """Mock symbols list"""
        if not self.connected:
            return None
        return (
            self.symbol_info("EURUSD"),
            self.symbol_info("GBPUSD"),
            self.symbol_info("USDJPY"),
            self.symbol_info("USDCHF"),
        )

    def copy_rates_from_pos(
        self, symbol: str, timeframe: int, start_pos: int, count: int
    ) -> tuple | None:
        """Mock historical rates"""
        if not self.connected:
            return None
        # Return mock OHLC data
        import time

        current_time = int(time.time())
        rates = []
        for i in range(count):
            rates.append(
                {
                    "time": current_time - (count - i) * 60,  # 1-minute intervals
                    "open": 1.0950 + (i % 10) * 0.0001,
                    "high": 1.0955 + (i % 10) * 0.0001,
                    "low": 1.0945 + (i % 10) * 0.0001,
                    "close": 1.0952 + (i % 10) * 0.0001,
                    "tick_volume": 100 + i,
                    "spread": 2,
                    "real_volume": 0,
                }
            )
        return tuple(rates)

    def positions_get(
        self, symbol: str | None = None, ticket: int | None = None
    ) -> tuple | None:
        """Mock positions"""
        if not self.connected:
            return None
        return ()  # No open positions by default

    def orders_get(
        self, symbol: str | None = None, ticket: int | None = None
    ) -> tuple | None:
        """Mock pending orders"""
        if not self.connected:
            return None
        return ()  # No pending orders by default

    def order_send(self, request: dict) -> dict:
        """Mock order sending"""
        if not self.connected:
            return {
                "retcode": self.TRADE_RETCODE_CONNECTION,
                "deal": 0,
                "order": 0,
                "volume": 0.0,
                "price": 0.0,
                "bid": 0.0,
                "ask": 0.0,
                "comment": "Connection error",
                "request_id": request.get("magic", 0),
                "retcode_external": 0,
            }

        return {
            "retcode": self.TRADE_RETCODE_DONE,
            "deal": 123456789,
            "order": 987654321,
            "volume": request.get("volume", 0.01),
            "price": request.get("price", 1.0951),
            "bid": 1.0950,
            "ask": 1.0952,
            "comment": "Mocked execution",
            "request_id": request.get("magic", 0),
            "retcode_external": 0,
        }

    def last_error(self) -> tuple:
        """Mock last error"""
        return (0, "No error")


@pytest.fixture
def mock_mt5():
    """
    Fixture providing a comprehensive MT5 mock for unit testing.

    Usage:
        def test_my_function(mock_mt5):
            # mock_mt5 is already initialized and connected
            result = my_mt5_function(mock_mt5)
            assert result is not None
    """
    mt5_mock = MockMT5()
    mt5_mock.initialize()
    return mt5_mock


@pytest.fixture
def mock_mt5_disconnected():
    """
    Fixture providing a disconnected MT5 mock for testing error conditions.
    """
    return MockMT5()  # Not initialized/connected


@pytest.fixture(autouse=True)
def setup_mt5_mock_in_sys_modules():
    """
    Automatically inject MT5 mock into sys.modules for all tests.
    This allows imports of MetaTrader5 to work even when the package isn't installed.
    """
    if "MetaTrader5" not in sys.modules and not mt5_available():
        sys.modules["MetaTrader5"] = MockMT5()
    yield
    # Cleanup is optional since we're just mocking


# Skip marker for MT5 integration tests
mt5_integration_skip = pytest.mark.skipif(
    not mt5_available(), reason="MT5 not available in CI environment"
)


# Helper function for conditional MT5 testing
def skip_if_no_mt5(reason: str = "Requires MT5 connection"):
    """
    Decorator to skip tests when MT5 is not available.

    Args:
        reason: Custom reason for skipping

    Usage:
        @skip_if_no_mt5("This test needs real MT5 data")
        def test_live_data():
            pass
    """
    return pytest.mark.skipif(not mt5_available(), reason=reason)
