# infra/workqueue.py
"""
Thread-safe worker queue system for offloading heavy tasks from main trading loop.
Provides async task processing to isolate chart rendering, reports, and other IO-heavy
operations to prevent blocking the main trading thread.
"""

import queue
import threading
import time
import traceback
from collections.abc import Callable
from typing import Any, Optional

from core.logger import get_logger

logger = get_logger("workqueue")


class WorkerStats:
    """Statistics tracking for worker performance"""

    def __init__(self):
        self._lock = threading.Lock()
        self.reset()

    def reset(self):
        with self._lock:
            self.tasks_processed = 0
            self.tasks_failed = 0
            self.processing_time_ms = 0.0
            self.avg_processing_time_ms = 0.0

    def record_task(self, processing_time_ms: float, success: bool = True):
        with self._lock:
            if success:
                self.tasks_processed += 1
            else:
                self.tasks_failed += 1

            self.processing_time_ms += processing_time_ms
            total_tasks = self.tasks_processed + self.tasks_failed
            if total_tasks > 0:
                self.avg_processing_time_ms = self.processing_time_ms / total_tasks

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "tasks_processed": self.tasks_processed,
                "tasks_failed": self.tasks_failed,
                "avg_processing_time_ms": self.avg_processing_time_ms,
                "total_processing_time_ms": self.processing_time_ms,
            }


