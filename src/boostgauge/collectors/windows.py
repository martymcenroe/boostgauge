"""Windows-specific resource data collector using psutil and Win32 process filtering.

Issue #4: Windows data collector — ConPTY, processes, memory, handles
"""

import logging
import re
import time
from typing import Any, Dict, Optional, Set
import queue

import psutil

from boostgauge.collector import (
    DataCollector,
    SystemSnapshot,
    calculate_composite_metric,
)

logger = logging.getLogger(__name__)

UNLEASHED_REGEX = re.compile(r"unleashed-c-.*\.py", re.IGNORECASE)
CONPTY_PROCESS_NAMES: Set[str] = {
    "conhost.exe",
    "openconsole.exe",
    "windowsterminal.exe",
}


class WindowsCollector(DataCollector):
    """Windows implementation of system resource collector using psutil."""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        snapshot_queue: Optional[queue.Queue] = None,
    ) -> None:
        super().__init__(config=config, snapshot_queue=snapshot_queue)
        self._cached_conpty: int = 0
        self._cached_procs: int = 0
        self._cached_memory: float = 0.0

    def collect_conpty_count(self) -> int:
        """Count active ConPTY / pseudo-console processes."""
        count = 0
        try:
            for proc in psutil.process_iter(attrs=["name"]):
                try:
                    name = proc.info.get("name")
                    if name and name.lower() in CONPTY_PROCESS_NAMES:
                        count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as err:
            logger.debug("Error iterating processes for ConPTY count: %s", err)
            return self._cached_conpty

        self._cached_conpty = count
        return count

    def collect_process_count(self) -> int:
        """Retrieve total count of active system processes."""
        try:
            count = len(psutil.pids())
            self._cached_procs = count
            return count
        except Exception as err:
            logger.debug("Error querying process count: %s", err)
            return self._cached_procs

    def collect_memory_percent(self) -> float:
        """Retrieve total system virtual memory utilization percentage."""
        try:
            pct = float(psutil.virtual_memory().percent)
            self._cached_memory = pct
            return pct
        except Exception as err:
            logger.debug("Error querying memory percentage: %s", err)
            return self._cached_memory

    def collect_handle_count(self) -> int:
        """Aggregate open handle count across accessible processes."""
        total_handles = 0
        try:
            for proc in psutil.process_iter(attrs=["pid"]):
                try:
                    num_handles = proc.num_handles()
                    if num_handles:
                        total_handles += num_handles
                except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
                    continue
        except Exception as err:
            logger.debug("Error aggregating process handles: %s", err)
            return self._last_handles

        self._last_handles = total_handles
        return total_handles

    def collect_unleashed_sessions(self) -> int:
        """Count active Python processes running scripts matching unleashed-c-*.py."""
        count = 0
        try:
            for proc in psutil.process_iter(attrs=["name"]):
                try:
                    name = proc.info.get("name")
                    if name and "python" in name.lower():
                        cmdline = proc.cmdline()
                        if any(UNLEASHED_REGEX.search(arg) for arg in cmdline):
                            count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as err:
            logger.debug("Error scanning unleashed session processes: %s", err)
            return self._last_unleashed

        self._last_unleashed = count
        return count

    def collect_snapshot(self) -> SystemSnapshot:
        """Collect fast and heavy metrics according to sample ratio and return SystemSnapshot."""
        now = time.time()

        conpty = self.collect_conpty_count()
        procs = self.collect_process_count()
        mem_pct = self.collect_memory_percent()

        if self._iteration_count % self.heavy_sample_ratio == 0:
            handles = self.collect_handle_count()
            unleashed = self.collect_unleashed_sessions()
            self._last_handles = handles
            self._last_unleashed = unleashed
        else:
            handles = self._last_handles
            unleashed = self._last_unleashed

        self._iteration_count += 1

        comp_val, driver = calculate_composite_metric(
            conpty=conpty,
            memory_pct=mem_pct,
            process_cnt=procs,
            handle_cnt=handles,
            thresholds=self.config.get("thresholds"),
        )

        return SystemSnapshot(
            timestamp=now,
            conpty_count=conpty,
            process_count=procs,
            memory_percent=mem_pct,
            handle_count=handles,
            unleashed_sessions=unleashed,
            driver=driver,
            composite_value=comp_val,
        )