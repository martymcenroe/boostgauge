"""Abstract base class and composite metric calculations for boostgauge collectors.

Issue #4: Feature: Windows Data Collector — ConPTY, Processes, Memory, Handles
"""

from __future__ import annotations

import queue
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Optional, Tuple, TypedDict


@dataclass(frozen=True)
class SystemSnapshot:
    """Immutable data snapshot containing raw system metrics and composite score."""

    timestamp: float
    conpty_count: int
    process_count: int
    memory_percent: float
    handle_count: int
    unleashed_sessions: int
    driver: str
    composite_value: float


class MetricThreshold(TypedDict):
    """Yellow and red boundary thresholds for metric normalization."""

    yellow: float
    red: float


class MetricThresholdsDict(TypedDict):
    """Dictionary mapping metric keys to boundary thresholds."""

    conpty: MetricThreshold
    memory_percent: MetricThreshold
    process_count: MetricThreshold
    handle_count: MetricThreshold


DEFAULT_THRESHOLDS: MetricThresholdsDict = {
    "conpty": {"yellow": 20.0, "red": 30.0},
    "memory_percent": {"yellow": 70.0, "red": 85.0},
    "process_count": {"yellow": 150.0, "red": 300.0},
    "handle_count": {"yellow": 10000.0, "red": 20000.0},
}


def normalize_metric(value: float, yellow: float, red: float) -> float:
    """Map scalar metric value to 0.0-100.0 score based on yellow (60%) and red (100%) thresholds."""
    if value <= 0.0:
        return 0.0
    if yellow <= 0.0 or red <= yellow:
        return 100.0 if value > 0 else 0.0

    if value <= yellow:
        return (value / yellow) * 60.0
    elif value <= red:
        return 60.0 + ((value - yellow) / (red - yellow)) * 40.0
    else:
        return 100.0 + ((value - red) / red) * 20.0


def compute_composite_metric(
    conpty_count: int,
    memory_percent: float,
    process_count: int,
    handle_count: int,
    thresholds: Optional[MetricThresholdsDict] = None,
) -> Tuple[float, str]:
    """Compute normalized-max composite score (0-100) and identify driving metric name."""
    t = thresholds if thresholds is not None else DEFAULT_THRESHOLDS

    scores: Dict[str, float] = {
        "conpty": normalize_metric(
            float(conpty_count), t["conpty"]["yellow"], t["conpty"]["red"]
        ),
        "memory_percent": normalize_metric(
            float(memory_percent),
            t["memory_percent"]["yellow"],
            t["memory_percent"]["red"],
        ),
        "process_count": normalize_metric(
            float(process_count),
            t["process_count"]["yellow"],
            t["process_count"]["red"],
        ),
        "handle_count": normalize_metric(
            float(handle_count),
            t["handle_count"]["yellow"],
            t["handle_count"]["red"],
        ),
    }

    # Deterministic order precedence: conpty > memory_percent > process_count > handle_count
    driver = "conpty"
    max_score = -1.0
    for key in ["conpty", "memory_percent", "process_count", "handle_count"]:
        if scores[key] > max_score:
            max_score = scores[key]
            driver = key

    composite_value = max(0.0, min(100.0, max_score))
    return composite_value, driver


class DataCollector(ABC):
    """Abstract base class for platform-specific metric collectors."""

    def __init__(self, poll_interval: float = 2.0) -> None:
        self.poll_interval = poll_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    @abstractmethod
    def collect_snapshot(self) -> SystemSnapshot:
        """Poll platform APIs and return a SystemSnapshot."""
        ...

    def start(self, output_queue: queue.Queue[SystemSnapshot]) -> None:
        """Start non-blocking background polling thread pushing snapshots to output_queue."""
        if self._running:
            return

        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._worker_loop, args=(output_queue,), daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop background worker polling thread gracefully."""
        self._running = False
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None

    def is_running(self) -> bool:
        """Return True if background thread is active."""
        return self._running and self._thread is not None and self._thread.is_alive()

    def _worker_loop(self, output_queue: queue.Queue[SystemSnapshot]) -> None:
        """Background thread polling execution loop."""
        while self._running and not self._stop_event.is_set():
            try:
                snapshot = self.collect_snapshot()
                try:
                    output_queue.put_nowait(snapshot)
                except queue.Full:
                    # Drop oldest snapshot on queue overflow
                    try:
                        output_queue.get_nowait()
                        output_queue.put_nowait(snapshot)
                    except queue.Empty:
                        pass
            except Exception:
                pass
            self._stop_event.wait(self.poll_interval)