"""
OrderBook - SQLite-based order state management for lifecycle tracking

Manages order states through: PENDING → ACCEPTED → PARTIAL → FILLED/CANCELLED
Tracks partial fills, average fill prices, and stop loss/take profit levels.
"""

import logging
import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import Optional

logger = logging.getLogger(__name__)

# SQLite schema for order and fill tracking
SCHEMA = """
CREATE TABLE IF NOT EXISTS orders(
    coid TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    qty REAL NOT NULL,
    filled_qty REAL DEFAULT 0,
    avg_fill_price REAL DEFAULT 0,
    broker_order_id TEXT,
    status TEXT NOT NULL,
    sl REAL,
    tp REAL,
    created_ts REAL NOT NULL,
    updated_ts REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS fills(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    coid TEXT NOT NULL,
    qty REAL NOT NULL,
    price REAL NOT NULL,
    ts REAL NOT NULL,
    FOREIGN KEY (coid) REFERENCES orders(coid)
);

CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_updated ON orders(updated_ts);
CREATE INDEX IF NOT EXISTS idx_fills_coid ON fills(coid);
"""


# Order status constants
class OrderStatus:
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    PARTIAL = "PARTIAL"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class OrderInfo:
    """Order information data class"""

    def __init__(
        self,
        coid: str,
        symbol: str,
        side: str,
        qty: float,
        filled_qty: float = 0,
        avg_fill_price: float = 0,
        broker_order_id: str | None = None,
        status: str = OrderStatus.PENDING,
        sl: float | None = None,
        tp: float | None = None,
        created_ts: float = 0,
        updated_ts: float = 0,
    ):
        self.coid = coid
        self.symbol = symbol
        self.side = side
        self.qty = qty
        self.filled_qty = filled_qty
        self.avg_fill_price = avg_fill_price
        self.broker_order_id = broker_order_id
        self.status = status
        self.sl = sl
        self.tp = tp
        self.created_ts = created_ts
        self.updated_ts = updated_ts

    @property
    def remaining_qty(self) -> float:
        """Remaining quantity to fill"""
        return max(0, self.qty - self.filled_qty)

    @property
    def is_fully_filled(self) -> bool:
        """Check if order is completely filled"""
        return (
            self.filled_qty >= self.qty - 1e-9
        )  # Small tolerance for float comparison

    @property
    def fill_percentage(self) -> float:
        """Fill percentage (0.0 to 1.0)"""
        return self.filled_qty / max(self.qty, 1e-9)


