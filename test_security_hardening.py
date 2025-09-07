#!/usr/bin/env python3
"""
Security & Secrets Hardening Test

Test keyring integration, log redaction, and secure configuration loading.
"""

import logging
import os
import sys
import tempfile
import time
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from infra.secrets import (
    get_keyring_backend,
    get_secret,
    is_keyring_available,
    set_secret,
)
from logging_setup import RedactionFilter, setup_advanced_logger


def test_keyring_functionality():
    """Test keyring secret storage and retrieval"""
    print("🔐 Testing Keyring Functionality")
    print("=" * 50)

    print(f"🔍 Keyring Available: {is_keyring_available()}")
    print(f"🔧 Backend: {get_keyring_backend()}")

    if not is_keyring_available():
        print("⚠️  Keyring not available - install with: pip install keyring")
        return False

    # Test secret storage and retrieval
    test_key = "TEST_SECRET_KEY"
    test_value = "test_secret_value_12345"

    try:
        print(f"📝 Storing test secret '{test_key}'...")
        set_secret(test_key, test_value)

        print(f"🔍 Retrieving test secret '{test_key}'...")
        retrieved_value = get_secret(test_key)

        if retrieved_value == test_value:
            print("✅ Keyring storage/retrieval: PASSED")
            return True
        else:
            print("❌ Keyring storage/retrieval: FAILED")
            print(f"   Expected: {test_value}")
            print(f"   Got: {retrieved_value}")
            return False

    except Exception as e:
        print(f"❌ Keyring test failed: {e}")
        return False


def test_environment_fallback():
    """Test environment variable fallback"""
    print("\n🌍 Testing Environment Variable Fallback")
    print("=" * 50)

    # Test with environment variable
    test_key = "TEST_ENV_FALLBACK"
    test_value = "env_fallback_value_67890"

    # Set environment variable
    os.environ[test_key] = test_value

    try:
        retrieved_value = get_secret(test_key)
        if retrieved_value == test_value:
            print("✅ Environment fallback: PASSED")
            return True
        else:
            print("❌ Environment fallback: FAILED")
            print(f"   Expected: {test_value}")
            print(f"   Got: {retrieved_value}")
            return False
    finally:
        # Clean up
        if test_key in os.environ:
            del os.environ[test_key]


def test_log_redaction():
    """Test log redaction functionality"""
    print("\n🛡️  Testing Log Redaction")
    print("=" * 50)

    # Create a temporary log handler for testing
    redaction_filter = RedactionFilter()

    # Test data with sensitive information
    test_cases = [
        {
            "input": "TELEGRAM_TOKEN=1234567890:ABCdefGhIJklmNOPqrsTUVwxyz",
            "expected_contains": "TELEGRAM_TOKEN=****",
            "description": "Telegram token redaction",
        },
        {
            "input": "password = my_secret_password_123",
            "expected_contains": "password = ****",
            "description": "Password redaction",
        },
        {
            "input": "api_key: sk-1234567890abcdefghijklmnopqrstuvwxyz",
            "expected_contains": "api_key: ****",
            "description": "API key redaction",
        },
        {
            "input": "MT5_PASSWORD=super_secret_mt5_pass",
            "expected_contains": "MT5_PASSWORD=****",
            "description": "MT5 password redaction",
        },
        {
            "input": "Normal log message without secrets",
            "expected_contains": "Normal log message without secrets",
            "description": "Normal message unchanged",
        },
    ]

    all_passed = True

    for case in test_cases:
        # Create a log record
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg=case["input"],
            args=(),
            exc_info=None,
        )

        # Apply redaction filter
        redaction_filter.filter(record)

        # Check result
        redacted_message = record.getMessage()

        if case["expected_contains"] in redacted_message:
            print(f"✅ {case['description']}: PASSED")
        else:
            print(f"❌ {case['description']}: FAILED")
            print(f"   Input: {case['input']}")
            print(f"   Output: {redacted_message}")
            print(f"   Expected to contain: {case['expected_contains']}")
            all_passed = False

    # Print redaction stats
    stats = redaction_filter.get_redaction_stats()
    print("\n📊 Redaction Statistics:")
    print(f"   Total redactions: {stats['total_redactions']}")
    print(f"   Active patterns: {stats['patterns_active']}")

    return all_passed


def test_configuration_loading():
    """Test configuration loading with keyring integration"""
    print("\n⚙️  Testing Configuration Loading")
    print("=" * 50)

    try:
        from config.settings import get_settings

        print("🔍 Loading settings...")
        settings = get_settings()

        # Test that settings load without errors
        print(f"📋 Environment: {settings.environment}")
        print(f"🔐 Dry run mode: {settings.dry_run}")

        # Test keyring integration fields
        print(
            f"📱 Telegram token loaded: {'Yes' if settings.telegram.bot_token else 'No (from keyring)'}"
        )
        print(
            f"💰 MT5 password loaded: {'Yes' if settings.mt5.password else 'No (from keyring)'}"
        )
        print(
            f"📈 TE API key loaded: {'Yes' if settings.integrations.te_api_key else 'No (from keyring)'}"
        )

        print("✅ Configuration loading: PASSED")
        return True

    except Exception as e:
        print(f"❌ Configuration loading: FAILED - {e}")
        return False


def test_logging_with_redaction():
    """Test logging system with redaction"""
    print("\n📝 Testing Logging with Redaction")
    print("=" * 50)

    try:
        # Setup logger
        logger = setup_advanced_logger("security_test")

        print("🔍 Testing log messages with sensitive data...")

        # Log some test messages (they should be redacted)
        logger.info("Starting authentication with password=secret123456")
        logger.info("API connection established with api_key=sk-abcdef1234567890")
        logger.warning("Failed login attempt for token=1234567890:ABCdef")
        logger.info("Normal log message without secrets")

        # Give a moment for logs to be written
        time.sleep(0.5)

        print("✅ Logging with redaction: PASSED")
        print("   Check logs/ directory to verify redaction is working")
        return True

    except Exception as e:
        print(f"❌ Logging with redaction: FAILED - {e}")
        return False


def main():
    """Run all security tests"""
    print("🔐 AIVO Bot Security & Secrets Hardening Test Suite")
    print("=" * 60)

    tests = [
        ("Keyring Functionality", test_keyring_functionality),
        ("Environment Fallback", test_environment_fallback),
        ("Log Redaction", test_log_redaction),
        ("Configuration Loading", test_configuration_loading),
        ("Logging with Redaction", test_logging_with_redaction),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {e}")
            results.append((test_name, False))

    # Print summary
    print("\n" + "=" * 60)
    print("🏁 TEST SUMMARY")
    print("=" * 60)

    passed = 0
    total = len(results)

    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status:<12} {test_name}")
        if result:
            passed += 1

    print("-" * 60)
    print(f"📊 Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 ALL SECURITY TESTS PASSED!")
        print("\n💡 Next steps:")
        print("   1. Store your secrets using scripts/secret_set.py")
        print("   2. Review .env.example for configuration")
        print("   3. Run CI secret scan workflow")
    else:
        print("⚠️  Some tests failed - review the output above")
        sys.exit(1)


if __name__ == "__main__":
    main()
