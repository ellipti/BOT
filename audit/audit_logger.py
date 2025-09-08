"""
Immutable Audit Logger (Prompt-31)
==================================

Append-only JSONL audit logging for compliance and regulatory requirements.
Captures all trading events, configuration changes, and system activities.

Features:
- Immutable append-only logs
- Daily log rotation (audit-YYYYMMDD.jsonl)
- Redaction filter integration
- Structured event logging
- Performance optimized for high-frequency events
"""

import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# Import redaction patterns from existing logging setup
try:
    from logging_setup import REDACTION_PATTERNS
except ImportError:
    # Fallback redaction patterns if import fails
    REDACTION_PATTERNS = [
        (
            re.compile(r'password["\']?\s*[:=]\s*["\']?([^"\',\s]+)', re.IGNORECASE),
            r'password="[REDACTED]"',
        ),
        (
            re.compile(r'api_key["\']?\s*[:=]\s*["\']?([^"\',\s]+)', re.IGNORECASE),
            r'api_key="[REDACTED]"',
        ),
        (
            re.compile(r'token["\']?\s*[:=]\s*["\']?([^"\',\s]+)', re.IGNORECASE),
            r'token="[REDACTED]"',
        ),
    ]

logger_instance = None


def redact_sensitive_data(record: dict[str, Any]) -> dict[str, Any]:
    """
    Apply redaction patterns to audit record data.

    Args:
        record: Audit record dictionary

    Returns:
        Dict with sensitive data redacted
    """
    # Convert record to JSON string for pattern matching
    record_json = json.dumps(record, ensure_ascii=False)

    # Apply redaction patterns
    for pattern in REDACTION_PATTERNS:
        if hasattr(pattern, "sub"):  # It's a compiled regex
            record_json = pattern.sub(lambda m: m.group(1) + "[REDACTED]", record_json)

    try:
        # Convert back to dict
        return json.loads(record_json)
    except json.JSONDecodeError:
        # If redaction broke JSON, return original record
        return record


class AuditLogger:
    """
    Immutable audit logger for compliance and regulatory requirements.

    Provides append-only JSONL logging with automatic daily rotation,
    redaction filtering, and structured event capture.
    """

    def __init__(self, log_dir: str = "logs"):
        """
        Initialize audit logger with specified directory.

        Args:
            log_dir: Directory for audit log files (default: "logs")
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def write(self, event: str, **fields) -> None:
        """
        Write audit event to immutable log.

        Args:
            event: Event type (e.g., "OrderAccepted", "ConfigChanged")
            **fields: Additional event data
        """
        # Create daily log file name
        date_str = time.strftime("%Y%m%d")
        log_file = self.log_dir / f"audit-{date_str}.jsonl"

        # Create audit record with timestamp
        record = {
            "ts": time.time(),
            "iso_ts": datetime.utcnow().isoformat() + "Z",
            "event": event,
            **fields,
        }

        # Apply redaction filter to sensitive data
        redacted_record = redact_sensitive_data(record)

        # Append to JSONL file (immutable, append-only)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(redacted_record, ensure_ascii=False) + "\n")

    def write_order_event(
        self,
        event: str,
        symbol: str,
        side: str,
        quantity: float,
        price: float | None = None,
        order_id: str | None = None,
        **extra,
    ) -> None:
        """
        Write order-related audit event.

        Args:
            event: Order event type
            symbol: Trading symbol
            side: Order side (BUY/SELL)
            quantity: Order quantity
            price: Order price (if applicable)
            order_id: Order identifier (if available)
            **extra: Additional order data
        """
        self.write(
            event,
            category="order",
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            order_id=order_id,
            **extra,
        )

    def write_fill_event(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        order_id: str | None = None,
        deal_id: str | None = None,
        **extra,
    ) -> None:
        """
        Write fill/execution audit event.

        Args:
            symbol: Trading symbol
            side: Order side
            quantity: Filled quantity
            price: Fill price
            order_id: Original order ID
            deal_id: Broker deal/trade ID
            **extra: Additional fill data
        """
        self.write(
            "Filled",
            category="fill",
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            order_id=order_id,
            deal_id=deal_id,
            **extra,
        )

    def write_config_event(
        self,
        config_type: str,
        old_value: Any = None,
        new_value: Any = None,
        file_path: str | None = None,
        **extra,
    ) -> None:
        """
        Write configuration change audit event.

        Args:
            config_type: Type of configuration changed
            old_value: Previous configuration value
            new_value: New configuration value
            file_path: Configuration file path
            **extra: Additional config data
        """
        self.write(
            "ConfigChanged",
            category="config",
            config_type=config_type,
            old_value=old_value,
            new_value=new_value,
            file_path=file_path,
            **extra,
        )

    def write_alert_event(
        self, alert_type: str, message: str, severity: str = "INFO", **extra
    ) -> None:
        """
        Write alert/notification audit event.

        Args:
            alert_type: Type of alert
            message: Alert message
            severity: Alert severity level
            **extra: Additional alert data
        """
        self.write(
            "AlertSent",
            category="alert",
            alert_type=alert_type,
            message=message,
            severity=severity,
            **extra,
        )

    def write_auth_event(
        self,
        event_type: str,
        user: str | None = None,
        source_ip: str | None = None,
        **extra,
    ) -> None:
        """
        Write authentication/authorization audit event.

        Args:
            event_type: Auth event type (Login, Logout, etc.)
            user: Username or identifier
            source_ip: Source IP address
            **extra: Additional auth data
        """
        self.write(event_type, category="auth", user=user, source_ip=source_ip, **extra)


def get_audit_logger() -> AuditLogger:
    """
    Get singleton audit logger instance.

    Returns:
        AuditLogger: Shared audit logger instance
    """
    global logger_instance
    if logger_instance is None:
        logger_instance = AuditLogger()
    return logger_instance


def audit_event(event: str, **fields) -> None:
    """
    Convenience function for writing audit events.

    Args:
        event: Event type
        **fields: Event data
    """
    get_audit_logger().write(event, **fields)


def audit_order(
    event: str,
    symbol: str,
    side: str,
    quantity: float,
    price: float | None = None,
    order_id: str | None = None,
    **extra,
) -> None:
    """
    Convenience function for order audit events.
    """
    get_audit_logger().write_order_event(
        event, symbol, side, quantity, price, order_id, **extra
    )


def audit_fill(
    symbol: str,
    side: str,
    quantity: float,
    price: float,
    order_id: str | None = None,
    deal_id: str | None = None,
    **extra,
) -> None:
    """
    Convenience function for fill audit events.
    """
    get_audit_logger().write_fill_event(
        symbol, side, quantity, price, order_id, deal_id, **extra
    )


def audit_config(
    config_type: str,
    old_value: Any = None,
    new_value: Any = None,
    file_path: str | None = None,
    **extra,
) -> None:
    """
    Convenience function for config audit events.
    """
    get_audit_logger().write_config_event(
        config_type, old_value, new_value, file_path, **extra
    )


def audit_alert(alert_type: str, message: str, severity: str = "INFO", **extra) -> None:
    """
    Convenience function for alert audit events.
    """
    get_audit_logger().write_alert_event(alert_type, message, severity, **extra)


def audit_auth(
    event_type: str,
    user: str | None = None,
    source_ip: str | None = None,
    **extra,
) -> None:
    """
    Convenience function for auth audit events.
    """
    get_audit_logger().write_auth_event(event_type, user, source_ip, **extra)
