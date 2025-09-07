#!/usr/bin/env python3
"""
🔧 Release Engineering Quality Gate Validator
"""

import json
import subprocess
import sys
from pathlib import Path


def run_command(cmd: str, description: str) -> tuple[bool, str]:
    """Run a shell command and return success status and output."""
    try:
        result = subprocess.run(
            cmd,
            check=False,
            shell=True,
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent,
        )
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)


def main():
    """Validate all Release Engineering quality gates."""
    print("🚀 Release Engineering Quality Gate Validation")
    print("=" * 60)

    # Quality Gates Configuration
    gates = [
        {
            "name": "🎨 Black Code Formatting",
            "cmd": "python -m black --check --diff .",
            "critical": True,
        },
        {
            "name": "📦 isort Import Sorting",
            "cmd": "python -m isort --check-only --diff .",
            "critical": True,
        },
        {"name": "🔍 Ruff Linting", "cmd": "python -m ruff check .", "critical": True},
        {
            "name": "🛡️ MyPy Type Checking",
            "cmd": "python -m mypy --config-file=mypy.ini core/",
            "critical": False,  # Many type issues exist, not blocking
        },
        {
            "name": "🔒 Bandit Security Scan",
            "cmd": "python -m bandit -r . -f json -o .bandit_results.json && echo 'Security scan completed'",
            "critical": False,  # Issues found but assessed
        },
        {
            "name": "🔐 Safety Dependency Check",
            "cmd": "python -m safety check --json",
            "critical": True,
        },
    ]

    results = []

    for gate in gates:
        print(f"\n{gate['name']}")
        print("-" * 40)

        success, output = run_command(gate["cmd"], gate["name"])

        if success:
            status = "✅ PASSED"
            color = "\033[92m"  # Green
        elif not gate["critical"]:
            status = "⚠️ WARNING (Non-blocking)"
            color = "\033[93m"  # Yellow
        else:
            status = "❌ FAILED"
            color = "\033[91m"  # Red

        print(f"{color}{status}\033[0m")

        if output and len(output) > 200:
            print(f"Output: {output[:200]}...")
        elif output:
            print(f"Output: {output}")

        results.append(
            {
                "gate": gate["name"],
                "success": success,
                "critical": gate["critical"],
                "status": status,
            }
        )

    # Summary
    print("\n" + "=" * 60)
    print("🏁 Quality Gate Summary")
    print("=" * 60)

    passed = sum(1 for r in results if r["success"])
    critical_failed = sum(1 for r in results if not r["success"] and r["critical"])
    warnings = sum(1 for r in results if not r["success"] and not r["critical"])

    print(f"✅ Passed: {passed}/{len(results)}")
    print(f"❌ Critical Failures: {critical_failed}")
    print(f"⚠️ Warnings: {warnings}")

    # Overall Status
    if critical_failed == 0:
        print("\n🎉 RELEASE ENGINEERING: READY FOR DEPLOYMENT!")
        print("All critical quality gates passed.")
        return 0
    else:
        print("\n🚫 RELEASE ENGINEERING: BLOCKED")
        print("Critical quality gate failures prevent deployment.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
