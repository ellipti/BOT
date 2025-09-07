#!/usr/bin/env python3
"""Simple test for atomic operations"""

from pathlib import Path

from utils.atomic_io import atomic_read_json, atomic_update_json, atomic_write_json


def test_basic_operations():
    """Test basic atomic operations"""
    test_file = Path("test_simple.json")

    # Clean up any existing file
    if test_file.exists():
        test_file.unlink()

    print("1. Атом бичилт тест хийж байна...")
    test_data = {"name": "test", "count": 5}
    atomic_write_json(test_file, test_data)
    print("   ✅ Бичилт амжилттай")

    print("2. Атом уншилт тест хийж байна...")
    read_data = atomic_read_json(test_file)
    print(f"   Уншсан өгөгдөл: {read_data}")
    assert read_data == test_data
    print("   ✅ Уншилт амжилттай")

    print("3. Атом шинэчлэлт тест хийж байна...")

    def increment_count(data):
        if data is None:
            data = {}
        result = data.copy()
        result["count"] = result.get("count", 0) + 1
        result["updated"] = True
        return result

    updated_data = atomic_update_json(test_file, increment_count)
    print(f"   Шинэчлэгдсэн өгөгдөл: {updated_data}")
    assert updated_data["count"] == 6
    assert updated_data["updated"] is True
    print("   ✅ Шинэчлэлт амжилттай")

    # Cleanup
    test_file.unlink()

    print("\n🎉 Бүх үндсэн тестүүд амжилттай!")


if __name__ == "__main__":
    test_basic_operations()
