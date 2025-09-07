#!/usr/bin/env python3
"""
Risk Management Package
Upgrade #07 - Эрсдэлийн засаглалын пакет
"""

from .governor import (
    CircuitBreakerState,
    RiskGovernor,
    RiskLevel,
    RiskMetrics,
    TradeDecision,
)

try:
    from .telegram_alerts import get_risk_alert_manager, send_risk_alert

    TELEGRAM_ALERTS_AVAILABLE = True
except ImportError:
    TELEGRAM_ALERTS_AVAILABLE = False

    def send_risk_alert(message: str, level: str = "INFO") -> bool:
        return False

    def get_risk_alert_manager():
        return None


__all__ = [
    "RiskGovernor",
    "RiskLevel",
    "CircuitBreakerState",
    "RiskMetrics",
    "TradeDecision",
    "send_risk_alert",
    "get_risk_alert_manager",
    "TELEGRAM_ALERTS_AVAILABLE",
]
