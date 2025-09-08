"""
Configuration Snapshot System (Prompt-31)
==========================================

Captures immutable snapshots of application configuration for audit and compliance.
Tracks configuration changes with Git diffs and integrity hashes.

Features:
- Configuration file hashing (SHA256)
- Git diff tracking for changes
- Snapshot on startup and configuration changes
- Integrity verification
- Version control integration
"""

import hashlib
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

from audit.audit_logger import audit_config


class ConfigSnapshotter:
    """
    Configuration snapshot system for compliance and audit requirements.
    
    Captures configuration state with hashes and Git diffs for immutable audit trail.
    """
    
    def __init__(self, config_dirs: Optional[List[str]] = None, 
                 snapshot_dir: str = "audit/snapshots"):
        """
        Initialize configuration snapshotter.
        
        Args:
            config_dirs: List of configuration directories to monitor
            snapshot_dir: Directory for storing snapshots
        """
        self.config_dirs = config_dirs or ["configs", "config"]
        self.snapshot_dir = Path(snapshot_dir)
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        
    def get_config_files(self) -> List[Path]:
        """
        Get list of all configuration files to snapshot.
        
        Returns:
            List of configuration file paths
        """
        config_files = []
        
        for config_dir in self.config_dirs:
            config_path = Path(config_dir)
            if config_path.exists():
                # Find YAML and Python config files
                config_files.extend(config_path.glob("**/*.yaml"))
                config_files.extend(config_path.glob("**/*.yml")) 
                config_files.extend(config_path.glob("**/*.json"))
                config_files.extend(config_path.glob("**/settings.py"))
                
        return sorted(config_files)
    
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
        except Exception as e:
            return f"ERROR: {str(e)}"
    
    def get_git_diff(self, file_path: Path) -> Optional[str]:
        """
        Get Git diff for a configuration file.
        
        Args:
            file_path: Path to file
            
        Returns:
            Git diff output or None if not available
        """
        try:
            # Check if we're in a Git repository
            result = subprocess.run(
                ["git", "status", "--porcelain", str(file_path)],
                capture_output=True,
                text=True,
                cwd=file_path.parent,
                timeout=10
            )
            
            if result.returncode != 0:
                return None
                
            # If file has changes, get the diff
            if result.stdout.strip():
                diff_result = subprocess.run(
                    ["git", "diff", str(file_path)],
                    capture_output=True, 
                    text=True,
                    cwd=file_path.parent,
                    timeout=10
                )
                
                if diff_result.returncode == 0:
                    return diff_result.stdout
                    
        except Exception:
            # Git operations failed, return None
            pass
            
        return None
    
    def create_snapshot(self, reason: str = "manual") -> Dict:
        """
        Create complete configuration snapshot.
        
        Args:
            reason: Reason for taking snapshot
            
        Returns:
            Snapshot metadata dictionary
        """
        timestamp = datetime.utcnow()
        snapshot_id = timestamp.strftime("%Y%m%d_%H%M%S")
        
        snapshot_data = {
            "snapshot_id": snapshot_id,
            "timestamp": timestamp.isoformat() + "Z",
            "reason": reason,
            "files": {},
            "diffs": {},
            "summary": {
                "total_files": 0,
                "changed_files": 0,
                "total_size": 0
            }
        }
        
        config_files = self.get_config_files()
        
        for file_path in config_files:
            if not file_path.exists():
                continue
                
            # Get file information
            file_stats = file_path.stat()
            file_hash = self.calculate_file_hash(file_path)
            
            # Store file metadata
            relative_path = str(file_path)
            snapshot_data["files"][relative_path] = {
                "size": file_stats.st_size,
                "modified": datetime.fromtimestamp(file_stats.st_mtime).isoformat() + "Z",
                "hash": file_hash
            }
            
            # Get Git diff if available
            git_diff = self.get_git_diff(file_path)
            if git_diff:
                snapshot_data["diffs"][relative_path] = git_diff
                snapshot_data["summary"]["changed_files"] += 1
            
            snapshot_data["summary"]["total_files"] += 1
            snapshot_data["summary"]["total_size"] += file_stats.st_size
        
        # Save snapshot to file
        snapshot_file = self.snapshot_dir / f"config_snapshot_{snapshot_id}.json"
        with open(snapshot_file, 'w', encoding='utf-8') as f:
            json.dump(snapshot_data, f, indent=2, ensure_ascii=False)
        
        # Write audit event
        audit_config(
            config_type="snapshot_created",
            snapshot_id=snapshot_id,
            reason=reason,
            total_files=snapshot_data["summary"]["total_files"],
            changed_files=snapshot_data["summary"]["changed_files"],
            file_path=str(snapshot_file)
        )
        
        return snapshot_data
    
    def compare_snapshots(self, snapshot1_id: str, snapshot2_id: str) -> Dict:
        """
        Compare two configuration snapshots.
        
        Args:
            snapshot1_id: First snapshot ID
            snapshot2_id: Second snapshot ID
            
        Returns:
            Comparison results dictionary
        """
        # Load snapshot files
        snapshot1_file = self.snapshot_dir / f"config_snapshot_{snapshot1_id}.json"
        snapshot2_file = self.snapshot_dir / f"config_snapshot_{snapshot2_id}.json"
        
        if not (snapshot1_file.exists() and snapshot2_file.exists()):
            return {"error": "One or both snapshots not found"}
        
        with open(snapshot1_file) as f:
            snapshot1 = json.load(f)
        with open(snapshot2_file) as f:
            snapshot2 = json.load(f)
        
        # Compare file hashes
        comparison = {
            "snapshot1_id": snapshot1_id,
            "snapshot2_id": snapshot2_id,
            "added_files": [],
            "removed_files": [],
            "modified_files": [],
            "unchanged_files": []
        }
        
        files1 = set(snapshot1["files"].keys())
        files2 = set(snapshot2["files"].keys())
        
        comparison["added_files"] = list(files2 - files1)
        comparison["removed_files"] = list(files1 - files2)
        
        # Check for modifications in common files
        common_files = files1.intersection(files2)
        for file_path in common_files:
            hash1 = snapshot1["files"][file_path]["hash"]
            hash2 = snapshot2["files"][file_path]["hash"]
            
            if hash1 != hash2:
                comparison["modified_files"].append(file_path)
            else:
                comparison["unchanged_files"].append(file_path)
        
        return comparison
    
    def get_latest_snapshot(self) -> Optional[Dict]:
        """
        Get the most recent configuration snapshot.
        
        Returns:
            Latest snapshot data or None if no snapshots exist
        """
        snapshot_files = list(self.snapshot_dir.glob("config_snapshot_*.json"))
        if not snapshot_files:
            return None
        
        # Sort by filename (which includes timestamp)
        latest_file = sorted(snapshot_files)[-1]
        
        with open(latest_file) as f:
            return json.load(f)


# Global snapshotter instance
_snapshotter = None


def get_config_snapshotter() -> ConfigSnapshotter:
    """
    Get singleton configuration snapshotter instance.
    
    Returns:
        ConfigSnapshotter instance
    """
    global _snapshotter
    if _snapshotter is None:
        _snapshotter = ConfigSnapshotter()
    return _snapshotter


def create_config_snapshot(reason: str = "manual") -> Dict:
    """
    Convenience function to create configuration snapshot.
    
    Args:
        reason: Reason for taking snapshot
        
    Returns:
        Snapshot metadata
    """
    return get_config_snapshotter().create_snapshot(reason)


def startup_snapshot() -> Dict:
    """
    Create startup configuration snapshot.
    
    Returns:
        Snapshot metadata
    """
    return create_config_snapshot("application_startup")
