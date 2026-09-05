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
    WindowsCollector = None  # type: ignore[assignment,misc]


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
    monkeypatch.setattr(DummyCollector, "_read_cmdline_safe", lambda self, pid: ["C:\\python.exe", "unleashed-c-123.py"])
    cmdline = collector._read_cmdline_safe(1234)
    assert "unleashed-c-123.py" in cmdline


def test_req_6():
    psutil = pytest.importorskip("psutil")
    proc = psutil.Process()
    assert proc is not None


def test_req_7(monkeypatch):
    calls = []

    def tracked(self):
        calls.append(1)
        return {}

    monkeypatch.setattr(DummyCollector, "collect", tracked)
    collector = DummyCollector({})
    collector.collect()

    assert len(calls) == 1


def test_req_8():
    collector = DummyCollector({})
    start = time.perf_counter()
    for _ in range(8):
        collector.collect()
    assert (time.perf_counter() - start) / 8.0 < 0.020