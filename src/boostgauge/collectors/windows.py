"""Windows-specific data collector implementing Win32 and psutil metric collection.

Issue #4: Feature: Windows Data Collector — ConPTY, Processes, Memory, Handles
"""

from __future__ import annotations

import ctypes
import re
import time
from typing import Optional

import psutil

from boostgauge.collector import (
    DataCollector,
    MetricThresholdsDict,
    SystemSnapshot,
    compute_composite_metric,
)


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


class WindowsCollector(DataCollector):
    """Windows-specific data collector implementing Win32 and psutil metric collection."""

    def __init__(
        self,
        poll_interval: float = 2.0,
        thresholds: Optional[MetricThresholdsDict] = None,
    ) -> None:
        super().__init__(poll_interval=poll_interval)
        self.thresholds = thresholds
        self._unleashed_regex = re.compile(r"unleashed-c-.*\.py", re.IGNORECASE)

    def count_conpty_processes(self) -> int:
        """Count active conhost.exe, OpenConsole.exe, and Windows Terminal (wt.exe/windowsterminal.exe) processes."""
        conpty_count = 0
        try:
            for proc in psutil.process_iter(["name", "cmdline"]):
                try:
                    name = proc.info.get("name") or ""
                    name_lower = name.lower()
                    if name_lower in (
                        "conhost.exe",
                        "openconsole.exe",
                        "windowsterminal.exe",
                        "wt.exe",
                    ):
                        conpty_count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        except Exception:
            pass
        return conpty_count

    def count_unleashed_sessions(self) -> int:
        """Count running python processes executing unleashed session scripts matching unleashed-c-*.py."""
        unleashed_count = 0
        try:
            for proc in psutil.process_iter(["name", "cmdline"]):
                try:
                    name = proc.info.get("name") or ""
                    if "python" in name.lower():
                        cmdline = proc.info.get("cmdline") or []
                        cmd_str = " ".join(cmdline)
                        if self._unleashed_regex.search(cmd_str):
                            unleashed_count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        except Exception:
            pass
        return unleashed_count

    def get_handle_count(self) -> int:
        """Collect total system handle count via psutil process handle sum."""
        total_handles = 0
        try:
            for proc in psutil.process_iter(["num_handles"]):
                try:
                    num_handles = proc.info.get("num_handles")
                    if num_handles is not None:
                        total_handles += num_handles
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        except Exception:
            pass
        return total_handles

    def _get_memory_percent(self) -> float:
        """Get virtual memory percent via psutil with ctypes Win32 fallback."""
        try:
            return float(psutil.virtual_memory().percent)
        except Exception:
            try:
                stat = MEMORYSTATUSEX()
                stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                    return float(stat.dwMemoryLoad)
            except Exception:
                pass
        return 0.0

    def collect_snapshot(self) -> SystemSnapshot:
        """Collect current Windows system metrics and return populated SystemSnapshot."""
        now = time.time()
        memory_percent = self._get_memory_percent()

        try:
            process_count = len(psutil.pids())
        except Exception:
            process_count = 0

        conpty_count = self.count_conpty_processes()
        handle_count = self.get_handle_count()
        unleashed_sessions = self.count_unleashed_sessions()

        composite_value, driver = compute_composite_metric(
            conpty_count=conpty_count,
            memory_percent=memory_percent,
            process_count=process_count,
            handle_count=handle_count,
            thresholds=self.thresholds,
        )

        return SystemSnapshot(
            timestamp=now,
            conpty_count=conpty_count,
            process_count=process_count,
            memory_percent=memory_percent,
            handle_count=handle_count,
            unleashed_sessions=unleashed_sessions,
            driver=driver,
            composite_value=composite_value,
        )