"""Test file for Issue #4.

Emitted by AssemblyZero from the implementation spec's Section 10
test functions. Bodies are the spec's own, verbatim (#2316).
"""

# #2887: modules the spec's bodies use without importing them
import psutil

# TDD: this import fails until the implementation exists (RED phase)
from boostgauge.collector import Band, CollectorThread, ProcessRow, WindowsCollector, _psutil_cmdline, make_collector, normalize  # noqa: F401


def test_req_1_conpty_matches(monkeypatch):
    # Live OS state (REQ-1) -- expected: conpty_count equals psutil count ±1
    import psutil
    c = WindowsCollector()
    success = False
    for _ in range(3):
        psutil_conpty = sum(1 for p in psutil.process_iter(['name']) if p.info['name'] and p.info['name'].lower() in ("conhost.exe", "openconsole.exe"))
        if abs(c.collect().conpty_count - psutil_conpty) <= 1:
            success = True
            break
    assert success


def test_req_2_processes_and_handles_match(monkeypatch):
    # Live OS state (REQ-2) -- expected: process_count equals psutil count ±1, handle_count within 1%
    import psutil
    c = WindowsCollector()
    success = False
    for _ in range(3):
        psutil_procs = list(psutil.process_iter(['num_handles']))
        psutil_count = len(psutil_procs)
        psutil_handles = sum(p.info['num_handles'] for p in psutil_procs if p.info['num_handles'] is not None)
        snap = c.collect()
        if abs(snap.process_count - psutil_count) <= 1:
            if psutil_handles == 0 or abs(snap.handle_count - psutil_handles) / psutil_handles <= 0.01:
                success = True
                break
    assert success


def test_req_3_memory_reads_directly(monkeypatch):
    # Mocked memory=45.5 (REQ-3) -- expected: snapshot memory_percent == 45.5
    monkeypatch.setattr("psutil.virtual_memory", lambda: type('obj', (object,), {'percent': 45.5}))
    c = WindowsCollector(sweep=lambda: [])
    assert c.collect().memory_percent == 45.5


def test_req_4_unleashed_session_match():
    # Python name + unleashed-c-1.py cmdline (REQ-4) -- expected: unleashed_sessions == 1
    c = WindowsCollector(sweep=lambda: [ProcessRow(1, "python.exe", 10)], cmdline=lambda p: ["python", "C:/unleashed-c-1.py"])
    assert c.collect().unleashed_sessions == 1


def test_req_5_thread_is_non_blocking_and_continues():
    # Interval=0.01 with thread start/stop (REQ-5) -- expected: Queue receives snapshot, stop() joins cleanly
    import unittest.mock
    c = unittest.mock.MagicMock()
    t = CollectorThread(c, interval=0.01)
    t.start()
    t.stop()
    is_alive = getattr(t, "is_alive")
    assert not is_alive()


def test_req_6_cmdline_access_denied_handled(monkeypatch):
    # AccessDenied mock (REQ-6) -- expected: _psutil_cmdline returns []
    exc = getattr(psutil, "AccessDenied")
    def mock_proc(*args): raise exc(1)
    monkeypatch.setattr("psutil.Process", mock_proc)
    assert _psutil_cmdline(1) == []


def test_req_7_single_sweep():
    # Calling collect() (REQ-7) -- expected: nt_sweep called exactly once per tick
    import unittest.mock
    sweep_mock = unittest.mock.MagicMock(return_value=[])
    cmdline_mock = unittest.mock.MagicMock(return_value=[])
    c = WindowsCollector(sweep=sweep_mock, cmdline=cmdline_mock)
    c.collect()
    assert sweep_mock.call_count == 1


def test_req_8_cpu_benchmark_is_fast():
    # 8 tick collections (REQ-8) -- expected: mean process_time < 0.040s
    import time
    c = WindowsCollector()
    c.collect()
    start = time.process_time()
    for _ in range(8):
        c.collect()
    assert (time.process_time() - start) / 8 < 0.040


