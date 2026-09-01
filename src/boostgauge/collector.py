"""Data collection: the snapshot the gauge consumes, and the one-sweep-per-tick rule.

`docs/adrs/0001-single-sweep-collection.md` is binding: every process-derived
metric — process count, ConPTY count, handle count, Unleashed session count —
is a predicate over ONE enumeration of the process table per tick. The
platform collector owns that enumeration (`collectors/windows.py`); this module
owns the snapshot, the thresholds, the composite, the platform switch, and the
polling thread.

Composite (issue #4, folded from #3): normalized-max. Each metric maps to
0–100 against its yellow/red band, and the gauge shows the hottest one, with
`driver` naming it. Averaging hides a single resource in the red; max keeps it.
"""

from __future__ import annotations

import queue
import sys
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Band:
    """A metric's yellow and red thresholds in the metric's own unit."""

    yellow: float
    red: float


@dataclass(frozen=True)
class Thresholds:
    """Per-metric bands. Defaults are issue #7's config defaults, verbatim."""

    conpty: Band = field(default_factory=lambda: Band(30, 60))
    memory_percent: Band = field(default_factory=lambda: Band(60, 80))
    process_count: Band = field(default_factory=lambda: Band(300, 500))
    handle_count: Band = field(default_factory=lambda: Band(30000, 50000))


@dataclass(frozen=True)
class SystemSnapshot:
    """Every field measured on the same tick. No field is staler than another."""

    timestamp: float
    conpty_count: int
    process_count: int
    memory_percent: float
    handle_count: int
    unleashed_sessions: int
    driver: str            # "conpty" | "memory" | "processes" | "handles"
    composite_value: float  # 0-100


def normalize(value: float, band: Band) -> float:
    """Map a raw metric to 0–100 (issue #4).

    0 at zero load, 60 at the yellow threshold, 100 at the red threshold,
    clamped. Linear between those points, so the issue's "80 at elevated"
    lands at the midpoint of yellow→red.
    """
    if value <= 0:
        return 0.0
    if value <= band.yellow:
        return 60.0 * value / band.yellow
    if value >= band.red:
        return 100.0
    return 60.0 + 40.0 * (value - band.yellow) / (band.red - band.yellow)


def composite(conpty_count: int, memory_percent: float, process_count: int,
              handle_count: int, thresholds: Thresholds) -> tuple[float, str]:
    """Normalized-max over the four metrics. Returns (value, driver).

    Ties resolve to the first metric in the order conpty, memory, processes,
    handles.
    """
    scores = (
        ("conpty", normalize(conpty_count, thresholds.conpty)),
        ("memory", normalize(memory_percent, thresholds.memory_percent)),
        ("processes", normalize(process_count, thresholds.process_count)),
        ("handles", normalize(handle_count, thresholds.handle_count)),
    )
    driver, value = max(scores, key=lambda s: s[1])
    return value, driver


class DataCollector(ABC):
    """A platform's one-sweep-per-tick collector."""

    def __init__(self, thresholds: Thresholds | None = None) -> None:
        self.thresholds = thresholds or Thresholds()

    @abstractmethod
    def collect(self) -> SystemSnapshot:
        """One tick: one enumeration, one snapshot."""


def make_collector(thresholds: Thresholds | None = None) -> DataCollector:
    """Platform detection. Windows only for now (#4); Mac/Linux are future."""
    if sys.platform == "win32":
        from boostgauge.collectors.windows import WindowsCollector

        return WindowsCollector(thresholds)
    raise NotImplementedError(
        f"no collector for platform {sys.platform!r}: WindowsCollector is the only "
        "one shipped (#4); MacCollector and LinuxCollector are future work")


class CollectorThread(threading.Thread):
    """Polls the collector every `interval` seconds on a daemon thread.

    Each snapshot goes onto `snapshots` (a thread-safe queue the GUI drains)
    and is kept as `latest`. A failing tick is recorded in `last_error` and
    the loop continues — one bad enumeration must not kill the monitor.
    """

    def __init__(self, collector: DataCollector, interval: float = 2.0,
                 snapshots: queue.Queue | None = None) -> None:
        super().__init__(name="boostgauge-collector", daemon=True)
        self.collector = collector
        self.interval = interval
        self.snapshots: queue.Queue = snapshots if snapshots is not None else queue.Queue()
        self.latest: SystemSnapshot | None = None
        self.last_error: BaseException | None = None
        self._stop_event = threading.Event()

    def run(self) -> None:
        while not self._stop_event.is_set():
            try:
                snap = self.collector.collect()
            except Exception as exc:  # noqa: BLE001 — the loop must survive a bad tick
                self.last_error = exc
            else:
                self.latest = snap
                self.snapshots.put(snap)
            self._stop_event.wait(self.interval)

    def stop(self, timeout: float | None = 5.0) -> None:
        self._stop_event.set()
        self.join(timeout)


__all__ = [
    "Band", "Thresholds", "SystemSnapshot", "normalize", "composite",
    "DataCollector", "make_collector", "CollectorThread", "time",
]
