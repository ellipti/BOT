"""
Order Reconciliation System V2
Enhanced reconciler with OrderBook integration, background polling, and lifecycle events.
Tracks order execution using MT5 history_deals_get for reliable fill detection.
"""

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import List, Optional, Set

from core.events.types import (
    Cancelled,
    CancelRequested,
    Filled,
    PartiallyFilled,
    PendingActivated,
    StopUpdated,
    StopUpdateRequested,
)
from core.executor.order_book import OrderBook, OrderStatus

logger = logging.getLogger(__name__)


class ReconciledFill:
    """Reconciled fill information"""

    def __init__(self, deal_ticket: str, qty: float, price: float, timestamp: float):
        self.deal_ticket = deal_ticket
        self.qty = qty
        self.price = price
        self.timestamp = timestamp


class ReconciliationEngine:
    """
    Enhanced reconciliation engine with OrderBook and background polling.

    Features:
    - Background thread for continuous MT5 polling
    - OrderBook integration for state management
    - Event emission for lifecycle changes
    - Partial fill detection and aggregation
    - Cancel/replace request handling
    """

    def __init__(
        self, mt5, event_bus, order_book: OrderBook, poll_interval: float = 2.0
    ):
        """
        Initialize reconciliation engine

        Args:
            mt5: MetaTrader5 module instance
            event_bus: Event bus for emitting lifecycle events
            order_book: OrderBook instance for state management
            poll_interval: Background polling interval in seconds
        """
        self.mt5 = mt5
        self.event_bus = event_bus
        self.order_book = order_book
        self.poll_interval = poll_interval

        # Background thread management
        self._thread = None
        self._stop_event = threading.Event()
        self._running = False

        # Track processed deals to avoid duplicates
        self._processed_deals: set[str] = set()
        self._deal_history_lock = threading.RLock()

        logger.info(f"ReconciliationEngine initialized (poll={poll_interval}s)")

    def start(self) -> None:
        """Start background reconciliation thread"""
        if self._running:
            logger.warning("Reconciliation already running")
            return

        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._reconcile_loop, daemon=True)
        self._thread.start()

        logger.info("Reconciliation engine started")

    def stop(self) -> None:
        """Stop background reconciliation thread"""
        if not self._running:
            return

        self._running = False
        self._stop_event.set()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
            if self._thread.is_alive():
                logger.warning("Reconciliation thread did not stop cleanly")

        logger.info("Reconciliation engine stopped")

    def _reconcile_loop(self) -> None:
        """Background reconciliation loop"""
        logger.info("Starting reconciliation background loop")

        while not self._stop_event.wait(self.poll_interval):
            try:
                self._reconcile_active_orders()
                self._process_pending_activations()
                self._process_cancel_requests()
                self._process_stop_updates()

            except Exception as e:
                logger.error(f"Error in reconciliation loop: {e}")

        logger.info("Reconciliation background loop stopped")

    def _reconcile_active_orders(self) -> None:
        """Reconcile all active orders against MT5 history"""
        active_orders = self.order_book.get_active_orders()

        if not active_orders:
            return

        logger.debug(f"Reconciling {len(active_orders)} active orders")

        # Search recent deal history (last 2 hours to be safe)
        search_start = datetime.now() - timedelta(hours=2)
        search_end = datetime.now()

        try:
            # Get all recent deals across symbols
            symbols = list({order.symbol for order in active_orders})
            all_deals = []

            for symbol in symbols:
                deals = self.mt5.history_deals_get(
                    search_start, search_end, symbol=symbol
                )
                if deals:
                    all_deals.extend(deals)

            if not all_deals:
                logger.debug("No recent deals found")
                return

            # Process deals for active orders
            for deal in all_deals:
                self._process_deal_for_orders(deal, active_orders)

        except Exception as e:
            logger.error(f"Error reconciling active orders: {e}")

    def _process_deal_for_orders(self, deal, active_orders: list) -> None:
        """Process a deal against active orders"""
        deal_ticket = str(deal.ticket)

        # Skip already processed deals
        with self._deal_history_lock:
            if deal_ticket in self._processed_deals:
                return

        deal_comment = getattr(deal, "comment", "")
        if not deal_comment:
            return

        # Find matching order by client order ID
        matching_order = None
        for order in active_orders:
            if deal_comment == order.coid or deal_comment.startswith(order.coid):
                matching_order = order
                break

        if not matching_order:
            return

        # Extract deal information
        deal_qty = float(abs(deal.volume))  # Volume is always positive
        deal_price = float(deal.price)
        deal_time = float(deal.time)

        with self._deal_history_lock:
            self._processed_deals.add(deal_ticket)

        try:
            # Apply fill to order book
            updated_order = self.order_book.mark_partial(
                matching_order.coid, deal_qty, deal_price
            )

            # Emit appropriate event
            if updated_order.status == OrderStatus.FILLED:
                self.event_bus.publish(
                    Filled(
                        client_order_id=updated_order.coid,
                        symbol=updated_order.symbol,
                        side=updated_order.side,
                        quantity=updated_order.qty,
                        price=updated_order.avg_fill_price,
                        broker_order_id=updated_order.broker_order_id or "",
                        deal_ticket=deal_ticket,
                        timestamp=deal_time,
                    )
                )
                logger.info(
                    f"Order fully filled: {updated_order.coid} @ {updated_order.avg_fill_price}"
                )

            elif updated_order.status == OrderStatus.PARTIAL:
                self.event_bus.publish(
                    PartiallyFilled(
                        client_order_id=updated_order.coid,
                        symbol=updated_order.symbol,
                        side=updated_order.side,
                        fill_quantity=deal_qty,
                        fill_price=deal_price,
                        total_filled=updated_order.filled_qty,
                        remaining_quantity=updated_order.remaining_qty,
                        avg_fill_price=updated_order.avg_fill_price,
                        deal_ticket=deal_ticket,
                        timestamp=deal_time,
                    )
                )
                logger.info(
                    f"Partial fill: {updated_order.coid} +{deal_qty}@{deal_price} "
                    f"→ {updated_order.filled_qty}/{updated_order.qty}"
                )

        except Exception as e:
            logger.error(
                f"Error processing deal {deal_ticket} for order {matching_order.coid}: {e}"
            )

    def _process_pending_activations(self) -> None:
        """Check for pending orders that have been activated on broker"""
        # Get pending orders
        active_orders = self.order_book.get_active_orders()
        pending_orders = [o for o in active_orders if o.status == OrderStatus.PENDING]

        if not pending_orders:
            return

        try:
            # Check MT5 positions and orders for broker IDs
            positions = self.mt5.positions_get()
            orders = self.mt5.orders_get()

            # Track broker order IDs and their comments
            broker_order_map = {}

            # Check positions (for market orders that executed immediately)
            if positions:
                for pos in positions:
                    comment = getattr(pos, "comment", "")
                    if comment:
                        broker_order_map[comment] = str(pos.ticket)

            # Check pending orders
            if orders:
                for order in orders:
                    comment = getattr(order, "comment", "")
                    if comment:
                        broker_order_map[comment] = str(order.ticket)

            # Update pending orders with broker IDs
            for pending in pending_orders:
                if pending.coid in broker_order_map:
                    broker_id = broker_order_map[pending.coid]

                    # Update order book
                    self.order_book.upsert_on_accept(
                        pending.coid,
                        pending.symbol,
                        pending.side,
                        pending.qty,
                        broker_id,
                        pending.sl,
                        pending.tp,
                        OrderStatus.ACCEPTED,
                    )

                    # Emit activation event
                    self.event_bus.publish(
                        PendingActivated(
                            client_order_id=pending.coid,
                            broker_order_id=broker_id,
                            symbol=pending.symbol,
                            side=pending.side,
                            quantity=pending.qty,
                            timestamp=time.time(),
                        )
                    )

                    logger.info(
                        f"Pending order activated: {pending.coid} → {broker_id}"
                    )

        except Exception as e:
            logger.error(f"Error processing pending activations: {e}")

    def _process_cancel_requests(self) -> None:
        """Process cancel requests by checking if orders still exist on broker"""
        # This would be enhanced to handle specific cancel request tracking
        # For now, detect orders that disappeared from MT5
        active_orders = self.order_book.get_active_orders()
        accepted_orders = [
            o
            for o in active_orders
            if o.status in [OrderStatus.ACCEPTED, OrderStatus.PARTIAL]
        ]

        if not accepted_orders:
            return

        try:
            # Get current MT5 orders
            mt5_orders = self.mt5.orders_get()
            mt5_positions = self.mt5.positions_get()

            # Track active broker order IDs
            active_broker_ids = set()

            if mt5_orders:
                active_broker_ids.update(str(order.ticket) for order in mt5_orders)

            if mt5_positions:
                active_broker_ids.update(str(pos.ticket) for pos in mt5_positions)

            # Check for orders that disappeared
            for order in accepted_orders:
                if (
                    order.broker_order_id
                    and order.broker_order_id not in active_broker_ids
                ):
                    # Order no longer exists on broker - likely cancelled
                    self.order_book.mark_cancelled(order.coid)

                    self.event_bus.publish(
                        Cancelled(
                            client_order_id=order.coid,
                            symbol=order.symbol,
                            reason="Broker cancellation detected",
                            timestamp=time.time(),
                        )
                    )

                    logger.info(f"Order cancelled (broker): {order.coid}")

        except Exception as e:
            logger.error(f"Error processing cancel requests: {e}")

    def _process_stop_updates(self) -> None:
        """Process stop loss and take profit updates"""
        # This is a placeholder for stop update processing
        # In a full implementation, this would track stop modification requests
        # and verify they were applied on the broker side
        pass

    def cleanup_old_data(self, max_age_hours: int = 24) -> None:
        """Clean up old processed deals and order book data"""
        try:
            # Clean up order book
            deleted_orders = self.order_book.cleanup_old_orders(max_age_hours)

            # Clean up processed deals (keep 2x the order retention time)
            with self._deal_history_lock:
                # Note: In production, we'd want to persist and selectively clean processed_deals
                # For now, clear the entire set periodically to prevent memory growth
                if len(self._processed_deals) > 10000:  # Arbitrary limit
                    self._processed_deals.clear()
                    logger.info("Cleared processed deals cache (size limit)")

            if deleted_orders > 0:
                logger.info(f"Cleanup: removed {deleted_orders} old orders")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


