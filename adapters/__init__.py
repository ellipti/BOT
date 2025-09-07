"""
Broker adapters - Concrete implementations of BrokerGateway protocol
Contains platform-specific adapters for various brokers.
"""

# Import only if needed to avoid forcing MT5 dependency
from .mt5_broker import MT5Broker

__all__ = [
    "MT5Broker",
]
