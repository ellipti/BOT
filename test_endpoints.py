#!/usr/bin/env python3
"""
Quick endpoint smoke test for dashboard
"""
import json

import requests


def test_healthz():
    """Test /healthz endpoint (no auth required)"""
    try:
        response = requests.get("http://127.0.0.1:8080/healthz", timeout=5)
        print(f"✅ /healthz: HTTP {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Service: {data.get('service')}")
            print(f"   Status: {data.get('status')}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ /healthz failed: {e}")
        return False


def test_metrics():
    """Test /api/metrics endpoint (requires auth)"""
    try:
        headers = {"X-DASH-TOKEN": "4li5ujj3ln7hSSoavNlTY82lfBRRC8vtcw9wR4eyzDSbriJw"}
        response = requests.get(
            "http://127.0.0.1:8080/api/metrics", headers=headers, timeout=5
        )
        print(f"✅ /api/metrics: HTTP {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Metrics keys: {list(data.keys())}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ /api/metrics failed: {e}")
        return False


def test_dashboard_auth():
    """Test dashboard root requires auth"""
    try:
        response = requests.get("http://127.0.0.1:8080/", timeout=5)
        print(f"✅ / (no auth): HTTP {response.status_code} (expected 401)")
        return response.status_code == 401
    except Exception as e:
        print(f"❌ / auth test failed: {e}")
        return False


def test_dashboard_with_auth():
    """Test dashboard root with auth"""
    try:
        headers = {"X-DASH-TOKEN": "4li5ujj3ln7hSSoavNlTY82lfBRRC8vtcw9wR4eyzDSbriJw"}
        response = requests.get("http://127.0.0.1:8080/", headers=headers, timeout=5)
        print(f"✅ / (with auth): HTTP {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ / with auth failed: {e}")
        return False


def main():
    print("🔍 Testing Dashboard Endpoints...")
    print("=" * 40)

    tests = [
        ("Health Check", test_healthz),
        ("Metrics API", test_metrics),
        ("Auth Required", test_dashboard_auth),
        ("Dashboard Access", test_dashboard_with_auth),
    ]

    passed = 0
    for name, test_func in tests:
        print(f"\n📋 {name}:")
        if test_func():
            passed += 1

    print(f"\n{'=' * 40}")
    print(f"🎯 Results: {passed}/{len(tests)} tests passed")

    if passed == len(tests):
        print("🎉 All endpoint tests passed!")
    else:
        print("⚠️  Some tests failed - check dashboard server status")


if __name__ == "__main__":
    main()
