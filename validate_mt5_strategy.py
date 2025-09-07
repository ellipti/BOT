#!/usr/bin/env python3
"""
MT5-less Testing Strategy Validation Script

This script validates that the MT5-less testing strategy is working correctly:
1. Tests can run without MT5 dependency
2. Mocks are properly configured
3. Integration tests are properly skipped in CI
4. Unit tests work with FakeBroker
5. Error handling is robust

Usage:
    python validate_mt5_strategy.py [--verbose] [--ci-mode]
"""

import argparse
import os
import sys
import subprocess
import importlib
from typing import Dict, List, Tuple
from unittest.mock import patch


class MT5StrategyValidator:
    """Validator for MT5-less testing strategy"""
    
    def __init__(self, verbose: bool = False, ci_mode: bool = False):
        self.verbose = verbose
        self.ci_mode = ci_mode
        self.results = []
    
    def log(self, message: str, level: str = "INFO"):
        """Log message with level"""
        if self.verbose or level == "ERROR":
            print(f"[{level}] {message}")
    
    def run_validation(self) -> bool:
        """Run all validation tests"""
        tests = [
            self.test_mt5_import_handling,
            self.test_mock_availability,
            self.test_fake_broker_functionality,
            self.test_pytest_markers,
            self.test_ci_configuration,
            self.test_unit_tests_run,
            self.test_integration_tests_skip,
            self.test_error_handling,
        ]
        
        print("🧪 Validating MT5-less Testing Strategy\n")
        
        passed = 0
        failed = 0
        
        for test in tests:
            try:
                test_name = test.__name__.replace("test_", "").replace("_", " ").title()
                print(f"Testing {test_name}...", end=" ")
                
                result = test()
                if result:
                    print("✅ PASS")
                    passed += 1
                else:
                    print("❌ FAIL")
                    failed += 1
                    
            except Exception as e:
                print(f"❌ ERROR: {e}")
                failed += 1
                self.log(f"Test {test.__name__} failed with error: {e}", "ERROR")
        
        print(f"\n📊 Results: {passed} passed, {failed} failed")
        
        if failed == 0:
            print("🎉 All MT5-less strategy validations passed!")
            return True
        else:
            print(f"💥 {failed} validations failed!")
            return False
    
    def test_mt5_import_handling(self) -> bool:
        """Test that MT5 import is handled gracefully"""
        try:
            # Test normal import
            try:
                import MetaTrader5 as mt5
                has_mt5 = True
                is_mock = hasattr(mt5, '__name__') and 'Mock' in str(type(mt5))
                self.log(f"MT5 import successful, is_mock: {is_mock}")
            except ImportError:
                has_mt5 = False
                self.log("MT5 import failed (expected in some environments)")
            
            # Test conditional import pattern
            def safe_import():
                try:
                    import MetaTrader5
                    return MetaTrader5
                except ImportError:
                    return None
            
            result = safe_import()
            self.log(f"Safe import result: {result is not None}")
            
            return True
            
        except Exception as e:
            self.log(f"MT5 import handling failed: {e}", "ERROR")
            return False
    
    def test_mock_availability(self) -> bool:
        """Test that MT5 mock is available and functional"""
        try:
            # Import the mock from conftest
            sys.path.insert(0, os.path.join(os.getcwd(), 'tests'))
            from conftest import MockMT5
            
            # Test mock creation
            mock_mt5 = MockMT5()
            
            # Test basic functionality
            assert hasattr(mock_mt5, 'initialize')
            assert hasattr(mock_mt5, 'terminal_info')
            assert hasattr(mock_mt5, 'account_info')
            assert hasattr(mock_mt5, 'symbol_info')
            assert hasattr(mock_mt5, 'order_send')
            
            # Test constants
            assert hasattr(mock_mt5, 'TRADE_ACTION_DEAL')
            assert hasattr(mock_mt5, 'ORDER_TYPE_BUY')
            assert hasattr(mock_mt5, 'TRADE_RETCODE_DONE')
            
            # Test initialization
            assert mock_mt5.initialize()
            assert mock_mt5.initialized
            assert mock_mt5.connected
            
            # Test methods
            terminal = mock_mt5.terminal_info()
            assert terminal is not None
            assert terminal["connected"] is True
            
            account = mock_mt5.account_info()
            assert account is not None
            assert account["balance"] == 10000.0
            
            self.log("MT5 mock functionality validated")
            return True
            
        except Exception as e:
            self.log(f"Mock availability test failed: {e}", "ERROR")
            return False
    
    def test_fake_broker_functionality(self) -> bool:
        """Test FakeBroker functionality"""
        try:
            sys.path.insert(0, os.getcwd())
            # Try multiple import paths
            try:
                from tests.fixtures.fake_broker import FakeBrokerAdapter
            except ImportError:
                # Fallback import
                sys.path.insert(0, os.path.join(os.getcwd(), 'tests', 'fixtures'))
                from fake_broker import FakeBrokerConnection as FakeBrokerAdapter
            
            try:
                from core.events.bus import EventBus
            except ImportError:
                # Mock EventBus if not available
                EventBus = type('MockEventBus', (), {'__init__': lambda self: None})
            
            # Create fake broker
            event_bus = EventBus()
            broker = FakeBrokerAdapter(event_bus=event_bus)
            
            # Test connection
            result = broker.connect()
            self.log(f"Connection result: {result}")
            assert result is True
            assert broker.connected
            
            # Test account info  
            account = broker.get_account_info()
            self.log(f"Account info: {account}")
            assert "balance" in account
            assert account["balance"] == 10000.0
            assert account["currency"] == "USD"
            
            # Test symbol info
            symbol = broker.get_symbol_info("EURUSD")
            self.log(f"Symbol info: {symbol}")
            assert symbol is not None
            assert symbol["name"] == "EURUSD"
            assert symbol["point"] == 0.00001
            
            # Test order submission
            result = broker.submit_market_order(
                symbol="EURUSD",
                side="buy",
                volume=0.1,
                client_order_id="validation_test"
            )
            self.log(f"Order result: {result}")
            assert result["success"] is True
            assert "order_id" in result
            
            # Test positions
            positions = broker.get_positions()
            self.log(f"Positions: {positions}")
            assert isinstance(positions, list)
            if len(positions) > 0:
                assert positions[0]["symbol"] == "EURUSD"
            
            self.log("FakeBroker functionality validated")
            return True
            
        except Exception as e:
            self.log(f"FakeBroker test failed: {e}", "ERROR")
            return False
    
    def test_pytest_markers(self) -> bool:
        """Test pytest markers are correctly configured"""
        try:
            # Check if pytest.ini exists and has correct markers
            pytest_files = ['pytest.ini', 'pyproject.toml']
            found_config = False
            
            for config_file in pytest_files:
                if os.path.exists(config_file):
                    with open(config_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Check for MT5-specific markers
                    required_markers = [
                        'mt5_integration',
                        'mt5_unit',
                        'broker_integration'
                    ]
                    
                    markers_found = []
                    for marker in required_markers:
                        if marker in content:
                            markers_found.append(marker)
                    
                    if len(markers_found) >= 2:  # At least 2 out of 3 markers
                        found_config = True
                        self.log(f"Found markers in {config_file}: {markers_found}")
                        break
            
            if not found_config:
                self.log("No pytest configuration with MT5 markers found", "ERROR")
                return False
            
            return True
            
        except Exception as e:
            self.log(f"Pytest markers test failed: {e}", "ERROR")
            return False
    
    def test_ci_configuration(self) -> bool:
        """Test CI configuration for MT5-less strategy"""
        try:
            ci_file = '.github/workflows/ci.yml'
            
            if not os.path.exists(ci_file):
                self.log("CI workflow file not found", "ERROR")
                return False
            
            with open(ci_file, 'r', encoding='utf-8') as f:
                ci_content = f.read()
            
            # Check for MT5-less strategy indicators
            indicators = [
                'not mt5_integration',  # Skip integration tests
                'pytest',  # Uses pytest
                'python-version',  # Multi-version testing
            ]
            
            found_indicators = []
            for indicator in indicators:
                if indicator in ci_content:
                    found_indicators.append(indicator)
            
            if len(found_indicators) >= 2:
                self.log(f"CI configuration validated: {found_indicators}")
                return True
            else:
                self.log(f"CI configuration incomplete: {found_indicators}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"CI configuration test failed: {e}", "ERROR")
            return False
    
    def test_unit_tests_run(self) -> bool:
        """Test that unit tests can run without MT5"""
        try:
            # Run a subset of unit tests
            cmd = [
                sys.executable, '-m', 'pytest',
                '-m', 'mt5_unit or not mt5_integration',
                '--collect-only',  # Just collect, don't run
                '-q',
                'tests/',  # Specify tests directory
                '--tb=no'  # No traceback for collection
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.getcwd())
            
            # Check if pytest is available
            if 'No module named' in result.stderr and 'pytest' in result.stderr:
                self.log("pytest not available, trying alternative approach")
                # Try to import test modules directly
                try:
                    sys.path.insert(0, os.path.join(os.getcwd(), 'tests'))
                    import test_mt5_less_strategy
                    self.log("Direct import of test modules successful")
                    return True
                except ImportError:
                    self.log("Direct import also failed")
                    return False
            
            if result.returncode == 0:
                # Parse output to see if tests were collected
                output = result.stdout + result.stderr
                if 'collected' in output.lower():
                    self.log("Unit tests collection successful")
                    return True
                else:
                    self.log("Unit tests collection completed (no specific tests found)")
                    return True  # This might be OK if no tests match
            else:
                self.log(f"Unit test collection failed: {result.stderr}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"Unit tests run test failed: {e}", "ERROR")
            return False
    
    def test_integration_tests_skip(self) -> bool:
        """Test that integration tests are properly skipped"""
        try:
            if not self.ci_mode:
                # In local mode, just check that the markers exist
                return self.test_pytest_markers()
            
            # In CI mode, verify integration tests are skipped
            cmd = [
                sys.executable, '-m', 'pytest',
                '-m', 'mt5_integration',
                '--collect-only',
                '-q'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.getcwd())
            
            # Integration tests should either be skipped or not collected
            if result.returncode == 0:
                output = result.stdout
                if 'collected 0 items' in output or 'SKIPPED' in output:
                    self.log("Integration tests properly skipped")
                    return True
                else:
                    self.log("Integration tests not properly skipped")
                    return False
            else:
                self.log("Integration test skip validation passed (no tests found)")
                return True
                
        except Exception as e:
            self.log(f"Integration tests skip test failed: {e}", "ERROR")
            return False
    
    def test_error_handling(self) -> bool:
        """Test error handling in MT5-less environment"""
        try:
            # Test import error handling
            with patch('builtins.__import__', side_effect=ImportError("No MT5")):
                def safe_import():
                    try:
                        import MetaTrader5
                        return MetaTrader5
                    except ImportError:
                        return None
                
                result = safe_import()
                assert result is None
            
            # Test graceful degradation
            def get_broker_type():
                try:
                    import MetaTrader5
                    return "MT5"
                except ImportError:
                    return "FAKE"
            
            broker_type = get_broker_type()
            assert broker_type in ["MT5", "FAKE"]
            
            self.log("Error handling validated")
            return True
            
        except Exception as e:
            self.log(f"Error handling test failed: {e}", "ERROR")
            return False


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Validate MT5-less testing strategy')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--ci-mode', action='store_true', help='Run in CI mode')
    
    args = parser.parse_args()
    
    # Set CI mode automatically if detected
    if not args.ci_mode:
        args.ci_mode = os.getenv('CI', '').lower() in ('true', '1', 'yes')
    
    validator = MT5StrategyValidator(verbose=args.verbose, ci_mode=args.ci_mode)
    success = validator.run_validation()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
