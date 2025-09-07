# infra/scheduler.py
"""
Async scheduler integration for periodic tasks without blocking main trading thread.
Uses APScheduler to schedule tasks that are executed via WorkQueue for consistency.
"""

import threading
import time
from collections.abc import Callable
from contextlib import contextmanager
from datetime import UTC, datetime, timezone
from typing import Any, Optional

from core.logger import get_logger
from observability.metrics import inc, set_gauge

logger = get_logger("scheduler")

try:
    from apscheduler.job import Job
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger

    APSCHEDULER_AVAILABLE = True
except ImportError:
    BackgroundScheduler = None
    IntervalTrigger = None
    CronTrigger = None
    Job = None
    APSCHEDULER_AVAILABLE = False
    logger.warning(
        "APScheduler not available, falling back to simple timer-based scheduler"
    )


class SimpleTimer:
    """Simple timer-based task for fallback when APScheduler is not available"""

    def __init__(
        self, interval_seconds: float, task_func: Callable, task_args: tuple = ()
    ):
        self.interval_seconds = interval_seconds
        self.task_func = task_func
        self.task_args = task_args
        self.stop_event = threading.Event()
        self.thread = None
        self.last_run = None
        self.run_count = 0

    def start(self):
        """Start the timer thread"""
        if self.thread and self.thread.is_alive():
            logger.warning("Timer already running")
            return

        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        logger.debug(f"Started timer with {self.interval_seconds}s interval")

    def stop(self):
        """Stop the timer thread"""
        if self.stop_event:
            self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=1.0)

    def _run_loop(self):
        """Main timer loop"""
        while not self.stop_event.is_set():
            try:
                start_time = time.time()
                self.task_func(*self.task_args)
                self.last_run = datetime.now(UTC)
                self.run_count += 1

                # Calculate sleep time accounting for execution time
                execution_time = time.time() - start_time
                sleep_time = max(0, self.interval_seconds - execution_time)

                if sleep_time > 0:
                    self.stop_event.wait(sleep_time)

            except Exception as e:
                logger.error(f"Timer task failed: {e}")
                # Continue running even if task fails
                self.stop_event.wait(self.interval_seconds)


