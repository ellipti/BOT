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

# Default MT5 settings that can be overridden by configuration
DEFAULT_MAGIC = 4242
DEFAULT_DEVIATION = 20


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

    def _ensure_symbol(self, symbol: str):
        """
        Ensure symbol is available and enabled for trading.

        Args:
            symbol: Trading symbol (e.g., XAUUSD)

        Returns:
            mt5.SymbolInfo: Symbol information

        Raises:
            RuntimeError: If symbol cannot be enabled or is not tradable
        """
        self._ensure_mt5_imported()

        if not self.is_connected():
            raise RuntimeError("Not connected to MT5 platform")

        # Get symbol info
        symbol_info = self._mt5.symbol_info(symbol)
        if symbol_info is None:
            # Try to select symbol first
            if not self._mt5.symbol_select(symbol, True):
                raise RuntimeError(f"Symbol {symbol} not available")
            symbol_info = self._mt5.symbol_info(symbol)
            if symbol_info is None:
                raise RuntimeError(f"Cannot retrieve info for symbol {symbol}")

        # Check if symbol is visible (enabled)
        if not symbol_info.visible:
            logger.info(f"Enabling symbol {symbol}")
            if not self._mt5.symbol_select(symbol, True):
                raise RuntimeError(f"Cannot enable symbol {symbol}")

            # Re-fetch info after enabling
            symbol_info = self._mt5.symbol_info(symbol)
            if symbol_info is None or not symbol_info.visible:
                raise RuntimeError(f"Failed to enable symbol {symbol}")

        # Check if symbol is tradable
        if symbol_info.trade_mode == self._mt5.SYMBOL_TRADE_MODE_DISABLED:
            raise RuntimeError(f"Symbol {symbol} is not tradable")

        logger.debug(
            f"Symbol {symbol} ready: visible={symbol_info.visible}, tradable=True"
        )
        return symbol_info

    def _resolve_price(self, symbol: str, side: Side) -> float:
        """
        Resolve current market price for order execution.

        Args:
            symbol: Trading symbol
            side: Order side (BUY/SELL)

        Returns:
            float: Current market price (ask for BUY, bid for SELL)

        Raises:
            RuntimeError: If tick data not available
        """
        self._ensure_mt5_imported()

        # Get current tick
        tick = self._mt5.symbol_info_tick(symbol)
        if tick is None:
            raise RuntimeError(f"Cannot get tick data for {symbol}")

        # BUY at ask price, SELL at bid price
        if side == Side.BUY:
            if tick.ask == 0.0:
                raise RuntimeError(f"Invalid ask price for {symbol}")
            return tick.ask
        else:  # SELL
            if tick.bid == 0.0:
                raise RuntimeError(f"Invalid bid price for {symbol}")
            return tick.bid

    def _resolve_filling(self, symbol: str) -> int:
        """
        Determine best filling mode for symbol with smart fallback.

        Args:
            symbol: Trading symbol

        Returns:
            int: MT5 filling mode constant (FOK -> IOC -> RETURN)
        """
        self._ensure_mt5_imported()

        symbol_info = self._mt5.symbol_info(symbol)
        if symbol_info is None:
            logger.warning(f"Cannot get symbol info for {symbol}, using RETURN filling")
            return self._mt5.ORDER_FILLING_RETURN

        filling_mode = symbol_info.filling_mode

        # Priority: FOK -> IOC -> RETURN
        if filling_mode & self._mt5.ORDER_FILLING_FOK:
            logger.debug(f"Using FOK filling for {symbol}")
            return self._mt5.ORDER_FILLING_FOK
        elif filling_mode & self._mt5.ORDER_FILLING_IOC:
            logger.debug(f"Using IOC filling for {symbol}")
            return self._mt5.ORDER_FILLING_IOC
        else:
            logger.debug(f"Using RETURN filling for {symbol}")
            return self._mt5.ORDER_FILLING_RETURN

    def _normalize_stops(
        self,
        symbol: str,
        entry_price: float,
        sl: float | None,
        tp: float | None,
        side: Side,
    ) -> tuple[float | None, float | None]:
        """
        Normalize stop loss and take profit levels to comply with MT5 restrictions.

        Args:
            symbol: Trading symbol
            entry_price: Order entry price
            sl: Stop loss price (None if not set)
            tp: Take profit price (None if not set)
            side: Order side (BUY/SELL)

        Returns:
            tuple: Normalized (sl, tp) prices, None if not set
        """
        self._ensure_mt5_imported()

        symbol_info = self._mt5.symbol_info(symbol)
        if symbol_info is None:
            logger.warning(
                f"Cannot get symbol info for {symbol}, returning stops as-is"
            )
            return sl, tp

        point = symbol_info.point
        stops_level = symbol_info.trade_stops_level
        digits = symbol_info.digits

        # Minimum distance from entry price
        min_distance = stops_level * point

        normalized_sl = sl
        normalized_tp = tp

        if sl is not None:
            # Round to symbol digits
            normalized_sl = round(sl, digits)

            # Check minimum distance
            if side == Side.BUY:
                # For BUY: SL must be below entry price by at least min_distance
                min_sl = entry_price - min_distance
                if normalized_sl > min_sl:
                    normalized_sl = min_sl
                    logger.warning(
                        f"SL adjusted for {symbol}: {sl} -> {normalized_sl} (min distance)"
                    )
            else:  # SELL
                # For SELL: SL must be above entry price by at least min_distance
                max_sl = entry_price + min_distance
                if normalized_sl < max_sl:
                    normalized_sl = max_sl
                    logger.warning(
                        f"SL adjusted for {symbol}: {sl} -> {normalized_sl} (min distance)"
                    )

        if tp is not None:
            # Round to symbol digits
            normalized_tp = round(tp, digits)

            # Check minimum distance
            if side == Side.BUY:
                # For BUY: TP must be above entry price by at least min_distance
                min_tp = entry_price + min_distance
                if normalized_tp < min_tp:
                    normalized_tp = min_tp
                    logger.warning(
                        f"TP adjusted for {symbol}: {tp} -> {normalized_tp} (min distance)"
                    )
            else:  # SELL
                # For SELL: TP must be below entry price by at least min_distance
                max_tp = entry_price - min_distance
                if normalized_tp > max_tp:
                    normalized_tp = max_tp
                    logger.warning(
                        f"TP adjusted for {symbol}: {tp} -> {normalized_tp} (min distance)"
                    )

        logger.debug(
            f"Stops normalized for {symbol}: SL={normalized_sl}, TP={normalized_tp}"
        )
        return normalized_sl, normalized_tp

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

        Supports MARKET orders with robust price resolution, symbol validation,
        filling mode optimization, and stop level normalization.

        Args:
            request: Standardized order request

        Returns:
            OrderResult: Execution result with MT5 order details
        """
        self._ensure_mt5_imported()

        if not self.is_connected():
            return OrderResult(accepted=False, reason="Not connected to MT5 platform")

        # Currently only support MARKET orders
        if request.order_type != "MARKET":
            return OrderResult(
                accepted=False,
                reason=f"Order type {request.order_type} not yet supported",
            )

        try:
            # Ensure symbol is available and tradable
            symbol_info = self._ensure_symbol(request.symbol)

            # Resolve current market price
            price = self._resolve_price(request.symbol, request.side)

            # Normalize stop loss and take profit levels
            sl, tp = self._normalize_stops(
                symbol=request.symbol,
                entry_price=price,
                sl=request.sl,
                tp=request.tp,
                side=request.side,
            )

            # Resolve optimal filling mode
            filling_mode = self._resolve_filling(request.symbol)

            # Build MT5 order request
            mt5_request = {
                "action": self._mt5.TRADE_ACTION_DEAL,
                "symbol": request.symbol,
                "volume": float(request.qty),  # Ensure float (lots)
                "type": (
                    self._mt5.ORDER_TYPE_BUY
                    if request.side == Side.BUY
                    else self._mt5.ORDER_TYPE_SELL
                ),
                "price": price,
                "sl": sl or 0.0,
                "tp": tp or 0.0,
                "deviation": getattr(self.settings, "DEVIATION", DEFAULT_DEVIATION),
                "magic": getattr(self.settings, "MAGIC", DEFAULT_MAGIC),
                "comment": request.client_order_id,  # Use client order ID as comment
                "type_time": self._mt5.ORDER_TIME_GTC,
                "type_filling": filling_mode,
            }

            logger.info(
                f"Sending MT5 order: {request.symbol} {request.side} {request.qty} @ {price}"
            )
            logger.debug(f"MT5 request: {mt5_request}")

            # Execute order through MT5
            result = self._mt5.order_send(mt5_request)

            if result is None:
                error_info = self._mt5.last_error()
                return OrderResult(
                    accepted=False,
                    reason=f"MT5 order_send failed: {error_info}",
                )

            # Map MT5 result codes to our response
            if result.retcode == self._mt5.TRADE_RETCODE_DONE:
                # Order executed successfully
                broker_order_id = str(result.deal or result.order)
                logger.info(
                    f"MT5 order executed: deal={result.deal}, volume={result.volume}, price={result.price}"
                )

                return OrderResult(
                    accepted=True,
                    broker_order_id=broker_order_id,
                    reason=f"Executed: volume={result.volume}, price={result.price}",
                )
            elif result.retcode == self._mt5.TRADE_RETCODE_PLACED:
                # Order placed as pending (shouldn't happen with MARKET orders)
                broker_order_id = str(result.order)
                logger.info(f"MT5 order placed: order={result.order}")

                return OrderResult(
                    accepted=True,
                    broker_order_id=broker_order_id,
                    reason=f"Placed: order={result.order}",
                )
            else:
                # Order rejected
                logger.warning(
                    f"MT5 order rejected: retcode={result.retcode}, comment={result.comment}"
                )

                return OrderResult(
                    accepted=False,
                    broker_order_id=str(result.order) if result.order else None,
                    reason=f"{result.retcode} {result.comment}",
                )

        except Exception as e:
            logger.error(f"MT5 order execution error: {e}")
            return OrderResult(accepted=False, reason=f"Execution error: {str(e)}")

    def cancel(self, broker_order_id: str) -> bool:
        """
        Cancel pending MT5 order.

        Args:
            broker_order_id: MT5 order ticket number

        Returns:
            bool: False (placeholder - will implement TRADE_ACTION_REMOVE for pending orders)
        """
        # TODO: Implement order cancellation for pending orders using TRADE_ACTION_REMOVE
        # For now, return False as market orders are immediately executed and cannot be cancelled
        logger.warning(
            f"MT5 order cancellation not implemented for order {broker_order_id}"
        )
        return False

    def positions(self) -> list[Position]:
        """
        Retrieve open positions from MT5 platform.

        Maps MT5 position data to standardized Position objects with
        proper volume sign handling (positive=long, negative=short).

        Returns:
            list[Position]: List of open positions converted to standardized format
        """
        self._ensure_mt5_imported()

        if not self.is_connected():
            logger.warning("Cannot fetch positions: not connected to MT5")
            return []

        try:
            # Get positions directly from MT5
            mt5_positions = self._mt5.positions_get()

            if not mt5_positions:
                return []

            # Convert MT5 positions to standardized Position objects
            positions = []
            for mt5_pos in mt5_positions:
                # MT5 position type: 0=BUY (long), 1=SELL (short)
                # Map to signed volume: positive=long, negative=short
                if mt5_pos.type == self._mt5.POSITION_TYPE_BUY:
                    qty = mt5_pos.volume  # Positive for long
                else:  # POSITION_TYPE_SELL
                    qty = -mt5_pos.volume  # Negative for short

                position = Position(
                    symbol=mt5_pos.symbol, qty=qty, avg_price=mt5_pos.price_open
                )
                positions.append(position)

            logger.debug(f"Retrieved {len(positions)} positions from MT5")
            return positions

        except Exception as e:
            logger.error(f"Error fetching MT5 positions: {e}")
            return []
