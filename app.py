import argparse
import glob
import os
import sys
from datetime import UTC, datetime

from config.settings import get_settings
from core.mt5_client import MT5Client
from integrations.calendar import get_calendar_guard_sync
from logging_setup import setup_advanced_logger
from observability import start_httpd
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

# Initialize settings
settings = get_settings()
logger = setup_advanced_logger("trading_bot")


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
    df = mt5c.get_rates(settings.trading.symbol, "M30", count=10)
    if df.empty:
        logger.error(f"Failed to fetch {settings.trading.symbol} rates!")
        return False
    logger.info(f"Successfully fetched {len(df)} bars for {settings.trading.symbol}")

    return True


def run_once():
    # Start observability HTTP server if enabled
    if settings.observability.enable_http_metrics:
        try:
            start_httpd(
                port=settings.observability.metrics_port,
                host=settings.observability.metrics_host,
            )
            logger.info(
                f"📊 Metrics server started on http://{settings.observability.metrics_host}:{settings.observability.metrics_port}"
            )
        except Exception as e:
            logger.error(f"Failed to start metrics server: {e}")

    mt5c = MT5Client()

    if settings.mt5.attach_mode:
        # ATTACH → Connect to the running terminal without credentials
        info = mt5c.connect(path=None, attach_mode=True)
    else:
        # HEADLESS login → Provide all parameters for login
        info = mt5c.connect(
            path=settings.mt5.terminal_path,
            login=settings.mt5.login,
            password=settings.mt5.password,
            server=settings.mt5.server,
            attach_mode=False,
        )

    if not info:
        logger.error(
            "MT5 холбогдож чадсангүй. Terminal нээж login хийсэн эсэхийг шалгана уу."
        )
        return False

    # Handle --diag flag
    if len(sys.argv) > 1 and sys.argv[1] == "--diag":
        success = run_diag(mt5c)
        mt5c.shutdown()
        return success

    # Make sure charts directory exists
    os.makedirs("charts", exist_ok=True)

    # Дансны мэдээлэл харуулах
    snap = mt5c.account_snapshot()
    if not snap:
        logger.error("Failed to get account snapshot!")
        mt5c.shutdown()
        return False

    account_balance = float(snap.get("balance", 0.0))

    # Setup Guard with settings
    guard = Guard(
        symbol=settings.trading.symbol,
        timeframe_min=settings.trading.timeframe_minutes,
        session=settings.trading.session,
        cooldown_mult=settings.trading.cooldown_multiplier,
        min_atr=settings.trading.min_atr,
        risk_pct=settings.trading.risk_percentage,
        sl_mult=settings.trading.stop_loss_multiplier,
        tp_mult=settings.trading.take_profit_multiplier,
        enable_news=True,
        news_window_min=60,
    )

    # Fetch and process data
    df = mt5c.get_rates(settings.trading.symbol, "M30", count=800)
    if df.empty:
        logger.warning(f"{settings.trading.symbol} хосын түүх хоосон байна")
        mt5c.shutdown()
        return False

    # Generate unique timestamp for chart
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")[:-3]
    out_png_rel = f"charts/{settings.trading.symbol}_M30_{ts}.png"

    # Render initial chart
    overlays = {"trendlines": [], "zones": [], "fibonacci": []}
    out_png = render_chart_with_overlays(df.tail(200), overlays, out_png_rel)
    logger.info(f"Chart saved: {out_png}")

    # Compute indicators
    sig = ma_crossover_signal(df)
    last_close = df["close"].iloc[-1]
    a = atr(df, period=20)  # Using standard 20-period ATR
    df["MA20"] = df["close"].rolling(window=20).mean()
    df["MA50"] = df["close"].rolling(window=50).mean()
    ma20 = float(df["MA20"].iloc[-1]) if not df["MA20"].isna().all() else float("nan")
    ma50 = float(df["MA50"].iloc[-1]) if not df["MA50"].isna().all() else float("nan")
    rsi14 = rsi(df["close"], period=14)

    # Base message for logging
    base_msg = f"[{settings.trading.symbol}] close={last_close:.2f} | atr={a:.5f} | signal={sig['signal']} | {sig['reason']}"
    logger.info(base_msg)

    raw_signal = sig["signal"]
    account_equity = float(snap.get("equity", account_balance))
    positions = mt5c.get_positions(settings.trading.symbol)
    open_pos = len(positions) if positions is not None else 0

    # CLI --force имхийг эхэлж шалгах
    if args.force:
        logger.warning(f"--force active: overriding decision -> {args.force}")
        decision = Decision(
            action=args.force,
            reason="CLI_FORCE",
            lot=0.10,
            sl_points=a * guard.sl_mult,
            tp_points=a * guard.tp_mult,
        )
    # Дараа нь .env force-ийг шалгах
    else:
        force = os.getenv("TEST_FORCE_SIDE", "").upper()
        if force in ("BUY", "SELL"):
            logger.warning(f"TEST_FORCE_SIDE active: overriding decision -> {force}")
            decision = Decision(
                action=force,
                reason="TEST_FORCE",
                lot=0.10,
                sl_points=a * guard.sl_mult,
                tp_points=a * guard.tp_mult,
            )
        # Calendar Guard шалгалт - Эдийн засгийн эвентийн blackout window
        elif settings.trading.calendar_enabled:
            # Symbol-аас currency гаргаж авах (жишээ: XAUUSD -> USD)
            symbol_currencies = []
            symbol = settings.trading.symbol.upper()
            if len(symbol) >= 6:
                base_currency = symbol[:3]  # XAU
                quote_currency = symbol[3:6]  # USD
                symbol_currencies = [quote_currency]  # USD-д анхаарах

            calendar_result = get_calendar_guard_sync(symbol_currencies)

            if not calendar_result.allowed:
                logger.warning(f"🗓️ Calendar Guard: {calendar_result.reason}")
                if calendar_result.next_clear_time:
                    remaining_minutes = (
                        calendar_result.next_clear_time - datetime.now(UTC)
                    ).total_seconds() / 60
                    logger.info(
                        f"Дараагийн арилжаа боломжтой: {remaining_minutes:.0f} минутын дараа"
                    )

                decision = Decision(
                    action="NONE",
                    reason=f"Calendar Guard: {calendar_result.reason}",
                    lot=0.0,
                    sl_points=0.0,
                    tp_points=0.0,
                )
            else:
                logger.debug(f"Calendar Guard: {calendar_result.reason}")
                decision = guard.filter_decision(
                    raw_signal,
                    last_close,
                    ma20,
                    ma50,
                    rsi14,
                    a,
                    account_balance,
                    now_utc=datetime.now(UTC),
                    open_positions=open_pos,
                    equity_usd=account_equity,
                )
        else:
            # Calendar Guard идэвхгүй бол хуучин logic
            decision = guard.filter_decision(
                raw_signal,
                last_close,
                ma20,
                ma50,
                rsi14,
                a,
                account_balance,
                now_utc=datetime.now(UTC),
                open_positions=open_pos,
                equity_usd=account_equity,
            )

    logger.info(
        f"[{settings.trading.symbol}] decision={decision.action} | lot={decision.lot} | "
        f"SL={decision.sl_points:.2f} | TP={decision.tp_points:.2f} | reason={decision.reason}"
    )

    if decision.action in ("BUY", "SELL"):
        # Convert stop points to prices
        entry = last_close  # Using last close as entry price hint
        sl_pts = float(decision.sl_points)
        tp_pts = float(decision.tp_points)
        sl_price, tp_price = compute_stops(
            settings.trading.symbol, decision.action, entry, sl_pts, tp_pts
        )

        # Execute with absolute SL/TP prices
        res = place_market(
            symbol=settings.trading.symbol,
            side=decision.action,
            lot=decision.lot,
            sl=sl_price,
            tp=tp_price,
        )

        if res["ok"]:
            guard.mark_trade(decision.action)
            # Өдрийн лимитийн тоолуурыг нэмэгдүүлнэ
            guard.limits.mark_trade(settings.trading.symbol, datetime.now(UTC))
            logger.info("Trade placed and cooldown marked by safety gate.")

            # Аудит CSV
            if settings.TRADE_LOG_ENABLED:
                append_trade_row(
                    symbol=settings.trading.symbol,
                    side=decision.action,
                    lot=res.get("lot"),
                    entry=last_close,
                    sl=(
                        res.get("sl")
                        if res.get("sl") is not None
                        else (
                            last_close - decision.sl_points
                            if decision.action == "BUY"
                            else last_close + decision.sl_points
                        )
                    ),
                    tp=(
                        res.get("tp")
                        if res.get("tp") is not None
                        else (
                            last_close + decision.tp_points
                            if decision.action == "BUY"
                            else last_close - decision.tp_points
                        )
                    ),
                    reason=decision.reason,
                    ticket=res.get("ticket"),
                    dry_run=res.get("dry"),
                )

            # Send trade notification
            t = "DRY RUN" if settings.DRY_RUN else f"TICKET {res['ticket']}"

            # Re-render chart with Entry/SL/TP annotations
            try:
                overlays_anno = overlays.copy()
                overlays_anno["annotate_levels"] = {
                    "entry": last_close,
                    "sl": decision.sl_points,
                    "tp": decision.tp_points,
                }
                out_png_anno = render_chart_with_overlays(
                    df.tail(200),
                    overlays_anno,
                    out_png_rel,
                    f"{settings.trading.symbol} {decision.action}",
                )

                # Send notifications using new system
                send_trade_notification(
                    symbol=settings.trading.symbol,
                    action=decision.action,
                    lot=decision.lot,
                    entry=last_close,
                    sl=sl_price,
                    tp=tp_price,
                    reason=decision.reason,
                    ticket=res.get("ticket"),
                    dry_run=settings.DRY_RUN,
                )
                send_photo(
                    out_png_anno,
                    caption=f"{settings.trading.symbol} {decision.action} {t}",
                )

            except Exception as e:
                logger.exception("Failed to render/send annotated chart: %s", e)
                send_error_alert(
                    f"Chart rendering failed: {str(e)}", "Trade notification"
                )
        else:
            logger.error(f"Ордер биелүүлж чадсангүй (safety gate): {res}")
            # Send error notification
            send_error_alert(
                f"Trade execution failed: {res.get('retcode', 'Unknown error')}",
                f"{settings.trading.symbol} {decision.action}",
            )
    else:
        logger.info("No trade after safety gate.")

    mt5c.shutdown()
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--diag", action="store_true", help="Run diagnostics and exit.")
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
    args = parser.parse_args()

    if args.diag:
        sys.exit(0 if run_once() else 1)
    elif args.teletest:
        send_text("✅ Telegram PING: bot is connected.")
        p = latest_chart_path_for(settings.trading.symbol)
        if p:
            send_photo(p, caption="Latest chart")
        else:
            send_text("ℹ️ No chart file found to attach.")
        sys.exit(0)
    else:
        run_once()
