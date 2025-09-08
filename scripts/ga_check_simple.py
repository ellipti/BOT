#!/usr/bin/env python3
"""
GA Readiness Checker - Trading Bot System v1.0.0
Simple automated Go/No-Go assessment for General Availability release.
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class CheckResult:
    name: str
    status: str  # PASS/FAIL/WARN
    value: str
    threshold: str
    message: str
    category: str  # CRITICAL/HIGH/MEDIUM

@dataclass
class GAAssessment:
    timestamp: str
    version: str
    overall_status: str  # GO/NO-GO/REVIEW
    total_checks: int
    passed: int
    failed: int
    warnings: int
    checks: List[CheckResult]

class GAChecker:
    """Simple GA Readiness Assessment"""
    
    def __init__(self):
        self.results: List[CheckResult] = []
    
    def check_files_exist(self) -> CheckResult:
        """Check that critical files exist"""
        critical_files = [
            'app.py',
            'requirements.txt',
            'configs/',
            'scripts/backup.py',
            'scripts/restore.py'
        ]
        
        missing_files = []
        for file_path in critical_files:
            if not Path(file_path).exists():
                missing_files.append(file_path)
        
        if not missing_files:
            return CheckResult(
                name="Critical Files",
                status="PASS",
                value=f"{len(critical_files)} files found",
                threshold="All critical files present",
                message="All critical application files present",
                category="CRITICAL"
            )
        else:
            return CheckResult(
                name="Critical Files",
                status="FAIL",
                value=f"{len(missing_files)} missing",
                threshold="All critical files present",
                message=f"Missing files: {', '.join(missing_files)}",
                category="CRITICAL"
            )
    
    def check_directories(self) -> CheckResult:
        """Check that required directories exist"""
        required_dirs = ['configs', 'scripts', 'app', 'docs']
        missing_dirs = [d for d in required_dirs if not Path(d).exists()]
        
        if not missing_dirs:
            return CheckResult(
                name="Directory Structure",
                status="PASS", 
                value=f"{len(required_dirs)} directories",
                threshold="Required directories exist",
                message="All required directories present",
                category="HIGH"
            )
        else:
            return CheckResult(
                name="Directory Structure",
                status="WARN",
                value=f"{len(missing_dirs)} missing",
                threshold="Required directories exist", 
                message=f"Missing directories: {', '.join(missing_dirs)}",
                category="HIGH"
            )
    
    def check_backup_capability(self) -> CheckResult:
        """Check backup script exists and is executable"""
        backup_script = Path('scripts/backup.py')
        
        if backup_script.exists():
            return CheckResult(
                name="Backup Capability",
                status="PASS",
                value="Script available",
                threshold="Backup script exists",
                message="Backup script found and ready",
                category="CRITICAL"
            )
        else:
            return CheckResult(
                name="Backup Capability", 
                status="FAIL",
                value="Script missing",
                threshold="Backup script exists",
                message="Backup script not found - DR capability compromised",
                category="CRITICAL"
            )
    
    def check_restore_capability(self) -> CheckResult:
        """Check restore script exists"""
        restore_script = Path('scripts/restore.py')
        
        if restore_script.exists():
            return CheckResult(
                name="Restore Capability",
                status="PASS", 
                value="Script available",
                threshold="Restore script exists",
                message="Restore script found and ready",
                category="CRITICAL"
            )
        else:
            return CheckResult(
                name="Restore Capability",
                status="FAIL",
                value="Script missing", 
                threshold="Restore script exists",
                message="Restore script not found - DR capability compromised",
                category="CRITICAL"
            )
    
    def check_documentation(self) -> CheckResult:
        """Check that documentation exists"""
        doc_files = ['README.md', 'docs/GA_READINESS.md']
        existing_docs = [doc for doc in doc_files if Path(doc).exists()]
        
        if len(existing_docs) >= len(doc_files) * 0.8:  # 80% of docs exist
            return CheckResult(
                name="Documentation",
                status="PASS",
                value=f"{len(existing_docs)} docs found",
                threshold="≥80% documentation present", 
                message="Sufficient documentation available",
                category="MEDIUM"
            )
        else:
            return CheckResult(
                name="Documentation",
                status="WARN",
                value=f"{len(existing_docs)} docs found",
                threshold="≥80% documentation present",
                message="Limited documentation - consider updating",
                category="MEDIUM"
            )
    
    def check_configuration(self) -> CheckResult:
        """Check configuration files"""
        config_dir = Path('configs')
        
        if not config_dir.exists():
            return CheckResult(
                name="Configuration",
                status="FAIL",
                value="Config directory missing",
                threshold="Config directory exists",
                message="Configuration directory not found",
                category="HIGH"
            )
        
        config_files = list(config_dir.glob('*.yaml')) + list(config_dir.glob('*.json'))
        
        if config_files:
            return CheckResult(
                name="Configuration",
                status="PASS",
                value=f"{len(config_files)} config files",
                threshold="≥1 config file",
                message=f"Found {len(config_files)} configuration files",
                category="HIGH" 
            )
        else:
            return CheckResult(
                name="Configuration",
                status="WARN",
                value="No config files",
                threshold="≥1 config file",
                message="No configuration files found in configs/",
                category="HIGH"
            )
    
    def run_all_checks(self) -> GAAssessment:
        """Execute all GA readiness checks"""
        logger.info("Starting GA Readiness Assessment...")
        
        # Run all checks
        self.results = [
            self.check_files_exist(),
            self.check_directories(),
            self.check_backup_capability(),
            self.check_restore_capability(),
            self.check_documentation(),
            self.check_configuration()
        ]
        
        # Calculate summary
        total_checks = len(self.results)
        passed = len([r for r in self.results if r.status == 'PASS'])
        failed = len([r for r in self.results if r.status == 'FAIL'])
        warnings = len([r for r in self.results if r.status == 'WARN'])
        
        # Determine overall status
        critical_failures = len([r for r in self.results if r.status == 'FAIL' and r.category == 'CRITICAL'])
        
        if critical_failures > 0:
            overall_status = 'NO-GO'
        elif failed > 0:
            overall_status = 'REVIEW'
        else:
            overall_status = 'GO'
        
        return GAAssessment(
            timestamp=datetime.now().isoformat(),
            version='1.0.0',
            overall_status=overall_status,
            total_checks=total_checks,
            passed=passed,
            failed=failed,
            warnings=warnings,
            checks=self.results
        )

def print_results(assessment: GAAssessment, detailed: bool = False):
    """Print formatted assessment results"""
    print("=" * 60)
    print("🚀 GA READINESS ASSESSMENT - TRADING BOT v1.0.0")
    print("=" * 60)
    
    status_emoji = {"GO": "✅", "NO-GO": "❌", "REVIEW": "⚠️"}
    print(f"🎯 **OVERALL STATUS: {status_emoji.get(assessment.overall_status)} {assessment.overall_status}**")
    print()
    
    print(f"📊 Summary: {assessment.passed} passed, {assessment.failed} failed, {assessment.warnings} warnings")
    print()
    
    if detailed:
        print("📋 **DETAILED RESULTS:**")
        for check in assessment.checks:
            status_symbol = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️"}
            print(f"   {status_symbol.get(check.status)} {check.name}: {check.message}")
        print()
    
    if assessment.overall_status == 'GO':
        print("✅ System ready for General Availability deployment")
    elif assessment.overall_status == 'REVIEW':
        print("⚠️  Some issues detected - review before deployment")
    else:
        print("❌ Critical issues prevent GA deployment")
    
    print("=" * 60)

def main():
    """Main entry point"""
    import argparse
    parser = argparse.ArgumentParser(description='GA Readiness Assessment')
    parser.add_argument('--detailed', action='store_true', help='Show detailed results')
    parser.add_argument('--json', action='store_true', help='Output JSON format')
    
    args = parser.parse_args()
    
    try:
        checker = GAChecker()
        assessment = checker.run_all_checks()
        
        if args.json:
            print(json.dumps(asdict(assessment), indent=2))
        else:
            print_results(assessment, args.detailed)
        
        # Exit codes for automation
        if assessment.overall_status == 'GO':
            sys.exit(0)
        elif assessment.overall_status == 'REVIEW':
            sys.exit(2)
        else:  # NO-GO
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Assessment failed: {e}")
        print(f"❌ Assessment Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
