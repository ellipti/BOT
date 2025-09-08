"""
Observability alerts and SLA monitoring with debouncing.

Provides alerting functionality to monitor system health and performance
metrics with configurable debouncing to prevent alert spam.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class AlertState:
    """Track alert state and debouncing information"""

    last_triggered: float | None = None
    last_resolved: float | None = None
    is_active: bool = False
    trigger_count: int = 0
    debounce_until: float | None = None


class AlertManager:
    """
    Manages alerts with debouncing to prevent notification spam.

    Features:
    - Configurable debounce periods per alert type
    - SLA violation detection
    - Alert state tracking
    - Integration with health checks
    """

    def __init__(self, debounce_seconds: int = 120):
        """
        Initialize alert manager.

        Args:
            debounce_seconds: Default debounce period in seconds
        """
        self.debounce_seconds = debounce_seconds
        self.alert_states: dict[str, AlertState] = {}

        logger.info(f"AlertManager initialized with {debounce_seconds}s debounce")

    def should_trigger_alert(self, alert_id: str, force: bool = False) -> bool:
        """
        Check if alert should be triggered based on debouncing rules.

        Args:
            alert_id: Unique identifier for the alert
            force: Force alert regardless of debounce period

        Returns:
            True if alert should be triggered
        """
        if force:
            return True

        current_time = time.time()

        if alert_id not in self.alert_states:
            self.alert_states[alert_id] = AlertState()
            return True

        state = self.alert_states[alert_id]

        # Check if still in debounce period
        if state.debounce_until and current_time < state.debounce_until:
            logger.debug(f"Alert {alert_id} still in debounce period")
            return False

        # Check if sufficient time has passed since last trigger
        if state.last_triggered:
            time_since_last = current_time - state.last_triggered
            if time_since_last < self.debounce_seconds:
                logger.debug(
                    f"Alert {alert_id} debounced: {time_since_last:.1f}s < {self.debounce_seconds}s"
                )
                return False

        return True

    def trigger_alert(
        self,
        alert_id: str,
        message: str,
        severity: str = "warning",
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """
        Trigger an alert with debouncing.

        Args:
            alert_id: Unique identifier for the alert
            message: Alert message
            severity: Alert severity (info, warning, error, critical)
            metadata: Additional alert metadata

        Returns:
            True if alert was triggered (not debounced)
        """
        if not self.should_trigger_alert(alert_id):
            return False

        current_time = time.time()

        # Update alert state
        if alert_id not in self.alert_states:
            self.alert_states[alert_id] = AlertState()

        state = self.alert_states[alert_id]
        state.last_triggered = current_time
        state.is_active = True
        state.trigger_count += 1
        state.debounce_until = current_time + self.debounce_seconds

        # Create alert record
        alert = {
            "id": alert_id,
            "message": message,
            "severity": severity,
            "timestamp": datetime.fromtimestamp(current_time).isoformat(),
            "trigger_count": state.trigger_count,
            "metadata": metadata or {},
        }

        # Log the alert
        log_level = {
            "info": logging.INFO,
            "warning": logging.WARNING,
            "error": logging.ERROR,
            "critical": logging.CRITICAL,
        }.get(severity, logging.WARNING)

        logger.log(log_level, f"🚨 ALERT [{severity.upper()}] {alert_id}: {message}")

        # In a real implementation, this would send to external systems
        # (email, Slack, PagerDuty, etc.)
        self._send_alert(alert)

        return True

    def resolve_alert(self, alert_id: str, message: str = "Alert resolved") -> bool:
        """
        Resolve an active alert.

        Args:
            alert_id: Unique identifier for the alert
            message: Resolution message

        Returns:
            True if alert was resolved
        """
        if alert_id not in self.alert_states:
            return False

        state = self.alert_states[alert_id]
        if not state.is_active:
            return False

        current_time = time.time()
        state.last_resolved = current_time
        state.is_active = False

        logger.info(f"✅ RESOLVED {alert_id}: {message}")

        # Send resolution notification
        resolution = {
            "id": alert_id,
            "message": message,
            "timestamp": datetime.fromtimestamp(current_time).isoformat(),
            "resolved": True,
        }

        self._send_alert(resolution)
        return True

    def _send_alert(self, alert: dict[str, Any]) -> None:
        """
        Send alert to external systems.

        This is a placeholder for integration with external alerting systems
        like email, Slack, PagerDuty, etc.

        Args:
            alert: Alert dictionary to send
        """
        # Placeholder implementation - in practice this would integrate with:
        # - Email notifications
        # - Slack/Teams webhooks
        # - PagerDuty API
        # - Custom webhook endpoints
        logger.debug(f"Alert would be sent to external systems: {alert['id']}")

    def check_sla_violation(
        self,
        metric_name: str,
        current_value: float,
        threshold: float,
        comparison: str = "gt",
    ) -> bool:
        """
        Check for SLA violation and trigger alert if needed.

        Args:
            metric_name: Name of the metric being checked
            current_value: Current metric value
            threshold: SLA threshold value
            comparison: Comparison operator (gt, lt, gte, lte)

        Returns:
            True if SLA violation was detected and alert triggered
        """
        violation_detected = False

        if (
            comparison == "gt"
            and current_value > threshold
            or comparison == "lt"
            and current_value < threshold
            or comparison == "gte"
            and current_value >= threshold
            or comparison == "lte"
            and current_value <= threshold
        ):
            violation_detected = True

        if violation_detected:
            alert_id = f"sla_violation_{metric_name}"
            message = (
                f"SLA violation: {metric_name}={current_value} "
                f"{comparison} {threshold}"
            )

            return self.trigger_alert(
                alert_id=alert_id,
                message=message,
                severity="error",
                metadata={
                    "metric": metric_name,
                    "value": current_value,
                    "threshold": threshold,
                    "comparison": comparison,
                },
            )
        else:
            # Check if we should resolve an existing SLA violation
            alert_id = f"sla_violation_{metric_name}"
            if alert_id in self.alert_states and self.alert_states[alert_id].is_active:
                self.resolve_alert(
                    alert_id, f"SLA restored: {metric_name}={current_value}"
                )

        return False

    def monitor_health_slas(self, health_data: dict[str, Any]) -> int:
        """
        Monitor health check data for SLA violations.

        Args:
            health_data: Health check results from health.check_health()

        Returns:
            Number of SLA violations detected
        """
        violations = 0

        # Check event lag SLA (should be < 300 seconds)
        if "event_lag_sec" in health_data:
            if self.check_sla_violation(
                "event_lag", health_data["event_lag_sec"], 300.0, "gt"
            ):
                violations += 1

        # Check MT5 connection SLA
        if "mt5_connected" in health_data:
            if not health_data["mt5_connected"]:
                if self.trigger_alert(
                    "mt5_disconnected", "MT5 connection lost", "critical"
                ):
                    violations += 1
            else:
                self.resolve_alert("mt5_disconnected", "MT5 connection restored")

        # Check position count SLA (warn if > 50 positions)
        if "positions_count" in health_data:
            if self.check_sla_violation(
                "position_count", health_data["positions_count"], 50.0, "gt"
            ):
                violations += 1

        # Check database connectivity SLA
        if "idempotency_db_ok" in health_data:
            if not health_data["idempotency_db_ok"]:
                if self.trigger_alert(
                    "database_error", "Idempotency database not accessible", "error"
                ):
                    violations += 1
            else:
                self.resolve_alert("database_error", "Database connectivity restored")

        return violations

    def get_alert_state(self, alert_id: str) -> AlertState | None:
        """Get current state of an alert."""
        return self.alert_states.get(alert_id)

    def get_active_alerts(self) -> dict[str, AlertState]:
        """Get all currently active alerts."""
        return {
            alert_id: state
            for alert_id, state in self.alert_states.items()
            if state.is_active
        }

    def cleanup_old_alerts(self, max_age_hours: int = 24) -> int:
        """
        Clean up old resolved alert states.

        Args:
            max_age_hours: Maximum age in hours for keeping resolved alerts

        Returns:
            Number of alert states cleaned up
        """
        cutoff_time = time.time() - (max_age_hours * 3600)
        cleaned_count = 0

        alert_ids_to_remove = []
        for alert_id, state in self.alert_states.items():
            if (
                not state.is_active
                and state.last_resolved
                and state.last_resolved < cutoff_time
            ):
                alert_ids_to_remove.append(alert_id)

        for alert_id in alert_ids_to_remove:
            del self.alert_states[alert_id]
            cleaned_count += 1

        if cleaned_count > 0:
            logger.debug(f"Cleaned up {cleaned_count} old alert states")

        return cleaned_count


# Global alert manager instance
_alert_manager: AlertManager | None = None


def get_alert_manager(debounce_seconds: int = 120) -> AlertManager:
    """
    Get the global alert manager instance.

    Args:
        debounce_seconds: Debounce period in seconds (default 120s = 2 minutes)

    Returns:
        AlertManager instance
    """
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager(debounce_seconds=debounce_seconds)
    return _alert_manager


def trigger_alert(
    alert_id: str,
    message: str,
    severity: str = "warning",
    metadata: dict[str, Any] | None = None,
) -> bool:
    """
    Convenience function to trigger an alert using the global manager.

    Args:
        alert_id: Unique identifier for the alert
        message: Alert message
        severity: Alert severity level
        metadata: Additional alert metadata

    Returns:
        True if alert was triggered (not debounced)
    """
    return get_alert_manager().trigger_alert(alert_id, message, severity, metadata)


def monitor_health() -> int:
    """
    Monitor system health and trigger alerts for SLA violations.

    Returns:
        Number of SLA violations detected
    """
    try:
        from observability.health import check_health

        health_data = check_health()
        return get_alert_manager().monitor_health_slas(health_data)

    except Exception as e:
        logger.error(f"Health monitoring failed: {e}")
        trigger_alert("health_monitor_error", f"Health monitoring error: {e}", "error")
        return 1


if __name__ == "__main__":
    # Test the alert system
    print("Testing alert system with 120s debounce...")

    manager = get_alert_manager(debounce_seconds=120)

    # Test normal alert
    success = manager.trigger_alert("test_alert", "This is a test alert", "warning")
    print(f"Alert triggered: {success}")

    # Test debouncing (should be blocked)
    success = manager.trigger_alert("test_alert", "This should be debounced", "warning")
    print(f"Debounced alert triggered: {success}")

    # Test SLA monitoring
    violations = monitor_health()
    print(f"SLA violations detected: {violations}")

    print("Alert system test complete!")
