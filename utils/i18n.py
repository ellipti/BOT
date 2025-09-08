# utils/i18n.py
# --------------------------------------------
# Энэ файл нь бүх лог/алертын түлхүүр мессежийг монголоор буулгаж өгнө.
# LOCALE="mn" үед доорх өгүүлбэрүүд ашиглагдана.
# --------------------------------------------
from typing import Any

_MESSAGES_MN: dict[str, str] = {
    # Ерөнхий
    "ok": "OK",
    "degraded": "Бага зэргийн доголдол",
    "down": "Ажиллахгүй",
    # Алертууд
    "sla_breach": "/!\\ SLA зөрчил: {metric} утга={value} босго={threshold}",
    "health_degraded": "Системийн байдал: {status}. Шалтгаан: {reason}",
    "risk_block": "Эрсдэлийн хориг: {reason}",
    "ab_rollback": "A/B туршилтаас буцалт хийгдлээ: {reason}",
    # Захиалгын урсгал
    "order_placed": "Захиалга илгээгдлээ: {symbol} {side} {qty}",
    "order_filled": "Захиалга биелэв: {symbol} {filled_qty} @ {price}",
    "order_cancelled": "Захиалга цуцлагдлаа: {coid}",
    "stop_updated": "Stop шинэчлэгдлээ: {coid} SL={sl} TP={tp}",
    # Эрсдэл/горим
    "risk_regime": "Волатилитийн горим: {symbol} → {regime}",
    # Dashboard/Auth
    "auth_login_ok": "Нэвтрэлт амжилттай",
    "auth_login_fail": "Нэвтрэлт амжилтгүй: буруу эрхийн мэдээлэл",
    "auth_forbidden": "Эрхийн түвшин хүрэхгүй байна",
    # Систем статус
    "system_startup": "Систем эхэлж байна...",
    "system_ready": "Систем бэлэн",
    "system_shutdown": "Систем унтарч байна",
    "connection_lost": "Холболт тасарсан: {reason}",
    "connection_restored": "Холболт сэргэсэн",
    # Trading events
    "position_opened": "Позици нээгдлээ: {symbol} {side} {qty} @ {price}",
    "position_closed": "Позици хаагдлаа: {symbol} P&L={pnl}",
    "stop_loss_hit": "Stop Loss биелэв: {symbol} @ {price}",
    "take_profit_hit": "Take Profit биелэв: {symbol} @ {price}",
    # Risk management
    "daily_limit_reached": "Өдрийн хязгаарт хүрлээ: {limit_type}",
    "cooldown_active": "Cooldown идэвхтэй: {remaining_min} минут үлдсэн",
    "risk_level_high": "Эрсдэлийн түвшин өндөр: {level}%",
    "circuit_breaker_triggered": "Circuit breaker идэвхжлээ: {reason}",
    # Data and feed
    "feed_connected": "Мэдээллийн эх холбогдлоо: {feed_type}",
    "feed_disconnected": "Мэдээллийн эх салгаагдлаа",
    "price_update": "Үнийн шинэчлэлт: {symbol} Bid={bid} Ask={ask}",
    "news_blackout": "Мэдээний хориг: {event} хүртэл {duration}мин",
    # Performance and monitoring
    "latency_high": "Хоцролт өндөр: {latency}ms (босго: {threshold}ms)",
    "memory_usage_high": "Санах ойн хэрэглээ өндөр: {usage}%",
    "cpu_usage_high": "CPU хэрэглээ өндөр: {usage}%",
    # Backup and DR
    "backup_started": "Нөөцлөлт эхэллээ: {backup_type}",
    "backup_completed": "Нөөцлөлт дууслаа: {file_path} ({size_mb}MB)",
    "backup_failed": "Нөөцлөлт амжилтгүй: {error}",
    "restore_started": "Сэргээлт эхэллээ: {backup_file}",
    "restore_completed": "Сэргээлт дууслаа",
    "dr_drill_started": "DR дасгал эхэллээ: {drill_id}",
    "dr_drill_completed": "DR дасгал дууслаа: {status}",
}


def t(key: str, **kwargs: Any) -> str:
    """
    Translate a message key to Mongolian with format parameters.

    Args:
        key: Message key to translate
        **kwargs: Format parameters for the message

    Returns:
        Translated and formatted message
    """
    msg = _MESSAGES_MN.get(key, key)
    try:
        return msg.format(**kwargs)
    except Exception:
        # If formatting fails, return the raw message
        return msg


def get_message(key: str, locale: str = "mn", **kwargs: Any) -> str:
    """
    Get a localized message with optional locale override.

    Args:
        key: Message key to translate
        locale: Locale override (currently only supports 'mn')
        **kwargs: Format parameters for the message

    Returns:
        Localized and formatted message
    """
    if locale == "mn":
        return t(key, **kwargs)
    else:
        # Fallback to English (return key as-is for now)
        # In future, could add _MESSAGES_EN dictionary
        try:
            return key.format(**kwargs) if kwargs else key
        except Exception:
            return key


# Convenience aliases for common use cases
def alert_message(key: str, **kwargs: Any) -> str:
    """Get an alert message in Mongolian"""
    return t(key, **kwargs)


def log_message(key: str, **kwargs: Any) -> str:
    """Get a log message in Mongolian"""
    return t(key, **kwargs)


def ui_message(key: str, **kwargs: Any) -> str:
    """Get a UI message in Mongolian"""
    return t(key, **kwargs)
