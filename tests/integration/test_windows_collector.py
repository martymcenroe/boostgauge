"""Integration tests for WindowsCollector: live cross-checks against psutil.

Issue #4: Windows data collector
"""
from __future__ import annotations

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


def test_req_1_live(live_windows_collector):
    import psutil
    snapshot = live_windows_collector.sweep()
    psutil_conpty = sum(
        1 for p in psutil.process_iter(['name'])
        if p.info['name'] and p.info['name'].lower() in ("conhost.exe", "openconsole.exe")
    )
    assert abs(snapshot.conpty_count - psutil_conpty) <= 1


def test_req_2_live(live_windows_collector):
    import psutil
    snapshot = live_windows_collector.sweep()

    psutil_procs = 0
    psutil_handles = 0
    for p in psutil.process_iter(['num_handles']):
        psutil_procs += 1
        try:
            psutil_handles += p.info.get('num_handles', 0) or 0
        except Exception:
            pass

    assert abs(snapshot.process_count - psutil_procs) <= 1
    if psutil_handles > 0:
        assert abs(snapshot.handle_count - psutil_handles) / psutil_handles <= 0.01