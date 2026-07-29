"""Abstract base data collector and metric calculations for BoostGauge.

Issue #4: Feature: Windows Data Collector — ConPTY, Processes, Memory, Handles
"""

from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, TypedDict

import psutil


@dataclass(frozen=True)
class SystemSnapshot:
    """Immutable snapshot of system performance metrics and computed composite value."""

    timestamp: float
    conpty_count: int
    process_count: int
    memory_percent: float
    handle_count: int
    unleashed_sessions: int
    driver: str
    composite_value: float


class CollectorConfigDict(TypedDict, total=False):
    """Configuration dictionary subset passed to DataCollector."""

    poll_interval: float
    threshold_conpty: int
    threshold_memory: float
    threshold_process: int
    threshold_handles: int


DEFAULT_THRESHOLDS: Dict[str, float] = {
    "conpty": 10.0,
    "memory": 90.0,
    "process": 500.0,
    "handle": 100000.0,
}


def normalize_metric(value: float, threshold: float) -> float:
    """Normalize a raw metric value to 0.0 - 100.0 relative to threshold bounds.

    Args:
        value: Raw metric value (>= 0).
        threshold: Baseline 100% threshold value (> 0).

    Returns:
        Normalized score clamped between 0.0 and 100.0.
    """
    if threshold <= 0.0 or value <= 0.0:
        return 0.0
    normalized = (float(value) / float(threshold)) * 100.0
    return min(100.0, max(0.0, normalized))


def calculate_composite_value(
    conpty_count: int,
    memory_percent: float,
    process_count: int,
    handle_count: int,
    thresholds: Optional[Dict[str, float]] = None,
) -> Tuple[float, str]:
    """Calculate normalized-max composite metric value (0.0-100.0) and identify driving metric key.

    Tie-breaking priority order: conpty > memory > process > handle.

    Args:
        conpty_count: Number of active ConPTY processes.
        memory_percent: Virtual memory percentage (0.0-100.0).
        process_count: Total process count.
        handle_count: Aggregate open system handle count.
        thresholds: Optional dictionary mapping metric keys to max threshold values.

    Returns:
        Tuple of (composite_value, driver_name).
    """
    t = DEFAULT_THRESHOLDS.copy()
    if thresholds:
        t.update(thresholds)

    metrics: Dict[str, float] = {
        "conpty": normalize_metric(float(conpty_count), t.get("conpty", 10.0)),
        "memory": normalize_metric(float(memory_percent), t.get("memory", 90.0)),
        "process": normalize_metric(float(process_count), t.get("process", 500.0)),
        "handle": normalize_metric(float(handle_count), t.get("handle", 100000.0)),
    }

    priority = ["conpty", "memory", "process", "handle"]
    best_driver = priority[0]
    best_value = metrics[best_driver]

    for key in priority[1:]:
        val = metrics[key]
        if val > best_value:
            best_value = val
            best_driver = key

    return round(best_value, 2), best_driver


class DataCollector:
    """Abstract base class for platform system metric data collectors."""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        poll_interval: float = 2.0,
    ) -> None:
        """Initialize data collector with polling interval and queue.

        Args:
            config: Optional configuration dictionary.
            poll_interval: Polling interval in seconds (default 2.0s).
        """
        self.config: Dict[str, Any] = config or {}
        self.poll_interval: float = float(
            self.config.get("poll_interval", poll_interval)
        )
        self._running: bool = False
        self._thread: Optional[threading.Thread] = None
        self._queue: queue.Queue[SystemSnapshot] = queue.Queue(maxsize=10)
        self._latest_snapshot: Optional[SystemSnapshot] = None
        self._lock: threading.Lock = threading.Lock()

        self._cached_handle_count: int = 0
        self._cached_unleashed_sessions: int = 0
        self._last_5s_poll: float = 0.0

    def start(self) -> None:
        """Start asynchronous background polling thread."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(
                target=self._run_loop,
                name="DataCollectorThread",
                daemon=True,
            )
            self._thread.start()

    def stop(self) -> None:
        """Stop background polling thread gracefully."""
        with self._lock:
            self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
            self._thread = None

    def is_running(self) -> bool:
        """Check if background polling thread is active."""
        with self._lock:
            return self._running and self._thread is not None and self._thread.is_alive()

    def get_latest_snapshot(self) -> Optional[SystemSnapshot]:
        """Get latest snapshot from memory cache or pop non-blocking from queue.

        Returns:
            Latest SystemSnapshot or None if no snapshots collected yet.
        """
        latest = None
        while not self._queue.empty():
            try:
                latest = self._queue.get_nowait()
            except queue.Empty:
                break

        if latest is not None:
            with self._lock:
                self._latest_snapshot = latest

        with self._lock:
            return self._latest_snapshot

    def collect_snapshot(self, timestamp: float) -> SystemSnapshot:
        """Collect current system metrics snapshot.

        Args:
            timestamp: Sampling timestamp.

        Returns:
            SystemSnapshot instance.
        """
        mem_pct = float(psutil.virtual_memory().percent)
        proc_count = len(psutil.pids())
        conpty_count = 0

        if timestamp - self._last_5s_poll >= 5.0 or self._last_5s_poll == 0.0:
            self._cached_handle_count = self._get_aggregate_handle_count()
            self._cached_unleashed_sessions = self._count_unleashed_sessions_base()
            self._last_5s_poll = timestamp

        thresholds = {
            "conpty": float(self.config.get("threshold_conpty", 10)),
            "memory": float(self.config.get("threshold_memory", 90.0)),
            "process": float(self.config.get("threshold_process", 500)),
            "handle": float(self.config.get("threshold_handles", 100000)),
        }

        composite_val, driver = calculate_composite_value(
            conpty_count=conpty_count,
            memory_percent=mem_pct,
            process_count=proc_count,
            handle_count=self._cached_handle_count,
            thresholds=thresholds,
        )

        return SystemSnapshot(
            timestamp=timestamp,
            conpty_count=conpty_count,
            process_count=proc_count,
            memory_percent=mem_pct,
            handle_count=self._cached_handle_count,
            unleashed_sessions=self._cached_unleashed_sessions,
            driver=driver,
            composite_value=composite_val,
        )

    def _get_aggregate_handle_count(self) -> int:
        """Stub for slow metric aggregate handle count. Overridden by WindowsCollector."""
        return 0

    def _count_unleashed_sessions_base(self) -> int:
        """Stub for slow metric Unleashed sessions. Overridden by WindowsCollector."""
        return 0

    def _push_snapshot(self, snapshot: SystemSnapshot) -> None:
        """Push snapshot to queue, dropping oldest snapshot if queue is full."""
        try:
            self._queue.put_nowait(snapshot)
        except queue.Full:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(snapshot)
            except queue.Full:
                pass

    def _run_loop(self) -> None:
        """Background thread execution loop."""
        while True:
            with self._lock:
                if not self._running:
                    break

            now = time.time()
            try:
                snapshot = self.collect_snapshot(now)
                with self._lock:
                    self._latest_snapshot = snapshot
                self._push_snapshot(snapshot)
            except Exception:
                pass

            time.sleep(self.poll_interval)