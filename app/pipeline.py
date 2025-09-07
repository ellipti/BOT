"""
Trading Pipeline - Event-driven flow coordination
Wires together the trading pipeline: Signal → Validation → Risk → Order → Execution
"""

import hashlib
import logging
from datetime import datetime
from typing import TYPE_CHECKING

from core.broker import BrokerGateway, OrderRequest, OrderType, Side
from core.events import (
    EventBus,
    OrderPlaced,
    RiskApproved,
    SignalDetected,
    Validated,
)

if TYPE_CHECKING:
    from config.settings import ApplicationSettings

logger = logging.getLogger(__name__)


class TradingPipeline:
    """
    Event-driven trading pipeline coordinator.

    Registers handlers for domain events and orchestrates the flow:
    SignalDetected → Validated → RiskApproved → OrderPlaced → [Execution TBD]
    """

    def __init__(
        self, settings: "ApplicationSettings", bus: EventBus, broker: BrokerGateway
    ):
        """
        Initialize pipeline with dependencies.

        Args:
            settings: Application configuration
            bus: Event bus for pub/sub communication
            broker: Broker gateway for order execution
        """
        self.settings = settings
        self.bus = bus
        self.broker = broker

    def wire_handlers(self) -> None:
        """
        Register all pipeline event handlers.

        Creates the event flow by subscribing handlers to domain events.
        This method should be called once during application startup.
        """
        logger.info("Wiring trading pipeline event handlers")

        # Signal validation handler
        self.bus.subscribe(SignalDetected, self._handle_signal_detected)

        # Risk management handler
        self.bus.subscribe(Validated, self._handle_validated)

        # Order placement handler
        self.bus.subscribe(RiskApproved, self._handle_risk_approved)

        # Order execution handler (placeholder for now)
        self.bus.subscribe(OrderPlaced, self._handle_order_placed)

        logger.info("Pipeline handlers registered successfully")

    def _handle_signal_detected(self, event: SignalDetected) -> None:
        """
        Handle signal detection - perform basic validation.

        Args:
            event: SignalDetected event with trading signal
        """
        logger.info(
            f"Processing signal: {event.symbol} {event.side} strength={event.strength}"
        )

        # Placeholder validation logic
        # TODO: Add real validation (spread check, news filter, cooldown, etc.)
        validation_reason = None

        # Basic validation checks
        if event.strength < 0.5:
            validation_reason = f"Signal strength {event.strength} below minimum 0.5"
        elif event.side not in ["BUY", "SELL"]:
            validation_reason = f"Invalid side: {event.side}"
        elif not event.symbol:
            validation_reason = "Missing symbol"

        # Emit validation result
        validated = Validated(
            symbol=event.symbol, side=event.side, reason=validation_reason
        )

        logger.debug(
            f"Signal validation: {'PASS' if validated.is_valid else 'FAIL'} - {validation_reason or 'OK'}"
        )
        self.bus.publish(validated)

    def _handle_validated(self, event: Validated) -> None:
        """
        Handle validated signal - perform risk management and position sizing.

        Args:
            event: Validated event with validation result
        """
        if not event.is_valid:
            logger.info(f"Skipping invalid signal: {event.reason}")
            return

        logger.info(f"Processing validated signal: {event.symbol} {event.side}")

        # Placeholder position sizing and risk management
        # TODO: Replace with real risk management logic
        base_qty = 0.1  # Base position size
        risk_pct = self.settings.trading.risk_percentage

        # Simple position sizing (placeholder)
        qty = base_qty * risk_pct * 10  # Scaled by risk percentage

        # Placeholder SL/TP calculation
        # TODO: Use ATR, technical levels, or strategy-specific logic
        current_price = 2500.0  # Placeholder price
        atr_distance = 50.0  # Placeholder ATR

        if event.side == "BUY":
            sl = current_price - (1.5 * atr_distance)  # 1.5 ATR stop loss
            tp = current_price + (3.0 * atr_distance)  # 3.0 ATR take profit
        else:  # SELL
            sl = current_price + (1.5 * atr_distance)
            tp = current_price - (3.0 * atr_distance)

        # Emit risk approval
        risk_approved = RiskApproved(
            symbol=event.symbol,
            side=event.side,
            qty=qty,
            sl=sl,
            tp=tp,
            strategy_id="pipeline_placeholder",  # TODO: Pass through from signal
        )

        logger.debug(
            f"Risk approved: {event.symbol} {event.side} qty={qty:.3f} sl={sl:.1f} tp={tp:.1f}"
        )
        self.bus.publish(risk_approved)

    def _handle_risk_approved(self, event: RiskApproved) -> None:
        """
        Handle risk approval - compose order request.

        Args:
            event: RiskApproved event with position sizing and risk parameters
        """
        logger.info(
            f"Processing risk approval: {event.symbol} {event.side} qty={event.qty}"
        )

        # Generate unique client order ID
        client_order_id = self._generate_client_order_id(event)

        logger.debug(f"Generated client order ID: {client_order_id}")

        # Emit order placement event
        order_placed = OrderPlaced(
            client_order_id=client_order_id,
            symbol=event.symbol,
            side=event.side,
            qty=event.qty,
            sl=event.sl,
            tp=event.tp,
        )

        logger.debug(f"Order ready for placement: {client_order_id}")
        self.bus.publish(order_placed)

    def _handle_order_placed(self, event: OrderPlaced) -> None:
        """
        Handle order placement - execute through broker (placeholder).

        Args:
            event: OrderPlaced event ready for broker execution

        Note:
            This is a placeholder. Actual broker execution will be added in next prompt.
        """
        logger.info(
            f"Order placement received: {event.client_order_id} {event.symbol} {event.side}"
        )

        # TODO: In next prompt, this will:
        # 1. Convert OrderPlaced to OrderRequest
        # 2. Call broker.place_order()
        # 3. Emit Filled/Rejected based on result

        logger.debug(
            f"Order execution placeholder - would execute {event.client_order_id}"
        )

        # For now, just log the order details
        logger.info(
            f"Order details: symbol={event.symbol}, side={event.side}, "
            f"qty={event.qty}, sl={event.sl}, tp={event.tp}"
        )

    def _generate_client_order_id(self, event: RiskApproved) -> str:
        """
        Generate unique client order ID for tracking.

        Args:
            event: RiskApproved event to generate ID from

        Returns:
            Unique client order ID string
        """
        # Create deterministic hash from event data
        data = f"{event.symbol}_{event.side}_{event.qty}_{event.ts.isoformat()}"
        hash_obj = hashlib.md5(data.encode(), usedforsecurity=False)  # Not for security
        hash_hex = hash_obj.hexdigest()[:8]

        # Format: trade_YYYYMMDD_HHMMSS_hash
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        return f"trade_{timestamp}_{hash_hex}"


def build_pipeline(
    settings: "ApplicationSettings", bus: EventBus, broker: BrokerGateway
) -> TradingPipeline:
    """
    Build and wire the trading pipeline.

    Args:
        settings: Application configuration
        bus: Event bus instance
        broker: Broker gateway instance

    Returns:
        Configured TradingPipeline instance

    Usage:
        pipeline = build_pipeline(settings, bus, broker)
        # Pipeline handlers are automatically wired
    """
    pipeline = TradingPipeline(settings, bus, broker)

    if settings.enable_event_bus:
        pipeline.wire_handlers()
        logger.info("Trading pipeline built and wired successfully")
    else:
        logger.info("Event bus disabled - pipeline handlers not wired")

    return pipeline
