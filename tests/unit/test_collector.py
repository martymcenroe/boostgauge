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
    c = WindowsCollector()
    success = False
    for _ in range(3):
        psutil_conpty = sum(
            1 for p in psutil.process_iter(['name'])
            if p.info['name'] and p.info['name'].lower() in ("conhost.exe", "openconsole.exe")
        )
        if abs(c.collect().conpty_count - psutil_conpty) <= 1:
            success = True
            break
    assert success


def test_req_2_processes_and_handles_match(monkeypatch):
    c = WindowsCollector()
    success = False
    for _ in range(3):
        psutil_procs = list(psutil.process_iter(['num_handles']))
        psutil_count = len(psutil_procs)
        psutil_handles = sum(
            p.info['num_handles'] for p in psutil_procs if p.info['num_handles'] is not None
        )
        snap = c.collect()
        if abs(snap.process_count - psutil_count) <= 1:
            if psutil_handles == 0 or abs(snap.handle_count - psutil_handles) / psutil_handles <= 0.01:
                success = True
                break
    assert success


def test_req_3_memory_reads_directly(monkeypatch):
    monkeypatch.setattr("psutil.virtual_memory", lambda: type('obj', (object,), {'percent': 45.5}))
    c = WindowsCollector(sweep=lambda: [])
    assert c.collect().memory_percent == 45.5


def test_req_4_unleashed_session_match():
    c = WindowsCollector(
        sweep=lambda: [ProcessRow(1, "python.exe", 10)],
        cmdline=lambda p: ["python", "C:/unleashed-c-1.py"],
    )
    assert c.collect().unleashed_sessions == 1


def test_req_5_thread_is_non_blocking_and_continues():
    c = unittest.mock.MagicMock()
    t = CollectorThread(c, interval=0.01)
    t.start()
    t.stop()
    assert not t.is_alive()


def test_req_6_cmdline_access_denied_handled(monkeypatch):
    exc = psutil.AccessDenied

    def mock_proc(*args):
        raise exc(1)

    monkeypatch.setattr("psutil.Process", mock_proc)
    assert _psutil_cmdline(1) == []


def test_req_7_single_sweep():
    sweep_mock = unittest.mock.MagicMock(return_value=[])
    cmdline_mock = unittest.mock.MagicMock(return_value=[])
    c = WindowsCollector(sweep=sweep_mock, cmdline=cmdline_mock)
    c.collect()
    assert sweep_mock.call_count == 1


def test_req_8_cpu_benchmark_is_fast():
    import time
    c = WindowsCollector()
    c.collect()
    start = time.process_time()
    for _ in range(8):
        c.collect()
    assert (time.process_time() - start) / 8 < 0.040


def test_req_9_buffer_growth_on_mismatch(monkeypatch):
    mock_ntdll = unittest.mock.MagicMock()
    mock_ntdll.NtQuerySystemInformation.side_effect = [-1073741820, 0]
    c = WindowsCollector(ntdll=mock_ntdll)
    initial_len = len(c._buffer)
    c.nt_sweep()
    assert len(c._buffer) > initial_len


def test_req_10_oserror_fallback(monkeypatch):
    mock_ntdll = unittest.mock.MagicMock()
    mock_ntdll.NtQuerySystemInformation.return_value = -1
    c = WindowsCollector(ntdll=mock_ntdll)
    with pytest.raises(OSError):
        c.nt_sweep()
    mock_ntdll.NtQuerySystemInformation.return_value = -1073741820
    with pytest.raises(OSError):
        c.nt_sweep()


def test_req_11_composite_math_bounds():
    band = Band(10, 20)
    assert normalize(0, band) == 0
    assert normalize(10, band) == 60
    assert normalize(20, band) == 100


def test_req_12_thread_continues_on_error():
    c = unittest.mock.MagicMock()
    c.collect.side_effect = [Exception("mock error"), "success_snapshot"]
    t = CollectorThread(c, interval=0.01)
    t.start()
    item = t.snapshots.get(timeout=1.0)
    t.stop()
    assert item == "success_snapshot"


def test_req_13_mac_linux_raises_notimplemented(monkeypatch):
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
import ctypes
import struct
import unittest.mock

import pytest

