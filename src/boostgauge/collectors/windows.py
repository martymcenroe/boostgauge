"""Windows-specific system metric collector."""

import queue
import threading
import time
from typing import Dict, Optional

import psutil

from boostgauge.collector import DataCollector, SystemSnapshot


class WindowsCollector(DataCollector):
    def __init__(
        self,
        target_queue: queue.Queue,
        poll_interval: float = 2.0,
        thresholds: Optional[Dict[str, float]] = None,
    ):
        self._target_queue = target_queue
        self.poll_interval = poll_interval
        self._thresholds = thresholds or {
            "conpty": 10.0,
            "memory": 100.0,
            "processes": 500.0,
            "handles": 50000.0,
        }
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._python_interpreters = {"python.exe", "pythonw.exe"}

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join()

    def _poll_loop(self) -> None:
        while not self._stop_event.is_set():
            snapshot = self._collect_snapshot()
            try:
                self._target_queue.put_nowait(snapshot)
            except queue.Full:
                pass
            self._stop_event.wait(self.poll_interval)

    def _collect_snapshot(self) -> SystemSnapshot:
        """Performs the single process sweep and memory read to generate a snapshot."""
        conpty = 0
        process_count = 0
        handles = 0
        unleashed = 0

        for proc in psutil.process_iter(attrs=["name", "num_handles", "cmdline"]):
            try:
                info = proc.info
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

            process_count += 1

            name = info.get("name")
            name_lower = name.lower() if name else ""

            if name_lower in ("conhost.exe", "openconsole.exe"):
                conpty += 1

            num_handles = info.get("num_handles")
            if num_handles is not None:
                handles += num_handles

            if name_lower in self._python_interpreters:
                cmdline = info.get("cmdline") or []
                if any("unleashed-c-" in arg for arg in cmdline):
                    unleashed += 1

        memory = psutil.virtual_memory().percent

        norm_conpty = self._normalize(conpty, self._thresholds.get("conpty", 10.0))
        norm_mem = self._normalize(memory, self._thresholds.get("memory", 100.0))
        norm_proc = self._normalize(process_count, self._thresholds.get("processes", 500.0))
        norm_handles = self._normalize(handles, self._thresholds.get("handles", 50000.0))

        metrics = {
            "conpty": norm_conpty,
            "memory": norm_mem,
            "processes": norm_proc,
            "handles": norm_handles,
        }

        driver = max(metrics.items(), key=lambda x: x[1])[0]
        composite_value = metrics[driver]

        return SystemSnapshot(
            timestamp=time.time(),
            conpty_count=conpty,
            process_count=process_count,
            memory_percent=memory,
            handle_count=handles,
            unleashed_sessions=unleashed,
            driver=driver,
            composite_value=composite_value,
        )

    def _normalize(self, value: float, threshold: float) -> float:
        """Map raw metric to 0-100 gauge scale."""
        if threshold <= 0:
            return 100.0
        return min(100.0, (float(value) / threshold) * 100.0)