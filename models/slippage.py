"""
Slippage models for realistic order execution simulation

Provides different slippage models for backtesting and order execution
"""

import logging
from abc import ABC, abstractmethod
from typing import Protocol

logger = logging.getLogger(__name__)


class SlippageModel(Protocol):
    """Protocol for slippage calculation models"""

    def apply(self, side: str, price: float, atr: float | None = None) -> float:
        """
        Apply slippage to an order price

        Args:
            side: Order side ('BUY' or 'SELL')
            price: Original order price
            atr: Current ATR value (optional, for ATR-based models)

        Returns:
            Price after slippage adjustment

        Note:
            - BUY orders: slippage increases the execution price (worse fill)
            - SELL orders: slippage decreases the execution price (worse fill)
        """
        ...


class BaseSlippageModel(ABC):
    """Abstract base class for slippage model implementations"""

    @abstractmethod
    def apply(self, side: str, price: float, atr: float | None = None) -> float:
        """Apply slippage to order price"""
        pass

    def _validate_side(self, side: str) -> str:
        """Validate and normalize order side"""
        side_upper = side.upper()
        if side_upper not in ("BUY", "SELL"):
            raise ValueError(f"Invalid order side: {side}. Must be 'BUY' or 'SELL'")
        return side_upper

    def _validate_price(self, price: float) -> float:
        """Validate order price"""
        if price <= 0:
            raise ValueError(f"Price must be positive, got: {price}")
        return price


class FixedPipsSlippage(BaseSlippageModel):
    """Fixed pip-based slippage model"""

    def __init__(self, pips: float = 1.0, pip_size: float = 0.1):
        """
        Initialize fixed pips slippage model

        Args:
            pips: Number of pips slippage
            pip_size: Size of one pip for the instrument (0.1 for XAUUSD, 0.0001 for EURUSD)
        """
        if pips < 0:
            raise ValueError("Slippage pips must be non-negative")
        if pip_size <= 0:
            raise ValueError("Pip size must be positive")

        self.pips = pips
        self.pip_size = pip_size
        self.slippage_amount = pips * pip_size

        logger.info(
            f"FixedPipsSlippage initialized: {pips} pips = {self.slippage_amount}"
        )

    def apply(self, side: str, price: float, atr: float | None = None) -> float:
        """
        Apply fixed pip slippage

        Args:
            side: Order side ('BUY' or 'SELL')
            price: Original order price
            atr: Not used in fixed slippage model

        Returns:
            Price with slippage applied
        """
        side = self._validate_side(side)
        price = self._validate_price(price)

        if side == "BUY":
            # BUY: pay more (slippage against us)
            slipped_price = price + self.slippage_amount
        else:  # SELL
            # SELL: receive less (slippage against us)
            slipped_price = price - self.slippage_amount

        logger.debug(
            f"Fixed slippage applied: {side} {price} → {slipped_price} "
            f"(slip: {self.slippage_amount})"
        )

        return slipped_price


class PercentOfATRSlippage(BaseSlippageModel):
    """ATR percentage-based slippage model"""

    def __init__(self, atr_percentage: float = 2.0):
        """
        Initialize ATR percentage slippage model

        Args:
            atr_percentage: Percentage of ATR to use as slippage (e.g., 2.0 = 2%)
        """
        if atr_percentage < 0:
            raise ValueError("ATR percentage must be non-negative")

        self.atr_percentage = atr_percentage
        self.atr_multiplier = atr_percentage / 100.0

        logger.info(f"ATRSlippage initialized: {atr_percentage}% of ATR")

    def apply(self, side: str, price: float, atr: float | None = None) -> float:
        """
        Apply ATR percentage-based slippage

        Args:
            side: Order side ('BUY' or 'SELL')
            price: Original order price
            atr: Current ATR value (required for this model)

        Returns:
            Price with slippage applied

        Raises:
            ValueError: If ATR is None or invalid
        """
        side = self._validate_side(side)
        price = self._validate_price(price)

        if atr is None:
            raise ValueError("ATR value required for ATR-based slippage model")
        if atr <= 0:
            raise ValueError(f"ATR must be positive, got: {atr}")

        # Calculate slippage amount as percentage of ATR
        slippage_amount = atr * self.atr_multiplier

        if side == "BUY":
            # BUY: pay more (slippage against us)
            slipped_price = price + slippage_amount
        else:  # SELL
            # SELL: receive less (slippage against us)
            slipped_price = price - slippage_amount

        logger.debug(
            f"ATR slippage applied: {side} {price} → {slipped_price} "
            f"(ATR: {atr}, slip: {slippage_amount}, {self.atr_percentage}%)"
        )

        return slipped_price


class NoSlippage(BaseSlippageModel):
    """No slippage model for perfect execution simulation"""

    def apply(self, side: str, price: float, atr: float | None = None) -> float:
        """
        Apply no slippage (perfect execution)

        Args:
            side: Order side (validated but not used)
            price: Original order price
            atr: Not used in no slippage model

        Returns:
            Original price unchanged
        """
        self._validate_side(side)
        return self._validate_price(price)
