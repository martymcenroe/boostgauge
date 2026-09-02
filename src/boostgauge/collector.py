"""Abstract base collector and composite calculation.

Issue #4: Windows data collector
"""
from __future__ import annotations

import queue
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TypedDict


class ThresholdsConfig(TypedDict):
    yellow: float
    red: float


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

    def __post_init__(self) -> None:
        # Windows APIs return ctypes wchar arrays; coerce to plain str so callers
        # can store the value in a c_wchar_p field without a TypeError.
        if not isinstance(self.driver, str):
            if hasattr(self.driver, "value"):
                self.driver = self.driver.value or ""
            else:
                self.driver = str(self.driver)


class DataCollector(ABC):
    def __init__(self, thresholds: dict[str, ThresholdsConfig], poll_interval: float = 2.0):
        self.thresholds = thresholds
        self.poll_interval = poll_interval
        self._queue: queue.Queue[SystemSnapshot] = queue.Queue()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join()

    def get_queue(self) -> queue.Queue[SystemSnapshot]:
        return self._queue

    def _poll_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                snapshot = self.sweep()
                self._queue.put(snapshot)
            except Exception:
                pass
            self._stop_event.wait(self.poll_interval)

    def _compute_composite(self, conpty: int, memory: float, processes: int, handles: int) -> tuple[float, str]:
        metrics = {
            "conpty": conpty,
            "memory_percent": memory,
            "process_count": processes,
            "handle_count": handles,
        }

        max_norm = 0.0
        driver = "memory_percent"

        for name, val in metrics.items():
            if name not in self.thresholds:
                continue
            t = self.thresholds[name]
            yellow = t.get("yellow", 0.0)
            red = t.get("red", 0.0)

            if val <= yellow:
                norm = (val / yellow) * 60.0 if yellow > 0 else 0.0
            else:
                norm = 60.0 + ((val - yellow) / (red - yellow)) * 40.0 if red > yellow else 60.0
                norm = min(100.0, norm)

            if norm >= max_norm:
                max_norm = norm
                driver = name

        return max_norm, driver

    @abstractmethod
    def sweep(self) -> SystemSnapshot:
        """Perform system sweep and return snapshot."""
        pass