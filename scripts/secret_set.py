#!/usr/bin/env python3
"""
Secret Set Script

Store secrets securely in OS keyring (Windows Credential Manager on Windows).

Usage:
    python scripts/secret_set.py SECRET_NAME SECRET_VALUE

Example:
    python scripts/secret_set.py TELEGRAM_TOKEN "1234567890:ABCdefGhIJklmNOPqrsTUVwxyz"
"""

import os
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from infra.secrets import get_keyring_backend, is_keyring_available, set_secret


def main():
    if len(sys.argv) != 3:
        print("Usage: python scripts/secret_set.py SECRET_NAME SECRET_VALUE")
        print("")
        print("Example:")
        print('  python scripts/secret_set.py TELEGRAM_TOKEN "1234567890:ABC..."')
        sys.exit(1)

    secret_name = sys.argv[1]
    secret_value = sys.argv[2]

    if not secret_name or not secret_value:
        print("Error: SECRET_NAME and SECRET_VALUE cannot be empty")
        sys.exit(1)

    # Check keyring availability
    if not is_keyring_available():
        print("❌ Error: Keyring backend not available")
        print("Install keyring package: pip install keyring")
        sys.exit(1)

    print(f"🔐 Keyring Backend: {get_keyring_backend()}")
    print(f"📝 Storing secret '{secret_name}' in OS keyring...")

    try:
        set_secret(secret_name, secret_value)
        print(f"✅ Successfully saved '{secret_name}' to OS keyring")
        print("🔑 Secret can now be accessed by the application")

        # Security reminder
        print("")
        print("🛡️  Security Reminder:")
        print("   • Clear your terminal history if it contains the secret")
        print("   • Use environment variables for temporary testing only")
        print("   • The secret is now stored securely in Windows Credential Manager")

    except Exception as e:
        print(f"❌ Error storing secret: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
