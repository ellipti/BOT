"""
Comprehensive unit tests for log redaction system.

Tests all aspects of the security log redaction functionality including:
- Sensitive pattern detection and masking
- Multiple redaction patterns
- Edge cases and boundary conditions
- Performance characteristics
- Integration with logging system
"""

import logging
import re
import unittest
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from logging_setup import (
    REDACTION_PATTERNS,
    SENSITIVE_KEYS,
    JsonFormatter,
    RedactionFilter,
    setup_advanced_logger,
)


class TestRedactionFilter(unittest.TestCase):
    """Test cases for the RedactionFilter class"""

    def setUp(self):
        """Set up test fixtures"""
        self.filter = RedactionFilter()
        self.logger = logging.getLogger("test_redaction")
        self.logger.setLevel(logging.DEBUG)

        # Clear any existing handlers
        self.logger.handlers.clear()

        # Add a test handler with our filter
        self.test_stream = StringIO()
        self.handler = logging.StreamHandler(self.test_stream)
        self.handler.addFilter(self.filter)
        self.handler.setFormatter(logging.Formatter("%(message)s"))
        self.logger.addHandler(self.handler)

    def test_basic_sensitive_key_redaction(self):
        """Test basic redaction of sensitive keys"""
        test_cases = [
            ("password=secret123", "password=****"),
            ("token: abc123456789def", "token: ****"),
            ("api_key=fake_test_1234567890", "api_key=****"),
            ("secret = my_secret_value", "secret = ****"),
            ("mt5_password: trading123!", "mt5_password: ****"),
            ("telegram_token=1234:AABBCC", "telegram_token=****"),
            ("bot_token = ghp_abcdef123", "bot_token = ****"),
            ("refresh_token: eyJ0eXAiOiJKV1Q", "refresh_token: ****"),
        ]

        for original, expected in test_cases:
            with self.subTest(original=original):
                self.logger.info(original)
                output = self.test_stream.getvalue().strip().split("\n")[-1]
                self.assertEqual(
                    output, expected, f"Failed to redact '{original}' correctly"
                )
                self.test_stream.truncate(0)
                self.test_stream.seek(0)

    def test_case_insensitive_redaction(self):
        """Test that redaction works case-insensitively"""
        test_cases = [
            ("PASSWORD=Secret123", "PASSWORD=****"),
            ("Token: abc123456789", "Token: ****"),
            ("API_KEY=fake_test_1234567890", "API_KEY=****"),
            ("Secret = MySecretValue", "Secret = ****"),
            ("MT5_PASSWORD: Trading123!", "MT5_PASSWORD: ****"),
        ]

        for original, expected in test_cases:
            with self.subTest(original=original):
                self.logger.info(original)
                output = self.test_stream.getvalue().strip().split("\n")[-1]
                self.assertEqual(output, expected)
                self.test_stream.truncate(0)
                self.test_stream.seek(0)

    def test_multiple_secrets_in_one_message(self):
        """Test redaction of multiple secrets in a single log message"""
        original = (
            "Config loaded: api_key=sk_123456 password=secret123 token=ghp_789abc"
        )
        expected = "Config loaded: api_key=**** password=**** token=****"

        self.logger.info(original)
        output = self.test_stream.getvalue().strip()
        self.assertEqual(output, expected)

    def test_api_key_pattern_redaction(self):
        """Test specific API key pattern redaction"""
        test_cases = [
            ("api_key=fake_test_abcdef123456", "api_key=****"),
            ("'api-key': 'AIzaSyBdI0hCZtE6vySjMm'", "'api-key': '****'"),
            ('"apiKey":"pk_test_1234567890abcdef"', '"apiKey":"****"'),
            ("x-api-key: Bearer sk_1234567890", "x-api-key: Bearer ****"),
        ]

        for original, expected in test_cases:
            with self.subTest(original=original):
                self.logger.info(original)
                output = self.test_stream.getvalue().strip().split("\n")[-1]
                self.assertEqual(output, expected)
                self.test_stream.truncate(0)
                self.test_stream.seek(0)

    def test_bearer_token_redaction(self):
        """Test Bearer token redaction"""
        test_cases = [
            ("Authorization: Bearer abc123def456ghi", "Authorization: Bearer ****"),
            ("bearer token: xyz789uvw123", "bearer token: ****"),
            ("Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", "Bearer ****"),
        ]

        for original, expected in test_cases:
            with self.subTest(original=original):
                self.logger.info(original)
                output = self.test_stream.getvalue().strip().split("\n")[-1]
                self.assertEqual(output, expected)
                self.test_stream.truncate(0)
                self.test_stream.seek(0)

    def test_jwt_token_redaction(self):
        """Test JWT token redaction"""
        jwt_samples = [
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
            "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOjEyMzQ1Njc4OTB9",
            "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.payload.signature",
        ]

        for jwt_token in jwt_samples:
            with self.subTest(jwt=jwt_token[:20] + "..."):
                original = f"JWT token received: {jwt_token}"
                self.logger.info(original)
                output = self.test_stream.getvalue().strip().split("\n")[-1]
                # JWT should be partially redacted
                self.assertIn("****", output)
                self.assertNotEqual(output, original)
                self.test_stream.truncate(0)
                self.test_stream.seek(0)

    def test_url_credentials_redaction(self):
        """Test redaction of credentials in URLs"""
        test_cases = [
            (
                "Database: https://user:secretpass@db.example.com:5432/mydb",
                "Database: https://user:****@db.example.com:5432/mydb",
            ),
            (
                "Connect to: http://admin:password123@api.service.com/v1",
                "Connect to: http://admin:****@api.service.com/v1",
            ),
            (
                "FTP: ftp://ftpuser:myftppass@files.example.org/uploads",
                "FTP: ftp://ftpuser:****@files.example.org/uploads",
            ),
        ]

        for original, expected in test_cases:
            with self.subTest(original=original):
                self.logger.info(original)
                output = self.test_stream.getvalue().strip().split("\n")[-1]
                self.assertEqual(output, expected)
                self.test_stream.truncate(0)
                self.test_stream.seek(0)

    def test_no_redaction_for_normal_text(self):
        """Test that normal text is not redacted"""
        normal_messages = [
            "User logged in successfully",
            "Processing EURUSD order for 0.1 lots",
            "Connection established to broker",
            "Order token generated: ID-12345",  # 'token' but not in key=value format
            "Password validation completed",  # 'password' but not sensitive
            "API call successful",
            "Secret service authentication failed",  # 'secret' but not key=value
            "Short key=ab",  # Too short to be redacted
            "Empty token=",  # Empty value
        ]

        for message in normal_messages:
            with self.subTest(message=message):
                self.logger.info(message)
                output = self.test_stream.getvalue().strip().split("\n")[-1]
                self.assertEqual(
                    output, message, f"Normal text was incorrectly redacted: {message}"
                )
                self.test_stream.truncate(0)
                self.test_stream.seek(0)

    def test_minimum_length_requirements(self):
        """Test that very short values are not redacted"""
        short_values = [
            "password=abc",  # 3 chars - too short
            "token=12345",  # 5 chars - too short
            "secret=x",  # 1 char - too short
            "api_key=",  # Empty - too short
        ]

        for message in short_values:
            with self.subTest(message=message):
                self.logger.info(message)
                output = self.test_stream.getvalue().strip().split("\n")[-1]
                self.assertEqual(
                    output, message, f"Short value was incorrectly redacted: {message}"
                )
                self.test_stream.truncate(0)
                self.test_stream.seek(0)

    def test_redaction_statistics(self):
        """Test redaction statistics tracking"""
        initial_stats = self.filter.get_redaction_stats()
        self.assertEqual(initial_stats["total_redactions"], 0)
        self.assertGreater(initial_stats["patterns_active"], 0)

        # Trigger some redactions
        self.logger.info("password=secret123")
        self.logger.info("api_key=fake_test_abcdef")
        self.logger.info("token=ghp_123456789")

        stats = self.filter.get_redaction_stats()
        self.assertEqual(stats["total_redactions"], 3)
        self.assertEqual(stats["patterns_active"], len(REDACTION_PATTERNS))

    def test_redaction_flag_on_record(self):
        """Test that redaction flag is set on log records"""
        # Create a custom handler to capture the record
        records = []

        class RecordCapturingHandler(logging.Handler):
            def emit(self, record):
                records.append(record)

        record_handler = RecordCapturingHandler()
        record_handler.addFilter(self.filter)
        self.logger.addHandler(record_handler)

        # Log a message that will be redacted
        self.logger.info("password=secret123")

        # Check that the record has the redaction flag
        self.assertEqual(len(records), 1)
        self.assertTrue(hasattr(records[0], "redacted"))
        self.assertTrue(records[0].redacted)

    def test_filter_exception_handling(self):
        """Test that filter doesn't break logging if it encounters an error"""
        # Create a mock log record that will cause an error in redaction
        bad_record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg=None,
            args=(),
            exc_info=None,  # Invalid record
        )

        # This should not raise an exception
        result = self.filter.filter(bad_record)
        self.assertTrue(result)  # Filter should still return True

    def test_complex_json_redaction(self):
        """Test redaction within JSON-like structures"""
        test_cases = [
            (
                '{"api_key": "fake_test_abcdef123456", "timeout": 30}',
                '{"api_key": "****", "timeout": 30}',
            ),
            (
                "Config: {'password': 'mysecret123', 'host': 'localhost'}",
                "Config: {'password': '****', 'host': 'localhost'}",
            ),
            (
                'Settings = {"telegram_token": "123456:ABC-DEF", "debug": true}',
                'Settings = {"telegram_token": "****", "debug": true}',
            ),
        ]

        for original, expected in test_cases:
            with self.subTest(original=original):
                self.logger.info(original)
                output = self.test_stream.getvalue().strip().split("\n")[-1]
                self.assertEqual(output, expected)
                self.test_stream.truncate(0)
                self.test_stream.seek(0)

    def test_all_sensitive_keys_covered(self):
        """Test that all defined sensitive keys are properly covered by patterns"""
        for key in SENSITIVE_KEYS:
            test_message = f"{key}=testvalue123456"
            expected = f"{key}=****"

            with self.subTest(key=key):
                self.logger.info(test_message)
                output = self.test_stream.getvalue().strip().split("\n")[-1]
                self.assertEqual(
                    output, expected, f"Sensitive key '{key}' was not redacted"
                )
                self.test_stream.truncate(0)
                self.test_stream.seek(0)


