"""Unit tests for WindowsCollector: single-sweep call count and composite logic.

Issue #4: Windows data collector
"""
from __future__ import annotations

import ctypes
import struct
from ctypes import wintypes
from unittest.mock import MagicMock, patch

import psutil
import pytest

from boostgauge.collector import DataCollector, SystemSnapshot, ThresholdsConfig
from boostgauge.collectors.windows import (
    SYSTEM_PROCESS_INFORMATION,
    UNICODE_STRING,
    WindowsCollector,
)

DEFAULT_THRESHOLDS: dict[str, ThresholdsConfig] = {
    "conpty": {"yellow": 2.0, "red": 5.0},
    "memory_percent": {"yellow": 60.0, "red": 80.0},
    "process_count": {"yellow": 300.0, "red": 400.0},
    "handle_count": {"yellow": 30000.0, "red": 40000.0},
}


def _build_process_buffer(entries: list[dict]) -> ctypes.Array:
    """Build a raw SYSTEM_PROCESS_INFORMATION buffer from a list of entry dicts.

    Each dict may have: name (str), handle_count (int), pid (int).
    """
    record_size = ctypes.sizeof(SYSTEM_PROCESS_INFORMATION)
    total = len(entries) * record_size
    buffer = ctypes.create_string_buffer(total)

    for i, entry in enumerate(entries):
        offset = i * record_size
        proc = SYSTEM_PROCESS_INFORMATION.from_buffer(buffer, offset)
        proc.NumberOfThreads = 1
        proc.HandleCount = entry.get("handle_count", 10)
        proc.UniqueProcessId = entry.get("pid", 1000 + i)
        proc.NextEntryOffset = record_size if i < len(entries) - 1 else 0

        name = entry.get("name", "")
        if name:
            buf_attr = ctypes.create_unicode_buffer(name)
            proc.ImageName.Buffer = buf_attr
            proc.ImageName.Length = len(name) * 2
            proc.ImageName.MaximumLength = (len(name) + 1) * 2
            # Keep reference alive on the proc object to prevent GC
            proc._name_buf = buf_attr

    return buffer


def _make_collector_with_mock_ntquery(buffer: ctypes.Array) -> WindowsCollector:
    """Return a WindowsCollector whose nt_query is mocked to return the given buffer."""
    with patch("ctypes.WinDLL"):
        collector = WindowsCollector(DEFAULT_THRESHOLDS)

    def fake_nt_query(info_class, out_buf, buf_size, ret_len):
        src = (ctypes.c_char * len(buffer)).from_buffer_copy(buffer)
        ctypes.memmove(out_buf, src, min(len(buffer), buf_size))
        if hasattr(ret_len, "contents"):
            ret_len.contents.value = len(buffer)
        return 0

    collector.nt_query = MagicMock(side_effect=fake_nt_query)
    return collector


@pytest.fixture
def mock_windows_collector():
    entries = [
        {"name": "conhost.exe", "handle_count": 50, "pid": 100},
        {"name": "conhost.exe", "handle_count": 50, "pid": 101},
        {"name": "system.exe", "handle_count": 100, "pid": 4},
    ]
    buffer = _build_process_buffer(entries)
    collector = _make_collector_with_mock_ntquery(buffer)
    with patch("psutil.virtual_memory") as mock_vmem:
        mock_vmem.return_value = MagicMock(percent=65.0)
        yield collector


@pytest.fixture
def mocked_ntquery_struct():
    """Fixture identity — setup is embedded in mock_windows_collector."""
    return None


@pytest.fixture
def mocked_ntquery_struct_python():
    entries = [
        {"name": "python.exe", "handle_count": 80, "pid": 200},
        {"name": "system.exe", "handle_count": 100, "pid": 4},
    ]
    buffer = _build_process_buffer(entries)
    with patch("ctypes.WinDLL"):
        collector = WindowsCollector(DEFAULT_THRESHOLDS)

    def fake_nt_query(info_class, out_buf, buf_size, ret_len):
        src = (ctypes.c_char * len(buffer)).from_buffer_copy(buffer)
        ctypes.memmove(out_buf, src, min(len(buffer), buf_size))
        if hasattr(ret_len, "contents"):
            ret_len.contents.value = len(buffer)
        return 0

    collector.nt_query = MagicMock(side_effect=fake_nt_query)
    return collector


def test_req_1(mock_windows_collector, mocked_ntquery_struct):
    with patch("psutil.virtual_memory") as mock_vmem:
        mock_vmem.return_value = MagicMock(percent=65.0)
        snapshot = mock_windows_collector.sweep()
    assert snapshot.conpty_count == 2


def test_req_3(mocked_ntquery_struct_python):
    with patch("psutil.virtual_memory") as mock_vmem, \
         patch("psutil.Process.cmdline", return_value=["python", "unleashed-c-1.py"]):
        mock_vmem.return_value = MagicMock(percent=65.0)
        snapshot = mocked_ntquery_struct_python.sweep()
    assert snapshot.unleashed_sessions == 1


def test_req_4(mock_windows_collector):
    with patch("psutil.virtual_memory") as mock_vmem:
        mock_vmem.return_value = MagicMock(percent=65.0)
        mock_windows_collector.start()
        snapshot = mock_windows_collector.get_queue().get(timeout=3.0)
        mock_windows_collector.stop()
    assert snapshot is not None


def test_req_5(mocked_ntquery_struct_python):
    with patch("psutil.virtual_memory") as mock_vmem, \
         patch("psutil.Process.cmdline", side_effect=psutil.AccessDenied(pid=1234)):
        mock_vmem.return_value = MagicMock(percent=65.0)
        snapshot = mocked_ntquery_struct_python.sweep()
    assert snapshot.unleashed_sessions == 0


def test_req_6(mock_windows_collector):
    real_mock = MagicMock(return_value=0)
    mock_windows_collector.nt_query = real_mock
    with patch("psutil.virtual_memory") as mock_vmem:
        mock_vmem.return_value = MagicMock(percent=65.0)
        mock_windows_collector.sweep()
    assert real_mock.call_count == 1


def test_req_8(mock_windows_collector):
    mock_windows_collector.thresholds = {"memory_percent": {"yellow": 60, "red": 80}}
    comp, driver = mock_windows_collector._compute_composite(0, 80.0, 0, 0)
    assert driver == "memory_percent"
    assert comp == 100.0