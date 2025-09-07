"""
Broker Factory - Creates broker instances based on configuration
Provides factory pattern for broker gateway instantiation.
"""

import logging
from typing import TYPE_CHECKING

from core.broker import BrokerGateway

if TYPE_CHECKING:
    from config.settings import ApplicationSettings

logger = logging.getLogger(__name__)


def create_broker(settings: "ApplicationSettings") -> BrokerGateway:
    """
    Create broker gateway instance based on configuration.

    Currently supports MT5 broker only. Future versions can add
    support for additional brokers by checking configuration
    and returning appropriate adapter.

    Args:
        settings: Application configuration containing broker settings

    Returns:
        BrokerGateway: Configured broker adapter instance

    Raises:
        ValueError: If broker type not supported
        ImportError: If required broker dependencies not available
    """

    # For now, we only support MT5
    # Future: could check settings.broker_type or similar
    broker_type = getattr(settings, "broker_type", "mt5").lower()

    if broker_type == "mt5":
        try:
            from adapters.mt5_broker import MT5Broker

            logger.info("Creating MT5 broker adapter")
            return MT5Broker(settings)
        except ImportError as e:
            raise ImportError(
                "MT5 broker adapter requires MetaTrader5 package. "
                "Install with: pip install MetaTrader5"
            ) from e

    # Future broker support can be added here:
    # elif broker_type == "ib":
    #     from adapters.ib_broker import IBBroker
    #     return IBBroker(settings)
    # elif broker_type == "alpaca":
    #     from adapters.alpaca_broker import AlpacaBroker
    #     return AlpacaBroker(settings)

    else:
        raise ValueError(
            f"Unsupported broker type: {broker_type}. " f"Supported types: mt5"
        )
