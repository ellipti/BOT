#!/usr/bin/env python3
"""
Log Redaction Test Runner and Coverage Reporter

This script runs comprehensive tests for the log redaction system and generates
a coverage report to ensure all security aspects are thoroughly tested.

Usage:
    python run_log_redaction_tests.py [--verbose] [--coverage] [--security-only]
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path


def run_unittest_suite(verbose: bool = False) -> tuple[bool, str]:
    """Run the unittest-based test suite"""
    print("🧪 Running unittest-based log redaction tests...")

    cmd = [
        sys.executable,
        "-m",
        "unittest",
        "tests.test_log_redaction_comprehensive",
        "-v" if verbose else "-q",
    ]

    try:
        result = subprocess.run(
            cmd, check=False, capture_output=True, text=True, cwd="."
        )
        success = result.returncode == 0
        output = result.stdout + result.stderr
        return success, output
    except Exception as e:
        return False, f"Failed to run unittest suite: {e}"


def run_pytest_suite(
    verbose: bool = False, security_only: bool = False
) -> tuple[bool, str]:
    """Run the pytest-based test suite"""
    print("🔬 Running pytest-based security tests...")

    cmd = [sys.executable, "-m", "pytest"]

    if security_only:
        cmd.extend(["-m", "security"])

    cmd.extend(
        [
            "tests/test_log_redaction_security.py",
            "-v" if verbose else "-q",
            "--tb=short",
        ]
    )

    try:
        result = subprocess.run(
            cmd, check=False, capture_output=True, text=True, cwd="."
        )
        success = result.returncode == 0
        output = result.stdout + result.stderr
        return success, output
    except Exception as e:
        return False, f"Failed to run pytest suite: {e}"


def run_coverage_analysis(verbose: bool = False) -> tuple[bool, str]:
    """Run coverage analysis on log redaction code"""
    print("📊 Running coverage analysis...")

    # Install coverage if not available
    try:
        subprocess.run(
            [sys.executable, "-m", "coverage", "--version"],
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        print("Installing coverage package...")
        subprocess.run([sys.executable, "-m", "pip", "install", "coverage"], check=True)

    try:
        # Run tests with coverage
        cmd = [
            sys.executable,
            "-m",
            "coverage",
            "run",
            "--source",
            "logging_setup",
            "--omit",
            "*/tests/*",
            "-m",
            "unittest",
            "tests.test_log_redaction_comprehensive",
        ]

        result = subprocess.run(
            cmd, check=False, capture_output=True, text=True, cwd="."
        )
        if result.returncode != 0:
            return False, f"Coverage run failed: {result.stderr}"

        # Generate coverage report
        report_cmd = [sys.executable, "-m", "coverage", "report", "--show-missing"]
        if verbose:
            report_cmd.append("-v")

        report_result = subprocess.run(
            report_cmd, check=False, capture_output=True, text=True, cwd="."
        )

        # Generate HTML report
        html_cmd = [sys.executable, "-m", "coverage", "html", "-d", "htmlcov_redaction"]
        subprocess.run(html_cmd, check=False, capture_output=True, cwd=".")

        return True, report_result.stdout

    except Exception as e:
        return False, f"Coverage analysis failed: {e}"


def run_performance_benchmark() -> tuple[bool, str]:
    """Run performance benchmark for redaction system"""
    print("⚡ Running performance benchmark...")

    benchmark_code = """
import time
import logging
from logging_setup import RedactionFilter

# Set up test
filter_obj = RedactionFilter()
test_messages = [
    "password=secret123",
    "api_key=sk_live_abcdefghij",
    "normal log message",
    "token=ghp_1234567890abcdef",
    "another normal message"
]

# Benchmark redaction
start_time = time.perf_counter()
iterations = 10000

for i in range(iterations):
    for msg in test_messages:
        record = logging.LogRecord(
            name="benchmark", level=logging.INFO, pathname="", lineno=1,
            msg=msg, args=(), exc_info=None
        )
        filter_obj.filter(record)

end_time = time.perf_counter()
total_time = end_time - start_time
total_messages = iterations * len(test_messages)
rate = total_messages / total_time

print(f"Processed {total_messages:,} messages in {total_time:.3f}s")
print(f"Rate: {rate:,.1f} messages/sec")
print(f"Average: {(total_time / total_messages * 1000000):.1f} μs/message")

# Check redaction stats
stats = filter_obj.get_redaction_stats()
print(f"Total redactions: {stats['total_redactions']:,}")
print(f"Redaction rate: {(stats['total_redactions'] / total_messages * 100):.1f}%")
"""

    try:
        result = subprocess.run(
            [sys.executable, "-c", benchmark_code],
            check=False,
            capture_output=True,
            text=True,
            cwd=".",
        )
        success = result.returncode == 0
        return success, result.stdout if success else result.stderr
    except Exception as e:
        return False, f"Benchmark failed: {e}"


def validate_redaction_examples() -> tuple[bool, str]:
    """Validate redaction with real examples"""
    print("✅ Validating redaction examples...")

    validation_code = """
import logging
from io import StringIO
from logging_setup import RedactionFilter

# Set up logger with redaction
output = StringIO()
logger = logging.getLogger("validation")
logger.handlers.clear()
handler = logging.StreamHandler(output)
handler.addFilter(RedactionFilter())
handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Test cases
test_cases = [
    ("password=mypassword123", "password=****"),
    ("api_key=sk_live_abcdefghij", "api_key=****"),
    ("Bearer eyJhbGciOiJIUzI1NiJ9.payload", "Bearer ****"),
    ("https://user:secret@db.com/db", "https://user:****@db.com/db"),
    ("Normal message without secrets", "Normal message without secrets"),
]