from boostgauge.collector import Band, Thresholds, composite, normalize, make_collector
from boostgauge.collector import DataCollector
from boostgauge.collectors.windows import WindowsCollector, _PTR_SIZE


# normalize: yellow == 0, value < red
def test_normalize_yellow_zero_below_red():
    band = Band(yellow=0, red=100.0)
    assert normalize(50.0, band) == 60.0


# normalize: yellow == 0, value >= red
def test_normalize_yellow_zero_at_or_above_red():
    band = Band(yellow=0, red=100.0)
    assert normalize(100.0, band) == 100.0
    assert normalize(200.0, band) == 100.0


# normalize: red == yellow (non-zero), value in [yellow, red)
def test_normalize_red_equals_yellow_returns_100():
    band = Band(yellow=50.0, red=50.0)
    # value < red is impossible when red==yellow, but value == yellow triggers the branch
    # value >= yellow and < red: since red==yellow this is unreachable via <, so hit via ==
    # Actually: value < band.red is False when value==red==yellow, so we fall to return 100.0
    # Let's test value just below: with red==yellow==50, value=49 goes through value<yellow path
    # For the red==yellow branch: value must be >= yellow and < red, impossible if equal
    # The branch at line 62 is inside `if value < band.red`, so value must be < red=50
    # but also >= yellow=50 — impossible. So we need value < red where red != yellow but red == yellow...
    # Re-reading: band.red == band.yellow check is inside `if value < band.red`.
    # With red=yellow=50 and value=49: value < yellow -> hits line 60 path, not 62.
    # Only way to hit line 62: value >= yellow AND value < red AND red == yellow -> impossible.
    # Coverage tool may still mark it; let's just set red slightly above yellow and patch.
    # Instead: construct via a Band where yellow < red but we monkeypatch red==yellow after.
    # Simplest: subclass or use object directly.
    class EqualBand:
        yellow = 50.0
        red = 50.0
    result = normalize(49.9, EqualBand())
    # 49.9 < 50.0 (yellow) -> hits line 60: (49.9/50)*60 = 59.88
    # That doesn't hit line 62. We need value >= yellow=50 AND value < red=50 — impossible.
    # The only way: make yellow < red in the Band but have red==yellow internally be True.
    # Let's just accept and write the test that covers the nearest reachable path.
    # Actually re-reading: if band.red == band.yellow and both are 50, and value=50:
    # value < band.yellow (50<50) is False -> check value < band.red (50<50) is False -> return 100.0
    # So line 62 is unreachable. But coverage says it's uncovered, meaning it IS reachable.
    # Maybe: yellow=50, red=50, value=50 -> line 61: 50<50 False -> line 65: return 100. Skip 62.
    # yellow=50, red=51, value=50 -> line 61: 50<51 True -> line 62: red(51)==yellow(50)? No -> line 64.
    # yellow=50, red=50, value=49 -> line 59: 49<50 True -> line 60: (49/50)*60. Line 62 unreachable.
    # So to hit line 62 we need red==yellow AND value in [yellow, red) — truly impossible.
    # The only path: yellow=X, red=X (equal), value >= X but < X — impossible.
    # Perhaps via float precision: yellow=red=50.0, value=49.999...
    # Let's use a mock object to force the branch:
    band2 = unittest.mock.MagicMock()
    band2.yellow = 40.0
    band2.red = 40.0  # red == yellow
    # value=45: 45 < yellow(40)? No. 45 < red(40)? No. -> return 100.0 (line 65), still misses 62.
    # value=39: 39 < yellow(40)? Yes -> line 60. Still misses 62.
    # Conclusion: need value >= yellow AND value < red AND red == yellow.
    # Make red slightly greater via mock so < check passes but == check also passes:
    class TrickyBand:
        yellow = 50.0
        @property
        def red(self):
            return 50.0
    # 49 < yellow(50) -> line 60. 51 >= yellow, 51 < red(50)? No.
    # There's no normal float that satisfies x >= 50 AND x < 50.
    # The branch is logically dead but coverage tracks it. Skip dedicated test; covered by accident impossible.
    # Let's at least assert the equal-band scenario returns 100 for value above both:
    band3 = Band(yellow=50.0, red=50.0)
    assert normalize(100.0, band3) == 100.0


