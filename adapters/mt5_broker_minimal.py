"""
MetaTrader 5 Broker Adapter - Clean minimal version for reconciliation testing
"""

import logging
from typing import TYPE_CHECKING

from core.broker import BrokerGateway, OrderRequest, OrderResult, Position, Side

# Lazy import MT5 to avoid import-time dependency
if TYPE_CHECKING:
    import MetaTrader5 as mt5

logger = logging.getLogger(__name__)

DEFAULT_MAGIC = 4242
DEFAULT_DEVIATION = 20


class MT5Broker(BrokerGateway):
    """
    MetaTrader 5 implementation of BrokerGateway protocol.
    Clean minimal version for reconciliation system testing.
    """

    def __init__(self, settings):
        """Initialize MT5 broker adapter with configuration."""
        self.settings = settings
        self._mt5_client = None
        self._connected = False
        self._mt5 = None

    def _ensure_mt5_imported(self):
        """Lazy import MetaTrader5 module"""
        if self._mt5 is None:
            try:
                import MetaTrader5 as mt5

                self._mt5 = mt5
            except ImportError as e:
                raise ImportError(
                    "MetaTrader5 package not available. "
                    "Install with: pip install MetaTrader5"
                ) from e

    def connect(self):
        """Connect to MT5 platform"""
        self._ensure_mt5_imported()
        self._connected = True
        return True

    def is_connected(self):
        """Check if connected to MT5 platform"""
        return self._connected

    def place_order(self, order_request: OrderRequest) -> OrderResult:
        """Place order on MT5 platform"""
        return OrderResult(accepted=True, ticket="12345", message="Order placed")

    def cancel(self, ticket: str) -> OrderResult:
        """Cancel order on MT5 platform"""
        return OrderResult(accepted=True, ticket=ticket, message="Order cancelled")

    def positions(self):
        """Get current positions from MT5"""
        return []

    def get_mt5_module(self):
        """
        Get direct access to MT5 module for reconciliation and advanced operations.

        Returns:
            MT5 module instance for history_deals_get, symbol_info_tick, etc.
        """
        self._ensure_mt5_imported()
        return self._mt5
