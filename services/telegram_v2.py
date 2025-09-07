"""Modern Telegram integration using python-telegram-bot v20+"""

import asyncio
import os
from pathlib import Path

from telegram import Bot, Update
from telegram.error import TelegramError
from telegram.ext import Application, CommandHandler, ContextTypes

from config.settings import get_settings
from core.logger import get_logger

logger = get_logger("telegram_v2")
settings = get_settings()


class TelegramBotV2:
    """Modern Telegram bot client using python-telegram-bot v20+ Application API"""

    def __init__(self, token: str | None = None, chat_ids: str | None = None):
        self.token = token or settings.telegram.bot_token
        # Use the structured chat_ids from settings
        self.chat_ids = self._parse_chat_ids(chat_ids or settings.telegram.chat_ids)
        self.bot: Bot | None = None
        self.application: Application | None = None

        if not self.token:
            logger.warning("No Telegram token provided - bot disabled")
            return

        if not self.chat_ids:
            logger.warning("No chat IDs provided - notifications disabled")
            return

        # Initialize bot
        self.bot = Bot(token=self.token)

    def _parse_chat_ids(self, chat_ids_str: str | None) -> list[int | str]:
        """Parse comma-separated chat IDs"""
        if not chat_ids_str:
            return []

        ids = []
        for chat_id in str(chat_ids_str).split(","):
            chat_id = chat_id.strip()
            if not chat_id:
                continue
            try:
                # Try to parse as integer (numeric chat ID)
                ids.append(int(chat_id))
            except ValueError:
                # Keep as string (username or channel)
                ids.append(chat_id)
        return ids

    async def send_message(self, text: str, parse_mode: str | None = None) -> bool:
        """Send text message to all configured chats"""
        if not (self.bot and self.chat_ids):
            logger.debug("Telegram send_message skipped: bot not configured")
            return False

        success = True
        for chat_id in self.chat_ids:
            try:
                await self.bot.send_message(
                    chat_id=chat_id, text=text, parse_mode=parse_mode
                )
                logger.debug(f"Message sent to {chat_id}")
            except TelegramError as e:
                logger.error(f"Failed to send message to {chat_id}: {e}")
                success = False
        return success

    async def send_photo(
        self, photo_path: str | Path, caption: str | None = None
    ) -> bool:
        """Send photo to all configured chats"""
        if not (self.bot and self.chat_ids):
            logger.debug("Telegram send_photo skipped: bot not configured")
            return False

        photo_path = Path(photo_path)
        if not photo_path.exists():
            logger.error(f"Photo file not found: {photo_path}")
            return False

        success = True
        for chat_id in self.chat_ids:
            try:
                with open(photo_path, "rb") as photo_file:
                    await self.bot.send_photo(
                        chat_id=chat_id, photo=photo_file, caption=caption
                    )
                logger.debug(f"Photo sent to {chat_id}")
            except TelegramError as e:
                logger.error(f"Failed to send photo to {chat_id}: {e}")
                success = False
        return success

    async def send_document(
        self, document_path: str | Path, caption: str | None = None
    ) -> bool:
        """Send document to all configured chats"""
        if not (self.bot and self.chat_ids):
            logger.debug("Telegram send_document skipped: bot not configured")
            return False

        document_path = Path(document_path)
        if not document_path.exists():
            logger.error(f"Document file not found: {document_path}")
            return False

        success = True
        for chat_id in self.chat_ids:
            try:
                with open(document_path, "rb") as doc_file:
                    await self.bot.send_document(
                        chat_id=chat_id, document=doc_file, caption=caption
                    )
                logger.debug(f"Document sent to {chat_id}")
            except TelegramError as e:
                logger.error(f"Failed to send document to {chat_id}: {e}")
                success = False
        return success


def build_application(token: str) -> Application:
    """Build Telegram Application with handlers"""

    async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        await update.message.reply_text(
            "🤖 Trading Bot Online ✅\n"
            "Available commands:\n"
            "/start - Show this message\n"
            "/status - Bot status\n"
            "/help - Help information"
        )

    async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        # This would be enhanced to show actual bot status
        await update.message.reply_text(
            "📊 Bot Status:\n"
            "• Connection: Active\n"
            "• Last trade: N/A\n"
            "• Safety gates: Active\n"
            f"• Chat ID: {update.effective_chat.id}"
        )

    async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        await update.message.reply_text(
            "🆘 Trading Bot Help\n\n"
            "This bot provides automated trading notifications and can respond to basic commands.\n\n"
            "Commands:\n"
            "/start - Initialize bot\n"
            "/status - Check bot status\n"
            "/help - This help message\n\n"
            "The bot will automatically send trade notifications and charts when trades are executed."
        )

    # Build application
    application = Application.builder().token(token).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("help", help_command))

    return application


# Sync wrapper functions for backward compatibility
def send_text_sync(text: str, parse_mode: str | None = None) -> bool:
    """Synchronous wrapper for sending text messages"""
    bot = TelegramBotV2()
    if not (bot.bot and bot.chat_ids):
        return False

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(bot.send_message(text, parse_mode))


def send_photo_sync(photo_path: str | Path, caption: str | None = None) -> bool:
    """Synchronous wrapper for sending photos"""
    bot = TelegramBotV2()
    if not (bot.bot and bot.chat_ids):
        return False

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(bot.send_photo(photo_path, caption))


# Legacy compatibility - maintain old interface
class TelegramClient:
    """Legacy compatibility wrapper"""

    def __init__(
        self,
        token: str | None = None,
        chat_id: str | None = None,
        timeout: int = 10,
    ):
        self.bot_v2 = TelegramBotV2(token, chat_id)

    def send(self, text: str) -> bool:
        """Legacy send method"""
        return send_text_sync(text)

    def send_photo(self, photo_path: str, caption: str | None = None) -> bool:
        """Legacy send_photo method"""
        return send_photo_sync(photo_path, caption)


if __name__ == "__main__":
    """Standalone bot runner for testing"""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable required")
        exit(1)

    app = build_application(token)

    logger.info("Starting Telegram bot...")
    app.run_polling(close_loop_on_interrupt=True)
