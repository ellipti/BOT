"""
MetaTrader 5 Broker Adapter - Implementation of BrokerGateway protocol
Adapts MT5 platform to the broker-agnostic interface.
"""

import logging
from typing import TYPE_CHECKING

from core.broker import BrokerGateway, OrderRequest, OrderResult, Position, Side

# Lazy import MT5 to avoid import-time dependency
if TYPE_CHECKING:
    import MetaTrader5 as mt5

logger = logging.getLogger(__name__)


class MT5Broker(BrokerGateway):
    """
    MetaTrader 5 implementation of BrokerGateway protocol.

    Provides adapter layer between broker-agnostic trading interface
    and MT5-specific implementation. Uses existing MT5Client for
    connection management and delegates to MT5 platform for execution.
    """

    def __init__(self, settings):
        """
        Initialize MT5 broker adapter with configuration.

        Args:
            settings: Application settings containing MT5 configuration
        """
        self.settings = settings
        self._mt5_client = None
        self._connected = False

        # Lazy import to avoid MT5 dependency at import time
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

    def _get_mt5_client(self):
        """Get or create MT5Client instance"""
        if self._mt5_client is None:
            # Import here to avoid circular dependency
            from core.mt5_client import MT5Client

            self._mt5_client = MT5Client()
        return self._mt5_client

    def connect(self) -> None:
        """
        Establish connection to MetaTrader 5 platform.

        Uses existing MT5Client with settings from configuration.
        Supports both attach mode (connect to running terminal)
        and headless login mode.

        Raises:
            ConnectionError: If MT5 connection cannot be established
        """
        self._ensure_mt5_imported()

        try:
            client = self._get_mt5_client()

            # Use settings to determine connection method
            mt5_settings = self.settings.mt5

            if mt5_settings.attach_mode:
                # Attach to running MT5 terminal
                success = client.connect(
                    attach_mode=True, path=mt5_settings.terminal_path
                )
            else:
                # Headless login with credentials
                success = client.connect(
                    login=mt5_settings.login,
                    password=mt5_settings.password,
                    server=mt5_settings.server,
                    path=mt5_settings.terminal_path,
                    attach_mode=False,
                )

            if not success:
                raise ConnectionError("Failed to connect to MT5 platform")

            self._connected = True
            logger.info("Successfully connected to MT5 broker")

        except Exception as e:
            logger.error(f"MT5 connection failed: {e}")
            raise ConnectionError(f"MT5 connection failed: {e}") from e

    def is_connected(self) -> bool:
        """
        Check if connected to MT5 platform.

        Returns:
            bool: True if connected and MT5 is initialized
        """
        self._ensure_mt5_imported()

        # Check both our state and MT5 terminal state
        return self._connected and self._mt5.terminal_info() is not None

    def place_order(self, request: OrderRequest) -> OrderResult:
        """
        Execute trading order through MetaTrader 5.

        Currently supports MARKET orders only. Maps broker-agnostic
        OrderRequest to MT5-specific order structure and executes
        through MT5 platform.

        Args:
            request: Standardized order request

        Returns:
            OrderResult: Execution result with MT5 order details
        """
        self._ensure_mt5_imported()

        if not self.is_connected():
            return OrderResult(accepted=False, reason="Not connected to MT5 platform")

        # Currently only support MARKET orders
        if request.order_type.value != "MARKET":
            return OrderResult(
                accepted=False,
                reason=f"Order type {request.order_type} not yet supported",
            )

        try:
            # Map to MT5 order structure
            mt5_request = self._map_to_mt5_order(request)

            # Execute order through MT5
            result = self._mt5.order_send(mt5_request)

            if result is None:
                return OrderResult(
                    accepted=False,
                    reason=f"MT5 order_send failed: {self._mt5.last_error()}",
                )

            # Check if order was accepted
            if result.retcode != self._mt5.TRADE_RETCODE_DONE:
                return OrderResult(
                    accepted=False,
                    broker_order_id=str(result.order) if result.order else None,
                    reason=f"MT5 rejected order: retcode={result.retcode}, comment={result.comment}",
                )

            logger.info(f"MT5 order executed: {result.order}, volume={result.volume}")

            return OrderResult(
                accepted=True,
                broker_order_id=str(result.order),
                reason=f"Executed: volume={result.volume}, price={result.price}",
            )

        except Exception as e:
            logger.error(f"MT5 order execution error: {e}")
            return OrderResult(accepted=False, reason=f"Execution error: {str(e)}")

    def _map_to_mt5_order(self, request: OrderRequest) -> dict:
        """
        Map broker-agnostic OrderRequest to MT5 order structure.

        Args:
            request: Standardized order request

        Returns:
            dict: MT5-compatible order request structure
        """
        self._ensure_mt5_imported()

        # Map side to MT5 action
        action = self._mt5.TRADE_ACTION_DEAL
        order_type = (
            self._mt5.ORDER_TYPE_BUY
            if request.side == Side.BUY
            else self._mt5.ORDER_TYPE_SELL
        )

        # Build MT5 order request
        mt5_request = {
            "action": action,
            "symbol": request.symbol,
            "volume": request.qty,
            "type": order_type,
            "comment": f"ClientID:{request.client_order_id}",
            "type_filling": self._mt5.ORDER_FILLING_IOC,  # Immediate or Cancel
        }

        # Add stop loss if specified
        if request.sl is not None:
            mt5_request["sl"] = request.sl

        # Add take profit if specified
        if request.tp is not None:
            mt5_request["tp"] = request.tp

        return mt5_request

    def cancel(self, broker_order_id: str) -> bool:
        """
        Cancel pending MT5 order.

        Args:
            broker_order_id: MT5 order ticket number

        Returns:
            bool: False (MT5 market orders cannot be cancelled after execution)
        """
        # MT5 market orders are immediately executed and cannot be cancelled
        # This would need to be implemented for pending orders (LIMIT/STOP)
        logger.warning(
            f"MT5 order cancellation not implemented for order {broker_order_id}"
        )
        return False

    def positions(self) -> list[Position]:
        """
        Retrieve open positions from MT5 platform.

        Returns:
            list[Position]: List of open positions converted to standardized format
        """
        self._ensure_mt5_imported()

        if not self.is_connected():
            logger.warning("Cannot fetch positions: not connected to MT5")
            return []

        try:
            # Get positions from MT5Client (reuse existing logic)
            client = self._get_mt5_client()
            mt5_positions = client.get_positions()

            if not mt5_positions:
                return []

            # Convert MT5 positions to standardized Position objects
            positions = []
            for mt5_pos in mt5_positions:
                # MT5 position type: 0=BUY, 1=SELL
                qty = mt5_pos.volume if mt5_pos.type == 0 else -mt5_pos.volume

                position = Position(
                    symbol=mt5_pos.symbol, qty=qty, avg_price=mt5_pos.price_open
                )
                positions.append(position)

            logger.debug(f"Retrieved {len(positions)} positions from MT5")
            return positions

        except Exception as e:
            logger.error(f"Error fetching MT5 positions: {e}")
            return []
