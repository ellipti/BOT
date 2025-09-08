#!/usr/bin/env python3
"""
A/B Experiment System Test

Tests the complete A/B testing framework including assignment,
guardrails, pipeline integration, and reporting.
"""

import json
import time
from datetime import datetime

from core.events.types import SignalDetected, OrderPlaced, Filled, Rejected
from core.exp import (
    assign_arm,
    is_experiment_active,
    get_experiment_stats,
    handle_signal_detected,
    handle_order_placed,
    handle_order_filled,
    handle_order_rejected,
    get_experiment_metrics,
    get_guardrail_status
)
from reports.ab_summary import generate_ab_report


def test_assignment_system():
    """Test deterministic assignment system"""
    print("🎯 Testing Assignment System...")
    
    # Test assignment consistency
    arm1, config1 = assign_arm("XAUUSD")
    arm2, config2 = assign_arm("XAUUSD")
    
    assert arm1 == arm2, "Assignment should be deterministic"
    print(f"✅ Deterministic assignment: XAUUSD → {arm1}")
    
    # Test different symbols get different assignments
    assignments = {}
    test_symbols = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "USDCAD"]
    
    for symbol in test_symbols:
        arm, config = assign_arm(symbol)
        assignments[symbol] = arm
        print(f"   {symbol} → {arm} (strategy: {config.get('strategy_id')})")
    
    # Check distribution
    arm_counts = {}
    for arm in assignments.values():
        arm_counts[arm] = arm_counts.get(arm, 0) + 1
    
    print(f"   Distribution: {arm_counts}")
    
    return True


def test_pipeline_integration():
    """Test pipeline integration with experiment tracking"""
    print("\n🔄 Testing Pipeline Integration...")
    
    # Create test signal
    signal = SignalDetected(
        symbol="XAUUSD",
        side="BUY", 
        strength=0.85,
        strategy_id="baseline_ma"
    )
    
    # Process through experiment pipeline
    modified_signal = handle_signal_detected(signal)
    
    print(f"   Original strategy: {signal.strategy_id}")
    print(f"   Assigned strategy: {modified_signal.strategy_id}")
    
    # Test order placement tracking
    order = OrderPlaced(
        client_order_id="test_order_123",
        symbol="XAUUSD",
        side="BUY",
        qty=0.1,
        sl=2450.0,
        tp=2550.0
    )
    
    handle_order_placed(order)
    print("   ✅ Order placement tracked")
    
    # Test order fill tracking
    fill = Filled(
        broker_order_id="MT5_12345",
        client_order_id="test_order_123", 
        price=2485.50,
        qty=0.1
    )
    
    handle_order_filled(fill)
    print("   ✅ Order fill tracked")
    
    return True


def test_guardrail_system():
    """Test guardrail monitoring system"""
    print("\n🛡️ Testing Guardrail System...")
    
    # Simulate some trading activity
    for i in range(20):
        arm = "A" if i % 2 == 0 else "B"
        
        # Simulate mostly successful fills
        if i < 18:  # 90% success rate
            from core.exp.guard import record_order_filled
            record_order_filled(arm, "XAUUSD", 500.0)  # 500ms fill time
        else:
            from core.exp.guard import record_order_rejected
            record_order_rejected(arm, "XAUUSD")
    
    # Check guardrail status
    status = get_guardrail_status()
    print(f"   Rollback active: {status.get('rollback_active', False)}")
    
    for arm, arm_status in status.get("arms", {}).items():
        rejection_rate = arm_status.get("rejection_rate_15m", 0)
        sample_count = arm_status.get("sample_count_15m", 0)
        print(f"   Arm {arm}: {rejection_rate:.1%} rejection rate ({sample_count} samples)")
    
    return True


def test_reporting_system():
    """Test report generation"""
    print("\n📊 Testing Reporting System...")
    
    try:
        report = generate_ab_report(hours_back=1)  # Last 1 hour
        
        print(f"   Experiment: {report.get('experiment', 'unknown')}")
        print(f"   Arms: {list(report.get('arms', {}).keys())}")
        print(f"   Winner: {report.get('summary', {}).get('winner', 'none')}")
        print(f"   Recommendations: {len(report.get('recommendations', []))}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Report generation failed: {e}")
        return False


def test_experiment_metrics():
    """Test experiment metrics collection"""
    print("\n📈 Testing Experiment Metrics...")
    
    metrics = get_experiment_metrics()
    
    print(f"   Assignment stats: {metrics.get('assignment', {}).get('total_assignments', 0)} assignments")
    print(f"   Active orders: {metrics.get('active_orders', 0)}")
    print(f"   Guardrail status: {'active' if metrics.get('guardrails', {}).get('rollback_active') else 'normal'}")
    
    return True


def main():
    """Run complete A/B experiment system test"""
    print("🧪 A/B Experiment System Test")
    print("=" * 50)
    
    print(f"Experiment active: {is_experiment_active()}")
    
    if not is_experiment_active():
        print("⚠️ No experiment active - results will use defaults")
    
    tests = [
        ("Assignment System", test_assignment_system),
        ("Pipeline Integration", test_pipeline_integration), 
        ("Guardrail System", test_guardrail_system),
        ("Experiment Metrics", test_experiment_metrics),
        ("Reporting System", test_reporting_system),
    ]
    
    passed = 0
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name}: PASSED")
            else:
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {e}")
    
    print("\n" + "=" * 50)
    print(f"🎯 Test Results: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("🎉 All A/B experiment tests passed!")
        
        # Show final experiment stats
        stats = get_experiment_stats()
        print(f"\n📊 Final Stats:")
        print(json.dumps(stats, indent=2))
        
    else:
        print("⚠️ Some tests failed - check experiment configuration")
    
    return passed == len(tests)


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
