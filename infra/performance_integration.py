# infra/performance_integration.py
"""
Performance & Workload Isolation integration layer.
Connects EventBus with WorkQueue and AsyncScheduler for isolated heavy task processing.
"""

import os
import time
from datetime import UTC, datetime, timezone
from typing import Any, Dict, Optional

from config.settings import get_settings
from core.events.bus import EventBus
from core.events.types import ChartRequested
from core.logger import get_logger
from infra.latency_tracker import get_trading_loop_tracker
from infra.scheduler import AsyncScheduler
from infra.workqueue import WorkQueue
from observability.metrics import inc, observe, set_gauge
from services.chart_tasks import generate_report, render_chart

logger = get_logger("performance_integration")


class PerformanceManager:
    """
    Manages WorkQueue, Scheduler, and latency tracking for isolated task processing.

    Provides centralized management of all performance-related components to ensure
    heavy operations don't block the main trading loop.
    """

    def __init__(self, event_bus: EventBus | None = None):
        self.settings = get_settings()
        self.event_bus = event_bus
        self.workqueue = WorkQueue()
        self.scheduler = AsyncScheduler(workqueue=self.workqueue)
        self.latency_tracker = get_trading_loop_tracker()

        self._running = False
        self._registered_handlers = False

        # Performance monitoring
        self._last_performance_check = time.time()
        self._performance_check_interval = 30.0  # seconds

        logger.info("PerformanceManager initialized")

    def start(self) -> None:
        """Start all performance components"""
        if self._running:
            logger.warning("PerformanceManager already running")
            return

        try:
            # Register task handlers with WorkQueue
            self._register_task_handlers()

            # Start WorkQueue with configured worker count
            worker_count = self.settings.workers
            self.workqueue.start(n_workers=worker_count)
            logger.info(f"Started WorkQueue with {worker_count} workers")

            # Start scheduler if enabled
            if self.settings.enable_scheduler:
                self.scheduler.start()
                self._schedule_periodic_tasks()
                logger.info("Started AsyncScheduler with periodic tasks")

            # Register EventBus handlers
            if self.event_bus:
                self._register_event_handlers()
                logger.info("Registered EventBus handlers")

            self._running = True
            set_gauge("performance_manager_running", 1)

            logger.info("PerformanceManager started successfully")

        except Exception as e:
            logger.error(f"Failed to start PerformanceManager: {e}")
            self.stop()  # Cleanup on failure
            raise

    def stop(self) -> None:
        """Stop all performance components"""
        if not self._running:
            return

        logger.info("Stopping PerformanceManager...")

        try:
            # Stop scheduler first
            if self.scheduler.is_running():
                self.scheduler.stop()
                logger.info("Stopped AsyncScheduler")

            # Stop WorkQueue
            if self.workqueue.is_running():
                success = self.workqueue.stop(timeout=5.0)
                if success:
                    logger.info("Stopped WorkQueue successfully")
                else:
                    logger.warning(
                        "WorkQueue stop timeout - some workers may still be running"
                    )

            self._running = False
            set_gauge("performance_manager_running", 0)

            logger.info("PerformanceManager stopped")

        except Exception as e:
            logger.error(f"Error stopping PerformanceManager: {e}")

    def _register_task_handlers(self) -> None:
        """Register task handlers with WorkQueue"""
        if self._registered_handlers:
            return

        # Chart rendering handler
        self.workqueue.register("chart_render", render_chart)
        logger.debug("Registered chart_render task handler")

        # Report generation handler
        self.workqueue.register("generate_report", generate_report)
        logger.debug("Registered generate_report task handler")

        # Performance check handler (internal)
        self.workqueue.register("performance_check", self._handle_performance_check)
        logger.debug("Registered performance_check task handler")

        self._registered_handlers = True

    def _register_event_handlers(self) -> None:
        """Register EventBus event handlers"""
        if not self.event_bus:
            return

        # Handle ChartRequested events
        self.event_bus.subscribe(ChartRequested, self._handle_chart_requested)
        logger.debug("Subscribed to ChartRequested events")

    def _handle_chart_requested(self, event: ChartRequested) -> None:
        """Handle ChartRequested event by submitting to WorkQueue"""
        try:
            # Convert event to task payload
            payload = {
                "symbol": event.symbol,
                "timeframe": event.timeframe,
                "out_path": event.out_path,
                "title": event.title,
                "bars_count": event.bars_count,
                "overlays": event.overlays,
                "send_telegram": event.send_telegram,
                "telegram_caption": event.telegram_caption,
            }

            # Submit to WorkQueue for async processing
            self.workqueue.submit("chart_render", payload)

            inc(
                "chart_requests_submitted_total",
                symbol=event.symbol,
                timeframe=event.timeframe,
            )

            logger.debug(
                f"Submitted ChartRequested to WorkQueue: {event.symbol} {event.timeframe}"
            )

        except Exception as e:
            logger.error(f"Failed to handle ChartRequested event: {e}")
            inc("chart_requests_failed_total", reason="submission_error")

    def _schedule_periodic_tasks(self) -> None:
        """Schedule periodic maintenance and monitoring tasks"""
        if not self.settings.enable_scheduler:
            return

        # Schedule performance monitoring every 30 seconds
        self.scheduler.schedule_interval(
            task_name="performance_check",
            task_payload={"check_type": "periodic"},
            interval_seconds=self._performance_check_interval,
            job_id="performance_monitoring",
        )
        logger.debug("Scheduled periodic performance monitoring")

        # Schedule daily cleanup at 02:00 (requires APScheduler)
        try:
            self.scheduler.schedule_cron(
                task_name="generate_report",
                task_payload={
                    "report_type": "daily",
                    "output_path": f"reports/daily_{datetime.now(UTC).strftime('%Y%m%d')}.txt",
                    "send_telegram": True,
                    "telegram_caption": "📊 Daily Performance Report",
                },
                cron_expression="0 2 * * *",  # 2 AM daily
                job_id="daily_report",
            )
            logger.debug("Scheduled daily report generation")
        except RuntimeError as e:
            logger.warning(f"Could not schedule cron tasks: {e}")

    def _handle_performance_check(self, payload: dict[str, Any]) -> None:
        """Handle periodic performance monitoring task"""
        try:
            check_type = payload.get("check_type", "unknown")
            logger.debug(f"Running performance check: {check_type}")

            # Get current performance stats
            latency_stats = self.latency_tracker.get_all_stats()
            workqueue_stats = self.workqueue.get_stats()
            scheduler_stats = self.scheduler.get_stats()

            # Check if trading loop latency is above threshold
            overall_stats = latency_stats.get("overall", {})
            current_p95 = overall_stats.get("p95_ms", 0.0)

            if current_p95 > self.settings.latency_threshold_ms:
                logger.warning(
                    f"Trading loop P95 latency ({current_p95:.1f}ms) exceeds threshold ({self.settings.latency_threshold_ms}ms)"
                )
                inc("performance_threshold_violations_total", metric="latency_p95")

                # Send alert if Telegram is enabled
                if self.settings.telegram.enabled:
                    try:
                        from services.telegram_notify import send_error_alert

                        send_error_alert(
                            f"🐌 High latency detected: P95={current_p95:.1f}ms (threshold: {self.settings.latency_threshold_ms}ms)",
                            "Performance Monitor",
                        )
                    except Exception as e:
                        logger.error(f"Failed to send latency alert: {e}")

            # Update performance metrics
            set_gauge("workqueue_pending_tasks", workqueue_stats.get("queue_size", 0))
            set_gauge(
                "workqueue_workers_running", workqueue_stats.get("workers_running", 0)
            )
            set_gauge("scheduler_jobs_active", len(scheduler_stats.get("jobs", {})))

            # Log summary
            logger.debug(
                f"Performance check completed - P95: {current_p95:.1f}ms, Queue: {workqueue_stats.get('queue_size', 0)}, Workers: {workqueue_stats.get('workers_running', 0)}"
            )

            inc("performance_checks_completed_total", check_type=check_type)

        except Exception as e:
            logger.error(f"Performance check failed: {e}")
            inc("performance_checks_failed_total", error=str(type(e).__name__))

    def submit_chart_request(
        self,
        symbol: str,
        timeframe: str = "M30",
        out_path: str | None = None,
        **kwargs,
    ) -> None:
        """
        Convenience method to submit chart rendering request directly.

        Args:
            symbol: Trading symbol
            timeframe: Chart timeframe
            out_path: Output file path (auto-generated if None)
            **kwargs: Additional chart parameters
        """
        if not out_path:
            timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            out_path = f"charts/{symbol}_{timeframe}_{timestamp}.png"

        # Create ChartRequested event
        event = ChartRequested(
            client_order_id=kwargs.get("client_order_id", f"chart_{int(time.time())}"),
            symbol=symbol,
            timeframe=timeframe,
            out_path=out_path,
            title=kwargs.get("title"),
            bars_count=kwargs.get("bars_count", 200),
            overlays=kwargs.get("overlays", {}),
            send_telegram=kwargs.get("send_telegram", False),
            telegram_caption=kwargs.get("telegram_caption"),
        )

        # Handle via event system
        if self.event_bus:
            self.event_bus.publish(event)
            logger.debug(f"Published ChartRequested event: {symbol} {timeframe}")
        else:
            # Direct submission if no event bus
            self._handle_chart_requested(event)
            logger.debug(f"Directly submitted chart request: {symbol} {timeframe}")

    def submit_report_request(
        self, report_type: str, output_path: str, **kwargs
    ) -> None:
        """
        Convenience method to submit report generation request.

        Args:
            report_type: Type of report to generate
            output_path: Where to save the report
            **kwargs: Additional report parameters
        """
        payload = {
            "report_type": report_type,
            "output_path": output_path,
            "symbol": kwargs.get("symbol"),
            "date": kwargs.get("date"),
            "send_telegram": kwargs.get("send_telegram", False),
            "telegram_caption": kwargs.get("telegram_caption"),
        }

        self.workqueue.submit("generate_report", payload)
        logger.debug(f"Submitted report request: {report_type} -> {output_path}")

    def get_performance_stats(self) -> dict[str, Any]:
        """Get comprehensive performance statistics"""
        return {
            "running": self._running,
            "settings": {
                "workers": self.settings.workers,
                "enable_async_charts": self.settings.enable_async_charts,
                "enable_async_reports": self.settings.enable_async_reports,
                "enable_scheduler": self.settings.enable_scheduler,
                "latency_threshold_ms": self.settings.latency_threshold_ms,
            },
            "latency": self.latency_tracker.get_all_stats(),
            "workqueue": self.workqueue.get_stats(),
            "scheduler": self.scheduler.get_stats(),
        }

    def is_healthy(self) -> bool:
        """Check if all performance components are healthy"""
        if not self._running:
            return False

        # Check if WorkQueue is running with workers
        workqueue_stats = self.workqueue.get_stats()
        if not workqueue_stats.get("is_running", False):
            return False

        if workqueue_stats.get("workers_running", 0) == 0:
            return False

        # Check if scheduler is running (if enabled)
        if self.settings.enable_scheduler:
            if not self.scheduler.is_running():
                return False

        return True

    def __enter__(self):
        """Context manager entry"""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.stop()


# Global performance manager instance
_performance_manager: PerformanceManager | None = None


def get_performance_manager(event_bus: EventBus | None = None) -> PerformanceManager:
    """Get or create global performance manager instance"""
    global _performance_manager

    if _performance_manager is None:
        _performance_manager = PerformanceManager(event_bus=event_bus)

    return _performance_manager


def setup_performance_integration(event_bus: EventBus) -> PerformanceManager:
    """Setup and start performance integration with event bus"""
    manager = get_performance_manager(event_bus=event_bus)

    if not manager.is_healthy():
        manager.start()

    return manager