# composite: thresholds passed as dict
def test_composite_accepts_dict_thresholds():
    thresholds_dict = {
        "conpty": {"yellow": 10.0, "red": 20.0},
        "memory_percent": {"yellow": 50.0, "red": 100.0},
        "process_count": {"yellow": 10.0, "red": 20.0},
        "handle_count": {"yellow": 10.0, "red": 20.0},
    }
    val, driver = composite(5, 75.0, 5, 5, thresholds_dict)
    assert driver == "memory_percent"
    assert val == 80.0


# DataCollector.collect raises NotImplementedError
def test_base_data_collector_collect_raises():
    class ConcreteCollector(DataCollector):
        pass
    c = ConcreteCollector()
    with pytest.raises(NotImplementedError):
        c.collect()


# make_collector on win32 returns WindowsCollector
@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_make_collector_win32_returns_windows_collector():
    c = make_collector()
    assert isinstance(c, WindowsCollector)


# nt_sweep raises when ntdll is None
def test_nt_sweep_raises_when_ntdll_none(monkeypatch):
    monkeypatch.setattr("boostgauge.collectors.windows._nt_query_system_information", lambda: None)
    c = WindowsCollector(ntdll=None)
    c._ntdll = None
    with pytest.raises(OSError, match="not available"):
        c.nt_sweep()


# nt_sweep: 32-bit PTR_SIZE path
@pytest.mark.skipif(_PTR_SIZE != 4, reason="32-bit platform only")
def test_nt_sweep_32bit_pid_extraction():
    c = WindowsCollector()
    rows = c.nt_sweep()
    assert isinstance(rows, list)


# nt_sweep: name decode error is silently swallowed -> name becomes ""
def test_nt_sweep_name_decode_error_gives_empty_name(monkeypatch):
    """Patch ctypes.string_at to raise OSError; the row should still appear with name=''."""
    import boostgauge.collectors.windows as wmod

    mock_ntdll = unittest.mock.MagicMock()

    # Build a minimal valid buffer: one process entry with next_entry_offset=0
    # Offsets from windows.py constants
    from boostgauge.collectors.windows import (
        _OFF_NEXT_ENTRY, _OFF_NAME_LEN, _OFF_NAME_BUF, _OFF_PID,
        _OFF_HANDLE_COUNT, _PTR_SIZE,
    )
    buf_size = 256
    buf = bytearray(buf_size)

    # next_entry_offset = 0 (last entry)
    struct.pack_into("<I", buf, _OFF_NEXT_ENTRY, 0)
    # name_len > 0 so we try to decode
    struct.pack_into("<H", buf, _OFF_NAME_LEN, 10)
    # name_buf_ptr nonzero so we try ctypes.string_at
    if _PTR_SIZE == 8:
        struct.pack_into("<Q", buf, _OFF_NAME_BUF, 0xDEADBEEF)
        struct.pack_into("<Q", buf, _OFF_PID, 999)
        struct.pack_into("<I", buf, _OFF_HANDLE_COUNT, 5)
    else:
        struct.pack_into("<I", buf, _OFF_NAME_BUF, 0xDEADBEEF)
        _off_pid_32 = 64 + 4 + 8
        struct.pack_into("<I", buf, _off_pid_32, 999)
        struct.pack_into("<I", buf, _off_pid_32 + 8, 5)

    raw_buf = ctypes.create_string_buffer(bytes(buf), buf_size)
    mock_ntdll.NtQuerySystemInformation.return_value = 0

    c = WindowsCollector(ntdll=mock_ntdll)
    c._buffer = raw_buf

    with unittest.mock.patch("ctypes.string_at", side_effect=OSError("bad address")):
        rows = c.nt_sweep()

    assert any(r.name == "" for r in rows)


# collect: thresholds set -> composite is called and composite_value populated
def test_collect_with_thresholds_sets_composite(monkeypatch):
    monkeypatch.setattr("psutil.virtual_memory", lambda: type("V", (), {"percent": 0.0})())
    thresholds = Thresholds(Band(10, 20), Band(50, 100), Band(10, 20), Band(10, 20))
    c = WindowsCollector(sweep=lambda: [], thresholds=thresholds)
    snap = c.collect()
    assert snap.composite_value == 0.0
    assert snap.driver == "conpty"
