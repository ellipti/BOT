# app_with_performance.py
"""
Enhanced trading bot with Performance & Workload Isolation.
Demonstrates integration of WorkQueue, latency tracking, and async chart rendering.
"""

import argparse
import glob
import os
import sys
import time
from datetime import UTC, datetime, timezone

import MetaTrader5 as mt5
import pandas as pd

from config.settings import get_settings
from core.events.bus import EventBus
from core.events.types import ChartRequested
from core.logger import setup_advanced_logger
from core.mt5_client import MT5Client
from infra.latency_tracker import (
    increment_loop_count,
    measure_data_fetch,
    measure_decision_making,
    measure_signal_detection,
    measure_trading_loop,
)
from infra.performance_integration import PerformanceManager
from observability.metrics import inc, observe, set_gauge
from safety_gate import Decision, Guard
from services.chart_renderer import render_chart_with_overlays
from services.telegram_notify import (
    send_error_alert,
    send_photo,
    send_text,
    send_trade_notification,
)
from services.trade_logging import append_trade_row
from strategies.baseline import ma_crossover_signal
from strategies.indicators import atr, rsi
from utils.mt5_exec import compute_stops, place_market

# Setup logging
logger = setup_advanced_logger("trading_bot_performance")


def latest_chart_path_for(symbol: str) -> str:
    """Get the path to the most recently saved chart for a symbol."""
    pattern = f"charts/{symbol}_*.png"
    files = glob.glob(pattern)
    if not files:
        return ""
    return max(files, key=os.path.getctime)


def run_diag(mt5c: MT5Client):
    """Test MT5 connectivity and basic data fetching."""
    logger.info("Running diagnostic mode...")

    # Check MT5 connection
    snap = mt5c.account_snapshot()
    if not snap:
        logger.error("MT5 account snapshot failed!")
        return False

    # Test data fetch
    df = mt5c.get_rates(get_settings().trading.symbol, "M30", count=10)
    if df.empty:
        logger.error(f"Failed to fetch {get_settings().trading.symbol} rates!")
        return False
    logger.info(
        f"Successfully fetched {len(df)} bars for {get_settings().trading.symbol}"
    )

    return True


