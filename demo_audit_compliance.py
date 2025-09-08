"""
Audit System Integration Demo (Prompt-31)
==========================================

Demonstrates the complete compliance and audit system in action.
Shows audit logging, configuration snapshots, and daily export functionality.
"""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path

from audit.audit_logger import (
    audit_auth,
    audit_config,
    audit_event,
    audit_fill,
    audit_order,
    get_audit_logger,
)
from audit.config_snapshot import create_config_snapshot, get_config_snapshotter
from scripts.export_audit_pack import AuditExporter


def demo_audit_logging():
    """Demonstrate audit logging capabilities."""
    print("🔍 Audit Logging Demonstration")
    print("=" * 50)

    # Get audit logger instance
    audit_logger = get_audit_logger()
    print(f"✅ Audit logger initialized, logging to: {audit_logger.log_dir}")

    # Demo various audit events
    print("\n📝 Logging various audit events...")

    # System startup
    audit_auth("Login", user="trading_system", source_ip="127.0.0.1")
    print("  ✅ System login event logged")

    # Configuration change
    audit_config(
        "risk_percentage",
        old_value=0.02,
        new_value=0.015,
        file_path="configs/risk.yaml",
    )
    print("  ✅ Configuration change logged")

    # Trading events
    audit_order("OrderAccepted", "EURUSD", "BUY", 0.1, price=1.1000, order_id="ORD001")
    print("  ✅ Order acceptance logged")

    time.sleep(0.1)  # Small delay to show different timestamps

    audit_fill("EURUSD", "BUY", 0.1, 1.1005, order_id="ORD001", deal_id="DEAL001")
    print("  ✅ Order fill logged")

    # Alert event
    audit_event(
        "AlertSent",
        alert_type="price_target",
        symbol="XAUUSD",
        message="Gold price reached target level",
        severity="HIGH",
    )
    print("  ✅ Alert event logged")

    # Stop loss update
    audit_event(
        "StopUpdated",
        symbol="GBPUSD",
        old_sl=1.2500,
        new_sl=1.2520,
        reason="trailing_stop",
        order_id="ORD002",
    )
    print("  ✅ Stop loss update logged")

    # Show current log file
    today_log = audit_logger.log_dir / f"audit-{time.strftime('%Y%m%d')}.jsonl"
    if today_log.exists():
        with open(today_log) as f:
            line_count = sum(1 for _ in f)
        print(f"\n📊 Current audit log: {today_log}")
        print(f"   Events logged today: {line_count}")

        # Show sample of recent events
        print("\n📄 Recent audit events:")
        with open(today_log) as f:
            lines = f.readlines()
            for line in lines[-3:]:  # Show last 3 events
                record = json.loads(line.strip())
                timestamp = datetime.fromisoformat(
                    record["iso_ts"].replace("Z", "+00:00")
                )
                print(
                    f"   {timestamp.strftime('%H:%M:%S')} - {record['event']} "
                    f"({record.get('category', 'general')})"
                )


def demo_config_snapshots():
    """Demonstrate configuration snapshot functionality."""
    print("\n\n📸 Configuration Snapshot Demonstration")
    print("=" * 50)

    # Create configuration snapshot
    print("Creating configuration snapshot...")
    snapshot = create_config_snapshot("demo_snapshot")

    print(f"✅ Snapshot created: {snapshot['snapshot_id']}")
    print(f"   Timestamp: {snapshot['timestamp']}")
    print(f"   Reason: {snapshot['reason']}")
    print(f"   Files captured: {snapshot['summary']['total_files']}")
    print(f"   Total size: {snapshot['summary']['total_size']} bytes")

    if snapshot["summary"]["changed_files"] > 0:
        print(f"   Changed files: {snapshot['summary']['changed_files']}")

    # Show some captured files
    print("\n📁 Captured configuration files:")
    for file_path, file_info in list(snapshot["files"].items())[:5]:  # Show first 5
        print(
            f"   {Path(file_path).name}: {file_info['size']} bytes, "
            f"hash: {file_info['hash'][:8]}..."
        )

    if len(snapshot["files"]) > 5:
        print(f"   ... and {len(snapshot['files']) - 5} more files")

    # Check for Git diffs
    if snapshot.get("diffs"):
        print("\n🔄 Configuration changes detected:")
        for file_path in snapshot["diffs"].keys():
            print(f"   Modified: {file_path}")
    else:
        print("\n✅ No configuration changes detected")


