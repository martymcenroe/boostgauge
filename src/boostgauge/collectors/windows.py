"""WindowsCollector — ADR 0001's one sweep per tick, as one system call.

The sweep is a single `NtQuerySystemInformation(SystemProcessInformation)`
call. It returns image name, pid and handle count for every process without
opening any of them, in about 2 ms on a 373-process machine. The psutil
`process_iter` sweep the ADR originally named cost 422 ms per tick — 21 % of
a core at 2 s — because reading `num_handles` opens every process (#405).

psutil is still used, but never to enumerate: `virtual_memory()` for memory,
and `Process(pid).cmdline()` for exactly the rows the sweep identified as
Python interpreters, which is where the Unleashed session count comes from.
"""

from __future__ import annotations

import ctypes
import fnmatch
import os
import struct
import sys
import time
from dataclasses import dataclass

import psutil

from boostgauge.collector import DataCollector, SystemSnapshot, Thresholds, composite

CONSOLE_HOSTS = frozenset({"conhost.exe", "openconsole.exe"})
PYTHON_NAMES = frozenset({"python.exe", "pythonw.exe"})
UNLEASHED_SIGNATURE = "unleashed-c-*.py"

SYSTEM_PROCESS_INFORMATION = 5
STATUS_INFO_LENGTH_MISMATCH = -1073741820  # NTSTATUS 0xC0000004 as a signed LONG

# x64 SYSTEM_PROCESS_INFORMATION header — 104 bytes through SessionId:
#   0 NextEntryOffset u32 | 4 NumberOfThreads u32 | 8 WorkingSetPrivateSize i64
#  16 HardFaultCount u32 | 20 NumberOfThreadsHighWatermark u32 | 24 CycleTime u64
#  32 CreateTime i64 | 40 UserTime i64 | 48 KernelTime i64
#  56 ImageName UNICODE_STRING {u16 Length, u16 MaximumLength, pad4, u64 Buffer}
#  72 BasePriority i32 | pad4 | 80 UniqueProcessId u64 | 88 InheritedFromUniqueProcessId u64
#  96 HandleCount u32 | 100 SessionId u32
# The parse is pinned by tests/integration/test_windows_sweep_crosscheck.py: a
# wrong offset would miscount silently, so the counts are checked against
# psutil on the running machine.
_HEADER = struct.Struct("<IIqIIQqqqHH4xQl4xQQII")
assert _HEADER.size == 104

_INITIAL_BUFFER = 1 << 20
_GROWTH_SLACK = 64 << 10


@dataclass(frozen=True)
class ProcessRow:
    """One row of the sweep. `name` is the lower-cased image name."""

    pid: int
    name: str
    handle_count: int


_ntdll = None


def _nt_query_system_information():
    """Bind ntdll lazily so the module imports on non-Windows platforms."""
    global _ntdll
    if _ntdll is None:
        from ctypes import wintypes

        lib = ctypes.WinDLL("ntdll")
        fn = lib.NtQuerySystemInformation
        fn.argtypes = [wintypes.ULONG, ctypes.c_void_p, wintypes.ULONG,
                       ctypes.POINTER(wintypes.ULONG)]
        fn.restype = wintypes.LONG
        _ntdll = fn
    return _ntdll


def _psutil_cmdline(pid: int) -> list[str]:
    """Per-row attribute read on an identified row. A row that died is skipped."""
    try:
        return psutil.Process(pid).cmdline()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return []


def is_unleashed_cmdline(args: list[str]) -> bool:
    """Ruling #239's second predicate: an argument's basename matches the signature."""
    return any(fnmatch.fnmatch(os.path.basename(a).lower(), UNLEASHED_SIGNATURE)
               for a in args)


class WindowsCollector(DataCollector):
    """One `NtQuerySystemInformation` call per tick; every metric a predicate over it.

    `sweep` and `cmdline` are injectable for the unit tier, which stubs the
    system call and asserts that one call yields all four metrics.
    """

    def __init__(self, thresholds: Thresholds | None = None, *,
                 sweep=None, cmdline=None) -> None:
        super().__init__(thresholds)
        self._sweep = sweep or self.nt_sweep
        self._cmdline = cmdline or _psutil_cmdline
        self._buffer = ctypes.create_string_buffer(_INITIAL_BUFFER)

    def nt_sweep(self) -> list[ProcessRow]:
        """The one enumeration: one system call, one walk of the returned block."""
        from ctypes import wintypes

        query = _nt_query_system_information()
        needed = wintypes.ULONG(0)
        while True:
            status = query(SYSTEM_PROCESS_INFORMATION, self._buffer,
                           len(self._buffer), ctypes.byref(needed))
            if status == STATUS_INFO_LENGTH_MISMATCH:
                self._buffer = ctypes.create_string_buffer(needed.value + _GROWTH_SLACK)
                continue
            if status != 0:
                raise OSError(f"NtQuerySystemInformation failed: NTSTATUS 0x{status & 0xFFFFFFFF:08X}")
            break

        rows: list[ProcessRow] = []
        raw = self._buffer.raw
        offset = 0
        while True:
            (next_offset, _threads, _wsp, _hard_faults, _hwm, _cycles,
             _created, _user, _kernel, name_len, _name_max, name_ptr,
             _priority, pid, _parent_pid, handle_count, _session) = _HEADER.unpack_from(raw, offset)
            name = ctypes.wstring_at(name_ptr, name_len // 2).lower() if name_ptr and name_len else ""
            rows.append(ProcessRow(pid=pid, name=name, handle_count=handle_count))
            if next_offset == 0:
                return rows
            offset += next_offset

    def collect(self) -> SystemSnapshot:
        rows = self._sweep()  # the one enumeration this tick

        process_count = len(rows)
        conpty_count = sum(1 for r in rows if r.name in CONSOLE_HOSTS)
        handle_count = sum(r.handle_count for r in rows)
        unleashed_sessions = sum(
            1 for r in rows
            if r.name in PYTHON_NAMES and is_unleashed_cmdline(self._cmdline(r.pid)))

        memory_percent = float(psutil.virtual_memory().percent)  # ADR 0001 §2.6: outside the mandate

        value, driver = composite(conpty_count, memory_percent, process_count,
                                  handle_count, self.thresholds)
        return SystemSnapshot(
            timestamp=time.time(),
            conpty_count=conpty_count,
            process_count=process_count,
            memory_percent=memory_percent,
            handle_count=handle_count,
            unleashed_sessions=unleashed_sessions,
            driver=driver,
            composite_value=value,
        )


IS_WINDOWS = sys.platform == "win32"
