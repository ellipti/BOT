#!/usr/bin/env python3
"""
GA Smoke Test - Mongolian i18n Validation
==========================================

Монгол хэлний i18n системийн GA (General Availability) smoke тест

Шалгах зүйлс:
1. ✓ Эрүүл мэнд - i18n систем ажиллаж байна
2. ✓ Метрик - Telegram алерт монгол хэлээр
3. ✓ Smoke - Лог системүүд монгол хэлээр

Acceptance criteria for D. phase validation.
"""

import logging
import sys
import time
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import our systems
from config.settings import settings
from utils.i18n import alert_message, log_message, t
from utils.timez import fmt_ts, ub_now


# Colors for terminal output
class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    PURPLE = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"
    END = "\033[0m"


def print_header():
    """Толгойн хэсэг хэвлэх"""
    print(f"{Colors.CYAN}{Colors.BOLD}")
    print("=" * 60)
    print("GA SMOKE TEST - MONGOLIAN i18n VALIDATION")
    print("Монгол хэлний i18n системийн ерөнхий хүртээмжийн тест")
    print("=" * 60)
    print(f"{Colors.END}")
    print(f"Огноо: {fmt_ts(ub_now())}")
    print(f"Цагийн бүс: {settings.TZ}")
    print(f"Locale: {settings.LOCALE}")
    print()


def test_health_check():
    """✓ Эрүүл мэнд - i18n систем ажиллаж байна"""
    print(f"{Colors.YELLOW}1. Эрүүл мэнд шалгалт...{Colors.END}")

    try:
        # Test basic translation
        system_msg = t("system_startup")
        expected_mongolian = "Систем эхэлж байна..."

        if system_msg == expected_mongolian:
            print(f"   {Colors.GREEN}✓ Үндсэн орчуулга: {system_msg}{Colors.END}")
        else:
            print(
                f"   {Colors.RED}✗ Үндсэн орчуулга алдаа: '{system_msg}' != '{expected_mongolian}'{Colors.END}"
            )
            return False

        # Test parameterized translation
        order_msg = t("order_placed", symbol="EURUSD", side="BUY", qty=1.0)
        if "Захиалга илгээгдлээ" in order_msg and "EURUSD" in order_msg:
            print(f"   {Colors.GREEN}✓ Параметртэй орчуулга: {order_msg}{Colors.END}")
        else:
            print(
                f"   {Colors.RED}✗ Параметртэй орчуулга алдаа: {order_msg}{Colors.END}"
            )
            return False

        # Test Mongolian characters
        mongolian_chars = ["ө", "ү", "э"]
        has_mongolian = any(char in system_msg for char in mongolian_chars)
        if has_mongolian:
            print(
                f"   {Colors.GREEN}✓ Монгол үсэг дэмжлэг: Зөв ажиллаж байна{Colors.END}"
            )
        else:
            print(f"   {Colors.RED}✗ Монгол үсэг дэмжлэг: Алдаатай{Colors.END}")
            return False

        # Test error handling
        fallback_msg = t("nonexistent_key")
        if fallback_msg == "nonexistent_key":
            print(
                f"   {Colors.GREEN}✓ Алдааны боловсруулалт: Fallback зөв ажиллаж байна{Colors.END}"
            )
        else:
            print(f"   {Colors.RED}✗ Алдааны боловсруулалт: {fallback_msg}{Colors.END}")
            return False

        print(
            f"   {Colors.GREEN}{Colors.BOLD}✓ ЭРҮҮЛ МЭНД: Бүх тест амжилттай{Colors.END}"
        )
        return True

    except Exception as e:
        print(f"   {Colors.RED}✗ Эрүүл мэнд шалгалт алдаа: {e}{Colors.END}")
        return False


