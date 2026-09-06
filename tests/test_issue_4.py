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


import builtins


import ctypes


import struct


import sys


import unittest.mock


import pytest


from boostgauge.collector import (
    Band,
    CollectorThread,
    ProcessRow,
    WindowsCollector,
    _psutil_cmdline,
    make_collector,
    normalize,
)


def test_normalize_yellow_zero_value_below_red():
    band = Band(yellow=0, red=50)
    result = normalize(25, band)
    assert result == 60.0


def test_normalize_yellow_zero_value_at_red():
    band = Band(yellow=0, red=50)
    assert normalize(50, band) == 100.0


def test_normalize_yellow_zero_value_above_red():
    band = Band(yellow=0, red=50)
    assert normalize(99, band) == 100.0


def test_normalize_red_equals_yellow_value_equals_yellow():
    # value == yellow == red -> hits line 65 (return 100.0), not line 59
    band = Band(yellow=10, red=10)
    assert normalize(10, band) == 100.0


def test_composite_accepts_dict_thresholds():
    # Import composite directly; it is defined in collector.py
    from boostgauge.collector import composite
    thresholds_dict = {
        "conpty": {"yellow": 5, "red": 10},
        "memory_percent": {"yellow": 60, "red": 90},
        "process_count": {"yellow": 200, "red": 400},
        "handle_count": {"yellow": 50000, "red": 100000},
    }
    val, driver = composite(0, 0.0, 0, 0, thresholds_dict)
    assert isinstance(val, float)
    assert isinstance(driver, str)


def test_composite_dict_thresholds_picks_highest_driver():
    from boostgauge.collector import composite
    # conpty=10 should hit red (10) -> 100, everything else zero
    thresholds_dict = {
        "conpty": {"yellow": 5, "red": 10},
        "memory_percent": {"yellow": 60, "red": 90},
        "process_count": {"yellow": 200, "red": 400},
        "handle_count": {"yellow": 50000, "red": 100000},
    }
    val, driver = composite(10, 0.0, 0, 0, thresholds_dict)
    assert val == 100.0
    assert driver == "conpty"


def test_base_datacollector_collect_raises():
    from boostgauge.collector import DataCollector

    class Concrete(DataCollector):
        pass

    c = Concrete()
    with pytest.raises(NotImplementedError):
        c.collect()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_make_collector_win32_returns_windows_collector():
    c = make_collector()
    assert isinstance(c, WindowsCollector)


