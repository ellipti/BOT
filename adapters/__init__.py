"""
Broker adapters - Concrete implementations of BrokerGateway protocol
Contains platform-specific adapters for various brokers.
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from config.settings import Settings

logger = logging.getLogger(__name__)


def create_broker(settings):
    """
    Factory function to create broker adapter based on settings.
    
    Args:
        settings: Application settings containing broker configuration
        
    Returns:
        BrokerGateway: Broker adapter instance (MT5Broker, PaperBroker, etc.)
        
    Raises:
        ImportError: If required broker dependencies are not available
        ValueError: If broker kind is not supported
    """
    broker_kind = getattr(settings, 'BROKER_KIND', 'paper')
    
    logger.info(f"Creating broker adapter: {broker_kind}")
    
    if broker_kind == "mt5":
        # Try to import and create MT5 broker with fallback
        try:
            from .mt5_broker import MT5Broker
            
            # Try to create MT5Broker - this will fail if MetaTrader5 module not available
            broker = MT5Broker(settings)
            
            # Test if MT5 dependencies are actually available
            try:
                broker._ensure_mt5_imported()
                logger.info("Created MT5Broker adapter")
                return broker
            except ImportError as e:
                logger.warning(f"MT5 dependencies not available: {e}")
                raise ImportError(f"MT5 not available: {e}")
                
        except ImportError as e:
            logger.error(f"MT5 broker not available: {e}")
            logger.info("Falling back to PaperBroker")
            # Fallback to paper broker
            from .paper_broker import PaperBroker
            return PaperBroker(settings)
            
    elif broker_kind == "paper":
        from .paper_broker import PaperBroker
        broker = PaperBroker(settings)
        logger.info("Created PaperBroker adapter")
        return broker
        
    else:
        raise ValueError(f"Unsupported broker kind: {broker_kind}. Supported: mt5, paper")


# Import classes for direct usage if needed
from .mt5_broker import MT5Broker
from .paper_broker import PaperBroker

__all__ = [
    "create_broker",
    "MT5Broker", 
    "PaperBroker",
]
