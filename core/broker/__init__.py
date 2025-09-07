"""
Broker abstraction layer - Ports & Adapters architecture
Provides broker-agnostic trading interfaces and models.
"""

from .gateway import AbstractBrokerGateway, BrokerGateway
from .models import OrderRequest, OrderResult, OrderType, Position, Side

__all__ = [
    # Protocol and abstract base
    "BrokerGateway",
    "AbstractBrokerGateway",
    # Domain models
    "Side",
    "OrderType",
    "OrderRequest",
    "OrderResult",
    "Position",
]
