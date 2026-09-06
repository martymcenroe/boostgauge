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
    monkeypatch.setattr(
        "boostgauge.collectors.windows._nt_query_system_information", lambda: mock_ntdll
    )
    c = WindowsCollector()
    initial_len = len(c._buffer)
    c.nt_sweep()
    assert len(c._buffer) > initial_len


def test_req_10_oserror_fallback(monkeypatch):
    mock_ntdll = unittest.mock.MagicMock()
    mock_ntdll.NtQuerySystemInformation.return_value = -1
    monkeypatch.setattr(
        "boostgauge.collectors.windows._nt_query_system_information", lambda: mock_ntdll
    )
    c = WindowsCollector()
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