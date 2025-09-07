# MT5-Less Testing Strategy

This document explains our comprehensive testing strategy that allows the trading bot to be tested in CI environments without requiring MetaTrader5 installation.

## 🎯 Overview

The MT5-less testing strategy provides:

1. **Unit Tests**: Run everywhere with comprehensive mocks
2. **Integration Tests**: Run only when MT5 is available
3. **CI Compatibility**: Public CI runs without MT5 dependencies
4. **Local Development**: Full testing when MT5 is installed
5. **Idempotent Behavior**: Test broker operations without side effects

## 🏗️ Architecture

### Test Categories

| Test Type | Marker | Runs In CI | Requires MT5 | Purpose |
|-----------|--------|------------|--------------|---------|
| Unit Tests | `@pytest.mark.mt5_unit` | ✅ Yes | ❌ No | Test business logic with mocks |
| Integration Tests | `@pytest.mark.mt5_integration` | ❌ No | ✅ Yes | Test real MT5 connectivity |
| Broker Integration | `@pytest.mark.broker_integration` | ❌ No | ✅ Yes | Test live broker operations |

### Components

```
tests/
├── conftest.py              # MT5 availability detection & mocks
├── fixtures/
│   ├── fake_broker.py      # Complete fake broker implementation
│   └── __init__.py
└── test_mt5_less_strategy.py # Example usage patterns
```

## 🔧 Implementation Details

### 1. MT5 Availability Detection

```python
# tests/conftest.py
def mt5_available() -> bool:
    """Check if MetaTrader5 module is available and functional."""
    try:
        mt5_module = importlib.import_module("MetaTrader5")
        return mt5_module is not None
    except ImportError:
        return False
    except Exception:
        return False
```

### 2. Automatic Mocking

```python
# Automatic mock injection when MT5 is not available
@pytest.fixture(autouse=True)
def setup_mt5_mock_in_sys_modules():
    """Inject MT5 mock into sys.modules for all tests."""
    if "MetaTrader5" not in sys.modules and not mt5_available():
        sys.modules["MetaTrader5"] = MockMT5()
```

### 3. Conditional Test Skipping

```python
# Skip integration tests when MT5 is not available
@pytest.mark.mt5_integration
@skip_if_no_mt5("Requires actual MT5 installation")
def test_real_mt5_connection():
    import MetaTrader5 as mt5
    assert mt5.initialize()
```

### 4. Fake Broker Implementation

The `FakeBrokerAdapter` provides a complete in-memory broker that:

- ✅ Implements the same interface as `MT5Broker`
- ✅ Supports idempotent order operations
- ✅ Integrates with the event bus
- ✅ Tracks positions and orders in memory
- ✅ Simulates market data and execution
- ✅ No external dependencies

## 📝 Usage Patterns

### Writing Unit Tests

```python
import pytest
from tests.fixtures.fake_broker import FakeBrokerAdapter

@pytest.mark.mt5_unit
def test_broker_functionality(mock_mt5):
    """Unit test using mocks - runs in CI"""
    broker = FakeBrokerAdapter()
    assert broker.connect()

    result = broker.submit_market_order(
        symbol="EURUSD",
        side="buy",
        volume=0.1,
        client_order_id="test_001"
    )
    assert result["success"]
```

### Writing Integration Tests

```python
from tests.conftest import skip_if_no_mt5

@pytest.mark.mt5_integration
@skip_if_no_mt5("Requires real MT5 connection")
def test_real_mt5_integration():
    """Integration test - skipped in CI, runs locally if MT5 available"""
    import MetaTrader5 as mt5

    initialized = mt5.initialize()
    if not initialized:
        pytest.skip("Could not initialize MT5")

    # Test real MT5 functionality
    terminal_info = mt5.terminal_info()
    assert terminal_info is not None
```

### Module-Level Skipping

```python
# Skip entire test modules for integration tests
import pytest
from tests.conftest import mt5_available

pytestmark = pytest.mark.skipif(
    not mt5_available() and "integration" in __file__,
    reason="MT5 integration tests require MT5 installation"
)
```

## 🚀 CI/CD Integration

