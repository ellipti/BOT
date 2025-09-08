"""
Dashboard dependencies - shared components and data access layer

Provides centralized access to:
- OrderBook for order/fill data
- Metrics reader from observability layer
- Health checker for system status
- Chart data aggregation
"""

import logging
import sqlite3
from contextlib import contextmanager
from typing import Any, Optional

from core.executor.order_book import OrderBook
from observability.health import check_health
from observability.metrics import MetricsRegistry
from observability.metrics import render_as_text as get_metrics_text

logger = logging.getLogger(__name__)


class DashboardDataProvider:
    """Centralized data provider for dashboard components"""

    def __init__(self, order_book_path: str = "order_book.db"):
        self.order_book_path = order_book_path
        self._order_book: OrderBook | None = None

    def get_order_book(self) -> OrderBook:
        """Get OrderBook instance (lazy initialized)"""
        if self._order_book is None:
            self._order_book = OrderBook(db_path=self.order_book_path)
        return self._order_book

    def get_health_status(self) -> dict[str, Any]:
        """Get system health status"""
        try:
            health_data = check_health()
            return {
                "status": (
                    "healthy" if health_data.get("status") == "UP" else "degraded"
                ),
                "details": health_data,
                "timestamp": health_data.get("timestamp"),
                "components": health_data.get("components", {}),
            }
        except Exception as e:
            logger.error(f"Failed to get health status: {e}")
            return {
                "status": "error",
                "details": {"error": str(e)},
                "timestamp": None,
                "components": {},
            }

    def get_metrics_data(self) -> dict[str, Any]:
        """Get parsed metrics data"""
        try:
            metrics_text = get_metrics_text()
            # Parse simple metrics from Prometheus format
            metrics = {}
            for line in metrics_text.split("\n"):
                line = line.strip()
                if line and not line.startswith("#"):
                    try:
                        if " " in line:
                            metric_name, value = line.rsplit(" ", 1)
                            metrics[metric_name] = float(value)
                    except (ValueError, IndexError):
                        continue

            return {
                "raw_metrics": metrics_text,
                "parsed_metrics": metrics,
                "total_metrics": len(metrics),
            }
        except Exception as e:
            logger.error(f"Failed to get metrics: {e}")
            return {
                "raw_metrics": "",
                "parsed_metrics": {},
                "total_metrics": 0,
                "error": str(e),
            }

    def get_orders_summary(self) -> dict[str, Any]:
        """Get orders summary from OrderBook"""
        try:
            order_book = self.get_order_book()

            # Get orders by status
            with self._get_db_connection() as conn:
                cursor = conn.cursor()

                # Count orders by status
                cursor.execute(
                    """
                    SELECT status, COUNT(*)
                    FROM orders
                    GROUP BY status
                """
                )
                status_counts = dict(cursor.fetchall())

                # Get recent orders (last 10)
                cursor.execute(
                    """
                    SELECT coid, symbol, side, qty, filled_qty, status,
                           datetime(created_ts, 'unixepoch') as created_time
                    FROM orders
                    ORDER BY created_ts DESC
                    LIMIT 10
                """
                )
                recent_orders = [
                    {
                        "coid": row[0],
                        "symbol": row[1],
                        "side": row[2],
                        "qty": row[3],
                        "filled_qty": row[4],
                        "status": row[5],
                        "created_time": row[6],
                    }
                    for row in cursor.fetchall()
                ]

                # Calculate today's PnL (simplified)
                cursor.execute(
                    """
                    SELECT SUM(
                        CASE
                            WHEN side = 'BUY' THEN filled_qty * avg_fill_price * -1
                            WHEN side = 'SELL' THEN filled_qty * avg_fill_price
                            ELSE 0
                        END
                    ) as total_pnl
                    FROM orders
                    WHERE status IN ('FILLED', 'PARTIAL')
                    AND date(created_ts, 'unixepoch') = date('now')
                """
                )
                today_pnl = cursor.fetchone()[0] or 0.0

                return {
                    "status_counts": status_counts,
                    "recent_orders": recent_orders,
                    "today_pnl": today_pnl,
                    "total_orders": sum(status_counts.values()),
                }

        except Exception as e:
            logger.error(f"Failed to get orders summary: {e}")
            return {
                "status_counts": {},
                "recent_orders": [],
                "today_pnl": 0.0,
                "total_orders": 0,
                "error": str(e),
            }

    def get_orders_by_status(self, status: str | None = None) -> list[dict[str, Any]]:
        """Get orders filtered by status"""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()

                if status:
                    cursor.execute(
                        """
                        SELECT coid, symbol, side, qty, filled_qty, avg_fill_price,
                               broker_order_id, status, sl, tp,
                               datetime(created_ts, 'unixepoch') as created_time,
                               datetime(updated_ts, 'unixepoch') as updated_time
                        FROM orders
                        WHERE status = ?
                        ORDER BY created_ts DESC
                    """,
                        (status,),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT coid, symbol, side, qty, filled_qty, avg_fill_price,
                               broker_order_id, status, sl, tp,
                               datetime(created_ts, 'unixepoch') as created_time,
                               datetime(updated_ts, 'unixepoch') as updated_time
                        FROM orders
                        ORDER BY created_ts DESC
                    """
                    )

                return [
                    {
                        "coid": row[0],
                        "symbol": row[1],
                        "side": row[2],
                        "qty": row[3],
                        "filled_qty": row[4],
                        "avg_fill_price": row[5],
                        "broker_order_id": row[6],
                        "status": row[7],
                        "sl": row[8],
                        "tp": row[9],
                        "created_time": row[10],
                        "updated_time": row[11],
                    }
                    for row in cursor.fetchall()
                ]

        except Exception as e:
            logger.error(f"Failed to get orders by status {status}: {e}")
            return []

    def get_chart_data(self, symbol: str, limit: int = 100) -> dict[str, Any]:
        """Get chart data for symbol (mock implementation)"""
        try:
            # For now, return mock data - in real implementation this would
            # query price history from MT5 or stored historical data
            import random
            import time
            from datetime import datetime, timedelta

            base_price = 1.2000 if symbol == "EURUSD" else 2000.0
            data_points = []

            current_time = datetime.now()
            current_price = base_price

            for i in range(limit):
                timestamp = current_time - timedelta(minutes=i * 5)
                # Simple random walk
                change = random.uniform(-0.001, 0.001) * base_price
                current_price += change

                data_points.append(
                    {
                        "timestamp": timestamp.isoformat(),
                        "price": round(current_price, 5),
                        "volume": random.randint(100, 1000),
                    }
                )

            # Reverse to get chronological order
            data_points.reverse()

            return {
                "symbol": symbol,
                "data_points": data_points,
                "count": len(data_points),
                "latest_price": data_points[-1]["price"] if data_points else 0,
            }

        except Exception as e:
            logger.error(f"Failed to get chart data for {symbol}: {e}")
            return {
                "symbol": symbol,
                "data_points": [],
                "count": 0,
                "latest_price": 0,
                "error": str(e),
            }

    @contextmanager
    def _get_db_connection(self):
        """Get database connection context manager"""
        conn = sqlite3.connect(self.order_book_path)
        try:
            yield conn
        finally:
            conn.close()


# Global instance for dependency injection
_dashboard_provider: DashboardDataProvider | None = None


def get_dashboard_provider(db_path: str = None) -> DashboardDataProvider:
    """Get global dashboard data provider instance"""
    global _dashboard_provider

    # Use demo database if it exists, otherwise default
    if db_path is None:
        demo_db = "demo_order_book.db"
        default_db = "order_book.db"

        from pathlib import Path

        if Path(demo_db).exists():
            db_path = demo_db
        else:
            db_path = default_db

    if _dashboard_provider is None or _dashboard_provider.order_book_path != db_path:
        _dashboard_provider = DashboardDataProvider(db_path)
    return _dashboard_provider