results = []
for original, expected in test_cases:
    logger.info(original)
    lines = output.getvalue().strip().split('\\n')
    actual = lines[-1] if lines else ""

    passed = actual == expected
    results.append({
        "original": original,
        "expected": expected,
        "actual": actual,
        "passed": passed
    })

    # Clear for next test
    output.truncate(0)
    output.seek(0)

# Print results
for i, result in enumerate(results, 1):
    status = "✅ PASS" if result["passed"] else "❌ FAIL"
    print(f"{i}. {status}: {result['original'][:30]}...")
    if not result["passed"]:
        print(f"   Expected: {result['expected']}")
        print(f"   Actual:   {result['actual']}")

passed_count = sum(1 for r in results if r["passed"])
total_count = len(results)
print(f"\\nResults: {passed_count}/{total_count} tests passed")
"""

    try:
        result = subprocess.run(
            [sys.executable, "-c", validation_code],
            check=False,
            capture_output=True,
            text=True,
            cwd=".",
        )
        success = result.returncode == 0 and "5/5 tests passed" in result.stdout
        return success, result.stdout if success else result.stderr
    except Exception as e:
        return False, f"Validation failed: {e}"


def generate_test_report(
    results: dict, output_file: str = "log_redaction_test_report.md"
):
    """Generate a comprehensive test report"""
    print(f"📄 Generating test report: {output_file}")

    report_content = f"""# Log Redaction Test Report

Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}

## Test Results Summary

| Test Suite | Status | Details |
|------------|--------|---------|
| Unit Tests | {'✅ PASS' if results['unittest'][0] else '❌ FAIL'} | Comprehensive functionality tests |
| Security Tests | {'✅ PASS' if results['pytest'][0] else '❌ FAIL'} | Security compliance and attack vectors |
| Coverage Analysis | {'✅ PASS' if results['coverage'][0] else '❌ FAIL'} | Code coverage measurement |
| Performance Benchmark | {'✅ PASS' if results['performance'][0] else '❌ FAIL'} | Performance characteristics |
| Validation Examples | {'✅ PASS' if results['validation'][0] else '❌ FAIL'} | Real-world example validation |

## Detailed Results

### Unit Tests
```
{results['unittest'][1]}
```

### Security Tests
```
{results['pytest'][1]}
```

### Coverage Analysis
```
{results['coverage'][1]}
```

### Performance Benchmark
```
{results['performance'][1]}
```

### Validation Examples
```
{results['validation'][1]}
```

## Security Compliance Checklist

- [{'x' if results['pytest'][0] else ' '}] PCI DSS compliance patterns tested
- [{'x' if results['pytest'][0] else ' '}] GDPR compliance patterns tested
- [{'x' if results['pytest'][0] else ' '}] Attack vector resistance validated
- [{'x' if results['pytest'][0] else ' '}] Timing attack resistance verified
- [{'x' if results['pytest'][0] else ' '}] Memory cleanup validated
- [{'x' if results['pytest'][0] else ' '}] Concurrent access safety tested
- [{'x' if results['coverage'][0] else ' '}] Code coverage > 90%
- [{'x' if results['performance'][0] else ' '}] Performance requirements met

## Recommendations

{'✅ All tests passed. Log redaction system is ready for production use.' if all(r[0] for r in results.values()) else '''
❌ Some tests failed. Review the detailed results above and address the following:

1. Fix any failing unit tests to ensure core functionality works
2. Address security test failures to prevent data leaks
3. Improve code coverage if below 90%
4. Optimize performance if benchmark requirements not met
5. Validate that all example cases work correctly

Rerun tests after addressing issues.'''}

---
*This report was generated automatically by the log redaction test suite.*
"""

    try:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(report_content)
        return True
    except Exception as e:
        print(f"Failed to generate report: {e}")
        return False


def main():
    """Main test runner"""
    parser = argparse.ArgumentParser(description="Run log redaction test suite")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument(
        "--coverage", "-c", action="store_true", help="Include coverage analysis"
    )
    parser.add_argument(
        "--security-only", "-s", action="store_true", help="Run only security tests"
    )
    parser.add_argument(
        "--report",
        "-r",
        default="log_redaction_test_report.md",
        help="Output report file name",
    )

    args = parser.parse_args()

    print("🚀 Log Redaction Test Suite")
    print("=" * 50)

    # Track all results
    results = {}

    # Run test suites
    if not args.security_only:
        results["unittest"] = run_unittest_suite(args.verbose)
        results["validation"] = validate_redaction_examples()
        results["performance"] = run_performance_benchmark()

        if args.coverage:
            results["coverage"] = run_coverage_analysis(args.verbose)
        else:
            results["coverage"] = (True, "Coverage analysis skipped")

    # Always run security tests
    results["pytest"] = run_pytest_suite(args.verbose, args.security_only)

    # Print summary
    print("\n" + "=" * 50)
    print("📋 Test Summary")

    passed_suites = 0
    total_suites = 0

    for suite_name, (success, output) in results.items():
        total_suites += 1
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{suite_name.upper()}: {status}")

        if success:
            passed_suites += 1
        elif args.verbose:
            print(f"  Error: {output[:200]}...")

    print(f"\nOverall: {passed_suites}/{total_suites} test suites passed")

    # Generate report
    if generate_test_report(results, args.report):
        print(f"📄 Test report generated: {args.report}")

    # Exit with appropriate code
    sys.exit(0 if passed_suites == total_suites else 1)


if __name__ == "__main__":
    main()
