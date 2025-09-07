#!/usr/bin/env python3
"""
Integration test for the observability system
"""

import json
import time
from threading import Thread

import requests

from observability.health import check_health

# Import our observability components
from observability.httpd import start_httpd
from observability.metrics import inc, observe, set_gauge


def test_http_endpoints():
    """Test the HTTP endpoints are working correctly."""
    print("🚀 Starting HTTP server on port 9101...")

    # Start the HTTP server
    start_httpd(port=9101)

    # Give the server a moment to start
    time.sleep(2)

    # Generate some test metrics
    print("📊 Generating test metrics...")
    inc("test_counter", type="integration_test")
    inc("test_counter", type="integration_test")  # Should be 2
    set_gauge("test_gauge", 42.5, service="bot")
    observe("test_histogram", 1.23, endpoint="/test")
    observe("test_histogram", 2.34, endpoint="/test")

    # Test /metrics endpoint
    print("📋 Testing /metrics endpoint...")
    try:
        response = requests.get("http://localhost:9101/metrics", timeout=5)
        print(f"Status: {response.status_code}")
        print(f"Content-Type: {response.headers.get('content-type')}")

        if response.status_code == 200:
            metrics_text = response.text
            print(f"Metrics response length: {len(metrics_text)} chars")
            print("Sample metrics:")
            for line in metrics_text.split("\n")[:10]:  # First 10 lines
                if line.strip():
                    print(f"  {line}")

            # Check if our test metrics are present
            if "test_counter" in metrics_text:
                print("✅ test_counter found in metrics")
            if "test_gauge" in metrics_text:
                print("✅ test_gauge found in metrics")
            if "test_histogram" in metrics_text:
                print("✅ test_histogram found in metrics")
        else:
            print(f"❌ /metrics endpoint failed: {response.status_code}")

    except Exception as e:
        print(f"❌ Error accessing /metrics: {e}")

    # Test /healthz endpoint
    print("\n🏥 Testing /healthz endpoint...")
    try:
        response = requests.get("http://localhost:9101/healthz", timeout=5)
        print(f"Status: {response.status_code}")
        print(f"Content-Type: {response.headers.get('content-type')}")

        if response.status_code == 200:
            health_data = response.json()
            print(f"Health status: {health_data.get('status')}")
            print("Health checks:")
            for check_name, check_result in health_data.get("checks", {}).items():
                print(f"  {check_name}: {check_result.get('status')}")
        else:
            print(f"❌ /healthz endpoint failed: {response.status_code}")

    except Exception as e:
        print(f"❌ Error accessing /healthz: {e}")

    # Test / (status page) endpoint
    print("\n📄 Testing / (status page) endpoint...")
    try:
        response = requests.get("http://localhost:9101/", timeout=5)
        print(f"Status: {response.status_code}")
        print(f"Content-Type: {response.headers.get('content-type')}")

        if response.status_code == 200:
            print(f"Status page length: {len(response.text)} chars")
            if "<title>" in response.text:
                print("✅ HTML status page served successfully")
        else:
            print(f"❌ / endpoint failed: {response.status_code}")

    except Exception as e:
        print(f"❌ Error accessing /: {e}")


def test_health_check():
    """Test the health check function directly."""
    print("\n🏥 Testing health check function...")
    try:
        health = check_health()
        print(f"Overall status: {health.get('status')}")
        print(f"Timestamp: {health.get('timestamp')}")
        print("Individual checks:")
        for check_name, check_result in health.get("checks", {}).items():
            print(
                f"  {check_name}: {check_result.get('status')} - {check_result.get('message', 'no message')}"
            )
    except Exception as e:
        print(f"❌ Health check failed: {e}")


if __name__ == "__main__":
    print("🧪 Observability Integration Test")
    print("=" * 50)

    test_health_check()
    test_http_endpoints()

    print("\n✅ Integration test completed!")
    print("Note: HTTP server is running in background. You can test manually at:")
    print("  http://localhost:9101/metrics")
    print("  http://localhost:9101/healthz")
    print("  http://localhost:9101/")
