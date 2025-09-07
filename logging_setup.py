"""
Advanced Logging System (Upgrade #05)
JSON formatting + Rotating files + ELK/Sentry ready + Retention management
"""

import json
import logging
import logging.handlers
import traceback
from datetime import UTC, datetime
from pathlib import Path

from config.settings import get_settings


class JsonFormatter(logging.Formatter):
    """
    JSON formatter for structured logging
    ELK Stack and Sentry compatible
    """

    def __init__(self, include_trace: bool = True):
        super().__init__()
        self.include_trace = include_trace

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        # Base log entry
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "timestamp_iso": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
        }

        # Add process/thread info for debugging
        if record.process:
            log_entry["process_id"] = record.process
        if record.thread:
            log_entry["thread_id"] = record.thread

        # Add exception info if present
        if record.exc_info and self.include_trace:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": (
                    traceback.format_exception(*record.exc_info)
                    if record.exc_info
                    else None
                ),
            }

        # Add extra fields from LogRecord
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in {
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "message",
                "asctime",
            }:
                extra_fields[key] = value

        if extra_fields:
            log_entry["extra"] = extra_fields

        return json.dumps(log_entry, ensure_ascii=False, separators=(",", ":"))


class TelegramLogHandler(logging.Handler):
    """
    Enhanced Telegram log handler with rate limiting and error filtering
    """

    def __init__(self, level: int = logging.ERROR):
        super().__init__(level)
        self.last_error_time = {}
        self.error_cooldown = 300  # 5 minutes cooldown per error type

    def emit(self, record: logging.LogRecord):
        """Send critical logs to Telegram with rate limiting"""
        try:
            # Rate limiting based on error message hash
            error_key = f"{record.levelname}:{record.module}:{record.funcName}"
            current_time = datetime.now().timestamp()

            if error_key in self.last_error_time:
                if current_time - self.last_error_time[error_key] < self.error_cooldown:
                    return  # Skip if within cooldown period

            self.last_error_time[error_key] = current_time

            # Import here to avoid circular imports
            from services.telegram_notify import send_error_alert

            # Format message for Telegram
            msg = self.format(record)
            alert_text = f"🚨 **{record.levelname}** Alert\n\n"
            alert_text += (
                f"**Module:** `{record.module}.{record.funcName}:{record.lineno}`\n"
            )
            alert_text += f"**Message:** {record.getMessage()}\n"
            alert_text += f"**Time:** {datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')}"

            if record.exc_info:
                alert_text += f"\n**Exception:** `{record.exc_info[0].__name__}`"

            send_error_alert(alert_text)

        except Exception:
            # Avoid recursion - don't log errors from the log handler
            pass


class DailyRotatingJsonHandler(logging.handlers.TimedRotatingFileHandler):
    """
    Daily rotating JSON log handler with retention management
    Creates logs/app-YYYY-MM-DD.json files
    """

    def __init__(
        self, base_filename: str, retention_days: int = 30, encoding: str = "utf-8"
    ):
        """
        Args:
            base_filename: Base name for log files (without extension)
            retention_days: Number of days to keep log files
            encoding: File encoding
        """
        log_dir = Path(base_filename).parent
        log_dir.mkdir(exist_ok=True)

        # Use daily rotation
        super().__init__(
            filename=base_filename,
            when="midnight",
            interval=1,
            backupCount=retention_days,
            encoding=encoding,
            utc=True,
        )

        self.retention_days = retention_days

    def namer(self, default_name: str) -> str:
        """Custom naming for rotated files: app-YYYY-MM-DD.json"""
        base_path = Path(self.baseFilename)
        date_str = datetime.now().strftime("%Y-%m-%d")
        return str(base_path.parent / f"{base_path.stem}-{date_str}.json")


def setup_advanced_logger(
    name: str = "bot", level: str | None = None
) -> logging.Logger:
    """
    Setup advanced logging system with JSON formatting and rotation

    Features:
    - JSON structured logs for ELK Stack compatibility
    - Daily rotation with retention management
    - Separate error/warning level filtering
    - Telegram alerts for critical errors
    - Console output with readable formatting

    Args:
        name: Logger name
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Configured logger instance
    """
    settings = get_settings()

    # Determine log level
    if level is None:
        level = settings.logging.log_level.value
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(log_level)

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    # Create logs directory
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # === Console Handler (Human-readable format) ===
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_format = (
        "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"
    )
    console_formatter = logging.Formatter(console_format, datefmt="%Y-%m-%d %H:%M:%S")
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # === JSON File Handler (All levels, daily rotation) ===
    json_handler = DailyRotatingJsonHandler(
        base_filename=str(log_dir / "app.json"),
        retention_days=settings.logging.log_retention_days,
    )
    json_handler.setLevel(logging.DEBUG)  # Capture all levels in JSON
    json_formatter = JsonFormatter(include_trace=True)
    json_handler.setFormatter(json_formatter)
    logger.addHandler(json_handler)

    # === Error/Warning File Handler (Separate file for alerts) ===
    error_handler = DailyRotatingJsonHandler(
        base_filename=str(log_dir / "errors.json"),
        retention_days=settings.logging.log_retention_days,
    )
    error_handler.setLevel(logging.WARNING)
    error_formatter = JsonFormatter(include_trace=True)
    error_handler.setFormatter(error_formatter)
    logger.addHandler(error_handler)

    # === Telegram Alert Handler (Critical errors only) ===
    if settings.telegram.error_alerts and settings.telegram.bot_token:
        telegram_handler = TelegramLogHandler(level=logging.ERROR)
        telegram_format = (
            "%(levelname)s | %(name)s:%(funcName)s:%(lineno)d | %(message)s"
        )
        telegram_formatter = logging.Formatter(telegram_format)
        telegram_handler.setFormatter(telegram_formatter)
        logger.addHandler(telegram_handler)

    # Log system initialization
    logger.info(
        "Дэвшилтэт лог систем эхэллээ",
        extra={
            "log_level": level,
            "json_logs": True,
            "rotation": "daily",
            "retention_days": settings.logging.log_retention_days,
            "telegram_alerts": settings.telegram.error_alerts,
        },
    )

    return logger


def get_logger_with_context(name: str, **context) -> logging.LoggerAdapter:
    """
    Get logger with persistent context data

    Args:
        name: Logger name
        **context: Context data to include in all log messages

    Returns:
        LoggerAdapter with context
    """
    logger = setup_advanced_logger(name)
    return logging.LoggerAdapter(logger, context)


# Legacy compatibility
def setup_logger(name: str = "bot", level: int = logging.INFO) -> logging.Logger:
    """Legacy setup_logger function for backward compatibility"""
    level_name = logging.getLevelName(level)
    return setup_advanced_logger(name, level_name)
