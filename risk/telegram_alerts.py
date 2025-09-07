#!/usr/bin/env python3
"""
Risk Governance Telegram Alerts
Upgrade #07 - Эрсдэлийн засаглалын Telegram анхааруулга
"""

import asyncio
from datetime import UTC, datetime

try:
    from telegram import Bot
    from telegram.error import TelegramError

    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False

from config.settings import get_settings
from logging_setup import setup_advanced_logger

logger = setup_advanced_logger(__name__)


class RiskAlertManager:
    """Эрсдэлийн засаглалын анхааруулга илгээх"""

    def __init__(self):
        self.settings = get_settings()
        self.bot: Bot | None = None
        self.chat_ids: list[str] = []

        if not TELEGRAM_AVAILABLE:
            logger.warning(
                "python-telegram-bot суугаагүй байна - Telegram alert ажиллахгүй"
            )
            return

        self._initialize_bot()

    def _initialize_bot(self):
        """Telegram bot эхлүүлэх"""
        if not self.settings.telegram.bot_token:
            logger.info("Telegram bot token байхгүй - alert систем идэвхгүй")
            return

        try:
            self.bot = Bot(token=self.settings.telegram.bot_token)

            # Chat ID-ууд тохируулах
            if self.settings.telegram.chat_ids:
                self.chat_ids = [
                    chat_id.strip()
                    for chat_id in self.settings.telegram.chat_ids.split(",")
                    if chat_id.strip()
                ]
            elif self.settings.telegram.chat_id:
                self.chat_ids = [self.settings.telegram.chat_id]

            if self.chat_ids:
                logger.info(
                    "Risk alert Telegram bot бэлэн боллоо",
                    extra={"chat_count": len(self.chat_ids)},
                )
            else:
                logger.warning("Chat ID байхгүй - Telegram alert идэвхгүй")
                self.bot = None

        except Exception as e:
            logger.error(
                "Telegram bot эхлүүлэхэд алдаа гарлаа", extra={"error": str(e)}
            )
            self.bot = None

    async def send_risk_alert(self, message: str, level: str = "INFO") -> bool:
        """Эрсдэлийн анхааруулга илгээх"""
        if not self.bot or not self.chat_ids:
            logger.debug("Telegram bot эсвэл chat ID байхгүй")
            return False

        # Emoji нэмэх
        emoji_map = {
            "INFO": "ℹ️",
            "WARNING": "⚠️",
            "ERROR": "❌",
            "CRITICAL": "🚨",
            "SUCCESS": "✅",
        }

        emoji = emoji_map.get(level, "ℹ️")
        formatted_message = f"{emoji} **ЭРСДЭЛИЙН ЗАСАГЛАЛ**\n\n{message}\n\n⏰ {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}"

        success_count = 0

        for chat_id in self.chat_ids:
            try:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=formatted_message,
                    parse_mode="Markdown",
                    timeout=self.settings.telegram.timeout_seconds,
                )
                success_count += 1

            except TelegramError as e:
                logger.error(
                    "Telegram мессеж илгээхэд алдаа гарлаа",
                    extra={"chat_id": chat_id, "error": str(e)},
                )
            except Exception as e:
                logger.error(
                    "Санаандгүй алдаа Telegram илгээхэд",
                    extra={"chat_id": chat_id, "error": str(e)},
                )

        if success_count > 0:
            logger.info(
                "Risk alert амжилттай илгээлээ",
                extra={
                    "success_count": success_count,
                    "total_chats": len(self.chat_ids),
                    "level": level,
                },
            )
            return True
        else:
            logger.error("Risk alert илгээх бүрэн амжилтгүй боллоо")
            return False

    def send_risk_alert_sync(self, message: str, level: str = "INFO") -> bool:
        """Синхрон горимд эрсдэлийн анхааруулга илгээх"""
        if not self.bot:
            return False

        try:
            # Шинэ event loop үүсгэх эсвэл байгааг ашиглах
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Event loop ажиллаж байвал task үүсгэх
                    asyncio.create_task(self.send_risk_alert(message, level))
                    return True
                else:
                    return loop.run_until_complete(self.send_risk_alert(message, level))
            except RuntimeError:
                # Event loop байхгүй бол шинээр үүсгэх
                return asyncio.run(self.send_risk_alert(message, level))

        except Exception as e:
            logger.error(
                "Синхрон Telegram alert илгээхэд алдаа гарлаа", extra={"error": str(e)}
            )
            return False

    def format_risk_metrics_alert(self, metrics: dict, alert_type: str) -> str:
        """Эрсдэлийн хэмжүүрийн анхааруулга бэлтгэх"""
        messages = {
            "daily_limit_warning": "📊 **ӨДРИЙН ХЯЗГААР АНХААРУУЛГА**",
            "weekly_limit_warning": "📈 **7 ХОНОГИЙН ХЯЗГААР АНХААРУУЛГА**",
            "circuit_breaker_triggered": "🚨 **CIRCUIT BREAKER ИДЭВХЖЛЭЭ**",
            "high_risk_alert": "⚠️ **ӨНДӨР ЭРСДЭЛИЙН АНХААРУУЛГА**",
            "consecutive_loss_alert": "📉 **ДАРААЛСАН АЛДАГДЛЫН АНХААРУУЛГА**",
        }

        header = messages.get(alert_type, "📋 **ЭРСДЭЛИЙН МЭДЭЭЛЭЛ**")

        message_parts = [header]

        # Өдрийн хэмжүүр
        if "daily_loss" in metrics:
            message_parts.append("📅 **Өдрийн мэдээлэл:**")
            message_parts.append(f"   • Алдагдал: {metrics['daily_loss']:.2f}%")
            message_parts.append(f"   • Арилжаа: {metrics.get('daily_trades', 0)} удаа")

        # 7 хоногийн хэмжүүр
        if "weekly_loss" in metrics:
            message_parts.append("📊 **7 хоногийн мэдээлэл:**")
            message_parts.append(f"   • Алдагдал: {metrics['weekly_loss']:.2f}%")
            message_parts.append(
                f"   • Арилжаа: {metrics.get('weekly_trades', 0)} удаа"
            )

        # Нэмэлт мэдээлэл
        if "consecutive_losses" in metrics:
            message_parts.append(
                f"🔄 **Дараалсан алдагдал:** {metrics['consecutive_losses']} удаа"
            )

        if "risk_level" in metrics:
            message_parts.append(
                f"📈 **Эрсдэлийн түвшин:** {metrics['risk_level'].upper()}"
            )

        if "next_trade_allowed" in metrics:
            message_parts.append(
                f"⏳ **Дараагийн арилжаа:** {metrics['next_trade_allowed']}"
            )

        return "\n".join(message_parts)


# Глобал хувьсагч instance
_risk_alert_manager: RiskAlertManager | None = None


def get_risk_alert_manager() -> RiskAlertManager:
    """Risk alert manager-ын instance авах"""
    global _risk_alert_manager
    if _risk_alert_manager is None:
        _risk_alert_manager = RiskAlertManager()
    return _risk_alert_manager


def send_risk_alert(message: str, level: str = "INFO") -> bool:
    """Хялбар функц risk alert илгээхэд"""
    manager = get_risk_alert_manager()
    return manager.send_risk_alert_sync(message, level)
