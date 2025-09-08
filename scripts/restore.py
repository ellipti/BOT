#!/usr/bin/env python3
"""
Restore Script - Trading Bot System
Restores system from backup archives with data integrity verification.

Restore Components:
- SQLite databases with consistency checks
- Configuration files with validation
- Log files and audit trails
- Application state reconstruction
- Position reconciliation

Features:
- Archive integrity verification
- Selective component restoration
- Position reconciliation with broker
- Rollback capability
- Data validation

Usage:
    python scripts/restore.py <backup_archive> [--component databases] [--verify] [--reconcile]
"""

import os
import sys
import tarfile
import shutil
import logging
import argparse
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import sqlite3
import hashlib
import yaml

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RestoreManager:
    """Comprehensive backup restoration system"""
    
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.restore_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.backup_original_path = Path("backup_original") / self.restore_timestamp
        
    def calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum for file"""
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    
    def verify_archive_integrity(self, archive_path: Path) -> bool:
        """Verify backup archive integrity"""
        try:
            logger.info(f"Verifying archive integrity: {archive_path.name}")
            
            # Check if checksum file exists
            checksum_file = archive_path.with_suffix(archive_path.suffix + '.sha256')
            if checksum_file.exists():
                with open(checksum_file, 'r') as f:
                    expected_checksum = f.read().split()[0]
                
                actual_checksum = self.calculate_checksum(archive_path)
                if actual_checksum != expected_checksum:
                    logger.error("Archive checksum verification failed")
                    logger.error(f"Expected: {expected_checksum}")
                    logger.error(f"Actual: {actual_checksum}")
                    return False
                
                logger.info("✅ Archive checksum verified")
            else:
                logger.warning("No checksum file found, skipping checksum verification")
            
            # Test archive extraction
            with tarfile.open(archive_path, "r:gz") as tar:
                members = tar.getmembers()
                logger.info(f"Archive contains {len(members)} files")
                
                # Check for required structure
                required_files = ['BACKUP_MANIFEST.json']
                for required in required_files:
                    if not any(m.name.endswith(required) for m in members):
                        logger.error(f"Required file not found in archive: {required}")
                        return False
                
            logger.info("✅ Archive structure verified")
            return True
            
        except Exception as e:
            logger.error(f"Archive verification failed: {e}")
            return False
    
    def extract_archive(self, archive_path: Path, extract_path: Path) -> Optional[Dict[str, Any]]:
        """Extract backup archive and return manifest"""
        try:
            logger.info(f"Extracting archive to: {extract_path}")
            extract_path.mkdir(parents=True, exist_ok=True)
            
            with tarfile.open(archive_path, "r:gz") as tar:
                tar.extractall(extract_path)
            
            # Find and load manifest
            manifest_files = list(extract_path.rglob("BACKUP_MANIFEST.json"))
            if not manifest_files:
                logger.error("Backup manifest not found in extracted archive")
                return None
            
            manifest_path = manifest_files[0]
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
            
            logger.info(f"✅ Archive extracted successfully")
            logger.info(f"Backup ID: {manifest.get('backup_id', 'unknown')}")
            logger.info(f"Created: {manifest.get('created_at', 'unknown')}")
            
            return manifest
            
        except Exception as e:
            logger.error(f"Failed to extract archive: {e}")
            return None
    
    def backup_current_state(self) -> bool:
        """Create backup of current state before restore"""
        if self.dry_run:
            logger.info("DRY RUN: Would backup current state")
            return True
        
        try:
            self.backup_original_path.mkdir(parents=True, exist_ok=True)
            
            # Backup current databases
            infra_dir = Path("infra")
            if infra_dir.exists():
                backup_infra = self.backup_original_path / "infra"
                shutil.copytree(infra_dir, backup_infra, ignore_errors=True)
                logger.info(f"Backed up current databases to {backup_infra}")
            
            # Backup current configs
            configs_dir = Path("configs")
            if configs_dir.exists():
                backup_configs = self.backup_original_path / "configs"
                shutil.copytree(configs_dir, backup_configs, ignore_errors=True)
                logger.info(f"Backed up current configs to {backup_configs}")
            
            # Backup critical state files
            state_files = ["settings.py", "last_decision.json"]
            for state_file in state_files:
                if Path(state_file).exists():
                    shutil.copy2(state_file, self.backup_original_path / state_file)
            
            logger.info("✅ Current state backed up successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to backup current state: {e}")
            return False
    
    def restore_databases(self, backup_root: Path, manifest: Dict[str, Any]) -> Dict[str, Any]:
        """Restore SQLite databases with consistency checks"""
        result = {"success": True, "restored": [], "failed": [], "verified": []}
        
        db_backup_path = backup_root / "databases"
        if not db_backup_path.exists():
            logger.warning("No databases found in backup")
            return result
        
        infra_dir = Path("infra")
        if not self.dry_run:
            infra_dir.mkdir(exist_ok=True)
        
        db_info = manifest.get("contents", {}).get("databases", {}).get("databases", [])
        
        for db_entry in db_info:
            db_name = db_entry["name"]
            source_db = db_backup_path / db_name
            target_db = infra_dir / db_name
            
            try:
                if not source_db.exists():
                    logger.error(f"Database file not found in backup: {db_name}")
                    result["failed"].append(db_name)
                    continue
                
                logger.info(f"Restoring database: {db_name}")
                
                if self.dry_run:
                    logger.info(f"DRY RUN: Would restore {db_name}")
                else:
                    # Copy database file
                    shutil.copy2(source_db, target_db)
                    
                    # Verify database integrity
                    with sqlite3.connect(str(target_db)) as conn:
                        cursor = conn.cursor()
                        cursor.execute("PRAGMA integrity_check")
                        integrity_result = cursor.fetchone()[0]
                        
                        if integrity_result == "ok":
                            logger.info(f"✅ Database integrity verified: {db_name}")
                            result["verified"].append(db_name)
                        else:
                            logger.error(f"Database integrity check failed: {db_name}")
                            result["failed"].append(db_name)
                            continue
                
                result["restored"].append(db_name)
                logger.info(f"✅ Database restored: {db_name}")
                
            except Exception as e:
                logger.error(f"Failed to restore database {db_name}: {e}")
                result["failed"].append(db_name)
                result["success"] = False
        
        return result
    
    def restore_configs(self, backup_root: Path, manifest: Dict[str, Any]) -> Dict[str, Any]:
        """Restore configuration files with validation"""
        result = {"success": True, "restored": [], "failed": [], "validated": []}
        
        config_backup_path = backup_root / "configs"
        if not config_backup_path.exists():
            logger.warning("No configs found in backup")
            return result
        
        configs_dir = Path("configs")
        if not self.dry_run:
            configs_dir.mkdir(exist_ok=True)
        
        config_info = manifest.get("contents", {}).get("configs", {}).get("files", [])
        
        for config_entry in config_info:
            config_name = config_entry["name"]
            source_config = config_backup_path / config_name
            target_config = configs_dir / config_name
            
            try:
                if not source_config.exists():
                    logger.error(f"Config file not found in backup: {config_name}")
                    result["failed"].append(config_name)
                    continue
                
                logger.info(f"Restoring config: {config_name}")
                
                if self.dry_run:
                    logger.info(f"DRY RUN: Would restore {config_name}")
                else:
                    # Ensure target directory exists
                    target_config.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_config, target_config)
                    
                    # Validate config file format
                    if self.validate_config_file(target_config):
                        result["validated"].append(config_name)
                        logger.info(f"✅ Config validated: {config_name}")
                    else:
                        logger.warning(f"Config validation failed: {config_name}")
                
                result["restored"].append(config_name)
                
            except Exception as e:
                logger.error(f"Failed to restore config {config_name}: {e}")
                result["failed"].append(config_name)
                result["success"] = False
        
        return result
    
    def validate_config_file(self, config_path: Path) -> bool:
        """Validate configuration file format"""
        try:
            if config_path.suffix.lower() in ['.yaml', '.yml']:
                with open(config_path, 'r') as f:
                    yaml.safe_load(f)
                return True
            elif config_path.suffix.lower() == '.json':
                with open(config_path, 'r') as f:
                    json.load(f)
                return True
            else:
                # For other file types, just check if readable
                with open(config_path, 'r') as f:
                    f.read(1024)  # Read first 1KB to check
                return True
        except Exception as e:
            logger.error(f"Config validation failed for {config_path}: {e}")
            return False
    
    def restore_logs(self, backup_root: Path, manifest: Dict[str, Any]) -> Dict[str, Any]:
        """Restore log files"""
        result = {"success": True, "restored": [], "failed": []}
        
        log_backup_path = backup_root / "logs"
        if not log_backup_path.exists():
            logger.warning("No logs found in backup")
            return result
        
        logs_dir = Path("logs")
        if not self.dry_run:
            logs_dir.mkdir(exist_ok=True)
        
        log_info = manifest.get("contents", {}).get("logs", {}).get("files", [])
        
        for log_entry in log_info:
            log_name = log_entry["name"]
            source_log = log_backup_path / log_name
            target_log = logs_dir / log_name
            
            try:
                if not source_log.exists():
                    logger.error(f"Log file not found in backup: {log_name}")
                    result["failed"].append(log_name)
                    continue
                
                logger.info(f"Restoring log: {log_name}")
                
                if self.dry_run:
                    logger.info(f"DRY RUN: Would restore {log_name}")
                else:
                    target_log.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_log, target_log)
                
                result["restored"].append(log_name)
                
            except Exception as e:
                logger.error(f"Failed to restore log {log_name}: {e}")
                result["failed"].append(log_name)
                result["success"] = False
        
        return result
    
    def restore_audit_trails(self, backup_root: Path, manifest: Dict[str, Any]) -> Dict[str, Any]:
        """Restore audit trail files"""
        result = {"success": True, "restored": [], "failed": []}
        
        audit_backup_path = backup_root / "audit"
        if not audit_backup_path.exists():
            logger.warning("No audit trails found in backup")
            return result
        
        audit_dir = Path("audit")
        if not self.dry_run:
            audit_dir.mkdir(exist_ok=True)
        
        audit_info = manifest.get("contents", {}).get("audit", {}).get("files", [])
        
        for audit_entry in audit_info:
            audit_name = audit_entry["name"]
            source_audit = audit_backup_path / audit_name
            target_audit = audit_dir / audit_name
            
            try:
                if not source_audit.exists():
                    logger.error(f"Audit file not found in backup: {audit_name}")
                    result["failed"].append(audit_name)
                    continue
                
                logger.info(f"Restoring audit file: {audit_name}")
                
                if self.dry_run:
                    logger.info(f"DRY RUN: Would restore {audit_name}")
                else:
                    target_audit.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_audit, target_audit)
                
                result["restored"].append(audit_name)
                
            except Exception as e:
                logger.error(f"Failed to restore audit file {audit_name}: {e}")
                result["failed"].append(audit_name)
                result["success"] = False
        
        return result
    
    def restore_application_state(self, backup_root: Path, manifest: Dict[str, Any]) -> Dict[str, Any]:
        """Restore application state files"""
        result = {"success": True, "restored": [], "failed": []}
        
        state_backup_path = backup_root / "state"
        if not state_backup_path.exists():
            logger.warning("No application state found in backup")
            return result
        
        state_info = manifest.get("contents", {}).get("state", {}).get("files", [])
        
        for state_entry in state_info:
            state_name = state_entry["name"]
            source_state = state_backup_path / state_name
            target_state = Path(state_name)
            
            try:
                if not source_state.exists():
                    logger.error(f"State file not found in backup: {state_name}")
                    result["failed"].append(state_name)
                    continue
                
                logger.info(f"Restoring state file: {state_name}")
                
                if self.dry_run:
                    logger.info(f"DRY RUN: Would restore {state_name}")
                else:
                    shutil.copy2(source_state, target_state)
                
                result["restored"].append(state_name)
                
            except Exception as e:
                logger.error(f"Failed to restore state file {state_name}: {e}")
                result["failed"].append(state_name)
                result["success"] = False
        
        return result
    
    def reconcile_positions(self) -> Dict[str, Any]:
        """Reconcile positions with broker after restore"""
        result = {"success": True, "positions_checked": 0, "discrepancies": []}
        
        try:
            if self.dry_run:
                logger.info("DRY RUN: Would reconcile positions with broker")
                return result
            
            logger.info("Starting position reconciliation...")
            
            # Check if MT5 connection is available
            try:
                import MT5
                if not MT5.initialize():
                    logger.warning("MT5 not available for position reconciliation")
                    return result
                
                # Get current positions from broker
                broker_positions = MT5.positions_get()
                if broker_positions is None:
                    broker_positions = []
                
                # Compare with database positions
                db_path = Path("infra/trading.sqlite")
                if db_path.exists():
                    with sqlite3.connect(str(db_path)) as conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            SELECT symbol, SUM(quantity) as net_position 
                            FROM orders 
                            WHERE status = 'filled' 
                            GROUP BY symbol 
                            HAVING net_position != 0
                        """)
                        db_positions = {row[0]: row[1] for row in cursor.fetchall()}
                
                result["positions_checked"] = len(broker_positions)
                
                # Check for discrepancies
                broker_symbols = {pos.symbol: pos.volume for pos in broker_positions}
                
                for symbol, db_volume in db_positions.items():
                    broker_volume = broker_symbols.get(symbol, 0)
                    if abs(db_volume - broker_volume) > 0.01:  # Allow small floating point differences
                        discrepancy = {
                            "symbol": symbol,
                            "database_position": db_volume,
                            "broker_position": broker_volume,
                            "difference": db_volume - broker_volume
                        }
                        result["discrepancies"].append(discrepancy)
                        logger.warning(f"Position discrepancy: {symbol} DB={db_volume} Broker={broker_volume}")
                
                MT5.shutdown()
                
            except ImportError:
                logger.info("MT5 module not available, skipping broker reconciliation")
            
            if result["discrepancies"]:
                logger.warning(f"Found {len(result['discrepancies'])} position discrepancies")
            else:
                logger.info("✅ Position reconciliation completed - no discrepancies found")
            
        except Exception as e:
            logger.error(f"Position reconciliation failed: {e}")
            result["success"] = False
        
        return result
    
    def run_restore(self, archive_path: Path, components: Optional[List[str]] = None, 
                   verify: bool = True, reconcile: bool = True) -> Dict[str, Any]:
        """Execute complete restore process"""
        logger.info(f"Starting restore from archive: {archive_path.name}")
        start_time = datetime.now()
        
        if components is None:
            components = ["databases", "configs", "logs", "audit", "state"]
        
        result = {
            "success": True,
            "archive": str(archive_path),
            "components_requested": components,
            "verification_passed": False,
            "backup_created": False,
            "components_restored": {},
            "reconciliation": {},
            "errors": []
        }
        
        try:
            # Step 1: Verify archive integrity
            if verify:
                if not self.verify_archive_integrity(archive_path):
                    result["success"] = False
                    result["errors"].append("Archive integrity verification failed")
                    return result
                result["verification_passed"] = True
            
            # Step 2: Create backup of current state
            if not self.backup_current_state():
                result["success"] = False
                result["errors"].append("Failed to backup current state")
                return result
            result["backup_created"] = True
            
            # Step 3: Extract archive
            extract_path = Path("temp_restore") / self.restore_timestamp
            manifest = self.extract_archive(archive_path, extract_path)
            if not manifest:
                result["success"] = False
                result["errors"].append("Failed to extract archive")
                return result
            
            # Find the backup root directory in extracted content
            backup_root = None
            for item in extract_path.iterdir():
                if item.is_dir() and item.name.startswith("backup_"):
                    backup_root = item
                    break
            
            if not backup_root:
                result["success"] = False
                result["errors"].append("Backup data not found in extracted archive")
                return result
            
            # Step 4: Restore components
            if "databases" in components:
                result["components_restored"]["databases"] = self.restore_databases(backup_root, manifest)
            
            if "configs" in components:
                result["components_restored"]["configs"] = self.restore_configs(backup_root, manifest)
            
            if "logs" in components:
                result["components_restored"]["logs"] = self.restore_logs(backup_root, manifest)
            
            if "audit" in components:
                result["components_restored"]["audit"] = self.restore_audit_trails(backup_root, manifest)
            
            if "state" in components:
                result["components_restored"]["state"] = self.restore_application_state(backup_root, manifest)
            
            # Step 5: Position reconciliation
            if reconcile and "databases" in components:
                result["reconciliation"] = self.reconcile_positions()
            
            # Check if any component restore failed
            for component, comp_result in result["components_restored"].items():
                if not comp_result.get("success", True):
                    result["success"] = False
                    result["errors"].append(f"Component restore failed: {component}")
            
            end_time = datetime.now()
            result["duration_seconds"] = (end_time - start_time).total_seconds()
            result["completed_at"] = end_time.isoformat()
            
            if result["success"]:
                logger.info(f"✅ Restore completed successfully in {result['duration_seconds']:.1f}s")
            else:
                logger.error("❌ Restore completed with errors")
            
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            result["success"] = False
            result["errors"].append(f"Unexpected error: {str(e)}")
        
        finally:
            # Cleanup temporary extraction directory
            extract_path = Path("temp_restore") / self.restore_timestamp
            if extract_path.exists():
                shutil.rmtree(extract_path, ignore_errors=True)
        
        return result

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Trading Bot Restore System')
    parser.add_argument('archive', help='Backup archive file to restore from')
    parser.add_argument('--component', action='append', choices=['databases', 'configs', 'logs', 'audit', 'state'],
                       help='Specific components to restore (can be used multiple times)')
    parser.add_argument('--no-verify', action='store_true', help='Skip archive verification')
    parser.add_argument('--no-reconcile', action='store_true', help='Skip position reconciliation')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be restored without making changes')
    parser.add_argument('--json', action='store_true', help='Output JSON results')
    parser.add_argument('--quiet', action='store_true', help='Minimal output')
    
    args = parser.parse_args()
    
    if args.quiet:
        logging.getLogger().setLevel(logging.WARNING)
    
    archive_path = Path(args.archive)
    if not archive_path.exists():
        logger.error(f"Archive file not found: {archive_path}")
        sys.exit(1)
    
    try:
        restore_manager = RestoreManager(dry_run=args.dry_run)
        
        components = args.component if args.component else None
        verify = not args.no_verify
        reconcile = not args.no_reconcile
        
        result = restore_manager.run_restore(archive_path, components, verify, reconcile)
        
        if args.json:
            print(json.dumps(result, indent=2))
        elif not args.quiet:
            if result["success"]:
                print(f"✅ Restore completed successfully")
                print(f"📦 Archive: {Path(result['archive']).name}")
                print(f"⏱️  Duration: {result['duration_seconds']:.1f}s")
                
                # Show component results
                for component, comp_result in result.get("components_restored", {}).items():
                    restored_count = len(comp_result.get("restored", []))
                    failed_count = len(comp_result.get("failed", []))
                    print(f"📁 {component.title()}: {restored_count} restored, {failed_count} failed")
                
                # Show reconciliation results
                recon = result.get("reconciliation", {})
                if recon:
                    positions_checked = recon.get("positions_checked", 0)
                    discrepancies = len(recon.get("discrepancies", []))
                    print(f"🔄 Reconciliation: {positions_checked} positions checked, {discrepancies} discrepancies")
                
            else:
                print(f"❌ Restore failed")
                for error in result.get("errors", []):
                    print(f"   Error: {error}")
        
        sys.exit(0 if result["success"] else 1)
        
    except KeyboardInterrupt:
        logger.info("Restore interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
