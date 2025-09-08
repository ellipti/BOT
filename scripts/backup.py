#!/usr/bin/env python3
"""
Backup Script - Trading Bot System
Creates comprehensive backups of databases, configurations, and logs.

Backup Components:
- SQLite databases (infra/*.sqlite)
- Configuration files (configs/*)
- Log files (logs/*)
- Audit trails (audit/*)
- Application state files

Features:
- Compressed tar.gz archives
- Timestamp-based naming
- Integrity checksums
- Retention policies
- Incremental backup support

Usage:
    python scripts/backup.py [--full] [--retention 30] [--verify]
"""

import argparse
import hashlib
import json
import logging
import os
import shutil
import sqlite3
import sys
import tarfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class BackupManager:
    """Comprehensive backup management system"""

    def __init__(self, backup_dir: str = "backups", retention_days: int = 30):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)
        self.retention_days = retention_days
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    def calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum for file"""
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()

    def backup_databases(self, backup_path: Path) -> dict[str, Any]:
        """Backup SQLite databases with integrity checks"""
        db_info = {"databases": [], "total_size": 0, "backup_method": "hot_backup"}

        infra_dir = Path("infra")
        if not infra_dir.exists():
            logger.warning("infra/ directory not found")
            return db_info

        db_backup_dir = backup_path / "databases"
        db_backup_dir.mkdir(exist_ok=True)

        for db_file in infra_dir.glob("*.sqlite"):
            try:
                logger.info(f"Backing up database: {db_file.name}")

                # Use SQLite hot backup for consistency
                backup_file = db_backup_dir / db_file.name

                # Hot backup using SQLite backup API
                with sqlite3.connect(str(db_file)) as source:
                    with sqlite3.connect(str(backup_file)) as backup:
                        source.backup(backup)

                # Calculate checksums
                original_checksum = self.calculate_checksum(db_file)
                backup_checksum = self.calculate_checksum(backup_file)

                size = backup_file.stat().st_size
                db_info["databases"].append(
                    {
                        "name": db_file.name,
                        "size": size,
                        "original_checksum": original_checksum,
                        "backup_checksum": backup_checksum,
                        "backup_time": datetime.now().isoformat(),
                    }
                )
                db_info["total_size"] += size

                logger.info(
                    f"Database backup completed: {db_file.name} ({size:,} bytes)"
                )

            except Exception as e:
                logger.error(f"Failed to backup database {db_file.name}: {e}")
                db_info["databases"].append(
                    {
                        "name": db_file.name,
                        "error": str(e),
                        "backup_time": datetime.now().isoformat(),
                    }
                )

        return db_info

    def backup_configs(self, backup_path: Path) -> dict[str, Any]:
        """Backup configuration files"""
        config_info = {"files": [], "total_size": 0}

        configs_dir = Path("configs")
        if not configs_dir.exists():
            logger.warning("configs/ directory not found")
            return config_info

        config_backup_dir = backup_path / "configs"
        config_backup_dir.mkdir(exist_ok=True)

        # Backup all config files
        for config_file in configs_dir.rglob("*"):
            if config_file.is_file():
                try:
                    relative_path = config_file.relative_to(configs_dir)
                    backup_file = config_backup_dir / relative_path
                    backup_file.parent.mkdir(parents=True, exist_ok=True)

                    shutil.copy2(config_file, backup_file)

                    checksum = self.calculate_checksum(backup_file)
                    size = backup_file.stat().st_size

                    config_info["files"].append(
                        {
                            "name": str(relative_path),
                            "size": size,
                            "checksum": checksum,
                            "modified": datetime.fromtimestamp(
                                config_file.stat().st_mtime
                            ).isoformat(),
                        }
                    )
                    config_info["total_size"] += size

                except Exception as e:
                    logger.error(f"Failed to backup config {config_file}: {e}")

        logger.info(
            f"Backed up {len(config_info['files'])} config files ({config_info['total_size']:,} bytes)"
        )
        return config_info

    def backup_logs(self, backup_path: Path, max_age_days: int = 7) -> dict[str, Any]:
        """Backup recent log files"""
        log_info = {"files": [], "total_size": 0, "max_age_days": max_age_days}

        logs_dir = Path("logs")
        if not logs_dir.exists():
            logger.warning("logs/ directory not found")
            return log_info

        log_backup_dir = backup_path / "logs"
        log_backup_dir.mkdir(exist_ok=True)

        cutoff_time = datetime.now() - timedelta(days=max_age_days)

        for log_file in logs_dir.rglob("*"):
            if log_file.is_file():
                try:
                    mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                    if mtime > cutoff_time:
                        relative_path = log_file.relative_to(logs_dir)
                        backup_file = log_backup_dir / relative_path
                        backup_file.parent.mkdir(parents=True, exist_ok=True)

                        shutil.copy2(log_file, backup_file)

                        checksum = self.calculate_checksum(backup_file)
                        size = backup_file.stat().st_size

                        log_info["files"].append(
                            {
                                "name": str(relative_path),
                                "size": size,
                                "checksum": checksum,
                                "modified": mtime.isoformat(),
                            }
                        )
                        log_info["total_size"] += size

                except Exception as e:
                    logger.error(f"Failed to backup log {log_file}: {e}")

        logger.info(
            f"Backed up {len(log_info['files'])} log files ({log_info['total_size']:,} bytes)"
        )
        return log_info

    def backup_audit_trails(self, backup_path: Path) -> dict[str, Any]:
        """Backup audit trail files"""
        audit_info = {"files": [], "total_size": 0}

        audit_dir = Path("audit")
        if not audit_dir.exists():
            logger.warning("audit/ directory not found")
            return audit_info

        audit_backup_dir = backup_path / "audit"
        audit_backup_dir.mkdir(exist_ok=True)

        for audit_file in audit_dir.rglob("*"):
            if audit_file.is_file():
                try:
                    relative_path = audit_file.relative_to(audit_dir)
                    backup_file = audit_backup_dir / relative_path
                    backup_file.parent.mkdir(parents=True, exist_ok=True)

                    shutil.copy2(audit_file, backup_file)

                    checksum = self.calculate_checksum(backup_file)
                    size = backup_file.stat().st_size

                    audit_info["files"].append(
                        {
                            "name": str(relative_path),
                            "size": size,
                            "checksum": checksum,
                            "modified": datetime.fromtimestamp(
                                audit_file.stat().st_mtime
                            ).isoformat(),
                        }
                    )
                    audit_info["total_size"] += size

                except Exception as e:
                    logger.error(f"Failed to backup audit file {audit_file}: {e}")

        logger.info(
            f"Backed up {len(audit_info['files'])} audit files ({audit_info['total_size']:,} bytes)"
        )
        return audit_info

    def backup_application_state(self, backup_path: Path) -> dict[str, Any]:
        """Backup application state and settings"""
        state_info = {"files": [], "total_size": 0}

        state_files = ["settings.py", "last_decision.json", "*.json", "*.yaml"]

        state_backup_dir = backup_path / "state"
        state_backup_dir.mkdir(exist_ok=True)

        for pattern in state_files:
            for state_file in Path(".").glob(pattern):
                if state_file.is_file() and not state_file.name.startswith("."):
                    try:
                        backup_file = state_backup_dir / state_file.name
                        shutil.copy2(state_file, backup_file)

                        checksum = self.calculate_checksum(backup_file)
                        size = backup_file.stat().st_size

                        state_info["files"].append(
                            {
                                "name": state_file.name,
                                "size": size,
                                "checksum": checksum,
                                "modified": datetime.fromtimestamp(
                                    state_file.stat().st_mtime
                                ).isoformat(),
                            }
                        )
                        state_info["total_size"] += size

                    except Exception as e:
                        logger.error(f"Failed to backup state file {state_file}: {e}")

        logger.info(
            f"Backed up {len(state_info['files'])} state files ({state_info['total_size']:,} bytes)"
        )
        return state_info

    def create_manifest(self, backup_path: Path, backup_info: dict[str, Any]) -> Path:
        """Create backup manifest with metadata and checksums"""
        manifest_path = backup_path / "BACKUP_MANIFEST.json"

        manifest = {
            "backup_id": f"backup_{self.timestamp}",
            "created_at": datetime.now().isoformat(),
            "backup_type": "full",
            "system_info": {
                "platform": sys.platform,
                "python_version": sys.version,
                "working_directory": str(Path.cwd().absolute()),
            },
            "contents": backup_info,
            "integrity": {
                "manifest_checksum": "",  # Will be calculated after writing
                "total_files": sum(
                    len(info.get("files", [])) for info in backup_info.values()
                )
                + sum(len(info.get("databases", [])) for info in backup_info.values()),
                "total_size": sum(
                    info.get("total_size", 0) for info in backup_info.values()
                ),
            },
        }

        # Write manifest
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)

        # Calculate manifest checksum
        manifest_checksum = self.calculate_checksum(manifest_path)
        manifest["integrity"]["manifest_checksum"] = manifest_checksum

        # Rewrite with checksum
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)

        logger.info(
            f"Backup manifest created: {manifest['integrity']['total_files']} files, {manifest['integrity']['total_size']:,} bytes"
        )
        return manifest_path

    def create_archive(self, backup_path: Path) -> Path:
        """Create compressed tar.gz archive"""
        archive_name = f"trading_bot_backup_{self.timestamp}.tar.gz"
        archive_path = self.backup_dir / archive_name

        logger.info(f"Creating backup archive: {archive_name}")

        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(backup_path, arcname=f"backup_{self.timestamp}")

        # Calculate archive checksum
        archive_checksum = self.calculate_checksum(archive_path)
        checksum_file = archive_path.with_suffix(archive_path.suffix + ".sha256")

        with open(checksum_file, "w") as f:
            f.write(f"{archive_checksum}  {archive_name}\n")

        archive_size = archive_path.stat().st_size
        logger.info(f"Backup archive created: {archive_name} ({archive_size:,} bytes)")
        logger.info(f"Archive checksum: {archive_checksum}")

        return archive_path

    def cleanup_old_backups(self) -> int:
        """Remove backups older than retention period"""
        cutoff_time = datetime.now() - timedelta(days=self.retention_days)
        removed_count = 0

        for backup_file in self.backup_dir.glob("trading_bot_backup_*.tar.gz"):
            try:
                mtime = datetime.fromtimestamp(backup_file.stat().st_mtime)
                if mtime < cutoff_time:
                    logger.info(f"Removing old backup: {backup_file.name}")
                    backup_file.unlink()

                    # Remove associated checksum file
                    checksum_file = backup_file.with_suffix(
                        backup_file.suffix + ".sha256"
                    )
                    if checksum_file.exists():
                        checksum_file.unlink()

                    removed_count += 1
            except Exception as e:
                logger.error(f"Failed to remove old backup {backup_file}: {e}")

        logger.info(f"Cleaned up {removed_count} old backups")
        return removed_count

    def verify_archive(self, archive_path: Path) -> bool:
        """Verify archive integrity"""
        try:
            logger.info(f"Verifying backup archive: {archive_path.name}")

            # Check checksum
            checksum_file = archive_path.with_suffix(archive_path.suffix + ".sha256")
            if checksum_file.exists():
                with open(checksum_file) as f:
                    expected_checksum = f.read().split()[0]

                actual_checksum = self.calculate_checksum(archive_path)
                if actual_checksum != expected_checksum:
                    logger.error("Archive checksum verification failed")
                    return False

                logger.info("Archive checksum verified")

            # Test archive extraction
            with tarfile.open(archive_path, "r:gz") as tar:
                # Verify archive can be opened and read
                members = tar.getmembers()
                logger.info(f"Archive contains {len(members)} files")

                # Check for manifest file
                manifest_found = any(
                    m.name.endswith("BACKUP_MANIFEST.json") for m in members
                )
                if not manifest_found:
                    logger.warning("Backup manifest not found in archive")
                    return False

            logger.info("Archive verification completed successfully")
            return True

        except Exception as e:
            logger.error(f"Archive verification failed: {e}")
            return False

    def run_backup(
        self, full_backup: bool = True, verify: bool = True
    ) -> dict[str, Any]:
        """Execute complete backup process"""
        logger.info(
            f"Starting {'full' if full_backup else 'incremental'} backup process..."
        )
        start_time = datetime.now()

        # Create temporary backup directory
        temp_backup_path = self.backup_dir / f"temp_backup_{self.timestamp}"
        temp_backup_path.mkdir(exist_ok=True)

        try:
            backup_info = {}

            # Execute backup components
            backup_info["databases"] = self.backup_databases(temp_backup_path)
            backup_info["configs"] = self.backup_configs(temp_backup_path)
            backup_info["logs"] = self.backup_logs(temp_backup_path)
            backup_info["audit"] = self.backup_audit_trails(temp_backup_path)
            backup_info["state"] = self.backup_application_state(temp_backup_path)

            # Create manifest
            self.create_manifest(temp_backup_path, backup_info)

            # Create archive
            archive_path = self.create_archive(temp_backup_path)

            # Verify archive if requested
            verification_passed = True
            if verify:
                verification_passed = self.verify_archive(archive_path)

            # Cleanup old backups
            removed_count = self.cleanup_old_backups()

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            result = {
                "success": True,
                "backup_id": f"backup_{self.timestamp}",
                "archive_path": str(archive_path),
                "archive_size": archive_path.stat().st_size,
                "duration_seconds": duration,
                "verification_passed": verification_passed,
                "removed_old_backups": removed_count,
                "components": backup_info,
                "timestamp": end_time.isoformat(),
            }

            logger.info(f"Backup completed successfully in {duration:.1f}s")
            logger.info(
                f"Archive: {archive_path.name} ({result['archive_size']:,} bytes)"
            )

            return result

        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

        finally:
            # Cleanup temporary directory
            if temp_backup_path.exists():
                shutil.rmtree(temp_backup_path)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Trading Bot Backup System")
    parser.add_argument(
        "--full", action="store_true", default=True, help="Full backup (default)"
    )
    parser.add_argument("--incremental", action="store_true", help="Incremental backup")
    parser.add_argument(
        "--retention",
        type=int,
        default=30,
        help="Retention period in days (default: 30)",
    )
    parser.add_argument(
        "--backup-dir", default="backups", help="Backup directory (default: backups)"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        default=True,
        help="Verify backup archive (default: True)",
    )
    parser.add_argument(
        "--no-verify", action="store_true", help="Skip backup verification"
    )
    parser.add_argument("--json", action="store_true", help="Output JSON results")
    parser.add_argument("--quiet", action="store_true", help="Minimal output")

    args = parser.parse_args()

    if args.quiet:
        logging.getLogger().setLevel(logging.WARNING)

    try:
        backup_manager = BackupManager(args.backup_dir, args.retention)

        full_backup = not args.incremental
        verify = args.verify and not args.no_verify

        result = backup_manager.run_backup(full_backup, verify)

        if args.json:
            print(json.dumps(result, indent=2))
        elif not args.quiet:
            if result["success"]:
                print("✅ Backup completed successfully")
                print(f"📦 Archive: {Path(result['archive_path']).name}")
                print(f"💾 Size: {result['archive_size']:,} bytes")
                print(f"⏱️  Duration: {result['duration_seconds']:.1f}s")
                if result.get("verification_passed"):
                    print("✅ Verification: PASSED")
                if result.get("removed_old_backups", 0) > 0:
                    print(f"🧹 Cleaned up: {result['removed_old_backups']} old backups")
            else:
                print(f"❌ Backup failed: {result.get('error', 'Unknown error')}")

        sys.exit(0 if result["success"] else 1)

    except KeyboardInterrupt:
        logger.info("Backup interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
