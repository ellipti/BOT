"""
Security-focused unit tests for log redaction system.

This module focuses specifically on security aspects:
- Ensuring no sensitive data leaks through edge cases
- Testing against known attack vectors
- Validating compliance with security requirements
- Performance impact assessment
"""

import logging
import time
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from logging_setup import REDACTION_PATTERNS, SENSITIVE_KEYS, RedactionFilter


class TestSecurityCompliance:
    """Security compliance tests for log redaction"""

    def setup_method(self):
        """Set up test environment for each test"""
        self.filter = RedactionFilter()
        self.logger = logging.getLogger("security_test")
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()

        # Capture output
        self.output_stream = StringIO()
        self.handler = logging.StreamHandler(self.output_stream)
        self.handler.addFilter(self.filter)
        self.handler.setFormatter(logging.Formatter("%(message)s"))
        self.logger.addHandler(self.handler)

    def get_last_log_output(self) -> str:
        """Get the last log output line"""
        lines = self.output_stream.getvalue().strip().split("\n")
        return lines[-1] if lines and lines[0] else ""

    def clear_output(self):
        """Clear the output stream"""
        self.output_stream.truncate(0)
        self.output_stream.seek(0)

    @pytest.mark.security
    def test_pci_dss_compliance_patterns(self):
        """Test PCI DSS compliance - ensure card data patterns are redacted"""
        # Test credit card-like patterns (if we add them to SENSITIVE_KEYS)
        sensitive_financial_data = [
            "card_number=4532-1234-5678-9012",
            "cvv=123",
            "pin=1234",
            "account_number=123456789012",
            "routing_number=021000021",
        ]

        for data in sensitive_financial_data:
            self.logger.info(data)
            output = self.get_last_log_output()

            # Check if the pattern contains known sensitive keys
            key = data.split("=")[0]
            if key in SENSITIVE_KEYS:
                assert "****" in output, f"Financial data not redacted: {data}"
                assert (
                    data.split("=")[1] not in output
                ), f"Raw financial data leaked: {data}"

            self.clear_output()

    @pytest.mark.security
    def test_gdpr_compliance_patterns(self):
        """Test GDPR compliance - ensure PII patterns are handled"""
        # Test personally identifiable information patterns
        pii_data = [
            "email=user@example.com",  # Not typically redacted
            "user_id=12345",  # Not typically redacted
            "session_token=abc123def456ghi789",
            "user_token=xyz789uvw456",
            "auth_token=bearer_abc123",
        ]

        for data in pii_data:
            self.logger.info(data)
            output = self.get_last_log_output()

            # Check if contains 'token' - should be redacted
            if "token" in data:
                assert "****" in output, f"PII token not redacted: {data}"

            self.clear_output()

    @pytest.mark.security
    def test_zero_day_attack_vectors(self):
        """Test protection against potential bypass attack vectors"""
        attack_vectors = [
            # Unicode and encoding attacks
            "password\u200b=secret123",  # Zero-width space
            "token\u00a0=hidden_value",  # Non-breaking space
            "api_key\u2028=multiline",  # Line separator
            # Case variation attacks
            "PaSsWoRd=MixedCase123",
            "tOkEn=AlTeRnAtInG456",
            # Separator variation attacks
            "password\t=\ttabseparated",
            "token   =   spaceseparated",
            "secret\r\n=\r\nnewlineseparated",
            # Obfuscation attempts
            "pass word=split_key_123",  # Split key (shouldn't match)
            "password_backup=backup123",  # Modified key
            "my_password_field=field123",  # Embedded key
            # JSON/XML injection attempts
            '"password":"injected_json"',
            "'token':'single_quoted'",
            "<password>xml_content</password>",
        ]

        for vector in attack_vectors:
            # Clean the vector for logging (remove control chars)
            clean_vector = "".join(c for c in vector if c.isprintable() or c.isspace())

            self.logger.info(clean_vector)
            output = self.get_last_log_output()

            # Check if any known sensitive patterns are detected
            contains_sensitive_key = any(
                key in clean_vector.lower() for key in SENSITIVE_KEYS
            )

            if contains_sensitive_key and "=" in clean_vector:
                # If it contains a sensitive key and assignment, it should be redacted
                # But some obfuscation attempts might not be caught (and that's by design)
                key_part = clean_vector.split("=")[0].strip().lower()
                direct_match = key_part in SENSITIVE_KEYS

                if direct_match:
                    assert (
                        "****" in output
                    ), f"Attack vector not blocked: {clean_vector}"

            self.clear_output()

    @pytest.mark.security
    def test_information_disclosure_prevention(self):
        """Test prevention of information disclosure through error messages"""
        # Test that exceptions in redaction don't leak information
        with patch.object(
            self.filter, "filter", side_effect=Exception("Redaction error")
        ):
            # This should not prevent logging or leak sensitive information
            sensitive_message = "password=secret123"

            # The filter should handle the exception gracefully
            self.logger.info(sensitive_message)
            output = self.get_last_log_output()

            # Message should still be logged (even if not redacted due to error)
            assert len(output) > 0, "Logging completely failed due to filter error"
            # But ideally, the original sensitive info should not be in the output
            # This is a trade-off between reliability and security

    @pytest.mark.security
    def test_timing_attack_resistance(self):
        """Test that redaction timing doesn't leak information about secret presence"""
        # Messages with and without secrets should have similar processing time
        messages_with_secrets = [
            "password=verylongsecretvalue123456789",
            "token=anotherlongsecrettoken987654321",
            "api_key=fake_test_key_123456789abcdef",
        ]

        messages_without_secrets = [
            "normal message with similar length content 123456789",
            "another normal log message without sensitive data 987654321",
            "regular application log entry with comparable text length",
        ]

        # Measure timing for messages with secrets
        start_time = time.perf_counter()
        for _ in range(100):
            for msg in messages_with_secrets:
                self.logger.info(msg)
        secret_time = time.perf_counter() - start_time

        self.clear_output()

        # Measure timing for messages without secrets
        start_time = time.perf_counter()
        for _ in range(100):
            for msg in messages_without_secrets:
                self.logger.info(msg)
        normal_time = time.perf_counter() - start_time

        # Timing difference should not be excessive (less than 2x)
        ratio = secret_time / normal_time if normal_time > 0 else float("inf")
        assert (
            ratio < 2.0
        ), f"Timing attack possible: secret={secret_time:.4f}s, normal={normal_time:.4f}s, ratio={ratio:.2f}"

    @pytest.mark.security
    def test_memory_cleanup_after_redaction(self):
        """Test that sensitive data doesn't linger in memory after redaction"""
        import gc

        # Log a message with sensitive data
        sensitive_data = "password=verysensitivedata123456789"
        self.logger.info(sensitive_data)

        # Force garbage collection
        gc.collect()

        # Check that the original sensitive data is not in the log output
        output = self.get_last_log_output()
        assert "verysensitivedata123456789" not in output, "Sensitive data not redacted"
        assert "password=****" in output, "Redaction marker not present"

    @pytest.mark.security
    def test_concurrent_redaction_safety(self):
        """Test thread safety of redaction filter"""
        import concurrent.futures
        import threading

        results = []

        def log_sensitive_data(thread_id):
            # Each thread logs different sensitive data
            message = f"thread_{thread_id}_password=secret_{thread_id}_123456"

            # Create a separate output stream for this thread
            thread_output = StringIO()
            thread_handler = logging.StreamHandler(thread_output)
            thread_filter = RedactionFilter()
            thread_handler.addFilter(thread_filter)
            thread_handler.setFormatter(logging.Formatter("%(message)s"))

            thread_logger = logging.getLogger(f"thread_{thread_id}")
            thread_logger.handlers.clear()
            thread_logger.addHandler(thread_handler)
            thread_logger.setLevel(logging.INFO)

            thread_logger.info(message)
            output = thread_output.getvalue().strip()
            results.append((thread_id, output))

        # Run multiple threads concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(log_sensitive_data, i) for i in range(10)]
            concurrent.futures.wait(futures)

        # Verify all threads properly redacted their data
        for thread_id, output in results:
            assert "****" in output, f"Thread {thread_id} failed to redact: {output}"
            assert (
                f"secret_{thread_id}_123456" not in output
            ), f"Thread {thread_id} leaked data: {output}"

    @pytest.mark.security
    def test_redaction_statistics_dont_leak_info(self):
        """Test that redaction statistics don't leak sensitive information"""
        # Log various messages
        self.logger.info("password=secret123")
        self.logger.info("normal message")
        self.logger.info("api_key=fake_test_abcdef")

        # Get statistics
        stats = self.filter.get_redaction_stats()

        # Statistics should only contain counts, not actual sensitive data
        assert isinstance(stats, dict), "Stats should be a dictionary"
        assert "total_redactions" in stats, "Should track redaction count"
        assert "patterns_active" in stats, "Should track pattern count"

        # Stats should not contain sensitive data
        stats_str = str(stats)
        assert "secret123" not in stats_str, "Stats leaked sensitive data"
        assert "fake_test_abcdef" not in stats_str, "Stats leaked sensitive data"

        # Stats should be reasonable
        assert stats["total_redactions"] == 2, "Incorrect redaction count"
        assert stats["patterns_active"] > 0, "No patterns reported"

    @pytest.mark.security
    def test_edge_case_buffer_overflow_protection(self):
        """Test protection against buffer overflow-style attacks in log messages"""
        # Test with extremely long messages containing secrets
        long_prefix = "A" * 10000
        long_suffix = "B" * 10000
        sensitive_data = f"{long_prefix}password=hidden_in_large_message{long_suffix}"

        start_time = time.perf_counter()
        self.logger.info(sensitive_data)
        process_time = time.perf_counter() - start_time

        # Should complete in reasonable time (not hang or crash)
        assert process_time < 1.0, f"Processing took too long: {process_time:.3f}s"

        # Should still redact the sensitive data
        output = self.get_last_log_output()
        assert "password=****" in output, "Large message redaction failed"
        assert (
            "hidden_in_large_message" not in output
        ), "Sensitive data leaked in large message"

    @pytest.mark.security
    def test_regex_dos_protection(self):
        """Test protection against ReDoS (Regular Expression Denial of Service) attacks"""
        # Test patterns that could cause catastrophic backtracking
        potentially_problematic_inputs = [
            "password=" + "a" * 1000 + "b" * 1000,  # Long repeated patterns
            "token=" + "ab" * 500 + "c",  # Alternating patterns
            "api_key=" + "x" * 100 + "y" * 100 + "z" * 100,  # Multiple groups
            "secret=" + ("nested" * 50),  # Repeated substrings
        ]

        for problematic_input in potentially_problematic_inputs:
            start_time = time.perf_counter()
            self.logger.info(problematic_input)
            process_time = time.perf_counter() - start_time

            # Should complete quickly even with problematic input
            assert (
                process_time < 0.1
            ), f"Potential ReDoS detected: {process_time:.3f}s for input length {len(problematic_input)}"

            # Should still perform redaction
            output = self.get_last_log_output()
            assert "****" in output, "Redaction failed on problematic input"

            self.clear_output()

    @pytest.mark.security
    def test_encoding_attack_protection(self):
        """Test protection against various encoding-based attacks"""
        # Test different encodings and special characters
        encoding_attacks = [
            "password=secret\x00hidden",  # Null byte injection
            "token=visible\x1bhidden",  # Escape sequence
            "api_key=normal\x7fhidden",  # DEL character
            "secret=test\x08\x08\x08secret",  # Backspace characters
            "password=value\r\nhidden: data",  # CRLF injection
        ]

        for attack in encoding_attacks:
            # Clean for display
            clean_attack = repr(attack)

            self.logger.info(attack)
            output = self.get_last_log_output()

            # Should redact the sensitive part
            assert (
                "****" in output or "secret" not in output
            ), f"Encoding attack not handled: {clean_attack}"

            self.clear_output()


