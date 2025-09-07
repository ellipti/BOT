"""
Enhanced Telegram bot commands with observability integration.

Provides comprehensive bot status commands using metrics and health checks.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any

from telegram import Update
from telegram.ext import ContextTypes

from observability.health import check_health
from observability.metrics import get_metrics

logger = logging.getLogger(__name__)


async def enhanced_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Enhanced /status command showing comprehensive bot status.

    Provides:
    - Health check results
    - Trading metrics summary
    - Recent activity
    - Alert status
    """
    try:
        # Run health check
        health_data = await asyncio.get_event_loop().run_in_executor(None, check_health)

        # Get metrics summary
        metrics = get_metrics().get_all_metrics()

        # Build status message
        status_emoji = {"ok": "✅", "degraded": "⚠️", "down": "❌", "error": "💥"}

        overall_status = health_data.get("status", "unknown")
        status_icon = status_emoji.get(overall_status, "❓")

        # Format message
        msg_lines = [
            f"🤖 **Bot Status Report** {status_icon}",
            "",
            f"📊 **Overall Status:** {overall_status.upper()}",
            f"🕐 **Updated:** {datetime.now().strftime('%H:%M:%S')}",
            "",
            "🔌 **Connections:**",
        ]

        # MT5 Connection
        mt5_status = (
            "✅ Connected" if health_data.get("mt5_connected") else "❌ Disconnected"
        )
        msg_lines.append(f"  • MT5: {mt5_status}")

        # Database
        db_status = "✅ OK" if health_data.get("idempotency_db_ok") else "❌ Error"
        msg_lines.append(f"  • Database: {db_status}")

        # Trading Activity
        msg_lines.extend(["", "📈 **Trading:**"])

        positions_count = health_data.get("positions_count", 0)
        positions_status = (
            f"{positions_count} open position{'s' if positions_count != 1 else ''}"
        )
        msg_lines.append(f"  • Positions: {positions_status}")

        # Get metrics if available
        orders_placed = 0
        if "counters" in metrics and "orders_placed" in metrics["counters"]:
            orders_placed = sum(metrics["counters"]["orders_placed"].values())

        msg_lines.append(f"  • Orders placed: {orders_placed}")

        # Event processing
        event_lag = health_data.get("event_lag_sec", 0)
        if event_lag < 10:
            lag_status = f"✅ {event_lag}s"
        elif event_lag < 60:
            lag_status = f"⚠️ {event_lag}s"
        else:
            lag_status = f"❌ {event_lag}s"

        msg_lines.extend(["", "⚡ **Performance:**", f"  • Event lag: {lag_status}"])

        # Add latency info if available
        if "histograms" in metrics:
            for metric_name in ["fill_latency_ms", "broker_latency_ms"]:
                if metric_name in metrics["histograms"]:
                    for label_key, data in metrics["histograms"][metric_name].items():
                        if data["count"] > 0:
                            avg_ms = data["sum"] / data["count"]
                            msg_lines.append(
                                f"  • {metric_name.replace('_', ' ').title()}: {avg_ms:.0f}ms avg"
                            )

        # Alerts and errors
        error_count = 0
        if "counters" in metrics and "errors_total" in metrics["counters"]:
            error_count = sum(metrics["counters"]["errors_total"].values())

        if error_count > 0:
            msg_lines.extend(
                ["", "🚨 **Alerts:**", f"  • Recent errors: {error_count}"]
            )

        # Footer
        msg_lines.extend(
            [
                "",
                "💡 Use /metrics for detailed metrics",
                "🔍 Use /health for health details",
            ]
        )

        # Send response
        status_text = "\n".join(msg_lines)
        await update.message.reply_text(status_text, parse_mode="Markdown")

        logger.debug(f"Status command served to chat {update.effective_chat.id}")

    except Exception as e:
        logger.error(f"Status command failed: {e}")
        await update.message.reply_text(
            "❌ **Status Check Failed**\n"
            f"Error: {str(e)}\n"
            "Please try again or contact support.",
            parse_mode="Markdown",
        )


