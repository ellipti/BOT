# test_performance_workload.py
"""
Comprehensive test for Performance & Workload Isolation system.
Tests WorkQueue, Scheduler, LatencyTracker, and EventBus integration.
Validates that trading loop latency remains stable under chart rendering load.
"""

import threading
import time
from datetime import UTC, datetime, timezone
from pathlib import Path
from typing import List

import pytest

from config.settings import get_settings
from core.events.bus import EventBus
from core.events.types import ChartRequested
from core.logger import get_logger
from infra.latency_tracker import LatencyTracker, TradingLoopLatencyTracker
from infra.performance_integration import PerformanceManager
from infra.scheduler import AsyncScheduler
from infra.workqueue import WorkQueue
from observability.metrics import get_metrics
from services.chart_tasks import generate_report, render_chart

logger = get_logger("test_performance")


class TestWorkQueue:
    """Test WorkQueue functionality"""

    def test_basic_task_processing(self):
        """Test basic task submission and processing"""
        results = []

        def test_handler(payload):
            results.append(payload["value"])

        workqueue = WorkQueue()
        workqueue.register("test_task", test_handler)
        workqueue.start(n_workers=2)

        try:
            # Submit tasks
            for i in range(5):
                workqueue.submit("test_task", {"value": i})

            # Wait for processing
            workqueue.wait_empty(timeout=5.0)

            # Verify results
            assert len(results) == 5
            assert set(results) == {0, 1, 2, 3, 4}

            # Check stats
            stats = workqueue.get_stats()
            assert stats["tasks_processed"] == 5
            assert stats["tasks_failed"] == 0
            assert stats["workers_running"] == 2

        finally:
            workqueue.stop()

    def test_error_handling(self):
        """Test task error handling doesn't stop processing"""
        results = []

        def error_handler(payload):
            if payload["should_error"]:
                raise ValueError("Test error")
            results.append(payload["value"])

        workqueue = WorkQueue()
        workqueue.register("error_task", error_handler)
        workqueue.start(n_workers=1)

        try:
            # Submit mix of success and error tasks
            workqueue.submit("error_task", {"should_error": True, "value": "error1"})
            workqueue.submit("error_task", {"should_error": False, "value": "success1"})
            workqueue.submit("error_task", {"should_error": True, "value": "error2"})
            workqueue.submit("error_task", {"should_error": False, "value": "success2"})

            # Wait for processing
            workqueue.wait_empty(timeout=5.0)

            # Verify only successful tasks completed
            assert results == ["success1", "success2"]

            # Check stats show both success and failures
            stats = workqueue.get_stats()
            assert stats["tasks_processed"] == 2
            assert stats["tasks_failed"] == 2

        finally:
            workqueue.stop()

    def test_concurrent_access(self):
        """Test thread-safe concurrent task submission"""
        results = []
        result_lock = threading.Lock()

        def concurrent_handler(payload):
            with result_lock:
                results.append(payload["worker_id"])

        workqueue = WorkQueue()
        workqueue.register("concurrent_task", concurrent_handler)
        workqueue.start(n_workers=3)

        try:
            # Submit tasks from multiple threads
            threads = []
            for worker_id in range(5):

                def submit_tasks(w_id):
                    for i in range(10):
                        workqueue.submit("concurrent_task", {"worker_id": w_id})

                thread = threading.Thread(target=submit_tasks, args=(worker_id,))
                threads.append(thread)
                thread.start()

            # Wait for all submissions
            for thread in threads:
                thread.join()

            # Wait for processing
            workqueue.wait_empty(timeout=10.0)

            # Verify all tasks completed
            assert len(results) == 50  # 5 workers * 10 tasks each

            # Check each worker submitted 10 tasks
            for worker_id in range(5):
                assert results.count(worker_id) == 10

        finally:
            workqueue.stop()


