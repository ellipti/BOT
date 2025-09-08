#!/usr/bin/env python3
"""
Quick Diagnostics - i18n System Health Check
=============================================

Монгол хэлний i18n системийн хурдан оношилгоо
Операторууд болон DevOps-уудад зориулсан хурдан шалгалтын скрипт

Ажиллуулах: python scripts/quick_diagnostics.py
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def print_header():
    print("🔧 QUICK DIAGNOSTICS - i18n SYSTEM HEALTH CHECK")
    print("Монгол хэлний i18n системийн хурдан оншилгоо")
    print("=" * 55)


def check_locale_config():
    """Locale тохиргоо шалгах"""
    print("\n1️⃣ Locale тохиргоо шалгалт...")

    try:
        from config.settings import settings

        locale = settings.LOCALE
        timezone = settings.TZ

        if locale == "mn":
            print(f"   ✅ LOCALE: {locale} (зөв)")
        else:
            print(f"   ❌ LOCALE: {locale} (mn байх ёстой)")

        if timezone == "Asia/Ulaanbaatar":
            print(f"   ✅ TIMEZONE: {timezone} (зөв)")
        else:
            print(f"   ⚠️  TIMEZONE: {timezone} (Asia/Ulaanbaatar байх ёстой)")

        return locale == "mn"

    except Exception as e:
        print(f"   ❌ Алдаа: {e}")
        return False


def check_i18n_system():
    """i18n систем ажиллаж буй эсэх"""
    print("\n2️⃣ i18n систем шалгалт...")

    try:
        from utils.i18n import _MESSAGES_MN, t

        # Test basic translation
        test_msg = t("system_startup")
        expected = "Систем эхэлж байна..."

        if test_msg == expected:
            print(f"   ✅ Орчуулга: {test_msg}")
        else:
            print(f"   ❌ Орчуулга алдаа: '{test_msg}' != '{expected}'")
            return False

        # Test parameterized translation
        param_msg = t("order_placed", symbol="TEST", side="BUY", qty=1.0)
        if "Захиалга илгээгдлээ" in param_msg and "TEST" in param_msg:
            print(f"   ✅ Параметртэй орчуулга: {param_msg}")
        else:
            print(f"   ❌ Параметртэй орчуулга алдаа: {param_msg}")
            return False

        # Count translations
        total_translations = len(_MESSAGES_MN)
        print(f"   📊 Нийт орчуулга: {total_translations}")

        return True

    except Exception as e:
        print(f"   ❌ Алдаа: {e}")
        return False


def check_utf8_encoding():
    """UTF-8 дэмжлэг шалгах"""
    print("\n3️⃣ UTF-8 encoding шалгалт...")

    try:
        # Check system encoding
        encoding = sys.stdout.encoding
        if encoding and "utf-8" in encoding.lower():
            print(f"   ✅ System encoding: {encoding}")
        else:
            print(f"   ⚠️  System encoding: {encoding} (UTF-8 биш)")

        # Check environment variable
        pythonioencoding = os.environ.get("PYTHONIOENCODING", "унимагдуу")
        if pythonioencoding and "utf-8" in pythonioencoding.lower():
            print(f"   ✅ PYTHONIOENCODING: {pythonioencoding}")
        else:
            print(f"   ⚠️  PYTHONIOENCODING: {pythonioencoding}")
            print("      → Тохиргоо: $env:PYTHONIOENCODING='UTF-8'")

        # Test Mongolian characters
        mongolian_test = "Монгол үсэг тест: өүэ"
        print(f"   🇲🇳 Монгол үсэг тест: {mongolian_test}")

        return True

    except Exception as e:
        print(f"   ❌ Алдаа: {e}")
        return False


def check_timezone_functions():
    """Цагийн бүсийн функцүүд шалгах"""
    print("\n4️⃣ Цагийн бүс шалгалт...")

    try:
        from datetime import datetime

        from utils.timez import fmt_ts, ub_now

        # Test UB timezone
        ub_time = ub_now()
        formatted_time = fmt_ts(ub_time)

        if "+08" in str(ub_time) or "UTC+08" in formatted_time:
            print(f"   ✅ УБ цагийн бүс: {formatted_time}")
        else:
            print(f"   ⚠️  Цагийн бүс тодорхойгүй: {formatted_time}")

        return True

    except Exception as e:
        print(f"   ❌ Алдаа: {e}")
        return False


def check_integration_files():
    """Интеграци хийгдсэн файлуудыг шалгах"""
    print("\n5️⃣ Файл интеграци шалгалт...")

    integration_files = [
        ("risk/telegram_alerts.py", "Telegram алерт"),
        ("risk/regime.py", "Дэглэм тогтоолт"),
        ("app/pipeline.py", "Арилжааны pipeline"),
        ("dashboard/auth.py", "Dashboard нэвтрэх"),
        ("core/executor/order_book.py", "Захиалгын амьдралын мөчлөг"),
    ]

    integrated_count = 0

    for filepath, description in integration_files:
        full_path = Path(filepath)
        if full_path.exists():
            try:
                content = full_path.read_text(encoding="utf-8")
                if "from utils.i18n import t" in content:
                    print(f"   ✅ {description}: i18n интеграци хийгдсэн")
                    integrated_count += 1
                else:
                    print(f"   ⚠️  {description}: i18n импорт олдсонгүй")
            except Exception as e:
                print(f"   ❌ {description}: Файл унших алдаа - {e}")
        else:
            print(f"   ❌ {description}: Файл олдсонгүй - {filepath}")

    print(f"   📊 Интеграци хийгдсэн: {integrated_count}/{len(integration_files)}")
    return integrated_count >= 3  # At least 3 files should be integrated


def show_quick_fixes():
    """Хурдан засварын зөвлөмжүүд"""
    print("\n🔧 ХУРДАН ЗАСВАРЫН ЗӨВЛӨМЖҮҮД:")
    print("=" * 40)

    print("\n❌ Мессеж англи хэвээр:")
    print("   → settings.LOCALE='mn' эсэхээ шалга")
    print("   → logger.info(t('message_key')) ашигла")
    print("   → from utils.i18n import t импорт хийгдсэн эсэхээ шалга")

    print("\n❌ UTF-8 алдаа:")
    print("   → PowerShell: $env:PYTHONIOENCODING='UTF-8'")
    print("   → Python файлд: # -*- coding: utf-8 -*-")
    print("   → JSON файл: ensure_ascii=False ашигла")

    print("\n❌ Snapshot алдаа:")
    print("   → settings.OBS_BASE ашигла")
    print("   → Давхар slash-аас зайлсхий: /metrics (//metrics биш)")
    print("   → Port тохиргоо шалга")

    print("\n✅ Тест команд:")
    print("   → python scripts/ga_smoke_mn.py")
    print("   → python scripts/snapshot_metrics.py")
    print("   → python scripts/demo_mongolian_logs.py")


def main():
    """Үндсэн оношилгоо функц"""
    print_header()

    # Run all checks
    results = []
    results.append(check_locale_config())
    results.append(check_i18n_system())
    results.append(check_utf8_encoding())
    results.append(check_timezone_functions())
    results.append(check_integration_files())

    # Summary
    passed = sum(results)
    total = len(results)

    print(f"\n{'='*55}")
    print("📊 ДҮГНЭЛТ - DIAGNOSTICS SUMMARY")
    print(f"{'='*55}")

    if passed == total:
        print(f"✅ БҮГД ЗӨВӨӨР ТОХИРУУЛСАН: {passed}/{total}")
        print("🎉 i18n систем бүрэн ажиллахад бэлэн!")
        print("🚀 Production-д deploy хийж болно!")
    else:
        print(f"⚠️  АНХААРАЛ: {passed}/{total} зөв тохируулсан")
        print("🔧 Дээрх алдаануудыг засаад дахин турша.")

        # Show fixes
        show_quick_fixes()

    print("\n🔄 Дахин шалгах: python scripts/quick_diagnostics.py")
    return 0 if passed == total else 1


if __name__ == "__main__":
    exit(main())
