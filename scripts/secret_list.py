#!/usr/bin/env python3
"""
Secret List Script

List all available secrets in the keyring.

Usage:
    python scripts/secret_list.py
"""

import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from infra.secrets import get_keyring_backend, is_keyring_available, list_secrets


def main():
    print(f"🔐 Keyring Backend: {get_keyring_backend()}")
    print("")

    if not is_keyring_available():
        print("❌ Keyring backend not available")
        print("Install keyring package: pip install keyring")
        sys.exit(1)

    print("🔍 Scanning for available secrets...")
    secrets = list_secrets()

    if secrets:
        print(f"✅ Found {len(secrets)} secret(s) in keyring:")
        print("")
        for secret in secrets:
            print(f"  🔑 {secret}")
        print("")
        print("💡 Use 'python scripts/secret_get.py SECRET_NAME' to retrieve a secret")
    else:
        print("📭 No secrets found in keyring")
        print("")
        print(
            "💡 Use 'python scripts/secret_set.py SECRET_NAME SECRET_VALUE' to store secrets"
        )


if __name__ == "__main__":
    main()
