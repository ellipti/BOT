import logging, os
from logging.handlers import RotatingFileHandler

class TelegramLogHandler(logging.Handler):
    def emit(self, record):
        try:
            from services.telegram_notify import send_text
            msg = self.format(record)
            send_text(f"🚨 {msg}")
        except Exception:
            pass

def setup_logger(name: str = "bot", level: int = logging.INFO) -> logging.Logger:
    os.makedirs("logs", exist_ok=True)
    fmt = "%(asctime)s | %(levelname)-7s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Console
    ch = logging.StreamHandler()
    ch.setLevel(level)
    ch.setFormatter(logging.Formatter(fmt))

    # Rotating file (5MB x 7)
    fh = RotatingFileHandler("logs/bot.log", maxBytes=5*1024*1024, backupCount=7, encoding="utf-8")
    fh.setLevel(level)
    fh.setFormatter(logging.Formatter(fmt))

    if not logger.handlers:
        logger.addHandler(ch)
        logger.addHandler(fh)
        # ERROR↑ үед Telegram-руу
        th = TelegramLogHandler(level=logging.ERROR)
        th.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
        logger.addHandler(th)
    return logger
