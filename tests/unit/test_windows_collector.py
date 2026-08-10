"""Unit tests for the Windows collector.

Issue #4: Windows data collector
"""

import queue
import time
from unittest import mock

import pytest
import psutil

from boostgauge.collectors.windows import WindowsCollector


@pytest.fixture
def collector():
    q = queue.Queue()
    return WindowsCollector(target_queue=q, poll_interval=2.0)


def test_single_sweep_validation(collector):
    """T010: psutil.process_iter called exactly once per snapshot."""
    with mock.patch("psutil.process_iter", return_value=[]) as mock_iter, \
         mock.patch("psutil.virtual_memory") as mock_mem:
        mock_mem.return_value.percent = 50.0

        collector._collect_snapshot()

        mock_iter.assert_called_once_with(attrs=["name", "num_handles", "cmdline"])


def test_memory_read_validation(collector):
    """T020: virtual_memory called once per snapshot."""
    with mock.patch("psutil.process_iter", return_value=[]), \
         mock.patch("psutil.virtual_memory") as mock_mem:
        mock_mem.return_value.percent = 50.0

        snapshot = collector._collect_snapshot()

        mock_mem.assert_called_once()
        assert snapshot.memory_percent == 50.0


def test_mid_walk_exception_handling(collector):
    """T030: Process raises NoSuchProcess or AccessDenied; thread skips and continues."""
    mock_proc1 = mock.Mock()
    type(mock_proc1).info = mock.PropertyMock(side_effect=psutil.NoSuchProcess(1))

    mock_proc2 = mock.Mock()
    type(mock_proc2).info = mock.PropertyMock(side_effect=psutil.AccessDenied(2))

    mock_proc3 = mock.Mock()
    type(mock_proc3).info = mock.PropertyMock(
        return_value={"name": "test.exe", "num_handles": 10, "cmdline": []}
    )

    with mock.patch("psutil.process_iter", return_value=[mock_proc1, mock_proc2, mock_proc3]), \
         mock.patch("psutil.virtual_memory") as mock_mem:
        mock_mem.return_value.percent = 10.0

        snapshot = collector._collect_snapshot()

        assert snapshot.process_count == 1
        assert snapshot.handle_count == 10


def test_process_counting(collector):
    """T040: Returns total count of processed rows."""
    procs = []
    for _ in range(5):
        m = mock.Mock()
        type(m).info = mock.PropertyMock(
            return_value={"name": "dummy.exe", "num_handles": 1, "cmdline": []}
        )
        procs.append(m)

    with mock.patch("psutil.process_iter", return_value=procs), \
         mock.patch("psutil.virtual_memory") as mock_mem:
        mock_mem.return_value.percent = 10.0

        snapshot = collector._collect_snapshot()

        assert snapshot.process_count == 5


def test_conpty_filtering(collector):
    """T050: Matches case-insensitive conhost.exe and openconsole.exe."""
    names = ["ConHost.exe", "openconsole.exe", "other.exe"]
    procs = []
    for name in names:
        m = mock.Mock()
        type(m).info = mock.PropertyMock(
            return_value={"name": name, "num_handles": 1, "cmdline": []}
        )
        procs.append(m)

    with mock.patch("psutil.process_iter", return_value=procs), \
         mock.patch("psutil.virtual_memory") as mock_mem:
        mock_mem.return_value.percent = 10.0

        snapshot = collector._collect_snapshot()

        assert snapshot.conpty_count == 2


def test_handle_aggregation(collector):
    """T060: Sums num_handles across all read processes."""
    procs = []
    for handles in [10, 20]:
        m = mock.Mock()
        type(m).info = mock.PropertyMock(
            return_value={"name": "dummy.exe", "num_handles": handles, "cmdline": []}
        )
        procs.append(m)

    with mock.patch("psutil.process_iter", return_value=procs), \
         mock.patch("psutil.virtual_memory") as mock_mem:
        mock_mem.return_value.percent = 10.0

        snapshot = collector._collect_snapshot()

        assert snapshot.handle_count == 30


def test_unleashed_session_matching(collector):
    """T070: Matches python interpreters running unleashed-c-*.py."""
    mock_proc1 = mock.Mock()
    type(mock_proc1).info = mock.PropertyMock(return_value={
        "name": "pythonw.exe",
        "num_handles": 10,
        "cmdline": ["pythonw.exe", "unleashed-c-123.py"],
    })

    with mock.patch("psutil.process_iter", return_value=[mock_proc1]), \
         mock.patch("psutil.virtual_memory") as mock_mem:
        mock_mem.return_value.percent = 10.0

        snapshot = collector._collect_snapshot()

        assert snapshot.unleashed_sessions == 1


def test_background_thread_lifecycle(collector):
    """T080: Starts, pushes to queue, and stops gracefully."""
    with mock.patch.object(collector, "_collect_snapshot") as mock_collect:
        mock_collect.return_value = "fake_snapshot"
        collector.poll_interval = 0.01

        collector.start()
        time.sleep(0.05)
        collector.stop()

        assert mock_collect.called
        assert not collector._target_queue.empty()
        assert collector._target_queue.get() == "fake_snapshot"
        assert not collector._thread.is_alive()


def test_normalized_max_logic():
    """T090: Returns the max normalized metric and its driver name."""
    q = queue.Queue()
    collector = WindowsCollector(target_queue=q, poll_interval=2.0, thresholds={
        "conpty": 10.0,
        "memory": 100.0,
        "processes": 100.0,
        "handles": 100.0,
    })

    mock_proc = mock.Mock()
    type(mock_proc).info = mock.PropertyMock(
        return_value={"name": "conhost.exe", "num_handles": 0, "cmdline": []}
    )

    with mock.patch("psutil.process_iter", return_value=[mock_proc] * 5), \
         mock.patch("psutil.virtual_memory") as mock_mem:
        mock_mem.return_value.percent = 10.0

        snapshot = collector._collect_snapshot()

        assert snapshot.driver == "conpty"
        assert snapshot.composite_value == 50.0


def test_default_config_validation():
    """T100: Polling interval defaults to 2.0s."""
    q = queue.Queue()
    collector = WindowsCollector(target_queue=q)
    assert collector.poll_interval == 2.0


@pytest.mark.live
def test_cpu_overhead():
    """T110: CPU < 1% over interval."""
    q = queue.Queue()
    collector = WindowsCollector(target_queue=q, poll_interval=2.0)

    process = psutil.Process()
    process.cpu_percent(interval=None)

    start_time = time.time()
    collector.start()
    time.sleep(2.5)
    collector.stop()
    duration = time.time() - start_time

    cpu_usage = process.cpu_percent(interval=None)

    assert duration >= 2.5
    assert cpu_usage < 1.0
    assert not collector._thread.is_alive()