class TestJsonFormatter(unittest.TestCase):
    """Test cases for JSON log formatter"""

    def setUp(self):
        """Set up test fixtures"""
        self.formatter = JsonFormatter()

    def test_basic_json_formatting(self):
        """Test basic JSON log formatting"""
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="/path/to/file.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.funcName = "test_function"
        record.module = "test_module"

        output = self.formatter.format(record)

        # Parse the JSON
        import json

        log_data = json.loads(output)

        # Check required fields
        self.assertEqual(log_data["message"], "Test message")
        self.assertEqual(log_data["level"], "INFO")
        self.assertEqual(log_data["logger"], "test_logger")
        self.assertEqual(log_data["module"], "test_module")
        self.assertEqual(log_data["function"], "test_function")
        self.assertEqual(log_data["line"], 42)
        self.assertIn("timestamp", log_data)
        self.assertIn("timestamp_iso", log_data)

    def test_json_formatter_with_exception(self):
        """Test JSON formatter with exception information"""
        try:
            raise ValueError("Test exception")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test_logger",
            level=logging.ERROR,
            pathname="/path/to/file.py",
            lineno=42,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )
        record.funcName = "test_function"
        record.module = "test_module"

        output = self.formatter.format(record)

        # Parse the JSON
        import json

        log_data = json.loads(output)

        # Check exception information
        self.assertIn("exception", log_data)
        self.assertEqual(log_data["exception"]["type"], "ValueError")
        self.assertEqual(log_data["exception"]["message"], "Test exception")
        self.assertIsInstance(log_data["exception"]["traceback"], list)
        self.assertGreater(len(log_data["exception"]["traceback"]), 0)

    def test_json_formatter_extra_fields(self):
        """Test JSON formatter with extra fields"""
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="/path/to/file.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.funcName = "test_function"
        record.module = "test_module"

        # Add extra fields
        record.user_id = 12345
        record.request_id = "req-abc-123"
        record.custom_data = {"key": "value"}

        output = self.formatter.format(record)

        # Parse the JSON
        import json

        log_data = json.loads(output)

        # Check extra fields
        self.assertIn("extra", log_data)
        self.assertEqual(log_data["extra"]["user_id"], 12345)
        self.assertEqual(log_data["extra"]["request_id"], "req-abc-123")
        self.assertEqual(log_data["extra"]["custom_data"], {"key": "value"})