def demo_daily_export():
    """Demonstrate daily audit export functionality."""
    print("\n\n📦 Daily Export Demonstration")
    print("=" * 50)

    # Create exporter
    exporter = AuditExporter("demo_artifacts")

    print("Creating daily audit export package...")

    # Export for yesterday (since today might not have complete data)
    export_date = datetime.now() - timedelta(days=1)

    try:
        export_dir = exporter.export_daily_audit_pack(export_date, retention_days=30)

        print(f"✅ Export package created: {export_dir}")
        print(f"   Export date: {export_date.strftime('%Y-%m-%d')}")

        # List exported files
        exported_files = list(export_dir.glob("*"))
        print(f"   Files in package: {len(exported_files)}")

        for file_path in exported_files:
            if file_path.is_file():
                size = file_path.stat().st_size
                print(f"     {file_path.name}: {size} bytes")

        # Show manifest details if available
        manifest_file = export_dir / "manifest.json"
        if manifest_file.exists():
            with open(manifest_file) as f:
                manifest = json.load(f)

            print("\n📋 Integrity Manifest:")
            print(f"   Created: {manifest['created_at']}")
            print(f"   Total files: {manifest['summary']['total_files']}")
            print(f"   Total size: {manifest['summary']['total_size']} bytes")

            print("\n🔐 File integrity hashes:")
            for filename, file_info in manifest["files"].items():
                print(f"     {filename}: {file_info['sha256'][:16]}...")

    except Exception as e:
        print(f"⚠️  Export demo note: {e}")
        print("   (This is expected if no order database or audit logs exist)")


def demo_redaction_system():
    """Demonstrate sensitive data redaction."""
    print("\n\n🔒 Redaction System Demonstration")
    print("=" * 50)

    audit_logger = get_audit_logger()

    print("Logging sensitive data (will be automatically redacted)...")

    # Log events with sensitive information
    audit_event(
        "ConfigTest",
        database_password="super_secret_123",
        api_key="sk-1234567890abcdef",
        user_token="eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9",
        normal_data="this should remain visible",
    )

    # Check the log file to show redaction
    today_log = audit_logger.log_dir / f"audit-{time.strftime('%Y%m%d')}.jsonl"
    if today_log.exists():
        with open(today_log) as f:
            lines = f.readlines()
            last_line = lines[-1]

            print("✅ Raw log entry (with redaction applied):")
            print(f"   {last_line.strip()}")

            # Verify redaction worked
            if "[REDACTED]" in last_line:
                print("✅ Sensitive data successfully redacted")
            else:
                print("⚠️  Note: Redaction patterns may need adjustment")


def demo_audit_statistics():
    """Show audit system statistics."""
    print("\n\n📊 Audit System Statistics")
    print("=" * 50)

    # Count log files and events
    logs_dir = Path("logs")
    if logs_dir.exists():
        audit_files = list(logs_dir.glob("audit-*.jsonl"))

        print(f"📁 Audit log files: {len(audit_files)}")

        total_events = 0
        for log_file in audit_files:
            with open(log_file) as f:
                file_events = sum(1 for _ in f)
                total_events += file_events
                print(f"   {log_file.name}: {file_events} events")

        print(f"📈 Total audit events: {total_events}")

    # Count snapshots
    snapshotter = get_config_snapshotter()
    snapshot_files = list(snapshotter.snapshot_dir.glob("config_snapshot_*.json"))

    print(f"📸 Configuration snapshots: {len(snapshot_files)}")

    if snapshot_files:
        latest_snapshot = snapshotter.get_latest_snapshot()
        if latest_snapshot:
            print(f"   Latest snapshot: {latest_snapshot['snapshot_id']}")
            print(f"   Files tracked: {latest_snapshot['summary']['total_files']}")

    # Count export packages
    artifacts_dir = Path("artifacts")
    if artifacts_dir.exists():
        export_dirs = [
            d for d in artifacts_dir.iterdir() if d.is_dir() and len(d.name) == 10
        ]
        print(f"📦 Export packages: {len(export_dirs)}")

        for export_dir in sorted(export_dirs)[-3:]:  # Show last 3
            manifest_file = export_dir / "manifest.json"
            if manifest_file.exists():
                with open(manifest_file) as f:
                    manifest = json.load(f)
                print(
                    f"   {export_dir.name}: {manifest['summary']['total_files']} files"
                )


def main():
    """Main demonstration function."""
    print("🚀 Prompt-31 Compliance & Audit System Demo")
    print("=" * 60)
    print("Demonstrating immutable audit trails, configuration snapshots,")
    print("and automated daily export with integrity manifests.")
    print()

    try:
        # Run all demonstrations
        demo_audit_logging()
        demo_config_snapshots()
        demo_daily_export()
        demo_redaction_system()
        demo_audit_statistics()

        print("\n" + "=" * 60)
        print("✅ Compliance & Audit System Demo Complete!")
        print()
        print("🔍 Key Features Demonstrated:")
        print("   • Immutable append-only audit logging (JSONL)")
        print("   • Automatic sensitive data redaction")
        print("   • Configuration change snapshots with Git diffs")
        print("   • Daily export packages with integrity manifests")
        print("   • Automated retention policy management")
        print("   • Comprehensive event categorization")
        print()
        print("📁 Generated Artifacts:")
        print("   • logs/audit-YYYYMMDD.jsonl - Daily audit logs")
        print("   • audit/snapshots/ - Configuration snapshots")
        print("   • artifacts/YYYY-MM-DD/ - Daily export packages")
        print("   • manifest.json - File integrity hashes")

    except Exception as e:
        print(f"\n❌ Demo error: {e}")
        print("This may be expected if running without full system setup.")


if __name__ == "__main__":
    main()
