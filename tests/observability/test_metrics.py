"""
Tests for the metrics registry functionality.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import threading
import time
import unittest

from observability.metrics import MetricsRegistry, get_metrics, inc, observe, set_gauge


class TestMetrics(unittest.TestCase):
    """Test metrics registry functionality."""

    def setUp(self):
        """Set up test environment."""
        # Create a fresh registry for each test
        self.registry = MetricsRegistry()

    def test_counter_increment(self):
        """Test counter increments."""
        # Basic increment
        self.registry.inc("test_counter", 1.0)
        metrics = self.registry.get_all_metrics()
        self.assertEqual(metrics["counters"]["test_counter"]["__default__"], 1.0)

        # Increment with value
        self.registry.inc("test_counter", 2.5)
        metrics = self.registry.get_all_metrics()
        self.assertEqual(metrics["counters"]["test_counter"]["__default__"], 3.5)

    def test_counter_with_labels(self):
        """Test counters with labels."""
        self.registry.inc("requests", 1.0, method="GET", status="200")
        self.registry.inc("requests", 1.0, method="POST", status="201")
        self.registry.inc("requests", 2.0, method="GET", status="200")

        metrics = self.registry.get_all_metrics()
        counters = metrics["counters"]["requests"]

        self.assertEqual(counters["method=GET&status=200"], 3.0)
        self.assertEqual(counters["method=POST&status=201"], 1.0)

    def test_gauge_set(self):
        """Test gauge setting."""
        self.registry.set_gauge("temperature", 25.5)
        metrics = self.registry.get_all_metrics()
        self.assertEqual(metrics["gauges"]["temperature"]["__default__"], 25.5)

        # Update gauge
        self.registry.set_gauge("temperature", 30.0)
        metrics = self.registry.get_all_metrics()
        self.assertEqual(metrics["gauges"]["temperature"]["__default__"], 30.0)

    def test_gauge_with_labels(self):
        """Test gauges with labels."""
        self.registry.set_gauge("cpu_usage", 45.2, core="0")
        self.registry.set_gauge("cpu_usage", 52.8, core="1")

        metrics = self.registry.get_all_metrics()
        gauges = metrics["gauges"]["cpu_usage"]

        self.assertEqual(gauges["core=0"], 45.2)
        self.assertEqual(gauges["core=1"], 52.8)

    def test_histogram_observe(self):
        """Test histogram observations."""
        values = [1.0, 2.0, 3.0, 2.5, 1.5]
        for val in values:
            self.registry.observe("response_time", val)

        metrics = self.registry.get_all_metrics()
        histogram = metrics["histograms"]["response_time"]["__default__"]

        self.assertEqual(histogram["count"], 5)
        self.assertEqual(histogram["sum"], 10.0)
        self.assertEqual(len(histogram["values"]), 5)  # Recent values

    def test_histogram_with_labels(self):
        """Test histograms with labels."""
        self.registry.observe("latency", 100.0, endpoint="/api/v1")
        self.registry.observe("latency", 150.0, endpoint="/api/v1")
        self.registry.observe("latency", 200.0, endpoint="/api/v2")

        metrics = self.registry.get_all_metrics()
        histograms = metrics["histograms"]["latency"]

        self.assertEqual(histograms["endpoint=/api/v1"]["count"], 2)
        self.assertEqual(histograms["endpoint=/api/v1"]["sum"], 250.0)
        self.assertEqual(histograms["endpoint=/api/v2"]["count"], 1)
        self.assertEqual(histograms["endpoint=/api/v2"]["sum"], 200.0)

    def test_thread_safety(self):
        """Test thread safety of metrics registry."""

        def increment_counter():
            for _ in range(100):
                self.registry.inc("thread_test", 1.0)

        # Create multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=increment_counter)
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # Check final count
        metrics = self.registry.get_all_metrics()
        self.assertEqual(metrics["counters"]["thread_test"]["__default__"], 500.0)

    def test_histogram_memory_limit(self):
        """Test histogram memory limit (max 1000 observations)."""
        # Add more than 1000 observations
        for i in range(1200):
            self.registry.observe("memory_test", float(i))

        metrics = self.registry.get_all_metrics()
        histogram = metrics["histograms"]["memory_test"]["__default__"]

        # Should only keep last 1000 observations
        self.assertEqual(len(histogram["values"]), 10)  # Only shows last 10 in summary
        # Count is limited to the size of the list, which is max 1000
        self.assertLessEqual(histogram["count"], 1000)

    def test_render_as_text(self):
        """Test text rendering of metrics."""
        self.registry.inc("test_counter", 5.0)
        self.registry.set_gauge("test_gauge", 42.0)
        self.registry.observe("test_histogram", 1.5)
        self.registry.observe("test_histogram", 2.5)

        text = self.registry.render_as_text()

        # Should contain all metric types
        self.assertIn("test_counter 5", text)
        self.assertIn("test_gauge 42", text)
        self.assertIn("test_histogram_count 2", text)
        self.assertIn("test_histogram_sum 4", text)
        self.assertIn("test_histogram_avg 2", text)

    def test_global_metrics_functions(self):
        """Test global metrics convenience functions."""
        # Test global functions
        inc("global_counter", 3.0, service="test")
        set_gauge("global_gauge", 100.0, type="memory")
        observe("global_histogram", 0.5, operation="read")

        # Get global registry
        global_metrics = get_metrics().get_all_metrics()

        self.assertEqual(
            global_metrics["counters"]["global_counter"]["service=test"], 3.0
        )
        self.assertEqual(global_metrics["gauges"]["global_gauge"]["type=memory"], 100.0)
        self.assertEqual(
            global_metrics["histograms"]["global_histogram"]["operation=read"]["count"],
            1,
        )


if __name__ == "__main__":
    unittest.main()
