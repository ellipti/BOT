# services/chart_tasks.py
"""
Chart rendering task handlers for async workqueue processing.
Handles chart generation requests without blocking the main trading loop.
"""

import os
import time
from datetime import UTC, datetime, timezone
from pathlib import Path
from typing import Any, Optional

from config.settings import get_settings
from core.logger import get_logger
from core.mt5_client import MT5Client
from observability.metrics import inc, observe
from services.chart_renderer import render_chart_with_overlays
from services.telegram_notify import send_error_alert, send_photo

# Get settings instance
settings = get_settings()

logger = get_logger("chart_tasks")


def render_chart(payload: dict[str, Any]) -> None:
    """
    Async chart rendering handler for WorkQueue.

    Payload format:
    {
        "symbol": str,              # Trading symbol (e.g., "XAUUSD")
        "timeframe": str,           # MT5 timeframe (e.g., "M30")
        "out_path": str,            # Relative output path
        "title": str,               # Chart title (optional)
        "bars_count": int,          # Number of bars to render (default: 200)
        "overlays": dict,           # Chart overlays (optional)
        "send_telegram": bool,      # Send to Telegram after rendering (default: False)
        "telegram_caption": str     # Telegram caption (optional)
    }
    """
    start_time = time.time()

    try:
        # Extract required parameters
        symbol = payload.get("symbol")
        timeframe = payload.get("timeframe", "M30")
        out_path = payload.get("out_path")

        if not symbol or not out_path:
            raise ValueError(
                f"Missing required parameters: symbol={symbol}, out_path={out_path}"
            )

        logger.info(f"Starting chart render: {symbol} {timeframe} -> {out_path}")

        # Optional parameters with defaults
        title = payload.get("title")
        bars_count = payload.get("bars_count", 200)
        overlays = payload.get("overlays", {})
        send_telegram = payload.get("send_telegram", False)
        telegram_caption = payload.get("telegram_caption", "")

        # Create MT5 client for data fetching
        # Note: This creates a new connection per task - could be optimized with pooling
        mt5c = MT5Client()

        # Connect and fetch data
        if not mt5c.connect():
            raise RuntimeError("Failed to connect to MT5 for chart rendering")

        try:
            # Fetch OHLCV data
            logger.debug(f"Fetching {bars_count} bars of {symbol} {timeframe}")
            df = mt5c.get_rates(symbol, timeframe, count=bars_count)

            if df.empty:
                raise ValueError(f"No data available for {symbol} {timeframe}")

            logger.debug(f"Fetched {len(df)} bars (requested {bars_count})")

            # Render chart
            actual_out_path = render_chart_with_overlays(
                df=df,
                overlays=overlays,
                out_path=out_path,
                title=title or f"{symbol} {timeframe}",
            )

            # Metrics
            render_time_ms = (time.time() - start_time) * 1000
            observe(
                "chart_render_duration_ms",
                render_time_ms,
                symbol=symbol,
                timeframe=timeframe,
            )
            inc("charts_rendered_total", symbol=symbol, timeframe=timeframe)

            logger.info(
                f"Chart rendered successfully: {actual_out_path} ({render_time_ms:.1f}ms)"
            )

            # Send to Telegram if requested
            if send_telegram and _telegram_enabled():
                try:
                    telegram_start = time.time()

                    caption = telegram_caption or f"📊 {symbol} {timeframe} Chart"
                    send_photo(actual_out_path, caption=caption)

                    telegram_time_ms = (time.time() - telegram_start) * 1000
                    observe("telegram_send_duration_ms", telegram_time_ms, type="chart")
                    inc("telegram_charts_sent_total", symbol=symbol)

                    logger.info(f"Chart sent to Telegram ({telegram_time_ms:.1f}ms)")

                except Exception as e:
                    logger.error(f"Failed to send chart to Telegram: {e}")
                    inc(
                        "telegram_send_errors_total",
                        type="chart",
                        error=str(type(e).__name__),
                    )
                    # Don't raise - chart rendering was successful

        finally:
            mt5c.disconnect()

    except Exception as e:
        # Record error metrics
        error_time_ms = (time.time() - start_time) * 1000
        observe(
            "chart_render_duration_ms",
            error_time_ms,
            symbol=payload.get("symbol", "unknown"),
            timeframe=payload.get("timeframe", "unknown"),
            status="error",
        )
        inc("chart_render_errors_total", error=str(type(e).__name__))

        logger.error(f"Chart rendering failed after {error_time_ms:.1f}ms: {e}")
        logger.debug(f"Failed payload: {payload}")

        # Send error alert if enabled
        if settings.TELEGRAM_ERROR_ALERTS:
            try:
                symbol = payload.get("symbol", "unknown")
                send_error_alert(
                    f"Chart rendering failed for {symbol}: {str(e)}", "Chart Tasks"
                )
            except Exception as alert_error:
                logger.error(f"Failed to send error alert: {alert_error}")

        # Re-raise to let WorkQueue handle the failure
        raise


