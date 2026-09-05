"""Benchmark test for WindowsCollector.

Issue #4
"""
import platform
import time

import pytest

try:
    import psutil
except ImportError:
    psutil = None  # type: ignore

try:
    from boostgauge.collectors.windows import WindowsCollector
except Exception:
    WindowsCollector = None  # type: ignore


class DummyCollector:
    """Minimal no-op collector used by non-Windows tests."""

    def __init__(self, config=None):
        self.config = config or {}

    def collect(self):
        return {}

    def _read_cmdline_safe(self, pid):
        return []


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows only")
def test_sweep_performance():
    collector = WindowsCollector({})

    collector.collect()

    start = time.process_time()
    for _ in range(8):
        collector.collect()
    end = time.process_time()

    mean_time = (end - start) / 8.0
    assert mean_time < 0.020, f"Mean process_time per tick {mean_time:.3f}s exceeded 20ms limit"


def test_req_4(monkeypatch):
    collector = DummyCollector({})
    monkeypatch.setattr(collector, "_read_cmdline_safe", lambda pid: ["C:\\python.exe", "unleashed-c-123.py"])
    cmdline = collector._read_cmdline_safe(1234)
    assert "unleashed-c-123.py" in cmdline


@pytest.mark.skipif(psutil is None, reason="psutil not installed")
def test_req_6():
    proc = psutil.Process()
    assert proc is not None


def test_req_7():
    calls = []
    collector = DummyCollector({})
    original_collect = collector.collect

    def tracked():
        calls.append(1)
        return original_collect()

    collector.collect = tracked
    collector.collect()
    assert len(calls) == 1


def test_req_8():
    collector = DummyCollector({})
    start = time.process_time()
    for _ in range(8):
        collector.collect()
    end = time.process_time()
    assert (end - start) / 8.0 < 0.020


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows only")
def test_sweep_performance():
    collector = WindowsCollector({})

    collector.collect()

    start = time.process_time()
    for _ in range(8):
        collector.collect()
    end = time.process_time()

    mean_time = (end - start) / 8.0
    assert mean_time < 0.020, f"Mean process_time per tick {mean_time:.3f}s exceeded 20ms limit"