# Legacy functions for backward compatibility
def wait_for_fill(
    mt5, client_order_id: str, symbol: str, timeout_sec: float = 4.0, poll: float = 0.25
) -> tuple[bool, str | None]:
    """
    Wait for order fill by polling MT5 deal history using client_order_id comment.

    Legacy function - consider using ReconciliationEngine for new code.
    """
    if not mt5:
        logger.error("MT5 module not provided")
        return False, None

    start_time = time.time()
    logger.info(
        f"Starting fill reconciliation for {client_order_id} on {symbol} "
        f"(timeout={timeout_sec}s, poll={poll}s)"
    )

    # Pre-calculate search window (1 hour back from start)
    search_start = datetime.now() - timedelta(hours=1)

    poll_count = 0

    while True:
        current_time = time.time()
        elapsed = current_time - start_time

        # Check timeout
        if elapsed > timeout_sec:
            logger.info(
                f"Fill reconciliation timeout for {client_order_id} after {elapsed:.2f}s "
                f"({poll_count} polls)"
            )
            return False, None

        poll_count += 1

        try:
            # Get deal history for the symbol
            # Search from 1 hour ago to now to ensure we catch the deal
            search_end = datetime.now()

            logger.debug(
                f"Poll #{poll_count}: Searching deals for {symbol} from "
                f"{search_start.strftime('%H:%M:%S')} to {search_end.strftime('%H:%M:%S')}"
            )

            # Get deals for the specific symbol in the time window
            deals = mt5.history_deals_get(search_start, search_end, symbol=symbol)

            if deals is None:
                logger.debug(f"No deals returned for {symbol} in search window")
            else:
                logger.debug(f"Found {len(deals)} deals for {symbol}")

                # Search for our deal by comment
                for deal in deals:
                    deal_comment = getattr(deal, "comment", "")

                    # Exact match on client_order_id
                    if deal_comment == client_order_id:
                        deal_ticket = str(deal.ticket)
                        logger.info(
                            f"✅ Fill found for {client_order_id}: deal #{deal_ticket} "
                            f"after {elapsed:.2f}s ({poll_count} polls)"
                        )
                        return True, deal_ticket

                    # Also check if comment starts with client_order_id
                    # (in case MT5 appends additional info)
                    elif deal_comment.startswith(client_order_id):
                        deal_ticket = str(deal.ticket)
                        logger.info(
                            f"✅ Fill found for {client_order_id} (prefix match): "
                            f"deal #{deal_ticket} after {elapsed:.2f}s ({poll_count} polls) "
                            f"comment='{deal_comment}'"
                        )
                        return True, deal_ticket

                logger.debug(
                    f"No matching deal found for {client_order_id} in {len(deals)} deals"
                )

        except Exception as e:
            logger.warning(
                f"Error during deal history search for {client_order_id}: {e}"
            )

        # Sleep before next poll
        time.sleep(poll)

    # This line should never be reached due to timeout check above
    return False, None


