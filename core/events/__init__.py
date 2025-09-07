"""
Event-driven architecture components
Provides domain events and in-process EventBus for trading pipeline coordination.
"""

from .bus import EventBus
from .types import (
    BaseEvent,
    BreakevenTriggered,
    Cancelled,
    CancelRequested,
    Filled,
    OrderPlaced,
    PartiallyFilled,
    PendingActivated,
    PendingCreated,
    Rejected,
    RiskApproved,
    SignalDetected,
    StopUpdated,
    StopUpdateRequested,
    TradeBlocked,
    TradeClosed,
    Validated,
)

__all__ = [
    # Event bus
    "EventBus",
    # Domain events - Core Pipeline
    "BaseEvent",
    "SignalDetected",
    "Validated",
    "RiskApproved",
    "OrderPlaced",
    "Filled",
    "Rejected",
    "TradeClosed",
    "TradeBlocked",
    # Domain events - Order Lifecycle V2
    "PendingCreated",
    "PendingActivated",
    "PartiallyFilled",
    "CancelRequested",
    "Cancelled",
    "StopUpdateRequested",
    "StopUpdated",
    "BreakevenTriggered",
]
