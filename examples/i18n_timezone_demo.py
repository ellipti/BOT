#!/usr/bin/env python3
"""
Example demonstrating i18n and timezone usage in the trading system.
Shows how to use Mongolian localization and Ulaanbaatar timezone.
"""
import logging
from datetime import datetime

from config.settings import get_settings
from utils.i18n import alert_message, get_message, log_message, t
from utils.timez import fmt_ts, fmt_ts_compact, fmt_ts_short, now_str, today_str, ub_now


# Configure logging with Mongolian messages
def setup_logging():
    """Setup logging with localized messages"""
    settings = get_settings()

    # Create logger
    logger = logging.getLogger("trading_bot")
    logger.setLevel(logging.INFO)

    # Create formatter with timezone
    formatter = logging.Formatter(
        f"%(asctime)s [{settings.TZ}] %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    return logger


def demonstrate_i18n():
    """Demonstrate internationalization features"""
    settings = get_settings()
    logger = setup_logging()

    print("=== Монгол хэлний мессеж жишээнүүд ===")

    # System status messages
    print("\n1. Системийн статус:")
    print(f"   {t('system_startup')}")
    print(f"   {t('system_ready')}")
    print(f"   {t('connection_restored')}")

    # Trading messages
    print("\n2. Арилжааны мессежүүд:")
    print(f"   {t('order_placed', symbol='XAUUSD', side='BUY', qty='0.1')}")
    print(f"   {t('order_filled', symbol='XAUUSD', filled_qty='0.1', price='2650.50')}")
    print(
        f"   {t('position_opened', symbol='XAUUSD', side='BUY', qty='0.1', price='2650.50')}"
    )
    print(f"   {t('stop_loss_hit', symbol='XAUUSD', price='2640.00')}")

    # Risk management messages
    print("\n3. Эрсдэлийн удирдлага:")
    print(f"   {t('risk_level_high', level=75)}")
    print(f"   {t('daily_limit_reached', limit_type='арилжаа')}")
    print(f"   {t('circuit_breaker_triggered', reason='дараалсан 5 алдагдал')}")
    print(f"   {t('cooldown_active', remaining_min=15)}")

    # Alert messages
    print("\n4. Анхааруулга:")
    print(f"   {t('sla_breach', metric='хоцролт', value='150ms', threshold='100ms')}")
    print(f"   {t('health_degraded', status='доголдолтой', reason='MT5 холболт')}")
    print(f"   {t('latency_high', latency=250, threshold=100)}")

    # Backup and DR messages
    print("\n5. Нөөцлөлт/Сэргээлт:")
    print(f"   {t('backup_started', backup_type='бүрэн')}")
    print(f"   {t('backup_completed', file_path='backup_20250908.tar.gz', size_mb=15)}")
    print(f"   {t('dr_drill_started', drill_id='DR_20250908_001')}")
    print(f"   {t('dr_drill_completed', status='амжилттай')}")


def demonstrate_timezone():
    """Demonstrate timezone handling"""
    settings = get_settings()

    print(f"\n=== Цагийн бүсийн жишээнүүд ({settings.TZ}) ===")

    # Current time in different formats
    current_time = ub_now(settings)
    print("\n1. Одоогийн цаг:")
    print(f"   Бүрэн:    {fmt_ts(current_time, settings)}")
    print(f"   Богино:   {fmt_ts_short(current_time, settings)}")
    print(f"   Хураангуй: {fmt_ts_compact(current_time, settings)}")
    print(f"   Өнөөдөр:  {today_str(settings)}")

    # Compare with UTC
    utc_time = datetime.utcnow()
    print("\n2. UTC-тай харьцуулах:")
    print(f"   UTC цаг:      {utc_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"   УБ цаг:       {fmt_ts(current_time, settings)}")
    print(f"   Ялгаа:       {current_time.utcoffset()}")


def demonstrate_logging_integration():
    """Demonstrate logging with localized messages"""
    settings = get_settings()
    logger = setup_logging()

    print("\n=== Лог интеграци жишээ ===")

    # Log messages with timestamps in UB timezone
    current_time = ub_now(settings)

    # Simulate trading events with localized messages
    logger.info(f"[{fmt_ts_short(current_time, settings)}] {t('system_startup')}")
    logger.info(
        f"[{fmt_ts_short(current_time, settings)}] {t('feed_connected', feed_type='MT5')}"
    )
    logger.info(
        f"[{fmt_ts_short(current_time, settings)}] {t('order_placed', symbol='XAUUSD', side='BUY', qty='0.1')}"
    )
    logger.warning(
        f"[{fmt_ts_short(current_time, settings)}] {t('latency_high', latency=150, threshold=100)}"
    )
    logger.error(
        f"[{fmt_ts_short(current_time, settings)}] {t('connection_lost', reason='сүлжээний алдаа')}"
    )


def demonstrate_conditional_localization():
    """Demonstrate conditional localization based on settings"""
    settings = get_settings()

    print(f"\n=== Нөхцөлт орчуулга (LOCALE={settings.LOCALE}) ===")

    # Example of using different messages based on locale
    messages = [
        ("system_ready", {}),
        ("order_placed", {"symbol": "XAUUSD", "side": "BUY", "qty": "0.1"}),
        ("risk_level_high", {"level": 80}),
        ("backup_completed", {"file_path": "backup.tar.gz", "size_mb": 25}),
    ]

    print("\nМонгол хэл (mn):")
    for key, params in messages:
        msg = get_message(key, locale="mn", **params)
        print(f"   {key}: {msg}")

    print("\nАнгли хэл (en) - fallback:")
    for key, params in messages:
        msg = get_message(key, locale="en", **params)
        print(f"   {key}: {msg}")


if __name__ == "__main__":
    print("🌏 Монгол хэлний дэмжлэг болон цагийн бүс тохиргоо")
    print("=" * 60)

    # Run demonstrations
    demonstrate_i18n()
    demonstrate_timezone()
    demonstrate_logging_integration()
    demonstrate_conditional_localization()

    print("\n✅ Бүх жишээ амжилттай ажиллалаа!")
    print("📝 config/settings.py дээр LOCALE болон TZ тохируулна уу")
    print("🔧 utils/i18n.py дээр шинэ мессежүүд нэмнэ үү")
    print("⏰ utils/timez.py ашиглан цагийн бүс харуулна уу")
