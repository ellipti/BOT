"""
Event-driven architecture components
Provides domain events and in-process EventBus for trading pipeline coordination.
"""

from .bus import EventBus
from .types import (
    BaseEvent,
    Filled,
    OrderPlaced,
    Rejected,
    RiskApproved,
    SignalDetected,
    TradeBlocked,
    TradeClosed,
    Validated,
)

__all__ = [
    # Event bus
    "EventBus",
    # Domain events
    "BaseEvent",
    "SignalDetected",
    "Validated",
    "RiskApproved",
    "OrderPlaced",
    "Filled",
    "Rejected",
    "TradeClosed",
    "TradeBlocked",
]
