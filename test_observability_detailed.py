#!/usr/bin/env python3
"""
Detailed test of observability endpoints
"""
import sys
import time
import requests
from observability.httpd import start_httpd, stop_httpd

def detailed_test():
    """Detailed test of all endpoints"""
    print("🔍 Detailed Observability Server Test")
    print("=" * 50)
    
    try:
        # Start the server
        server = start_httpd(port=9101, host="127.0.0.1")
        print("✅ Server started on http://127.0.0.1:9101")
        time.sleep(2)
        
        # Test /healthz endpoint
        print("\n📋 Testing /healthz:")
        try:
            response = requests.get('http://127.0.0.1:9101/healthz', timeout=5)
            print(f"   Status: {response.status_code}")
            print(f"   Headers: {dict(response.headers)}")
            if response.headers.get('content-type', '').startswith('application/json'):
                print(f"   JSON: {response.json()}")
            else:
                print(f"   Text: {response.text[:200]}")
        except Exception as e:
            print(f"   Error: {e}")
        
        # Test /metrics endpoint
        print("\n📋 Testing /metrics:")
        try:
            response = requests.get('http://127.0.0.1:9101/metrics', timeout=5)
            print(f"   Status: {response.status_code}")
            print(f"   Content-Type: {response.headers.get('content-type')}")
            content = response.text
            lines = content.split('\n')
            print(f"   Lines: {len(lines)}")
            print(f"   Preview: {lines[:5]}")
        except Exception as e:
            print(f"   Error: {e}")
        
        # Test root endpoint
        print("\n📋 Testing / (root):")
        try:
            response = requests.get('http://127.0.0.1:9101/', timeout=5)
            print(f"   Status: {response.status_code}")
            print(f"   Content-Type: {response.headers.get('content-type')}")
            if response.headers.get('content-type', '').startswith('text/html'):
                print("   HTML content detected")
                # Check for links
                if '/metrics' in response.text:
                    print("   ✅ Contains /metrics link")
                if '/healthz' in response.text:
                    print("   ✅ Contains /healthz link")
        except Exception as e:
            print(f"   Error: {e}")
        
        print("\n" + "=" * 50)
        print("🎉 Observability server tests completed!")
        
    except Exception as e:
        print(f"❌ Server error: {e}")
    finally:
        try:
            stop_httpd()
            print("🛑 Server stopped")
        except:
            pass

if __name__ == "__main__":
    detailed_test()
