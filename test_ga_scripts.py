#!/usr/bin/env python3
"""
Test Suite for GA Scripts - Trading Bot System v1.0.0
Unit tests for GA readiness checker, DR drill runner, and release scripts.

Tests:
- GA readiness assessment logic
- DR drill simulation and validation
- Backup and restore functionality
- Release tagging and validation

Usage:
    python -m pytest test_ga_scripts.py -v
    python test_ga_scripts.py  # Direct execution
"""

import unittest
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sqlite3
import sys
import os

# Add scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "scripts"))

try:
    from ga_check import GAChecker, CheckResult, GAAssessment
    from backup import BackupManager
    from restore import RestoreManager
    from dr_drill import DRDrillRunner
except ImportError as e:
    print(f"Warning: Could not import GA scripts: {e}")
    print("This test suite requires the GA scripts to be available")

class TestGAChecker(unittest.TestCase):
    """Test GA readiness checker functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.test_config = {
            'api_url': 'http://localhost:9101',
            'request_timeout': 5,
            'thresholds': {
                'trade_loop_latency_ms_p95': 250,
                'rejected_rate': 0.05,
                'fill_timeout_rate': 0.02,
                'memory_usage_gb': 2.0,
                'cpu_usage_percent': 70,
                'audit_age_hours': 24
            },
            'database_path': str(self.temp_dir / 'trading.sqlite'),
            'audit_path': str(self.temp_dir / 'audit')
        }
        
        # Create test directories and files
        (self.temp_dir / 'audit').mkdir(exist_ok=True)
        (self.temp_dir / 'configs').mkdir(exist_ok=True)
        
        # Create test database
        db_path = self.temp_dir / 'trading.sqlite'
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute('''
                CREATE TABLE orders (
                    id INTEGER PRIMARY KEY,
                    symbol TEXT,
                    quantity REAL,
                    status TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.execute('''
                INSERT INTO orders (symbol, quantity, status)
                VALUES ('EURUSD', 1000, 'filled')
            ''')
        
        # Create test audit files
        audit_file = self.temp_dir / 'audit' / 'audit_20250908.jsonl'
        with open(audit_file, 'w') as f:
            f.write('{"event": "test", "timestamp": "2025-09-08T10:00:00"}\n')
    
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_check_result_creation(self):
        """Test CheckResult creation"""
        result = CheckResult(
            name="Test Check",
            status="PASS",
            value=100,
            threshold=200,
            message="Test passed",
            category="CRITICAL"
        )
        
        self.assertEqual(result.name, "Test Check")
        self.assertEqual(result.status, "PASS")
        self.assertEqual(result.value, 100)
        self.assertEqual(result.category, "CRITICAL")
    
    @patch('requests.get')
    def test_health_endpoint_success(self, mock_get):
        """Test successful health endpoint check"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}
        mock_get.return_value = mock_response
        
        checker = GAChecker()
        result = checker.check_health_endpoint()
        
        self.assertEqual(result.status, "PASS")
        self.assertEqual(result.value, "ok")
    
    @patch('requests.get')
    def test_health_endpoint_failure(self, mock_get):
        """Test failed health endpoint check"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response
        
        checker = GAChecker()
        result = checker.check_health_endpoint()
        
        self.assertEqual(result.status, "FAIL")
        self.assertIn("HTTP 500", result.value)
    
    @patch('requests.get')
    def test_metrics_parsing(self, mock_get):
        """Test metrics parsing"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = """
