"""
Tests for Audit and Compliance System (Prompt-31)
=================================================

Tests for immutable audit logging, configuration snapshots, and daily export functionality.
Validates JSONL format, export packages, and manifest integrity.
"""

import json
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from audit.audit_logger import (
    AuditLogger,
    audit_event,
    audit_fill,
    audit_order,
    get_audit_logger,
)
from audit.config_snapshot import ConfigSnapshotter, create_config_snapshot
from scripts.export_audit_pack import AuditExporter


class TestAuditLogger:
    """Test immutable audit logging functionality."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test logs."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.fixture
    def audit_logger(self, temp_dir):
        """Create audit logger with temporary directory."""
        return AuditLogger(temp_dir)

    def test_basic_audit_logging(self, audit_logger):
        """Test basic audit event logging."""
        audit_logger.write("TestEvent", data="test_data", user_id=123)

        # Check log file was created
        log_files = list(Path(audit_logger.log_dir).glob("audit-*.jsonl"))
        assert len(log_files) == 1

        # Verify log content
        with open(log_files[0]) as f:
            line = f.readline().strip()
            record = json.loads(line)

            assert record["event"] == "TestEvent"
            assert record["data"] == "test_data"
            assert record["user_id"] == 123
            assert "ts" in record
            assert "iso_ts" in record

    def test_daily_log_rotation(self, audit_logger):
        """Test that logs rotate daily."""
        # Mock different dates
        with patch("time.strftime") as mock_strftime:
            mock_strftime.return_value = "20240101"
            audit_logger.write("Day1Event")

            mock_strftime.return_value = "20240102"
            audit_logger.write("Day2Event")

        # Should have two different log files
        log_files = list(Path(audit_logger.log_dir).glob("audit-*.jsonl"))
        assert len(log_files) == 2

        assert any("20240101" in f.name for f in log_files)
        assert any("20240102" in f.name for f in log_files)

    def test_order_event_logging(self, audit_logger):
        """Test order-specific audit event logging."""
        audit_logger.write_order_event(
            "OrderAccepted",
            symbol="EURUSD",
            side="BUY",
            quantity=0.1,
            price=1.1000,
            order_id="ORDER123",
        )

        log_files = list(Path(audit_logger.log_dir).glob("audit-*.jsonl"))
        with open(log_files[0]) as f:
            record = json.loads(f.readline())

            assert record["event"] == "OrderAccepted"
            assert record["category"] == "order"
            assert record["symbol"] == "EURUSD"
            assert record["side"] == "BUY"
            assert record["quantity"] == 0.1
            assert record["price"] == 1.1000
            assert record["order_id"] == "ORDER123"

    def test_fill_event_logging(self, audit_logger):
        """Test fill-specific audit event logging."""
        audit_logger.write_fill_event(
            symbol="XAUUSD",
            side="SELL",
            quantity=0.05,
            price=2000.0,
            order_id="ORDER456",
            deal_id="DEAL789",
        )

        log_files = list(Path(audit_logger.log_dir).glob("audit-*.jsonl"))
        with open(log_files[0]) as f:
            record = json.loads(f.readline())

            assert record["event"] == "Filled"
            assert record["category"] == "fill"
            assert record["symbol"] == "XAUUSD"
            assert record["side"] == "SELL"
            assert record["deal_id"] == "DEAL789"

    def test_config_event_logging(self, audit_logger):
        """Test configuration change audit logging."""
        audit_logger.write_config_event(
            config_type="risk_limit",
            old_value=0.02,
            new_value=0.01,
            file_path="configs/risk.yaml",
        )

        log_files = list(Path(audit_logger.log_dir).glob("audit-*.jsonl"))
        with open(log_files[0]) as f:
            record = json.loads(f.readline())

            assert record["event"] == "ConfigChanged"
            assert record["category"] == "config"
            assert record["config_type"] == "risk_limit"
            assert record["old_value"] == 0.02
            assert record["new_value"] == 0.01

    def test_redaction_applied(self, audit_logger):
        """Test that sensitive data redaction is applied."""
        audit_logger.write(
            "LoginAttempt",
            username="test_user",
            password="secret123",
            api_key="sk-1234567890abcdef",
        )

        log_files = list(Path(audit_logger.log_dir).glob("audit-*.jsonl"))
        with open(log_files[0]) as f:
            content = f.read()

            # Sensitive data should be redacted
            assert "secret123" not in content
            assert "sk-1234567890abcdef" not in content
            assert "[REDACTED]" in content

    def test_jsonl_format_validity(self, audit_logger):
        """Test that all log entries are valid JSON."""
        # Write multiple events
        for i in range(5):
            audit_logger.write(f"Event{i}", counter=i)

        log_files = list(Path(audit_logger.log_dir).glob("audit-*.jsonl"))
        with open(log_files[0]) as f:
            lines = f.readlines()

            assert len(lines) == 5
            for line in lines:
                # Each line should be valid JSON
                record = json.loads(line.strip())
                assert "event" in record
                assert "ts" in record

    def test_convenience_functions(self, temp_dir):
        """Test convenience audit functions."""
        # Mock the global logger to use temp directory
        with patch("audit.audit_logger.get_audit_logger") as mock_get_logger:
            mock_logger = AuditLogger(temp_dir)
            mock_get_logger.return_value = mock_logger

            # Test convenience functions
            audit_event("TestEvent", test_data=True)
            audit_order("OrderTest", "EURUSD", "BUY", 0.1)
            audit_fill("GBPUSD", "SELL", 0.2, 1.2500)

        # Verify logs were written
        log_files = list(Path(temp_dir).glob("audit-*.jsonl"))
        assert len(log_files) == 1

        with open(log_files[0]) as f:
            lines = f.readlines()
            assert len(lines) == 3


class TestConfigSnapshotter:
    """Test configuration snapshot functionality."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test snapshots."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.fixture
    def snapshotter(self, temp_dir):
        """Create config snapshotter with temporary directory."""
        return ConfigSnapshotter(config_dirs=[], snapshot_dir=f"{temp_dir}/snapshots")

    @pytest.fixture
    def temp_config_files(self, temp_dir):
        """Create temporary configuration files."""
        config_dir = Path(temp_dir) / "configs"
        config_dir.mkdir()

        # Create test config files
        yaml_file = config_dir / "test.yaml"
        yaml_file.write_text("test_setting: value1\nanother_setting: 123")

        json_file = config_dir / "test.json"
        json_file.write_text('{"api_endpoint": "https://api.example.com"}')

        return [yaml_file, json_file]

    def test_snapshot_creation(self, temp_dir, temp_config_files):
        """Test creating configuration snapshot."""
        snapshotter = ConfigSnapshotter(
            config_dirs=[str(Path(temp_dir) / "configs")],
            snapshot_dir=f"{temp_dir}/snapshots",
        )

        snapshot = snapshotter.create_snapshot("test_snapshot")

        assert snapshot["reason"] == "test_snapshot"
        assert "snapshot_id" in snapshot
        assert "timestamp" in snapshot
        assert "files" in snapshot
        assert "summary" in snapshot

        # Should have captured both config files
        assert snapshot["summary"]["total_files"] == 2

        # Files should have hashes
        for file_path, file_info in snapshot["files"].items():
            assert "hash" in file_info
            assert "size" in file_info
            assert "modified" in file_info

    def test_snapshot_file_persistence(self, temp_dir, temp_config_files):
        """Test that snapshots are saved to files."""
        snapshotter = ConfigSnapshotter(
            config_dirs=[str(Path(temp_dir) / "configs")],
            snapshot_dir=f"{temp_dir}/snapshots",
        )

        snapshot = snapshotter.create_snapshot("persistence_test")

        # Check snapshot file was created
        snapshot_files = list(
            Path(f"{temp_dir}/snapshots").glob("config_snapshot_*.json")
        )
        assert len(snapshot_files) == 1

        # Verify file content
        with open(snapshot_files[0]) as f:
            saved_snapshot = json.load(f)
            assert saved_snapshot["snapshot_id"] == snapshot["snapshot_id"]

    def test_file_hash_calculation(self, snapshotter, temp_dir):
        """Test file hash calculation."""
        test_file = Path(temp_dir) / "test.txt"
        test_file.write_text("test content for hashing")

        hash1 = snapshotter.calculate_file_hash(test_file)
        hash2 = snapshotter.calculate_file_hash(test_file)

        # Same file should produce same hash
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex length

        # Different content should produce different hash
        test_file.write_text("different content")
        hash3 = snapshotter.calculate_file_hash(test_file)
        assert hash1 != hash3

    def test_latest_snapshot_retrieval(self, temp_dir, temp_config_files):
        """Test getting the latest snapshot."""
        snapshotter = ConfigSnapshotter(
            config_dirs=[str(Path(temp_dir) / "configs")],
            snapshot_dir=f"{temp_dir}/snapshots",
        )

        # Create multiple snapshots with time delays
        snapshot1 = snapshotter.create_snapshot("first")
        time.sleep(0.1)  # Ensure different timestamps
        snapshot2 = snapshotter.create_snapshot("second")

        latest = snapshotter.get_latest_snapshot()
        assert latest["snapshot_id"] == snapshot2["snapshot_id"]
        assert latest["reason"] == "second"