class WorkQueue:
    """
    Thread-safe worker queue with configurable worker pool size.

    Provides async task execution to isolate heavy operations from main thread.
    Tasks are processed by worker threads in FIFO order.

    Example:
        queue = WorkQueue()
        queue.register("chart_render", render_chart_handler)
        queue.start(n_workers=2)
        queue.submit("chart_render", {"symbol": "XAUUSD", "path": "chart.png"})
    """

    def __init__(self):
        self.q = queue.Queue()
        self.handlers: dict[str, Callable[[dict[str, Any]], None]] = {}
        self.stop_event = threading.Event()
        self.workers: list[threading.Thread] = []
        self.stats = WorkerStats()
        self._started = False
        self._lock = threading.Lock()

    def register(
        self, task_name: str, handler: Callable[[dict[str, Any]], None]
    ) -> None:
        """
        Register a task handler function.

        Args:
            task_name: Unique identifier for the task type
            handler: Callable that accepts payload dict and processes the task
        """
        if not callable(handler):
            raise ValueError(f"Handler must be callable, got {type(handler)}")

        with self._lock:
            self.handlers[task_name] = handler

        logger.info(f"Registered handler for task '{task_name}': {handler.__name__}")

    def submit(self, task_name: str, payload: dict[str, Any]) -> None:
        """
        Submit a task for async processing.

        Args:
            task_name: Name of registered task handler
            payload: Data to pass to the handler

        Raises:
            ValueError: If task_name is not registered
        """
        if task_name not in self.handlers:
            raise ValueError(f"No handler registered for task '{task_name}'")

        task = (task_name, payload, time.time())
        self.q.put(task)
        logger.debug(f"Submitted task '{task_name}' to queue (size: {self.q.qsize()})")

    def _worker_loop(self, worker_id: int) -> None:
        """
        Main worker thread loop - processes tasks until stop event is set.

        Args:
            worker_id: Unique identifier for this worker thread
        """
        logger.info(f"Worker {worker_id} started")

        while not self.stop_event.is_set():
            try:
                # Wait for task with timeout to allow periodic stop checking
                task_name, payload, submit_time = self.q.get(timeout=0.5)

                # Track queue latency
                queue_latency_ms = (time.time() - submit_time) * 1000
                logger.debug(
                    f"Worker {worker_id} processing '{task_name}' (queue latency: {queue_latency_ms:.1f}ms)"
                )

                # Execute task with timing
                start_time = time.time()
                try:
                    handler = self.handlers.get(task_name)
                    if handler is None:
                        logger.error(
                            f"Handler for '{task_name}' not found during execution"
                        )
                        self.stats.record_task(0, success=False)
                        continue

                    # Call the handler
                    handler(payload)

                    # Record successful execution
                    processing_time_ms = (time.time() - start_time) * 1000
                    self.stats.record_task(processing_time_ms, success=True)

                    logger.debug(
                        f"Worker {worker_id} completed '{task_name}' in {processing_time_ms:.1f}ms"
                    )

                except Exception as e:
                    # Record failed execution
                    processing_time_ms = (time.time() - start_time) * 1000
                    self.stats.record_task(processing_time_ms, success=False)

                    logger.error(
                        f"Worker {worker_id} failed processing '{task_name}': {e}"
                    )
                    logger.debug(f"Task payload: {payload}")
                    logger.debug(f"Traceback:\n{traceback.format_exc()}")

                finally:
                    self.q.task_done()

            except queue.Empty:
                # Timeout - continue to check stop event
                continue
            except Exception as e:
                logger.error(f"Worker {worker_id} encountered unexpected error: {e}")
                logger.debug(f"Traceback:\n{traceback.format_exc()}")

        logger.info(f"Worker {worker_id} stopped")

    def start(self, n_workers: int = 1) -> None:
        """
        Start the worker pool.

        Args:
            n_workers: Number of worker threads to spawn

        Raises:
            RuntimeError: If already started
        """
        with self._lock:
            if self._started:
                raise RuntimeError("WorkQueue is already started")

            self.stop_event.clear()
            self.stats.reset()

            # Start worker threads
            for i in range(n_workers):
                worker = threading.Thread(
                    target=self._worker_loop,
                    args=(i + 1,),
                    daemon=True,
                    name=f"WorkQueue-Worker-{i+1}",
                )
                worker.start()
                self.workers.append(worker)

            self._started = True

        logger.info(f"Started WorkQueue with {n_workers} workers")

    def stop(self, timeout: float = 5.0) -> bool:
        """
        Stop the worker pool gracefully.

        Args:
            timeout: Maximum time to wait for workers to finish

        Returns:
            True if all workers stopped within timeout, False otherwise
        """
        with self._lock:
            if not self._started:
                logger.warning("WorkQueue is not started, nothing to stop")
                return True

            logger.info("Stopping WorkQueue...")

            # Signal stop to all workers
            self.stop_event.set()

            # Wait for workers to finish
            start_time = time.time()
            workers_alive = []

            while time.time() - start_time < timeout:
                workers_alive = [w for w in self.workers if w.is_alive()]
                if not workers_alive:
                    break
                time.sleep(0.1)

            # Log final status
            if workers_alive:
                logger.warning(
                    f"WorkQueue stopped with {len(workers_alive)} workers still alive after {timeout}s timeout"
                )
                success = False
            else:
                logger.info("WorkQueue stopped successfully - all workers finished")
                success = True

            # Cleanup
            self.workers.clear()
            self._started = False

            return success

    def is_running(self) -> bool:
        """Check if the worker pool is currently running"""
        with self._lock:
            return self._started and any(w.is_alive() for w in self.workers)

    def get_queue_size(self) -> int:
        """Get current number of pending tasks"""
        return self.q.qsize()

    def get_stats(self) -> dict[str, Any]:
        """Get worker performance statistics"""
        base_stats = self.stats.get_stats()

        with self._lock:
            base_stats.update(
                {
                    "queue_size": self.q.qsize(),
                    "workers_running": len([w for w in self.workers if w.is_alive()]),
                    "workers_total": len(self.workers),
                    "is_running": self._started,
                    "registered_tasks": list(self.handlers.keys()),
                }
            )

        return base_stats

    def wait_empty(self, timeout: float | None = None) -> bool:
        """
        Wait for queue to become empty.

        Args:
            timeout: Maximum time to wait (None for no timeout)

        Returns:
            True if queue became empty, False if timeout
        """
        start_time = time.time()

        while self.q.qsize() > 0:
            if timeout and (time.time() - start_time) > timeout:
                return False
            time.sleep(0.1)

        return True

    def __del__(self):
        """Cleanup on deletion"""
        if hasattr(self, "_started") and self._started:
            logger.warning(
                "WorkQueue being deleted while still running - attempting stop"
            )
            self.stop(timeout=1.0)