# HELP trade_loop_latency_ms_p95 Trade loop latency
trade_loop_latency_ms_p95 180.5
rejected_rate 0.021
fill_timeout_rate 0.008
"""
        mock_get.return_value = mock_response
        
        checker = GAChecker()
        results = checker.check_metrics_performance()
        
        # Should have results for latency, rejection rate, and timeout rate
        self.assertEqual(len(results), 3)
        
        # Check latency result
        latency_result = next(r for r in results if r.name == "Trade Loop Latency P95")
        self.assertEqual(latency_result.status, "PASS")
    
    def test_database_health_check(self):
        """Test database health check"""
        # Create GA checker with test config
        with patch.object(GAChecker, '__init__', lambda x: None):
            checker = GAChecker()
            checker.config = self.test_config
            
            results = checker.check_database_health()
            
            # Should have connectivity and activity results
            self.assertGreater(len(results), 0)
            
            connectivity_result = next(r for r in results if r.name == "Database Connectivity")
            self.assertEqual(connectivity_result.status, "PASS")
    
    def test_audit_compliance_check(self):
        """Test audit compliance check"""
        with patch.object(GAChecker, '__init__', lambda x: None):
            checker = GAChecker()
            checker.config = self.test_config
            
            results = checker.check_audit_compliance()
            
            # Should find audit directory and recent files
            directory_result = next(r for r in results if r.name == "Audit Directory")
            self.assertEqual(directory_result.status, "PASS")
    
    def test_overall_assessment(self):
        """Test complete GA assessment"""
        with patch.object(GAChecker, '__init__', lambda x: None):
            checker = GAChecker()
            checker.config = self.test_config
            
            # Mock all check methods to return passing results
            def mock_health_check():
                return CheckResult("Health", "PASS", "ok", "ok", "OK", "CRITICAL")
            
            def mock_metrics_check():
                return [
                    CheckResult("Latency", "PASS", 180, 250, "OK", "CRITICAL"),
                    CheckResult("Rejection", "PASS", 0.02, 0.05, "OK", "HIGH")
                ]
            
            checker.check_health_endpoint = mock_health_check
            checker.check_metrics_performance = mock_metrics_check
            checker.check_audit_compliance = lambda: [CheckResult("Audit", "PASS", "OK", "OK", "OK", "HIGH")]
            checker.check_database_health = lambda: [CheckResult("Database", "PASS", "OK", "OK", "OK", "CRITICAL")]
            checker.check_security_posture = lambda: [CheckResult("Security", "PASS", "OK", "OK", "OK", "HIGH")]
            checker.check_dr_readiness = lambda: [CheckResult("DR", "PASS", "OK", "OK", "OK", "HIGH")]
            
            assessment = checker.run_all_checks()
            
            self.assertEqual(assessment.overall_status, "GO")
            self.assertGreater(assessment.passed, 0)
            self.assertEqual(assessment.failed, 0)

class TestBackupManager(unittest.TestCase):
    """Test backup functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.backup_dir = self.temp_dir / "backups"
        self.backup_dir.mkdir(exist_ok=True)
        
        # Create test files
        (self.temp_dir / "infra").mkdir(exist_ok=True)
        (self.temp_dir / "configs").mkdir(exist_ok=True)
        (self.temp_dir / "audit").mkdir(exist_ok=True)
        
        # Create test database
        db_path = self.temp_dir / "infra" / "trading.sqlite"
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute('CREATE TABLE test (id INTEGER PRIMARY KEY)')
            conn.execute('INSERT INTO test (id) VALUES (1)')
        
        # Create test config
        config_file = self.temp_dir / "configs" / "test.yaml"
        with open(config_file, 'w') as f:
            f.write("test_setting: value\n")
        
        # Change to temp directory
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
    
    def tearDown(self):
        """Clean up test environment"""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_backup_manager_initialization(self):
        """Test backup manager initialization"""
        manager = BackupManager(str(self.backup_dir))
        self.assertEqual(manager.backup_dir, self.backup_dir)
        self.assertTrue(self.backup_dir.exists())
    
    def test_checksum_calculation(self):
        """Test file checksum calculation"""
        manager = BackupManager(str(self.backup_dir))
        
        # Create test file
        test_file = self.temp_dir / "test.txt"
        with open(test_file, 'w') as f:
            f.write("test content")
        
        checksum1 = manager.calculate_checksum(test_file)
        checksum2 = manager.calculate_checksum(test_file)
        
        # Same file should have same checksum
        self.assertEqual(checksum1, checksum2)
        self.assertEqual(len(checksum1), 64)  # SHA256 hex length
    
    def test_database_backup(self):
        """Test database backup"""
        manager = BackupManager(str(self.backup_dir))
        
        backup_path = self.temp_dir / "test_backup"
        backup_path.mkdir(exist_ok=True)
        
        db_info = manager.backup_databases(backup_path)
        
        self.assertGreater(len(db_info["databases"]), 0)
        self.assertGreater(db_info["total_size"], 0)
        
        # Check that backup file was created
        backup_db = backup_path / "databases" / "trading.sqlite"
        self.assertTrue(backup_db.exists())
    
    def test_config_backup(self):
        """Test configuration backup"""
        manager = BackupManager(str(self.backup_dir))
        
        backup_path = self.temp_dir / "test_backup"
        backup_path.mkdir(exist_ok=True)
        
        config_info = manager.backup_configs(backup_path)
        
        self.assertGreater(len(config_info["files"]), 0)
        self.assertGreater(config_info["total_size"], 0)

