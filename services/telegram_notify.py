"""
Enhanced Telegram notification system with python-telegram-bot v20+ support
Supports multiple recipients and async operations with sync wrappers
"""

import asyncio
from typing import Optional, Union, List
from pathlib import Path

from services.telegram_v2 import TelegramBotV2, send_text_sync, send_photo_sync
from settings import settings
from core.logger import get_logger

logger = get_logger("telegram_notify")

# Global bot instance
_bot_instance: Optional[TelegramBotV2] = None

def get_bot() -> Optional[TelegramBotV2]:
    """Get or create global bot instance"""
    global _bot_instance
    if _bot_instance is None and settings.TELEGRAM_BOT_TOKEN:
        # Multi-recipient support: TELEGRAM_CHAT_IDS (comma-separated) or fallback to TELEGRAM_CHAT_ID
        chat_ids = getattr(settings, "TELEGRAM_CHAT_IDS", None) or settings.TELEGRAM_CHAT_ID
        _bot_instance = TelegramBotV2(settings.TELEGRAM_BOT_TOKEN, chat_ids)
    return _bot_instance

def _enabled() -> bool:
    """Check if Telegram notifications are enabled"""
    bot = get_bot()
    return bot is not None and bot.bot is not None and bool(bot.chat_ids)

def send_text(text: str, parse_mode: Optional[str] = None) -> None:
    """Send text message to all configured recipients"""
    if not _enabled():
        logger.debug("Telegram notifications disabled")
        return
        
    success = send_text_sync(text, parse_mode)
    if success:
        logger.info(f"Telegram message sent: {text[:50]}{'...' if len(text) > 50 else ''}")
    else:
        logger.warning("Failed to send Telegram message")

def send_photo(path: Union[str, Path], caption: str = "") -> None:
    """Send photo to all configured recipients"""
    if not _enabled():
        logger.debug("Telegram notifications disabled")
        return
        
    success = send_photo_sync(path, caption or None)
    if success:
        logger.info(f"Telegram photo sent: {Path(path).name}")
    else:
        logger.warning(f"Failed to send Telegram photo: {path}")

def send_error_alert(error_msg: str, context: Optional[str] = None) -> None:
    """Send error alert with emoji and formatting"""
    if not _enabled():
        return
        
    full_msg = f"🚨 ERROR ALERT\n\n{error_msg}"
    if context:
        full_msg += f"\n\nContext: {context}"
        
    send_text(full_msg)

def send_trade_notification(symbol: str, action: str, lot: float, entry: float, 
                          sl: float, tp: float, reason: str, ticket: Optional[str] = None,
                          dry_run: bool = True) -> None:
    """Send formatted trade notification"""
    if not _enabled():
        return
        
    status_emoji = "🧪" if dry_run else "💰"
    action_emoji = "📈" if action == "BUY" else "📉"
    
    msg = (
        f"{status_emoji} TRADE EXECUTED {action_emoji}\n\n"
        f"Symbol: {symbol}\n"
        f"Action: {action}\n"
        f"Lot Size: {lot}\n"
        f"Entry: ${entry:.2f}\n"
        f"Stop Loss: ${sl:.2f}\n" 
        f"Take Profit: ${tp:.2f}\n"
        f"Reason: {reason}"
    )
    
    if ticket:
        msg += f"\nTicket: {ticket}"
        
    if dry_run:
        msg += "\n\n⚠️ DRY RUN MODE"
        
    send_text(msg)

def send_bot_status(status: str, details: Optional[str] = None) -> None:
    """Send bot status update"""
    if not _enabled():
        return
        
    msg = f"🤖 Bot Status: {status}"
    if details:
        msg += f"\n\n{details}"
        
    send_text(msg)

# Async versions for direct use
async def send_text_async(text: str, parse_mode: Optional[str] = None) -> bool:
    """Async version of send_text"""
    bot = get_bot()
    if not bot:
        return False
    return await bot.send_message(text, parse_mode)

async def send_photo_async(path: Union[str, Path], caption: Optional[str] = None) -> bool:
    """Async version of send_photo"""
    bot = get_bot()
    if not bot:
        return False
    return await bot.send_photo(path, caption)