class TestRedactionPatterns(unittest.TestCase):
    """Test redaction pattern compilation and matching"""

    def test_all_patterns_compile(self):
        """Test that all redaction patterns compile successfully"""
        for i, pattern in enumerate(REDACTION_PATTERNS):
            with self.subTest(pattern_index=i):
                self.assertIsInstance(pattern, re.Pattern)
                # Try a simple search to ensure pattern works
                try:
                    pattern.search("test string")
                except Exception as e:
                    self.fail(f"Pattern {i} failed: {e}")

    def test_sensitive_keys_coverage(self):
        """Test that all sensitive keys have corresponding patterns"""
        # This is a meta-test to ensure we have patterns for all keys
        for key in SENSITIVE_KEYS:
            found_pattern = False
            test_string = f"{key}=testvalue123456"

            for pattern in REDACTION_PATTERNS:
                if pattern.search(test_string):
                    found_pattern = True
                    break

            self.assertTrue(found_pattern, f"No pattern matches sensitive key: {key}")

    def test_pattern_performance(self):
        """Test that patterns don't take too long to execute"""
        import time

        test_strings = [
            "password=secret123 token=abc456 api_key=fake_test_789",
            "Normal log message with no secrets",
            "Mixed: user=john password=secret token=ghp_123 host=localhost",
            "Multiple secrets: "
            + " ".join([f"key{i}=value{i}123456" for i in range(10)]),
        ]

        start_time = time.time()
        iterations = 1000

        for _ in range(iterations):
            for test_string in test_strings:
                for pattern in REDACTION_PATTERNS:
                    pattern.search(test_string)

        end_time = time.time()
        total_time = end_time - start_time

        # Performance should be reasonable (less than 1 second for 1000 iterations)
        self.assertLess(
            total_time, 1.0, f"Pattern matching took too long: {total_time:.3f}s"
        )


