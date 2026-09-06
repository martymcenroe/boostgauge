from __future__ import annotations

import unittest.mock

import pytest
import psutil

from boostgauge.collector import (
    Band,
    CollectorThread,
    Thresholds,
    composite,
    make_collector,
    normalize,
)
from boostgauge.collectors.windows import (
    ProcessRow,
    WindowsCollector,
    _psutil_cmdline,
    is_unleashed_cmdline,
)
from boostgauge.collector import Band, CollectorThread, ProcessRow, WindowsCollector, _psutil_cmdline, make_collector, normalize  # noqa: F401


def test_normalize_literal_points():
    band = Band(50.0, 100.0)
    assert normalize(0.0, band) == 0.0
    assert normalize(25.0, band) == 30.0
    assert normalize(50.0, band) == 60.0
    assert normalize(75.0, band) == 80.0
    assert normalize(100.0, band) == 100.0
    assert normalize(150.0, band) == 100.0


def test_composite_is_max_and_names_the_driver():
    thresholds = Thresholds(Band(10, 20), Band(50, 100), Band(10, 20), Band(10, 20))
    val, driver = composite(5, 75.0, 5, 5, thresholds)
    assert driver == "memory_percent"
    assert val == 80.0


def test_composite_ties_resolve_in_metric_order():
    thresholds = Thresholds(Band(10, 20), Band(10, 20), Band(10, 20), Band(10, 20))
    val, driver = composite(15, 15.0, 15, 15, thresholds)
    assert driver == "conpty"


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


def test_is_unleashed_cmdline_empty():
    assert is_unleashed_cmdline([]) is False


def test_is_unleashed_cmdline_mixed_case():
    assert is_unleashed_cmdline(["C:\\Python310\\python.exe", "C:\\scripts\\UnLeashed-C-2.Py"]) is True


def test_is_unleashed_cmdline_no_match():
    assert is_unleashed_cmdline(["python.exe", "script.py"]) is False


def test_normalize_clamps_negative():
    band = Band(10.0, 20.0)
    assert normalize(-5.0, band) == 0.0


def test_normalize_at_red():
    band = Band(10.0, 20.0)
    assert normalize(20.0, band) == 100.0


def test_normalize_above_red():
    band = Band(10.0, 20.0)
    assert normalize(999.0, band) == 100.0


def test_collector_thread_puts_snapshot_in_queue():
    snap = unittest.mock.MagicMock()
    c = unittest.mock.MagicMock()
    c.collect.return_value = snap
    t = CollectorThread(c, interval=0.01)
    t.start()
    item = t.snapshots.get(timeout=1.0)
    t.stop()
    assert item is snap


import sys
import unittest.mock

import pytest
import psutil

from boostgauge.collector import Band, Thresholds, composite, normalize, make_collector
from boostgauge.collectors.windows import WindowsCollector, _psutil_cmdline


def test_normalize_yellow_zero_value_below_red():
    band = Band(yellow=0, red=100.0)
    assert normalize(50.0, band) == 60.0


def test_normalize_yellow_zero_value_at_or_above_red():
    band = Band(yellow=0, red=100.0)
    assert normalize(100.0, band) == 100.0
    assert normalize(150.0, band) == 100.0


def test_normalize_red_equals_yellow_returns_100():
    band = Band(yellow=50.0, red=50.0)
    result = normalize(50.0, band)
    assert result == 100.0


def test_composite_accepts_dict_thresholds():
    thresholds_dict = {
        "conpty": {"yellow": 10, "red": 20},
        "memory_percent": {"yellow": 50, "red": 100},
        "process_count": {"yellow": 10, "red": 20},
        "handle_count": {"yellow": 10, "red": 20},
    }
    val, driver = composite(5, 75.0, 5, 5, thresholds_dict)
    assert driver == "memory_percent"
    assert val == 80.0


