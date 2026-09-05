"""Integration tests for WindowsCollector.

Issue #4
"""
import platform

import psutil
import pytest

from boostgauge.collectors.windows import WindowsCollector


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows only")
def test_windows_collector_counts():
    collector = WindowsCollector({})

    matched = False
    for _ in range(3):
        snap = collector.collect()

        p_count = 0
        h_count = 0
        c_count = 0

        for p in psutil.process_iter(['name', 'num_handles']):
            p_count += 1
            try:
                h_count += p.info['num_handles'] or 0
                name = (p.info['name'] or "").lower()
                if name in ("conhost.exe", "openconsole.exe"):
                    c_count += 1
            except Exception:
                pass

        if (abs(snap.process_count - p_count) <= 1 and
                abs(snap.conpty_count - c_count) <= 1 and
                h_count > 0 and abs(snap.handle_count - h_count) / h_count <= 0.01):
            matched = True
            break

    assert matched, "Failed to match process counts within tolerance after 3 attempts"


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows only")
def test_req_3(monkeypatch):
    import collections
    vmem = collections.namedtuple('vmem', ['percent'])
    monkeypatch.setattr("psutil.virtual_memory", lambda: vmem(percent=77.7))
    collector = WindowsCollector({})
    snap = collector.collect()
    assert snap.memory_percent == 77.7


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows only")
def test_req_4(monkeypatch):
    collector = WindowsCollector({})
    monkeypatch.setattr(collector, "_read_cmdline_safe", lambda pid: ["C:\\python.exe", "unleashed-c-123.py"])
    assert collector._is_unleashed_session(12345, "python.exe")


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows only")
def test_req_6(monkeypatch):
    def mock_cmdline(*args):
        raise psutil.AccessDenied()

    monkeypatch.setattr(psutil.Process, "cmdline", mock_cmdline)
    collector = WindowsCollector({})
    assert collector._read_cmdline_safe(0) == []


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows only")
def test_req_7(monkeypatch):
    import ctypes

    calls = []

    def mock_query(*args):
        calls.append(1)
        return 0

    monkeypatch.setattr(ctypes.windll.ntdll, "NtQuerySystemInformation", mock_query)
    collector = WindowsCollector({})
    collector.collect()
    assert len(calls) == 1