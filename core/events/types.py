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


class TradeBlocked(BaseEvent):
    """Trade blocked by risk governance event"""

    symbol: str = Field(description="Trading symbol (e.g., XAUUSD)")
    side: str = Field(description="Intended trading direction (BUY/SELL)")
    reason: str = Field(description="Blocking reason from risk governor")
    governor_version: str = Field(default="v2", description="Risk governor version")

    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "XAUUSD",
                "side": "BUY",
                "reason": "LOSS_STREAK_COOLDOWN (үлдсэн: 25.3 мин)",
                "governor_version": "v2",
            }
        }


# === Order Lifecycle V2 Events ===


class PendingCreated(BaseEvent):
    """Order created and pending broker acceptance"""

    client_order_id: str = Field(description="Client-generated order ID")
    symbol: str = Field(description="Trading symbol")
    side: str = Field(description="Trading direction (BUY/SELL)")
    qty: float = Field(gt=0, description="Order quantity in lots")
    price: float | None = Field(
        default=None, description="Order price (None for market)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "client_order_id": "trade_20250907_143052_abc123",
                "symbol": "XAUUSD",
                "side": "BUY",
                "qty": 0.1,
                "price": 2485.50,
            }
        }


class PendingActivated(BaseEvent):
    """Order activated by broker with assigned ID"""

    client_order_id: str = Field(description="Client-generated order ID")
    broker_order_id: str = Field(description="Broker-assigned order ID")

    class Config:
        json_schema_extra = {
            "example": {
                "client_order_id": "trade_20250907_143052_abc123",
                "broker_order_id": "MT5_12345678",
            }
        }


class PartiallyFilled(BaseEvent):
    """Order partially filled"""

    client_order_id: str = Field(description="Client-generated order ID")
    fill_qty: float = Field(gt=0, description="Quantity filled in this event")
    fill_price: float = Field(gt=0, description="Price of this fill")
    cumulative_qty: float = Field(ge=0, description="Total quantity filled so far")

    class Config:
        json_schema_extra = {
            "example": {
                "client_order_id": "trade_20250907_143052_abc123",
                "fill_qty": 0.05,
                "fill_price": 2485.75,
                "cumulative_qty": 0.05,
            }
        }


class CancelRequested(BaseEvent):
    """Cancel request initiated for pending order"""

    client_order_id: str = Field(description="Client-generated order ID to cancel")

    class Config:
        json_schema_extra = {
            "example": {
                "client_order_id": "trade_20250907_143052_abc123",
            }
        }


class Cancelled(BaseEvent):
    """Order successfully cancelled"""

    client_order_id: str = Field(description="Client-generated order ID")

    class Config:
        json_schema_extra = {
            "example": {
                "client_order_id": "trade_20250907_143052_abc123",
            }
        }


class StopUpdateRequested(BaseEvent):
    """Request to update stop loss / take profit levels"""

    client_order_id: str = Field(description="Client-generated order ID")
    sl: float | None = Field(default=None, description="New stop loss price")
    tp: float | None = Field(default=None, description="New take profit price")

    class Config:
        json_schema_extra = {
            "example": {
                "client_order_id": "trade_20250907_143052_abc123",
                "sl": 2470.0,
                "tp": 2560.0,
            }
        }


class StopUpdated(BaseEvent):
    """Stop loss / take profit successfully updated"""

    client_order_id: str = Field(description="Client-generated order ID")
    sl: float | None = Field(default=None, description="Updated stop loss price")
    tp: float | None = Field(default=None, description="Updated take profit price")

    class Config:
        json_schema_extra = {
            "example": {
                "client_order_id": "trade_20250907_143052_abc123",
                "sl": 2470.0,
                "tp": 2560.0,
            }
        }


class BreakevenTriggered(BaseEvent):
    """Breakeven condition met, stop loss moved to entry"""

    client_order_id: str = Field(description="Client-generated order ID")
    new_sl: float = Field(description="New stop loss price (breakeven)")

    class Config:
        json_schema_extra = {
            "example": {
                "client_order_id": "trade_20250907_143052_abc123",
                "new_sl": 2485.50,
            }
        }


# === Performance & Workload Isolation Events ===


class ChartRequested(BaseEvent):
    """Chart rendering request for async processing"""

    client_order_id: str = Field(description="Context identifier for the request")
    symbol: str = Field(description="Trading symbol")
    timeframe: str = Field(description="Chart timeframe (e.g., M30, H1)")
    out_path: str = Field(description="Output file path")
    title: str | None = Field(default=None, description="Chart title")
    bars_count: int = Field(default=200, description="Number of bars to render")
    overlays: dict = Field(default_factory=dict, description="Chart overlays")
    send_telegram: bool = Field(
        default=False, description="Send to Telegram after rendering"
    )
    telegram_caption: str | None = Field(
        default=None, description="Telegram message caption"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "client_order_id": "trade_20250907_143052_abc123",
                "symbol": "XAUUSD",
                "timeframe": "M30",
                "out_path": "charts/XAUUSD_M30_20250907_143052.png",
                "title": "XAUUSD Buy Signal",
                "bars_count": 200,
                "overlays": {
                    "annotate_levels": {"entry": 2485.50, "sl": 2450.0, "tp": 2550.0}
                },
                "send_telegram": True,
                "telegram_caption": "📈 Trade executed: XAUUSD BUY",
            }
        }
