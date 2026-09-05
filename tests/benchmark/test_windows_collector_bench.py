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