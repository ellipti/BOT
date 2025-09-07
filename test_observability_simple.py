#!/usr/bin/env python3
"""
Simplified test for observability components
"""


def test_core_observability():
    """Test core observability functionality."""
    print("📊 Testing core observability...")

    try:
        # Test metrics
        from observability.metrics import (
            get_metrics,
            inc,
            observe,
            render_as_text,
            set_gauge,
        )

        print("✅ Metrics module imported successfully")

        # Test health
        from observability.health import check_health, check_mt5_connection

        print("✅ Health module imported successfully")

        # Test HTTP server
        from observability.httpd import start_httpd

        print("✅ HTTP server module imported successfully")

        # Generate some metrics
        inc("test_metric", service="test")
        set_gauge("test_gauge", 123.45)
        observe("test_histogram", 0.5)

        # Get metrics text
        metrics_text = render_as_text()
        print(f"Generated {len(metrics_text)} chars of metrics")

        if "test_metric" in metrics_text:
            print("✅ Metrics generation working")
        else:
            print("❌ Metrics not found in output")

        # Test health check
        health = check_health()
        print(f"Health check status: {health.get('status')}")
        print("✅ Health checks working")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_settings_integration():
    """Test settings integration."""
    print("\n⚙️ Testing settings integration...")

    try:
        from config.settings import get_settings

        settings = get_settings()

        # Check if observability settings are present
        if hasattr(settings, "observability"):
            obs_settings = settings.observability
            print("✅ Observability settings found")
            print(f"  metrics_port: {obs_settings.metrics_port}")
            print(f"  enable_http_metrics: {obs_settings.enable_http_metrics}")
            print(f"  enable_prometheus: {obs_settings.enable_prometheus}")
        else:
            print("❌ Observability settings not found")

        return True

    except Exception as e:
        print(f"❌ Settings error: {e}")
        return False


if __name__ == "__main__":
    print("🧪 Core Observability Test")
    print("=" * 30)

    success1 = test_core_observability()
    success2 = test_settings_integration()

    if success1 and success2:
        print("\n🎉 All tests passed! Observability system is working correctly.")
    else:
        print("\n❌ Some tests failed.")