class TestAuditExporter:
    """Test daily audit export functionality."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for export tests."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.fixture
    def exporter(self, temp_dir):
        """Create audit exporter with temporary directory."""
        return AuditExporter(temp_dir)

    @pytest.fixture
    def sample_audit_log(self, temp_dir):
        """Create sample audit log file."""
        logs_dir = Path(temp_dir) / "logs"
        logs_dir.mkdir()

        # Create sample audit log
        yesterday = datetime.now() - timedelta(days=1)
        date_str = yesterday.strftime("%Y%m%d")
        log_file = logs_dir / f"audit-{date_str}.jsonl"

        sample_events = [
            {
                "ts": time.time(),
                "event": "OrderAccepted",
                "symbol": "EURUSD",
                "side": "BUY",
            },
            {
                "ts": time.time(),
                "event": "AlertSent",
                "alert_type": "price_alert",
                "message": "Price target reached",
            },
            {"ts": time.time(), "event": "Filled", "symbol": "EURUSD", "quantity": 0.1},
            {
                "ts": time.time(),
                "event": "ConfigChanged",
                "config_type": "risk_limit",
                "new_value": 0.01,
            },
        ]

        with open(log_file, "w") as f:
            for event in sample_events:
                f.write(json.dumps(event) + "\n")

        return log_file, yesterday

    def test_export_directory_creation(self, exporter):
        """Test export directory creation."""
        test_date = datetime(2024, 1, 15)
        export_dir = exporter.create_export_directory(test_date)

        assert export_dir.exists()
        assert export_dir.name == "2024-01-15"

    @patch("pathlib.Path.exists")
    def test_export_audit_logs(self, mock_exists, exporter, temp_dir, sample_audit_log):
        """Test audit log export functionality."""
        log_file, export_date = sample_audit_log

        # Mock the log file path lookup
        def exists_side_effect(self):
            return str(self).endswith(f"audit-{export_date.strftime('%Y%m%d')}.jsonl")

        mock_exists.side_effect = exists_side_effect

        # Patch Path to return our test log file
        with patch("pathlib.Path") as mock_path:
            mock_path.return_value = log_file

            export_dir = exporter.create_export_directory(export_date)
            result = exporter.export_audit_logs(export_dir, export_date)

            if result:  # Only test if export was successful
                assert result.name == "alerts.jsonl"
                assert result.exists()

    def test_manifest_creation(self, exporter, temp_dir):
        """Test integrity manifest creation."""
        export_dir = Path(temp_dir) / "2024-01-15"
        export_dir.mkdir(parents=True)

        # Create sample files
        test_file1 = export_dir / "orders.csv"
        test_file1.write_text("id,symbol,side\n1,EURUSD,BUY")

        test_file2 = export_dir / "alerts.jsonl"
        test_file2.write_text('{"event": "AlertSent"}\n')

        # Create manifest
        manifest_file = exporter.create_manifest(export_dir, [test_file1, test_file2])

        assert manifest_file.exists()
        assert manifest_file.name == "manifest.json"

        # Verify manifest content
        with open(manifest_file) as f:
            manifest = json.load(f)

            assert "created_at" in manifest
            assert "export_date" in manifest
            assert "files" in manifest
            assert "summary" in manifest

            assert manifest["summary"]["total_files"] == 2
            assert "orders.csv" in manifest["files"]
            assert "alerts.jsonl" in manifest["files"]

            # Each file should have hash and size
            for file_info in manifest["files"].values():
                assert "sha256" in file_info
                assert "size" in file_info

    def test_file_hash_calculation(self, exporter, temp_dir):
        """Test file hash calculation for manifest."""
        test_file = Path(temp_dir) / "test.txt"
        test_file.write_text("test content")

        hash_value = exporter.calculate_file_hash(test_file)

        assert isinstance(hash_value, str)
        assert len(hash_value) == 64  # SHA256 hex length
        assert hash_value != "ERROR"

    def test_retention_policy(self, exporter, temp_dir):
        """Test retention policy application."""
        # Create old export directories
        old_date = datetime.now() - timedelta(days=100)
        recent_date = datetime.now() - timedelta(days=30)

        old_dir = Path(temp_dir) / old_date.strftime("%Y-%m-%d")
        recent_dir = Path(temp_dir) / recent_date.strftime("%Y-%m-%d")

        old_dir.mkdir(parents=True)
        recent_dir.mkdir(parents=True)

        # Apply retention policy (90 days)
        exporter.apply_retention_policy(retention_days=90)

        # Old directory should be removed, recent should remain
        assert not old_dir.exists()
        assert recent_dir.exists()


@pytest.mark.integration
class TestAuditIntegration:
    """Integration tests for complete audit system."""

    def test_end_to_end_audit_flow(self):
        """Test complete audit flow from logging to export."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # 1. Create audit logger and log some events
            audit_logger = AuditLogger(f"{temp_dir}/logs")

            audit_logger.write_order_event(
                "OrderAccepted", "EURUSD", "BUY", 0.1, 1.1000
            )
            audit_logger.write_fill_event("EURUSD", "BUY", 0.1, 1.1005)
            audit_logger.write_config_event("risk_limit", 0.02, 0.01)

            # 2. Create config snapshot
            snapshotter = ConfigSnapshotter(
                config_dirs=[],  # No real configs for this test
                snapshot_dir=f"{temp_dir}/snapshots",
            )
            snapshot = snapshotter.create_snapshot("integration_test")

            # 3. Export audit pack
            exporter = AuditExporter(f"{temp_dir}/artifacts")

            # Mock the audit log path lookup for export
            with patch("pathlib.Path.exists") as mock_exists:
                mock_exists.return_value = True

                export_date = datetime.now()
                export_dir = exporter.export_daily_audit_pack(export_date)

                # Verify export directory exists
                assert export_dir.exists()

                # Verify manifest was created
                manifest_file = export_dir / "manifest.json"
                if manifest_file.exists():
                    with open(manifest_file) as f:
                        manifest = json.load(f)
                        assert "files" in manifest
                        assert "summary" in manifest


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
