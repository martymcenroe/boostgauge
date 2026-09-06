from __future__ import annotations

import psutil
import pytest

try:
    from boostgauge.collectors.windows import CONSOLE_HOSTS, WindowsCollector
except (ImportError, OSError):
    CONSOLE_HOSTS = set()  # type: ignore[assignment]
    WindowsCollector = None  # type: ignore[assignment,misc]


def _psutil_oracle():
    procs = list(psutil.process_iter(["name", "num_handles"]))
    process_count = len(procs)
    consoles = sum(
        1 for p in procs
        if p.info["name"] and p.info["name"].lower() in CONSOLE_HOSTS
    )
    handles = sum(
        p.info["num_handles"]
        for p in procs
        if p.info["num_handles"] is not None
    )
    return process_count, consoles, handles


@pytest.mark.skipif(
    __import__("sys").platform != "win32",
    reason="Windows-only: NtQuerySystemInformation not available",
)
def test_sweep_matches_psutil_on_this_machine():
    c = WindowsCollector()
    success = False
    for _ in range(3):
        snap = c.collect()
        psutil_count, psutil_conpty, psutil_handles = _psutil_oracle()

        count_ok = abs(snap.process_count - psutil_count) <= 1
        conpty_ok = abs(snap.conpty_count - psutil_conpty) <= 1
        handles_ok = (
            psutil_handles == 0
            or abs(snap.handle_count - psutil_handles) / psutil_handles <= 0.01
        )

        if count_ok and conpty_ok and handles_ok:
            success = True
            break

    assert success