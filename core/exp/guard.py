#!/usr/bin/env python3
"""
Experiment Guardrail Module

Monitors experiment metrics and triggers automatic rollback when safety
thresholds are exceeded. Provides real-time safety monitoring for A/B tests.
"""

import logging
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import yaml

from observability.metrics import get_metrics

logger = logging.getLogger(__name__)


class MetricWindow:
    """Sliding window for metric collection"""
    
    def __init__(self, window_minutes: int, max_size: int = 1000):
        self.window_minutes = window_minutes
        self.max_size = max_size
        self.values = deque(maxlen=max_size)
        
    def add(self, value: float, timestamp: Optional[datetime] = None) -> None:
        """Add a value to the window"""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        self.values.append((timestamp, value))
        
        # Clean old values
        self._clean_old_values()
    
    def _clean_old_values(self) -> None:
        """Remove values outside the window"""
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=self.window_minutes)
        
        while self.values and self.values[0][0] < cutoff:
            self.values.popleft()
    
    def get_rate(self) -> float:
        """Get rate (events per total) in current window"""
        self._clean_old_values()
        
        if not self.values:
            return 0.0
        
        # Count events (assuming 1.0 = event, 0.0 = no event)
        events = sum(1 for _, value in self.values if value > 0.5)
        total = len(self.values)
        
        return events / total if total > 0 else 0.0
    
    def get_average(self) -> float:
        """Get average value in current window"""
        self._clean_old_values()
        
        if not self.values:
            return 0.0
        
        total = sum(value for _, value in self.values)
        return total / len(self.values)
    
    def get_count(self) -> int:
        """Get number of values in current window"""
        self._clean_old_values()
        return len(self.values)


