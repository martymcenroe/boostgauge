from __future__ import annotations

import time

import pytest

try:
    from boostgauge.collectors.windows import WindowsCollector
except Exception:  # ImportError on non-Windows, or missing ctypes symbols
    WindowsCollector = None  # type: ignore[assignment,misc]

CPU_BUDGET_PER_TICK_S = 0.040


@pytest.mark.skipif(
    __import__("sys").platform != "win32",
    reason="Windows-only: NtQuerySystemInformation not available",
)
def test_full_collect_tick_is_under_one_percent_of_a_core():
    c = WindowsCollector()
    c.collect()
    start = time.process_time()
    for _ in range(8):
        c.collect()
    mean = (time.process_time() - start) / 8
    assert mean < CPU_BUDGET_PER_TICK_S