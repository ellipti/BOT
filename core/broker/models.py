"""
Broker-agnostic trading models following Ports & Adapters architecture.
Defines core domain models for order management and position tracking.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, validator


class Side(str, Enum):
    """Trading direction"""

    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    """Order execution type"""

    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"


class OrderRequest(BaseModel):
    """Broker-agnostic order request model"""

    client_order_id: str = Field(
        description="Client-generated unique identifier for this order"
    )
    symbol: str = Field(description="Trading symbol (e.g., XAUUSD)")
    side: Side = Field(description="Trading direction (BUY/SELL)")
    qty: float = Field(gt=0, description="Order quantity in lots")
    order_type: OrderType = Field(
        default=OrderType.MARKET, description="Order execution type"
    )
    sl: float | None = Field(default=None, description="Stop loss price (optional)")
    tp: float | None = Field(default=None, description="Take profit price (optional)")
    price: float | None = Field(
        default=None,
        description="Limit/Stop order price (required for non-MARKET orders)",
    )

    @validator("price", always=True)
    def validate_price_for_non_market(cls, v, values):
        """Price required for LIMIT/STOP orders"""
        order_type = values.get("order_type")
        if order_type in ["LIMIT", "STOP"] and v is None:
            raise ValueError(f"{order_type} orders require a price")
        return v

    class Config:
        use_enum_values = True


class OrderResult(BaseModel):
    """Broker order execution result"""

    accepted: bool = Field(description="Whether the order was accepted by broker")
    broker_order_id: str | None = Field(
        default=None, description="Broker-assigned order identifier"
    )
    reason: str | None = Field(
        default=None, description="Rejection reason or additional info"
    )

    @validator("broker_order_id")
    def validate_order_id_when_accepted(cls, v, values):
        """Accepted orders should have broker_order_id"""
        accepted = values.get("accepted", False)
        if accepted and not v:
            raise ValueError("Accepted orders must have broker_order_id")
        return v


class Position(BaseModel):
    """Open position representation"""

    symbol: str = Field(description="Trading symbol")
    qty: float = Field(description="Position size (positive=long, negative=short)")
    avg_price: float = Field(gt=0, description="Average entry price")

    @property
    def is_long(self) -> bool:
        """Check if position is long"""
        return self.qty > 0

    @property
    def is_short(self) -> bool:
        """Check if position is short"""
        return self.qty < 0

    @property
    def abs_qty(self) -> float:
        """Absolute position size"""
        return abs(self.qty)

    class Config:
        use_enum_values = True
