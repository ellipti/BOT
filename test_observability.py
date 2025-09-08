#!/usr/bin/env python3
"""
Quick test of the observability HTTP server
"""
import sys
import time

import requests

from observability.httpd import start_httpd, stop_httpd


def test_observability_server():
    """Start observability server and test endpoints"""
    print("🚀 Starting Observability HTTP Server...")

    try:
        # Start the server on port 9101
        server = start_httpd(port=9101, host="127.0.0.1")
        print("✅ Server started on http://127.0.0.1:9101")

        # Give it a moment to start
        time.sleep(2)

        # Test /healthz endpoint
        try:
            response = requests.get("http://127.0.0.1:9101/healthz", timeout=5)
            print(f"✅ /healthz: HTTP {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   Response: {data}")
        except Exception as e:
            print(f"❌ /healthz failed: {e}")

        # Test /metrics endpoint
        try:
            response = requests.get("http://127.0.0.1:9101/metrics", timeout=5)
            print(f"✅ /metrics: HTTP {response.status_code}")
            if response.status_code == 200:
                content = (
                    response.text[:200] + "..."
                    if len(response.text) > 200
                    else response.text
                )
                print(f"   Content preview: {content}")
        except Exception as e:
            print(f"❌ /metrics failed: {e}")

        # Test root endpoint
        try:
            response = requests.get("http://127.0.0.1:9101/", timeout=5)
            print(f"✅ / (root): HTTP {response.status_code}")
        except Exception as e:
            print(f"❌ / (root) failed: {e}")

    except Exception as e:
        print(f"❌ Failed to start server: {e}")
    finally:
        # Stop the server
        try:
            stop_httpd()
            print("🛑 Server stopped")
        except Exception as e:
            print(f"⚠️  Error stopping server: {e}")


if __name__ == "__main__":
    test_observability_server()
