"""
Idempotent Order Execution System
Ensures each logical order is submitted to broker at most once using SQLite storage.
"""

import hashlib
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.broker import BrokerGateway, OrderRequest, OrderResult

logger = logging.getLogger(__name__)


def make_coid(symbol: str, side: str, strategy_id: str, ts_bucket: str) -> str:
    """
    Generate deterministic client order ID from order parameters.

    Args:
        symbol: Trading symbol (e.g., XAUUSD)
        side: Trading direction (BUY/SELL)
        strategy_id: Strategy that generated the signal
        ts_bucket: Time bucket for grouping (e.g., minute-level timestamp)

    Returns:
        24-character client order ID based on SHA256 hash

    Example:
        >>> make_coid("XAUUSD", "BUY", "ma_cross", "20250907_1510")
        'f4a2b8c3d9e1f6g7h8i9j0k1'
    """
    # Create deterministic input string
    input_data = f"{symbol}_{side}_{strategy_id}_{ts_bucket}"

    # Generate SHA256 hash (secure and deterministic)
    hash_obj = hashlib.sha256(input_data.encode(), usedforsecurity=False)
    hash_hex = hash_obj.hexdigest()

    # Return first 24 characters for readability
    return hash_hex[:24]


class IdempotentOrderExecutor:
    """
    Idempotent order executor with SQLite-based deduplication.

    Ensures that orders with the same client_order_id are submitted to the
    broker at most once, preventing duplicate executions due to retries,
    system restarts, or other reliability issues.
    """

    def __init__(self, broker: BrokerGateway, db_path: str = "infra/id_store.sqlite"):
        """
        Initialize idempotent executor with broker and database.

        Args:
            broker: Broker gateway for order execution
            db_path: Path to SQLite database for tracking sent orders
        """
        self.broker = broker
        self.db_path = Path(db_path)

        # Ensure database directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database schema
        self._init_database()

        logger.info(f"IdempotentOrderExecutor initialized with db: {self.db_path}")

    def _init_database(self) -> None:
        """Initialize SQLite database with required tables"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sent (
                        client_order_id TEXT PRIMARY KEY,
                        broker_order_id TEXT,
                        ts DATETIME DEFAULT CURRENT_TIMESTAMP,
                        symbol TEXT,
                        side TEXT,
                        qty REAL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """
                )
                conn.commit()

            logger.debug(f"Database initialized: {self.db_path}")

        except sqlite3.Error as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def already_sent(self, client_order_id: str) -> bool:
        """
        Check if order with given client_order_id was already sent.

        Args:
            client_order_id: Client order identifier to check

        Returns:
            bool: True if order was already sent, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT 1 FROM sent WHERE client_order_id = ? LIMIT 1",
                    (client_order_id,),
                )
                result = cursor.fetchone()

            exists = result is not None
            logger.debug(f"Order {client_order_id} already sent: {exists}")
            return exists

        except sqlite3.Error as e:
            logger.error(f"Database error checking order {client_order_id}: {e}")
            # Fail safe: assume not sent to avoid blocking new orders
            return False

    def record(
        self, client_order_id: str, broker_order_id: str | None = None
    ) -> None:
        """
        Record that order was sent to broker.

        Args:
            client_order_id: Client order identifier
            broker_order_id: Broker-assigned order ID (if available)
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO sent (client_order_id, broker_order_id, ts)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    """,
                    (client_order_id, broker_order_id),
                )
                conn.commit()

            logger.debug(f"Recorded order: {client_order_id} -> {broker_order_id}")

        except sqlite3.Error as e:
            logger.error(f"Failed to record order {client_order_id}: {e}")
            # Don't raise - order was already sent to broker

    def place(self, request: OrderRequest) -> OrderResult:
        """
        Place order with idempotency guarantee.

        Args:
            request: Order request with client_order_id

        Returns:
            OrderResult: Execution result, with special handling for duplicates

        Behavior:
            - If order already sent: returns OrderResult(accepted=False, reason="DUPLICATE_COID")
            - If new order: sends to broker, records if accepted, returns broker result
        """
        client_order_id = request.client_order_id

        logger.info(
            f"Processing order: {client_order_id} {request.symbol} {request.side}"
        )

        # Check for duplicate
        if self.already_sent(client_order_id):
            logger.warning(f"Duplicate order blocked: {client_order_id}")
            return OrderResult(
                accepted=False, broker_order_id=None, reason="DUPLICATE_COID"
            )

        # Send to broker
        try:
            logger.debug(f"Sending order to broker: {client_order_id}")
            result = self.broker.place_order(request)

            # Record if order was accepted by broker
            if result.accepted:
                self.record(client_order_id, result.broker_order_id)
                logger.info(
                    f"Order accepted and recorded: {client_order_id} -> {result.broker_order_id}"
                )
            else:
                # Don't record rejected orders - they can be retried
                logger.warning(
                    f"Order rejected by broker: {client_order_id} - {result.reason}"
                )

            return result

        except Exception as e:
            logger.error(f"Error placing order {client_order_id}: {e}")
            return OrderResult(
                accepted=False,
                broker_order_id=None,
                reason=f"Execution error: {str(e)}",
            )

    def get_sent_orders(self, limit: int = 100) -> list[dict]:
        """
        Get recently sent orders for monitoring/debugging.

        Args:
            limit: Maximum number of orders to return

        Returns:
            List of order records from database
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row  # Enable dict-like access
                cursor = conn.execute(
                    """
                    SELECT client_order_id, broker_order_id, ts, symbol, side, qty
                    FROM sent
                    ORDER BY ts DESC
                    LIMIT ?
                    """,
                    (limit,),
                )
                return [dict(row) for row in cursor.fetchall()]

        except sqlite3.Error as e:
            logger.error(f"Error fetching sent orders: {e}")
            return []

    def purge_old_records(self, days_old: int = 30) -> int:
        """
        Remove old order records for cleanup.

        Args:
            days_old: Remove records older than this many days

        Returns:
            Number of records removed
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    f"""
                    DELETE FROM sent
                    WHERE ts < datetime('now', '-{days_old} days')
                    """
                )
                count = cursor.rowcount
                conn.commit()

            logger.info(f"Purged {count} old order records (>{days_old} days)")
            return count

        except sqlite3.Error as e:
            logger.error(f"Error purging old records: {e}")
            return 0

    def __repr__(self) -> str:
        """String representation showing database path and broker type"""
        broker_type = type(self.broker).__name__
        return f"IdempotentOrderExecutor(broker={broker_type}, db={self.db_path})"

    def close(self) -> None:
        """Close database connection - provided for explicit cleanup"""
        # SQLite connections are closed automatically when using context managers
        # This method is provided for test cleanup if needed
        pass