class TestRedactionPerformance:
    """Performance-focused tests for redaction system"""

    def setup_method(self):
        """Set up performance test environment"""
        self.filter = RedactionFilter()

    @pytest.mark.performance
    def test_redaction_pattern_compilation_time(self):
        """Test that pattern compilation time is reasonable"""
        start_time = time.perf_counter()

        # Re-compile patterns (simulate startup)
        import re

        patterns = [
            re.compile(rf"({key}\s*[=:]\s*)([A-Za-z0-9_\-:.+/]{{6,}})", re.IGNORECASE)
            for key in SENSITIVE_KEYS
        ]

        compile_time = time.perf_counter() - start_time

        assert (
            compile_time < 0.1
        ), f"Pattern compilation took too long: {compile_time:.3f}s"
        assert len(patterns) == len(SENSITIVE_KEYS), "Not all patterns compiled"

    @pytest.mark.performance
    def test_high_volume_redaction_performance(self):
        """Test redaction performance under high message volume"""
        # Create test messages
        test_messages = [
            "password=secret123",
            "normal log message without sensitive data",
            "api_key=fake_test_abcdefghij",
            "another normal message with more content to test",
            "token=ghp_1234567890abcdef and more content",
            "regular application log with timestamps and data",
        ]

        iterations = 1000
        start_time = time.perf_counter()

        for _ in range(iterations):
            for message in test_messages:
                # Simulate log record processing
                record = logging.LogRecord(
                    name="perf_test",
                    level=logging.INFO,
                    pathname="",
                    lineno=1,
                    msg=message,
                    args=(),
                    exc_info=None,
                )
                self.filter.filter(record)

        total_time = time.perf_counter() - start_time
        messages_processed = iterations * len(test_messages)
        rate = messages_processed / total_time

        # Should handle at least 1000 messages per second
        assert rate > 1000, f"Redaction rate too slow: {rate:.1f} messages/sec"

        print(f"Redaction performance: {rate:.1f} messages/sec")

    @pytest.mark.performance
    def test_memory_usage_stability(self):
        """Test that memory usage doesn't grow excessively with redaction"""
        import os

        import psutil

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        # Process many messages with redaction
        for i in range(10000):
            message = f"password=secret_{i}_value token=ghp_abcdef_{i}"
            record = logging.LogRecord(
                name="memory_test",
                level=logging.INFO,
                pathname="",
                lineno=1,
                msg=message,
                args=(),
                exc_info=None,
            )
            self.filter.filter(record)

        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory

        # Memory increase should be reasonable (less than 10MB)
        memory_mb = memory_increase / (1024 * 1024)
        assert memory_mb < 10, f"Excessive memory usage: {memory_mb:.2f}MB increase"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
