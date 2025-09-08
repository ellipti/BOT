#!/usr/bin/env python3
"""
Dashboard Demo Setup Script

Creates demo data and starts the dashboard for testing.
"""

import sqlite3
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path


# Create demo order book data
def create_demo_data(db_path: str = "demo_order_book.db"):
    """Create demo order book data for dashboard testing"""

    # Remove existing demo database
    Path(db_path).unlink(missing_ok=True)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create orders table
    cursor.execute(
        """
        CREATE TABLE orders (
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
        )
    """
    )

    # Create fills table
    cursor.execute(
        """
        CREATE TABLE fills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            coid TEXT NOT NULL,
            fill_price REAL NOT NULL,
            fill_qty REAL NOT NULL,
            fill_time REAL NOT NULL,
            FOREIGN KEY (coid) REFERENCES orders (coid)
        )
    """
    )

    # Sample demo orders
    base_time = datetime.now() - timedelta(hours=24)
    demo_orders = [
        {
            "coid": str(uuid.uuid4()),
            "symbol": "EURUSD",
            "side": "BUY",
            "qty": 0.1,
            "filled_qty": 0.1,
            "avg_fill_price": 1.20500,
            "broker_order_id": "MT5_12345",
            "status": "FILLED",
            "sl": 1.20300,
            "tp": 1.21000,
            "created_ts": (base_time + timedelta(hours=1)).timestamp(),
            "updated_ts": (base_time + timedelta(hours=1, minutes=5)).timestamp(),
        },
        {
            "coid": str(uuid.uuid4()),
            "symbol": "GBPUSD",
            "side": "SELL",
            "qty": 0.2,
            "filled_qty": 0.1,
            "avg_fill_price": 1.28200,
            "broker_order_id": "MT5_12346",
            "status": "PARTIAL",
            "sl": 1.28500,
            "tp": 1.27500,
            "created_ts": (base_time + timedelta(hours=2)).timestamp(),
            "updated_ts": (base_time + timedelta(hours=2, minutes=15)).timestamp(),
        },
        {
            "coid": str(uuid.uuid4()),
            "symbol": "XAUUSD",
            "side": "BUY",
            "qty": 0.05,
            "filled_qty": 0.0,
            "avg_fill_price": 0.0,
            "broker_order_id": None,
            "status": "PENDING",
            "sl": 1950.00,
            "tp": 2050.00,
            "created_ts": (base_time + timedelta(hours=3)).timestamp(),
            "updated_ts": (base_time + timedelta(hours=3)).timestamp(),
        },
        {
            "coid": str(uuid.uuid4()),
            "symbol": "USDJPY",
            "side": "SELL",
            "qty": 0.15,
            "filled_qty": 0.0,
            "avg_fill_price": 0.0,
            "broker_order_id": None,
            "status": "CANCELLED",
            "sl": None,
            "tp": None,
            "created_ts": (base_time + timedelta(hours=4)).timestamp(),
            "updated_ts": (base_time + timedelta(hours=4, minutes=30)).timestamp(),
        },
        {
            "coid": str(uuid.uuid4()),
            "symbol": "EURUSD",
            "side": "SELL",
            "qty": 0.25,
            "filled_qty": 0.25,
            "avg_fill_price": 1.20300,
            "broker_order_id": "MT5_12347",
            "status": "FILLED",
            "sl": 1.20600,
            "tp": 1.19800,
            "created_ts": (base_time + timedelta(hours=5)).timestamp(),
            "updated_ts": (base_time + timedelta(hours=5, minutes=10)).timestamp(),
        },
    ]

    # Insert demo orders
    for order in demo_orders:
        cursor.execute(
            """
            INSERT INTO orders (
                coid, symbol, side, qty, filled_qty, avg_fill_price,
                broker_order_id, status, sl, tp, created_ts, updated_ts
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                order["coid"],
                order["symbol"],
                order["side"],
                order["qty"],
                order["filled_qty"],
                order["avg_fill_price"],
                order["broker_order_id"],
                order["status"],
                order["sl"],
                order["tp"],
                order["created_ts"],
                order["updated_ts"],
            ),
        )

        # Add fills for filled orders
        if order["status"] in ["FILLED", "PARTIAL"] and order["filled_qty"] > 0:
            cursor.execute(
                """
                INSERT INTO fills (coid, fill_price, fill_qty, fill_time)
                VALUES (?, ?, ?, ?)
            """,
                (
                    order["coid"],
                    order["avg_fill_price"],
                    order["filled_qty"],
                    order["updated_ts"],
                ),
            )

    conn.commit()
    conn.close()

    print(f"✅ Created demo order book database: {db_path}")
    print(f"   - {len(demo_orders)} demo orders")
    print("   - Multiple symbols: EURUSD, GBPUSD, XAUUSD, USDJPY")
    print("   - Various statuses: FILLED, PARTIAL, PENDING, CANCELLED")
    return db_path


def main():
    """Create demo data and show instructions"""
    print("🚀 BOT Dashboard Demo Setup")
    print("=" * 50)

    # Create demo data
    db_path = create_demo_data()

    print()
    print("📊 Dashboard Access Instructions:")
    print()
    print("1. Start the dashboard:")
    print("   python scripts/run_dashboard.py --reload")
    print()
    print("2. Access the dashboard:")
    print("   URL: http://127.0.0.1:8080")
    print()
    print("3. Authentication:")
    print("   Add header: X-DASH-TOKEN: dev-dashboard-token-2025")
    print(
        "   Or use: curl -H 'X-DASH-TOKEN: dev-dashboard-token-2025' http://127.0.0.1:8080"
    )
    print()
    print("4. Available endpoints:")
    print("   - GET /            → Overview dashboard")
    print("   - GET /orders      → Orders management")
    print("   - GET /charts/EURUSD → Chart visualization")
    print("   - GET /api/health  → Health API")
    print("   - GET /api/orders  → Orders API")
    print("   - GET /healthz     → Health check (no auth)")
    print()
    print("💡 Demo database created with sample orders for testing.")
    print("   Use DASH_DATA_PATH environment variable to specify path.")


if __name__ == "__main__":
    main()