def test_metrics_system():
    """✓ Метрик - Telegram алерт монгол хэлээр"""
    print(f"\n{Colors.YELLOW}2. Метрик систем шалгалт...{Colors.END}")

    try:
        # Test risk alerts
        risk_alert = t("risk_block", reason="High volatility detected")
        if "Эрсдэлийн хориг" in risk_alert:
            print(f"   {Colors.GREEN}✓ Эрсдэлийн алерт: {risk_alert}{Colors.END}")
        else:
            print(f"   {Colors.RED}✗ Эрсдэлийн алерт алдаа: {risk_alert}{Colors.END}")
            return False

        # Test system alerts
        system_alert = t("sla_breach", metric="latency", value=500, threshold=100)
        if "SLA зөрчил" in system_alert:
            print(f"   {Colors.GREEN}✓ SLA алерт: {system_alert}{Colors.END}")
        else:
            print(f"   {Colors.RED}✗ SLA алерт алдаа: {system_alert}{Colors.END}")
            return False

        # Test health degradation
        health_alert = t(
            "health_degraded", status="degraded", reason="Database connection slow"
        )
        if "Системийн байдал" in health_alert:
            print(f"   {Colors.GREEN}✓ Эрүүл мэндийн алерт: {health_alert}{Colors.END}")
        else:
            print(
                f"   {Colors.RED}✗ Эрүүл мэндийн алерт алдаа: {health_alert}{Colors.END}"
            )
            return False

        # Test convenience functions
        alert_msg = alert_message(
            "circuit_breaker_triggered", reason="Too many failures"
        )
        if "Circuit breaker идэвхжлээ" in alert_msg:
            print(f"   {Colors.GREEN}✓ Алерт функц: {alert_msg}{Colors.END}")
        else:
            print(f"   {Colors.RED}✗ Алерт функц алдаа: {alert_msg}{Colors.END}")
            return False

        print(
            f"   {Colors.GREEN}{Colors.BOLD}✓ МЕТРИК: Telegram алерт систем монгол хэлээр ажиллаж байна{Colors.END}"
        )
        return True

    except Exception as e:
        print(f"   {Colors.RED}✗ Метрик систем алдаа: {e}{Colors.END}")
        return False


def test_smoke_logs():
    """✓ Smoke - Лог системүүд монгол хэлээр"""
    print(f"\n{Colors.YELLOW}3. Smoke лог систем шалгалт...{Colors.END}")

    try:
        # Test regime detection logs
        regime_log = t(
            "regime_detector_init",
            active=True,
            thresholds={"low": 0.003, "high": 0.015},
        )
        if "RegimeDetector эхэллээ" in regime_log:
            print(
                f"   {Colors.GREEN}✓ Дэглэм тогтоолт: {regime_log[:80]}...{Colors.END}"
            )
        else:
            print(f"   {Colors.RED}✗ Дэглэм тогтоолт алдаа: {regime_log}{Colors.END}")
            return False

        # Test order lifecycle logs
        order_log = t("orderbook_initialized", db_path="/tmp/orders.db")
        if "OrderBook өгөгдлийн сантай эхэллээ" in order_log:
            print(
                f"   {Colors.GREEN}✓ Захиалгын амьдралын мөчлөг: {order_log}{Colors.END}"
            )
        else:
            print(
                f"   {Colors.RED}✗ Захиалгын амьдралын мөчлөг алдаа: {order_log}{Colors.END}"
            )
            return False

        # Test auth system logs
        auth_log = t("auth_login_ok")
        if "Нэвтрэлт амжилттай" in auth_log:
            print(f"   {Colors.GREEN}✓ Нэвтрэх систем: {auth_log}{Colors.END}")
        else:
            print(f"   {Colors.RED}✗ Нэвтрэх систем алдаа: {auth_log}{Colors.END}")
            return False

        # Test pipeline logs
        pipeline_log = t("order_filled", symbol="GBPUSD", filled_qty=0.5, price=1.2856)
        if "Захиалга биелэв" in pipeline_log:
            print(f"   {Colors.GREEN}✓ Арилжааны pipeline: {pipeline_log}{Colors.END}")
        else:
            print(
                f"   {Colors.RED}✗ Арилжааны pipeline алдаа: {pipeline_log}{Colors.END}"
            )
            return False

        # Test convenience log function
        log_msg = log_message("system_ready")
        if "Систем бэлэн" in log_msg:
            print(f"   {Colors.GREEN}✓ Лог функц: {log_msg}{Colors.END}")
        else:
            print(f"   {Colors.RED}✗ Лог функц алдаа: {log_msg}{Colors.END}")
            return False

        print(
            f"   {Colors.GREEN}{Colors.BOLD}✓ SMOKE: Лог системүүд монгол хэлээр ажиллаж байна{Colors.END}"
        )
        return True

    except Exception as e:
        print(f"   {Colors.RED}✗ Smoke лог системийн алдаа: {e}{Colors.END}")
        return False


