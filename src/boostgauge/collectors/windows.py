"""Windows-specific system metrics data collector.

Issue #4: Windows data collector — ConPTY, processes, memory, handles
"""

import logging
import time
from typing import Any, Dict, Optional
import queue
import psutil

from boostgauge.collector import DataCollector, SystemSnapshot

logger = logging.getLogger(__name__)


class WindowsCollector(DataCollector):
    """Windows-specific system resource data collector."""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        snapshot_queue: Optional[queue.Queue[SystemSnapshot]] = None,
    ) -> None:
        super().__init__(config=config, snapshot_queue=snapshot_queue)
        self._last_handle_time: float = 0.0
        self._last_unleashed_time: float = 0.0
        self._cached_handle_count: int = 0
        self._cached_unleashed_count: int = 0

    def _collect_raw_metrics(self) -> Dict[str, Any]:
        """Poll Windows system metrics using psutil and Win32 API calls."""
        now = time.time()

        conpty_cnt = self._count_conpty()
        process_cnt = self._count_processes()
        memory_pct = self._count_memory()

        if now - self._last_handle_time >= 5.0 or self._last_handle_time == 0.0:
            self._cached_handle_count = self._count_handles()
            self._last_handle_time = now

        if now - self._last_unleashed_time >= 5.0 or self._last_unleashed_time == 0.0:
            self._cached_unleashed_count = self._count_unleashed_sessions()
            self._last_unleashed_time = now

        return {
            "conpty_count": conpty_cnt,
            "process_count": process_cnt,
            "memory_percent": memory_pct,
            "handle_count": self._cached_handle_count,
            "unleashed_sessions": self._cached_unleashed_count,
        }

    def _count_conpty(self) -> int:
        """Count conhost.exe processes and Windows Terminal internal pseudo-consoles."""
        conpty_count = 0
        try:
            for proc in psutil.process_iter(["name"]):
                try:
                    name = proc.info.get("name") or ""
                    name_lower = name.lower()
                    if name_lower == "conhost.exe":
                        conpty_count += 1
                    elif name_lower == "windowsterminal.exe":
                        conpty_count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        except Exception as exc:
            logger.warning("Error scanning ConPTY processes: %s", exc)
        return conpty_count

    def _count_processes(self) -> int:
        """Return total active process count."""
        try:
            return len(psutil.pids())
        except Exception:
            return 0

    def _count_memory(self) -> float:
        """Return current virtual memory percentage."""
        try:
            return float(psutil.virtual_memory().percent)
        except Exception:
            return 0.0

    def _count_handles(self) -> int:
        """Calculate total process handle count across accessible processes."""
        total_handles = 0
        try:
            for proc in psutil.process_iter(["num_handles"]):
                try:
                    num_handles = proc.info.get("num_handles")
                    if num_handles is not None:
                        total_handles += num_handles
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        except Exception as exc:
            logger.warning("Error calculating system handle count: %s", exc)
            return self._cached_handle_count
        return total_handles

    def _count_unleashed_sessions(self) -> int:
        """Count python processes with unleashed-c-*.py in their command line."""
        unleashed_count = 0
        try:
            for proc in psutil.process_iter(["name", "cmdline"]):
                try:
                    name = proc.info.get("name") or ""
                    if "python" in name.lower():
                        cmdline = proc.info.get("cmdline") or []
                        if any("unleashed-c-" in arg for arg in cmdline):
                            unleashed_count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        except Exception as exc:
            logger.warning("Error searching Unleashed sessions: %s", exc)
            return self._cached_unleashed_count
        return unleashed_count