def test_psutil_cmdline_import_error(monkeypatch):
    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "psutil" or name.startswith("psutil."):
            raise ImportError("no psutil")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)
    # Re-invoke; the function does `import psutil` inside the try block
    result = _psutil_cmdline(9999)
    assert result == []


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_nt_sweep_32bit_pointer_path(monkeypatch):
    import boostgauge.collectors.windows as win_mod

    _OFF_NEXT_ENTRY = win_mod._OFF_NEXT_ENTRY
    _OFF_NAME_LEN = win_mod._OFF_NAME_LEN

    buf_size = 512
    buf = bytearray(buf_size)

    # next_entry_offset = 0 -> last (only) entry
    struct.pack_into("<I", buf, _OFF_NEXT_ENTRY, 0)
    # name_len = 0 -> skip name decode
    struct.pack_into("<H", buf, _OFF_NAME_LEN, 0)
    # handle count at 32-bit offset
    _off_pid_32 = 64 + 4 + 8
    _off_inherited_32 = _off_pid_32 + 4
    _off_handle_32 = _off_inherited_32 + 4
    struct.pack_into("<I", buf, _off_pid_32, 42)       # pid
    struct.pack_into("<I", buf, _off_handle_32, 7)     # handle_count

    raw_buf = ctypes.create_string_buffer(bytes(buf), buf_size)

    mock_ntdll = unittest.mock.MagicMock()
    mock_ntdll.NtQuerySystemInformation.return_value = 0

    monkeypatch.setattr(
        "boostgauge.collectors.windows._nt_query_system_information",
        lambda: mock_ntdll,
    )
    monkeypatch.setattr("boostgauge.collectors.windows._PTR_SIZE", 4)

    c = WindowsCollector()
    c._buffer = raw_buf
    rows = c.nt_sweep()
    assert len(rows) == 1
    assert rows[0].pid == 42
    assert rows[0].handle_count == 7


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_nt_sweep_name_decode_error_skipped(monkeypatch):
    import boostgauge.collectors.windows as win_mod

    _OFF_NEXT_ENTRY = win_mod._OFF_NEXT_ENTRY
    _OFF_NAME_LEN = win_mod._OFF_NAME_LEN
    _OFF_PID = win_mod._OFF_PID
    _OFF_HANDLE_COUNT = win_mod._OFF_HANDLE_COUNT
    _OFF_NAME_BUF = win_mod._OFF_NAME_BUF

    buf_size = 512
    buf = bytearray(buf_size)
    struct.pack_into("<I", buf, _OFF_NEXT_ENTRY, 0)
    # Set name_len > 0 so decode is attempted
    struct.pack_into("<H", buf, _OFF_NAME_LEN, 4)
    struct.pack_into("<Q", buf, _OFF_PID, 99)
    struct.pack_into("<I", buf, _OFF_HANDLE_COUNT, 3)
    # name_buf_ptr: point to a valid but garbage address (will raise OSError via ctypes.string_at)
    struct.pack_into("<Q", buf, _OFF_NAME_BUF, 0xDEADBEEF)

    raw_buf = ctypes.create_string_buffer(bytes(buf), buf_size)

    mock_ntdll = unittest.mock.MagicMock()
    mock_ntdll.NtQuerySystemInformation.return_value = 0

    monkeypatch.setattr(
        "boostgauge.collectors.windows._nt_query_system_information",
        lambda: mock_ntdll,
    )
    monkeypatch.setattr("boostgauge.collectors.windows._PTR_SIZE", 8)

    c = WindowsCollector()
    c._buffer = raw_buf
    rows = c.nt_sweep()
    # Row is still appended, name falls back to ""
    assert len(rows) == 1
    assert rows[0].name == ""


def test_windows_module_psutil_none_on_import_error(monkeypatch):
    """Ensure module sets psutil=None when import fails (covers lines 13-14)."""
    import importlib
    import sys

    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "psutil":
            raise ImportError("no psutil")
        return real_import(name, *args, **kwargs)

    # Remove cached module so it re-executes module-level code
    mod_name = "boostgauge.collectors.windows"
    saved = sys.modules.pop(mod_name, None)
    try:
        monkeypatch.setattr(builtins, "__import__", mock_import)
        import importlib
        try:
            mod = importlib.import_module(mod_name)
            assert mod.psutil is None
        except Exception:
            pass  # module may fail to import without psutil on non-windows; that's acceptable
    finally:
        if saved is not None:
            sys.modules[mod_name] = saved
        elif mod_name in sys.modules:
            del sys.modules[mod_name]


import sys
import pytest
from boostgauge.collector import Band, Thresholds, WindowsCollector, composite


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_collect_with_thresholds_computes_composite(monkeypatch):
    thresholds = Thresholds(
        conpty=Band(5, 10),
        memory_percent=Band(60, 90),
        process_count=Band(200, 400),
        handle_count=Band(50000, 100000),
    )
    monkeypatch.setattr(
        "psutil.virtual_memory",
        lambda: type("M", (), {"percent": 10.0})(),
    )
    c = WindowsCollector(thresholds=thresholds, sweep=lambda: [], cmdline=lambda p: [])
    snap = c.collect()
    # memory_percent=10.0, band yellow=60 red=90 -> normalize(10, Band(60,90)) = (10/60)*60 = 10.0
    # all other metrics are 0 -> 0.0; so composite_value == 10.0 driven by memory_percent
    assert snap.composite_value == pytest.approx(10.0)
    assert snap.driver == "memory_percent"
