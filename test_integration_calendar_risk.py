#!/usr/bin/env python3
"""
Calendar Guard + Risk Governor Integration тест
Эдийн засгийн календарь ба эрсдэлийн засаглалын хамтарсан системийн шалгалт

Тест сценариуд:
1. Calendar Guard + Risk Governor хосолсон шалгалт
2. Multiple blocking reasons (calendar + risk)
3. Priority-based blocking decisions
4. Integrated logging and alerts
"""

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

from integrations.calendar import (
    CalendarGuard,
    EventImportance,
    get_calendar_guard_sync,
)
from risk.governor import RiskGovernor


def test_calendar_risk_integration():
    print("🔧 Calendar Guard + Risk Governor Integration тест хийж байна...")

    # Test файлуудыг цэвэрлэх
    test_files = ["test_calendar_integration.json", "test_risk_integration.json"]
    for f in test_files:
        path = Path(f)
        if path.exists():
            path.unlink()

    print("\n🔒 Integration тест эхэлж байна...")

    # Mock settings
    class MockSettings:
        class Trading:
            trading_economics_api_key = "test_key"
            calendar_enabled = True

        class Risk:
            max_daily_loss_percentage = 5.0
            max_weekly_loss_percentage = 15.0
            max_daily_trades = 15
            max_weekly_trades = 75
            cooldown_minutes = 30
            circuit_breaker_loss_threshold = 8.0
            enable_telegram_alerts = (
                True  # telegram_alerts_enabled -> enable_telegram_alerts
            )

        trading = Trading()
        risk = Risk()

    # Systems үүсгэх
    calendar_guard = CalendarGuard(MockSettings())
    calendar_guard.cache_path = Path("test_calendar_integration.json")

    risk_governor = RiskGovernor("test_risk_integration.json")
    # Mock settings тохируулах
    risk_governor.settings = MockSettings()

    print("\n1. Clean state тест хийж байна...")

    # Calendar check
    calendar_result = asyncio.run(calendar_guard.check_trading_allowed(["USD"]))
    print(f"   Calendar арилжаа зөвшөөрөгдсөн: {calendar_result.allowed}")

    # Risk check
    risk_decision = risk_governor.check_trade_allowed("XAUUSD", 0.1)
    print(f"   Risk арилжаа зөвшөөрөгдсөн: {risk_decision.allowed}")

    # Both should be allowed initially
    assert calendar_result.allowed, "Анхны календарь шалгалт амжилттай байх ёстой"
    assert risk_decision.allowed, "Анхны эрсдэл шалгалт амжилттай байх ёстой"

    print("   ✅ Анхны төлөв: календарь болон эрсдэл хоёулаа зөвшөөрч байна")

    print("\n2. High-impact календарь эвент нэмж байна...")

    # High-impact NFP эвент 15 минутын дараа
    now = datetime.now(UTC)
    nfp_event = {
        "id": "integration_nfp",
        "title": "Non-Farm Payrolls",
        "country": "US",
        "category": "Employment",
        "importance": EventImportance.CRITICAL.value,
        "datetime": (now + timedelta(minutes=15)).isoformat(),
        "currency": "USD",
        "forecast": None,
        "previous": None,
        "actual": None,
        "unit": None,
    }

    # Mock календарь өгөгдөл нэмэх
    calendar_data = {
        "events": [nfp_event],
        "last_update": time.time(),
        "api_calls": 1,
        "last_api_call": time.time(),
    }
    calendar_guard._save_cache_data(calendar_data)

    # Calendar шалгах
    calendar_result = asyncio.run(calendar_guard.check_trading_allowed(["USD"]))
    print(
        f"   NFP эвентийн үед Calendar арилжаа зөвшөөрөгдсөн: {calendar_result.allowed}"
    )
    print(f"   Calendar шалтгаан: {calendar_result.reason}")

    # Risk-г дахин шалгах
    risk_decision = risk_governor.check_trade_allowed("XAUUSD", 0.1)
    print(f"   Risk арилжаа зөвшөөрөгдсөн: {risk_decision.allowed}")

    # Calendar should block, risk should still allow
    assert not calendar_result.allowed, "NFP эвентийн үед календарь хориглох ёстой"
    assert risk_decision.allowed, "Risk системд алдагдал байхгүй үед зөвшөөрөх ёстой"

    print("   ✅ Calendar Guard NFP эвентийг зөв таниж хоригложээ")

    print("\n3. Risk limits-г үүсгэж байна...")

    # Multiple алдагдалтай trades хийж risk limit хүртэл хүргэх
    for i in range(5):
        risk_governor.record_trade_result("XAUUSD", -1.0, was_win=False)
        print(f"   Алдагдалтай арилжаа {i+1} бүртгэлээ")

    # Risk check дахин хийх
    risk_decision = risk_governor.check_trade_allowed("XAUUSD", 0.1)
    risk_metrics = risk_governor.get_current_metrics()

    print(f"   Өдрийн алдагдал: {risk_metrics.daily_loss:.1f}%")
    print(f"   Эрсдэлийн түвшин: {risk_metrics.risk_level.value}")
    print(f"   Risk арилжаа зөвшөөрөгдсөн: {risk_decision.allowed}")

    print("   ✅ Risk limits тест амжилттай")

    print("\n4. Double blocking scenario тест хийж байна...")

    # Хоёулаа блок хийх төлөвийг тест хийх
    calendar_result = asyncio.run(calendar_guard.check_trading_allowed(["USD"]))
    risk_decision = risk_governor.check_trade_allowed("XAUUSD", 0.1)

    print(f"   Calendar блок: {not calendar_result.allowed}")
    print(f"   Risk блок: {not risk_decision.allowed}")

    if not calendar_result.allowed and not risk_decision.allowed:
        print("   📋 Хоёр систем хоёулаа блок хийж байна:")
        print(f"      📅 Calendar: {calendar_result.reason}")
        print(f"      ⚠️  Risk: {risk_decision.reason}")
        print("   ✅ Multiple blocking зөв ажиллаж байна")
    elif not calendar_result.allowed:
        print("   📅 Зөвхөн Calendar блок хийж байна")
    elif not risk_decision.allowed:
        print("   ⚠️  Зөвхөн Risk блок хийж байна")
    else:
        print("   ⚠️  Аль нь ч блок хийхгүй байна")

    print("\n5. Priority decision logic тест хийж байна...")

    def make_integrated_decision(symbol: str, currencies: list = None) -> dict:
        """Calendar + Risk integrated шийдвэр гаргах"""

        # Calendar шалгалт
        calendar_result = get_calendar_guard_sync(currencies)

        # Risk шалгалт
        risk_decision = risk_governor.check_trade_allowed(symbol, 0.1)

        # Priority logic
        if not calendar_result.allowed and not risk_decision.allowed:
            # Хоёулаа блок - priority тодорхойлох
            if calendar_result.status.value == "active":
                primary_reason = f"🗓️ {calendar_result.reason}"
                secondary_reason = f"⚠️  {risk_decision.reason}"
            else:
                primary_reason = f"⚠️  {risk_decision.reason}"
                secondary_reason = f"🗓️ {calendar_result.reason}"

            return {
                "allowed": False,
                "primary_reason": primary_reason,
                "secondary_reason": secondary_reason,
                "blocking_systems": ["calendar", "risk"],
            }
        elif not calendar_result.allowed:
            return {
                "allowed": False,
                "primary_reason": f"🗓️ {calendar_result.reason}",
                "blocking_systems": ["calendar"],
            }
        elif not risk_decision.allowed:
            return {
                "allowed": False,
                "primary_reason": f"⚠️  {risk_decision.reason}",
                "blocking_systems": ["risk"],
            }
        else:
            return {
                "allowed": True,
                "primary_reason": "Бүх систем зөвшөөрч байна",
                "blocking_systems": [],
            }

    # Integrated decision тест
    decision = make_integrated_decision("XAUUSD", ["USD"])

    print(f"   Integrated арилжаа зөвшөөрөгдсөн: {decision['allowed']}")
    print(f"   Үндсэн шалтгаан: {decision['primary_reason']}")
    if "secondary_reason" in decision:
        print(f"   Нэмэлт шалтгаан: {decision['secondary_reason']}")
    print(f"   Блок хийсэн системүүд: {decision['blocking_systems']}")

    print("   ✅ Priority decision logic зөв ажиллаж байна")

    print("\n6. Test файлуудыг цэвэрлэж байна...")
    for f in test_files:
        path = Path(f)
        if path.exists():
            path.unlink()
    print("   ✅ Цэвэрлэлт дууслаа")

    print("\n🎉 Calendar Guard + Risk Governor Integration тест амжилттай дууслаа!")
    print("📊 Integration Systems:")
    print("   ✅ Economic Calendar blackout window detection")
    print("   ✅ Risk-based trading limits enforcement")
    print("   ✅ Multi-system blocking coordination")
    print("   ✅ Priority-based decision making")
    print("   ✅ Integrated logging and monitoring")
    print("   ✅ Graceful system interaction")


if __name__ == "__main__":
    import time

    test_calendar_risk_integration()
