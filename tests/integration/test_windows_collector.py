"""Integration tests for WindowsCollector.

Issue #4
"""
import collections
import platform

import psutil
import pytest

from boostgauge.collectors.windows import WindowsCollector


class DummyCollector:
    """Stub collector for cross-platform unit tests (no Windows APIs called)."""

    def __init__(self, config):
        if not isinstance(config, dict):
            raise ValueError("config must be a dict")
        self.config = config


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
    vmem = collections.namedtuple('vmem', ['percent'])
    monkeypatch.setattr("psutil.virtual_memory", lambda: vmem(percent=77.7))
    collector = WindowsCollector({})
    snap = collector.collect()
    assert snap.memory_percent == 77.7


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows only")
def test_req_4(monkeypatch):
    collector = WindowsCollector({})
    monkeypatch.setattr(collector, "_read_cmdline_safe", lambda pid: ["C:\\python.exe", "unleashed-c-123.py"], raising=False)
    assert collector._is_unleashed_session("python.exe", 12345)


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows only")
def test_req_6(monkeypatch):
    import psutil as _psutil
    def mock_cmdline(*args):
        raise _psutil.AccessDenied(pid=0)
    monkeypatch.setattr(_psutil.Process, "cmdline", mock_cmdline)
    collector = WindowsCollector({})
    assert collector._read_cmdline_safe(0) == []


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows only")
def test_req_7(monkeypatch):
    import boostgauge.collectors.windows as _wmod
    calls = []

    def mock_query(*args):
        calls.append(1)
        return 0

    monkeypatch.setattr(_wmod, "NtQuerySystemInformation", mock_query, raising=False)
    collector = WindowsCollector({})
    collector.collect()
    assert len(calls) >= 1


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows only")
def test_snapshot_fields():
    collector = WindowsCollector({})
    snap = collector.collect()
    assert snap.timestamp > 0
    assert snap.process_count >= 0
    assert snap.handle_count >= 0
    assert snap.conpty_count >= 0
    assert snap.unleashed_sessions >= 0
    assert 0.0 <= snap.memory_percent <= 100.0


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows only")
@pytest.mark.skipif(platform.system() != "Windows", reason="Windows only")
def test_req_8(monkeypatch):
    import time
    import collections
    vmem = collections.namedtuple('vmem', ['percent'])
    monkeypatch.setattr("psutil.virtual_memory", lambda: vmem(percent=50.0))
    monkeypatch.setattr("psutil.process_iter", lambda *args, **kwargs: iter([]))
    import boostgauge.collectors.windows as _wmod
    monkeypatch.setattr(_wmod, "NtQuerySystemInformation", lambda *a: 0, raising=False)
    collector = WindowsCollector({})
    start = time.process_time()
    for _ in range(8):
        collector.collect()
    assert (time.process_time() - start) / 8.0 < 0.020


def test_no_such_process_cmdline(monkeypatch):
    def mock_cmdline(*args):
        raise psutil.NoSuchProcess(pid=0)
    monkeypatch.setattr(psutil.Process, "cmdline", mock_cmdline)
    collector = WindowsCollector({})
    assert collector._read_cmdline_safe(99999) == []


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows only")
def test_not_unleashed_non_python():
    collector = WindowsCollector({})
    assert not collector._is_unleashed_session("notepad.exe", 12345)


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows only")
def test_not_unleashed_python_wrong_cmdline(monkeypatch):
    collector = WindowsCollector({})
    monkeypatch.setattr(collector, "_read_cmdline_safe", lambda pid: ["C:\\python.exe", "other_script.py"])
    assert not collector._is_unleashed_session("python.exe", 12345)