class TestRestoreManager(unittest.TestCase):
    """Test restore functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
    
    def tearDown(self):
        """Clean up test environment"""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_restore_manager_initialization(self):
        """Test restore manager initialization"""
        manager = RestoreManager(dry_run=True)
        self.assertTrue(manager.dry_run)
        self.assertIsNotNone(manager.restore_timestamp)
    
    def test_checksum_verification(self):
        """Test checksum verification functionality"""
        manager = RestoreManager(dry_run=True)
        
        # Create test file
        test_file = self.temp_dir / "test.txt"
        with open(test_file, 'w') as f:
            f.write("test content")
        
        checksum = manager.calculate_checksum(test_file)
        self.assertEqual(len(checksum), 64)  # SHA256 hex length

class TestDRDrillRunner(unittest.TestCase):
    """Test DR drill functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        
        # Create basic structure
        (self.temp_dir / "scripts").mkdir(exist_ok=True)
        (self.temp_dir / "backups").mkdir(exist_ok=True)
        (self.temp_dir / "infra").mkdir(exist_ok=True)
        
        # Create mock scripts
        backup_script = self.temp_dir / "scripts" / "backup.py"
        with open(backup_script, 'w') as f:
            f.write('print("Backup completed")')
        
        restore_script = self.temp_dir / "scripts" / "restore.py"
        with open(restore_script, 'w') as f:
            f.write('print("Restore completed")')
    
    def tearDown(self):
        """Clean up test environment"""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_drill_runner_initialization(self):
        """Test DR drill runner initialization"""
        runner = DRDrillRunner(dry_run=True)
        self.assertTrue(runner.dry_run)
        self.assertIsNotNone(runner.drill_id)
        self.assertIn("dr_drill_", runner.drill_id)
    
    def test_phase_logging(self):
        """Test phase logging functionality"""
        runner = DRDrillRunner(dry_run=True)
        
        # Test phase start
        runner.log_phase_start("test_phase")
        self.assertIn("test_phase", runner.results["phases"])
        self.assertEqual(runner.results["phases"]["test_phase"]["status"], "running")
        
        # Test phase end
        runner.log_phase_end("test_phase", True, {"detail": "test"})
        self.assertEqual(runner.results["phases"]["test_phase"]["status"], "success")
        self.assertIn("detail", runner.results["phases"]["test_phase"]["details"])
    
    def test_command_execution_dry_run(self):
        """Test command execution in dry run mode"""
        runner = DRDrillRunner(dry_run=True)
        
        success, stdout, stderr = runner.run_command(["echo", "test"])
        self.assertTrue(success)
        self.assertEqual(stdout, "DRY RUN OUTPUT")
    
    @patch('subprocess.run')
    def test_command_execution_live(self, mock_run):
        """Test command execution in live mode"""
        runner = DRDrillRunner(dry_run=False)
        
        # Mock successful command execution
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.stdout = "Success"
        mock_process.stderr = ""
        mock_run.return_value = mock_process
        
        success, stdout, stderr = runner.run_command(["echo", "test"])
        self.assertTrue(success)
        self.assertEqual(stdout, "Success")
    
    def test_health_checks(self):
        """Test individual health check methods"""
        runner = DRDrillRunner(dry_run=True)
        
        # These should not fail in dry run mode
        self.assertTrue(isinstance(runner.check_database_integrity(), bool))
        self.assertTrue(isinstance(runner.check_config_files(), bool))
        self.assertTrue(isinstance(runner.check_audit_system(), bool))
        self.assertTrue(isinstance(runner.check_application_state(), bool))