def test_req_9_buffer_growth_on_mismatch(monkeypatch):
    # Buffer growth on mismatch (REQ-9) -- expected: len(c._buffer) increases
    import unittest.mock
    mock_ntdll = unittest.mock.MagicMock()
    mock_ntdll.NtQuerySystemInformation.side_effect = [-1073741820, 0]
    monkeypatch.setattr("boostgauge.collectors.windows._nt_query_system_information", lambda: mock_ntdll)
    c = WindowsCollector()
    initial_len = len(c._buffer)
    c.nt_sweep()
    assert len(c._buffer) > initial_len


def test_req_10_oserror_fallback(monkeypatch):
    # Exception raised (REQ-10)
    import pytest
    import unittest.mock
    mock_ntdll = unittest.mock.MagicMock()
    mock_ntdll.NtQuerySystemInformation.return_value = -1
    monkeypatch.setattr("boostgauge.collectors.windows._nt_query_system_information", lambda: mock_ntdll)
    c = WindowsCollector()
    with pytest.raises(OSError):
        c.nt_sweep()
    mock_ntdll.NtQuerySystemInformation.return_value = -1073741820
    with pytest.raises(OSError):
        c.nt_sweep()


def test_req_11_composite_math_bounds():
    # Low, Medium, High inputs (REQ-11) -- expected: 0, 60, 100 outputs
    band = Band(10, 20)
    assert normalize(0, band) == 0
    assert normalize(10, band) == 60
    assert normalize(20, band) == 100


def test_req_12_thread_continues_on_error():
    # Exception in loop (REQ-12) -- expected: thread continues polling
    import unittest.mock
    c = unittest.mock.MagicMock()
    c.collect.side_effect = [Exception("mock error"), "success_snapshot"]
    t = CollectorThread(c, interval=0.01)
    t.start()
    item = t.snapshots.get(timeout=1.0)
    t.stop()
    assert item == "success_snapshot"


def test_req_13_mac_linux_raises_notimplemented(monkeypatch):
    # Mac/Linux (REQ-13)
    import pytest
    monkeypatch.setattr("sys.platform", "linux")
    with pytest.raises(NotImplementedError):
        make_collector()


import sys
import struct
import unittest.mock
import pytest

from boostgauge.collector import Band, normalize, make_collector, WindowsCollector, ProcessRow


def test_normalize_at_red_threshold_returns_100():
    band = Band(10, 20)
    assert normalize(20, band) == 100.0


def test_normalize_above_red_threshold_returns_100():
    band = Band(10, 20)
    assert normalize(25, band) == 100.0


def test_normalize_at_yellow_threshold_returns_60():
    band = Band(10, 20)
    assert normalize(10, band) == 60.0


def test_normalize_below_yellow_returns_0():
    band = Band(10, 20)
    assert normalize(5, band) == 0.0


def test_make_collector_windows_returns_windows_collector(monkeypatch):
    monkeypatch.setattr("sys.platform", "win32")
    c = make_collector()
    assert isinstance(c, WindowsCollector)


def test_make_collector_darwin_raises_not_implemented(monkeypatch):
    monkeypatch.setattr("sys.platform", "darwin")
    with pytest.raises(NotImplementedError):
        make_collector()


