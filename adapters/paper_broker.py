"""
Paper Broker - Simulation implementation of BrokerGateway protocol
Provides realistic order simulation using price feeds for testing and development.
"""

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from core.broker import BrokerGateway, OrderRequest, OrderResult, Position, Side

logger = logging.getLogger(__name__)


class PaperBroker(BrokerGateway):
    """
    Paper trading implementation of BrokerGateway protocol.

    Simulates order execution using price feeds without real money.
    Maintains internal state for fills, positions, and account balance.
    """

    def __init__(self, settings, price_feed=None):
        """
        Initialize paper broker with configuration.

        Args:
            settings: Application settings containing simulation parameters
            price_feed: Price feed source (optional - uses fake data if None)
        """
        self.settings = settings
        self.price_feed = price_feed
        self._connected = False

        # Internal simulation state
        self._orders: dict[str, dict] = {}  # client_order_id -> order data
        self._positions: dict[str, Position] = {}  # symbol -> position
        self._balance = getattr(settings, "INITIAL_BALANCE", 10000.0)
        self._equity = self._balance
        self._commission_per_lot = getattr(settings, "COMMISSION_PER_LOT", 5.0)
        self._slippage_pips = getattr(settings, "SLIPPAGE_PIPS", 0.2)

        # Market simulation data (fallback if no price feed)
        self._market_data = {
            "XAUUSD": {"bid": 2025.50, "ask": 2025.80, "point": 0.01, "pip_value": 1.0},
            "EURUSD": {
                "bid": 1.0950,
                "ask": 1.0952,
                "point": 0.00001,
                "pip_value": 10.0,
            },
            "GBPUSD": {
                "bid": 1.2650,
                "ask": 1.2653,
                "point": 0.00001,
                "pip_value": 10.0,
            },
            "USDJPY": {"bid": 149.50, "ask": 149.53, "point": 0.01, "pip_value": 0.67},
        }

        logger.info(f"PaperBroker initialized with balance=${self._balance}")

    def _get_current_price(self, symbol: str, side: Side) -> float:
        """
        Get current market price for symbol from price feed or simulation.

        Args:
            symbol: Trading symbol
            side: Order side (BUY uses ask, SELL uses bid)

        Returns:
            float: Current market price with optional slippage
        """
        if self.price_feed:
            try:
                # Try to get real price from feed
                tick = self.price_feed.get_tick(symbol)
                if tick:
                    price = tick.ask if side == Side.BUY else tick.bid
                    # Apply simulated slippage
                    point = self._market_data.get(symbol, {}).get("point", 0.00001)
                    slippage = (
                        self._slippage_pips * point * 10
                    )  # Convert pips to points
                    if side == Side.BUY:
                        price += slippage  # Worse price for buy
                    else:
                        price -= slippage  # Worse price for sell
                    return price
            except Exception as e:
                logger.warning(f"Price feed error for {symbol}: {e}, using simulation")

        # Fallback to simulated market data
        market = self._market_data.get(symbol)
        if not market:
            # Create default market for unknown symbol
            base_price = 1.0000 if "USD" in symbol else 100.0
            market = {
                "bid": base_price - 0.0002,
                "ask": base_price + 0.0002,
                "point": 0.00001,
                "pip_value": 10.0,
            }
            self._market_data[symbol] = market
            logger.info(f"Created simulated market data for {symbol}")

        price = market["ask"] if side == Side.BUY else market["bid"]

        # Apply slippage simulation
        point = market["point"]
        slippage = self._slippage_pips * point * 10
        if side == Side.BUY:
            price += slippage
        else:
            price -= slippage

        return price

    def _update_position(self, symbol: str, qty_change: float, avg_price: float):
        """
        Update position for symbol with new quantity and average price.

        Args:
            symbol: Trading symbol
            qty_change: Quantity change (positive=buy, negative=sell)
            avg_price: Execution price
        """
        current_pos = self._positions.get(symbol)

        if current_pos is None:
            # New position
            if qty_change != 0:
                self._positions[symbol] = Position(
                    symbol=symbol, qty=qty_change, avg_price=avg_price
                )
                logger.debug(f"New position: {symbol} qty={qty_change} @ {avg_price}")
        else:
            # Update existing position
            new_qty = current_pos.qty + qty_change

            if (
                abs(new_qty) < 0.001
            ):  # Position closed (considering floating point precision)
                del self._positions[symbol]
                logger.debug(f"Position closed: {symbol}")
            else:
                # Update average price using weighted average
                if (current_pos.qty > 0 and qty_change > 0) or (
                    current_pos.qty < 0 and qty_change < 0
                ):
                    # Adding to position in same direction
                    total_cost = (current_pos.qty * current_pos.avg_price) + (
                        qty_change * avg_price
                    )
                    new_avg_price = total_cost / new_qty
                else:
                    # Reducing position or reversing
                    new_avg_price = (
                        avg_price
                        if abs(qty_change) > abs(current_pos.qty)
                        else current_pos.avg_price
                    )

                self._positions[symbol] = Position(
                    symbol=symbol, qty=new_qty, avg_price=new_avg_price
                )
                logger.debug(
                    f"Updated position: {symbol} qty={new_qty} @ {new_avg_price}"
                )

    def _calculate_commission(self, symbol: str, qty: float) -> float:
        """
        Calculate commission for trade.

        Args:
            symbol: Trading symbol
            qty: Quantity in lots

        Returns:
            float: Commission amount in account currency
        """
        return abs(qty) * self._commission_per_lot

    def connect(self) -> None:
        """
        Establish connection to paper trading system.

        Raises:
            ConnectionError: Never - paper broker always connects successfully
        """
        self._connected = True
        logger.info("Connected to PaperBroker simulation")

    def is_connected(self) -> bool:
        """
        Check if connected to paper trading system.

        Returns:
            bool: Always True for paper broker
        """
        return self._connected

    def place_order(self, request: OrderRequest) -> OrderResult:
        """
        Simulate order execution through paper trading system.

        Immediately fills market orders at simulated prices with slippage.
        Updates internal positions and balance tracking.

        Args:
            request: Standardized order request

        Returns:
            OrderResult: Execution result with simulated fill details
        """
        if not self.is_connected():
            return OrderResult(accepted=False, reason="Paper broker not connected")

        # Currently only support MARKET orders for simulation
        if request.order_type != "MARKET":
            return OrderResult(
                accepted=False,
                reason=f"Paper broker only supports MARKET orders, got {request.order_type}",
            )

        try:
            # Check for duplicate client order ID (idempotency)
            if request.client_order_id in self._orders:
                existing_order = self._orders[request.client_order_id]
                logger.info(
                    f"Duplicate order ID {request.client_order_id}, returning existing result"
                )
                return OrderResult(
                    accepted=True,
                    broker_order_id=existing_order["broker_order_id"],
                    reason="Duplicate order - returned existing result",
                )

            # Generate unique broker order ID
            broker_order_id = str(uuid.uuid4())[:8]

            # Get current market price with slippage
            fill_price = self._get_current_price(request.symbol, request.side)

            # Convert side to quantity (positive=buy, negative=sell)
            qty_change = request.qty if request.side == Side.BUY else -request.qty

            # Calculate commission
            commission = self._calculate_commission(request.symbol, request.qty)

            # Update position
            self._update_position(request.symbol, qty_change, fill_price)

            # Update account balance (deduct commission)
            self._balance -= commission
            self._equity = self._balance  # Simplified P&L calculation

            # Store order record
            order_record = {
                "client_order_id": request.client_order_id,
                "broker_order_id": broker_order_id,
                "symbol": request.symbol,
                "side": request.side,
                "qty": request.qty,
                "fill_price": fill_price,
                "commission": commission,
                "timestamp": time.time(),
                "sl": request.sl,
                "tp": request.tp,
            }
            self._orders[request.client_order_id] = order_record

            logger.info(
                f"Paper order FILLED: {request.symbol} {request.side} {request.qty} @ {fill_price} "
                f"(commission=${commission:.2f}, balance=${self._balance:.2f})"
            )

            return OrderResult(
                accepted=True,
                broker_order_id=broker_order_id,
                reason=f"FILLED: {request.qty} @ {fill_price} (commission=${commission:.2f})",
            )

        except Exception as e:
            logger.error(f"Paper broker order execution error: {e}")
            return OrderResult(accepted=False, reason=f"Simulation error: {str(e)}")

    def cancel(self, broker_order_id: str) -> bool:
        """
        Cancel order in paper trading system.

        Args:
            broker_order_id: Broker-assigned order ID

        Returns:
            bool: False - market orders are immediately filled and cannot be cancelled
        """
        logger.warning(
            f"Paper broker order cancellation requested for {broker_order_id} (not supported)"
        )
        return False

    def positions(self) -> list[Position]:
        """
        Retrieve current positions from paper trading system.

        Returns:
            list[Position]: List of current simulated positions
        """
        if not self.is_connected():
            logger.warning("Cannot fetch positions: paper broker not connected")
            return []

        positions = list(self._positions.values())
        logger.debug(f"Paper broker positions: {len(positions)} open")
        return positions

    def get_account_info(self) -> dict:
        """
        Get paper trading account information.

        Returns:
            dict: Simulated account details with balance, equity, positions
        """
        return {
            "login": 99999999,  # Fake account number
            "balance": self._balance,
            "equity": self._equity,
            "margin": 0.0,  # Simplified - no margin calculation
            "margin_free": self._equity,
            "margin_level": 0.0,
            "leverage": 100,
            "currency": "USD",
            "trade_allowed": True,
            "server": "PaperBroker-Simulation",
            "company": "Paper Trading Inc.",
            "positions_count": len(self._positions),
            "orders_count": len(self._orders),
        }

    def get_order_history(self) -> list[dict]:
        """
        Get order execution history.

        Returns:
            list: List of executed orders with details
        """
        return list(self._orders.values())

    def reset_simulation(self):
        """
        Reset paper broker to initial state (for testing).
        """
        self._orders.clear()
        self._positions.clear()
        self._balance = getattr(self.settings, "INITIAL_BALANCE", 10000.0)
        self._equity = self._balance
        logger.info("Paper broker simulation reset")
