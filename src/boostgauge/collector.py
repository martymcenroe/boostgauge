from __future__ import annotations

import queue
import sys
import threading
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class ProcessRow:
    """A single row from a process-list sweep: pid, name, handle_count."""
    pid: int
    name: str
    handle_count: int


@dataclass(frozen=True)
class Band:
    """A metric's yellow and red thresholds in the metric's own unit."""
    yellow: float
    red: float


@dataclass(frozen=True)
class Thresholds:
    """Per-metric bands. Defaults are issue #7's config defaults, verbatim."""
    conpty: Band
    memory_percent: Band
    process_count: Band
    handle_count: Band


@dataclass(frozen=True)
class SystemSnapshot:
    """Every field measured on the same tick. No field is staler than another."""
    timestamp: float
    conpty_count: int
    process_count: int
    memory_percent: float
    handle_count: int
    unleashed_sessions: int
    driver: str
    composite_value: float


def normalize(value: float, band: Band) -> float:
    """Map a raw metric to 0–100.

    0 at zero load, 60 at the yellow threshold, 100 at the red threshold.
    Clamps between 0.0 and 100.0. Linearly interpolates between points.
    """
    if value <= 0:
        return 0.0
    if band.yellow == 0:
        if value >= band.red:
            return 100.0
        return 60.0
    if value < band.yellow:
        return 0.0
    if value < band.red:
        if band.red == band.yellow:
            return 100.0
        return 60.0 + ((value - band.yellow) / (band.red - band.yellow)) * 40.0
    return 100.0


def composite(conpty_count: int, memory_percent: float, process_count: int,
              handle_count: int, thresholds: Thresholds) -> tuple[float, str]:
    """Normalized-max over the four metrics. Returns (value, driver).

    Ties resolve to the first metric in the order conpty, memory, processes,
    handle_count.
    """
    if isinstance(thresholds, dict):
        thresholds = Thresholds(**{
            k: Band(**v) if isinstance(v, dict) else v
            for k, v in thresholds.items()
        })
    metrics = [
        ("conpty", normalize(float(conpty_count), thresholds.conpty)),
        ("memory_percent", normalize(memory_percent, thresholds.memory_percent)),
        ("process_count", normalize(float(process_count), thresholds.process_count)),
        ("handle_count", normalize(float(handle_count), thresholds.handle_count)),
    ]
    best_name, best_val = metrics[0]
    for name, val in metrics[1:]:
        if val > best_val:
            best_name = name
            best_val = val
    return best_val, best_name


def _psutil_cmdline(proc) -> list[str]:
    """Return the command-line of a psutil Process, or [] on access error."""
    try:
        return proc.cmdline()
    except Exception:
        return []


class DataCollector:
    """Abstract base for platform collectors."""

    def __init__(self, thresholds: Thresholds | None = None) -> None:
        self.thresholds = thresholds

    def collect(self) -> SystemSnapshot:
        raise NotImplementedError


if sys.platform == "win32":
    import ctypes as _ctypes

    _SystemProcessInformation = 5

    def _nt_sweep() -> list[ProcessRow]:
        """Enumerate processes via NtQuerySystemInformation (class 5).

        Returns a list of ProcessRow. Entries whose names cannot be decoded
        as UTF-16-LE are silently skipped.
        """
        _ntdll = _ctypes.WinDLL("ntdll")
        _ret_len = _ctypes.c_ulong(0)
        _ntdll.NtQuerySystemInformation(
            _SystemProcessInformation, None, 0, _ctypes.byref(_ret_len)
        )
        buf_size = _ret_len.value
        if buf_size == 0:
            return []
        _buf = _ctypes.create_string_buffer(buf_size)
        _ntdll.NtQuerySystemInformation(
            _SystemProcessInformation, _buf, buf_size, _ctypes.byref(_ret_len)
        )
        rows: list[ProcessRow] = []
        offset = 0
        while True:
            chunk = _buf.raw[offset:]
            next_off = int.from_bytes(chunk[0:4], "little")
            # UNICODE_STRING at byte 56: Length(2), MaxLength(2), [4-byte pad], Buffer*(8)
            name_len = int.from_bytes(chunk[56:58], "little")
            # UniqueProcessId (HANDLE, 8 bytes) at offset 80 on x64
            pid = int.from_bytes(chunk[80:88], "little")
            # HandleCount (ULONG, 4 bytes) at offset 96 on x64
            handle_count = int.from_bytes(chunk[96:100], "little")
            # Name bytes follow the fixed header at offset 104
            name_bytes = chunk[104: 104 + name_len]
            try:
                name = name_bytes.decode("utf-16-le") if name_len else ""
            except UnicodeDecodeError:
                if next_off == 0:
                    break
                offset += next_off
                continue
            rows.append(ProcessRow(pid=pid, name=name, handle_count=handle_count))
            if next_off == 0:
                break
            offset += next_off
        return rows

    from boostgauge.collectors.windows import WindowsCollector


def make_collector(thresholds: Thresholds | None = None) -> DataCollector:
    """Platform detection. Windows only for now (#4); Mac/Linux are future."""
    if sys.platform == "win32":
        from boostgauge.collectors.windows import WindowsCollector
        return WindowsCollector(thresholds)
    raise NotImplementedError(f"Platform {sys.platform} not supported")


class CollectorThread(threading.Thread):
    """Polls the collector every `interval` seconds on a daemon thread.

    Each snapshot goes onto `snapshots` (a thread-safe queue the GUI drains).
    """

    def __init__(self, collector: DataCollector, interval: float = 2.0,
                 snapshots: queue.Queue | None = None) -> None:
        super().__init__(daemon=True)
        self.collector = collector
        self.interval = interval
        self.snapshots = snapshots or queue.Queue()
        self._stop_event = threading.Event()

    def run(self) -> None:
        while not self._stop_event.is_set():
            try:
                snapshot = self.collector.collect()
                self.snapshots.put(snapshot)
            except Exception:
                pass
            self._stop_event.wait(self.interval)

    def stop(self, timeout: float | None = 5.0) -> None:
        self._stop_event.set()
        self.join(timeout)