class AsyncScheduler:
    """
    Async task scheduler that integrates with WorkQueue.

    Schedules periodic tasks (reconciliation, reporting, etc.) to run in background
    workers without blocking the main trading thread.
    """

    def __init__(self, workqueue=None):
        self.workqueue = workqueue
        self._scheduler = None
        self._simple_timers: list[SimpleTimer] = []
        self._running = False
        self._lock = threading.Lock()
        self._job_stats = {}

        # Initialize scheduler backend
        if APSCHEDULER_AVAILABLE:
            self._scheduler = BackgroundScheduler()
            logger.info("Using APScheduler backend")
        else:
            logger.info("Using simple timer backend")

    def schedule_interval(
        self,
        task_name: str,
        task_payload: dict[str, Any],
        interval_seconds: float,
        job_id: str | None = None,
    ) -> str:
        """
        Schedule a task to run at regular intervals.

        Args:
            task_name: Name of registered WorkQueue task
            task_payload: Payload to send to the task handler
            interval_seconds: Interval between executions
            job_id: Optional custom job ID (auto-generated if None)

        Returns:
            Job ID for later reference
        """
        job_id = job_id or f"{task_name}_{int(time.time())}"

        if not self.workqueue:
            raise RuntimeError("WorkQueue not configured for scheduler")

        if APSCHEDULER_AVAILABLE and self._scheduler:
            # Use APScheduler
            self._scheduler.add_job(
                func=self._submit_task,
                args=(task_name, task_payload, job_id),
                trigger=IntervalTrigger(seconds=interval_seconds),
                id=job_id,
                max_instances=1,  # Prevent overlapping executions
                coalesce=True,  # Merge missed runs
            )
            logger.info(
                f"Scheduled task '{task_name}' every {interval_seconds}s (APScheduler)"
            )
        else:
            # Use simple timer
            timer = SimpleTimer(
                interval_seconds=interval_seconds,
                task_func=self._submit_task,
                task_args=(task_name, task_payload, job_id),
            )
            self._simple_timers.append(timer)
            if self._running:
                timer.start()
            logger.info(
                f"Scheduled task '{task_name}' every {interval_seconds}s (SimpleTimer)"
            )

        # Initialize job stats
        with self._lock:
            self._job_stats[job_id] = {
                "task_name": task_name,
                "submissions": 0,
                "last_submission": None,
                "interval_seconds": interval_seconds,
            }

        return job_id

    def schedule_cron(
        self,
        task_name: str,
        task_payload: dict[str, Any],
        cron_expression: str,
        job_id: str | None = None,
    ) -> str:
        """
        Schedule a task using cron expression (requires APScheduler).

        Args:
            task_name: Name of registered WorkQueue task
            task_payload: Payload to send to the task handler
            cron_expression: Cron expression (e.g., "0 9 * * MON-FRI")
            job_id: Optional custom job ID

        Returns:
            Job ID for later reference

        Raises:
            RuntimeError: If APScheduler is not available
        """
        if not APSCHEDULER_AVAILABLE:
            raise RuntimeError(
                "Cron scheduling requires APScheduler (pip install apscheduler)"
            )

        if not self.workqueue:
            raise RuntimeError("WorkQueue not configured for scheduler")

        job_id = job_id or f"{task_name}_cron_{int(time.time())}"

        # Parse cron expression (simplified - APScheduler handles the complexity)
        parts = cron_expression.split()
        if len(parts) != 5:
            raise ValueError(f"Invalid cron expression: {cron_expression}")

        minute, hour, day, month, day_of_week = parts

        self._scheduler.add_job(
            func=self._submit_task,
            args=(task_name, task_payload, job_id),
            trigger=CronTrigger(
                minute=minute, hour=hour, day=day, month=month, day_of_week=day_of_week
            ),
            id=job_id,
            max_instances=1,
            coalesce=True,
        )

        # Initialize job stats
        with self._lock:
            self._job_stats[job_id] = {
                "task_name": task_name,
                "submissions": 0,
                "last_submission": None,
                "cron_expression": cron_expression,
            }

        logger.info(f"Scheduled task '{task_name}' with cron '{cron_expression}'")
        return job_id

    def _submit_task(self, task_name: str, task_payload: dict[str, Any], job_id: str):
        """Internal method to submit task to WorkQueue"""
        try:
            if self.workqueue:
                self.workqueue.submit(task_name, task_payload)

                # Update stats
                with self._lock:
                    if job_id in self._job_stats:
                        self._job_stats[job_id]["submissions"] += 1
                        self._job_stats[job_id]["last_submission"] = datetime.now(UTC)

                inc(
                    "scheduled_tasks_submitted_total",
                    task_name=task_name,
                    job_id=job_id,
                )
                logger.debug(
                    f"Submitted scheduled task '{task_name}' (job_id: {job_id})"
                )
            else:
                logger.error(f"WorkQueue not available for task '{task_name}'")
                inc(
                    "scheduled_tasks_failed_total",
                    task_name=task_name,
                    reason="no_workqueue",
                )

        except Exception as e:
            logger.error(f"Failed to submit scheduled task '{task_name}': {e}")
            inc(
                "scheduled_tasks_failed_total",
                task_name=task_name,
                reason="submission_error",
            )

    def start(self):
        """Start the scheduler"""
        with self._lock:
            if self._running:
                logger.warning("Scheduler already running")
                return

            if APSCHEDULER_AVAILABLE and self._scheduler:
                self._scheduler.start()
                logger.info("Started APScheduler")

            # Start simple timers
            for timer in self._simple_timers:
                timer.start()

            self._running = True
            set_gauge("scheduler_running", 1)
            logger.info("AsyncScheduler started")

    def stop(self):
        """Stop the scheduler"""
        with self._lock:
            if not self._running:
                return

            if APSCHEDULER_AVAILABLE and self._scheduler:
                self._scheduler.shutdown(wait=True)
                logger.info("Stopped APScheduler")

            # Stop simple timers
            for timer in self._simple_timers:
                timer.stop()

            self._running = False
            set_gauge("scheduler_running", 0)
            logger.info("AsyncScheduler stopped")

    def remove_job(self, job_id: str) -> bool:
        """
        Remove a scheduled job.

        Args:
            job_id: Job ID to remove

        Returns:
            True if job was found and removed
        """
        try:
            if APSCHEDULER_AVAILABLE and self._scheduler:
                self._scheduler.remove_job(job_id)
                logger.info(f"Removed APScheduler job '{job_id}'")
                removed = True
            else:
                # For simple timers, we need to find and stop the specific timer
                # This is more complex, so for now just log
                logger.warning(
                    f"Cannot remove specific SimpleTimer job '{job_id}' - restart scheduler to change jobs"
                )
                removed = False

            # Remove from stats
            with self._lock:
                if job_id in self._job_stats:
                    del self._job_stats[job_id]

            return removed

        except Exception as e:
            logger.error(f"Failed to remove job '{job_id}': {e}")
            return False

    def list_jobs(self) -> list[dict[str, Any]]:
        """List all scheduled jobs with their status"""
        jobs = []

        if APSCHEDULER_AVAILABLE and self._scheduler:
            for job in self._scheduler.get_jobs():
                job_info = {
                    "id": job.id,
                    "name": job.name,
                    "next_run": (
                        job.next_run_time.isoformat() if job.next_run_time else None
                    ),
                    "trigger": str(job.trigger),
                }

                # Add stats if available
                with self._lock:
                    if job.id in self._job_stats:
                        job_info.update(self._job_stats[job.id])

                jobs.append(job_info)
        else:
            # For simple timers, create basic job info
            with self._lock:
                for job_id, stats in self._job_stats.items():
                    job_info = {
                        "id": job_id,
                        "name": stats["task_name"],
                        "next_run": None,  # Not easily calculable for simple timers
                        "trigger": f"interval({stats.get('interval_seconds', 'unknown')}s)",
                    }
                    job_info.update(stats)
                    jobs.append(job_info)

        return jobs

    def get_stats(self) -> dict[str, Any]:
        """Get scheduler statistics"""
        with self._lock:
            return {
                "running": self._running,
                "backend": "APScheduler" if APSCHEDULER_AVAILABLE else "SimpleTimer",
                "job_count": len(self._job_stats),
                "jobs": dict(self._job_stats),
            }

    def is_running(self) -> bool:
        """Check if scheduler is running"""
        return self._running
