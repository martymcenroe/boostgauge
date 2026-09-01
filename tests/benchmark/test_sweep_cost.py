"""ADR 0001 §4 hook 4: the `< 1% CPU at 2 s` criterion as a number a test can fail on.

1 % of one core over a 2 s tick is 20 ms of CPU per tick. The sweep's mean
`process_time` over eight ticks (the first discarded as warm-up) must be under
that. Measured 2.2 ms on the operator's machine (#405); the psutil sweep this
replaced measured 422 ms and would fail here by 21x.
"""

from __future__ import annotations

import sys
import time

import pytest

from boostgauge.collectors.windows import WindowsCollector

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows sweep")

CPU_BUDGET_PER_TICK_S = 0.020   # 1 % of a core at a 2 s tick
TICKS = 8


def test_full_collect_tick_is_under_one_percent_of_a_core():
    collector = WindowsCollector()
    cpu = []
    for _ in range(TICKS):
        c0 = time.process_time()
        collector.collect()          # the whole tick: sweep + per-row cmdline + memory
        cpu.append(time.process_time() - c0)
        time.sleep(0.05)
    steady = cpu[1:]
    mean = sum(steady) / len(steady)
    assert mean < CPU_BUDGET_PER_TICK_S, (
        f"mean {mean * 1000:.1f} ms per tick over {len(steady)} ticks "
        f"= {mean / 2.0 * 100:.2f}% of a core at 2 s; budget {CPU_BUDGET_PER_TICK_S * 1000:.0f} ms")
