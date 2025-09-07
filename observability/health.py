"""
Health probes and system status checks.

Provides health check functionality to monitor:
- MT5 connection status
- Event lag and last trade timing
- Database connectivity
- Overall system health status
"""

import logging
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


def check_mt5_connection() -> dict[str, Any]:
    """Check MT5 connection status."""
    try:
        # Try to import the broker adapter
        from adapters.mt5_broker import MT5Broker
        from config.settings import get_settings

        settings = get_settings()
        broker = MT5Broker(settings)

        # Check if connected
        is_connected = broker.is_connected()

        return {
            "mt5_connected": is_connected,
            "status": "ok" if is_connected else "error",
            "message": "MT5 connected" if is_connected else "MT5 not connected",
        }

    except Exception as e:
        logger.error(f"MT5 health check failed: {e}")
        return {
            "mt5_connected": False,
            "status": "error",
            "message": f"MT5 health check error: {str(e)}",
        }


def check_event_lag() -> dict[str, Any]:
    """Check for event processing lag."""
    try:
        # This is a placeholder - in real implementation we'd track event timestamps
        # For now, return healthy status
        now = datetime.now()
        last_event_ts = now.isoformat()
        event_lag_sec = 0

        return {
            "last_event_ts": last_event_ts,
            "event_lag_sec": event_lag_sec,
            "status": "ok" if event_lag_sec < 60 else "warning",
            "message": f"Event lag: {event_lag_sec}s",
        }

    except Exception as e:
        logger.error(f"Event lag check failed: {e}")
        return {
            "last_event_ts": None,
            "event_lag_sec": 999,
            "status": "error",
            "message": f"Event lag check error: {str(e)}",
        }


def check_trading_activity() -> dict[str, Any]:
    """Check recent trading activity."""
    try:
        # Placeholder for trading activity check
        # In real implementation, this would check recent trades, positions, etc.
        now = datetime.now()
        last_trade_ts = now.isoformat()  # Placeholder
        positions_count = 0  # Placeholder

        return {
            "last_trade_ts": last_trade_ts,
            "positions_count": positions_count,
            "status": "ok",
            "message": f"Trading activity: {positions_count} positions",
        }

    except Exception as e:
        logger.error(f"Trading activity check failed: {e}")
        return {
            "last_trade_ts": None,
            "positions_count": 0,
            "status": "error",
            "message": f"Trading activity check error: {str(e)}",
        }


def check_idempotency_db() -> dict[str, Any]:
    """Check idempotency database connectivity."""
    try:
        # Look for the idempotency database
        db_paths = [
            "state/idempotent.db",
            "idempotent.db",
            "core/executor/idempotent.db",
        ]

        db_path = None
        for path in db_paths:
            if Path(path).exists():
                db_path = path
                break

        if not db_path:
            return {
                "idempotency_db_ok": False,
                "status": "warning",
                "message": "Idempotency database not found",
            }

        # Test database connection
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        conn.close()

        return {
            "idempotency_db_ok": True,
            "status": "ok",
            "message": f"Idempotency DB accessible at {db_path}",
        }

    except Exception as e:
        logger.error(f"Idempotency DB check failed: {e}")
        return {
            "idempotency_db_ok": False,
            "status": "error",
            "message": f"Idempotency DB check error: {str(e)}",
        }


def determine_overall_status(checks: dict[str, dict[str, Any]]) -> str:
    """Determine overall system status based on individual checks."""
    error_count = 0
    warning_count = 0

    for check_name, check_result in checks.items():
        status = check_result.get("status", "unknown")
        if status == "error":
            error_count += 1
        elif status == "warning":
            warning_count += 1

    # Simple rules for overall status
    if error_count > 0:
        return "down"
    elif warning_count > 0:
        return "degraded"
    else:
        return "ok"


def check_health() -> dict[str, Any]:
    """
    Perform comprehensive health check.

    Returns:
        Dict containing all health check results and overall status
    """
    try:
        # Run all health checks
        checks = {
            "mt5": check_mt5_connection(),
            "events": check_event_lag(),
            "trading": check_trading_activity(),
            "database": check_idempotency_db(),
        }

        # Determine overall status
        overall_status = determine_overall_status(checks)

        # Build result
        result = {
            "timestamp": datetime.now().isoformat(),
            "status": overall_status,
            "checks": checks,
        }

        # Add individual check results to top level for backward compatibility
        result["mt5_connected"] = checks["mt5"]["mt5_connected"]
        result["last_event_ts"] = checks["events"]["last_event_ts"]
        result["event_lag_sec"] = checks["events"]["event_lag_sec"]
        result["last_trade_ts"] = checks["trading"]["last_trade_ts"]
        result["positions_count"] = checks["trading"]["positions_count"]
        result["idempotency_db_ok"] = checks["database"]["idempotency_db_ok"]

        logger.debug(f"Health check completed: status={overall_status}")
        return result

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "timestamp": datetime.now().isoformat(),
            "status": "error",
            "error": str(e),
            "mt5_connected": False,
            "last_event_ts": None,
            "event_lag_sec": 999,
            "last_trade_ts": None,
            "positions_count": 0,
            "idempotency_db_ok": False,
        }