def test_timezone_integration():
    """Цагийн бүсийн интеграци шалгах"""
    print(f"\n{Colors.BLUE}4. Цагийн бүсийн интеграци...{Colors.END}")

    try:
        # Test timezone functions
        local_time = fmt_ts(ub_now())
        timezone_info = settings.TZ

        if "Asia/Ulaanbaatar" in timezone_info or "+08" in local_time:
            print(
                f"   {Colors.GREEN}✓ Улаанбаатарын цагийн бүс: {local_time}{Colors.END}"
            )
        else:
            print(
                f"   {Colors.YELLOW}⚠ Цагийн бүс тодорхойгүй: {timezone_info}{Colors.END}"
            )

        # Test locale setting
        if settings.LOCALE == "mn":
            print(f"   {Colors.GREEN}✓ Locale тохиргоо: {settings.LOCALE}{Colors.END}")
        else:
            print(
                f"   {Colors.RED}✗ Locale тохиргоо алдаа: {settings.LOCALE}{Colors.END}"
            )
            return False

        return True

    except Exception as e:
        print(f"   {Colors.RED}✗ Цагийн бүсийн алдаа: {e}{Colors.END}")
        return False


def print_summary(results):
    """Дүгнэлт хэвлэх"""
    print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}ДҮГНЭЛТ - GA SMOKE TEST RESULTS{Colors.END}")
    print(f"{'='*60}")

    passed = sum(results)
    total = len(results)

    if passed == total:
        print(
            f"{Colors.GREEN}{Colors.BOLD}✅ БҮГД АМЖИЛТТАЙ: {passed}/{total} тест амжилттай{Colors.END}"
        )
        print()
        print(f"{Colors.GREEN}🎉 МОНГОЛ ХЭЛНИЙ i18n СИСТЕМ GA-д БЭЛЭН!{Colors.END}")
        print(
            f"{Colors.GREEN}   - Эрүүл мэнд: Бүх үндсэн функц ажиллаж байна{Colors.END}"
        )
        print(f"{Colors.GREEN}   - Метрик: Telegram алерт монгол хэлээр{Colors.END}")
        print(f"{Colors.GREEN}   - Smoke: Лог системүүд монгол мессежтэй{Colors.END}")
        print()
        return 0
    else:
        print(
            f"{Colors.RED}{Colors.BOLD}❌ АЛДАА: {passed}/{total} тест амжилттай{Colors.END}"
        )
        print(f"{Colors.RED}   GA-д бэлэн биш. Алдаануудыг засна уу.{Colors.END}")
        return 1


def main():
    """Үндсэн функц"""
    print_header()

    # Run all tests
    results = []

    # ✓ Эрүүл мэнд
    results.append(test_health_check())

    # ✓ Метрик
    results.append(test_metrics_system())

    # ✓ Smoke
    results.append(test_smoke_logs())

    # Цагийн бүс (bonus)
    timezone_ok = test_timezone_integration()

    # Print final summary
    exit_code = print_summary(results)

    if exit_code == 0:
        print(f"{Colors.CYAN}i18n систем production-д ашиглахад бэлэн! 🇲🇳{Colors.END}")

    return exit_code


if __name__ == "__main__":
    exit(main())
