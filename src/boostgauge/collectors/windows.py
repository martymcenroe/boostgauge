"""WindowsCollector implementing the one-sweep NtQuerySystemInformation metric collection.

Issue #4: Windows data collector.
"""

from __future__ import annotations

import ctypes
import sys
import time
import psutil

from boostgauge.collector import DataCollector, SystemSnapshot

SystemProcessInformation = 5
STATUS_INFO_LENGTH_MISMATCH = 0xC0000004
MAX_BUFFER_SIZE = 10 * 1024 * 1024


if sys.platform == "win32":
    from ctypes import wintypes
    ntdll = ctypes.windll.ntdll
else:
    import types as _types
    wintypes = _types.SimpleNamespace(USHORT=ctypes.c_ushort, ULONG=ctypes.c_ulong)
    ntdll = None


class UNICODE_STRING(ctypes.Structure):
    _fields_ = [
        ("Length", wintypes.USHORT),
        ("MaximumLength", wintypes.USHORT),
        ("Buffer", ctypes.c_void_p),
    ]


class WindowsCollector(DataCollector):

    def collect(self) -> SystemSnapshot:
        """Perform one complete metric collection tick."""
        timestamp = time.time()
        memory_percent = psutil.virtual_memory().percent
        process_count, handle_count, conpty_count, unleashed_sessions = self._sweep()

        raw_metrics = {
            "conpty": float(conpty_count),
            "process_count": float(process_count),
            "memory_percent": memory_percent,
            "handle_count": float(handle_count),
        }

        composite_value, driver = self._compute_composite(raw_metrics)

        return SystemSnapshot(
            timestamp=timestamp,
            conpty_count=conpty_count,
            process_count=process_count,
            memory_percent=memory_percent,
            handle_count=handle_count,
            unleashed_sessions=unleashed_sessions,
            driver=driver,
            composite_value=composite_value,
        )

    def _sweep(self) -> tuple[int, int, int, int]:
        """Call NtQuerySystemInformation and compute metrics in a single pass.
        Returns (process_count, handle_count, conpty_count, unleashed_sessions)."""
        size = wintypes.ULONG(512 * 1024)
        buffer = ctypes.create_string_buffer(size.value)

        while True:
            status = ntdll.NtQuerySystemInformation(
                SystemProcessInformation,
                ctypes.byref(buffer),
                size,
                ctypes.byref(size),
            )

            if (status & 0xFFFFFFFF) == STATUS_INFO_LENGTH_MISMATCH:
                if size.value > MAX_BUFFER_SIZE:
                    return 0, 0, 0, 0
                buffer = ctypes.create_string_buffer(size.value)
            elif status >= 0:
                break
            else:
                return 0, 0, 0, 0

        process_count = 0
        handle_count = 0
        conpty_count = 0
        unleashed_sessions = 0

        offset = 0
        while True:
            process_count += 1

            p_handle_count = ctypes.cast(
                ctypes.byref(buffer, offset + 96), ctypes.POINTER(ctypes.c_ulong)
            ).contents.value
            handle_count += p_handle_count

            us = ctypes.cast(
                ctypes.byref(buffer, offset + 56), ctypes.POINTER(UNICODE_STRING)
            ).contents
            name = ""
            if us.Buffer and us.Length > 0:
                name_bytes = ctypes.string_at(us.Buffer, us.Length)
                name = name_bytes.decode("utf-16-le", errors="ignore").lower()

            if name in ("conhost.exe", "openconsole.exe"):
                conpty_count += 1

            pid = ctypes.cast(
                ctypes.byref(buffer, offset + 80), ctypes.POINTER(ctypes.c_ulonglong)
            ).contents.value

            if self._is_unleashed_session(name, pid):
                unleashed_sessions += 1

            next_entry_offset = ctypes.cast(
                ctypes.byref(buffer, offset), ctypes.POINTER(ctypes.c_ulong)
            ).contents.value
            if next_entry_offset == 0:
                break
            offset += next_entry_offset

        return process_count, handle_count, conpty_count, unleashed_sessions

    def _is_unleashed_session(self, name: str, pid: int) -> bool:
        """Determine if process is an unleashed python session."""
        if "python" not in name:
            return False
        cmdline = self._read_cmdline_safe(pid)
        for arg in cmdline:
            if arg.startswith("unleashed-c-") and arg.endswith(".py"):
                return True
        return False

    def _read_cmdline_safe(self, pid: int) -> list[str]:
        """Safely read command line of a process using psutil."""
        try:
            return psutil.Process(pid).cmdline()
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            return []