# utils/timez.py
"""
Timezone utilities for handling Ulaanbaatar time zone and localized formatting.
Provides consistent timezone handling across the application.
"""
import zoneinfo
from datetime import datetime, timedelta
from typing import Optional

from config.settings import ApplicationSettings


def ub_now(settings: ApplicationSettings | None = None) -> datetime:
    """
    Get current time in Ulaanbaatar timezone.

    Args:
        settings: Application settings (if None, will create new instance)

    Returns:
        Current datetime in configured timezone
    """
    if settings is None:
        from config.settings import get_settings

        settings = get_settings()

    return datetime.now(zoneinfo.ZoneInfo(settings.TZ))


def fmt_ts(ts: datetime, settings: ApplicationSettings | None = None) -> str:
    """
    Format timestamp in Ulaanbaatar timezone with standard format.

    Args:
        ts: Timestamp to format
        settings: Application settings (if None, will create new instance)

    Returns:
        Formatted timestamp string with timezone
    """
    if settings is None:
        from config.settings import get_settings

        settings = get_settings()

    # Convert to configured timezone
    localized_ts = ts.astimezone(zoneinfo.ZoneInfo(settings.TZ))

    # Standard format: YYYY-MM-DD HH:MM:SS TZ
    return localized_ts.strftime("%Y-%m-%d %H:%M:%S %Z")


def fmt_ts_short(ts: datetime, settings: ApplicationSettings | None = None) -> str:
    """
    Format timestamp in short format (no timezone suffix).

    Args:
        ts: Timestamp to format
        settings: Application settings (if None, will create new instance)

    Returns:
        Short formatted timestamp string
    """
    if settings is None:
        from config.settings import get_settings

        settings = get_settings()

    # Convert to configured timezone
    localized_ts = ts.astimezone(zoneinfo.ZoneInfo(settings.TZ))

    # Short format: YYYY-MM-DD HH:MM:SS
    return localized_ts.strftime("%Y-%m-%d %H:%M:%S")


def fmt_ts_compact(ts: datetime, settings: ApplicationSettings | None = None) -> str:
    """
    Format timestamp in compact format for file names and IDs.

    Args:
        ts: Timestamp to format
        settings: Application settings (if None, will create new instance)

    Returns:
        Compact formatted timestamp string
    """
    if settings is None:
        from config.settings import get_settings

        settings = get_settings()

    # Convert to configured timezone
    localized_ts = ts.astimezone(zoneinfo.ZoneInfo(settings.TZ))

    # Compact format: YYYYMMDD_HHMMSS
    return localized_ts.strftime("%Y%m%d_%H%M%S")


def parse_ts(ts_str: str, settings: ApplicationSettings | None = None) -> datetime:
    """
    Parse timestamp string and return timezone-aware datetime.

    Args:
        ts_str: Timestamp string to parse
        settings: Application settings (if None, will create new instance)

    Returns:
        Parsed timezone-aware datetime
    """
    if settings is None:
        from config.settings import get_settings

        settings = get_settings()

    tz = zoneinfo.ZoneInfo(settings.TZ)

    # Try different timestamp formats
    formats = [
        "%Y-%m-%d %H:%M:%S %Z",  # Full format with timezone
        "%Y-%m-%d %H:%M:%S",  # Standard format
        "%Y-%m-%dT%H:%M:%S",  # ISO format without timezone
        "%Y-%m-%dT%H:%M:%S%z",  # ISO format with timezone offset
        "%Y%m%d_%H%M%S",  # Compact format
    ]

    for fmt in formats:
        try:
            if "%Z" in fmt or "%z" in fmt:
                # Parse with timezone info
                return datetime.strptime(ts_str, fmt)
            else:
                # Parse as naive datetime and localize
                naive_dt = datetime.strptime(ts_str, fmt)
                return naive_dt.replace(tzinfo=tz)
        except ValueError:
            continue

    raise ValueError(f"Unable to parse timestamp: {ts_str}")


def get_trading_day(
    dt: datetime | None = None, settings: ApplicationSettings | None = None
) -> str:
    """
    Get trading day identifier (YYYY-MM-DD) for a given datetime.

    Args:
        dt: Datetime to get trading day for (if None, uses current time)
        settings: Application settings (if None, will create new instance)

    Returns:
        Trading day string in YYYY-MM-DD format
    """
    if settings is None:
        from config.settings import get_settings

        settings = get_settings()

    if dt is None:
        dt = ub_now(settings)
    else:
        # Ensure datetime is in correct timezone
        dt = dt.astimezone(zoneinfo.ZoneInfo(settings.TZ))

    return dt.strftime("%Y-%m-%d")


def is_same_trading_day(
    dt1: datetime, dt2: datetime, settings: ApplicationSettings | None = None
) -> bool:
    """
    Check if two datetimes are on the same trading day.

    Args:
        dt1: First datetime
        dt2: Second datetime
        settings: Application settings (if None, will create new instance)

    Returns:
        True if both datetimes are on the same trading day
    """
    return get_trading_day(dt1, settings) == get_trading_day(dt2, settings)


def seconds_until_next_day(settings: ApplicationSettings | None = None) -> int:
    """
    Get seconds until next trading day starts (midnight in configured timezone).

    Args:
        settings: Application settings (if None, will create new instance)

    Returns:
        Seconds until next day
    """
    if settings is None:
        from config.settings import get_settings

        settings = get_settings()

    now = ub_now(settings)

    # Get next midnight
    next_day = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
        days=1
    )

    return int((next_day - now).total_seconds())


# Convenience functions for common timestamp operations
def now_str(settings: ApplicationSettings | None = None) -> str:
    """Get current timestamp as formatted string"""
    return fmt_ts(ub_now(settings), settings)


def now_compact(settings: ApplicationSettings | None = None) -> str:
    """Get current timestamp in compact format"""
    return fmt_ts_compact(ub_now(settings), settings)


def today_str(settings: ApplicationSettings | None = None) -> str:
    """Get today's trading day string"""
    return get_trading_day(None, settings)
