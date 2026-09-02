"""Windows collector utilizing NtQuerySystemInformation.

Issue #4: Windows data collector
"""
from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

import psutil

from boostgauge.collector import DataCollector, SystemSnapshot

NTSTATUS = wintypes.LONG
SystemProcessInformation = 5
STATUS_INFO_LENGTH_MISMATCH = 0xC0000004


class UNICODE_STRING(ctypes.Structure):
    _fields_ = [
        ("Length", wintypes.USHORT),
        ("MaximumLength", wintypes.USHORT),
        ("Buffer", wintypes.LPWSTR),
    ]


class SYSTEM_PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("NextEntryOffset", wintypes.ULONG),
        ("NumberOfThreads", wintypes.ULONG),
        ("WorkingSetPrivateSize", ctypes.c_int64),
        ("HardFaultCount", wintypes.ULONG),
        ("NumberOfThreadsHighWatermark", wintypes.ULONG),
        ("CycleTime", ctypes.c_uint64),
        ("CreateTime", ctypes.c_int64),
        ("UserTime", ctypes.c_int64),
        ("KernelTime", ctypes.c_int64),
        ("ImageName", UNICODE_STRING),
        ("BasePriority", wintypes.LONG),
        ("UniqueProcessId", wintypes.HANDLE),
        ("InheritedFromUniqueProcessId", wintypes.HANDLE),
        ("HandleCount", wintypes.ULONG),
    ]


class WindowsCollector(DataCollector):
    def __init__(self, thresholds, poll_interval=2.0):
        super().__init__(thresholds, poll_interval)
        self.ntdll = ctypes.WinDLL("ntdll")
        self.nt_query = self.ntdll.NtQuerySystemInformation
        self.nt_query.argtypes = [
            wintypes.ULONG,
            wintypes.LPVOID,
            wintypes.ULONG,
            ctypes.POINTER(wintypes.ULONG),
        ]
        self.nt_query.restype = NTSTATUS

    def sweep(self) -> SystemSnapshot:
        size = wintypes.ULONG(1024 * 1024)
        buffer = ctypes.create_string_buffer(size.value)

        status = self.nt_query(SystemProcessInformation, buffer, size, ctypes.byref(size))

        while status == STATUS_INFO_LENGTH_MISMATCH:
            buffer = ctypes.create_string_buffer(size.value)
            status = self.nt_query(SystemProcessInformation, buffer, size, ctypes.byref(size))

        if status != 0:
            return SystemSnapshot(time.time(), 0, 0, 0.0, 0, 0, "unknown", 0.0)

        process_count = 0
        conpty_count = 0
        handle_count = 0
        unleashed_sessions = 0

        offset = 0
        while True:
            proc = ctypes.cast(
                ctypes.addressof(buffer) + offset,
                ctypes.POINTER(SYSTEM_PROCESS_INFORMATION),
            ).contents

            process_count += 1
            handle_count += proc.HandleCount

            name = ""
            if proc.ImageName.Buffer:
                name = proc.ImageName.Buffer.lower()

            if name in ("conhost.exe", "openconsole.exe"):
                conpty_count += 1

            if "python" in name:
                pid = proc.UniqueProcessId
                if pid:
                    try:
                        p = psutil.Process(pid)
                        cmdline = p.cmdline()
                        if any("unleashed-c-" in arg for arg in cmdline):
                            unleashed_sessions += 1
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass

            if proc.NextEntryOffset == 0:
                break
            offset += proc.NextEntryOffset

        memory_percent = psutil.virtual_memory().percent
        comp_val, driver = self._compute_composite(
            conpty_count, memory_percent, process_count, handle_count
        )

        return SystemSnapshot(
            timestamp=time.time(),
            conpty_count=conpty_count,
            process_count=process_count,
            memory_percent=memory_percent,
            handle_count=handle_count,
            unleashed_sessions=unleashed_sessions,
            driver=driver,
            composite_value=comp_val,
        )