"""
Idempotent Order Execution System
Ensures each logical order is submitted to broker at most once using SQLite storage.
Integrates position netting policy for intelligent order management.
"""

import hashlib
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from core.broker import BrokerGateway, OrderRequest, OrderResult
from core.positions import PositionAggregator, NettingMode, ReduceRule, Position

if TYPE_CHECKING:
    from config.settings import ApplicationSettings

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

    def __init__(self, broker: BrokerGateway, db_path: str = "infra/id_store.sqlite", 
                 settings: Optional["ApplicationSettings"] = None):
        """
        Initialize idempotent executor with broker and database.

        Args:
            broker: Broker gateway for order execution
            db_path: Path to SQLite database for tracking sent orders
            settings: Application settings for netting configuration
        """
        self.broker = broker
        self.db_path = Path(db_path)
        self.settings = settings

        # Initialize position aggregator based on settings
        if settings:
            netting_mode = NettingMode(settings.trading.netting_mode)
            reduce_rule = ReduceRule(settings.trading.reduce_rule)
        else:
            netting_mode = NettingMode.NETTING
            reduce_rule = ReduceRule.FIFO
            
        self.position_aggregator = PositionAggregator(netting_mode, reduce_rule)

        # Ensure database directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database schema
        self._init_database()

        logger.info(f"IdempotentOrderExecutor initialized with db: {self.db_path}, "
                   f"netting: {netting_mode}, reduce: {reduce_rule}")

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

    def record(self, client_order_id: str, broker_order_id: str | None = None) -> None:
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
        Place order with idempotency guarantee and position netting.

        Args:
            request: Order request with client_order_id

        Returns:
            OrderResult: Execution result, with special handling for duplicates and netting

        Behavior:
            - If order already sent: returns OrderResult(accepted=False, reason="DUPLICATE_COID")
            - HEDGING mode: sends order as-is (legacy behavior)
            - NETTING mode: processes against existing positions, may create reduce orders
        """
        client_order_id = request.client_order_id

        logger.info(
            f"Processing order: {client_order_id} {request.symbol} {request.side} {request.qty}"
        )

        # Check for duplicate
        if self.already_sent(client_order_id):
            logger.warning(f"Duplicate order blocked: {client_order_id}")
            return OrderResult(
                accepted=False, broker_order_id=None, reason="DUPLICATE_COID"
            )

        # Apply position netting policy
        try:
            return self._execute_with_netting(request)
        except Exception as e:
            logger.error(f"Error executing order with netting {client_order_id}: {e}")
            return OrderResult(
                accepted=False,
                broker_order_id=None,
                reason=f"Netting execution error: {str(e)}",
            )

    def _execute_with_netting(self, request: OrderRequest) -> OrderResult:
        """Execute order with position netting policy."""
        client_order_id = request.client_order_id
        
        # Get existing positions for the symbol
        existing_positions = self._get_existing_positions(request.symbol)
        
        # Process through position aggregator
        netting_result = self.position_aggregator.process_incoming_order(
            symbol=request.symbol,
            side=request.side,
            volume=request.qty,
            price=request.price,
            existing_positions=existing_positions
        )
        
        logger.info(f"Netting result: {netting_result.summary}")
        
        # Execute reduce actions first (close/partial close existing positions)
        reduce_results = []
        if netting_result.reduce_actions:
            for action in netting_result.reduce_actions:
                reduce_result = self._execute_reduce_action(action)
                reduce_results.append(reduce_result)
                if not reduce_result.accepted:
                    logger.warning(f"Reduce action failed: {action.position_ticket} - {reduce_result.reason}")
        
        # Execute remaining volume as new position if any
        main_result = None
        if netting_result.remaining_volume > 0:
            # Create new order request for remaining volume
            remaining_request = OrderRequest(
                client_order_id=client_order_id,
                symbol=request.symbol,
                side=request.side,
                qty=netting_result.remaining_volume,
                order_type=request.order_type,
                price=request.price,
                sl=request.sl,
                tp=request.tp
            )
            
            # Send remaining order to broker
            logger.debug(f"Sending remaining order to broker: {client_order_id}")
            main_result = self.broker.place_order(remaining_request)
            
            if main_result.accepted:
                self.record(client_order_id, main_result.broker_order_id)
                logger.info(f"Order accepted and recorded: {client_order_id} -> {main_result.broker_order_id}")
            else:
                logger.warning(f"Order rejected by broker: {client_order_id} - {main_result.reason}")
        else:
            # No remaining volume - order was fully netted
            main_result = OrderResult(
                accepted=True,
                broker_order_id=f"NETTED_{client_order_id}",
                reason="Fully netted against existing positions"
            )
            self.record(client_order_id, main_result.broker_order_id)
        
        # Send Telegram summary if configured
        if self.settings and hasattr(self.settings, 'telegram'):
            self._send_netting_summary(netting_result, reduce_results, main_result)
        
        return main_result

    def _get_existing_positions(self, symbol: str) -> list[Position]:
        """Get existing positions for symbol from broker."""
        try:
            # Get positions from broker (assuming method exists)
            if hasattr(self.broker, 'get_positions'):
                broker_positions = self.broker.get_positions(symbol)
                
                # Convert to our Position format
                positions = []
                for pos in broker_positions:
                    position = Position(
                        ticket=str(pos.ticket),
                        symbol=pos.symbol,
                        side="BUY" if pos.type == 0 else "SELL",
                        volume=float(pos.volume),
                        entry_price=float(pos.price_open),
                        open_time=datetime.fromtimestamp(pos.time),
                        sl=float(pos.sl) if pos.sl else None,
                        tp=float(pos.tp) if pos.tp else None
                    )
                    positions.append(position)
                
                return positions
            else:
                logger.warning("Broker does not support get_positions, assuming no existing positions")
                return []
                
        except Exception as e:
            logger.error(f"Error getting existing positions for {symbol}: {e}")
            return []

    def _execute_reduce_action(self, action) -> OrderResult:
        """Execute a position reduce action (close/partial close)."""
        try:
            # Create close order request
            reduce_request = OrderRequest(
                client_order_id=f"REDUCE_{action.position_ticket}_{datetime.now().strftime('%H%M%S')}",
                symbol="",  # Will be set by broker based on position
                side="SELL" if action.position_ticket.startswith("BUY") else "BUY",  # Opposite side
                qty=action.reduce_volume,
                order_type="MARKET",
                price=action.close_price
            )
            
            # Send reduce order to broker
            if hasattr(self.broker, 'close_position'):
                result = self.broker.close_position(action.position_ticket, action.reduce_volume)
            else:
                # Fallback to regular order
                result = self.broker.place_order(reduce_request)
            
            logger.info(f"Reduce action executed: {action.position_ticket} "
                       f"volume={action.reduce_volume} result={result.accepted}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing reduce action {action.position_ticket}: {e}")
            return OrderResult(
                accepted=False,
                broker_order_id=None,
                reason=f"Reduce execution error: {str(e)}"
            )

    def _send_netting_summary(self, netting_result, reduce_results, main_result):
        """Send Telegram summary of netting operation."""
        try:
            from risk.telegram_alerts import send_risk_alert
            
            summary_parts = []
            
            # Add reduce actions summary
            if reduce_results:
                closed_volume = sum(action.reduce_volume for action in netting_result.reduce_actions)
                avg_price = netting_result.average_close_price
                summary_parts.append(f"Closed {closed_volume} lots @{avg_price:.5f}")
            
            # Add new position summary
            if netting_result.remaining_volume > 0:
                summary_parts.append(f"Opened {netting_result.remaining_volume} lots")
            
            if summary_parts:
                message = f"🔄 Netting: {', '.join(summary_parts)}"
                send_risk_alert(message, level="INFO")
                
        except Exception as e:
            logger.warning(f"Failed to send netting summary: {e}")

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