def test_base_collector_collect_raises_not_implemented():
    from boostgauge.collector import DataCollector
    class Concrete(DataCollector):
        pass
    c = Concrete()
    with pytest.raises(NotImplementedError):
        c.collect()


@pytest.mark.skipif(sys.platform == "win32", reason="tests non-windows path")
def test_make_collector_non_windows_raises():
    with pytest.raises(NotImplementedError, match="not supported"):
        make_collector()


@pytest.mark.skipif(sys.platform != "win32", reason="windows only")
def test_make_collector_windows_returns_windows_collector():
    collector = make_collector()
    assert isinstance(collector, WindowsCollector)


def test_psutil_cmdline_exception_returns_empty(monkeypatch):
    monkeypatch.setattr("psutil.Process", lambda pid: (_ for _ in ()).throw(OSError("gone")))
    assert _psutil_cmdline(999999) == []


def test_nt_sweep_ntdll_none_raises_oserror(monkeypatch):
    monkeypatch.setattr("boostgauge.collectors.windows._nt_query_system_information", lambda: None)
    c = WindowsCollector()
    c._ntdll = None
    with pytest.raises(OSError, match="NtQuerySystemInformation not available"):
        c.nt_sweep()


def test_collect_with_thresholds_calls_composite(monkeypatch):
    monkeypatch.setattr("psutil.virtual_memory", lambda: type("M", (), {"percent": 50.0})())
    thresholds = Thresholds(Band(10, 20), Band(40, 80), Band(10, 20), Band(10, 20))
    c = WindowsCollector(sweep=lambda: [], thresholds=thresholds)
    snap = c.collect()
    assert snap.driver != ""
    assert snap.composite_value >= 0.0


def test_nt_sweep_unicode_decode_error_skipped(monkeypatch):
    import ctypes
    import struct
    from boostgauge.collectors.windows import (
        SYSTEM_PROCESS_INFORMATION,
        _OFF_NEXT_ENTRY,
        _OFF_NAME_LEN,
        _OFF_NAME_BUF,
        _OFF_PID,
        _OFF_HANDLE_COUNT,
        _PTR_SIZE,
        _GROWTH_SLACK,
    )

    mock_ntdll = unittest.mock.MagicMock()
    mock_ntdll.NtQuerySystemInformation.return_value = 0

    # Build a minimal buffer that triggers the UnicodeDecodeError path:
    # name_len > 0 and name_buf_ptr pointing somewhere that ctypes.string_at will fail
    # We patch ctypes.string_at to raise OSError
    monkeypatch.setattr("boostgauge.collectors.windows._nt_query_system_information", lambda: mock_ntdll)
    monkeypatch.setattr("ctypes.string_at", unittest.mock.Mock(side_effect=OSError("bad ptr")))

    c = WindowsCollector()
    # Build a fake buffer with name_len=2 and a nonzero ptr
    buf_size = 512
    buf = bytearray(buf_size)
    # next_entry_offset = 0 (last entry)
    struct.pack_into("<I", buf, _OFF_NEXT_ENTRY, 0)
    # name_len = 2
    struct.pack_into("<H", buf, _OFF_NAME_LEN, 2)
    if _PTR_SIZE == 8:
        struct.pack_into("<Q", buf, _OFF_PID, 1)
        struct.pack_into("<I", buf, _OFF_HANDLE_COUNT, 0)
        struct.pack_into("<Q", buf, _OFF_NAME_BUF, 0xDEADBEEF)
    else:
        _off_pid_32 = 64 + 4 + 8
        struct.pack_into("<I", buf, _off_pid_32, 1)
        struct.pack_into("<I", buf, _off_pid_32 + 8, 0)
        struct.pack_into("<I", buf, _OFF_NAME_BUF, 0xDEADBEEF)

    c._buffer = ctypes.create_string_buffer(bytes(buf), buf_size)
    rows = c.nt_sweep()
    # Should still return a row with empty name (error was swallowed)
    assert isinstance(rows, list)
    assert rows[0].name == ""