def get_deal_price(mt5, deal_ticket: str, symbol: str) -> float | None:
    """
    Get execution price for a specific deal ticket.

    Args:
        mt5: MT5 module instance
        deal_ticket: Deal ticket number as string
        symbol: Trading symbol

    Returns:
        Optional[float]: Deal execution price, or None if not found

    Example:
        >>> price = get_deal_price(mt5, "12345678", "XAUUSD")
        >>> if price:
        ...     print(f"Deal executed at ${price:.2f}")
    """
    if not mt5:
        logger.error("MT5 module not provided")
        return None

    try:
        # Search recent deals for the specific ticket
        search_start = datetime.now() - timedelta(hours=1)
        search_end = datetime.now()

        deals = mt5.history_deals_get(search_start, search_end, symbol=symbol)

        if deals:
            for deal in deals:
                if str(deal.ticket) == deal_ticket:
                    price = float(deal.price)
                    logger.debug(f"Found deal #{deal_ticket} price: {price}")
                    return price

        # Fallback: try to get deal directly by ticket (if MT5 supports it)
        # Note: This may not work in all MT5 versions
        logger.debug(f"Deal #{deal_ticket} not found in recent history")
        return None

    except Exception as e:
        logger.error(f"Error retrieving price for deal #{deal_ticket}: {e}")
        return None


def get_current_tick_price(mt5, symbol: str, side: str) -> float | None:
    """
    Get current market price for fallback when deal price is unavailable.

    Args:
        mt5: MT5 module instance
        symbol: Trading symbol
        side: Order side ("BUY" or "SELL")

    Returns:
        Optional[float]: Current ask (for BUY) or bid (for SELL) price

    Example:
        >>> price = get_current_tick_price(mt5, "XAUUSD", "BUY")
        >>> print(f"Current ask price: ${price:.2f}")
    """
    if not mt5:
        logger.error("MT5 module not provided")
        return None

    try:
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            logger.error(f"Cannot get tick data for {symbol}")
            return None

        if side == "BUY":
            price = float(tick.ask)
        elif side == "SELL":
            price = float(tick.bid)
        else:
            logger.error(f"Invalid side: {side}")
            return None

        logger.debug(f"Current {side} price for {symbol}: {price}")
        return price

    except Exception as e:
        logger.error(f"Error getting current price for {symbol}: {e}")
        return None
