from __future__ import annotations

import ctypes
import fnmatch
import os
import struct
import sys
import time
from dataclasses import dataclass

import psutil



__all__ = [
    "SYSTEM_PROCESS_INFORMATION",
    "STATUS_INFO_LENGTH_MISMATCH",
    "CONSOLE_HOSTS",
    "PYTHON_NAMES",
    "UNLEASHED_SIGNATURE",
    "IS_WINDOWS",
    "ProcessRow",
    "WindowsCollector",
    "is_unleashed_cmdline",
    "_psutil_cmdline",
]

SYSTEM_PROCESS_INFORMATION = 5
STATUS_INFO_LENGTH_MISMATCH = -1073741820
_INITIAL_BUFFER = 1024 * 1024
_GROWTH_SLACK = 512 * 1024
CONSOLE_HOSTS = frozenset({"conhost.exe", "openconsole.exe"})
PYTHON_NAMES = frozenset({"python.exe", "python3.exe", "py.exe"})
UNLEASHED_SIGNATURE = "unleashed-c-*.py"
IS_WINDOWS = sys.platform == "win32"

_ntdll = None

_PTR_SIZE = ctypes.sizeof(ctypes.c_void_p)

# Fixed offsets within SYSTEM_PROCESS_INFORMATION (64-bit Windows):
# UNICODE_STRING ImageName starts at 56: Length(USHORT)@56, Buffer(PVOID)@64
# LONG BasePriority@72, 4-byte pad, HANDLE UniqueProcessId@80
# HANDLE InheritedFrom@88, ULONG HandleCount@96
_OFF_NEXT_ENTRY = 0
_OFF_NAME_LEN = 56
_OFF_NAME_BUF = 64
_OFF_PID = 64 + _PTR_SIZE + 8
_OFF_INHERITED = _OFF_PID + _PTR_SIZE
_OFF_HANDLE_COUNT = _OFF_INHERITED + _PTR_SIZE


@dataclass(frozen=True)
class ProcessRow:
    """One row of the sweep. `name` is the lower-cased image name."""
    pid: int
    name: str
    handle_count: int


def _nt_query_system_information():
    """Bind ntdll lazily so the module imports on non-Windows platforms."""
    global _ntdll
    if _ntdll is None and IS_WINDOWS:
        _ntdll = ctypes.WinDLL("ntdll.dll")
    return _ntdll


def _psutil_cmdline(pid: int) -> list[str]:
    """Per-row attribute read on an identified row. A row that died is skipped."""
    try:
        return psutil.Process(pid).cmdline()
    except Exception:
        return []


def is_unleashed_cmdline(args: list[str]) -> bool:
    """Ruling #239's second predicate: an argument's basename matches the signature."""
    for arg in args:
        if fnmatch.fnmatch(os.path.basename(arg).lower(), UNLEASHED_SIGNATURE):
            return True
    return False


class WindowsCollector:
    """One `NtQuerySystemInformation` call per tick; every metric a predicate over it.

    `sweep` and `cmdline` are injectable for the unit tier, which stubs the
    OS calls. `ntdll` injects the ntdll handle directly (also for unit tests).
    """

    def __init__(self, thresholds: Thresholds | None = None, *,
                 sweep=None, cmdline=None, ntdll=None) -> None:
        super().__init__(thresholds)
        self._ntdll = ntdll
        self._sweep = sweep or self.nt_sweep
        self._cmdline = cmdline or _psutil_cmdline
        self._buffer = ctypes.create_string_buffer(_INITIAL_BUFFER)

    def nt_sweep(self) -> list[ProcessRow]:
        """The one enumeration: one system call, one walk of the returned block."""
        ntdll = self._ntdll if self._ntdll is not None else _nt_query_system_information()
        if ntdll is None:
            raise OSError("NtQuerySystemInformation not available on this platform")

        retries = 0
        while retries < 10:
            status = ntdll.NtQuerySystemInformation(
                SYSTEM_PROCESS_INFORMATION,
                self._buffer,
                len(self._buffer),
                None,
            )
            if status == STATUS_INFO_LENGTH_MISMATCH:
                self._buffer = ctypes.create_string_buffer(
                    len(self._buffer) + _GROWTH_SLACK
                )
                retries += 1
                continue
            if status < 0:
                raise OSError(f"NtQuerySystemInformation failed with status {status:#010x}")
            break
        else:
            raise OSError("NtQuerySystemInformation buffer size retries exceeded")

        rows = []
        offset = 0
        buf = self._buffer
        buf_len = len(buf)

        while offset < buf_len:
            base = offset

            next_entry_offset = struct.unpack_from("<I", buf, base + _OFF_NEXT_ENTRY)[0]
            name_len = struct.unpack_from("<H", buf, base + _OFF_NAME_LEN)[0]

            if _PTR_SIZE == 8:
                pid = struct.unpack_from("<Q", buf, base + _OFF_PID)[0]
                handle_count = struct.unpack_from("<I", buf, base + _OFF_HANDLE_COUNT)[0]
                name_buf_ptr = struct.unpack_from("<Q", buf, base + _OFF_NAME_BUF)[0]
            else:
                _off_pid_32 = 64 + 4 + 8
                _off_inherited_32 = _off_pid_32 + 4
                _off_handle_32 = _off_inherited_32 + 4
                pid = struct.unpack_from("<I", buf, base + _off_pid_32)[0]
                handle_count = struct.unpack_from("<I", buf, base + _off_handle_32)[0]
                name_buf_ptr = struct.unpack_from("<I", buf, base + _OFF_NAME_BUF)[0]

            name = ""
            if name_len > 0 and name_buf_ptr:
                try:
                    name_bytes = ctypes.string_at(name_buf_ptr, name_len)
                    name = name_bytes.decode("utf-16-le").lower()
                except (UnicodeDecodeError, OSError):
                    pass

            rows.append(ProcessRow(pid=pid, name=name, handle_count=handle_count))

            if next_entry_offset == 0:
                break
            offset += next_entry_offset

        return rows

    def collect(self) -> SystemSnapshot:
        """One tick: one enumeration, one snapshot."""
        rows = self._sweep()

        process_count = len(rows)
        conpty_count = 0
        handle_count = 0
        unleashed_sessions = 0

        for row in rows:
            handle_count += row.handle_count
            if row.name in CONSOLE_HOSTS:
                conpty_count += 1
            if row.name in PYTHON_NAMES:
                cmdline_args = self._cmdline(row.pid)
                if is_unleashed_cmdline(cmdline_args):
                    unleashed_sessions += 1

        memory_percent = psutil.virtual_memory().percent

        if self.thresholds:
            composite_value, driver = composite(
                conpty_count, memory_percent, process_count, handle_count, self.thresholds
            )
        else:
            composite_value, driver = 0.0, "conpty"

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


# Deferred import breaks the circular dependency: boostgauge.collector imports
# this module at line 113, so importing collector here at module-load time (before
# WindowsCollector is defined) causes the partially-initialised-module ImportError.
# By deferring to after the class body, WindowsCollector exists when collector.py
# re-enters this module, and DataCollector is available for __bases__ back-patching.
from boostgauge.collector import (  # noqa: E402
    DataCollector,
    SystemSnapshot,
    Thresholds,
    composite,
)
WindowsCollector.__bases__ = (DataCollector,)