"""
Trading Pipeline - Event-driven flow coordination with Risk Management and Reconciliation
Wires together the trading pipeline: Signal → Validation → Risk → Order → Execution → Reconciliation
Integrates ATR-based position sizing and MT5 deal history reconciliation with comprehensive metrics
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
    TradeBlocked,
    TradeClosed,
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
from observability.metrics import inc, observe, set_gauge
from risk.governor_v2 import RiskGovernorV2

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

        # Initialize RiskGovernorV2
        self.risk_governor = RiskGovernorV2()

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

        # Trade lifecycle handlers for RiskGovernorV2
        self.bus.subscribe(TradeClosed, self._handle_trade_closed)
        self.bus.subscribe(TradeBlocked, self._handle_trade_blocked)

        # Order execution handler (placeholder for now)
        self.bus.subscribe(OrderPlaced, self._handle_order_placed)

        logger.info("Pipeline handlers registered successfully")

    def _handle_signal_detected(self, event: SignalDetected) -> None:
        """
        Handle signal detection - perform basic validation and RiskGovernorV2 check.

        Args:
            event: SignalDetected event with trading signal
        """
        # Increment signal counter
        inc("signals_detected", symbol=event.symbol, side=event.side)

        logger.info(
            f"📡 Processing signal: {event.symbol} {event.side} strength={event.strength}"
        )

        # Check RiskGovernorV2 before proceeding
        now = datetime.now()
        can_trade, risk_reason = self.risk_governor.can_trade(now)

        if not can_trade:
            logger.warning(f"🚫 Trade blocked by RiskGovernorV2: {risk_reason}")

            # Publish TradeBlocked event
            blocked_event = TradeBlocked(
                symbol=event.symbol,
                side=event.side,
                reason=risk_reason,
                governor_version="v2",
            )
            self.bus.publish(blocked_event)

            # Increment blocked trades metric
            inc(
                "trades_blocked",
                reason=risk_reason.split("(")[0].strip(),
                symbol=event.symbol,
            )
            return

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

        # Track validation results
        if validated.is_valid:
            inc("signals_validated", symbol=event.symbol, side=event.side)
        else:
            inc("signals_rejected", symbol=event.symbol, reason="validation_failed")

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

        # Track order placement
        inc("orders_placed", symbol=event.symbol, side=event.side)
        set_gauge("current_orders_processing", 1)

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

            # Track broker latency
            observe("broker_latency_ms", broker_latency * 1000, symbol=event.symbol)

            logger.info(
                f"🏦 Broker response for {client_order_id}: accepted={result.accepted}, "
                f"broker_order_id={result.broker_order_id}, reason='{result.reason}', "
                f"latency={broker_latency:.3f}s"
            )

            if result.accepted:
                # Track accepted orders
                inc("orders_accepted", symbol=event.symbol, side=event.side)

                # Order accepted by broker - now wait for fill confirmation
                reconciliation_start = time.time()

                # Get MT5 module for reconciliation
                mt5 = None
                if hasattr(self.broker, "get_mt5_module"):
                    try:
                        mt5 = self.broker.get_mt5_module()
                    except Exception as e:
                        logger.warning(f"Cannot get MT5 module for reconciliation: {e}")
                        inc("errors_total", error_type="mt5_module_access")

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

                    # Track reconciliation latency
                    observe(
                        "reconciliation_latency_ms",
                        reconciliation_latency * 1000,
                        symbol=event.symbol,
                    )
                    observe(
                        "total_latency_ms", total_latency * 1000, symbol=event.symbol
                    )

                    if filled:
                        # Track successful fills
                        inc("orders_filled", symbol=event.symbol, side=event.side)

                        # Get deal execution price
                        fill_price = None
                        if deal_ticket:
                            fill_price = get_deal_price(mt5, deal_ticket, event.symbol)

                        # Fallback to current market price if deal price unavailable
                        if fill_price is None:
                            fill_price = get_current_tick_price(
                                mt5, event.symbol, event.side
                            )
                            inc("fill_price_fallbacks", fallback_type="market_price")

                        # Final fallback to placeholder (should rarely happen)
                        if fill_price is None:
                            fill_price = 2500.0  # Placeholder
                            inc("fill_price_fallbacks", fallback_type="placeholder")
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
                        # Track reconciliation timeouts
                        inc("orders_timeout", symbol=event.symbol, side=event.side)

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
                    inc("orders_no_reconciliation", symbol=event.symbol)

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
                # Track rejected orders
                inc(
                    "orders_rejected",
                    symbol=event.symbol,
                    side=event.side,
                    reason="broker_rejected",
                )

                # Order rejected by broker
                total_latency = time.time() - start_time
                observe(
                    "total_latency_ms",
                    total_latency * 1000,
                    symbol=event.symbol,
                    outcome="rejected",
                )

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
            # Track execution errors
            inc("errors_total", error_type="order_execution")
            inc(
                "orders_rejected",
                symbol=event.symbol,
                side=event.side,
                reason="execution_error",
            )

            # Execution error
            total_latency = time.time() - start_time
            observe(
                "total_latency_ms",
                total_latency * 1000,
                symbol=event.symbol,
                outcome="error",
            )

            logger.error(
                f"💥 Order execution failed: {client_order_id} - {e}, "
                f"latency={total_latency:.3f}s"
            )

            rejected = Rejected(
                client_order_id=client_order_id,
                reason=f"Execution error: {str(e)}",
            )
            self.bus.publish(rejected)

        finally:
            # Always reset processing gauge
            set_gauge("current_orders_processing", 0)

        # Log final order details for monitoring
        final_latency = time.time() - start_time
        observe("final_latency_ms", final_latency * 1000, symbol=event.symbol)

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

    def _handle_trade_closed(self, event: TradeClosed) -> None:
        """
        Handle trade closure - update RiskGovernorV2 with trade result.

        Args:
            event: TradeClosed event with trade P&L
        """
        now = datetime.now()
        self.risk_governor.on_trade_closed(event.pnl, now)

        logger.info(
            f"💰 Trade closed: PnL={event.pnl}, updated RiskGovernorV2",
            extra={
                "symbol": event.symbol if hasattr(event, "symbol") else "UNKNOWN",
                "pnl": event.pnl,
                "close_reason": (
                    event.close_reason if hasattr(event, "close_reason") else "UNKNOWN"
                ),
            },
        )

        # Update metrics
        inc("trades_closed", result="win" if event.pnl > 0 else "loss")
        observe("trade_pnl", event.pnl)

        # Update governor state metrics
        state = self.risk_governor.get_state_summary()
        set_gauge("consecutive_losses", state["consecutive_losses"])
        set_gauge("session_trades_today", state["trades_today"])

    def _handle_trade_blocked(self, event: TradeBlocked) -> None:
        """
        Handle trade blocked event - send Telegram ops alert.

        Args:
            event: TradeBlocked event with block reason
        """
        logger.warning(
            f"🚫 Trade blocked: {event.symbol} {event.side} - {event.reason}",
            extra={
                "symbol": event.symbol,
                "side": event.side,
                "reason": event.reason,
                "governor_version": event.governor_version,
            },
        )

        # Send Telegram alert (if available)
        try:
            from risk.telegram_alerts import send_risk_alert

            alert_message = (
                f"/!\\ Risk block: {event.reason}\n"
                f"Symbol: {event.symbol}\n"
                f"Side: {event.side}\n"
                f"Time: {event.ts.strftime('%H:%M:%S')}\n"
                f"Governor: {event.governor_version}"
            )

            send_risk_alert(alert_message, level="WARNING")
            logger.info("Risk block alert sent to Telegram")

        except ImportError:
            logger.debug("Telegram alerts not available")
        except Exception as e:
            logger.error(f"Failed to send risk block alert: {e}")

    def apply_news_blackout(self, impact: str) -> None:
        """
        Apply news blackout based on calendar event impact.

        This method should be called by calendar/news handlers when
        high-impact events are detected.

        Args:
            impact: Event impact level ('high', 'medium', 'low')
        """
        now = datetime.now()
        self.risk_governor.apply_news_blackout(impact, now)

        logger.info(
            f"📰 News blackout applied: impact={impact}",
            extra={"impact": impact, "applied_at": now.isoformat()},
        )

        # Update metrics
        inc("news_blackouts_applied", impact=impact)

        # Send Telegram alert
        try:
            from risk.telegram_alerts import send_risk_alert

            state = self.risk_governor.get_state_summary()
            blackout_min = state.get("blackout_remaining_min", 0)

            alert_message = (
                f"/!\\ News blackout: {impact.upper()} impact event\n"
                f"Trading blocked for {blackout_min:.1f} minutes\n"
                f"Applied at: {now.strftime('%H:%M:%S')}"
            )

            send_risk_alert(alert_message, level="INFO")
            logger.info("News blackout alert sent to Telegram")

        except ImportError:
            logger.debug("Telegram alerts not available")
        except Exception as e:
            logger.error(f"Failed to send news blackout alert: {e}")


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
