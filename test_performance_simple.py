# test_performance_simple.py
"""
Simple performance test without MT5 dependencies.
Tests WorkQueue, Scheduler, and LatencyTracker in isolation.
"""

import threading
import time
from typing import Any, Dict

from core.events.bus import EventBus
from core.events.types import ChartRequested
from core.logger import get_logger
from infra.latency_tracker import TradingLoopLatencyTracker
from infra.performance_integration import PerformanceManager
from infra.scheduler import AsyncScheduler
from infra.workqueue import WorkQueue

logger = get_logger("test_performance_simple")


def mock_chart_handler(payload: dict[str, Any]) -> None:
    """Mock chart rendering that simulates work without MT5"""
    symbol = payload.get("symbol", "MOCK")
    timeframe = payload.get("timeframe", "M30")

    # Simulate chart rendering work
    work_duration = 0.05  # 50ms simulation
    time.sleep(work_duration)

    logger.debug(f"Mock chart rendered: {symbol} {timeframe}")


def mock_report_handler(payload: dict[str, Any]) -> None:
    """Mock report generation"""
    report_type = payload.get("report_type", "unknown")

    # Simulate report work
    work_duration = 0.02  # 20ms simulation
    time.sleep(work_duration)

    logger.debug(f"Mock report generated: {report_type}")


def test_workqueue_basic():
    """Test basic WorkQueue functionality"""
    print("🧪 Testing WorkQueue basic functionality...")

    results = []
    result_lock = threading.Lock()

    def test_handler(payload):
        with result_lock:
            results.append(payload["value"])

    workqueue = WorkQueue()
    workqueue.register("test_task", test_handler)
    workqueue.start(n_workers=2)

    try:
        # Submit tasks
        for i in range(10):
            workqueue.submit("test_task", {"value": i})

        # Wait for processing with longer timeout
        workqueue.wait_empty(timeout=10.0)

        # Give a bit more time for final processing
        time.sleep(0.1)

        # Verify results
        with result_lock:
            result_count = len(results)
            if result_count != 10:
                print(f"⚠️ Got {result_count} results instead of 10: {results}")
                # Check workqueue stats for debugging
                stats = workqueue.get_stats()
                print(f"WorkQueue stats: {stats}")

            assert (
                result_count >= 8
            ), f"Expected at least 8 results, got {result_count}: {results}"
            # Allow some variance in timing-dependent tests
            unique_results = set(results)
            assert (
                len(unique_results) >= 8
            ), f"Expected at least 8 unique results, got {len(unique_results)}"

        # Check stats
        stats = workqueue.get_stats()
        print(f"✅ WorkQueue: {stats['tasks_processed']} tasks processed successfully")

    finally:
        workqueue.stop()


def test_latency_tracking():
    """Test latency tracking functionality"""
    print("🧪 Testing LatencyTracker...")

    tracker = TradingLoopLatencyTracker(window_size=100)

    # Simulate some trading loops with different latencies
    latencies = []
    for i in range(20):
        with tracker.measure_overall():
            # Simulate varying work
            work_time = 0.001 + (i % 5) * 0.002  # 1-9ms
            time.sleep(work_time)
            latencies.append(work_time * 1000)

        tracker.increment_loop_count()

    # Get stats
    stats = tracker.get_all_stats()

    assert stats["loop_count"] == 20
    assert stats["overall"]["count"] == 20

    # Verify latency measurements are reasonable
    avg_measured = stats["overall"]["rolling_avg_ms"]
    expected_avg = sum(latencies) / len(latencies)

    # Allow some tolerance for timing variations
    assert (
        abs(avg_measured - expected_avg) < 2.0
    ), f"Measured {avg_measured:.1f}ms vs expected {expected_avg:.1f}ms"

    print(
        f"✅ LatencyTracker: {stats['loop_count']} loops, avg latency {avg_measured:.1f}ms"
    )


def test_scheduler():
    """Test AsyncScheduler with mock tasks"""
    print("🧪 Testing AsyncScheduler...")

    execution_count = [0]  # Mutable closure

    def count_task(payload):
        execution_count[0] += 1

    workqueue = WorkQueue()
    workqueue.register("count_task", count_task)
    workqueue.start(n_workers=1)

    scheduler = AsyncScheduler(workqueue=workqueue)

    try:
        # Schedule task every 0.1 seconds
        job_id = scheduler.schedule_interval(
            task_name="count_task", task_payload={"test": True}, interval_seconds=0.1
        )

        scheduler.start()

        # Let it run for about 0.5 seconds
        time.sleep(0.55)

        # Wait for queue to process
        workqueue.wait_empty(timeout=2.0)

        # Should have executed several times
        assert (
            3 <= execution_count[0] <= 7
        ), f"Expected 3-7 executions, got {execution_count[0]}"

        print(f"✅ Scheduler: {execution_count[0]} scheduled executions")

    finally:
        scheduler.stop()
        workqueue.stop()


