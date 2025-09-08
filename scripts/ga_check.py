#!/usr/bin/env python3
"""
GA Readiness Checker - Trading Bot System v1.0.0
Automated Go/No-Go assessment for General Availability release.

Returns:
    Exit 0: All checks PASS - GO for GA
    Exit 1: Critical checks FAIL - NO-GO
"""

import argparse
import json
import logging
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class CheckResult:
    """Individual check result"""

    name: str
    status: str  # PASS/FAIL/WARN
    value: Any
    threshold: Any
    message: str
    category: str  # CRITICAL/HIGH/MEDIUM


@dataclass
class GAAssessment:
    """Overall GA readiness assessment"""

    timestamp: str
    version: str
    overall_status: str  # GO/NO-GO/REVIEW
    total_checks: int
    passed: int
    failed: int
    warnings: int
    checks: list[CheckResult]


class GAChecker:
    """GA Readiness Assessment Engine"""

    def __init__(self):
        self.results: list[CheckResult] = []

    def check_health_endpoint(self) -> CheckResult:
        """Verify /healthz endpoint returns 'ok' status"""
        try:
            response = requests.get(f"{self.base_url}/healthz", timeout=self.timeout)

            if response.status_code != 200:
                return CheckResult(
                    name="Health Endpoint",
                    status="FAIL",
                    value=f"HTTP {response.status_code}",
                    threshold="HTTP 200",
                    message=f"Health endpoint returned {response.status_code}",
                    category="CRITICAL",
                )

            data = response.json()
            health_status = data.get("status", "unknown")

            if health_status == "ok":
                return CheckResult(
                    name="Health Endpoint",
                    status="PASS",
                    value=health_status,
                    threshold="ok",
                    message="Health endpoint operational",
                    category="CRITICAL",
                )
            else:
                return CheckResult(
                    name="Health Endpoint",
                    status="FAIL",
                    value=health_status,
                    threshold="ok",
                    message=f"Health status is '{health_status}', expected 'ok'",
                    category="CRITICAL",
                )

        except requests.RequestException as e:
            return CheckResult(
                name="Health Endpoint",
                status="FAIL",
                value="Connection Failed",
                threshold="HTTP 200 + ok status",
                message=f"Failed to connect to health endpoint: {e}",
                category="CRITICAL",
            )

    @time_check
    def check_metrics_performance(self) -> list[CheckResult]:
        """Validate performance metrics against SLA thresholds"""
        results = []

        try:
            response = requests.get(f"{self.base_url}/metrics", timeout=self.timeout)

            if response.status_code != 200:
                return [
                    CheckResult(
                        name="Metrics Endpoint",
                        status="FAIL",
                        value=f"HTTP {response.status_code}",
                        threshold="HTTP 200",
                        message="Cannot access metrics endpoint",
                        category="CRITICAL",
                    )
                ]

            metrics_text = response.text
            metrics = self.parse_prometheus_metrics(metrics_text)

            # Check trade loop latency
            latency_p95 = metrics.get("trade_loop_latency_ms_p95", 999)
            threshold_latency = self.config["thresholds"]["trade_loop_latency_ms_p95"]

            results.append(
                CheckResult(
                    name="Trade Loop Latency P95",
                    status="PASS" if latency_p95 < threshold_latency else "FAIL",
                    value=f"{latency_p95}ms",
                    threshold=f"<{threshold_latency}ms",
                    message=f"P95 latency: {latency_p95}ms (threshold: {threshold_latency}ms)",
                    category="CRITICAL",
                )
            )

            # Check rejection rate
            reject_rate = metrics.get("rejected_rate", 1.0)
            threshold_reject = self.config["thresholds"]["rejected_rate"]

            results.append(
                CheckResult(
                    name="Order Rejection Rate",
                    status="PASS" if reject_rate < threshold_reject else "FAIL",
                    value=f"{reject_rate:.3%}",
                    threshold=f"<{threshold_reject:.1%}",
                    message=f"Rejection rate: {reject_rate:.3%} (threshold: {threshold_reject:.1%})",
                    category="HIGH",
                )
            )

            # Check fill timeout rate
            timeout_rate = metrics.get("fill_timeout_rate", 1.0)
            threshold_timeout = self.config["thresholds"]["fill_timeout_rate"]

            results.append(
                CheckResult(
                    name="Fill Timeout Rate",
                    status="PASS" if timeout_rate < threshold_timeout else "FAIL",
                    value=f"{timeout_rate:.3%}",
                    threshold=f"<{threshold_timeout:.1%}",
                    message=f"Timeout rate: {timeout_rate:.3%} (threshold: {threshold_timeout:.1%})",
                    category="CRITICAL",
                )
            )

        except requests.RequestException as e:
            results.append(
                CheckResult(
                    name="Metrics Collection",
                    status="FAIL",
                    value="Connection Failed",
                    threshold="Accessible metrics",
                    message=f"Failed to fetch metrics: {e}",
                    category="CRITICAL",
                )
            )

        return results

    def parse_prometheus_metrics(self, metrics_text: str) -> dict[str, float]:
        """Parse Prometheus format metrics text"""
        metrics = {}

        # Simple parsing - in production, use prometheus_client
        for line in metrics_text.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            try:
                if " " in line:
                    metric_name, value = line.split(" ", 1)
                    # Handle labels - extract base metric name
                    if "{" in metric_name:
                        metric_name = metric_name.split("{")[0]
                    metrics[metric_name] = float(value)
            except (ValueError, IndexError):
                continue

        return metrics

    @time_check
    def check_audit_compliance(self) -> list[CheckResult]:
        """Verify audit system compliance and recent activity"""
        results = []
        audit_path = Path(self.config["audit_path"])

        # Check audit directory exists
        if not audit_path.exists():
            results.append(
                CheckResult(
                    name="Audit Directory",
                    status="FAIL",
                    value="Missing",
                    threshold="Exists",
                    message=f"Audit directory {audit_path} does not exist",
                    category="CRITICAL",
                )
            )
            return results

        results.append(
            CheckResult(
                name="Audit Directory",
                status="PASS",
                value="Present",
                threshold="Exists",
                message=f"Audit directory found at {audit_path}",
                category="HIGH",
            )
        )

        # Check for recent audit files
        now = datetime.now()
        age_threshold = timedelta(hours=self.config["thresholds"]["audit_age_hours"])

        recent_files = []
        for file_path in audit_path.glob("*.jsonl"):
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            if now - mtime < age_threshold:
                recent_files.append(file_path.name)

        if recent_files:
            results.append(
                CheckResult(
                    name="Recent Audit Activity",
                    status="PASS",
                    value=f"{len(recent_files)} files",
                    threshold="≥1 file in 24h",
                    message=f"Found {len(recent_files)} recent audit files: {', '.join(recent_files[:3])}",
                    category="HIGH",
                )
            )
        else:
            results.append(
                CheckResult(
                    name="Recent Audit Activity",
                    status="WARN",
                    value="0 files",
                    threshold="≥1 file in 24h",
                    message="No recent audit files found - check audit logging",
                    category="HIGH",
                )
            )

        # Check for export packages
        exports_path = audit_path / "exports"
        if exports_path.exists():
            export_count = len(list(exports_path.glob("audit_export_*.tar.gz")))
            results.append(
                CheckResult(
                    name="Audit Export Packages",
                    status="PASS" if export_count > 0 else "WARN",
                    value=f"{export_count} packages",
                    threshold="≥1 package",
                    message=f"Found {export_count} audit export packages",
                    category="MEDIUM",
                )
            )

        return results

    @time_check
    def check_database_health(self) -> list[CheckResult]:
        """Verify database connectivity and integrity"""
        results = []
        db_path = Path(self.config["database_path"])

        if not db_path.exists():
            return [
                CheckResult(
                    name="Database File",
                    status="FAIL",
                    value="Missing",
                    threshold="Exists",
                    message=f"Database file {db_path} not found",
                    category="CRITICAL",
                )
            ]

        try:
            with sqlite3.connect(str(db_path)) as conn:
                cursor = conn.cursor()

                # Check basic connectivity
                cursor.execute("SELECT 1")
                cursor.fetchone()

                results.append(
                    CheckResult(
                        name="Database Connectivity",
                        status="PASS",
                        value="Connected",
                        threshold="Accessible",
                        message="Database connection successful",
                        category="CRITICAL",
                    )
                )

                # Check for recent orders
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM orders
                    WHERE created_at > datetime('now', '-1 day')
                """
                )
                recent_orders = cursor.fetchone()[0]

                results.append(
                    CheckResult(
                        name="Recent Trading Activity",
                        status="PASS" if recent_orders > 0 else "WARN",
                        value=f"{recent_orders} orders",
                        threshold="≥1 order/day",
                        message=f"Found {recent_orders} orders in last 24h",
                        category="MEDIUM",
                    )
                )

        except sqlite3.Error as e:
            results.append(
                CheckResult(
                    name="Database Health",
                    status="FAIL",
                    value="Error",
                    threshold="Healthy",
                    message=f"Database error: {e}",
                    category="CRITICAL",
                )
            )

        return results

    @time_check
    def check_security_posture(self) -> list[CheckResult]:
        """Validate security configuration and controls"""
        results = []

        # Check JWT configuration
        jwt_config_path = Path("configs/jwt_config.yaml")
        if jwt_config_path.exists():
            results.append(
                CheckResult(
                    name="JWT Configuration",
                    status="PASS",
                    value="Present",
                    threshold="Configured",
                    message="JWT configuration file found",
                    category="HIGH",
                )
            )
        else:
            results.append(
                CheckResult(
                    name="JWT Configuration",
                    status="FAIL",
                    value="Missing",
                    threshold="Configured",
                    message="JWT configuration file not found",
                    category="HIGH",
                )
            )

        # Check for SSL/TLS certificates (if applicable)
        cert_path = Path("certs")
        if cert_path.exists():
            cert_files = list(cert_path.glob("*.pem")) + list(cert_path.glob("*.crt"))
            results.append(
                CheckResult(
                    name="SSL Certificates",
                    status="PASS" if cert_files else "WARN",
                    value=f"{len(cert_files)} certs",
                    threshold="≥1 certificate",
                    message=f"Found {len(cert_files)} certificate files",
                    category="MEDIUM",
                )
            )

        # Check log redaction configuration
        if Path("logging_setup.py").exists():
            results.append(
                CheckResult(
                    name="Log Redaction",
                    status="PASS",
                    value="Configured",
                    threshold="Active",
                    message="Log redaction system configured",
                    category="HIGH",
                )
            )

        return results

    @time_check
    def check_dr_readiness(self) -> list[CheckResult]:
        """Verify disaster recovery capabilities"""
        results = []

        # Check backup scripts
        backup_script = Path("scripts/backup.py")
        if backup_script.exists():
            results.append(
                CheckResult(
                    name="Backup Scripts",
                    status="PASS",
                    value="Present",
                    threshold="Available",
                    message="Backup automation scripts found",
                    category="HIGH",
                )
            )
        else:
            results.append(
                CheckResult(
                    name="Backup Scripts",
                    status="FAIL",
                    value="Missing",
                    threshold="Available",
                    message="Backup scripts not found",
                    category="HIGH",
                )
            )

        # Check backup directory
        backup_dir = Path("backups")
        if backup_dir.exists():
            backup_count = len(list(backup_dir.glob("*.tar.gz")))
            results.append(
                CheckResult(
                    name="Recent Backups",
                    status="PASS" if backup_count > 0 else "WARN",
                    value=f"{backup_count} backups",
                    threshold="≥1 backup",
                    message=f"Found {backup_count} backup files",
                    category="HIGH",
                )
            )

        return results

    def run_all_checks(self) -> GAAssessment:
        """Execute all GA readiness checks"""
        logger.info("Starting GA Readiness Assessment...")
        start_time = time.perf_counter()

        # Execute all check categories
        self.results.extend([self.check_health_endpoint()])
        self.results.extend(self.check_metrics_performance())
        self.results.extend(self.check_audit_compliance())
        self.results.extend(self.check_database_health())
        self.results.extend(self.check_security_posture())
        self.results.extend(self.check_dr_readiness())

        # Calculate summary statistics
        total_checks = len(self.results)
        passed = len([r for r in self.results if r.status == "PASS"])
        failed = len([r for r in self.results if r.status == "FAIL"])
        warnings = len([r for r in self.results if r.status == "WARN"])
        skipped = len([r for r in self.results if r.status == "SKIP"])

        # Determine overall status
        critical_failures = len(
            [r for r in self.results if r.status == "FAIL" and r.category == "CRITICAL"]
        )
        high_failures = len(
            [r for r in self.results if r.status == "FAIL" and r.category == "HIGH"]
        )

        if critical_failures > 0:
            overall_status = "NO-GO"
        elif high_failures > 0:
            overall_status = "REVIEW"
        else:
            overall_status = "GO"

        end_time = time.perf_counter()

        # Build assessment summary
        summary = {
            "assessment_duration_ms": (end_time - start_time) * 1000,
            "critical_failures": critical_failures,
            "high_failures": high_failures,
            "pass_rate": passed / total_checks if total_checks > 0 else 0,
            "categories": {
                "CRITICAL": {"total": 0, "passed": 0, "failed": 0},
                "HIGH": {"total": 0, "passed": 0, "failed": 0},
                "MEDIUM": {"total": 0, "passed": 0, "failed": 0},
            },
        }

        # Calculate category statistics
        for result in self.results:
            cat = result.category
            if cat in summary["categories"]:
                summary["categories"][cat]["total"] += 1
                if result.status == "PASS":
                    summary["categories"][cat]["passed"] += 1
                elif result.status == "FAIL":
                    summary["categories"][cat]["failed"] += 1

        return GAAssessment(
            timestamp=datetime.now().isoformat(),
            version="1.0.0",
            overall_status=overall_status,
            total_checks=total_checks,
            passed=passed,
            failed=failed,
            warnings=warnings,
            skipped=skipped,
            checks=self.results,
            summary=summary,
        )


def print_results(assessment: GAAssessment, detailed: bool = False):
    """Print formatted assessment results"""

    # Header
    print("=" * 80)
    print("🚀 GA READINESS ASSESSMENT - TRADING BOT v1.0.0")
    print("=" * 80)
    print(f"📅 Assessment Time: {assessment.timestamp}")
    print(f"⏱️  Duration: {assessment.summary['assessment_duration_ms']:.1f}ms")
    print()

    # Overall Status
    status_emoji = {"GO": "✅", "NO-GO": "❌", "REVIEW": "⚠️"}
    print(
        f"🎯 **OVERALL STATUS: {status_emoji.get(assessment.overall_status, '❓')} {assessment.overall_status}**"
    )
    print()

    # Summary Statistics
    print("📊 **SUMMARY STATISTICS:**")
    print(f"   Total Checks: {assessment.total_checks}")
    print(f"   ✅ Passed: {assessment.passed}")
    print(f"   ❌ Failed: {assessment.failed}")
    print(f"   ⚠️  Warnings: {assessment.warnings}")
    print(f"   ⏭️  Skipped: {assessment.skipped}")
    print(f"   📈 Pass Rate: {assessment.summary['pass_rate']:.1%}")
    print()

    # Category Breakdown
    print("🏷️  **CATEGORY BREAKDOWN:**")
    for category, stats in assessment.summary["categories"].items():
        if stats["total"] > 0:
            pass_rate = stats["passed"] / stats["total"]
            status = "✅" if stats["failed"] == 0 else "❌" if pass_rate < 0.5 else "⚠️"
            print(
                f"   {status} {category}: {stats['passed']}/{stats['total']} ({pass_rate:.1%})"
            )
    print()

    # Failed Checks (Critical Issues)
    critical_failures = [
        c for c in assessment.checks if c.status == "FAIL" and c.category == "CRITICAL"
    ]
    if critical_failures:
        print("🚨 **CRITICAL FAILURES (MUST FIX):**")
        for check in critical_failures:
            print(f"   ❌ {check.name}: {check.message}")
        print()

    # High Priority Failures
    high_failures = [
        c for c in assessment.checks if c.status == "FAIL" and c.category == "HIGH"
    ]
    if high_failures:
        print("⚠️  **HIGH PRIORITY ISSUES:**")
        for check in high_failures:
            print(f"   ⚠️  {check.name}: {check.message}")
        print()

    # Detailed Results
    if detailed:
        print("📋 **DETAILED RESULTS:**")
        print("-" * 80)

        for category in ["CRITICAL", "HIGH", "MEDIUM"]:
            category_checks = [c for c in assessment.checks if c.category == category]
            if category_checks:
                print(f"\n🏷️  {category} CHECKS:")
                for check in category_checks:
                    status_symbol = {
                        "PASS": "✅",
                        "FAIL": "❌",
                        "WARN": "⚠️",
                        "SKIP": "⏭️",
                    }
                    print(f"   {status_symbol.get(check.status, '❓')} {check.name}")
                    print(f"      Value: {check.value} | Threshold: {check.threshold}")
                    print(f"      Duration: {check.duration_ms:.1f}ms")
                    print(f"      Message: {check.message}")
                    print()

    # Decision Guidance
    print("🎯 **DECISION GUIDANCE:**")
    if assessment.overall_status == "GO":
        print("   ✅ System meets all critical requirements")
        print("   ✅ Ready for General Availability deployment")
        print("   ✅ Proceed with production release")
    elif assessment.overall_status == "REVIEW":
        print("   ⚠️  Some high-priority issues detected")
        print("   ⚠️  Review required before GA deployment")
        print("   ⚠️  Consider fixing issues or accepting risk")
    else:  # NO-GO
        print("   ❌ Critical issues prevent GA deployment")
        print("   ❌ Must fix all critical failures before release")
        print("   ❌ DO NOT proceed to production")

    print("=" * 80)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="GA Readiness Assessment")
    parser.add_argument(
        "--detailed", action="store_true", help="Show detailed check results"
    )
    parser.add_argument("--config", help="Configuration file path")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    parser.add_argument("--quiet", action="store_true", help="Minimal output")

    args = parser.parse_args()

    try:
        # Run assessment
        checker = GAChecker(args.config)
        assessment = checker.run_all_checks()

        if args.json:
            # JSON output for automation
            print(json.dumps(asdict(assessment), indent=2, ensure_ascii=False))
        elif not args.quiet:
            # Human-readable output
            print_results(assessment, args.detailed)
        else:
            # Minimal output
            print(
                f"{assessment.overall_status}: {assessment.passed}/{assessment.total_checks} checks passed"
            )

        # Exit codes for automation
        if assessment.overall_status == "GO":
            sys.exit(0)
        elif assessment.overall_status == "REVIEW":
            sys.exit(2)
        else:  # NO-GO
            sys.exit(1)

    except Exception as e:
        logger.error(f"Assessment failed: {e}")
        if args.json:
            print(json.dumps({"error": str(e), "status": "ERROR"}))
        else:
            print(f"❌ Assessment Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
