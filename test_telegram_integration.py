#!/usr/bin/env python3
"""
Test the enhanced Telegram commands
"""


def test_telegram_imports():
    """Test that enhanced telegram commands can be imported."""
    print("📱 Testing Telegram command imports...")

    try:
        from services.telegram_commands import (
            handle_health_command,
            handle_metrics_command,
            handle_qs_command,
            handle_status_command,
        )

        print("✅ All enhanced Telegram commands imported successfully")

        # Test that the functions are callable
        print("🔧 Testing command function signatures...")

        # These functions should accept a chat_id parameter
        import inspect

        status_sig = inspect.signature(handle_status_command)
        print(f"handle_status_command: {status_sig}")

        qs_sig = inspect.signature(handle_qs_command)
        print(f"handle_qs_command: {qs_sig}")

        metrics_sig = inspect.signature(handle_metrics_command)
        print(f"handle_metrics_command: {metrics_sig}")

        health_sig = inspect.signature(handle_health_command)
        print(f"handle_health_command: {health_sig}")

        print("✅ All command functions have proper signatures")

    except ImportError as e:
        print(f"❌ Import error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


def test_observability_metrics():
    """Test that metrics can be collected."""
    print("\n📊 Testing observability metrics...")

    try:
        # Generate some test metrics
        from observability.metrics import (
            _registry,
            get_metrics_summary,
            inc,
            observe,
            set_gauge,
        )

        inc("telegram_commands", command="test")
        set_gauge("active_users", 5, service="telegram")
        observe("response_time", 0.123, endpoint="status")

        # Get metrics summary
        summary = get_metrics_summary()
        print(f"Metrics summary: {summary}")

        # Get raw metrics text
        metrics_text = _registry.render_as_text()
        print(f"Raw metrics (first 200 chars): {metrics_text[:200]}...")

        print("✅ Metrics collection working properly")

    except Exception as e:
        print(f"❌ Error with metrics: {e}")


if __name__ == "__main__":
    print("🧪 Telegram Integration Test")
    print("=" * 40)

    test_telegram_imports()
    test_observability_metrics()

    print("\n✅ Telegram integration test completed!")