def run_once_with_performance():
    """
    Enhanced main trading loop with performance monitoring and async chart rendering.
    Demonstrates how heavy operations are offloaded to prevent main loop blocking.
    """
    settings = get_settings()

    # Initialize performance system
    event_bus = EventBus()
    performance_manager = PerformanceManager(event_bus=event_bus)

    logger.info("🚀 Starting trading bot with Performance & Workload Isolation")
    logger.info(
        f"⚙️ Workers: {settings.workers}, Async Charts: {settings.enable_async_charts}"
    )

    # Start performance components
    performance_manager.start()

    try:
        # Main trading loop with comprehensive performance tracking
        with measure_trading_loop():
            # Phase 1: Data Fetching with latency measurement
            with measure_data_fetch():
                logger.info("📊 Connecting to MT5 and fetching market data...")

                mt5c = MT5Client()
                if not mt5c.connect():
                    raise RuntimeError("MT5 бэлтгэх шаг алдаатай")

                # Safety guard үүсгэх
                guard = Guard(
                    symbol=settings.trading.symbol,
                    timeframe_min=settings.trading.timeframe_minutes,
                    session=settings.trading.session,
                    cooldown_mult=settings.trading.cooldown_multiplier,
                    min_atr=settings.trading.min_atr,
                    risk_pct=settings.trading.risk_percentage,
                    sl_mult=settings.trading.stop_loss_multiplier,
                    tp_mult=settings.trading.take_profit_multiplier,
                    dry_run=settings.dry_run,
                )

                # OHLCV өгөгдөл татах
                df = mt5c.get_rates(settings.trading.symbol, "M30", count=800)
                if df.empty:
                    logger.warning(f"{settings.trading.symbol} хосын түүх хоосон байна")
                    return False

                # Record data fetch metrics
                observe(
                    "data_fetch_bars_count", len(df), symbol=settings.trading.symbol
                )
                logger.info(f"📈 Fetched {len(df)} bars for {settings.trading.symbol}")

            # Phase 2: Signal Detection with latency measurement
            with measure_signal_detection():
                logger.info("🔍 Analyzing market signals...")

                # Generate unique timestamp for chart
                ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
                out_png_rel = f"charts/{settings.trading.symbol}_M30_{ts}.png"

                # Initial chart rendering - ASYNC if enabled
                overlays = {"annotate_levels": {}}  # Empty initially

                if settings.enable_async_charts:
                    # Submit chart rendering to WorkQueue (non-blocking)
                    logger.info("📊 Submitting initial chart to async queue...")
                    performance_manager.submit_chart_request(
                        symbol=settings.trading.symbol,
                        timeframe="M30",
                        out_path=out_png_rel,
                        title=f"{settings.trading.symbol} Market Analysis",
                        bars_count=200,
                        overlays=overlays,
                        send_telegram=False,  # Don't send initial chart
                    )
                else:
                    # Synchronous rendering (blocks main loop)
                    logger.info("📊 Rendering chart synchronously...")
                    chart_start = time.time()
                    out_png = render_chart_with_overlays(
                        df.tail(200), overlays, out_png_rel
                    )
                    chart_time_ms = (time.time() - chart_start) * 1000
                    observe("sync_chart_render_duration_ms", chart_time_ms)
                    logger.info(f"Chart rendered in {chart_time_ms:.1f}ms: {out_png}")

                # Зүйл судалгаа
                last_close = df["close"].iloc[-1]
                a = atr(df, period=14).iloc[-1]

                # Signal detection
                sig = ma_crossover_signal(
                    df.tail(200), rsi_period=14, rsi_ob=70, rsi_os=30
                )

                # Record signal metrics
                inc(
                    "signals_generated_total",
                    symbol=settings.trading.symbol,
                    signal=sig["signal"],
                )
                observe("market_atr", a, symbol=settings.trading.symbol)
                set_gauge("market_price", last_close, symbol=settings.trading.symbol)

                logger.info(
                    f"📊 Market Analysis: Close={last_close:.2f}, ATR={a:.5f}, Signal={sig['signal']}"
                )

            # Phase 3: Decision Making with latency measurement
            with measure_decision_making():
                logger.info("🤔 Making trading decision...")

                base_msg = f"[{settings.trading.symbol}] close={last_close:.2f} | atr={a:.5f} | signal={sig['signal']} | {sig['reason']}"

                # Хүчин тэнцэл (positions) шалгах
                positions = mt5c.get_positions(settings.trading.symbol)
                logger.info(f"Open positions: {len(positions)}")

                if sig["signal"] == "WAIT":
                    logger.info(f"{base_msg}")
                    send_text(f"⏳ {base_msg}")
                    return True

                # Guard системээр батламж авах
                decision = guard.should_trade(
                    signal=sig["signal"],
                    close_price=last_close,
                    atr_value=a,
                    reason=sig["reason"],
                    open_positions=len(positions),
                )

                # Record decision metrics
                inc(
                    "trading_decisions_total",
                    symbol=settings.trading.symbol,
                    decision=decision.action if decision else "BLOCKED",
                )

            # Phase 4: Order Processing (if decision made)
            if decision and decision.action in ("BUY", "SELL"):
                logger.info("💰 Processing trade order...")

                # This is kept synchronous as it's critical path
                sl_price, tp_price = compute_stops(
                    symbol=settings.trading.symbol,
                    side=decision.action,
                    entry_price=last_close,
                    sl_points=decision.sl_points,
                    tp_points=decision.tp_points,
                    mt5_client=mt5c,
                )

                # Арилжаа хийх
                res = place_market(
                    symbol=settings.trading.symbol,
                    side=decision.action,
                    lot=decision.lot,
                    sl=sl_price,
                    tp=tp_price,
                    mt5_client=mt5c,
                    dry_run=settings.dry_run,
                )

                if res and res.get("success"):
                    logger.info("✅ Trade executed successfully!")
                    inc(
                        "trades_executed_total",
                        symbol=settings.trading.symbol,
                        side=decision.action,
                        dry_run=str(settings.dry_run),
                    )

                    # Audit CSV
                    if settings.trading.trade_log_enabled:
                        append_trade_row(
                            symbol=settings.trading.symbol,
                            side=decision.action,
                            lot=res.get("lot"),
                            entry=last_close,
                            sl=res.get("sl") if res.get("sl") is not None else sl_price,
                            tp=res.get("tp") if res.get("tp") is not None else tp_price,
                            reason=decision.reason,
                            ticket=res.get("ticket"),
                            dry_run=res.get("dry"),
                        )

                    # Annotated chart rendering - ASYNC
                    try:
                        overlays_anno = overlays.copy()
                        overlays_anno["annotate_levels"] = {
                            "entry": last_close,
                            "sl": sl_price,
                            "tp": tp_price,
                        }

                        t = "DRY RUN" if settings.dry_run else f"TICKET {res['ticket']}"
                        chart_title = (
                            f"{settings.trading.symbol} {decision.action} - {t}"
                        )

                        if settings.enable_async_charts:
                            # Async chart with trade annotation
                            logger.info("📊 Submitting trade chart to async queue...")

                            trade_chart_path = (
                                f"charts/{settings.trading.symbol}_trade_{ts}.png"
                            )
                            performance_manager.submit_chart_request(
                                symbol=settings.trading.symbol,
                                timeframe="M30",
                                out_path=trade_chart_path,
                                title=chart_title,
                                bars_count=200,
                                overlays=overlays_anno,
                                send_telegram=True,
                                telegram_caption=f"📈 {decision.action} {settings.trading.symbol} - {t}",
                            )

                            # Also send immediate trade notification
                            send_trade_notification(
                                symbol=settings.trading.symbol,
                                action=decision.action,
                                lot=decision.lot,
                                entry=last_close,
                                sl=sl_price,
                                tp=tp_price,
                                reason=decision.reason,
                                ticket=res.get("ticket"),
                                dry_run=settings.dry_run,
                            )

                        else:
                            # Synchronous chart rendering (blocks main loop)
                            logger.info("📊 Rendering trade chart synchronously...")
                            chart_start = time.time()

                            trade_chart_path = (
                                f"charts/{settings.trading.symbol}_trade_{ts}.png"
                            )
                            out_png_anno = render_chart_with_overlays(
                                df.tail(200),
                                overlays_anno,
                                trade_chart_path,
                                chart_title,
                            )

                            chart_time_ms = (time.time() - chart_start) * 1000
                            observe(
                                "sync_trade_chart_render_duration_ms", chart_time_ms
                            )

                            # Send notifications
                            send_trade_notification(
                                symbol=settings.trading.symbol,
                                action=decision.action,
                                lot=decision.lot,
                                entry=last_close,
                                sl=sl_price,
                                tp=tp_price,
                                reason=decision.reason,
                                ticket=res.get("ticket"),
                                dry_run=settings.dry_run,
                            )
                            send_photo(
                                out_png_anno,
                                caption=f"📈 {decision.action} {settings.trading.symbol} - {t}",
                            )

                            logger.info(
                                f"Trade chart rendered in {chart_time_ms:.1f}ms"
                            )

                    except Exception as e:
                        logger.exception("Failed to render/send trade chart: %s", e)
                        if settings.telegram.error_alerts:
                            send_error_alert(
                                f"Chart rendering failed: {str(e)}",
                                "Trade notification",
                            )
                else:
                    logger.error("❌ Trade execution failed!")
                    inc("trades_failed_total", symbol=settings.trading.symbol)
            else:
                logger.info(f"⏸️ No trade: {base_msg}")
                send_text(f"⏸️ {base_msg}")

        # Increment loop counter for metrics
        increment_loop_count()

        # Log performance stats
        loop_stats = performance_manager.latency_tracker.get_all_stats()
        overall_latency = loop_stats.get("overall", {}).get("rolling_avg_ms", 0)
        queue_size = performance_manager.workqueue.get_queue_size()

        logger.info(
            f"🔄 Trading loop completed in {overall_latency:.1f}ms (queue: {queue_size} tasks)"
        )

        return True

    except Exception as e:
        logger.exception("Trading loop failed: %s", e)
        inc("trading_loop_errors_total", error=str(type(e).__name__))

        if settings.telegram.error_alerts:
            send_error_alert(f"Trading loop error: {str(e)}", "Main Loop")

        return False

    finally:
        # Stop performance system
        logger.info("🛑 Stopping performance system...")
        performance_manager.stop()
        logger.info("✅ Performance system stopped")


