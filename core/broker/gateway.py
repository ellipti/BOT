"""
Broker Gateway Protocol - Ports & Adapters architecture
Defines the contract that all broker adapters must implement.
"""

from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable

from .models import OrderRequest, OrderResult, Position


@runtime_checkable
class BrokerGateway(Protocol):
    """
    Protocol defining the contract for broker integrations.

    This interface abstracts away broker-specific implementation details,
    allowing the trading strategy to work with any broker that implements
    this protocol.

    All implementations should handle connection management, order execution,
    and position tracking in a broker-specific manner while maintaining
    a consistent interface.
    """

    def connect(self) -> None:
        """
        Establish connection to the broker platform.

        Should handle all broker-specific connection logic including
        authentication, terminal attachment, or API initialization.

        Raises:
            ConnectionError: If connection cannot be established
        """
        ...

    def is_connected(self) -> bool:
        """
        Check if currently connected to broker platform.

        Returns:
            bool: True if connected and ready to trade, False otherwise
        """
        ...

    def place_order(self, request: OrderRequest) -> OrderResult:
        """
        Execute a trading order through the broker.

        Args:
            request: Order details following broker-agnostic format

        Returns:
            OrderResult: Execution result with broker order ID if accepted

        The implementation should:
        - Map the generic OrderRequest to broker-specific format
        - Execute the order through broker's API/platform
        - Return standardized result regardless of broker
        """
        ...

    def cancel(self, broker_order_id: str) -> bool:
        """
        Cancel a pending order by broker order ID.

        Args:
            broker_order_id: Broker-assigned order identifier

        Returns:
            bool: True if cancellation successful, False otherwise

        Note: Some brokers may not support order cancellation
        """
        ...

    def positions(self) -> list[Position]:
        """
        Retrieve all open positions from the broker.

        Returns:
            list[Position]: List of open positions in standardized format

        The implementation should:
        - Fetch positions from broker platform
        - Convert to standardized Position objects
        - Return empty list if no positions
        """
        ...


class AbstractBrokerGateway(ABC):
    """
    Abstract base class implementation of BrokerGateway.

    Provides a concrete base class for brokers that prefer inheritance
    over protocol implementation. Contains common logging and error
    handling patterns.
    """

    def __init__(self):
        self._connected = False

    @abstractmethod
    def connect(self) -> None:
        """Establish broker connection - must be implemented by subclass"""
        pass

    def is_connected(self) -> bool:
        """Default implementation tracking connection state"""
        return self._connected

    @abstractmethod
    def place_order(self, request: OrderRequest) -> OrderResult:
        """Execute order - must be implemented by subclass"""
        pass

    def cancel(self, broker_order_id: str) -> bool:
        """
        Default implementation - returns False (not supported).
        Subclasses should override if broker supports cancellation.
        """
        return False

    @abstractmethod
    def positions(self) -> list[Position]:
        """Retrieve positions - must be implemented by subclass"""
        pass
