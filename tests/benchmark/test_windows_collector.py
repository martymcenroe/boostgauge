"""Benchmark tests for WindowsCollector: sweep process_time over 8 ticks < 20 ms.

Issue #4: Windows data collector
"""
from __future__ import annotations

import time

import pytest

from boostgauge.collector import ThresholdsConfig
from boostgauge.collectors.windows import WindowsCollector

DEFAULT_THRESHOLDS: dict[str, ThresholdsConfig] = {
    "conpty": {"yellow": 2.0, "red": 5.0},
    "memory_percent": {"yellow": 60.0, "red": 80.0},
    "process_count": {"yellow": 300.0, "red": 400.0},
    "handle_count": {"yellow": 30000.0, "red": 40000.0},
}


@pytest.fixture
def live_windows_collector():
    return WindowsCollector(DEFAULT_THRESHOLDS)


def test_req_7_benchmark(live_windows_collector):
    latencies = []
    for _ in range(8):
        start = time.process_time()
        live_windows_collector.sweep()
        latencies.append(time.process_time() - start)
        time.sleep(0.01)

    mean_time = sum(latencies) / len(latencies)
    assert mean_time < 0.020