class TestLoggerIntegration(unittest.TestCase):
    """Integration tests for redaction with actual logger setup"""

    def test_setup_advanced_logger_with_redaction(self):
        """Test that setup_advanced_logger includes redaction filter"""
        with patch("config.settings.get_settings") as mock_settings:
            # Mock settings
            mock_settings.return_value = MagicMock()
            mock_settings.return_value.logging.log_level.value = "INFO"
            mock_settings.return_value.logging.log_retention_days = 30
            mock_settings.return_value.telegram.error_alerts = False
            mock_settings.return_value.telegram.bot_token = None

            logger = setup_advanced_logger("test_logger")

            # Check that redaction filters are applied to handlers
            redaction_filters = []
            for handler in logger.handlers:
                for filter_obj in handler.filters:
                    if isinstance(filter_obj, RedactionFilter):
                        redaction_filters.append(filter_obj)

            self.assertGreater(
                len(redaction_filters),
                0,
                "No redaction filters found in logger handlers",
            )

    def test_end_to_end_redaction_flow(self):
        """Test complete end-to-end redaction flow"""
        # Set up a logger with redaction
        test_stream = StringIO()
        logger = logging.getLogger("e2e_test")
        logger.handlers.clear()

        handler = logging.StreamHandler(test_stream)
        handler.addFilter(RedactionFilter())
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        # Log messages with various sensitive data
        sensitive_messages = [
            "Login attempt: password=mypassword123",
            "API call made with token=ghp_abcdef123456789",
            "Database connection: https://user:dbpass@localhost:5432/db",
            "Configuration loaded: {'api_key': 'fake_test_xyz789', 'timeout': 30}",
            "Bearer authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
        ]

        expected_redactions = [
            "Login attempt: password=****",
            "API call made with token=****",
            "Database connection: https://user:****@localhost:5432/db",
            "Configuration loaded: {'api_key': '****', 'timeout': 30}",
            "Bearer authorization: Bearer ****",
        ]

        for i, message in enumerate(sensitive_messages):
            logger.info(message)

        # Check output
        output_lines = test_stream.getvalue().strip().split("\n")

        for i, expected in enumerate(expected_redactions):
            with self.subTest(message_index=i):
                self.assertEqual(output_lines[i], expected)

    @patch("logging_setup.Path")
    def test_logger_creation_with_redaction_stats(self, mock_path):
        """Test logger creation and redaction statistics"""
        # Mock Path operations
        mock_path.return_value.mkdir = MagicMock()
        mock_path.return_value.parent = MagicMock()
        mock_path.return_value.stem = "app"

        with patch("config.settings.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock()
            mock_settings.return_value.logging.log_level.value = "DEBUG"
            mock_settings.return_value.logging.log_retention_days = 7
            mock_settings.return_value.telegram.error_alerts = False
            mock_settings.return_value.telegram.bot_token = None

            logger = setup_advanced_logger("stats_test")

            # Find redaction filter
            redaction_filter = None
            for handler in logger.handlers:
                for filter_obj in handler.filters:
                    if isinstance(filter_obj, RedactionFilter):
                        redaction_filter = filter_obj
                        break
                if redaction_filter:
                    break

            self.assertIsNotNone(redaction_filter, "Redaction filter not found")

            # Test statistics
            stats = redaction_filter.get_redaction_stats()
            self.assertEqual(stats["total_redactions"], 0)
            self.assertEqual(stats["patterns_active"], len(REDACTION_PATTERNS))


class TestSecurityRegression(unittest.TestCase):
    """Regression tests for security vulnerabilities"""

    def setUp(self):
        """Set up test fixtures"""
        self.filter = RedactionFilter()
        self.logger = logging.getLogger("security_test")
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()

        self.test_stream = StringIO()
        self.handler = logging.StreamHandler(self.test_stream)
        self.handler.addFilter(self.filter)
        self.handler.setFormatter(logging.Formatter("%(message)s"))
        self.logger.addHandler(self.handler)

    def test_real_world_sensitive_data(self):
        """Test with realistic sensitive data patterns"""
        # These are fake but realistic-looking secrets
        real_world_cases = [
            (
                "Telegram bot token: 5123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw",
                "Telegram bot token: ****",
            ),
            (
                "GitHub token: ghp_1234567890abcdefghijklmnopqrstuvwxyz",
                "GitHub token: ****",
            ),
            ("AWS key: AKIAIOSFODNN7EXAMPLE", "AWS key: ****"),  # If we add AWS pattern
            (
                "Database URL: postgresql://username:p4ssw0rd@localhost/dbname",
                "Database URL: postgresql://username:****@localhost/dbname",
            ),
            (
                "JWT: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
                "JWT: ****",
            ),
        ]

        for original, expected in real_world_cases:
            with self.subTest(original=original[:50] + "..."):
                self.logger.info(original)
                output = self.test_stream.getvalue().strip().split("\n")[-1]
                if expected.endswith("****"):
                    # For cases where we expect redaction
                    self.assertIn("****", output)
                    self.assertNotEqual(output, original)
                else:
                    self.assertEqual(output, expected)
                self.test_stream.truncate(0)
                self.test_stream.seek(0)

    def test_bypass_attempt_prevention(self):
        """Test that common redaction bypass attempts don't work"""
        bypass_attempts = [
            "password = 'secret123'",  # Quotes
            'token= "abc123def456"',  # Quotes and spaces
            "api_key:  fake_test_abcdef",  # Colon separator
            "secret\t=\tsecretvalue",  # Tabs
            "password\n=\nmypassword",  # Newlines (if in message)
        ]

        for attempt in bypass_attempts:
            # Remove newlines for this test
            clean_attempt = attempt.replace("\n", " ").replace("\t", " ")
            with self.subTest(attempt=clean_attempt):
                self.logger.info(clean_attempt)
                output = self.test_stream.getvalue().strip().split("\n")[-1]
                self.assertIn(
                    "****", output, f"Bypass attempt succeeded: {clean_attempt}"
                )
                self.test_stream.truncate(0)
                self.test_stream.seek(0)

    def test_performance_with_large_messages(self):
        """Test redaction performance with large log messages"""
        import time

        # Create a large message with embedded secrets
        base_message = "Normal log data " * 100  # ~1600 chars
        large_message = f"{base_message} password=secret123 {base_message} token=ghp_abcdef {base_message}"

        start_time = time.time()
        iterations = 100

        for _ in range(iterations):
            self.logger.info(large_message)

        end_time = time.time()
        total_time = end_time - start_time

        # Should complete reasonably quickly (less than 1 second for 100 iterations)
        self.assertLess(
            total_time, 1.0, f"Large message redaction took too long: {total_time:.3f}s"
        )

        # Verify redaction still worked
        final_output = self.test_stream.getvalue()
        self.assertIn("password=****", final_output)
        self.assertIn("token=****", final_output)
        self.assertNotIn("secret123", final_output)
        self.assertNotIn("ghp_abcdef", final_output)


if __name__ == "__main__":
    # Run the tests
    unittest.main(verbosity=2)