class TestIntegrationScenarios(unittest.TestCase):
    """Test integration scenarios"""
    
    def setUp(self):
        """Set up integration test environment"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        
        # Create comprehensive test environment
        dirs_to_create = [
            "scripts", "backups", "infra", "configs", "audit", "logs"
        ]
        
        for dir_name in dirs_to_create:
            (self.temp_dir / dir_name).mkdir(exist_ok=True)
        
        # Create test database
        db_path = self.temp_dir / "infra" / "trading.sqlite"
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute('''
                CREATE TABLE orders (
                    id INTEGER PRIMARY KEY,
                    symbol TEXT,
                    quantity REAL,
                    status TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
    
    def tearDown(self):
        """Clean up integration test environment"""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_backup_restore_cycle(self):
        """Test complete backup and restore cycle"""
        # Create backup
        backup_manager = BackupManager(str(self.temp_dir / "backups"))
        
        backup_path = self.temp_dir / "test_backup"
        backup_path.mkdir(exist_ok=True)
        
        # Test database backup
        db_info = backup_manager.backup_databases(backup_path)
        self.assertGreater(len(db_info["databases"]), 0)
        
        # Test that backup files exist
        backup_db = backup_path / "databases" / "trading.sqlite"
        self.assertTrue(backup_db.exists())
    
    def test_ga_check_with_mocked_environment(self):
        """Test GA check with mocked environment"""
        config = {
            'api_url': 'http://localhost:9101',
            'database_path': str(self.temp_dir / "infra" / "trading.sqlite"),
            'audit_path': str(self.temp_dir / "audit"),
            'thresholds': {
                'trade_loop_latency_ms_p95': 250,
                'rejected_rate': 0.05,
                'fill_timeout_rate': 0.02,
                'audit_age_hours': 24
            }
        }
        
        with patch.object(GAChecker, '__init__', lambda x, y=None: None):
            checker = GAChecker()
            checker.config = config
            
            # Test database health check
            results = checker.check_database_health()
            self.assertGreater(len(results), 0)
    
    def test_end_to_end_dr_drill_dry_run(self):
        """Test end-to-end DR drill in dry run mode"""
        runner = DRDrillRunner(dry_run=True)
        
        # Mock individual phases to pass
        runner.phase_1_create_backup = lambda: True
        runner.phase_2_simulate_failure = lambda: True
        runner.phase_3_restore_from_backup = lambda: True
        runner.phase_4_system_health_check = lambda: True
        runner.phase_5_broker_reconnection = lambda: True
        runner.phase_6_position_reconciliation = lambda: True
        runner.phase_7_smoke_tests = lambda: True
        
        # Run drill
        results = runner.run_full_drill()
        
        self.assertTrue(results["success"])
        self.assertGreater(len(results["phases"]), 0)
        self.assertTrue(results["dry_run"])

def run_tests():
    """Run all tests"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestGAChecker,
        TestBackupManager, 
        TestRestoreManager,
        TestDRDrillRunner,
        TestIntegrationScenarios
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return success/failure
    return result.wasSuccessful()

if __name__ == "__main__":
    print("=" * 80)
    print("🧪 GA SCRIPTS TEST SUITE - Trading Bot System v1.0.0")
    print("=" * 80)
    
    try:
        success = run_tests()
        
        print("\n" + "=" * 80)
        if success:
            print("✅ ALL TESTS PASSED")
            exit_code = 0
        else:
            print("❌ SOME TESTS FAILED")
            exit_code = 1
        print("=" * 80)
        
        sys.exit(exit_code)
        
    except Exception as e:
        print(f"\n❌ TEST SUITE FAILED: {e}")
        sys.exit(1)
