"""Unit tier for the collector: composite arithmetic, the single-sweep rule, the thread.

ADR 0001 §4 hook 1: stub the system call and assert all four process-derived
metrics derive from ONE call per tick. Values are literal (ruling #270).
"""

from __future__ import annotations

import queue

import pytest

from boostgauge.collector import (Band, CollectorThread, DataCollector, SystemSnapshot,
                                  Thresholds, composite, normalize)
from boostgauge.collectors.windows import ProcessRow, WindowsCollector, is_unleashed_cmdline

# ---- normalize / composite ---------------------------------------------------


def test_normalize_literal_points():
    band = Band(30, 60)                      # #7's conpty defaults
    assert normalize(0, band) == 0.0
    assert normalize(15, band) == 30.0        # half of yellow -> half of 60
    assert normalize(30, band) == 60.0        # yellow -> 60
    assert normalize(45, band) == 80.0        # midpoint yellow->red -> "elevated" 80
    assert normalize(60, band) == 100.0       # red -> 100
    assert normalize(90, band) == 100.0       # clamped
    assert normalize(-5, band) == 0.0         # clamped


def test_composite_is_max_and_names_the_driver():
    t = Thresholds()
    # conpty 45/30..60 -> 80; memory 66/60..80 -> 72; processes 373/300..500 -> 74.6;
    # handles 150000/30000..50000 -> 100 (clamped). Handles win.
    value, driver = composite(45, 66.0, 373, 150000, t)
    assert value == 100.0
    assert driver == "handles"
    # all cool: memory at 30% -> 30; everything else zero.
    value, driver = composite(0, 30.0, 0, 0, t)
    assert value == 30.0
    assert driver == "memory"


def test_composite_ties_resolve_in_metric_order():
    t = Thresholds()
    value, driver = composite(30, 60.0, 300, 30000, t)  # every metric exactly at yellow
    assert value == 60.0
    assert driver == "conpty"


# ---- the one-sweep rule (ADR 0001 §4 hook 1) ----------------------------------

FAKE_ROWS = [
    ProcessRow(pid=0, name="", handle_count=0),
    ProcessRow(pid=4, name="system", handle_count=5000),
    ProcessRow(pid=101, name="conhost.exe", handle_count=120),
    ProcessRow(pid=102, name="OpenConsole.exe".lower(), handle_count=95),
    ProcessRow(pid=103, name="conhost.exe", handle_count=110),
    ProcessRow(pid=201, name="python.exe", handle_count=400),      # unleashed session
    ProcessRow(pid=202, name="python.exe", handle_count=300),      # plain python
    ProcessRow(pid=203, name="pythonw.exe", handle_count=250),     # unleashed session
    ProcessRow(pid=301, name="code.exe", handle_count=900),        # editor holding the filename
    ProcessRow(pid=302, name="grep.exe", handle_count=30),         # grep holding the filename
]
FAKE_CMDLINES = {
    201: ["C:\\Python\\python.exe", "C:\\Users\\x\\unleashed-c-boostgauge.py"],
    202: ["C:\\Python\\python.exe", "-m", "pytest"],
    203: ["pythonw.exe", "unleashed-c-aletheia.py"],
    301: ["code.exe", "unleashed-c-boostgauge.py"],
    302: ["grep.exe", "unleashed-c-", "unleashed-c-x.py"],
}


class _Calls:
    def __init__(self):
        self.sweeps = 0
        self.cmdline_pids: list[int] = []

    def sweep(self):
        self.sweeps += 1
        return list(FAKE_ROWS)

    def cmdline(self, pid):
        self.cmdline_pids.append(pid)
        return FAKE_CMDLINES.get(pid, [])


@pytest.fixture
def fake_memory(monkeypatch):
    class VM:
        percent = 66.0

    monkeypatch.setattr("boostgauge.collectors.windows.psutil.virtual_memory", lambda: VM())


def test_all_four_metrics_from_one_sweep(fake_memory):
    calls = _Calls()
    collector = WindowsCollector(sweep=calls.sweep, cmdline=calls.cmdline)

    snap = collector.collect()

    assert calls.sweeps == 1                          # ONE enumeration per tick
    assert snap.process_count == 10                   # rows the sweep yielded, pid 0 included
    assert snap.conpty_count == 3                     # two conhost + one OpenConsole
    assert snap.handle_count == 7205                  # sum of every row's HandleCount
    assert snap.unleashed_sessions == 2               # 201 and 203; not 202, not code.exe, not grep
    assert snap.memory_percent == 66.0
    # cmdline was read ONLY for the rows the sweep identified as Python interpreters
    assert sorted(calls.cmdline_pids) == [201, 202, 203]


def test_second_tick_is_a_second_single_sweep(fake_memory):
    calls = _Calls()
    collector = WindowsCollector(sweep=calls.sweep, cmdline=calls.cmdline)
    collector.collect()
    collector.collect()
    assert calls.sweeps == 2


def test_unleashed_predicate_is_basename_glob():
    assert is_unleashed_cmdline(["python.exe", "C:\\a\\b\\unleashed-c-boostgauge.py"])
    assert is_unleashed_cmdline(["python.exe", "UNLEASHED-C-X.PY"])
    assert not is_unleashed_cmdline(["python.exe", "unleashed-c-x.pyc"])
    assert not is_unleashed_cmdline(["python.exe", "notunleashed-c-x.py"])
    assert not is_unleashed_cmdline([])


# ---- the polling thread --------------------------------------------------------


class _Fixed(DataCollector):
    def __init__(self):
        super().__init__()
        self.ticks = 0

    def collect(self) -> SystemSnapshot:
        self.ticks += 1
        return SystemSnapshot(timestamp=float(self.ticks), conpty_count=1, process_count=2,
                              memory_percent=3.0, handle_count=4, unleashed_sessions=5,
                              driver="memory", composite_value=6.0)


class _Flaky(_Fixed):
    def collect(self) -> SystemSnapshot:
        if self.ticks == 0:
            self.ticks += 1
            raise OSError("NtQuerySystemInformation failed: NTSTATUS 0xC0000005")
        return super().collect()


def test_thread_polls_and_stops_cleanly():
    q: queue.Queue = queue.Queue()
    t = CollectorThread(_Fixed(), interval=0.01, snapshots=q)
    t.start()
    first = q.get(timeout=2.0)
    second = q.get(timeout=2.0)
    t.stop(timeout=2.0)
    assert not t.is_alive()
    assert first.timestamp == 1.0 and second.timestamp == 2.0
    assert t.latest is not None and t.latest.timestamp >= 2.0
    assert t.daemon


def test_thread_survives_a_failing_tick():
    q: queue.Queue = queue.Queue()
    t = CollectorThread(_Flaky(), interval=0.01, snapshots=q)
    t.start()
    snap = q.get(timeout=2.0)          # the SECOND tick's snapshot — the first raised
    t.stop(timeout=2.0)
    assert snap.timestamp == 2.0
    assert isinstance(t.last_error, OSError)
    assert not t.is_alive()