class TestLatencyTracker:
    """Test latency tracking and percentile calculations"""

    def test_basic_tracking(self):
        """Test basic latency measurement and statistics"""
        tracker = LatencyTracker(window_size=100, name="test")

        # Record some measurements
        latencies = [10.0, 20.0, 30.0, 40.0, 50.0, 100.0, 200.0]
        for latency in latencies:
            tracker.record(latency)

        # Get stats
        stats = tracker.get_stats()

        assert stats["count"] == 7
        assert stats["min_ms"] == 10.0
        assert stats["max_ms"] == 200.0
        assert stats["p95_ms"] >= 100.0  # Should be high due to 200ms outlier
        assert 0 < stats["avg_ms"] < 100

    def test_context_manager(self):
        """Test context manager for automatic measurement"""
        tracker = LatencyTracker(window_size=100, name="test_context")

        # Measure some work
        with tracker.measure(operation="test_work"):
            time.sleep(0.01)  # 10ms

        stats = tracker.get_stats()
        assert stats["count"] == 1
        assert 8.0 <= stats["avg_ms"] <= 15.0  # Should be around 10ms

    def test_trading_loop_tracker(self):
        """Test specialized trading loop tracker"""
        tracker = TradingLoopLatencyTracker(window_size=50)

        # Simulate trading loop phases
        with tracker.measure_overall():
            with tracker.measure_data_fetch():
                time.sleep(0.002)  # 2ms

            with tracker.measure_signal_detection():
                time.sleep(0.003)  # 3ms

            with tracker.measure_decision_making():
                time.sleep(0.001)  # 1ms

            with tracker.measure_order_placement():
                time.sleep(0.004)  # 4ms

        tracker.increment_loop_count()

        # Get comprehensive stats
        all_stats = tracker.get_all_stats()

        assert "overall" in all_stats
        assert "data_fetch" in all_stats
        assert "signal_detection" in all_stats
        assert "decision_making" in all_stats
        assert "order_placement" in all_stats
        assert all_stats["loop_count"] == 1

        # Verify timing relationships
        overall_time = all_stats["overall"]["avg_ms"]
        component_sum = (
            all_stats["data_fetch"]["avg_ms"]
            + all_stats["signal_detection"]["avg_ms"]
            + all_stats["decision_making"]["avg_ms"]
            + all_stats["order_placement"]["avg_ms"]
        )

        # Overall should be >= sum of components (some overhead expected)
        assert overall_time >= component_sum * 0.8  # Allow some variance


class TestScheduler:
    """Test AsyncScheduler functionality"""

    def test_interval_scheduling(self):
        """Test interval-based task scheduling"""
        execution_count = [0]  # Use list for mutable closure

        def count_handler(payload):
            execution_count[0] += 1

        workqueue = WorkQueue()
        workqueue.register("count_task", count_handler)
        workqueue.start(n_workers=1)

        scheduler = AsyncScheduler(workqueue=workqueue)

        try:
            # Schedule task every 0.1 seconds
            job_id = scheduler.schedule_interval(
                task_name="count_task",
                task_payload={"test": True},
                interval_seconds=0.1,
            )

            scheduler.start()

            # Let it run for ~0.5 seconds
            time.sleep(0.55)

            # Wait for queue to empty
            workqueue.wait_empty(timeout=2.0)

            # Should have executed ~5 times
            assert 3 <= execution_count[0] <= 7  # Allow for timing variance

            # Verify job is listed
            jobs = scheduler.list_jobs()
            assert len(jobs) >= 1
            assert any(job["id"] == job_id for job in jobs)

        finally:
            scheduler.stop()
            workqueue.stop()

    def test_job_management(self):
        """Test job creation, listing, and removal"""
        workqueue = WorkQueue()
        workqueue.register("dummy_task", lambda p: None)
        workqueue.start(n_workers=1)

        scheduler = AsyncScheduler(workqueue=workqueue)

        try:
            # Create multiple jobs
            job1 = scheduler.schedule_interval("dummy_task", {}, 1.0, "job1")
            job2 = scheduler.schedule_interval("dummy_task", {}, 2.0, "job2")

            scheduler.start()

            # List jobs
            jobs = scheduler.list_jobs()
            job_ids = [job["id"] for job in jobs]
            assert "job1" in job_ids
            assert "job2" in job_ids

            # Remove one job
            removed = scheduler.remove_job("job1")
            assert removed  # Should succeed for APScheduler

            # Verify it's gone
            jobs_after = scheduler.list_jobs()
            remaining_ids = [job["id"] for job in jobs_after]
            assert "job1" not in remaining_ids or not removed  # Only if removal worked
            assert "job2" in remaining_ids

        finally:
            scheduler.stop()
            workqueue.stop()


class TestChartTasks:
    """Test chart rendering task handlers"""

    def test_chart_render_validation(self):
        """Test chart rendering with invalid inputs"""
        # Missing required parameters
        with pytest.raises(ValueError, match="Missing required parameters"):
            render_chart({})

        with pytest.raises(ValueError, match="Missing required parameters"):
            render_chart({"symbol": "XAUUSD"})  # Missing out_path

    def test_report_generation(self):
        """Test basic report generation"""
        output_path = "test_reports/test_report.txt"
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        try:
            payload = {
                "report_type": "daily",
                "output_path": output_path,
                "send_telegram": False,
            }

            generate_report(payload)

            # Verify report was created
            assert Path(output_path).exists()

            # Check content
            with open(output_path) as f:
                content = f.read()

            assert "Daily Trading Report" in content
            assert datetime.now(UTC).strftime("%Y-%m-%d") in content

        finally:
            # Cleanup
            if Path(output_path).exists():
                Path(output_path).unlink()


