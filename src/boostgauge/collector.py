"""Abstract base data collector, system snapshot dataclass, and composite metric calculations.

Issue #4: Windows data collector — ConPTY, processes, memory, handles
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
    """Dataclass holding a single system resource metrics snapshot."""

    timestamp: float
    conpty_count: int
    process_count: int
    memory_percent: float
    handle_count: int
    unleashed_sessions: int
    driver: str
    composite_value: float


def normalize_metric(value: float, threshold: float) -> float:
    """Normalize raw metric value against a threshold to 0-100 scale.

    Args:
        value: Raw metric numeric value.
        threshold: Critical threshold value corresponding to 100%.

    Returns:
        Normalized float between 0.0 and 100.0.
    """
    if threshold <= 0.0 or value <= 0.0:
        return 0.0
    normalized = (value / threshold) * 100.0
    return min(100.0, max(0.0, normalized))


def calculate_composite_metric(
    conpty: int,
    memory_pct: float,
    process_cnt: int,
    handle_cnt: int,
    thresholds: Optional[Dict[str, Dict[str, float]]] = None,
) -> Tuple[float, str]:
    """Calculate composite load score using normalized-max algorithm.

    Args:
        conpty: Raw ConPTY process count.
        memory_pct: System memory utilization percentage (0-100).
        process_cnt: Total active process count.
        handle_cnt: Total process open handle count.
        thresholds: Metric threshold dictionary.

    Returns:
        Tuple of (composite_value, driver_metric_name).
    """
    defaults = {
        "conpty": {"critical": 10.0},
        "memory": {"critical": 100.0},
        "process": {"critical": 500.0},
        "handle": {"critical": 100000.0},
    }
    cfg = thresholds if thresholds else defaults

    conpty_thresh = cfg.get("conpty", {}).get("critical", 10.0)
    memory_thresh = cfg.get("memory", {}).get("critical", 100.0)
    process_thresh = cfg.get("process", {}).get("critical", 500.0)
    handle_thresh = cfg.get("handle", {}).get("critical", 100000.0)

    normalized_scores = {
        "conpty": normalize_metric(float(conpty), conpty_thresh),
        "memory": normalize_metric(memory_pct, memory_thresh),
        "process": normalize_metric(float(process_cnt), process_thresh),
        "handle": normalize_metric(float(handle_cnt), handle_thresh),
    }

    driver = max(normalized_scores, key=lambda k: normalized_scores[k])
    composite_val = normalized_scores[driver]
    return composite_val, driver


class DataCollector:
    """Abstract base class for system resource data collectors."""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        snapshot_queue: Optional[queue.Queue] = None,
    ) -> None:
        """Initialize data collector with configuration and output queue."""
        self.config = config or {}
        self.snapshot_queue = snapshot_queue
        self.poll_interval = float(self.config.get("poll_interval", 2.0))
        self.heavy_sample_ratio = int(self.config.get("heavy_sample_ratio", 3))

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_handles: int = 0
        self._last_unleashed: int = 0
        self._iteration_count: int = 0

    def collect_snapshot(self) -> SystemSnapshot:
        """Collect current system metrics and return a SystemSnapshot."""
        now = time.time()
        comp_val, driver = calculate_composite_metric(
            0, 0.0, 0, 0, self.config.get("thresholds")
        )
        return SystemSnapshot(
            timestamp=now,
            conpty_count=0,
            process_count=0,
            memory_percent=0.0,
            handle_count=0,
            unleashed_sessions=0,
            driver=driver,
            composite_value=comp_val,
        )

    def _run_loop(self) -> None:
        """Background thread worker polling loop."""
        while not self._stop_event.is_set():
            t_start = time.time()
            try:
                snapshot = self.collect_snapshot()
                if self.snapshot_queue is not None:
                    try:
                        self.snapshot_queue.put_nowait(snapshot)
                    except queue.Full:
                        try:
                            self.snapshot_queue.get_nowait()
                        except queue.Empty:
                            pass
                        try:
                            self.snapshot_queue.put_nowait(snapshot)
                        except queue.Full:
                            pass
            except Exception as err:
                logger.error("Error collecting system snapshot: %s", err, exc_info=True)

            elapsed = time.time() - t_start
            sleep_duration = max(0.0, self.poll_interval - elapsed)
            self._stop_event.wait(timeout=sleep_duration)

    def start(self) -> None:
        """Start background polling thread if not active."""
        if self._thread is not None and self._thread.is_alive():
            logger.debug("DataCollector background thread already running.")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="BoostGauge-DataCollector",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop background polling thread gracefully."""
        if self._thread is None:
            return

        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None

    def is_running(self) -> bool:
        """Return True if background collector thread is running."""
        return self._thread is not None and self._thread.is_alive()