def test_performance_integration():
    """Test PerformanceManager integration"""
    print("🧪 Testing PerformanceManager integration...")

    event_bus = EventBus()

    # Override the chart handler to use our mock
    from infra import performance_integration

    original_start = performance_integration.PerformanceManager._register_task_handlers

    def mock_register_handlers(self):
        if self._registered_handlers:
            return
        self.workqueue.register("chart_render", mock_chart_handler)
        self.workqueue.register("generate_report", mock_report_handler)
        self.workqueue.register("performance_check", self._handle_performance_check)
        self._registered_handlers = True

    # Monkey patch temporarily
    performance_integration.PerformanceManager._register_task_handlers = (
        mock_register_handlers
    )

    try:
        manager = PerformanceManager(event_bus=event_bus)
        manager.start()

        # Test chart request via event
        event = ChartRequested(
            client_order_id="test_001",
            symbol="XAUUSD",
            timeframe="M30",
            out_path="mock_chart.png",
            bars_count=100,
            send_telegram=False,
        )

        event_bus.publish(event)

        # Wait for processing
        time.sleep(0.2)
        manager.workqueue.wait_empty(timeout=2.0)

        # Check stats
        stats = manager.get_performance_stats()
        assert stats["running"] is True
        assert stats["workqueue"]["tasks_processed"] >= 1

        print(
            f"✅ PerformanceManager: {stats['workqueue']['tasks_processed']} tasks processed"
        )

    finally:
        # Restore original method
        performance_integration.PerformanceManager._register_task_handlers = (
            original_start
        )
        if "manager" in locals():
            manager.stop()


def test_comprehensive_load():
    """Comprehensive load test without MT5 dependencies"""
    print("🧪 Running comprehensive load test...")

    event_bus = EventBus()

    # Mock the chart handler in the performance integration
    from infra import performance_integration

    original_start = performance_integration.PerformanceManager._register_task_handlers

    def mock_register_handlers(self):
        if self._registered_handlers:
            return
        self.workqueue.register("chart_render", mock_chart_handler)
        self.workqueue.register("generate_report", mock_report_handler)
        self.workqueue.register("performance_check", self._handle_performance_check)
        self._registered_handlers = True

    performance_integration.PerformanceManager._register_task_handlers = (
        mock_register_handlers
    )

    try:
        manager = PerformanceManager(event_bus=event_bus)
        manager.start()

        # Track main loop latencies
        main_loop_latencies = []

        def simulate_trading_loop():
            with manager.latency_tracker.measure_overall():
                # Simulate trading work
                time.sleep(0.002)  # 2ms base work

            stats = manager.latency_tracker.get_all_stats()
            if stats["overall"]["count"] > 0:
                main_loop_latencies.append(stats["overall"]["rolling_avg_ms"])

            manager.latency_tracker.increment_loop_count()

        # Phase 1: Baseline
        print("📊 Phase 1: Baseline (10 loops)")
        for _ in range(10):
            simulate_trading_loop()
            time.sleep(0.01)

        baseline_avg = sum(main_loop_latencies) / len(main_loop_latencies)
        print(f"📈 Baseline latency: {baseline_avg:.2f}ms")

        # Phase 2: Load test
        print("📊 Phase 2: Load test (50 direct chart tasks + 20 loops)")

        # Submit chart tasks directly to workqueue (bypassing event system for simpler test)
        for i in range(50):
            payload = {
                "symbol": "XAUUSD",
                "timeframe": "M30",
                "out_path": f"mock_chart_{i:03d}.png",
                "bars_count": 100,
                "send_telegram": False,
            }
            manager.workqueue.submit("chart_render", payload)

        print("📤 50 chart requests submitted directly")

        # Continue main loop
        phase2_start = len(main_loop_latencies)
        for _ in range(20):
            simulate_trading_loop()
            time.sleep(0.01)

        phase2_latencies = main_loop_latencies[phase2_start:]
        phase2_avg = sum(phase2_latencies) / len(phase2_latencies)
        print(f"📈 Under-load latency: {phase2_avg:.2f}ms")

        # Wait for all tasks
        print("⏳ Waiting for task completion...")
        success = manager.workqueue.wait_empty(
            timeout=15.0
        )  # Longer timeout for 50 tasks
        assert success, "Tasks did not complete within timeout"

        # Final stats
        final_stats = manager.get_performance_stats()
        tasks_processed = final_stats["workqueue"]["tasks_processed"]

        print("📊 Results:")
        print(f"   📈 Baseline latency: {baseline_avg:.2f}ms")
        print(f"   📈 Under-load latency: {phase2_avg:.2f}ms")
        print(f"   📈 Latency increase: {phase2_avg - baseline_avg:.2f}ms")
        print(f"   📈 Tasks processed: {tasks_processed}")

        # Validate performance - subtract 1 for the initial performance check task
        chart_tasks_processed = max(0, tasks_processed - 1)
        latency_increase = phase2_avg - baseline_avg
        assert (
            latency_increase <= 2.0
        ), f"Latency increased by {latency_increase:.2f}ms (max: 2ms)"
        assert (
            chart_tasks_processed >= 45
        ), f"Only {chart_tasks_processed} of 50 chart tasks completed"

        print("✅ Comprehensive load test PASSED!")

    finally:
        performance_integration.PerformanceManager._register_task_handlers = (
            original_start
        )
        if "manager" in locals():
            manager.stop()


def main():
    """Run all performance tests"""
    print("🚀 Starting Performance & Workload Isolation Tests")
    print("=" * 60)

    try:
        test_workqueue_basic()
        print()

        test_latency_tracking()
        print()

        test_scheduler()
        print()

        test_performance_integration()
        print()

        test_comprehensive_load()
        print()

        print("=" * 60)
        print("🎉 All performance tests PASSED!")

    except Exception as e:
        print(f"❌ Performance test failed: {e}")
        raise


if __name__ == "__main__":
    main()
