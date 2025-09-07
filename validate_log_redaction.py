#!/usr/bin/env python3
"""
Quick validation script for log redaction system.
Demonstrates that sensitive data is properly masked in logs.
"""

import logging
import sys
from io import StringIO

# Import our redaction system
from logging_setup import RedactionFilter


def main():
    """Demonstrate log redaction in action"""

    print("=== Log Redaction System Validation ===\n")

    # Set up a test logger with redaction
    logger = logging.getLogger("redaction_demo")
    logger.setLevel(logging.INFO)

    # Remove any existing handlers
    for handler in list(logger.handlers):
        logger.removeHandler(handler)

    # Add handler with redaction filter
    handler = logging.StreamHandler(sys.stdout)
    redaction_filter = RedactionFilter()
    handler.addFilter(redaction_filter)
    logger.addHandler(handler)

    print("1. Testing sensitive data redaction:")
    print("   (Original secrets should be masked with ****)")
    print()

    # Test various sensitive patterns
    sensitive_samples = [
        "telegram_token=1234567890:AAABBBCCCdddEEE",
        "TE_API_KEY=sk_live_9cA7xZQ12abcdef",
        "password=MySecretPassword123",
        "secret: A1b2C3d4E5f6g7h8i9j0",
        "bot_token = ghp_1234567890abcdefghijk",
        "mt5_password: MyTradingPassword!",
        "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.signature",
        "Database: https://user:secretpass@db.example.com:5432/mydb",
        "API endpoint with key: api_key=AIzaSyDdI0hCZtE6vySjMm-WEfRq3CPzqKqqsHI",
    ]

    for sample in sensitive_samples:
        logger.info(f"Processing: {sample}")

    print("\n2. Testing normal strings (should NOT be redacted):")
    print()

    normal_samples = [
        "User logged in successfully",
        "Processing EURUSD order for 0.1 lots",
        "Connection to broker established",
        "API endpoint /api/v1/orders called",
        "Token validation completed successfully",
        "Order ID 12345 executed at price 1.0950",
    ]

    for sample in normal_samples:
        logger.info(sample)

    print("\n3. Redaction statistics:")
    stats = redaction_filter.get_redaction_stats()
    print(f"   Total redactions applied: {stats['total_redactions']}")
    print(f"   Active redaction patterns: {stats['patterns_active']}")

    print("\n4. Testing edge cases:")
    edge_cases = [
        "Multiple secrets: api_key=sk_123 password=secret456 token=ghp_789",
        "Short values: pin=12 key=abc",  # Should not be redacted (too short)
        "Empty values: token= password:",  # Should not be redacted (empty)
        "Config: {'api_key': 'sk_live_abcdefghijk', 'timeout': 30}",
    ]

    for case in edge_cases:
        logger.info(f"Edge case: {case}")

    print("\n=== Validation Complete ===")
    print(
        f"Final redaction count: {redaction_filter.get_redaction_stats()['total_redactions']}"
    )
    print("Check the output above - sensitive values should be masked with ****")


if __name__ == "__main__":
    main()
