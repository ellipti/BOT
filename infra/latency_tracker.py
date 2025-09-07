# infra/latency_tracker.py
"""
Latency tracking for trading loop performance monitoring.
Provides P95/P99 latency calculation using rolling window approach.
"""

import threading
import time
from collections import deque
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

from core.logger import get_logger
from observability.metrics import observe, set_gauge

logger = get_logger("latency_tracker")


class LatencyTracker:
    """
    Thread-safe latency tracker with percentile calculations.

    Uses a rolling window of recent measurements to calculate P95/P99 metrics.
    Optimized for high-frequency trading loop measurements.
    """

    def __init__(self, window_size: int = 1000, name: str = "latency"):
        self.name = name
        self.window_size = window_size
        self._measurements = deque(maxlen=window_size)
        self._lock = threading.Lock()
        self._total_measurements = 0
        self._sum_latency = 0.0

    def record(self, latency_ms: float, **labels) -> None:
        """
        Record a latency measurement.

        Args:
            latency_ms: Latency measurement in milliseconds
            **labels: Additional labels for metrics (e.g., operation="signal_detection")
        """
        with self._lock:
            self._measurements.append(latency_ms)
            self._total_measurements += 1
            self._sum_latency += latency_ms

        # Send to observability system
        observe(f"{self.name}_latency_ms", latency_ms, **labels)

        # Update rolling percentiles if we have enough measurements
        if len(self._measurements) >= 10:  # Need some data for percentiles
            self._update_percentile_metrics(**labels)

    def _update_percentile_metrics(self, **labels) -> None:
        """Update P95/P99 gauge metrics (called with lock held)"""
        try:
            # Convert to sorted list for percentile calculation
            sorted_measurements = sorted(self._measurements)

            # Calculate percentiles
            n = len(sorted_measurements)
            p95_idx = int(n * 0.95) - 1
            p99_idx = int(n * 0.99) - 1

            p95 = sorted_measurements[max(0, p95_idx)]
            p99 = sorted_measurements[max(0, p99_idx)]
            avg = sum(sorted_measurements) / n

            # Update gauge metrics
            set_gauge(f"{self.name}_latency_p95_ms", p95, **labels)
            set_gauge(f"{self.name}_latency_p99_ms", p99, **labels)
            set_gauge(f"{self.name}_latency_avg_ms", avg, **labels)

        except Exception as e:
            logger.debug(f"Failed to update percentile metrics: {e}")

    @contextmanager
    def measure(self, **labels):
        """
        Context manager for measuring execution time.

        Usage:
            with tracker.measure(operation="signal_detection"):
                # ... code to measure ...
                pass
        """
        start_time = time.time()
        try:
            yield
        finally:
            latency_ms = (time.time() - start_time) * 1000
            self.record(latency_ms, **labels)

    def get_stats(self) -> dict[str, Any]:
        """Get current latency statistics"""
        with self._lock:
            if not self._measurements:
                return {
                    "name": self.name,
                    "count": 0,
                    "avg_ms": 0.0,
                    "p95_ms": 0.0,
                    "p99_ms": 0.0,
                    "min_ms": 0.0,
                    "max_ms": 0.0,
                }

            sorted_measurements = sorted(self._measurements)
            n = len(sorted_measurements)

            # Calculate percentiles
            p95_idx = int(n * 0.95) - 1
            p99_idx = int(n * 0.99) - 1

            return {
                "name": self.name,
                "count": len(self._measurements),
                "total_count": self._total_measurements,
                "avg_ms": (
                    self._sum_latency / self._total_measurements
                    if self._total_measurements > 0
                    else 0.0
                ),
                "rolling_avg_ms": sum(sorted_measurements) / n,
                "p95_ms": sorted_measurements[max(0, p95_idx)],
                "p99_ms": sorted_measurements[max(0, p99_idx)],
                "min_ms": sorted_measurements[0],
                "max_ms": sorted_measurements[-1],
                "window_size": self.window_size,
            }

    def reset(self) -> None:
        """Reset all measurements and statistics"""
        with self._lock:
            self._measurements.clear()
            self._total_measurements = 0
            self._sum_latency = 0.0

        logger.info(f"Reset latency tracker '{self.name}'")


class TradingLoopLatencyTracker:
    """
    Specialized latency tracker for the main trading loop.

    Tracks different phases of the trading loop separately:
    - Data fetching
    - Signal detection
    - Decision making
    - Order placement
    - Overall loop iteration
    """

    def __init__(self, window_size: int = 1000):
        self.trackers = {
            "overall": LatencyTracker(window_size, "trade_loop_overall"),
            "data_fetch": LatencyTracker(window_size, "trade_loop_data_fetch"),
            "signal_detection": LatencyTracker(window_size, "trade_loop_signal"),
            "decision_making": LatencyTracker(window_size, "trade_loop_decision"),
            "order_placement": LatencyTracker(window_size, "trade_loop_order"),
        }
        self._loop_count = 0
        self._lock = threading.Lock()

    def measure_overall(self):
        """Context manager for measuring overall loop iteration"""
        return self.trackers["overall"].measure()

    def measure_data_fetch(self):
        """Context manager for measuring data fetching phase"""
        return self.trackers["data_fetch"].measure()

    def measure_signal_detection(self):
        """Context manager for measuring signal detection phase"""
        return self.trackers["signal_detection"].measure()

    def measure_decision_making(self):
        """Context manager for measuring decision making phase"""
        return self.trackers["decision_making"].measure()

    def measure_order_placement(self):
        """Context manager for measuring order placement phase"""
        return self.trackers["order_placement"].measure()

    def increment_loop_count(self):
        """Increment the total loop iteration count"""
        with self._lock:
            self._loop_count += 1
        set_gauge("trade_loop_iterations_total", self._loop_count)

    def get_all_stats(self) -> dict[str, Any]:
        """Get statistics for all tracked phases"""
        stats = {}

        for phase, tracker in self.trackers.items():
            stats[phase] = tracker.get_stats()

        with self._lock:
            stats["loop_count"] = self._loop_count

        return stats

    def reset_all(self):
        """Reset all trackers and loop count"""
        for tracker in self.trackers.values():
            tracker.reset()

        with self._lock:
            self._loop_count = 0

        logger.info("Reset all trading loop latency trackers")


# Global instance for trading loop latency tracking
_trading_loop_tracker = TradingLoopLatencyTracker()


def get_trading_loop_tracker() -> TradingLoopLatencyTracker:
    """Get the global trading loop latency tracker"""
    return _trading_loop_tracker


def measure_trading_loop():
    """Context manager for measuring overall trading loop latency"""
    return _trading_loop_tracker.measure_overall()


def measure_data_fetch():
    """Context manager for measuring data fetch latency"""
    return _trading_loop_tracker.measure_data_fetch()


def measure_signal_detection():
    """Context manager for measuring signal detection latency"""
    return _trading_loop_tracker.measure_signal_detection()


def measure_decision_making():
    """Context manager for measuring decision making latency"""
    return _trading_loop_tracker.measure_decision_making()


def measure_order_placement():
    """Context manager for measuring order placement latency"""
    return _trading_loop_tracker.measure_order_placement()


def increment_loop_count():
    """Increment trading loop iteration counter"""
    _trading_loop_tracker.increment_loop_count()