class OrderBook:
    """SQLite-based order book for order lifecycle management"""

    def __init__(self, db_path: str = "infra/order_book.sqlite"):
        """
        Initialize OrderBook with SQLite database

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._lock = threading.RLock()  # Thread-safe operations

        # Initialize database
        self._init_database()

        logger.info(f"OrderBook initialized with database: {db_path}")

    def _init_database(self):
        """Initialize database schema"""
        with self._get_connection() as conn:
            conn.executescript(SCHEMA)
            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Get thread-safe database connection"""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        try:
            yield conn
        finally:
            conn.close()

    def create_pending(
        self,
        coid: str,
        symbol: str,
        side: str,
        qty: float,
        sl: float | None = None,
        tp: float | None = None,
    ) -> None:
        """
        Create new pending order

        Args:
            coid: Client order ID
            symbol: Trading symbol
            side: Order side (BUY/SELL)
            qty: Order quantity
            sl: Stop loss price
            tp: Take profit price
        """
        with self._lock:
            now = time.time()

            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO orders(coid, symbol, side, qty, status, sl, tp, created_ts, updated_ts)
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(coid) DO UPDATE SET
                        symbol=excluded.symbol, side=excluded.side, qty=excluded.qty,
                        sl=excluded.sl, tp=excluded.tp, updated_ts=excluded.updated_ts
                """,
                    (coid, symbol, side, qty, OrderStatus.PENDING, sl, tp, now, now),
                )
                conn.commit()

            logger.debug(f"Created pending order: {coid} {side} {qty} {symbol}")

    def upsert_on_accept(
        self,
        coid: str,
        symbol: str,
        side: str,
        qty: float,
        broker_id: str,
        sl: float | None = None,
        tp: float | None = None,
        status: str = OrderStatus.ACCEPTED,
    ) -> None:
        """
        Update order on broker acceptance

        Args:
            coid: Client order ID
            symbol: Trading symbol
            side: Order side
            qty: Order quantity
            broker_id: Broker-assigned order ID
            sl: Stop loss price
            tp: Take profit price
            status: Order status
        """
        with self._lock:
            now = time.time()

            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO orders(coid, symbol, side, qty, broker_order_id, sl, tp, status, created_ts, updated_ts)
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(coid) DO UPDATE SET
                        broker_order_id=excluded.broker_order_id, status=excluded.status,
                        sl=excluded.sl, tp=excluded.tp, updated_ts=excluded.updated_ts
                """,
                    (
                        coid,
                        symbol,
                        side,
                        qty,
                        broker_id,
                        sl,
                        tp,
                        status,
                        now,
                        now,
                    ),
                )
                conn.commit()

            logger.debug(f"Order accepted: {coid} → {broker_id} status={status}")

    def mark_partial(self, coid: str, fill_qty: float, price: float) -> OrderInfo:
        """
        Mark partial fill and update aggregate fill data

        Args:
            coid: Client order ID
            fill_qty: Quantity filled in this event
            price: Fill price

        Returns:
            Updated OrderInfo

        Raises:
            ValueError: If order not found or invalid fill
        """
        with self._lock, self._get_connection() as conn:
            # Get current order state
            cur = conn.execute(
                """
                SELECT filled_qty, qty, avg_fill_price, symbol, side, status, sl, tp
                FROM orders WHERE coid = ?
            """,
                (coid,),
            )
            row = cur.fetchone()

            if not row:
                raise ValueError(f"Order not found: {coid}")

            filled, total, avg_price, symbol, side, status, sl, tp = row

            # Validate fill
            if fill_qty <= 0:
                raise ValueError(f"Invalid fill quantity: {fill_qty}")

            if filled + fill_qty > total + 1e-9:  # Small tolerance
                raise ValueError(f"Over-fill: {filled + fill_qty} > {total}")

                # Calculate new aggregate values
                new_filled = filled + fill_qty
                new_avg = ((avg_price * filled) + (price * fill_qty)) / max(
                    new_filled, 1e-9
                )

                # Determine new status
                new_status = (
                    OrderStatus.FILLED
                    if new_filled >= total - 1e-9
                    else OrderStatus.PARTIAL
                )

                now = time.time()

                # Record the fill
                conn.execute(
                    """
                    INSERT INTO fills(coid, qty, price, ts) VALUES(?, ?, ?, ?)
                """,
                    (coid, fill_qty, price, now),
                )

                # Update order
                conn.execute(
                    """
                    UPDATE orders SET filled_qty = ?, avg_fill_price = ?, status = ?, updated_ts = ?
                    WHERE coid = ?
                """,
                    (new_filled, new_avg, new_status, now, coid),
                )

                conn.commit()

                # Create updated order info
                order_info = OrderInfo(
                    coid=coid,
                    symbol=symbol,
                    side=side,
                    qty=total,
                    filled_qty=new_filled,
                    avg_fill_price=new_avg,
                    status=new_status,
                    sl=sl,
                    tp=tp,
                    updated_ts=now,
                )

                logger.info(
                    f"Partial fill: {coid} +{fill_qty}@{price} "
                    f"→ {new_filled}/{total} avg={new_avg:.5f} status={new_status}"
                )

                return order_info

    def mark_cancelled(self, coid: str) -> None:
        """
        Mark order as cancelled

        Args:
            coid: Client order ID
        """
        with self._lock:
            now = time.time()

            with self._get_connection() as conn:
                result = conn.execute(
                    """
                    UPDATE orders SET status = ?, updated_ts = ? WHERE coid = ?
                """,
                    (OrderStatus.CANCELLED, now, coid),
                )

                if result.rowcount == 0:
                    logger.warning(f"Cancel failed: Order not found: {coid}")
                else:
                    logger.info(f"Order cancelled: {coid}")

                conn.commit()

    def update_stops(
        self, coid: str, sl: float | None = None, tp: float | None = None
    ) -> bool:
        """
        Update stop loss and take profit levels

        Args:
            coid: Client order ID
            sl: New stop loss price
            tp: New take profit price

        Returns:
            True if order was found and updated
        """
        with self._lock:
            now = time.time()

            with self._get_connection() as conn:
                # Build dynamic update query
                updates = []
                params = []

                if sl is not None:
                    updates.append("sl = ?")
                    params.append(sl)

                if tp is not None:
                    updates.append("tp = ?")
                    params.append(tp)

                if not updates:
                    return True  # Nothing to update

                updates.append("updated_ts = ?")
                params.append(now)
                params.append(coid)

                query = f"UPDATE orders SET {', '.join(updates)} WHERE coid = ?"
                result = conn.execute(query, params)
                conn.commit()

                if result.rowcount > 0:
                    logger.info(f"Stops updated: {coid} SL={sl} TP={tp}")
                    return True
                else:
                    logger.warning(f"Stop update failed: Order not found: {coid}")
                    return False

    def get_order(self, coid: str) -> OrderInfo | None:
        """
        Get order information by client order ID

        Args:
            coid: Client order ID

        Returns:
            OrderInfo if found, None otherwise
        """
        with self._lock, self._get_connection() as conn:
            cur = conn.execute(
                """
                    SELECT coid, symbol, side, qty, filled_qty, avg_fill_price,
                           broker_order_id, status, sl, tp, created_ts, updated_ts
                    FROM orders WHERE coid = ?
                """,
                (coid,),
            )
            row = cur.fetchone()

            if row:
                return OrderInfo(*row)
            return None

    def get_active_orders(self) -> list[OrderInfo]:
        """
        Get all active (non-terminal) orders

        Returns:
            List of OrderInfo for active orders
        """
        terminal_statuses = (
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
        )

        with self._lock, self._get_connection() as conn:
            cur = conn.execute(
                """
                    SELECT coid, symbol, side, qty, filled_qty, avg_fill_price,
                           broker_order_id, status, sl, tp, created_ts, updated_ts
                    FROM orders WHERE status NOT IN ({})
                    ORDER BY created_ts
                """.format(
                    ",".join(["?"] * len(terminal_statuses))
                ),
                terminal_statuses,
            )

            return [OrderInfo(*row) for row in cur.fetchall()]

    def get_fills(self, coid: str) -> list[tuple[float, float, float]]:
        """
        Get fill history for an order

        Args:
            coid: Client order ID

        Returns:
            List of (qty, price, timestamp) tuples
        """
        with self._lock, self._get_connection() as conn:
            cur = conn.execute(
                """
                    SELECT qty, price, ts FROM fills WHERE coid = ? ORDER BY ts
                """,
                (coid,),
            )
            return cur.fetchall()

    def get_order_count_by_status(self) -> dict[str, int]:
        """
        Get count of orders by status

        Returns:
            Dictionary mapping status to count
        """
        with self._lock, self._get_connection() as conn:
            cur = conn.execute(
                """
                    SELECT status, COUNT(*) FROM orders GROUP BY status
                """
            )
            return dict(cur.fetchall())

    def cleanup_old_orders(self, max_age_hours: int = 24) -> int:
        """
        Clean up old terminal orders

        Args:
            max_age_hours: Maximum age in hours for terminal orders

        Returns:
            Number of orders deleted
        """
        cutoff_time = time.time() - (max_age_hours * 3600)
        terminal_statuses = (
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
        )

        with self._lock, self._get_connection() as conn:
            # Delete old fills first (foreign key constraint)
            conn.execute(
                """
                    DELETE FROM fills WHERE coid IN (
                        SELECT coid FROM orders
                        WHERE status IN ({}) AND updated_ts < ?
                    )
                """.format(
                    ",".join(["?"] * len(terminal_statuses))
                ),
                list(terminal_statuses) + [cutoff_time],
            )

            # Delete old orders
            result = conn.execute(
                """
                    DELETE FROM orders WHERE status IN ({}) AND updated_ts < ?
                """.format(
                    ",".join(["?"] * len(terminal_statuses))
                ),
                list(terminal_statuses) + [cutoff_time],
            )

            conn.commit()

            deleted_count = result.rowcount
            if deleted_count > 0:
                logger.info(
                    f"Cleaned up {deleted_count} old orders (>{max_age_hours}h)"
                )

            return deleted_count
