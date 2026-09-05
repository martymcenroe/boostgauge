"""Abstract base class DataCollector and background thread management.

Issue #4: Windows data collector.
"""

from __future__ import annotations

import abc
import dataclasses
import threading
import time
from typing import TypedDict


try:
    import psutil
except ImportError:
    psutil = None  # type: ignore[assignment]

import ctypes as _ctypes

try:
    NtQuerySystemInformation = _ctypes.windll.ntdll.NtQuerySystemInformation
except (AttributeError, OSError):
    NtQuerySystemInformation = None


@dataclasses.dataclass
class SystemSnapshot:
    timestamp: float
    conpty_count: int
    process_count: int
    memory_percent: float
    handle_count: int
    unleashed_sessions: int
    driver: str
    composite_value: float


class ThresholdBand(TypedDict):
    yellow: float
    red: float


class DataCollector(abc.ABC):
    def __init__(self, thresholds: dict[str, ThresholdBand], poll_interval: float = 2.0, *, pid: int | None = None) -> None:
        if poll_interval <= 0:
            raise ValueError("poll_interval must be positive")
        self.thresholds = thresholds
        self.poll_interval = poll_interval
        self.pid = pid
        self._latest_snapshot: SystemSnapshot | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._callbacks: list = []

    def start(self) -> None:
        """Start the background polling thread."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._poll_loop, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        """Signal the background thread to stop and wait for it to exit."""
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join()

    def register_callback(self, cb) -> None:
        """Register a callable invoked with each new snapshot from the poll loop."""
        self._callbacks.append(cb)

    def get_latest_snapshot(self) -> SystemSnapshot | None:
        """Retrieve the most recent snapshot."""
        return self._latest_snapshot

    def _poll_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                snapshot = self.collect()
                self._latest_snapshot = snapshot
                for cb in list(self._callbacks):
                    try:
                        cb(snapshot)
                    except Exception:
                        pass
            except Exception:
                pass
            self._stop_event.wait(self.poll_interval)

    @abc.abstractmethod
    def collect(self) -> SystemSnapshot:
        """Perform one complete metric collection tick."""
        raise NotImplementedError

    def _normalize(self, value: float, threshold_band: ThresholdBand) -> float:
        """Normalize a raw value to a 0-100 gauge scale."""
        y = threshold_band["yellow"]
        r = threshold_band["red"]
        if r == y:
            return 100.0 if value >= r else 0.0
        if value < y:
            return (value / y) * 60.0
        elif value < r:
            return 60.0 + ((value - y) / (r - y)) * 20.0
        else:
            return min(100.0, 80.0 + ((value - r) / (max(1.0, r))) * 20.0)

    def _compute_composite(self, raw_metrics: dict[str, float]) -> tuple[float, str]:
        """Compute the highest normalized metric and its driver name."""
        highest_val = 0.0
        driver = "none"
        for metric_name, val in raw_metrics.items():
            if metric_name in self.thresholds:
                norm = self._normalize(val, self.thresholds[metric_name])
                if norm > highest_val:
                    highest_val = norm
                    driver = metric_name
        return highest_val, driver


class WindowsCollector(DataCollector):
    """Concrete collector that reads live Windows system metrics via psutil."""

    def _get_system_handle_count(self) -> int:
        """Return system-wide open handle count via NtQuerySystemInformation."""
        if NtQuerySystemInformation is None:
            return 0
        buf_size = 1 << 17  # 128 KB starting point
        for _ in range(5):
            buf = (_ctypes.c_byte * buf_size)()
            ret = NtQuerySystemInformation(16, buf, buf_size, None)
            if ret == 0:  # STATUS_SUCCESS
                return _ctypes.c_ulong.from_buffer(buf).value
            buf_size *= 2
        return 0

    def _is_unleashed_session(self, name: str, pid: int) -> bool:
        """Return True if the process looks like an Unleashed session."""
        if "unleashed" in name:
            return True
        cmdline_str = " ".join(self._read_cmdline_safe(pid)).lower()
        return "unleashed" in cmdline_str

    def _read_cmdline_safe(self, pid: int) -> list[str]:
        """Return the command-line argument list for *pid*, or [] on any error."""
        try:
            return psutil.Process(pid).cmdline()
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            return []

    def collect(self) -> SystemSnapshot:
        process_count = len(psutil.pids())
        memory_percent = psutil.virtual_memory().percent

        conpty_count = 0
        handle_count = self._get_system_handle_count()
        unleashed_sessions = 0
        for proc in psutil.process_iter(["name", "pid"]):
            try:
                name = (proc.info["name"] or "").lower()
                if name in ("conhost.exe", "openconsole.exe"):
                    conpty_count += 1
                if self._is_unleashed_session(name, proc.info["pid"]):
                    unleashed_sessions += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        raw_metrics = {
            "conpty_count": float(conpty_count),
            "process_count": float(process_count),
            "memory_percent": memory_percent,
            "handle_count": float(handle_count),
            "unleashed_sessions": float(unleashed_sessions),
        }
        composite_value, driver = self._compute_composite(raw_metrics)

        return SystemSnapshot(
            timestamp=time.time(),
            conpty_count=conpty_count,
            process_count=process_count,
            memory_percent=memory_percent,
            handle_count=handle_count,
            unleashed_sessions=unleashed_sessions,
            driver=driver,
            composite_value=composite_value,
        )


class DummyCollector(DataCollector):
    """Deterministic collector for tests; returns a fixed snapshot on each call."""

    def __init__(
        self,
        thresholds: dict[str, ThresholdBand],
        poll_interval: float = 2.0,
        *,
        snapshot: SystemSnapshot | None = None,
    ) -> None:
        super().__init__(thresholds, poll_interval)
        self._fixed_snapshot = snapshot

    def collect(self) -> SystemSnapshot:
        if self._fixed_snapshot is not None:
            return self._fixed_snapshot
        raw_metrics: dict[str, float] = {
            "conpty_count": 0.0,
            "process_count": 0.0,
            "memory_percent": 0.0,
            "handle_count": 0.0,
            "unleashed_sessions": 0.0,
        }
        composite_value, driver = self._compute_composite(raw_metrics)
        return SystemSnapshot(
            timestamp=time.time(),
            conpty_count=0,
            process_count=0,
            memory_percent=0.0,
            handle_count=0,
            unleashed_sessions=0,
            driver=driver,
            composite_value=composite_value,
        )