def show_performance_metrics():
    """Display current performance metrics from the observability system"""
    from observability.metrics import render_as_text

    print("📊 PERFORMANCE METRICS")
    print("=" * 50)
    print(render_as_text())
    print("=" * 50)


def run_performance_test():
    """Run the comprehensive performance test"""
    from test_performance_workload import test_comprehensive_performance_scenario

    logger.info("🧪 Running comprehensive performance test...")
    try:
        test_comprehensive_performance_scenario()
        logger.info("✅ Performance test completed successfully!")
        return True
    except Exception as e:
        logger.error(f"❌ Performance test failed: {e}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Trading Bot with Performance & Workload Isolation"
    )
    parser.add_argument("--diag", action="store_true", help="Run diagnostics and exit.")
    parser.add_argument(
        "--metrics", action="store_true", help="Show performance metrics and exit."
    )
    parser.add_argument(
        "--perf-test", action="store_true", help="Run performance test and exit."
    )
    parser.add_argument(
        "--teletest",
        action="store_true",
        help="Send a Telegram ping and latest chart, then exit.",
    )
    parser.add_argument(
        "--force",
        choices=["BUY", "SELL"],
        help="Force one-off decision (DRY_RUN recommended)",
    )
    parser.add_argument(
        "--sync-charts",
        action="store_true",
        help="Disable async chart rendering (for comparison)",
    )

    args = parser.parse_args()

    # Override chart settings if requested
    if args.sync_charts:
        settings = get_settings()
        settings.enable_async_charts = False
        logger.info("⚠️ Async chart rendering disabled - running in sync mode")

    if args.diag:
        mt5c = MT5Client()
        success = run_diag(mt5c)
        mt5c.disconnect()
        sys.exit(0 if success else 1)

    elif args.metrics:
        show_performance_metrics()
        sys.exit(0)

    elif args.perf_test:
        success = run_performance_test()
        sys.exit(0 if success else 1)

    elif args.teletest:
        send_text("✅ Telegram PING: Performance-enhanced bot is connected.")
        p = latest_chart_path_for(get_settings().trading.symbol)
        if p:
            send_photo(
                p, caption="Latest chart (with Performance & Workload Isolation)"
            )
        else:
            send_text("ℹ️ No chart file found to attach.")
        sys.exit(0)

    else:
        success = run_once_with_performance()

        # Show final performance summary
        logger.info("\n📊 PERFORMANCE SUMMARY")
        show_performance_metrics()

        sys.exit(0 if success else 1)
