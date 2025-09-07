"""
Order Reconciliation System
Tracks order execution using MT5 history_deals_get for reliable fill detection.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


def wait_for_fill(
    mt5, client_order_id: str, symbol: str, timeout_sec: float = 4.0, poll: float = 0.25
) -> tuple[bool, str | None]:
    """
    Wait for order fill by polling MT5 deal history using client_order_id comment.

    Args:
        mt5: MT5 module instance (MetaTrader5)
        client_order_id: Client order ID to search for in deal comments
        symbol: Trading symbol for the order
        timeout_sec: Maximum wait time in seconds (default: 4.0)
        poll: Polling interval in seconds (default: 0.25)

    Returns:
        Tuple[bool, Optional[str]]: (found, deal_ticket)
        - found: True if deal with matching comment was found
        - deal_ticket: Deal ticket number as string if found, None otherwise

    Algorithm:
        1. Start timer at t0 = now
        2. Poll loop:
           - Get deal history from (now - 1 hour) to now
           - Search for deal with comment == client_order_id
           - If found: return (True, deal_ticket)
           - Sleep for poll interval
           - If timeout exceeded: return (False, None)

    Example:
        >>> import MetaTrader5 as mt5
        >>> found, ticket = wait_for_fill(mt5, "abc123", "XAUUSD", timeout_sec=3.0)
        >>> if found:
        ...     print(f"Order filled: deal ticket {ticket}")
        >>> else:
        ...     print("Order not filled within timeout")
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
