#!/usr/bin/env python3
"""
Standalone Telegram bot for testing commands and interaction
Run this script to start the bot in polling mode
"""

import os
import sys
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from services.telegram_v2 import build_application
from settings import settings
from core.logger import get_logger

logger = get_logger("telegram_bot")

async def main():
    """Main bot runner"""
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not configured in settings")
        return 1
        
    logger.info("Starting Telegram bot...")
    
    try:
        # Build application with handlers
        app = build_application(settings.TELEGRAM_BOT_TOKEN)
        
        # Add custom error handler
        async def error_handler(update, context):
            logger.error(f"Bot error: {context.error}")
            
        app.add_error_handler(error_handler)
        
        # Start polling
        logger.info("Bot is running. Press Ctrl+C to stop.")
        await app.run_polling(
            close_loop_on_interrupt=True,
            drop_pending_updates=True
        )
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        return 0
    except Exception as e:
        logger.error(f"Bot error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
