#!/usr/bin/env python3
"""
Secret Get Script

Retrieve secrets from OS keyring or environment variables.

Usage:
    python scripts/secret_get.py SECRET_NAME

Example:
    python scripts/secret_get.py TELEGRAM_TOKEN
"""

import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from infra.secrets import get_keyring_backend, get_secret, is_keyring_available


def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/secret_get.py SECRET_NAME")
        print("")
        print("Example:")
        print("  python scripts/secret_get.py TELEGRAM_TOKEN")
        sys.exit(1)

    secret_name = sys.argv[1]

    if not secret_name:
        print("Error: SECRET_NAME cannot be empty")
        sys.exit(1)

    print(f"🔐 Keyring Backend: {get_keyring_backend()}", file=sys.stderr)
    print(f"🔍 Looking for secret '{secret_name}'...", file=sys.stderr)

    secret_value = get_secret(secret_name)

    if secret_value:
        # Output only the secret value to stdout (for piping/scripting)
        print(secret_value)
        print(f"✅ Secret '{secret_name}' found", file=sys.stderr)
    else:
        print(
            f"❌ Secret '{secret_name}' not found in keyring or environment",
            file=sys.stderr,
        )
        print("", file=sys.stderr)
        print("💡 To store a secret:", file=sys.stderr)
        print(
            f"   python scripts/secret_set.py {secret_name} 'your_secret_value'",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
