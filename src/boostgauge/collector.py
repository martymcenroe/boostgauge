"""Abstract base class and score calculation for system data collectors.

Issue #4: Feature: Windows data collector — ConPTY, processes, memory, handles
"""

from dataclasses import dataclass
import logging
import queue
import threading
import time
from typing import Any, Dict, Optional, Tuple, TypedDict

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLDS: Dict[str, float] = {
    "conpty": 20.0,
    "memory": 90.0,
    "process": 500.0,
    "handles": 100000.0,
}

DEFAULT_POLL_INTERVAL: float = 2.0
MAX_QUEUE_SIZE: int = 100


@dataclass
class SystemSnapshot:
    """Snapshot of current system load metrics and composite score."""

    timestamp: float
    conpty_count: int
    process_count: int
    memory_percent: float
    handle_count: int
    unleashed_sessions: int
    driver: str
    composite_value: float


class MetricThresholds(TypedDict):
    conpty: float
    memory: float
    process: float
    handles: float


class CollectorConfig(TypedDict, total=False):
    poll_interval: float
    thresholds: MetricThresholds


def normalize_metric(value: float, threshold: float) -> float:
    """Map a raw metric value to a 0-100 scale using a 4-point piecewise linear curve.

    0.0 -> 0.0
    0.6 * threshold -> 60.0
    0.8 * threshold -> 80.0
    threshold -> 100.0
    """
    if threshold <= 0.0:
        raise ValueError("Threshold must be positive")

    if value <= 0.0:
        return 0.0

    t60 = 0.6 * threshold
    t80 = 0.8 * threshold

    if value <= t60:
        return (value / t60) * 60.0
    elif value <= t80:
        return 60.0 + ((value - t60) / (t80 - t60)) * 20.0
    elif value <= threshold:
        return 80.0 + ((value - t80) / (threshold - t80)) * 20.0
    else:
        return 100.0


def calculate_composite_metric(
    conpty: int,
    memory_pct: float,
    process_cnt: int,
    handle_cnt: int,
    thresholds: Dict[str, float],
) -> Tuple[float, str]:
    """Compute normalized-max composite load (0-100) and identify the driver metric."""
    for key in ("conpty", "memory", "process", "handles"):
        if key not in thresholds:
            raise KeyError(f"Missing required metric threshold: {key}")

    scores = {
        "conpty": normalize_metric(float(conpty), thresholds["conpty"]),
        "memory": normalize_metric(float(memory_pct), thresholds["memory"]),
        "process": normalize_metric(float(process_cnt), thresholds["process"]),
        "handles": normalize_metric(float(handle_cnt), thresholds["handles"]),
    }

    canonical_order = ("conpty", "memory", "process", "handles")
    max_driver = canonical_order[0]
    max_score = scores[max_driver]

    for metric in canonical_order[1:]:
        if scores[metric] > max_score:
            max_score = scores[metric]
            max_driver = metric

    return max_score, max_driver


class DataCollector:
    """Abstract base class for system metric collectors with background thread polling."""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        snapshot_queue: Optional[queue.Queue[SystemSnapshot]] = None,
    ) -> None:
        self._config = config or {}
        self.poll_interval: float = float(
            self._config.get("poll_interval", DEFAULT_POLL_INTERVAL)
        )
        threshold_cfg = self._config.get("thresholds", {})
        self.thresholds: Dict[str, float] = {
            "conpty": float(threshold_cfg.get("conpty", DEFAULT_THRESHOLDS["conpty"])),
            "memory": float(threshold_cfg.get("memory", DEFAULT_THRESHOLDS["memory"])),
            "process": float(threshold_cfg.get("process", DEFAULT_THRESHOLDS["process"])),
            "handles": float(threshold_cfg.get("handles", DEFAULT_THRESHOLDS["handles"])),
        }

        self.snapshot_queue: queue.Queue[SystemSnapshot] = (
            snapshot_queue if snapshot_queue is not None else queue.Queue(maxsize=MAX_QUEUE_SIZE)
        )

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def collect(self) -> SystemSnapshot:
        """Collect current system metrics and return a SystemSnapshot.

        Must be implemented by platform subclasses.
        """
        raise NotImplementedError("Subclasses must implement collect()")

    def put(self, snapshot: SystemSnapshot) -> None:
        """Enqueue snapshot into snapshot_queue, evicting oldest item if queue is full."""
        try:
            self.snapshot_queue.put(snapshot, block=False)
        except queue.Full:
            try:
                self.snapshot_queue.get(block=False)
            except queue.Empty:
                pass
            try:
                self.snapshot_queue.put(snapshot, block=False)
            except queue.Full:
                pass

    def _poll_loop(self) -> None:
        """Background thread worker loop executing polling cycles."""
        while not self._stop_event.is_set():
            start_time = time.time()
            try:
                snapshot = self.collect()
                self.put(snapshot)
            except Exception as err:
                logger.warning("Collection poll error: %s", err)

            elapsed = time.time() - start_time
            sleep_duration = max(0.0, self.poll_interval - elapsed)
            self._stop_event.wait(timeout=sleep_duration)

    def start(self) -> None:
        """Start the background polling thread."""
        if self._thread is not None and self._thread.is_alive():
            logger.warning("DataCollector background thread is already running.")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._poll_loop, name="DataCollectorThread", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop the background polling thread and wait for completion."""
        if self._thread is None or not self._thread.is_alive():
            return

        self._stop_event.set()
        self._thread.join(timeout=5.0)
        self._thread = None

    @property
    def is_running(self) -> bool:
        """Return True if background thread is active."""
        return self._thread is not None and self._thread.is_alive()