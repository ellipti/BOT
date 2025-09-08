#!/usr/bin/env python3
"""
Experiment Assignment Module

Deterministic A/B assignment based on symbol + hour bucket + user salt.
Ensures consistent assignment while allowing for traffic control.
"""

import hashlib
import logging
import time
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

import yaml

from config.settings import get_settings

logger = logging.getLogger(__name__)


class ExperimentAssigner:
    """Handles deterministic A/B experiment assignment"""
    
    def __init__(self, config_path: str = "configs/experiments.yaml"):
        self.config_path = config_path
        self.config = self._load_config()
        self._assignment_cache = {}
        
    def _load_config(self) -> Dict:
        """Load experiment configuration from YAML"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            logger.info(f"Loaded experiment config: {config.get('name', 'unknown')}")
            return config
        except Exception as e:
            logger.error(f"Failed to load experiment config: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict:
        """Default config when file loading fails"""
        return {
            "active": False,
            "name": "default",
            "arms": {"A": {"weight": 100, "strategy_id": "strat_v1A"}},
            "assignment": {"salt": "default_salt", "bucket_hours": 1}
        }
    
    def reload_config(self) -> None:
        """Reload configuration (for dynamic updates)"""
        old_name = self.config.get('name', 'unknown')
        self.config = self._load_config()
        new_name = self.config.get('name', 'unknown')
        
        if old_name != new_name:
            self._assignment_cache.clear()
            logger.info(f"Experiment config reloaded: {old_name} → {new_name}")
    
    def is_active(self) -> bool:
        """Check if experiment is currently active"""
        return self.config.get("active", False)
    
    def get_experiment_name(self) -> str:
        """Get current experiment name"""
        return self.config.get("name", "none")
    
    def assign_arm(self, symbol: str, user_id: Optional[str] = None) -> Tuple[str, Dict]:
        """
        Assign experiment arm using deterministic hash
        
        Args:
            symbol: Trading symbol (e.g., "XAUUSD")
            user_id: Optional user identifier
            
        Returns:
            Tuple of (arm_name, arm_config)
        """
        if not self.is_active():
            # Return default arm A when experiment is inactive
            default_arm = list(self.config["arms"].keys())[0]
            return default_arm, self.config["arms"][default_arm]
        
        # Check for forced assignment (testing override)
        force_arm = self.config.get("assignment", {}).get("force_arm")
        if force_arm and force_arm in self.config["arms"]:
            logger.debug(f"Using forced assignment: {force_arm}")
            return force_arm, self.config["arms"][force_arm]
        
        # Generate cache key
        hour_bucket = self._get_hour_bucket()
        cache_key = f"{symbol}:{hour_bucket}:{user_id or 'default'}"
        
        # Check cache first
        if cache_key in self._assignment_cache:
            arm_name = self._assignment_cache[cache_key]
            return arm_name, self.config["arms"][arm_name]
        
        # Generate deterministic assignment
        arm_name = self._hash_assign(symbol, hour_bucket, user_id)
        
        # Cache the assignment
        self._assignment_cache[cache_key] = arm_name
        
        logger.debug(f"Assigned {symbol} to arm {arm_name} (bucket: {hour_bucket})")
        return arm_name, self.config["arms"][arm_name]
    
    def _get_hour_bucket(self) -> int:
        """Get current hour bucket for assignment stability"""
        bucket_hours = self.config.get("assignment", {}).get("bucket_hours", 1)
        current_hour = datetime.now(timezone.utc).hour
        return current_hour // bucket_hours
    
    def _hash_assign(self, symbol: str, hour_bucket: int, user_id: Optional[str]) -> str:
        """Generate deterministic assignment using hash"""
        # Create hash input
        salt = self.config.get("assignment", {}).get("salt", "default_salt")
        hash_input = f"{symbol}:{hour_bucket}:{user_id or 'default'}:{salt}"
        
        # Generate hash
        hash_obj = hashlib.md5(hash_input.encode('utf-8'))
        hash_int = int(hash_obj.hexdigest(), 16)
        
        # Convert to percentage (0-99)
        hash_pct = hash_int % 100
        
        # Assign based on weights
        arms = self.config["arms"]
        cumulative_weight = 0
        
        for arm_name, arm_config in arms.items():
            weight = arm_config.get("weight", 0)
            cumulative_weight += weight
            
            if hash_pct < cumulative_weight:
                return arm_name
        
        # Fallback to first arm
        return list(arms.keys())[0]
    
    def get_assignment_stats(self) -> Dict:
        """Get current assignment statistics"""
        if not self.is_active():
            return {"active": False, "assignments": 0}
        
        # Count assignments by arm
        arm_counts = {}
        for assignment in self._assignment_cache.values():
            arm_counts[assignment] = arm_counts.get(assignment, 0) + 1
        
        total_assignments = len(self._assignment_cache)
        
        # Calculate percentages
        arm_percentages = {}
        if total_assignments > 0:
            for arm, count in arm_counts.items():
                arm_percentages[arm] = (count / total_assignments) * 100
        
        return {
            "active": True,
            "experiment": self.get_experiment_name(),
            "total_assignments": total_assignments,
            "arm_counts": arm_counts,
            "arm_percentages": arm_percentages,
            "cache_size": len(self._assignment_cache)
        }
    
    def clear_cache(self) -> None:
        """Clear assignment cache (force reassignment)"""
        cache_size = len(self._assignment_cache)
        self._assignment_cache.clear()
        logger.info(f"Cleared assignment cache ({cache_size} entries)")


# Global assigner instance
_assigner: Optional[ExperimentAssigner] = None


def get_assigner() -> ExperimentAssigner:
    """Get global experiment assigner instance"""
    global _assigner
    if _assigner is None:
        _assigner = ExperimentAssigner()
    return _assigner


def assign_arm(symbol: str, user_id: Optional[str] = None) -> Tuple[str, Dict]:
    """
    Convenience function for arm assignment
    
    Args:
        symbol: Trading symbol
        user_id: Optional user identifier
        
    Returns:
        Tuple of (arm_name, arm_config)
    """
    return get_assigner().assign_arm(symbol, user_id)


def is_experiment_active() -> bool:
    """Check if any experiment is currently active"""
    return get_assigner().is_active()


def get_experiment_stats() -> Dict:
    """Get current experiment statistics"""
    return get_assigner().get_assignment_stats()


if __name__ == "__main__":
    # Test the assignment system
    import json
    
    assigner = ExperimentAssigner()
    
    print(f"Experiment active: {assigner.is_active()}")
    print(f"Experiment name: {assigner.get_experiment_name()}")
    
    # Test assignments for different symbols
    test_symbols = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY"]
    
    for symbol in test_symbols:
        arm, config = assigner.assign_arm(symbol)
        print(f"{symbol} → {arm} (strategy: {config.get('strategy_id')})")
    
    # Show assignment stats
    stats = assigner.get_assignment_stats()
    print(f"\nAssignment Stats:")
    print(json.dumps(stats, indent=2))
