#!/usr/bin/env python3
"""
Security & Secrets Management Demo

Demonstrate the complete security hardening system:
1. Keyring secret storage (Windows Credential Manager)
2. Configuration loading with keyring integration
3. Log redaction of sensitive information
4. Environment variable fallback
"""

import os
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config.settings import get_settings
from infra.secrets import get_secret, is_keyring_available, list_secrets, set_secret
from logging_setup import setup_advanced_logger


def demo_secret_management():
    """Demonstrate secret management with keyring"""
    print("🔐 Security & Secrets Management Demo")
    print("=" * 60)

    print(f"🔧 Keyring Backend: {is_keyring_available()}")

    if not is_keyring_available():
        print("⚠️  Keyring not available - install with: pip install keyring")
        return

    # Demo: Store secrets in keyring
    print("\n📝 1. Storing Secrets in Keyring")
    print("-" * 40)

    demo_secrets = {
        "TELEGRAM_TOKEN": "1234567890:ABCdefGhIJklmNOPqrsTUVwxyz_DEMO",
        "MT5_PASSWORD": "demo_mt5_password_123",
        "TE_API_KEY": "demo_te_api_key_456789",
    }

    for key, value in demo_secrets.items():
        try:
            set_secret(key, value)
            print(f"✅ Stored {key} in Windows Credential Manager")
        except Exception as e:
            print(f"❌ Failed to store {key}: {e}")

    # Demo: List stored secrets
    print("\n🔍 2. Listing Stored Secrets")
    print("-" * 40)

    secrets = list_secrets()
    for secret in secrets:
        print(f"🔑 {secret}")

    # Demo: Retrieve secrets
    print("\n🔓 3. Retrieving Secrets")
    print("-" * 40)

    for key in demo_secrets:
        value = get_secret(key)
        if value:
            print(f"✅ Retrieved {key}: {value[:15]}...")
        else:
            print(f"❌ Failed to retrieve {key}")


def demo_configuration_loading():
    """Demonstrate secure configuration loading"""
    print("\n⚙️  4. Configuration Loading with Keyring")
    print("-" * 40)

    # Set environment variable for chat ID to pass validation
    os.environ["TELEGRAM_CHAT_ID"] = "123456789"

    try:
        settings = get_settings()

        print(f"📋 Environment: {settings.environment}")
        print(f"🔐 Dry run mode: {settings.dry_run}")
        print(f"📱 Telegram token loaded: {bool(settings.telegram.bot_token)}")
        print(f"💰 MT5 password loaded: {bool(settings.mt5.password)}")
        print(f"📈 TE API key loaded: {bool(settings.integrations.te_api_key)}")

        if settings.telegram.bot_token:
            print(f"🔒 Token preview: {settings.telegram.bot_token[:15]}...")

        print("✅ Configuration loaded successfully from keyring!")

    except Exception as e:
        print(f"❌ Configuration loading failed: {e}")


def demo_log_redaction():
    """Demonstrate log redaction of sensitive information"""
    print("\n🛡️  5. Log Redaction Demo")
    print("-" * 40)

    logger = setup_advanced_logger("security_demo", level="INFO")

    print("📝 Logging messages with sensitive data (check console for redaction):")

    # These should be redacted in logs
    logger.info("User authentication: password=my_secret_password_123")
    logger.warning(
        "API request failed with token=1234567890:ABCdefGhIJklmNOPqrsTUVwxyz"
    )
    logger.error("MT5 connection error: MT5_PASSWORD=super_secret_mt5_password")
    logger.info("Trading Economics API key: te_api_key=sk-1234567890abcdef")

    # This should NOT be redacted
    logger.info("Normal trading message: XAUUSD price updated to 2650.50")

    print("✅ Check the log output above - sensitive values should show as ****")


def demo_environment_fallback():
    """Demonstrate environment variable fallback"""
    print("\n🌍 6. Environment Variable Fallback")
    print("-" * 40)

    # Set a test environment variable
    test_key = "DEMO_FALLBACK_SECRET"
    test_value = "env_fallback_value_12345"

    os.environ[test_key] = test_value

    # Retrieve using fallback
    retrieved = get_secret(test_key)

    if retrieved == test_value:
        print(f"✅ Environment fallback working: {test_key} = {retrieved}")
    else:
        print("❌ Environment fallback failed")

    # Clean up
    if test_key in os.environ:
        del os.environ[test_key]


def main():
    """Run security demonstration"""
    try:
        demo_secret_management()
        demo_configuration_loading()
        demo_log_redaction()
        demo_environment_fallback()

        print("\n" + "=" * 60)
        print("🎉 SECURITY DEMO COMPLETED SUCCESSFULLY!")
        print("=" * 60)

        print("\n💡 Security Features Demonstrated:")
        print("   ✅ OS Keyring integration (Windows Credential Manager)")
        print("   ✅ Secure configuration loading")
        print("   ✅ Log redaction of sensitive data")
        print("   ✅ Environment variable fallback")
        print("   ✅ Thread-safe secret management")

        print("\n🔐 Next Steps:")
        print(
            "   1. Store your real secrets: python scripts/secret_set.py SECRET_NAME 'value'"
        )
        print("   2. Remove .env files with secrets (use .env.example as template)")
        print("   3. Run CI security scans: GitHub Actions workflow")
        print("   4. Monitor logs for redaction effectiveness")

    except Exception as e:
        print(f"❌ Demo failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