async def metrics_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show detailed metrics summary."""
    try:
        metrics = get_metrics().get_all_metrics()

        msg_lines = ["📊 **Metrics Summary**", ""]

        # Counters
        if metrics.get("counters"):
            msg_lines.append("📈 **Counters:**")
            for name, labels_dict in metrics["counters"].items():
                total = sum(labels_dict.values())
                msg_lines.append(f"  • {name}: {total}")

        # Gauges
        if metrics.get("gauges"):
            msg_lines.append("")
            msg_lines.append("📏 **Gauges:**")
            for name, labels_dict in metrics["gauges"].items():
                for label_key, value in labels_dict.items():
                    label_suffix = (
                        "" if label_key == "__default__" else f" ({label_key})"
                    )
                    msg_lines.append(f"  • {name}{label_suffix}: {value}")

        # Histograms
        if metrics.get("histograms"):
            msg_lines.append("")
            msg_lines.append("📊 **Histograms:**")
            for name, labels_dict in metrics["histograms"].items():
                for label_key, data in labels_dict.items():
                    if data["count"] > 0:
                        avg = data["sum"] / data["count"]
                        label_suffix = (
                            "" if label_key == "__default__" else f" ({label_key})"
                        )
                        msg_lines.append(
                            f"  • {name}{label_suffix}: {data['count']} samples, avg={avg:.2f}"
                        )

        if len(msg_lines) == 2:  # Only header
            msg_lines.append("No metrics available yet.")

        metrics_text = "\n".join(msg_lines)
        await update.message.reply_text(metrics_text, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Metrics command failed: {e}")
        await update.message.reply_text(f"❌ Metrics error: {str(e)}")


async def health_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show detailed health check results."""
    try:
        health_data = await asyncio.get_event_loop().run_in_executor(None, check_health)

        status_emoji = {"ok": "✅", "degraded": "⚠️", "down": "❌", "error": "💥"}

        overall_status = health_data.get("status", "unknown")
        status_icon = status_emoji.get(overall_status, "❓")

        msg_lines = [
            f"🏥 **Health Check Results** {status_icon}",
            "",
            f"**Overall Status:** {overall_status.upper()}",
            f"**Timestamp:** {health_data.get('timestamp', 'N/A')}",
            "",
        ]

        # Individual checks
        checks = health_data.get("checks", {})
        for check_name, check_result in checks.items():
            status = check_result.get("status", "unknown")
            icon = status_emoji.get(status, "❓")
            message = check_result.get("message", "No details")

            msg_lines.extend(
                [f"**{check_name.title()} Check:** {icon}", f"  {message}", ""]
            )

        health_text = "\n".join(msg_lines)
        await update.message.reply_text(health_text, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Health command failed: {e}")
        await update.message.reply_text(f"❌ Health check error: {str(e)}")


async def quick_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quick one-line status for frequent checks."""
    try:
        health_data = await asyncio.get_event_loop().run_in_executor(None, check_health)

        status = health_data.get("status", "unknown")
        mt5_connected = health_data.get("mt5_connected", False)
        positions = health_data.get("positions_count", 0)

        # Quick status emojis
        status_icons = {"ok": "✅", "degraded": "⚠️", "down": "❌"}
        icon = status_icons.get(status, "❓")

        mt5_icon = "🔗" if mt5_connected else "❌"

        quick_msg = (
            f"{icon} Status: {status.upper()} | "
            f"{mt5_icon} MT5: {'ON' if mt5_connected else 'OFF'} | "
            f"📊 Positions: {positions} | "
            f"🕐 {datetime.now().strftime('%H:%M')}"
        )

        await update.message.reply_text(quick_msg)

    except Exception as e:
        logger.error(f"Quick status command failed: {e}")
        await update.message.reply_text(f"❌ Quick status error: {str(e)}")


async def handle_risk_status_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Handle /risk command - show RiskGovernorV2 status."""
    try:
        from risk.governor_v2 import RiskGovernorV2

        # Initialize governor (will load current state)
        governor = RiskGovernorV2()
        summary = governor.get_state_summary()

        # Format risk status message
        status_icon = "✅" if summary["can_trade_now"] else "🚫"

        message = f"""🛡️ **Risk Governance Status** {status_icon}

📊 **Trading Session:**
• Trades Today: {summary['trades_today']}/{summary['session_limit']}
• Session Usage: {summary['session_usage_pct']:.1f}%

🔥 **Loss Streak:**
• Consecutive Losses: {summary['consecutive_losses']}
• Cooldown Active: {'Yes' if summary['cooldown_active'] else 'No'}
{f"• Cooldown Remaining: {summary['cooldown_remaining_min']:.1f}m" if summary['cooldown_active'] else ""}

📰 **News Blackout:**
• Blackout Active: {'Yes' if summary['blackout_active'] else 'No'}
{f"• Blackout Remaining: {summary['blackout_remaining_min']:.1f}m" if summary['blackout_active'] else ""}

🎯 **Trading Status:**
• Can Trade Now: {'✅ Yes' if summary['can_trade_now'] else '❌ No'}
• Last Trade: {summary['last_trade_ts'][-8:-3] if summary['last_trade_ts'] else 'None'}

📅 **Session:** {summary['current_date']}
"""

        await update.message.reply_text(message, parse_mode="Markdown")
        logger.info(f"Risk status sent to chat {update.effective_chat.id}")

    except Exception as e:
        logger.error(f"Risk status command failed: {e}")
        await update.message.reply_text(f"❌ Risk status error: {str(e)}")


# Enhanced help command with new commands
async def enhanced_help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enhanced help command showing all available commands."""
    help_text = """🆘 **Trading Bot Commands**

📊 **Status & Monitoring:**
/status - Full bot status report
/qs - Quick status (one-line)
/metrics - Detailed metrics summary
/health - Health check results
/risk - RiskGovernorV2 status & limits

🤖 **General:**
/start - Initialize bot
/help - Show this help

💡 **Tips:**
• Use /qs for quick checks
• Use /status for detailed info
• Use /risk to check trading limits
• Bot updates status every 30 seconds
• Contact admin if status shows errors

🔗 **Endpoints:**
• Metrics: http://localhost:9101/metrics
• Health: http://localhost:9101/healthz
"""

    await update.message.reply_text(help_text, parse_mode="Markdown")
