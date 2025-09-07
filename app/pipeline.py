"""
Trading Pipeline - Event-driven flow coordination with Risk Management and Reconciliation
Wires together the trading pipeline: Signal → Validation → Risk → Order → Execution → Reconciliation
Integrates ATR-based position sizing and MT5 deal history reconciliation
"""

import hashlib
import logging
import time
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
from core.executor.reconciler import (
    get_current_tick_price,
    get_deal_price,
    wait_for_fill,
)
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
        Handle order placement with reconciliation - execute through idempotent broker executor
        and wait for fill confirmation via MT5 deal history.

        Args:
            event: OrderPlaced event ready for broker execution
        """
        start_time = time.time()
        client_order_id = event.client_order_id

        logger.info(
            f"📤 Order placement received: {client_order_id} {event.symbol} {event.side}"
        )

        # Convert OrderPlaced to OrderRequest
        order_request = OrderRequest(
            client_order_id=client_order_id,
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
            broker_latency = time.time() - start_time

            logger.info(
                f"🏦 Broker response for {client_order_id}: accepted={result.accepted}, "
                f"broker_order_id={result.broker_order_id}, reason='{result.reason}', "
                f"latency={broker_latency:.3f}s"
            )

            if result.accepted:
                # Order accepted by broker - now wait for fill confirmation
                reconciliation_start = time.time()

                # Get MT5 module for reconciliation
                mt5 = None
                if hasattr(self.broker, "get_mt5_module"):
                    try:
                        mt5 = self.broker.get_mt5_module()
                    except Exception as e:
                        logger.warning(f"Cannot get MT5 module for reconciliation: {e}")

                if mt5:
                    # Wait for fill using deal history reconciliation
                    logger.info(f"🔍 Starting reconciliation for {client_order_id}")

                    filled, deal_ticket = wait_for_fill(
                        mt5=mt5,
                        client_order_id=client_order_id,
                        symbol=event.symbol,
                        timeout_sec=3.0,  # 3 second timeout
                        poll=0.25,  # 250ms polling
                    )

                    reconciliation_latency = time.time() - reconciliation_start
                    total_latency = time.time() - start_time

                    if filled:
                        # Get deal execution price
                        fill_price = None
                        if deal_ticket:
                            fill_price = get_deal_price(mt5, deal_ticket, event.symbol)

                        # Fallback to current market price if deal price unavailable
                        if fill_price is None:
                            fill_price = get_current_tick_price(
                                mt5, event.symbol, event.side
                            )

                        # Final fallback to placeholder (should rarely happen)
                        if fill_price is None:
                            fill_price = 2500.0  # Placeholder
                            logger.warning(
                                f"Using placeholder fill price for {client_order_id}"
                            )

                        # Emit Filled event with reconciled data
                        filled_event = Filled(
                            broker_order_id=deal_ticket
                            or result.broker_order_id
                            or "unknown",
                            client_order_id=client_order_id,
                            price=fill_price,
                            qty=event.qty,
                        )
                        self.bus.publish(filled_event)

                        logger.info(
                            f"✅ Order filled: {client_order_id} -> deal #{deal_ticket} "
                            f"@ ${fill_price:.5f}, reconciliation={reconciliation_latency:.3f}s, "
                            f"total={total_latency:.3f}s"
                        )

                    else:
                        # Reconciliation timeout - order may still be pending
                        logger.warning(
                            f"⏱️ Reconciliation timeout for {client_order_id} after "
                            f"{reconciliation_latency:.3f}s - emitting Rejected"
                        )

                        rejected = Rejected(
                            client_order_id=client_order_id,
                            reason=f"RECONCILIATION_TIMEOUT after {reconciliation_latency:.3f}s",
                        )
                        self.bus.publish(rejected)

                else:
                    # No MT5 module available - emit basic Filled event
                    logger.warning(
                        f"No MT5 reconciliation available for {client_order_id} - "
                        f"emitting basic Filled event"
                    )

                    filled_event = Filled(
                        broker_order_id=result.broker_order_id or "unknown",
                        client_order_id=client_order_id,
                        price=2500.0,  # Placeholder price
                        qty=event.qty,
                    )
                    self.bus.publish(filled_event)

            else:
                # Order rejected by broker
                total_latency = time.time() - start_time

                logger.warning(
                    f"❌ Order rejected by broker: {client_order_id} - {result.reason}, "
                    f"latency={total_latency:.3f}s"
                )

                rejected = Rejected(
                    client_order_id=client_order_id,
                    reason=result.reason or "Unknown rejection",
                )
                self.bus.publish(rejected)

        except Exception as e:
            # Execution error
            total_latency = time.time() - start_time

            logger.error(
                f"💥 Order execution failed: {client_order_id} - {e}, "
                f"latency={total_latency:.3f}s"
            )

            rejected = Rejected(
                client_order_id=client_order_id,
                reason=f"Execution error: {str(e)}",
            )
            self.bus.publish(rejected)

        # Log final order details for monitoring
        final_latency = time.time() - start_time
        logger.info(
            f"📊 Order processing complete: symbol={event.symbol}, side={event.side}, "
            f"qty={event.qty}, sl={event.sl}, tp={event.tp}, "
            f"total_latency={final_latency:.3f}s"
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
