"""Windows-specific metrics collector using psutil and Win32 process enumeration.

Issue #4: Feature: Windows Data Collector — ConPTY, Processes, Memory, Handles
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple

import psutil
from boostgauge.collector import DataCollector, SystemSnapshot, calculate_composite_value


class WindowsCollector(DataCollector):
    """Windows metrics collector utilizing psutil C-bindings and Win32 API process inspection."""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        poll_interval: float = 2.0,
    ) -> None:
        super().__init__(config=config, poll_interval=poll_interval)
        self._unleashed_pattern: re.Pattern[str] = re.compile(
            r"unleashed-c-.*\.py", re.IGNORECASE
        )

    def collect_snapshot(self, timestamp: float) -> SystemSnapshot:
        """Collect Windows system metrics snapshot.

        Fast metrics (conpty, memory, process count) sampled every 2s.
        Heavy metrics (handles, unleashed sessions) sampled every 5s.

        Args:
            timestamp: Current collection epoch timestamp.

        Returns:
            SystemSnapshot populated with Windows system telemetry.
        """
        mem_pct = float(psutil.virtual_memory().percent)
        sample_heavy = timestamp - self._last_5s_poll >= 5.0 or self._last_5s_poll == 0.0
        proc_count, handle_count_sample = self._get_process_and_handle_counts(
            sample_handles=sample_heavy
        )
        conpty_count = self._count_conpty()

        if sample_heavy:
            self._cached_handle_count = handle_count_sample
            self._cached_unleashed_sessions = self._count_unleashed_sessions()
            self._last_5s_poll = timestamp

        thresholds = {
            "conpty": float(self.config.get("threshold_conpty", 10)),
            "memory": float(self.config.get("threshold_memory", 90.0)),
            "process": float(self.config.get("threshold_process", 500)),
            "handle": float(self.config.get("threshold_handles", 100000)),
        }

        composite_val, driver = calculate_composite_value(
            conpty_count=conpty_count,
            memory_percent=mem_pct,
            process_count=proc_count,
            handle_count=self._cached_handle_count,
            thresholds=thresholds,
        )

        return SystemSnapshot(
            timestamp=timestamp,
            conpty_count=conpty_count,
            process_count=proc_count,
            memory_percent=mem_pct,
            handle_count=self._cached_handle_count,
            unleashed_sessions=self._cached_unleashed_sessions,
            driver=driver,
            composite_value=composite_val,
        )

    def _count_conpty(self) -> int:
        """Count ConPTY allocations by scanning conhost.exe and OpenConsole.exe processes.

        Returns:
            Total ConPTY count.
        """
        count = 0
        for proc in psutil.process_iter(["name"]):
            try:
                name = proc.info.get("name") or ""
                if name.lower() in ("conhost.exe", "openconsole.exe"):
                    count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return count

    def _count_unleashed_sessions(self) -> int:
        """Count Python processes running unleashed-c-*.py scripts.

        Returns:
            Count of active Unleashed AI sessions.
        """
        count = 0
        for proc in psutil.process_iter(["name", "cmdline"]):
            try:
                name = proc.info.get("name") or ""
                if "python" not in name.lower():
                    continue
                cmdline = proc.info.get("cmdline")
                if not cmdline:
                    continue
                cmd_str = " ".join(cmdline)
                if self._unleashed_pattern.search(cmd_str):
                    count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return count

    def _get_process_and_handle_counts(
        self, sample_handles: bool = True
    ) -> Tuple[int, int]:
        """Count running processes and optionally aggregate handle counts.

        Args:
            sample_handles: If True, iterate processes to count total open handles.

        Returns:
            Tuple of (total_process_count, aggregate_handle_count).
        """
        proc_count = 0
        total_handles = 0

        for proc in psutil.process_iter(["num_handles"]):
            proc_count += 1
            if sample_handles:
                try:
                    num_h = proc.info.get("num_handles")
                    if num_h is not None and isinstance(num_h, int):
                        total_handles += num_h
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue

        if not sample_handles:
            total_handles = self._cached_handle_count

        return proc_count, total_handles