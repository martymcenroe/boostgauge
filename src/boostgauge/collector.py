"""Abstract base class for system data collectors, normalization, and composite metric calculation.

Issue #4: Feature: Windows data collector — ConPTY, processes, memory, handles
"""

from dataclasses import dataclass
import logging
import queue
import threading
import time
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class SystemSnapshot:
    """Immutable snapshot of system metrics at a specific timestamp."""

    timestamp: float
    conpty_count: int
    process_count: int
    memory_percent: float
    handle_count: int
    unleashed_sessions: int
    driver: str
    composite_value: float


DEFAULT_THRESHOLDS: Dict[str, float] = {
    "conpty": 20.0,
    "memory": 90.0,
    "process": 500.0,
    "handles": 100000.0,
}


def normalize_metric(value: float, threshold: float) -> float:
    """Map a raw metric value to a 0.0-100.0 scale relative to metric threshold."""
    if threshold <= 0.0 or value <= 0.0:
        return 0.0
    return min(100.0, (float(value) / float(threshold)) * 100.0)


def calculate_composite_metric(
    conpty: int,
    memory_pct: float,
    process_cnt: int,
    handle_cnt: int,
    thresholds: Dict[str, float],
) -> Tuple[float, str]:
    """Calculate composite load value (0-100) using normalized-max algorithm and return (composite_value, driver)."""
    t_conpty = thresholds.get("conpty", DEFAULT_THRESHOLDS["conpty"])
    t_memory = thresholds.get("memory", DEFAULT_THRESHOLDS["memory"])
    t_process = thresholds.get("process", DEFAULT_THRESHOLDS["process"])
    t_handles = thresholds.get("handles", DEFAULT_THRESHOLDS["handles"])

    norm_scores = {
        "conpty": normalize_metric(float(conpty), t_conpty),
        "memory": normalize_metric(float(memory_pct), t_memory),
        "process": normalize_metric(float(process_cnt), t_process),
        "handles": normalize_metric(float(handle_cnt), t_handles),
    }

    priority = ["conpty", "memory", "process", "handles"]
    best_driver = "conpty"
    max_val = -1.0

    for driver_key in priority:
        val = norm_scores[driver_key]
        if val > max_val:
            max_val = val
            best_driver = driver_key

    return round(max_val, 2), best_driver


class DataCollector:
    """Abstract base class for platform-specific system resource data collectors."""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        snapshot_queue: Optional[queue.Queue[SystemSnapshot]] = None,
    ) -> None:
        """Initialize data collector with configuration and thread-safe output queue."""
        self.config = config or {}
        self.poll_interval: float = float(self.config.get("poll_interval", 2.0))
        self.thresholds: Dict[str, float] = dict(DEFAULT_THRESHOLDS)

        user_thresholds = self.config.get("thresholds")
        if isinstance(user_thresholds, dict):
            for k, v in user_thresholds.items():
                if k in self.thresholds and isinstance(v, (int, float)):
                    self.thresholds[k] = float(v)

        if snapshot_queue is not None:
            self.snapshot_queue = snapshot_queue
        else:
            self.snapshot_queue = queue.Queue(maxsize=100)

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start background polling thread if not already running."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="BoostGaugeCollectorThread")
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        """Signal background thread to stop and join thread within timeout."""
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    def poll_metrics(self) -> SystemSnapshot:
        """Abstract method: Poll raw system metrics and return SystemSnapshot."""
        raise NotImplementedError("Subclasses must implement poll_metrics()")

    def _run_loop(self) -> None:
        """Main background loop polling metrics and pushing to snapshot_queue."""
        while not self._stop_event.is_set():
            start_time = time.monotonic()
            try:
                snapshot = self.poll_metrics()
                if self.snapshot_queue.full():
                    try:
                        self.snapshot_queue.get_nowait()
                    except queue.Empty:
                        pass
                self.snapshot_queue.put_nowait(snapshot)
            except Exception as err:
                logger.warning("Error during system metrics collection: %s", err, exc_info=True)

            elapsed = time.monotonic() - start_time
            sleep_duration = max(0.05, self.poll_interval - elapsed)
            self._stop_event.wait(timeout=sleep_duration)