### Main CI Pipeline (`.github/workflows/ci.yml`)

```yaml
- name: "🧪 Run Tests"
  run: |
    # Run tests with MT5-less strategy:
    # - Unit tests (including MT5 mocks): Always run
    # - Integration tests requiring MT5: Skip in CI
    pytest -q --tb=short --maxfail=3 \
      -m "not mt5_integration" \
      --cov=core --cov=adapters --cov=tests
```

**Result**: ✅ All unit tests pass, MT5 integration tests are skipped

### Optional MT5 Integration Pipeline (`.github/workflows/ci-mt5.yml`)

```yaml
# Only runs when:
# 1. Manual trigger with run_integration=true
# 2. MT5 secrets are available
# 3. Self-hosted runner with MT5 installed

- name: Run MT5 integration tests
  run: |
    pytest -v -m "mt5_integration"
```

**Result**: ✅ Real MT5 tests run only in controlled environments

## 🎯 Benefits

### For CI/CD
- ✅ **Fast builds**: No MT5 dependency installation
- ✅ **Reliable**: No flaky external connections
- ✅ **Cross-platform**: Works on Ubuntu, Windows, macOS
- ✅ **Cost-effective**: Uses standard GitHub runners

### For Development
- ✅ **Local flexibility**: Run integration tests when MT5 available
- ✅ **Comprehensive coverage**: Unit tests cover business logic
- ✅ **Fast feedback**: Mocked tests run quickly
- ✅ **Idempotent**: No side effects during testing

### For Code Quality
- ✅ **Separation of concerns**: Business logic vs. integration
- ✅ **Testable design**: Forces good architecture
- ✅ **Maintainable**: Easy to add new broker adapters
- ✅ **Documented**: Clear testing patterns

## 📊 Test Execution Matrix

| Environment | Unit Tests | MT5 Integration | Broker Integration |
|-------------|------------|----------------|-------------------|
| **GitHub CI** | ✅ Pass (mocks) | ⏭️ Skip | ⏭️ Skip |
| **Local (no MT5)** | ✅ Pass (mocks) | ⏭️ Skip | ⏭️ Skip |
| **Local (with MT5)** | ✅ Pass (mocks) | ✅ Run | ✅ Run |
| **Self-hosted CI** | ✅ Pass (mocks) | ✅ Run | ✅ Run |

## 🔍 Example Test Results

### Public CI (No MT5)
```
test_fake_broker_unit_test PASSED              ✅
test_mt5_mock_functionality PASSED             ✅
test_real_mt5_integration SKIPPED              ⏭️ (MT5 not available)
test_broker_integration SKIPPED                ⏭️ (Broker not available)
```

### Local Development (With MT5)
```
test_fake_broker_unit_test PASSED              ✅
test_mt5_mock_functionality PASSED             ✅
test_real_mt5_integration PASSED               ✅
test_broker_integration PASSED                 ✅
```

## 🎪 Running Tests

### All Tests (Skip Integration)
```bash
pytest -m "not mt5_integration"
```

### Only Unit Tests
```bash
pytest -m "mt5_unit"
```

### Only Integration Tests (if MT5 available)
```bash
pytest -m "mt5_integration"
```

### Specific Test Categories
```bash
pytest -m "event_bus"           # Event system tests
pytest -m "order_book"          # Order book tests
pytest -m "risk"                # Risk management tests
pytest -m "feed"                # Data feed tests
```

### Coverage Report
```bash
pytest --cov=core --cov=adapters --cov=tests --cov-report=html
```

## 🏆 Success Criteria

✅ **Public CI**: Unit tests pass, integration tests skipped
✅ **Local Development**: All tests can run when MT5 available
✅ **Fake Broker**: Comprehensive simulation without dependencies
✅ **Event Integration**: Full event bus testing with mocks
✅ **Idempotent Operations**: Repeatable test execution
✅ **Cross-Platform**: Works on Windows, Linux, macOS
✅ **Performance**: Fast test execution with mocks
✅ **Documentation**: Clear patterns and examples

This strategy ensures robust testing across all environments while maintaining the flexibility to run comprehensive integration tests when the full MT5 stack is available.
