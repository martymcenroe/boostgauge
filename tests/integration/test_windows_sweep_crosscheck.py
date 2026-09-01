"""ADR 0001 §4 hook 3: the one-call sweep cross-checked against psutil, live.

A wrong struct offset in the `SYSTEM_PROCESS_INFORMATION` parse would miscount
silently. This test runs the real sweep and psutil's `process_iter` back to
back on the running machine and requires: row count ±1, console-host count ±1,
handle total within 1 %. Process churn on a busy machine can move a count by
more than one between two enumerations, so a miss retries up to three times —
a tolerance of time, not of correctness.

psutil's enumeration is used HERE, in a test, as the independent oracle. It
is forbidden in the collector (tests/unit/test_collector_source_pin.py).
"""

from __future__ import annotations

import sys

import psutil
import pytest

from boostgauge.collectors.windows import CONSOLE_HOSTS, WindowsCollector

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows sweep")


def _psutil_oracle():
    rows = conpty = handles = 0
    for p in psutil.process_iter(attrs=["name", "num_handles"], ad_value=None):
        rows += 1
        if (p.info["name"] or "").lower() in CONSOLE_HOSTS:
            conpty += 1
        handles += p.info["num_handles"] or 0
    return rows, conpty, handles


def test_sweep_matches_psutil_on_this_machine():
    collector = WindowsCollector()
    last = None
    for _attempt in range(3):
        rows = collector.nt_sweep()
        o_rows, o_conpty, o_handles = _psutil_oracle()
        s_rows = len(rows)
        s_conpty = sum(1 for r in rows if r.name in CONSOLE_HOSTS)
        s_handles = sum(r.handle_count for r in rows)
        last = (s_rows, o_rows, s_conpty, o_conpty, s_handles, o_handles)
        if (abs(s_rows - o_rows) <= 1 and abs(s_conpty - o_conpty) <= 1
                and abs(s_handles - o_handles) <= 0.01 * max(o_handles, 1)):
            break
    else:
        pytest.fail(f"sweep vs psutil after 3 attempts (rows, rows; conpty, conpty; "
                    f"handles, handles): {last}")

    assert s_rows > 20                      # a real machine, not an empty parse
    assert any(r.name == "system" for r in rows)   # pid 4 is always there
    assert s_handles >= o_handles * 0.99    # the sweep sees rows psutil cannot open