class TestPerformanceIntegration:
    """Test complete performance system integration"""

    def test_manager_lifecycle(self):
        """Test PerformanceManager start/stop lifecycle"""
        event_bus = EventBus()
        manager = PerformanceManager(event_bus=event_bus)

        # Initially not running
        assert not manager.is_healthy()

        # Start manager
        manager.start()
        assert manager.is_healthy()

        # Check components are running
        stats = manager.get_performance_stats()
        assert stats["running"] is True
        assert stats["workqueue"]["is_running"] is True

        # Stop manager
        manager.stop()
        assert not manager.is_healthy()

    def test_chart_event_integration(self):
        """Test ChartRequested event handling via EventBus"""
        event_bus = EventBus()
        manager = PerformanceManager(event_bus=event_bus)

        # Create mock chart directory
        chart_dir = Path("test_charts")
        chart_dir.mkdir(exist_ok=True)

        try:
            manager.start()

            # Submit chart request via EventBus
            event = ChartRequested(
                client_order_id="test_chart_001",
                symbol="XAUUSD",
                timeframe="M30",
                out_path="test_charts/test_chart.png",
                bars_count=10,  # Small for testing
                send_telegram=False,
            )

            event_bus.publish(event)

            # Wait for processing
            time.sleep(2.0)
            manager.workqueue.wait_empty(timeout=5.0)

            # Check metrics were recorded
            metrics = get_metrics()
            all_metrics = metrics.get_all_metrics()

            # Should have chart request metrics
            counters = all_metrics.get("counters", {})
            assert "chart_requests_submitted_total" in counters

        finally:
            manager.stop()
            # Cleanup
            import shutil

            if chart_dir.exists():
                shutil.rmtree(chart_dir)

    def test_latency_threshold_monitoring(self):
        """Test latency threshold violation detection"""
        event_bus = EventBus()

        # Set very low threshold for testing
        settings = get_settings()
        original_threshold = settings.latency_threshold_ms
        settings.latency_threshold_ms = 1.0  # 1ms threshold

        try:
            manager = PerformanceManager(event_bus=event_bus)
            manager.start()

            # Record high latency measurements
            tracker = manager.latency_tracker
            for _ in range(10):
                tracker.trackers["overall"].record(
                    50.0
                )  # 50ms - way above 1ms threshold

            # Trigger performance check
            manager.workqueue.submit("performance_check", {"check_type": "test"})
            manager.workqueue.wait_empty(timeout=5.0)

            # Check that violation was recorded in metrics
            metrics = get_metrics()
            all_metrics = metrics.get_all_metrics()
            counters = all_metrics.get("counters", {})

            # Should have violation recorded
            violations = counters.get("performance_threshold_violations_total", {})
            assert len(violations) > 0  # Some violation should be recorded

        finally:
            settings.latency_threshold_ms = original_threshold
            if "manager" in locals():
                manager.stop()


