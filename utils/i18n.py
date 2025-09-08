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
    "system_error": "Системийн алдаа: {error}",
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
    # Regime detection system / Дэглэмийн тогтоолт
    "regime_detector_init": "RegimeDetector эхэллээ: идэвхтэй={active}, босго={thresholds}",
    "regime_config_not_found": "Дэглэмийн тохиргоо олдсонгүй: {path}, анхдагч утгуудыг ашиглана",
    "regime_config_load_error": "Дэглэмийн тохиргоо ачаалахад алдаа: {error}, анхдагч утгуудыг ашиглана",
    "regime_candles_insufficient": "ATR тооцоход ханш дутагдалтай: {count} < {required}",
    "regime_detection": "Дэглэм тогтоох [{symbol}]: norm_ATR={norm_atr:.6f}, ret_vol={ret_vol:.6f}, түүхий={raw_regime}, тогтвортой={stable_regime}",
    "regime_detection_disabled": "Дэглэм тогтоох идэвхгүй, анхдагч дэглэм ашиглана",
    "regime_candles_insufficient_warn": "Дэглэм тогтооход ханш дутагдалтай: {count}",
    "regime_detection_failed": "Дэглэм тогтоох алдаатай {symbol}: {error}",
    "regime_atr_invalid_price": "Буруу одоогийн үнэ: {price}",
    "regime_atr_error": "Нормчлагдсан ATR тооцох алдаа: {error}",
    "regime_return_vol_error": "Буцаагийн хэлбэлзэл тооцох алдаа: {error}",
    "regime_stability": "Дэглэмийн тогтвортой байдал: {current} хадгалах (тууштай={consistency:.2f} < {threshold})",
    "regime_unknown": "Үл мэдэгдэх дэглэм: {regime}, анхдагч дэглэм ашиглана",
    # Order lifecycle management / Захиалгын амьдралын мөчлөг
    "orderbook_initialized": "OrderBook өгөгдлийн сантай эхэллээ: {db_path}",
    "order_created_pending": "Хүлээгдэж буй захиалга үүсгэв: {coid} {side} {qty} {symbol}",
    "order_accepted": "Захиалга хүлээн авагдсан: {coid} → {broker_id} статус={status}",
    "order_cancel_requested": "Захиалга цуцлах хүсэлт илгээгдсэн: {coid}",
    "order_cancel_failed": "Захиалга цуцлах амжилтгүй: Захиалга олдсонгүй: {coid}",
    "order_stop_update_failed": "Stop шинэчлэх амжилтгүй: Захиалга олдсонгүй: {coid}",
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
