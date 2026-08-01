"""Windows-specific data collector using psutil and Win32 APIs.

Issue #4: Feature: Windows data collector — ConPTY, processes, memory, handles
"""

import logging
import time
from typing import Any, Dict, Optional
import queue

import psutil

from boostgauge.collector import DataCollector, SystemSnapshot, calculate_composite_metric

logger = logging.getLogger(__name__)


class WindowsCollector(DataCollector):
    """Windows system metric collector implementation."""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        snapshot_queue: Optional[queue.Queue[SystemSnapshot]] = None,
    ) -> None:
        super().__init__(config=config, snapshot_queue=snapshot_queue)

    def _get_conpty_count(self) -> int:
        """Count conhost.exe instances and OpenConsole process allocations."""
        count = 0
        for proc in psutil.process_iter(attrs=["name"]):
            try:
                name = (proc.info.get("name") or "").lower()
                if name in ("conhost.exe", "openconsole.exe"):
                    count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, PermissionError):
                continue
        return count

    def _get_handle_count(self) -> int:
        """Retrieve aggregate total process handles across system processes."""
        total_handles = 0
        for proc in psutil.process_iter(attrs=["num_handles"]):
            try:
                num_handles = proc.info.get("num_handles")
                if num_handles is not None:
                    total_handles += num_handles
            except (psutil.NoSuchProcess, psutil.AccessDenied, PermissionError):
                continue
        return total_handles

    def _get_unleashed_sessions(self) -> int:
        """Detect Unleashed sessions by inspecting python process command lines."""
        unleashed_count = 0
        for proc in psutil.process_iter(attrs=["name"]):
            try:
                name = (proc.info.get("name") or "").lower()
                if name in ("python.exe", "pythonw.exe"):
                    cmdline = proc.cmdline()
                    for arg in cmdline:
                        if "unleashed-c-" in arg and arg.endswith(".py"):
                            unleashed_count += 1
                            break
            except (psutil.NoSuchProcess, psutil.AccessDenied, PermissionError):
                continue
        return unleashed_count

    def collect(self) -> SystemSnapshot:
        """Collect Windows system metrics and calculate composite snapshot load."""
        conpty_cnt = self._get_conpty_count()
        pids = psutil.pids()
        proc_cnt = len(pids)
        mem_pct = psutil.virtual_memory().percent
        handle_cnt = self._get_handle_count()
        unleashed_cnt = self._get_unleashed_sessions()

        composite_val, driver = calculate_composite_metric(
            conpty=conpty_cnt,
            memory_pct=mem_pct,
            process_cnt=proc_cnt,
            handle_cnt=handle_cnt,
            thresholds=self.thresholds,
        )

        return SystemSnapshot(
            timestamp=time.time(),
            conpty_count=conpty_cnt,
            process_count=proc_cnt,
            memory_percent=mem_pct,
            handle_count=handle_cnt,
            unleashed_sessions=unleashed_cnt,
            driver=driver,
            composite_value=composite_val,
        )