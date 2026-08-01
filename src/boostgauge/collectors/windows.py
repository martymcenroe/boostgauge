"""Windows-specific system data collector implementation using psutil and Win32 APIs.

Issue #4: Feature: Windows data collector — ConPTY, processes, memory, handles
"""

import logging
import queue
import sys
import time
from typing import Any, Dict, Optional

import psutil

from boostgauge.collector import DataCollector, SystemSnapshot, calculate_composite_metric

logger = logging.getLogger(__name__)


class WindowsCollector(DataCollector):
    """Windows-specific data collector using psutil and Win32 handle enumeration."""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        snapshot_queue: Optional[queue.Queue[SystemSnapshot]] = None,
    ) -> None:
        cfg = config or {}
        super().__init__(config=cfg, snapshot_queue=snapshot_queue)
        if sys.platform != "win32" and not cfg.get("_allow_non_windows_for_testing", False):
            raise NotImplementedError("WindowsCollector requires Windows operating system")

    def _count_conpty(self) -> int:
        """Count conhost.exe and OpenConsole.exe processes as ConPTY allocations."""
        conpty_count = 0
        for proc in psutil.process_iter(["name"]):
            try:
                pname = (proc.info.get("name") or "").lower()
                if pname in ("conhost.exe", "openconsole.exe"):
                    conpty_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return conpty_count

    def _get_handle_count(self) -> int:
        """Aggregate open handle counts across all accessible processes."""
        total_handles = 0
        for proc in psutil.process_iter(["num_handles"]):
            try:
                num_h = proc.info.get("num_handles")
                if num_h and isinstance(num_h, int):
                    total_handles += num_h
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return total_handles

    def _count_unleashed_sessions(self) -> int:
        """Count Python processes running unleashed session scripts."""
        unleashed_count = 0
        for proc in psutil.process_iter(["name", "cmdline"]):
            try:
                pname = (proc.info.get("name") or "").lower()
                if pname.startswith("python"):
                    cmdline = proc.info.get("cmdline") or []
                    cmd_str = " ".join(cmdline).lower()
                    if "unleashed-c-" in cmd_str:
                        unleashed_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return unleashed_count

    def poll_metrics(self) -> SystemSnapshot:
        """Poll Windows system metrics and return a SystemSnapshot."""
        timestamp = time.time()
        conpty_cnt = self._count_conpty()
        proc_cnt = len(psutil.pids())
        mem_pct = float(psutil.virtual_memory().percent)
        handle_cnt = self._get_handle_count()
        unleashed_cnt = self._count_unleashed_sessions()

        composite_val, driver_name = calculate_composite_metric(
            conpty=conpty_cnt,
            memory_pct=mem_pct,
            process_cnt=proc_cnt,
            handle_cnt=handle_cnt,
            thresholds=self.thresholds,
        )

        return SystemSnapshot(
            timestamp=timestamp,
            conpty_count=conpty_cnt,
            process_count=proc_cnt,
            memory_percent=mem_pct,
            handle_count=handle_cnt,
            unleashed_sessions=unleashed_cnt,
            driver=driver_name,
            composite_value=composite_val,
        )