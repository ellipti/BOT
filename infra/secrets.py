"""
Security & Secrets Management

Provides secure secret storage using OS keyring with environment variable fallback.
Windows automatically uses Windows Credential Manager.
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Try to import keyring, gracefully fall back if not available
try:
    import keyring

    KEYRING_AVAILABLE = True
    logger.info("Keyring backend available for secure secret storage")
except ImportError:
    keyring = None
    KEYRING_AVAILABLE = False
    logger.warning("Keyring not available, falling back to environment variables only")

# Service name for keyring storage
SERVICE_NAME = "AIVO_BOT"


def get_secret(name: str) -> str | None:
    """
    Get secret value with priority:
    1. OS keyring (Windows Credential Manager on Windows)
    2. Environment variable
    3. None if not found

    Args:
        name: Secret name/key

    Returns:
        Secret value or None if not found
    """
    secret_value = None

    # Try keyring first if available
    if KEYRING_AVAILABLE and keyring:
        try:
            secret_value = keyring.get_password(SERVICE_NAME, name)
            if secret_value:
                logger.debug(f"Secret '{name}' loaded from keyring")
        except Exception as e:
            logger.warning(f"Failed to get secret '{name}' from keyring: {e}")
            secret_value = None

    # Fall back to environment variable
    if not secret_value:
        secret_value = os.getenv(name)
        if secret_value:
            logger.debug(f"Secret '{name}' loaded from environment variable")

    if not secret_value:
        logger.warning(f"Secret '{name}' not found in keyring or environment")

    return secret_value


def set_secret(name: str, value: str) -> None:
    """
    Store secret in OS keyring.

    Args:
        name: Secret name/key
        value: Secret value

    Raises:
        RuntimeError: If keyring backend is not available
    """
    if not KEYRING_AVAILABLE or not keyring:
        raise RuntimeError(
            "Keyring backend not available. Install keyring package: pip install keyring"
        )

    try:
        keyring.set_password(SERVICE_NAME, name, value)
        logger.info(f"Secret '{name}' stored in OS keyring successfully")
    except Exception as e:
        logger.error(f"Failed to store secret '{name}' in keyring: {e}")
        raise


def delete_secret(name: str) -> bool:
    """
    Delete secret from OS keyring.

    Args:
        name: Secret name/key

    Returns:
        True if deleted successfully, False otherwise
    """
    if not KEYRING_AVAILABLE or not keyring:
        logger.warning("Keyring backend not available, cannot delete secret")
        return False

    try:
        keyring.delete_password(SERVICE_NAME, name)
        logger.info(f"Secret '{name}' deleted from OS keyring successfully")
        return True
    except Exception as e:
        logger.warning(f"Failed to delete secret '{name}' from keyring: {e}")
        return False


def list_secrets() -> list[str]:
    """
    List available secrets in keyring.
    Note: This is a basic implementation - keyring doesn't provide native listing.

    Returns:
        List of known secret names
    """
    # Known secret names in our application
    known_secrets = [
        "TELEGRAM_TOKEN",
        "MT5_PASSWORD",
        "TE_API_KEY",
        "MT5_LOGIN",
        "DATABASE_URL",
        "ENCRYPTION_KEY",
    ]

    available_secrets = []
    if KEYRING_AVAILABLE and keyring:
        for secret_name in known_secrets:
            try:
                if keyring.get_password(SERVICE_NAME, secret_name):
                    available_secrets.append(secret_name)
            except Exception:
                continue

    return available_secrets


def is_keyring_available() -> bool:
    """Check if keyring backend is available."""
    return KEYRING_AVAILABLE and keyring is not None


def get_keyring_backend() -> str:
    """Get the current keyring backend name."""
    if not is_keyring_available():
        return "None (keyring not available)"

    try:
        backend = keyring.get_keyring()
        return f"{backend.__class__.__module__}.{backend.__class__.__name__}"
    except Exception:
        return "Unknown backend"