def generate_report(payload: dict[str, Any]) -> None:
    """
    Async report generation handler for WorkQueue.

    Payload format:
    {
        "report_type": str,         # Type of report ("daily", "performance", etc.)
        "symbol": str,              # Trading symbol (optional, for symbol-specific reports)
        "date": str,                # Report date in YYYY-MM-DD format (optional)
        "output_path": str,         # Where to save the report
        "send_telegram": bool,      # Send to Telegram after generation (default: False)
        "telegram_caption": str     # Telegram caption (optional)
    }
    """
    start_time = time.time()

    try:
        # Extract parameters
        report_type = payload.get("report_type", "unknown")
        symbol = payload.get("symbol")
        report_date = payload.get("date")
        output_path = payload.get("output_path")
        send_telegram = payload.get("send_telegram", False)
        telegram_caption = payload.get("telegram_caption", "")

        if not output_path:
            raise ValueError("Missing required parameter: output_path")

        logger.info(f"Starting report generation: {report_type} -> {output_path}")

        # Create output directory
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # Generate report based on type
        if report_type == "daily":
            _generate_daily_report(output_path, symbol, report_date)
        elif report_type == "performance":
            _generate_performance_report(output_path, symbol)
        else:
            # Generic report placeholder
            _generate_generic_report(output_path, report_type, payload)

        # Metrics
        generation_time_ms = (time.time() - start_time) * 1000
        observe(
            "report_generation_duration_ms",
            generation_time_ms,
            report_type=report_type,
            symbol=symbol or "all",
        )
        inc("reports_generated_total", report_type=report_type)

        logger.info(
            f"Report generated successfully: {output_path} ({generation_time_ms:.1f}ms)"
        )

        # Send to Telegram if requested
        if send_telegram and _telegram_enabled():
            try:
                telegram_start = time.time()

                caption = telegram_caption or f"📋 {report_type.title()} Report"
                # Assuming it's a text file - could be enhanced to handle different formats
                with open(output_path, encoding="utf-8") as f:
                    content = f.read()

                from services.telegram_notify import send_text

                send_text(f"{caption}\n\n```\n{content}\n```")

                telegram_time_ms = (time.time() - telegram_start) * 1000
                observe("telegram_send_duration_ms", telegram_time_ms, type="report")
                inc("telegram_reports_sent_total", report_type=report_type)

                logger.info(f"Report sent to Telegram ({telegram_time_ms:.1f}ms)")

            except Exception as e:
                logger.error(f"Failed to send report to Telegram: {e}")
                inc(
                    "telegram_send_errors_total",
                    type="report",
                    error=str(type(e).__name__),
                )

    except Exception as e:
        # Record error metrics
        error_time_ms = (time.time() - start_time) * 1000
        observe(
            "report_generation_duration_ms",
            error_time_ms,
            report_type=payload.get("report_type", "unknown"),
            symbol=payload.get("symbol", "unknown"),
            status="error",
        )
        inc("report_generation_errors_total", error=str(type(e).__name__))

        logger.error(f"Report generation failed after {error_time_ms:.1f}ms: {e}")
        logger.debug(f"Failed payload: {payload}")

        # Send error alert if enabled
        if settings.TELEGRAM_ERROR_ALERTS:
            try:
                report_type = payload.get("report_type", "unknown")
                send_error_alert(
                    f"Report generation failed ({report_type}): {str(e)}",
                    "Report Tasks",
                )
            except Exception as alert_error:
                logger.error(f"Failed to send error alert: {alert_error}")

        # Re-raise to let WorkQueue handle the failure
        raise


def _generate_daily_report(
    output_path: str, symbol: str | None, date: str | None
) -> None:
    """Generate a daily trading summary report"""
    report_date = date or datetime.now(UTC).strftime("%Y-%m-%d")

    # Placeholder report generation - could be enhanced with actual trading data
    report_content = f"Daily Trading Report - {report_date}\n"
    report_content += "=" * 50 + "\n\n"

    if symbol:
        report_content += f"Symbol: {symbol}\n"

    report_content += f"Generated at: {datetime.now(UTC).isoformat()}\n"
    report_content += "\n[Report content would be generated from trading database]\n"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report_content)


def _generate_performance_report(output_path: str, symbol: str | None) -> None:
    """Generate a performance analysis report"""
    report_content = "Performance Report\n"
    report_content += "=" * 50 + "\n\n"

    if symbol:
        report_content += f"Symbol: {symbol}\n"

    report_content += f"Generated at: {datetime.now(UTC).isoformat()}\n"
    report_content += "\n[Performance metrics would be calculated here]\n"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report_content)


def _generate_generic_report(
    output_path: str, report_type: str, payload: dict[str, Any]
) -> None:
    """Generate a generic report for unknown types"""
    report_content = f"{report_type.title()} Report\n"
    report_content += "=" * 50 + "\n\n"
    report_content += f"Generated at: {datetime.now(UTC).isoformat()}\n"
    report_content += f"Payload: {payload}\n"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report_content)


def _telegram_enabled() -> bool:
    """Check if Telegram notifications are enabled"""
    return bool(
        settings.TELEGRAM_BOT_TOKEN
        and (settings.TELEGRAM_CHAT_ID or settings.TELEGRAM_CHAT_IDS)
    )
