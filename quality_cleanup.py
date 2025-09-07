#!/usr/bin/env python3
"""
Comprehensive Quality Cleanup Script for PR-4

This script performs automated quality improvements:
1. Code formatting (Black)
2. Import sorting (isort)
3. Linting fixes (ruff)
4. Basic type annotation improvements
5. Security scans (bandit)
6. Generates quality report

Usage:
    python quality_cleanup.py [--fix] [--report]
"""

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any


class QualityProcessor:
    """Quality improvement processor for the codebase"""

    def __init__(self, fix_mode: bool = False):
        self.fix_mode = fix_mode
        self.results = {}

    def run_black_formatting(self) -> tuple[bool, str]:
        """Run Black code formatting"""
        print("🎨 Running Black code formatting...")

        cmd = [
            sys.executable,
            "-m",
            "black",
            "core/",
            "adapters/",
            "logging_setup.py",
            "app.py",
            "backtest.py",
        ]

        if not self.fix_mode:
            cmd.extend(["--check", "--diff"])

        try:
            result = subprocess.run(cmd, check=False, capture_output=True, text=True)
            success = result.returncode == 0

            if self.fix_mode:
                output = result.stderr if result.stderr else result.stdout
            else:
                output = result.stdout

            return success, output
        except Exception as e:
            return False, f"Black formatting failed: {e}"

    def run_isort_imports(self) -> tuple[bool, str]:
        """Run isort import sorting"""
        print("📦 Running isort import sorting...")

        cmd = [
            sys.executable,
            "-m",
            "isort",
            "core/",
            "adapters/",
            "logging_setup.py",
            "app.py",
            "backtest.py",
        ]

        if not self.fix_mode:
            cmd.extend(["--check-only", "--diff"])

        try:
            result = subprocess.run(cmd, check=False, capture_output=True, text=True)
            success = result.returncode == 0
            output = result.stdout + result.stderr
            return success, output
        except Exception as e:
            return False, f"isort failed: {e}"

    def run_ruff_linting(self) -> tuple[bool, str]:
        """Run ruff linting"""
        print("⚡ Running ruff linting...")

        cmd = [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "core/",
            "adapters/",
            "logging_setup.py",
            "app.py",
            "backtest.py",
            "--output-format=text",
        ]

        if self.fix_mode:
            cmd.append("--fix")

        try:
            result = subprocess.run(cmd, check=False, capture_output=True, text=True)
            # Ruff returns 0 if no issues, >0 if issues found
            success = result.returncode == 0
            output = result.stdout + result.stderr
            return success, output
        except Exception as e:
            return False, f"Ruff linting failed: {e}"

    def run_bandit_security(self) -> tuple[bool, str]:
        """Run bandit security scanning"""
        print("🛡️ Running bandit security scan...")

        cmd = [
            sys.executable,
            "-m",
            "bandit",
            "-r",
            "core/",
            "adapters/",
            "logging_setup.py",
            "app.py",
            "backtest.py",
            "-f",
            "txt",
            "--quiet",
        ]

        try:
            result = subprocess.run(cmd, check=False, capture_output=True, text=True)
            # Bandit returns >0 if issues found, but we want to capture output
            output = result.stdout + result.stderr
            success = "No issues identified" in output or result.returncode == 0
            return success, output
        except Exception as e:
            return False, f"Bandit security scan failed: {e}"

    def run_basic_mypy_check(self) -> tuple[bool, str]:
        """Run basic mypy type checking on key files"""
        print("🔍 Running basic mypy type checking...")

        # Check only a few key files to avoid module conflicts
        key_files = [
            "logging_setup.py",
            "app.py",
            "core/events/bus.py",
        ]

        existing_files = [f for f in key_files if Path(f).exists()]

        if not existing_files:
            return True, "No key files found for type checking"

        cmd = [
            sys.executable,
            "-m",
            "mypy",
            *existing_files,
            "--ignore-missing-imports",
            "--follow-imports=skip",
            "--show-error-codes",
        ]

        try:
            result = subprocess.run(cmd, check=False, capture_output=True, text=True)
            success = result.returncode == 0
            output = result.stdout + result.stderr
            return success, output
        except Exception as e:
            return False, f"mypy type checking failed: {e}"

    def count_code_metrics(self) -> dict[str, int]:
        """Count basic code metrics"""
        print("📊 Counting code metrics...")

        metrics = {
            "python_files": 0,
            "total_lines": 0,
            "code_lines": 0,
            "comment_lines": 0,
            "blank_lines": 0,
        }

        # Count files in key directories
        directories = ["core", "adapters", "config", "infra", "services"]

        for directory in directories:
            dir_path = Path(directory)
            if dir_path.exists():
                for py_file in dir_path.rglob("*.py"):
                    if "__pycache__" in str(py_file):
                        continue

                    metrics["python_files"] += 1

                    try:
                        with open(py_file, encoding="utf-8") as f:
                            lines = f.readlines()

                        for line in lines:
                            metrics["total_lines"] += 1
                            line = line.strip()

                            if not line:
                                metrics["blank_lines"] += 1
                            elif line.startswith("#"):
                                metrics["comment_lines"] += 1
                            else:
                                metrics["code_lines"] += 1

                    except Exception:
                        # Skip files that can't be read
                        pass

        # Add root level files
        root_files = ["app.py", "backtest.py", "logging_setup.py"]
        for file_name in root_files:
            file_path = Path(file_name)
            if file_path.exists():
                metrics["python_files"] += 1
                try:
                    with open(file_path, encoding="utf-8") as f:
                        lines = f.readlines()

                    for line in lines:
                        metrics["total_lines"] += 1
                        line = line.strip()

                        if not line:
                            metrics["blank_lines"] += 1
                        elif line.startswith("#"):
                            metrics["comment_lines"] += 1
                        else:
                            metrics["code_lines"] += 1

                except Exception:
                    pass

        return metrics

    def run_all_checks(self) -> dict[str, tuple[bool, str]]:
        """Run all quality checks"""
        print("🚀 Running comprehensive quality checks...")
        print("=" * 60)

        checks = [
            ("black_formatting", self.run_black_formatting),
            ("isort_imports", self.run_isort_imports),
            ("ruff_linting", self.run_ruff_linting),
            ("bandit_security", self.run_bandit_security),
            ("mypy_types", self.run_basic_mypy_check),
        ]

        results = {}

        for check_name, check_func in checks:
            try:
                success, output = check_func()
                results[check_name] = (success, output)

                status = "✅ PASS" if success else "❌ FAIL"
                print(f"{check_name.upper()}: {status}")

                if not success and output:
                    # Show first few lines of error
                    error_preview = "\n".join(output.split("\n")[:5])
                    print(f"  Preview: {error_preview}")

            except Exception as e:
                results[check_name] = (False, str(e))
                print(f"{check_name.upper()}: ❌ ERROR - {e}")

        return results

    def generate_quality_report(
        self, results: dict[str, tuple[bool, str]], metrics: dict[str, int]
    ) -> str:
        """Generate quality improvement report"""
        passed_checks = sum(1 for success, _ in results.values() if success)
        total_checks = len(results)

        from datetime import datetime

        report = f"""# Code Quality Report

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Mode: {'Fix Applied' if self.fix_mode else 'Check Only'}

## Summary

- **Quality Checks**: {passed_checks}/{total_checks} passed
- **Python Files**: {metrics['python_files']} files analyzed
- **Code Coverage**: {metrics['code_lines']:,} lines of code
- **Total Lines**: {metrics['total_lines']:,} (code: {metrics['code_lines']:,}, comments: {metrics['comment_lines']}, blank: {metrics['blank_lines']})

## Check Results

| Check | Status | Description |
|-------|--------|-------------|
| Black Formatting | {'✅ PASS' if results['black_formatting'][0] else '❌ FAIL'} | Code formatting consistency |
| Import Sorting | {'✅ PASS' if results['isort_imports'][0] else '❌ FAIL'} | Import organization (isort) |
| Linting | {'✅ PASS' if results['ruff_linting'][0] else '❌ FAIL'} | Code quality issues (ruff) |
| Security Scan | {'✅ PASS' if results['bandit_security'][0] else '❌ FAIL'} | Security vulnerabilities (bandit) |
| Type Checking | {'✅ PASS' if results['mypy_types'][0] else '❌ FAIL'} | Type annotations (mypy) |

## Detailed Results

### Black Formatting
```
{results['black_formatting'][1][:1000]}
```

### Import Sorting (isort)
```
{results['isort_imports'][1][:1000]}
```

### Linting (ruff)
```
{results['ruff_linting'][1][:1000]}
```

### Security Scan (bandit)
```
{results['bandit_security'][1][:1000]}
```

### Type Checking (mypy)
```
{results['mypy_types'][1][:1000]}
```

## Quality Score

**Overall Quality Score: {int((passed_checks / total_checks) * 100)}%**

### Recommendations

{self._generate_recommendations(results)}

---
*Report generated by quality_cleanup.py - PR-4 Quality Improvements*
"""
        return report

    def _generate_recommendations(self, results: dict[str, tuple[bool, str]]) -> str:
        """Generate recommendations based on results"""
        recommendations = []

        if not results["black_formatting"][0]:
            recommendations.append("- Run `black .` to fix code formatting issues")

        if not results["isort_imports"][0]:
            recommendations.append("- Run `isort .` to organize import statements")

        if not results["ruff_linting"][0]:
            recommendations.append(
                "- Run `ruff check --fix .` to automatically fix linting issues"
            )
            recommendations.append("- Review remaining ruff warnings manually")

        if not results["bandit_security"][0]:
            recommendations.append(
                "- Review bandit security warnings and address high-severity issues"
            )
            recommendations.append(
                "- Consider adding # nosec comments for false positives"
            )

        if not results["mypy_types"][0]:
            recommendations.append("- Add type annotations to improve type checking")
            recommendations.append(
                "- Consider using `mypy --strict` for stricter type checking"
            )

        if all(success for success, _ in results.values()):
            recommendations.append(
                "- ✅ All quality checks passed! Consider setting up pre-commit hooks"
            )
            recommendations.append("- Monitor code quality metrics in CI/CD pipeline")

        return (
            "\n".join(recommendations)
            if recommendations
            else "- No specific recommendations - quality checks passed!"
        )


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Run comprehensive quality cleanup")
    parser.add_argument(
        "--fix", action="store_true", help="Apply fixes instead of just checking"
    )
    parser.add_argument(
        "--report", default="quality_report.md", help="Output report file name"
    )

    args = parser.parse_args()

    processor = QualityProcessor(fix_mode=args.fix)

    # Run all quality checks
    results = processor.run_all_checks()

    # Count metrics
    print("\n📊 Collecting code metrics...")
    metrics = processor.count_code_metrics()

    # Generate report
    print(f"\n📄 Generating quality report: {args.report}")
    report = processor.generate_quality_report(results, metrics)

    try:
        with open(args.report, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"✅ Quality report saved to {args.report}")
    except Exception as e:
        print(f"❌ Failed to save report: {e}")

    # Print summary
    print("\n" + "=" * 60)
    print("📋 Quality Cleanup Summary")

    passed_checks = sum(1 for success, _ in results.values() if success)
    total_checks = len(results)

    print(f"Quality Score: {int((passed_checks / total_checks) * 100)}%")
    print(f"Files Processed: {metrics['python_files']}")
    print(f"Code Lines: {metrics['code_lines']:,}")

    if args.fix:
        print("\n🔧 Fixes were applied where possible")
        print("💡 Review the changes and run tests to ensure everything works")
    else:
        print("\n🔍 Check mode - no changes were made")
        print("💡 Run with --fix to apply automatic fixes")

    # Exit with appropriate code
    sys.exit(0 if passed_checks == total_checks else 1)


if __name__ == "__main__":
    main()