def test_comprehensive_performance_scenario():
    """
    Comprehensive test simulating realistic trading loop with chart generation load.
    Validates that main loop latency remains stable under heavy chart rendering.
    """
    logger.info("🚀 Starting comprehensive performance test")

    event_bus = EventBus()
    manager = PerformanceManager(event_bus=event_bus)

    # Track main "trading loop" latency
    main_loop_latencies = []

    def simulate_trading_loop():
        """Simulate main trading loop work"""
        with manager.latency_tracker.measure_overall():
            # Simulate data fetching
            with manager.latency_tracker.measure_data_fetch():
                time.sleep(0.001)  # 1ms

            # Simulate signal detection
            with manager.latency_tracker.measure_signal_detection():
                time.sleep(0.002)  # 2ms

            # Simulate decision making
            with manager.latency_tracker.measure_decision_making():
                time.sleep(0.001)  # 1ms

        # Track the total latency for this iteration
        stats = manager.latency_tracker.get_all_stats()
        if stats["overall"]["count"] > 0:
            main_loop_latencies.append(stats["overall"]["rolling_avg_ms"])

        manager.latency_tracker.increment_loop_count()

    try:
        # Start performance system
        manager.start()
        logger.info("✅ Performance system started")

        # Phase 1: Baseline - measure latency without load
        logger.info("📊 Phase 1: Baseline measurement (10 iterations)")
        for _ in range(10):
            simulate_trading_loop()
            time.sleep(0.01)  # 10ms between loops

        baseline_avg = sum(main_loop_latencies) / len(main_loop_latencies)
        logger.info(f"📈 Baseline average latency: {baseline_avg:.2f}ms")

        # Phase 2: Load test - submit many chart requests while measuring loop latency
        logger.info("📊 Phase 2: Load test with 100 chart requests")

        # Submit 100 chart requests rapidly
        for i in range(100):
            event = ChartRequested(
                client_order_id=f"load_test_{i:03d}",
                symbol="XAUUSD",
                timeframe="M1",
                out_path=f"test_charts/load_test_{i:03d}.png",
                bars_count=50,  # Small charts for speed
                send_telegram=False,
            )
            event_bus.publish(event)

        logger.info("📤 100 chart requests submitted to WorkQueue")

        # Continue measuring main loop while charts are processing
        phase2_start_idx = len(main_loop_latencies)
        for _ in range(20):  # 20 more trading loop iterations
            simulate_trading_loop()
            time.sleep(0.01)  # 10ms between loops

        phase2_latencies = main_loop_latencies[phase2_start_idx:]
        phase2_avg = sum(phase2_latencies) / len(phase2_latencies)
        logger.info(f"📈 Under-load average latency: {phase2_avg:.2f}ms")

        # Wait for all chart tasks to complete
        logger.info("⏳ Waiting for all chart tasks to complete...")
        success = manager.workqueue.wait_empty(timeout=30.0)
        assert success, "Chart tasks did not complete within timeout"

        # Phase 3: Final measurement after load
        logger.info("📊 Phase 3: Post-load measurement (10 iterations)")
        phase3_start_idx = len(main_loop_latencies)
        for _ in range(10):
            simulate_trading_loop()
            time.sleep(0.01)

        phase3_latencies = main_loop_latencies[phase3_start_idx:]
        phase3_avg = sum(phase3_latencies) / len(phase3_latencies)
        logger.info(f"📈 Post-load average latency: {phase3_avg:.2f}ms")

        # Performance validation
        logger.info("🔍 Analyzing performance impact...")

        # Main loop latency should not increase significantly under chart load
        latency_increase = phase2_avg - baseline_avg
        max_acceptable_increase = 5.0  # 5ms max increase

        logger.info(f"📊 Latency increase under load: {latency_increase:.2f}ms")

        assert latency_increase <= max_acceptable_increase, (
            f"Trading loop latency increased by {latency_increase:.2f}ms under load "
            f"(max acceptable: {max_acceptable_increase}ms)"
        )

        # Verify charts were processed
        final_stats = manager.get_performance_stats()
        workqueue_stats = final_stats["workqueue"]

        logger.info(
            f"📈 Total tasks processed: {workqueue_stats.get('tasks_processed', 0)}"
        )
        logger.info(f"📈 Total tasks failed: {workqueue_stats.get('tasks_failed', 0)}")

        # At least 90 of 100 chart tasks should have been processed successfully
        # (allowing for some test environment issues)
        tasks_processed = workqueue_stats.get("tasks_processed", 0)
        assert (
            tasks_processed >= 90
        ), f"Only {tasks_processed} of 100 chart tasks completed"

        # Overall P95 latency should be reasonable
        overall_p95 = final_stats["latency"]["overall"]["p95_ms"]
        max_p95_threshold = 20.0  # 20ms max P95

        logger.info(f"📈 Final P95 latency: {overall_p95:.2f}ms")

        assert (
            overall_p95 <= max_p95_threshold
        ), f"P95 latency ({overall_p95:.2f}ms) exceeds threshold ({max_p95_threshold}ms)"

        logger.info("✅ Comprehensive performance test PASSED!")
        logger.info(f"   📊 Baseline latency: {baseline_avg:.2f}ms")
        logger.info(f"   📊 Under-load latency: {phase2_avg:.2f}ms")
        logger.info(f"   📊 Post-load latency: {phase3_avg:.2f}ms")
        logger.info(f"   📊 P95 latency: {overall_p95:.2f}ms")
        logger.info(f"   📊 Tasks processed: {tasks_processed}/100")

    finally:
        manager.stop()
        logger.info("🛑 Performance system stopped")


if __name__ == "__main__":
    # Run comprehensive test directly
    test_comprehensive_performance_scenario()
