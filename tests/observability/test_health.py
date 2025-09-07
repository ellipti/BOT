"""
Tests for health check functionality.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import unittest
from unittest.mock import Mock, patch

from observability.health import (
    check_health,
    check_idempotency_db,
    check_mt5_connection,
    determine_overall_status,
)


class TestHealthChecks(unittest.TestCase):
    """Test health check functionality."""

    def test_determine_overall_status(self):
        """Test overall status determination logic."""
        # All OK
        checks = {"check1": {"status": "ok"}, "check2": {"status": "ok"}}
        self.assertEqual(determine_overall_status(checks), "ok")

        # One warning
        checks = {"check1": {"status": "ok"}, "check2": {"status": "warning"}}
        self.assertEqual(determine_overall_status(checks), "degraded")

        # One error
        checks = {"check1": {"status": "ok"}, "check2": {"status": "error"}}
        self.assertEqual(determine_overall_status(checks), "down")

        # Multiple errors and warnings (errors take precedence)
        checks = {
            "check1": {"status": "warning"},
            "check2": {"status": "error"},
            "check3": {"status": "warning"},
        }
        self.assertEqual(determine_overall_status(checks), "down")

    @patch("adapters.mt5_broker.MT5Broker")
    @patch("config.settings.get_settings")
    def test_check_mt5_connection_success(self, mock_get_settings, mock_broker_class):
        """Test successful MT5 connection check."""
        # Mock settings
        mock_settings = Mock()
        mock_get_settings.return_value = mock_settings

        # Mock broker
        mock_broker = Mock()
        mock_broker.is_connected.return_value = True
        mock_broker_class.return_value = mock_broker

        result = check_mt5_connection()

        self.assertTrue(result["mt5_connected"])
        self.assertEqual(result["status"], "ok")
        self.assertIn("MT5 connected", result["message"])

    @patch("adapters.mt5_broker.MT5Broker")
    @patch("config.settings.get_settings")
    def test_check_mt5_connection_failure(self, mock_get_settings, mock_broker_class):
        """Test failed MT5 connection check."""
        # Mock settings
        mock_settings = Mock()
        mock_get_settings.return_value = mock_settings

        # Mock broker
        mock_broker = Mock()
        mock_broker.is_connected.return_value = False
        mock_broker_class.return_value = mock_broker

        result = check_mt5_connection()

        self.assertFalse(result["mt5_connected"])
        self.assertEqual(result["status"], "error")
        self.assertIn("MT5 not connected", result["message"])

    @patch("adapters.mt5_broker.MT5Broker")
    def test_check_mt5_connection_exception(self, mock_broker_class):
        """Test MT5 connection check with exception."""
        # Mock broker to raise exception
        mock_broker_class.side_effect = Exception("Connection failed")

        result = check_mt5_connection()

        self.assertFalse(result["mt5_connected"])
        self.assertEqual(result["status"], "error")
        self.assertIn("Connection failed", result["message"])

    @patch("observability.health.sqlite3")
    @patch("observability.health.Path")
    def test_check_idempotency_db_success(self, mock_path, mock_sqlite):
        """Test successful database check."""
        # Mock path exists
        mock_path_instance = Mock()
        mock_path_instance.exists.return_value = True
        mock_path.return_value = mock_path_instance

        # Mock database connection
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_sqlite.connect.return_value = mock_conn

        result = check_idempotency_db()

        self.assertTrue(result["idempotency_db_ok"])
        self.assertEqual(result["status"], "ok")
        mock_cursor.execute.assert_called_once_with("SELECT 1")

    @patch("observability.health.Path")
    def test_check_idempotency_db_not_found(self, mock_path):
        """Test database check when file not found."""
        # Mock path doesn't exist
        mock_path_instance = Mock()
        mock_path_instance.exists.return_value = False
        mock_path.return_value = mock_path_instance

        result = check_idempotency_db()

        self.assertFalse(result["idempotency_db_ok"])
        self.assertEqual(result["status"], "warning")
        self.assertIn("not found", result["message"])

    @patch("observability.health.sqlite3")
    @patch("observability.health.Path")
    def test_check_idempotency_db_error(self, mock_path, mock_sqlite):
        """Test database check with connection error."""
        # Mock path exists
        mock_path_instance = Mock()
        mock_path_instance.exists.return_value = True
        mock_path.return_value = mock_path_instance

        # Mock database connection error
        mock_sqlite.connect.side_effect = Exception("Connection failed")

        result = check_idempotency_db()

        self.assertFalse(result["idempotency_db_ok"])
        self.assertEqual(result["status"], "error")
        self.assertIn("Connection failed", result["message"])

    @patch("observability.health.check_mt5_connection")
    @patch("observability.health.check_event_lag")
    @patch("observability.health.check_trading_activity")
    @patch("observability.health.check_idempotency_db")
    def test_check_health_complete(
        self, mock_db_check, mock_trading_check, mock_event_check, mock_mt5_check
    ):
        """Test complete health check with all components."""
        # Mock individual checks
        mock_mt5_check.return_value = {
            "mt5_connected": True,
            "status": "ok",
            "message": "MT5 connected",
        }

        mock_event_check.return_value = {
            "last_event_ts": "2025-09-08T12:00:00",
            "event_lag_sec": 5,
            "status": "ok",
            "message": "Event lag: 5s",
        }

        mock_trading_check.return_value = {
            "last_trade_ts": "2025-09-08T11:55:00",
            "positions_count": 1,
            "status": "ok",
            "message": "Trading activity: 1 positions",
        }

        mock_db_check.return_value = {
            "idempotency_db_ok": True,
            "status": "ok",
            "message": "Idempotency DB accessible",
        }

        result = check_health()

        # Check overall status
        self.assertEqual(result["status"], "ok")

        # Check individual check results are included
        self.assertTrue(result["mt5_connected"])
        self.assertEqual(result["event_lag_sec"], 5)
        self.assertEqual(result["positions_count"], 1)
        self.assertTrue(result["idempotency_db_ok"])

        # Check structured checks
        self.assertIn("checks", result)
        self.assertIn("mt5", result["checks"])
        self.assertIn("events", result["checks"])
        self.assertIn("trading", result["checks"])
        self.assertIn("database", result["checks"])

    @patch("observability.health.check_mt5_connection")
    @patch("observability.health.check_event_lag")
    @patch("observability.health.check_trading_activity")
    @patch("observability.health.check_idempotency_db")
    def test_check_health_degraded(
        self, mock_db_check, mock_trading_check, mock_event_check, mock_mt5_check
    ):
        """Test health check with degraded status."""
        # Mock checks with one warning
        mock_mt5_check.return_value = {
            "mt5_connected": True,
            "status": "ok",
            "message": "MT5 connected",
        }
        mock_event_check.return_value = {
            "last_event_ts": "2025-09-08T12:00:00",
            "event_lag_sec": 5,
            "status": "ok",
            "message": "Event lag: 5s",
        }
        mock_trading_check.return_value = {
            "last_trade_ts": "2025-09-08T11:55:00",
            "positions_count": 0,
            "status": "ok",
            "message": "No positions",
        }
        mock_db_check.return_value = {
            "idempotency_db_ok": False,
            "status": "warning",
            "message": "DB warning",
        }

        result = check_health()

        self.assertEqual(result["status"], "degraded")

    @patch("observability.health.check_mt5_connection")
    def test_check_health_exception(self, mock_mt5_check):
        """Test health check with exception handling."""
        # Mock check to raise exception
        mock_mt5_check.side_effect = Exception("Health check failed")

        result = check_health()

        self.assertEqual(result["status"], "error")
        self.assertIn("error", result)
        self.assertIn("Health check failed", result["error"])


if __name__ == "__main__":
    unittest.main()
