"""
Trading Pipeline - Event-driven flow coordination with Risk Management
Wires together the trading pipeline: Signal → Validation → Risk → Order → Execution
Integrates ATR-based position sizing and stop-loss/take-profit calculations
"""

import hashlib
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from core.broker import BrokerGateway, OrderRequest, OrderType, Side
from core.events import (
    EventBus,
    Filled,
    OrderPlaced,
    Rejected,
    RiskApproved,
    SignalDetected,
    Validated,
)
from core.executor import IdempotentOrderExecutor, make_coid
from core.sizing.sizing import (
    calc_lot_by_risk,
    calc_sl_tp_by_atr,
    fetch_atr,
    get_account_equity,
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

        # Initialize idempotent executor
        self.executor = IdempotentOrderExecutor(
            broker=broker, db_path=settings.idempotency_db
        )

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
        Handle validated signal - perform ATR-based risk management and position sizing.

        Args:
            event: Validated event with validation result
        """
        if not event.is_valid:
            logger.info(f"Skipping invalid signal: {event.reason}")
            return

        logger.info(f"Processing validated signal: {event.symbol} {event.side}")

        try:
            # Get account equity for position sizing
            equity = get_account_equity()
            if not equity:
                logger.error("Cannot retrieve account equity for position sizing")
                return

            # Get MT5 timeframe constant (M30)
            timeframe = 30  # MT5.TIMEFRAME_M30 equivalent

            # Fetch ATR for risk calculations
            atr = fetch_atr(event.symbol, timeframe, self.settings.trading.atr_period)
            if not atr:
                logger.error(f"Cannot calculate ATR for {event.symbol}")
                return

            # Check minimum ATR requirement
            if atr < self.settings.trading.min_atr:
                logger.warning(
                    f"ATR {atr:.5f} below minimum {self.settings.trading.min_atr} - skipping signal"
                )
                return

            # Get current market price (placeholder - would come from broker)
            # TODO: Get real current price from broker
            current_price = 2500.0  # Placeholder price

            # Calculate SL/TP based on ATR
            sl, tp = calc_sl_tp_by_atr(
                event.side,
                current_price,
                atr,
                self.settings.trading.stop_loss_multiplier,
                self.settings.trading.take_profit_multiplier,
            )

            # Get symbol info for position sizing (placeholder)
            # TODO: Get real symbol info from broker
            class MockSymbolInfo:
                def __init__(self):
                    self.trade_tick_size = 0.01
                    self.trade_tick_value = 1.0  # $1 per tick per lot
                    self.volume_min = 0.01
                    self.volume_max = 100.0
                    self.volume_step = 0.01

            symbol_info = MockSymbolInfo()

            # Calculate position size based on risk management
            qty = calc_lot_by_risk(
                symbol_info,
                current_price,
                sl,
                equity,
                self.settings.trading.risk_percentage,
            )

            risk_amount = equity * self.settings.trading.risk_percentage

            logger.info(
                f"ATR-based risk calculations: equity=${equity:.2f}, "
                f"ATR={atr:.5f}, risk_amount=${risk_amount:.2f}, "
                f"calculated_lots={qty:.3f}, SL={sl:.5f}, TP={tp:.5f}"
            )

            # Emit risk approval with calculated parameters
            risk_approved = RiskApproved(
                symbol=event.symbol,
                side=event.side,
                qty=qty,
                sl=sl,
                tp=tp,
                strategy_id="atr_pipeline",  # Updated strategy ID
            )

            logger.debug(
                f"Risk approved with ATR sizing: {event.symbol} {event.side} "
                f"qty={qty:.3f} sl={sl:.5f} tp={tp:.5f} (ATR={atr:.5f})"
            )
            self.bus.publish(risk_approved)

        except Exception as e:
            logger.error(f"ATR-based risk management failed for {event.symbol}: {e}")
            # Fallback to reject the signal
            return

    def _handle_risk_approved(self, event: RiskApproved) -> None:
        """
        Handle risk approval - compose order request.

        Args:
            event: RiskApproved event with position sizing and risk parameters
        """
        logger.info(
            f"Processing risk approval: {event.symbol} {event.side} qty={event.qty}"
        )

        # Generate deterministic client order ID
        ts_bucket = datetime.utcnow().strftime("%Y%m%d_%H%M")  # Minute-level bucket
        client_order_id = make_coid(
            symbol=event.symbol,
            side=event.side,
            strategy_id=event.strategy_id,
            ts_bucket=ts_bucket,
        )

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
        Handle order placement - execute through idempotent broker executor.

        Args:
            event: OrderPlaced event ready for broker execution
        """
        logger.info(
            f"Order placement received: {event.client_order_id} {event.symbol} {event.side}"
        )

        # Convert OrderPlaced to OrderRequest
        order_request = OrderRequest(
            client_order_id=event.client_order_id,
            symbol=event.symbol,
            side=Side.BUY if event.side == "BUY" else Side.SELL,
            qty=event.qty,
            order_type=OrderType.MARKET,
            sl=event.sl,
            tp=event.tp,
        )

        # Execute through idempotent executor
        try:
            result = self.executor.place(order_request)

            if result.accepted:
                # Emit Filled event (placeholder - real fill would come from broker)
                filled = Filled(
                    broker_order_id=result.broker_order_id or "unknown",
                    client_order_id=event.client_order_id,
                    price=2500.0,  # Placeholder price
                    qty=event.qty,
                )
                self.bus.publish(filled)
                logger.info(
                    f"Order filled: {event.client_order_id} -> {result.broker_order_id}"
                )

            else:
                # Emit Rejected event
                rejected = Rejected(
                    client_order_id=event.client_order_id,
                    reason=result.reason or "Unknown rejection",
                )
                self.bus.publish(rejected)
                logger.warning(
                    f"Order rejected: {event.client_order_id} - {result.reason}"
                )

        except Exception as e:
            # Emit Rejected on execution error
            rejected = Rejected(
                client_order_id=event.client_order_id,
                reason=f"Execution error: {str(e)}",
            )
            self.bus.publish(rejected)
            logger.error(f"Order execution failed: {event.client_order_id} - {e}")

        # Log order details for monitoring
        logger.info(
            f"Order processing complete: symbol={event.symbol}, side={event.side}, "
            f"qty={event.qty}, sl={event.sl}, tp={event.tp}"
        )

    def get_idempotent_stats(self) -> dict:
        """Get statistics from the idempotent executor"""
        return {
            "recent_orders": len(self.executor.get_sent_orders(limit=10)),
            "executor": str(self.executor),
        }


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
