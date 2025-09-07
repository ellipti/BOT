"""
Advanced Logging System (Upgrade #05)
JSON formatting + Rotating files + ELK/Sentry ready + Retention management + Security log redaction
"""

import json
import logging
import logging.handlers
import re
import traceback
from datetime import UTC, datetime
from pathlib import Path

from config.settings import get_settings

# Security: Sensitive keys and patterns for log redaction
SENSITIVE_KEYS = [
    "token",
    "api_key",
    "password",
    "secret",
    "mt5_password",
    "telegram_token",
    "te_api_key",
    "bot_token",
    "auth_token",
    "access_token",
    "refresh_token",
    "private_key",
    "certificate",
    "credential",
    "login",
    "pin",
    "otp",
]

# Compile regex patterns for sensitive data detection
REDACTION_PATTERNS = [
    re.compile(rf"({key}\s*[=:]\s*)([A-Za-z0-9_\-:.+/]{{6,}})", re.IGNORECASE)
    for key in SENSITIVE_KEYS
]

# Additional patterns for common secret formats
REDACTION_PATTERNS.extend(
    [
        # API keys (typical formats)
        re.compile(
            r"(['\"]?[a-z_]*api[_-]?key['\"]?\s*[=:]\s*['\"]?)([A-Za-z0-9_\-]{20,})['\"]?",
            re.IGNORECASE,
        ),
        # Bearer tokens
        re.compile(r"(bearer\s+)([A-Za-z0-9_\-\.]{20,})", re.IGNORECASE),
        # JWT tokens (basic pattern)
        re.compile(r"(eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+)(\.[A-Za-z0-9_\-]*)?"),
        # URLs with embedded credentials
        re.compile(r"(https?://[^:]+:)([^@]{4,})(@[^\s]+)", re.IGNORECASE),
    ]
)


class RedactionFilter(logging.Filter):
    """
    Security filter to redact sensitive information from log messages
    Protects against accidental logging of secrets, tokens, and passwords
    """

    def __init__(self):
        super().__init__()
        self.redaction_count = 0

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Filter and redact sensitive information from log record

        Args:
            record: The log record to filter

        Returns:
            True (always allow record, but modify sensitive content)
        """
        try:
            # Get the original message
            original_msg = record.getMessage()
            redacted_msg = original_msg

            # Apply redaction patterns
            for pattern in REDACTION_PATTERNS:
                if pattern.search(redacted_msg):
                    self.redaction_count += 1
                    redacted_msg = pattern.sub(r"\1****", redacted_msg)

            # Update the record message if redaction occurred
            if redacted_msg != original_msg:
                record.msg = redacted_msg
                record.args = ()  # Clear args since we've already formatted the message

                # Add a flag to indicate redaction occurred
                record.redacted = True

        except Exception:
            # If redaction fails, don't break logging - just continue
            pass

        return True

    def get_redaction_stats(self) -> dict:
        """Get statistics about redaction activity"""
        return {
            "total_redactions": self.redaction_count,
            "patterns_active": len(REDACTION_PATTERNS),
        }


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
    Setup advanced logging system with JSON formatting, rotation, and security redaction

    Features:
    - JSON structured logs for ELK Stack compatibility
    - Daily rotation with retention management
    - Separate error/warning level filtering
    - Telegram alerts for critical errors
    - Console output with readable formatting
    - Security redaction of sensitive information

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

    # Create redaction filter instance
    redaction_filter = RedactionFilter()

    # === Console Handler (Human-readable format) ===
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_format = (
        "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"
    )
    console_formatter = logging.Formatter(console_format, datefmt="%Y-%m-%d %H:%M:%S")
    console_handler.setFormatter(console_formatter)
    console_handler.addFilter(redaction_filter)  # Add security redaction
    logger.addHandler(console_handler)

    # === JSON File Handler (All levels, daily rotation) ===
    json_handler = DailyRotatingJsonHandler(
        base_filename=str(log_dir / "app.json"),
        retention_days=settings.logging.log_retention_days,
    )
    json_handler.setLevel(logging.DEBUG)  # Capture all levels in JSON
    json_formatter = JsonFormatter(include_trace=True)
    json_handler.setFormatter(json_formatter)
    json_handler.addFilter(redaction_filter)  # Add security redaction
    logger.addHandler(json_handler)

    # === Error/Warning File Handler (Separate file for alerts) ===
    error_handler = DailyRotatingJsonHandler(
        base_filename=str(log_dir / "errors.json"),
        retention_days=settings.logging.log_retention_days,
    )
    error_handler.setLevel(logging.WARNING)
    error_formatter = JsonFormatter(include_trace=True)
    error_handler.setFormatter(error_formatter)
    error_handler.addFilter(redaction_filter)  # Add security redaction
    logger.addHandler(error_handler)

    # === Telegram Alert Handler (Critical errors only) ===
    if settings.telegram.error_alerts and settings.telegram.bot_token:
        telegram_handler = TelegramLogHandler(level=logging.ERROR)
        telegram_format = (
            "%(levelname)s | %(name)s:%(funcName)s:%(lineno)d | %(message)s"
        )
        telegram_formatter = logging.Formatter(telegram_format)
        telegram_handler.setFormatter(telegram_formatter)
        telegram_handler.addFilter(redaction_filter)  # Add security redaction
        logger.addHandler(telegram_handler)

    # Log system initialization
    logger.info(
        "Дэвшилтэт лог систем эхэллээ (with security redaction)",
        extra={
            "log_level": level,
            "json_logs": True,
            "rotation": "daily",
            "retention_days": settings.logging.log_retention_days,
            "telegram_alerts": settings.telegram.error_alerts,
            "security_redaction": True,
            "redaction_patterns": len(REDACTION_PATTERNS),
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
