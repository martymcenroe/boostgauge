from __future__ import annotations

import time

import pytest

CPU_BUDGET_PER_TICK_S = 0.040


@pytest.mark.skipif(
    __import__("sys").platform != "win32",
    reason="Windows-only: NtQuerySystemInformation not available",
)
def test_full_collect_tick_is_under_one_percent_of_a_core():
    from boostgauge.collectors.windows import WindowsCollector  # noqa: PLC0415
    c = WindowsCollector()
    c.collect()
    start = time.process_time()
    for _ in range(8):
        c.collect()
    mean = (time.process_time() - start) / 8
    assert mean < CPU_BUDGET_PER_TICK_S