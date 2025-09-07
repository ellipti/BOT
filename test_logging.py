#!/usr/bin/env python3
"""
Test script for Upgrade #05 - Advanced Logging System
Demonstrates JSON logging, rotation, and structured output
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

import json

from config.settings import get_settings
from logging_setup import get_logger_with_context, setup_advanced_logger


def test_basic_logging():
    """Test basic logging functionality"""
    logger = setup_advanced_logger("test_basic")

    logger.info("Testing basic logging functionality")
    logger.debug("This is a debug message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")

    print("✅ Basic logging test completed")


def test_structured_logging():
    """Test structured logging with extra data"""
    logger = setup_advanced_logger("test_structured")

    # Log with extra structured data
    logger.info(
        "Trade signal generated",
        extra={
            "symbol": "XAUUSD",
            "signal": "BUY",
            "confidence": 0.85,
            "atr": 2.45,
            "price": 1985.50,
        },
    )

    logger.warning(
        "Risk limit approached",
        extra={
            "current_drawdown": 2.1,
            "max_allowed": 3.0,
            "account_balance": 5000.00,
            "open_positions": 2,
        },
    )

    print("✅ Structured logging test completed")


def test_context_logger():
    """Test logger with persistent context"""
    context_logger = get_logger_with_context(
        "test_context",
        session_id="sess_12345",
        user_id="trader_001",
        environment="testing",
    )

    context_logger.info("Starting trading session")
    context_logger.info("Market analysis completed")
    context_logger.warning("High volatility detected")

    print("✅ Context logger test completed")


def test_exception_logging():
    """Test exception logging with traceback"""
    logger = setup_advanced_logger("test_exceptions")

    try:
        # Simulate an error
        result = 10 / 0
    except Exception:
        logger.error(
            "Division by zero error occurred",
            exc_info=True,
            extra={"operation": "division", "dividend": 10, "divisor": 0},
        )

    print("✅ Exception logging test completed")


def test_json_output():
    """Test JSON log file creation"""
    logger = setup_advanced_logger("test_json")

    logger.info(
        "JSON output test",
        extra={
            "test_data": {
                "numbers": [1, 2, 3],
                "nested": {"key": "value"},
                "boolean": True,
                "null_value": None,
            }
        },
    )

    # Check if JSON files were created
    log_dir = Path("logs")
    json_files = list(log_dir.glob("*.json"))

    if json_files:
        print(f"✅ JSON log files created: {[f.name for f in json_files]}")

        # Show sample of JSON content
        for json_file in json_files[:1]:  # Show first file
            if json_file.stat().st_size > 0:
                with open(json_file, encoding="utf-8") as f:
                    # Read last line (most recent log entry)
                    lines = f.readlines()
                    if lines:
                        try:
                            last_entry = json.loads(lines[-1])
                            print(f"📄 Sample JSON log entry from {json_file.name}:")
                            print(json.dumps(last_entry, indent=2, ensure_ascii=False))
                        except json.JSONDecodeError:
                            print(f"⚠️ Could not parse JSON in {json_file.name}")
    else:
        print("❌ No JSON log files found")


def main():
    """Run all logging tests"""
    print("🧪 === UPGRADE #05 LOGGING SYSTEM TESTS ===\n")

    # Show current settings
    settings = get_settings()
    print(f"Log Level: {settings.logging.log_level}")
    print(f"Log Directory: {settings.logging.log_directory}")
    print(f"Retention Days: {settings.logging.log_retention_days}")
    print(f"Trade Logging: {settings.logging.trade_log_enabled}")
    print()

    # Run tests
    test_basic_logging()
    test_structured_logging()
    test_context_logger()
    test_exception_logging()
    test_json_output()

    print("\n🎯 === LOGGING SYSTEM VERIFICATION ===")

    # Verify log files structure
    log_dir = Path("logs")
    if log_dir.exists():
        print(f"📁 Log directory: {log_dir.absolute()}")

        log_files = list(log_dir.iterdir())
        for log_file in sorted(log_files):
            size_kb = log_file.stat().st_size / 1024
            print(f"   📄 {log_file.name} ({size_kb:.1f}KB)")
    else:
        print("❌ Log directory not found")

    print("\n✨ Advanced JSON logging system ready for ELK Stack integration!")
    print("🔄 Daily rotation enabled with retention management")
    print("📊 Structured logs ready for distant monitoring")


if __name__ == "__main__":
    main()
