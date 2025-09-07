# services/telegram.py
from __future__ import annotations

import os

import requests
from settings import settings

from core.logger import get_logger

logger = get_logger("telegram")


class TelegramClient:
    def __init__(
        self, token: str | None = None, chat_id: str | None = None, timeout: int = 10
    ):
        self.token = token or settings.TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or settings.TELEGRAM_CHAT_ID
        self.timeout = timeout
        if not self.token or not self.chat_id:
            logger.info("TelegramClient: no token/chat_id — sending disabled.")

    def send(self, text: str) -> bool:
        if not (self.token and self.chat_id):
            logger.warning("Telegram send skipped: missing token/chat_id.")
            return False
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            r = requests.post(
                url, json={"chat_id": self.chat_id, "text": text}, timeout=self.timeout
            )
            if r.ok:
                return True
            logger.error(f"Telegram send failed: {r.status_code} | {r.text}")
        except Exception as e:
            logger.exception(f"Telegram send exception: {e}")
        return False

    def send_photo(self, photo_path: str, caption: str | None = None) -> bool:
        """Send a photo to the configured chat. Returns True on success."""
        if not (self.token and self.chat_id):
            logger.warning("Telegram send_photo skipped: missing token/chat_id.")
            return False
        if not os.path.exists(photo_path):
            logger.error("Telegram send_photo: file not found: %s", photo_path)
            return False
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendPhoto"
            with open(photo_path, "rb") as f:
                files = {"photo": f}
                data = {"chat_id": self.chat_id}
                if caption:
                    data["caption"] = caption
                r = requests.post(url, data=data, files=files, timeout=self.timeout)
            if r.ok:
                return True
            logger.error(f"Telegram send_photo failed: {r.status_code} | {r.text}")
        except Exception as e:
            logger.exception(f"Telegram send_photo exception: {e}")
        return False