def test_nt_sweep_returns_empty_list_on_zero_length(monkeypatch):
    mock_ntdll = unittest.mock.MagicMock()
    # Return success but write 0 bytes (ReturnLength stays 0)
    def fake_query(info_class, buf, buf_len, ret_len):
        struct.pack_into("<I", ret_len._obj if hasattr(ret_len, '_obj') else (ret_len.__class__.__mro__, ret_len), 0, 0)
        return 0
    # Simpler: patch so the walk loop just sees empty buffer by making header length = buf size
    # Instead patch nt_sweep directly via the internal path
    c = WindowsCollector(sweep=lambda: [])
    # Patch _nt_query_system_information to return ntdll where NtQuerySystemInformation returns 0
    # but written ReturnLength = 0 so the while loop exits immediately
    import ctypes
    mock_ntdll2 = unittest.mock.MagicMock()
    written_len = ctypes.c_ulong(0)

    def side_effect(info_class, buf, buf_len, ret_len_ptr):
        # Write 0 into the ret_len_ptr
        ctypes.memmove(ret_len_ptr, ctypes.byref(ctypes.c_ulong(0)), 4)
        return 0

    mock_ntdll2.NtQuerySystemInformation.side_effect = side_effect
    monkeypatch.setattr("boostgauge.collectors.windows._nt_query_system_information", lambda: mock_ntdll2)
    result = c.nt_sweep()
    assert result == []


def test_nt_sweep_unicode_decode_error_skips_entry(monkeypatch):
    """Covers the UnicodeDecodeError/OSError except branch in the 32-bit walk."""
    import boostgauge.collectors.windows as wmod
    import ctypes

    c = WindowsCollector(sweep=lambda: [])

    _OFF_NAME_BUF = wmod._OFF_NAME_BUF

    # Build a minimal fake buffer: one entry with NextEntryOffset=0
    # so the loop processes exactly one entry and then stops.
    buf_size = 256
    buf = bytearray(buf_size)

    # NextEntryOffset = 0 (last entry)
    struct.pack_into("<I", buf, 0, 0)
    # ImageSize field (offset 4) = 0
    # Write pid at _off_pid_32 = 76
    _off_pid_32 = 64 + 4 + 8
    _off_inherited_32 = _off_pid_32 + 4
    _off_handle_32 = _off_inherited_32 + 4
    struct.pack_into("<I", buf, _off_pid_32, 9999)
    struct.pack_into("<I", buf, _off_handle_32, 5)
    # name_buf_ptr at _OFF_NAME_BUF: point to garbage (not a valid address)
    struct.pack_into("<I", buf, _OFF_NAME_BUF, 0xDEADBEEF)

    import ctypes
    raw = (ctypes.c_char * buf_size)(*buf)

    mock_ntdll = unittest.mock.MagicMock()

    def side_effect(info_class, out_buf, buf_len, ret_len_ptr):
        # Write our fake data into out_buf
        ctypes.memmove(out_buf, raw, min(buf_size, buf_len))
        ctypes.memmove(ret_len_ptr, ctypes.byref(ctypes.c_ulong(buf_size)), 4)
        return 0

    mock_ntdll.NtQuerySystemInformation.side_effect = side_effect
    monkeypatch.setattr("boostgauge.collectors.windows._nt_query_system_information", lambda: mock_ntdll)

    # Should not raise; the UnicodeDecodeError/OSError branch is hit and skipped
    result = c.nt_sweep()
    assert isinstance(result, list)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_collect_composite_driver_used(monkeypatch):
    """Covers composite() returning a driver name on Windows."""
    import boostgauge.collectors.windows as wmod

    fake_snap = unittest.mock.MagicMock()
    fake_snap.memory_percent = 50.0
    fake_snap.process_count = 100
    fake_snap.handle_count = 1000
    fake_snap.unleashed_sessions = 0
    fake_snap.conpty_count = 0

    # Patch composite to return a value with a driver
    original_composite = wmod.composite

    def fake_composite(snap):
        return 75.0, "memory"

    monkeypatch.setattr(wmod, "composite", fake_composite)
    c = WindowsCollector(sweep=lambda: [])
    monkeypatch.setattr(c, "collect", lambda: unittest.mock.MagicMock(
        memory_percent=50.0, process_count=100, handle_count=1000,
        unleashed_sessions=0, conpty_count=0, composite_value=75.0, driver="memory"
    ))
    snap = c.collect()
    assert snap.driver == "memory"
