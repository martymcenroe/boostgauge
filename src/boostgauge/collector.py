"""Abstract base data collector and snapshot dataclass.

Issue #4: Windows data collector — ConPTY, processes, memory, handles
"""

import abc
from dataclasses import dataclass
import logging
import queue
import threading
import time
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLDS: Dict[str, float] = {
    "conpty": 50.0,
    "memory": 90.0,
    "process": 500.0,
    "handles": 100000.0,
}


@dataclass
class SystemSnapshot:
    timestamp: float
    conpty_count: int
    process_count: int
    memory_percent: float
    handle_count: int
    unleashed_sessions: int
    driver: str
    composite_value: float


def normalize_metric(value: float, threshold: float) -> float:
    """Map a raw metric value to a 0-100 scale based on 0%, 60%, 80%, and 100% threshold boundaries."""
    if threshold <= 0.0 or value <= 0.0:
        return 0.0
    normalized = (float(value) / float(threshold)) * 100.0
    return min(100.0, max(0.0, normalized))


def calculate_composite_metric(
    conpty: int,
    memory_pct: float,
    process_cnt: int,
    handle_cnt: int,
    thresholds: Dict[str, float],
) -> Tuple[float, str]:
    """Calculate composite load value (0-100) using normalized-max algorithm and return (composite_value, driver_name)."""
    t_conpty = thresholds.get("conpty", DEFAULT_THRESHOLDS["conpty"])
    t_memory = thresholds.get("memory", DEFAULT_THRESHOLDS["memory"])
    t_process = thresholds.get("process", DEFAULT_THRESHOLDS["process"])
    t_handles = thresholds.get("handles", DEFAULT_THRESHOLDS["handles"])

    norm_map = {
        "conpty": normalize_metric(float(conpty), t_conpty),
        "memory": normalize_metric(float(memory_pct), t_memory),
        "process": normalize_metric(float(process_cnt), t_process),
        "handle": normalize_metric(float(handle_cnt), t_handles),
    }

    # Precedence order on tie: conpty > memory > process > handle
    precedence = ["conpty", "memory", "process", "handle"]
    max_driver = "conpty"
    max_val = -1.0

    for name in precedence:
        val = norm_map[name]
        if val > max_val:
            max_val = val
            max_driver = name

    return (max(0.0, max_val), max_driver)


class DataCollector(abc.ABC):
    """Abstract base class for platform-specific system resource data collectors."""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        snapshot_queue: Optional[queue.Queue] = None,
    ) -> None:
        self.config = config or {}
        self.poll_interval = float(self.config.get("poll_interval", 2.0))
        self.thresholds: Dict[str, float] = dict(
            DEFAULT_THRESHOLDS, **self.config.get("thresholds", {})
        )
        self.snapshot_queue = snapshot_queue

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start the background collector thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the background collector thread and wait for join."""
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None

    def is_running(self) -> bool:
        """Return True if the background thread is currently active."""
        return self._thread is not None and self._thread.is_alive()

    def poll(self) -> SystemSnapshot:
        """Perform a single synchronous metric collection poll."""
        start_time = time.time()
        raw = self._collect_raw_metrics()
        composite_val, driver = calculate_composite_metric(
            conpty=raw.get("conpty_count", 0),
            memory_pct=raw.get("memory_percent", 0.0),
            process_cnt=raw.get("process_count", 0),
            handle_cnt=raw.get("handle_count", 0),
            thresholds=self.thresholds,
        )
        return SystemSnapshot(
            timestamp=start_time,
            conpty_count=raw.get("conpty_count", 0),
            process_count=raw.get("process_count", 0),
            memory_percent=raw.get("memory_percent", 0.0),
            handle_count=raw.get("handle_count", 0),
            unleashed_sessions=raw.get("unleashed_sessions", 0),
            driver=driver,
            composite_value=composite_val,
        )

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            start_time = time.time()
            try:
                snapshot = self.poll()
                if self.snapshot_queue is not None:
                    try:
                        self.snapshot_queue.put_nowait(snapshot)
                    except queue.Full:
                        self.snapshot_queue.get_nowait()
                        self.snapshot_queue.put_nowait(snapshot)
            except Exception as exc:
                logger.warning("Error during collector polling: %s", exc)

            elapsed = time.time() - start_time
            sleep_time = max(0.0, self.poll_interval - elapsed)
            self._stop_event.wait(sleep_time)

    @abc.abstractmethod
    def _collect_raw_metrics(self) -> Dict[str, Any]:
        """Abstract method implemented by subclasses to poll raw system metrics."""
        ...