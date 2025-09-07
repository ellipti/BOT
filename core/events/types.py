"""
Domain events for the trading pipeline - Event-driven architecture
Defines the flow: SignalDetected → Validated → RiskApproved → OrderPlaced → Filled/Rejected
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class BaseEvent(BaseModel):
    """Base class for all domain events with timestamp"""

    ts: datetime = Field(
        default_factory=datetime.utcnow, description="Event timestamp (UTC)"
    )

    class Config:
        """Pydantic configuration"""

        json_encoders = {datetime: lambda v: v.isoformat()}


class SignalDetected(BaseEvent):
    """Signal detection event - start of trading pipeline"""

    symbol: str = Field(description="Trading symbol (e.g., XAUUSD)")
    side: str = Field(description="Trading direction (BUY/SELL)")
    strength: float = Field(ge=0.0, le=1.0, description="Signal strength (0.0-1.0)")
    strategy_id: str = Field(description="Strategy that generated the signal")

    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "XAUUSD",
                "side": "BUY",
                "strength": 0.85,
                "strategy_id": "ma_crossover_rsi",
            }
        }


class Validated(BaseEvent):
    """Signal validation event - after basic validation checks"""

    symbol: str = Field(description="Trading symbol")
    side: str = Field(description="Trading direction (BUY/SELL)")
    reason: str | None = Field(
        default=None, description="Validation failure reason (None if valid)"
    )

    @property
    def is_valid(self) -> bool:
        """Check if validation passed"""
        return self.reason is None

    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "XAUUSD",
                "side": "BUY",
                "reason": None,  # Valid signal
            }
        }


class RiskApproved(BaseEvent):
    """Risk approval event - after position sizing and risk management"""

    symbol: str = Field(description="Trading symbol")
    side: str = Field(description="Trading direction (BUY/SELL)")
    qty: float = Field(gt=0, description="Approved position size in lots")
    sl: float | None = Field(default=None, description="Stop loss price")
    tp: float | None = Field(default=None, description="Take profit price")
    strategy_id: str = Field(description="Strategy requesting the trade")

    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "XAUUSD",
                "side": "BUY",
                "qty": 0.1,
                "sl": 2450.0,
                "tp": 2550.0,
                "strategy_id": "ma_crossover_rsi",
            }
        }


class OrderPlaced(BaseEvent):
    """Order placement event - order sent to broker"""

    client_order_id: str = Field(description="Client-generated order ID")
    symbol: str = Field(description="Trading symbol")
    side: str = Field(description="Trading direction (BUY/SELL)")
    qty: float = Field(gt=0, description="Order quantity in lots")
    sl: float | None = Field(default=None, description="Stop loss price")
    tp: float | None = Field(default=None, description="Take profit price")

    class Config:
        json_schema_extra = {
            "example": {
                "client_order_id": "trade_20250907_143052_abc123",
                "symbol": "XAUUSD",
                "side": "BUY",
                "qty": 0.1,
                "sl": 2450.0,
                "tp": 2550.0,
            }
        }


class Filled(BaseEvent):
    """Order fill event - successful execution"""

    broker_order_id: str = Field(description="Broker-assigned order ID")
    client_order_id: str = Field(description="Client-generated order ID")
    price: float = Field(gt=0, description="Execution price")
    qty: float = Field(gt=0, description="Filled quantity in lots")

    class Config:
        json_schema_extra = {
            "example": {
                "broker_order_id": "MT5_12345678",
                "client_order_id": "trade_20250907_143052_abc123",
                "price": 2485.50,
                "qty": 0.1,
            }
        }


class Rejected(BaseEvent):
    """Order rejection event - execution failed"""

    client_order_id: str = Field(description="Client-generated order ID")
    reason: str = Field(description="Rejection reason from broker")

    class Config:
        json_schema_extra = {
            "example": {
                "client_order_id": "trade_20250907_143052_abc123",
                "reason": "Insufficient margin",
            }
        }


class TradeClosed(BaseEvent):
    """Trade closure event - position closed"""

    broker_order_id: str = Field(description="Original broker order ID")
    client_order_id: str = Field(description="Original client order ID")
    close_price: float = Field(gt=0, description="Position close price")
    pnl: float = Field(description="Profit/Loss in account currency")
    close_reason: str = Field(description="Reason for closure (SL/TP/Manual)")

    class Config:
        json_schema_extra = {
            "example": {
                "broker_order_id": "MT5_12345678",
                "client_order_id": "trade_20250907_143052_abc123",
                "close_price": 2550.0,
                "pnl": 645.0,
                "close_reason": "TP",
            }
        }
