"""
Thread-safe metrics registry with optional Prometheus integration.

Provides a simple metrics API with Counter, Gauge, and Histogram-like functionality.
Thread-safe using locks. Optional Prometheus exporter if ENABLE_PROMETHEUS=true.
"""

import os
import threading
import time
from collections import defaultdict
from typing import Any, Optional


class MetricsRegistry:
    """Thread-safe metrics registry with Counter, Gauge, and Histogram support."""

    def __init__(self):
        self._lock = threading.Lock()
        self._counters: dict[str, dict[str, float]] = defaultdict(
            lambda: defaultdict(float)
        )
        self._gauges: dict[str, dict[str, float]] = defaultdict(
            lambda: defaultdict(float)
        )
        self._histograms: dict[str, dict[str, list]] = defaultdict(
            lambda: defaultdict(list)
        )
        self._prometheus_enabled = (
            os.getenv("ENABLE_PROMETHEUS", "false").lower() == "true"
        )
        self._prometheus_registry = None

        if self._prometheus_enabled:
            self._init_prometheus()

    def _init_prometheus(self):
        """Initialize Prometheus client if enabled."""
        try:
            from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

            self._prometheus_registry = CollectorRegistry()
            self._prometheus_counters = {}
            self._prometheus_gauges = {}
            self._prometheus_histograms = {}
        except ImportError:
            self._prometheus_enabled = False
            print(
                "Warning: prometheus_client not available, falling back to simple metrics"
            )

    def _get_label_key(self, **labels) -> str:
        """Generate a key for label combinations."""
        if not labels:
            return "__default__"
        return "&".join(f"{k}={v}" for k, v in sorted(labels.items()))

    def inc(self, name: str, value: float = 1.0, **labels) -> None:
        """Increment a counter metric."""
        label_key = self._get_label_key(**labels)

        with self._lock:
            self._counters[name][label_key] += value

        if self._prometheus_enabled and self._prometheus_registry:
            self._prometheus_inc(name, value, **labels)

    def set_gauge(self, name: str, value: float, **labels) -> None:
        """Set a gauge metric value."""
        label_key = self._get_label_key(**labels)

        with self._lock:
            self._gauges[name][label_key] = value

        if self._prometheus_enabled and self._prometheus_registry:
            self._prometheus_set_gauge(name, value, **labels)

    def observe(self, name: str, value: float, **labels) -> None:
        """Observe a value for histogram-like metrics."""
        label_key = self._get_label_key(**labels)

        with self._lock:
            self._histograms[name][label_key].append(value)
            # Keep only last 1000 observations to prevent memory issues
            if len(self._histograms[name][label_key]) > 1000:
                self._histograms[name][label_key] = self._histograms[name][label_key][
                    -1000:
                ]

        if self._prometheus_enabled and self._prometheus_registry:
            self._prometheus_observe(name, value, **labels)

    def _prometheus_inc(self, name: str, value: float, **labels):
        """Handle Prometheus counter increment."""
        try:
            from prometheus_client import Counter

            if name not in self._prometheus_counters:
                label_names = list(labels.keys()) if labels else []
                self._prometheus_counters[name] = Counter(
                    name,
                    f"Counter metric: {name}",
                    labelnames=label_names,
                    registry=self._prometheus_registry,
                )

            if labels:
                self._prometheus_counters[name].labels(**labels).inc(value)
            else:
                self._prometheus_counters[name].inc(value)
        except Exception:
            pass  # Fail silently

    def _prometheus_set_gauge(self, name: str, value: float, **labels):
        """Handle Prometheus gauge setting."""
        try:
            from prometheus_client import Gauge

            if name not in self._prometheus_gauges:
                label_names = list(labels.keys()) if labels else []
                self._prometheus_gauges[name] = Gauge(
                    name,
                    f"Gauge metric: {name}",
                    labelnames=label_names,
                    registry=self._prometheus_registry,
                )

            if labels:
                self._prometheus_gauges[name].labels(**labels).set(value)
            else:
                self._prometheus_gauges[name].set(value)
        except Exception:
            pass  # Fail silently

    def _prometheus_observe(self, name: str, value: float, **labels):
        """Handle Prometheus histogram observation."""
        try:
            from prometheus_client import Histogram

            if name not in self._prometheus_histograms:
                label_names = list(labels.keys()) if labels else []
                self._prometheus_histograms[name] = Histogram(
                    name,
                    f"Histogram metric: {name}",
                    labelnames=label_names,
                    registry=self._prometheus_registry,
                )

            if labels:
                self._prometheus_histograms[name].labels(**labels).observe(value)
            else:
                self._prometheus_histograms[name].observe(value)
        except Exception:
            pass  # Fail silently

    def render_as_text(self) -> str:
        """Render metrics as Prometheus text format."""
        if self._prometheus_enabled and self._prometheus_registry:
            try:
                from prometheus_client import generate_latest

                return generate_latest(self._prometheus_registry).decode("utf-8")
            except Exception:
                pass  # Fall back to simple format

        # Simple text format fallback
        lines = []
        timestamp = int(time.time())

        with self._lock:
            # Counters
            for name, labels_dict in self._counters.items():
                for label_key, value in labels_dict.items():
                    if label_key == "__default__":
                        lines.append(f"{name} {value} {timestamp}")
                    else:
                        label_str = "{" + label_key.replace("&", ",") + "}"
                        lines.append(f"{name}{label_str} {value} {timestamp}")

            # Gauges
            for name, labels_dict in self._gauges.items():
                for label_key, value in labels_dict.items():
                    if label_key == "__default__":
                        lines.append(f"{name} {value} {timestamp}")
                    else:
                        label_str = "{" + label_key.replace("&", ",") + "}"
                        lines.append(f"{name}{label_str} {value} {timestamp}")

            # Histograms (simplified - just count, sum, avg)
            for name, labels_dict in self._histograms.items():
                for label_key, values in labels_dict.items():
                    if not values:
                        continue

                    count = len(values)
                    total = sum(values)
                    avg = total / count if count > 0 else 0

                    suffix = (
                        ""
                        if label_key == "__default__"
                        else "{" + label_key.replace("&", ",") + "}"
                    )
                    lines.append(f"{name}_count{suffix} {count} {timestamp}")
                    lines.append(f"{name}_sum{suffix} {total} {timestamp}")
                    lines.append(f"{name}_avg{suffix} {avg:.6f} {timestamp}")

        return "\n".join(lines) + "\n"

    def get_all_metrics(self) -> dict[str, Any]:
        """Get all metrics as a dict for debugging/inspection."""
        with self._lock:
            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {
                    k: {
                        lk: {"count": len(lv), "sum": sum(lv), "values": lv[-10:]}
                        for lk, lv in v.items()
                    }
                    for k, v in self._histograms.items()
                },
            }


# Global metrics registry instance
_registry = MetricsRegistry()


def get_metrics() -> MetricsRegistry:
    """Get the global metrics registry instance."""
    return _registry


def inc(name: str, value: float = 1.0, **labels) -> None:
    """Increment a counter metric."""
    _registry.inc(name, value, **labels)


def set_gauge(name: str, value: float, **labels) -> None:
    """Set a gauge metric value."""
    _registry.set_gauge(name, value, **labels)


def observe(name: str, value: float, **labels) -> None:
    """Observe a value for histogram-like metrics."""
    _registry.observe(name, value, **labels)


def render_as_text() -> str:
    """Render all metrics as text/plain format."""
    return _registry.render_as_text()