class GuardrailEvaluator:
    """Evaluates experiment guardrails and triggers rollbacks"""
    
    def __init__(self, config_path: str = "configs/experiments.yaml"):
        self.config_path = config_path
        self.config = self._load_config()
        
        # Metric windows per arm
        self.metrics = defaultdict(lambda: {
            'rejected_rate_15m': MetricWindow(15),
            'rejected_rate_60m': MetricWindow(60),
            'fill_timeout_15m': MetricWindow(15),
            'fill_timeout_60m': MetricWindow(60),
            'drawdown_15m': MetricWindow(15),
            'drawdown_60m': MetricWindow(60),
        })
        
        # Rollback state
        self.rollback_active = False
        self.rollback_time = None
        self.rollback_reason = None
        
        # Alert tracking
        self.last_alert_time = {}
        
    def _load_config(self) -> Dict:
        """Load experiment configuration"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load guardrail config: {e}")
            return {}
    
    def record_order_rejected(self, arm: str, symbol: str) -> None:
        """Record an order rejection event"""
        self.metrics[arm]['rejected_rate_15m'].add(1.0)
        self.metrics[arm]['rejected_rate_60m'].add(1.0)
        
        logger.debug(f"Recorded rejection for arm {arm}, symbol {symbol}")
        
        # Check guardrails after recording
        self._evaluate_guardrails()
    
    def record_order_filled(self, arm: str, symbol: str, fill_time_ms: float) -> None:
        """Record a successful order fill"""
        # Record as non-rejection
        self.metrics[arm]['rejected_rate_15m'].add(0.0)
        self.metrics[arm]['rejected_rate_60m'].add(0.0)
        
        # Record fill timeout if over threshold
        timeout_threshold_ms = 5000  # 5 seconds
        is_timeout = 1.0 if fill_time_ms > timeout_threshold_ms else 0.0
        
        self.metrics[arm]['fill_timeout_15m'].add(is_timeout)
        self.metrics[arm]['fill_timeout_60m'].add(is_timeout)
        
        logger.debug(f"Recorded fill for arm {arm}, time: {fill_time_ms}ms")
        
        # Check guardrails after recording
        self._evaluate_guardrails()
    
    def record_drawdown(self, arm: str, drawdown_pct: float) -> None:
        """Record daily drawdown percentage"""
        self.metrics[arm]['drawdown_15m'].add(drawdown_pct)
        self.metrics[arm]['drawdown_60m'].add(drawdown_pct)
        
        logger.debug(f"Recorded drawdown for arm {arm}: {drawdown_pct:.3f}%")
        
        # Check guardrails after recording
        self._evaluate_guardrails()
    
    def _evaluate_guardrails(self) -> None:
        """Evaluate all guardrails and trigger rollback if needed"""
        if self.rollback_active:
            return  # Already in rollback state
        
        guardrails = self.config.get('guardrails', {})
        min_trades = guardrails.get('min_trades_eval', 10)
        
        violations = []
        
        for arm, arm_metrics in self.metrics.items():
            # Skip if not enough data
            if arm_metrics['rejected_rate_15m'].get_count() < min_trades:
                continue
            
            # Check rejection rate (15 min and 60 min)
            reject_rate_15m = arm_metrics['rejected_rate_15m'].get_rate()
            reject_rate_60m = arm_metrics['rejected_rate_60m'].get_rate()
            reject_max = guardrails.get('rejected_rate_max', 0.05)
            
            if reject_rate_15m > reject_max:
                violations.append(f"Arm {arm}: rejection rate {reject_rate_15m:.3f} > {reject_max} (15m)")
            if reject_rate_60m > reject_max:
                violations.append(f"Arm {arm}: rejection rate {reject_rate_60m:.3f} > {reject_max} (60m)")
            
            # Check fill timeout rate
            timeout_rate_15m = arm_metrics['fill_timeout_15m'].get_rate()
            timeout_rate_60m = arm_metrics['fill_timeout_60m'].get_rate()
            timeout_max = guardrails.get('fill_timeout_max', 0.02)
            
            if timeout_rate_15m > timeout_max:
                violations.append(f"Arm {arm}: fill timeout rate {timeout_rate_15m:.3f} > {timeout_max} (15m)")
            if timeout_rate_60m > timeout_max:
                violations.append(f"Arm {arm}: fill timeout rate {timeout_rate_60m:.3f} > {timeout_max} (60m)")
            
            # Check drawdown
            drawdown_15m = arm_metrics['drawdown_15m'].get_average()
            drawdown_60m = arm_metrics['drawdown_60m'].get_average()
            drawdown_max = guardrails.get('drawdown_day_max', 0.03)
            
            if drawdown_15m > drawdown_max:
                violations.append(f"Arm {arm}: drawdown {drawdown_15m:.3f} > {drawdown_max} (15m)")
            if drawdown_60m > drawdown_max:
                violations.append(f"Arm {arm}: drawdown {drawdown_60m:.3f} > {drawdown_max} (60m)")
        
        # Trigger rollback if violations found
        if violations:
            self._trigger_rollback(violations)
    
    def _trigger_rollback(self, violations: List[str]) -> None:
        """Trigger automatic rollback due to guardrail violations"""
        if self.rollback_active:
            return
        
        self.rollback_active = True
        self.rollback_time = datetime.now(timezone.utc)
        self.rollback_reason = "; ".join(violations[:3])  # Limit reason length
        
        logger.error(f"GUARDRAIL VIOLATION - Triggering rollback: {self.rollback_reason}")
        
        # Update experiment weights to safe configuration
        self._apply_rollback_weights()
        
        # Send alert
        self._send_rollback_alert()
        
        # Record rollback metric
        metrics = get_metrics()
        metrics.inc("experiment_rollback_triggered", 
                   experiment=self.config.get("name", "unknown"),
                   reason="guardrail_violation")
    
    def _apply_rollback_weights(self) -> None:
        """Apply safe weights (rollback to arm A)"""
        try:
            safe_weights = self.config.get('rollback', {}).get('safe_weights', {'A': 100, 'B': 0})
            
            # Update config in memory (would need file write for persistence)
            if 'arms' in self.config:
                for arm_name, weight in safe_weights.items():
                    if arm_name in self.config['arms']:
                        self.config['arms'][arm_name]['weight'] = weight
            
            logger.info(f"Applied rollback weights: {safe_weights}")
            
        except Exception as e:
            logger.error(f"Failed to apply rollback weights: {e}")
    
    def _send_rollback_alert(self) -> None:
        """Send Telegram alert about rollback"""
        try:
            from services.telegram_v2 import TelegramBotV2
            
            telegram = TelegramBotV2()
            if telegram.enabled:
                experiment_name = self.config.get("name", "unknown")
                message = f"🚨 AB ROLLBACK: {experiment_name}\n\nReason: {self.rollback_reason}\n\nTime: {self.rollback_time.strftime('%Y-%m-%d %H:%M:%S UTC')}"
                
                telegram.send_message(message)
                logger.info("Sent rollback alert to Telegram")
            
        except Exception as e:
            logger.error(f"Failed to send rollback alert: {e}")
    
    def get_guardrail_status(self) -> Dict:
        """Get current guardrail status and metrics"""
        status = {
            "rollback_active": self.rollback_active,
            "rollback_time": self.rollback_time.isoformat() if self.rollback_time else None,
            "rollback_reason": self.rollback_reason,
            "arms": {}
        }
        
        guardrails = self.config.get('guardrails', {})
        
        for arm, arm_metrics in self.metrics.items():
            arm_status = {
                "rejection_rate_15m": arm_metrics['rejected_rate_15m'].get_rate(),
                "rejection_rate_60m": arm_metrics['rejected_rate_60m'].get_rate(),
                "fill_timeout_rate_15m": arm_metrics['fill_timeout_15m'].get_rate(),
                "fill_timeout_rate_60m": arm_metrics['fill_timeout_60m'].get_rate(),
                "drawdown_15m": arm_metrics['drawdown_15m'].get_average(),
                "drawdown_60m": arm_metrics['drawdown_60m'].get_average(),
                "sample_count_15m": arm_metrics['rejected_rate_15m'].get_count(),
                "sample_count_60m": arm_metrics['rejected_rate_60m'].get_count(),
            }
            
            # Add violation flags
            arm_status["violations"] = {
                "rejection_rate": max(arm_status["rejection_rate_15m"], arm_status["rejection_rate_60m"]) > guardrails.get('rejected_rate_max', 0.05),
                "fill_timeout": max(arm_status["fill_timeout_rate_15m"], arm_status["fill_timeout_rate_60m"]) > guardrails.get('fill_timeout_max', 0.02),
                "drawdown": max(arm_status["drawdown_15m"], arm_status["drawdown_60m"]) > guardrails.get('drawdown_day_max', 0.03),
            }
            
            status["arms"][arm] = arm_status
        
        return status
    
    def reset_rollback(self) -> None:
        """Reset rollback state (manual intervention)"""
        if self.rollback_active:
            logger.info(f"Resetting rollback state (was: {self.rollback_reason})")
            
            self.rollback_active = False
            self.rollback_time = None
            self.rollback_reason = None
            
            # Clear metrics to start fresh
            self.metrics.clear()


# Global evaluator instance
_evaluator: Optional[GuardrailEvaluator] = None


def get_evaluator() -> GuardrailEvaluator:
    """Get global guardrail evaluator instance"""
    global _evaluator
    if _evaluator is None:
        _evaluator = GuardrailEvaluator()
    return _evaluator


def record_order_rejected(arm: str, symbol: str) -> None:
    """Record order rejection for guardrail monitoring"""
    get_evaluator().record_order_rejected(arm, symbol)


def record_order_filled(arm: str, symbol: str, fill_time_ms: float) -> None:
    """Record order fill for guardrail monitoring"""
    get_evaluator().record_order_filled(arm, symbol, fill_time_ms)


def record_drawdown(arm: str, drawdown_pct: float) -> None:
    """Record drawdown for guardrail monitoring"""
    get_evaluator().record_drawdown(arm, drawdown_pct)


def get_guardrail_status() -> Dict:
    """Get current guardrail status"""
    return get_evaluator().get_guardrail_status()


if __name__ == "__main__":
    # Test the guardrail system
    import json
    import random
    
    evaluator = GuardrailEvaluator()
    
    # Simulate some trading activity
    print("Simulating trading activity...")
    
    for i in range(50):
        arm = "A" if i % 2 == 0 else "B"
        
        # Simulate order results
        if random.random() < 0.95:  # 95% fill rate
            fill_time = random.uniform(100, 3000)  # 100ms to 3s
            evaluator.record_order_filled(arm, "XAUUSD", fill_time)
        else:
            evaluator.record_order_rejected(arm, "XAUUSD")
        
        # Simulate drawdown
        drawdown = random.uniform(0, 0.02)  # 0-2% drawdown
        evaluator.record_drawdown(arm, drawdown)
    
    # Show status
    status = evaluator.get_guardrail_status()
    print(json.dumps(status, indent=2, default=str))
