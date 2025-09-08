"""
Daily Audit Export Script (Prompt-31)
======================================

Automated daily export of audit data for compliance and regulatory requirements.
Creates comprehensive audit packages with integrity manifests.

Exports:
- Orders and fills (CSV format)
- Audit logs (filtered JSONL)
- Configuration snapshots
- Integrity manifests with SHA256 hashes
- Retention policy enforcement

Usage:
    python scripts/export_audit_pack.py [--date YYYY-MM-DD] [--output-dir DIR]
"""

import argparse
import csv
import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from audit.audit_logger import get_audit_logger
from audit.config_snapshot import get_config_snapshotter


class AuditExporter:
    """
    Daily audit data exporter with integrity manifests and retention management.
    """
    
    def __init__(self, output_base_dir: str = "artifacts"):
        """
        Initialize audit exporter.
        
        Args:
            output_base_dir: Base directory for export artifacts
        """
        self.output_base_dir = Path(output_base_dir)
        self.output_base_dir.mkdir(parents=True, exist_ok=True)
        
    def create_export_directory(self, export_date: datetime) -> Path:
        """
        Create date-specific export directory.
        
        Args:
            export_date: Date for export
            
        Returns:
            Path to export directory
        """
        date_str = export_date.strftime("%Y-%m-%d")
        export_dir = self.output_base_dir / date_str
        export_dir.mkdir(parents=True, exist_ok=True)
        return export_dir
    
    def export_orders_csv(self, export_dir: Path, export_date: datetime) -> Optional[Path]:
        """
        Export orders data to CSV format.
        
        Args:
            export_dir: Export directory
            export_date: Date for export
            
        Returns:
            Path to orders CSV file or None if no data
        """
        orders_file = export_dir / "orders.csv"
        
        # Try to connect to order book database
        order_db_paths = ["demo_order_book.db", "order_book.db", "orders.db"]
        db_path = None
        
        for path in order_db_paths:
            if Path(path).exists():
                db_path = path
                break
        
        if not db_path:
            print(f"Warning: No order database found, skipping orders export")
            return None
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Query orders for the export date
            date_start = export_date.strftime("%Y-%m-%d 00:00:00")
            date_end = export_date.strftime("%Y-%m-%d 23:59:59")
            
            cursor.execute("""
                SELECT id, symbol, side, quantity, price, order_type, status, 
                       created_at, updated_at, client_order_id
                FROM orders 
                WHERE created_at BETWEEN ? AND ?
                ORDER BY created_at
            """, (date_start, date_end))
            
            rows = cursor.fetchall()
            
            if not rows:
                conn.close()
                return None
            
            # Write CSV file
            with open(orders_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'id', 'symbol', 'side', 'quantity', 'price', 'order_type', 
                    'status', 'created_at', 'updated_at', 'client_order_id'
                ])
                writer.writerows(rows)
            
            conn.close()
            print(f"Exported {len(rows)} orders to {orders_file}")
            return orders_file
            
        except Exception as e:
            print(f"Error exporting orders: {e}")
            return None
    
    def export_fills_csv(self, export_dir: Path, export_date: datetime) -> Optional[Path]:
        """
        Export fills/trades data to CSV format.
        
        Args:
            export_dir: Export directory
            export_date: Date for export
            
        Returns:
            Path to fills CSV file or None if no data
        """
        fills_file = export_dir / "fills.csv"
        
        # Try to connect to order book database
        order_db_paths = ["demo_order_book.db", "order_book.db", "orders.db"]
        db_path = None
        
        for path in order_db_paths:
            if Path(path).exists():
                db_path = path
                break
        
        if not db_path:
            print(f"Warning: No order database found, skipping fills export")
            return None
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Query fills for the export date
            date_start = export_date.strftime("%Y-%m-%d 00:00:00")
            date_end = export_date.strftime("%Y-%m-%d 23:59:59")
            
            cursor.execute("""
                SELECT id, order_id, symbol, side, quantity, price, 
                       commission, fill_time, deal_id, broker_id
                FROM fills 
                WHERE fill_time BETWEEN ? AND ?
                ORDER BY fill_time
            """, (date_start, date_end))
            
            rows = cursor.fetchall()
            
            if not rows:
                conn.close()
                return None
            
            # Write CSV file
            with open(fills_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'id', 'order_id', 'symbol', 'side', 'quantity', 'price',
                    'commission', 'fill_time', 'deal_id', 'broker_id'
                ])
                writer.writerows(rows)
            
            conn.close()
            print(f"Exported {len(rows)} fills to {fills_file}")
            return fills_file
            
        except Exception as e:
            print(f"Error exporting fills: {e}")
            return None
    
    def export_audit_logs(self, export_dir: Path, export_date: datetime) -> Optional[Path]:
        """
        Export filtered audit logs for the date.
        
        Args:
            export_dir: Export directory
            export_date: Date for export
            
        Returns:
            Path to audit logs file or None if no data
        """
        # Look for audit log file
        date_str = export_date.strftime("%Y%m%d")
        audit_log_path = Path(f"logs/audit-{date_str}.jsonl")
        
        if not audit_log_path.exists():
            print(f"Warning: No audit log found for {date_str}")
            return None
        
        alerts_file = export_dir / "alerts.jsonl"
        exported_count = 0
        
        try:
            with open(audit_log_path, 'r', encoding='utf-8') as infile:
                with open(alerts_file, 'w', encoding='utf-8') as outfile:
                    for line in infile:
                        try:
                            record = json.loads(line.strip())
                            
                            # Filter for alert-related events and significant trading events
                            if record.get("event") in [
                                "AlertSent", "OrderAccepted", "PartiallyFilled", 
                                "Filled", "Rejected", "StopUpdated", "Login", "ConfigChanged"
                            ]:
                                outfile.write(line)
                                exported_count += 1
                                
                        except json.JSONDecodeError:
                            # Skip malformed lines
                            continue
            
            if exported_count == 0:
                # Remove empty file
                alerts_file.unlink()
                return None
            
            print(f"Exported {exported_count} audit events to {alerts_file}")
            return alerts_file
            
        except Exception as e:
            print(f"Error exporting audit logs: {e}")
            return None
    
    def export_config_snapshot(self, export_dir: Path) -> Optional[Path]:
        """
        Export latest configuration snapshot.
        
        Args:
            export_dir: Export directory
            
        Returns:
            Path to config snapshot file or None if not available
        """
        snapshotter = get_config_snapshotter()
        latest_snapshot = snapshotter.get_latest_snapshot()
        
        if not latest_snapshot:
            print("Warning: No configuration snapshots available")
            return None
        
        # Copy snapshot to export directory
        snapshot_file = export_dir / "config_snapshot.json"
        with open(snapshot_file, 'w', encoding='utf-8') as f:
            json.dump(latest_snapshot, f, indent=2, ensure_ascii=False)
        
        # Also copy any diffs if available
        if latest_snapshot.get("diffs"):
            diff_file = export_dir / "config.diff"
            with open(diff_file, 'w', encoding='utf-8') as f:
                for file_path, diff_content in latest_snapshot["diffs"].items():
                    f.write(f"=== {file_path} ===\n")
                    f.write(diff_content)
                    f.write("\n\n")
        
        print(f"Exported configuration snapshot to {snapshot_file}")
        return snapshot_file
    
    def calculate_file_hash(self, file_path: Path) -> str:
        """
        Calculate SHA256 hash of a file.
        
        Args:
            file_path: Path to file
            
        Returns:
            SHA256 hash as hex string
        """
        try:
            with open(file_path, 'rb') as f:
                file_hash = hashlib.sha256()
                while chunk := f.read(8192):
                    file_hash.update(chunk)
                return file_hash.hexdigest()
        except Exception:
            return "ERROR"
    
    def create_manifest(self, export_dir: Path, exported_files: List[Path]) -> Path:
        """
        Create integrity manifest for exported files.
        
        Args:
            export_dir: Export directory
            exported_files: List of exported file paths
            
        Returns:
            Path to manifest file
        """
        manifest_file = export_dir / "manifest.json"
        manifest_data = {
            "created_at": datetime.utcnow().isoformat() + "Z",
            "export_date": export_dir.name,
            "files": {},
            "summary": {
                "total_files": len(exported_files),
                "total_size": 0
            }
        }
        
        for file_path in exported_files:
            if file_path and file_path.exists():
                file_stats = file_path.stat()
                file_hash = self.calculate_file_hash(file_path)
                
                manifest_data["files"][file_path.name] = {
                    "size": file_stats.st_size,
                    "sha256": file_hash,
                    "modified": datetime.fromtimestamp(file_stats.st_mtime).isoformat() + "Z"
                }
                
                manifest_data["summary"]["total_size"] += file_stats.st_size
        
        # Write manifest file
        with open(manifest_file, 'w', encoding='utf-8') as f:
            json.dump(manifest_data, f, indent=2, ensure_ascii=False)
        
        print(f"Created integrity manifest: {manifest_file}")
        return manifest_file
    
    def apply_retention_policy(self, retention_days: int = 90) -> None:
        """
        Apply retention policy to old export directories.
        
        Args:
            retention_days: Number of days to retain exports
        """
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        removed_count = 0
        
        for export_dir in self.output_base_dir.iterdir():
            if not export_dir.is_dir():
                continue
            
            try:
                # Parse directory name as date
                dir_date = datetime.strptime(export_dir.name, "%Y-%m-%d")
                
                if dir_date < cutoff_date:
                    # Remove old export directory
                    import shutil
                    shutil.rmtree(export_dir)
                    removed_count += 1
                    print(f"Removed old export directory: {export_dir}")
                    
            except ValueError:
                # Skip directories that don't match date format
                continue
        
        if removed_count > 0:
            print(f"Applied retention policy: removed {removed_count} old exports")
        else:
            print("Retention policy: no old exports to remove")
    
    def export_daily_audit_pack(self, export_date: Optional[datetime] = None,
                               retention_days: int = 90) -> Path:
        """
        Create complete daily audit export package.
        
        Args:
            export_date: Date to export (defaults to yesterday)
            retention_days: Retention period in days
            
        Returns:
            Path to export directory
        """
        if export_date is None:
            export_date = datetime.now() - timedelta(days=1)
        
        print(f"Creating audit export package for {export_date.strftime('%Y-%m-%d')}")
        
        # Create export directory
        export_dir = self.create_export_directory(export_date)
        exported_files = []
        
        # Export orders
        orders_file = self.export_orders_csv(export_dir, export_date)
        if orders_file:
            exported_files.append(orders_file)
        
        # Export fills
        fills_file = self.export_fills_csv(export_dir, export_date)
        if fills_file:
            exported_files.append(fills_file)
        
        # Export audit logs
        alerts_file = self.export_audit_logs(export_dir, export_date)
        if alerts_file:
            exported_files.append(alerts_file)
        
        # Export config snapshot
        config_file = self.export_config_snapshot(export_dir)
        if config_file:
            exported_files.append(config_file)
        
        # Check for config diff file
        diff_file = export_dir / "config.diff"
        if diff_file.exists():
            exported_files.append(diff_file)
        
        # Create integrity manifest
        manifest_file = self.create_manifest(export_dir, exported_files)
        exported_files.append(manifest_file)
        
        # Apply retention policy
        self.apply_retention_policy(retention_days)
        
        print(f"✅ Audit export package complete: {export_dir}")
        print(f"   Files: {len(exported_files)}")
        
        return export_dir


def main():
    """Main entry point for audit export script."""
    parser = argparse.ArgumentParser(description="Export daily audit pack")
    parser.add_argument(
        "--date", 
        help="Export date in YYYY-MM-DD format (defaults to yesterday)"
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts",
        help="Output directory for exports (default: artifacts)"
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=90,
        help="Retention period in days (default: 90)"
    )
    
    args = parser.parse_args()
    
    # Parse export date
    if args.date:
        try:
            export_date = datetime.strptime(args.date, "%Y-%m-%d")
        except ValueError:
            print("Error: Invalid date format. Use YYYY-MM-DD")
            sys.exit(1)
    else:
        export_date = datetime.now() - timedelta(days=1)
    
    # Create exporter and run export
    exporter = AuditExporter(args.output_dir)
    try:
        export_dir = exporter.export_daily_audit_pack(export_date, args.retention_days)
        print(f"Success: Audit pack exported to {export_dir}")
    except Exception as e:
        print(f"Error: Export failed - {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
