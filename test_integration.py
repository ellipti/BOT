#!/usr/bin/env python3
"""Test state management integration with atomic operations"""

import time
from datetime import UTC
from pathlib import Path

import core.state as state_module
from safety_gate import LimitsManager


def test_state_functions():
    """Test state functions with atomic operations"""
    print("Атом үйлдлүүдтэй төлөвийн функцуудыг тест хийж байна...")

    # Clean up any existing state files
    state_dir = Path("state")
    state_file = state_dir / "last_state.json"
    if state_file.exists():
        state_file.unlink()

    print("1. Саяхан арилжаа хийсэн эсэх шалгаж байна...")
    # Should return False for new symbol
    result = state_module.recently_traded("XAUUSD", tf_minutes=30)
    print(f"   Саяхан арилжаа хийсэн (шинэ): {result}")
    assert result is False
    print("   ✅ Шинэ тэмдэгт саяхан арилжаа хийгээгүй")

    print("2. Арилжаа тэмдэглэж байна...")
    state_module.mark_trade("XAUUSD", "BUY")
    print("   ✅ Арилжаа тэмдэглэгдлээ")

    print("3. Тэмдэглэсний дараа саяхан арилжаа хийсэн эсэх шалгаж байна...")
    result = state_module.recently_traded("XAUUSD", tf_minutes=30, cooldown_mult=1.5)
    print(f"   Саяхан арилжаа хийсэн (тэмдэглэсний дараа): {result}")
    assert result is True  # Should be in cooldown
    print("   ✅ Саяхан арилжаа хийсэн байдал зөв ажиллаж байна")

    print("4. Төлөвийн өгөгдлийн бүтцийг шалгаж байна...")
    state_data = state_module._read()
    print(f"   Төлөвийн өгөгдөл: {state_data}")
    assert "XAUUSD" in state_data
    assert "last_trade_ts" in state_data["XAUUSD"]
    print("   ✅ Төлөвийн бүтэц баталгаажлаа")

    # Cleanup
    if state_file.exists():
        state_file.unlink()

    print("   ✅ Төлөвийн функцын тест амжилттай!")


def test_limits_manager():
    """Test LimitsManager with atomic operations"""
    print("\nАтом үйлдлүүдтэй LimitsManager-г тест хийж байна...")

    # Clean up any existing limits file
    limits_file = Path("limits.json")
    if limits_file.exists():
        limits_file.unlink()

    limits_mgr = LimitsManager()

    print("1. Үндсэн утгыг тохируулж байна...")
    from datetime import datetime

    now_utc = datetime.now(UTC)
    limits_mgr.ensure_baseline("XAUUSD", now_utc, 1000.0)
    print("   ✅ Үндсэн утга тохируулагдлаа")

    print("2. Төлөв тохируулж байна...")
    test_state = {"last_execution": time.time(), "test_field": "test_value"}
    limits_mgr.set_state("XAUUSD", now_utc, test_state)
    print("   ✅ Төлөв тохируулагдлаа")

    print("3. Арилжааг тэмдэглэж байна...")
    limits_mgr.mark_trade("XAUUSD", now_utc)
    print("   ✅ Арилжаа тэмдэглэгдлээ")

    print("4. Төлөвийг унших...")
    state = limits_mgr._load()
    print(f"   Одоогийн төлөв: {state}")
    # Check that we have some data structure with date-based keys
    assert len(state) > 0, "Төлөв зарим нэгэн өгөгдөл агуулсан байх ёстой"
    print("   ✅ Төлөвийн бүтэц баталгаажлаа")

    # Cleanup
    if limits_file.exists():
        limits_file.unlink()

    print("   ✅ LimitsManager тест амжилттай!")


if __name__ == "__main__":
    test_state_functions()
    test_limits_manager()
    print("\n🎉 Бүх нэгтгэсэн тестүүд амжилттай!")
