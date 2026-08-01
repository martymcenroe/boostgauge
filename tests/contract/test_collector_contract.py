"""Contract test suite verifying DataCollector interface compliance across concrete implementations.

Issue #4: Feature: Windows data collector — ConPTY, processes, memory, handles
"""

import queue
import time
from unittest.mock import MagicMock, patch

import psutil
import pytest

from boostgauge.collector import DataCollector, SystemSnapshot
from boostgauge.collectors.windows import WindowsCollector


@pytest.fixture
def mock_psutil():
    with patch("boostgauge.collectors.windows.psutil") as mock_p:
        mock_mem = MagicMock()
        mock_mem.percent = 50.0
        mock_p.virtual_memory.return_value = mock_mem
        mock_p.pids.return_value = list(range(1, 101))

        p1 = MagicMock()
        p1.info = {"name": "conhost.exe", "num_handles": 200, "cmdline": ["conhost.exe"]}
        p2 = MagicMock()
        p2.info = {
            "name": "python.exe",
            "num_handles": 300,
            "cmdline": ["python.exe", "unleashed-c-session.py"],
        }
        mock_p.process_iter.return_value = [p1, p2]
        mock_p.NoSuchProcess = psutil.NoSuchProcess
        mock_p.AccessDenied = psutil.AccessDenied
        mock_p.ZombieProcess = psutil.ZombieProcess
        yield mock_p


@pytest.fixture
def collector(mock_psutil):
    return WindowsCollector(
        config={"poll_interval": 0.05, "_allow_non_windows_for_testing": True}
    )


def test_collector_is_subclass_of_data_collector(collector):
    assert isinstance(collector, DataCollector)


def test_collector_has_start_method(collector):
    assert callable(getattr(collector, "start", None))


def test_collector_has_stop_method(collector):
    assert callable(getattr(collector, "stop", None))


def test_collector_has_poll_metrics_method(collector):
    assert callable(getattr(collector, "poll_metrics", None))


def test_collector_has_snapshot_queue(collector):
    assert hasattr(collector, "snapshot_queue")
    assert isinstance(collector.snapshot_queue, queue.Queue)


def test_collector_has_poll_interval(collector):
    assert hasattr(collector, "poll_interval")
    assert isinstance(collector.poll_interval, float)


def test_collector_has_thresholds(collector):
    assert hasattr(collector, "thresholds")
    assert isinstance(collector.thresholds, dict)


def test_poll_metrics_returns_system_snapshot(collector):
    snapshot = collector.poll_metrics()
    assert isinstance(snapshot, SystemSnapshot)


def test_poll_metrics_snapshot_timestamp_is_float(collector):
    snapshot = collector.poll_metrics()
    assert isinstance(snapshot.timestamp, float)


def test_poll_metrics_snapshot_timestamp_is_recent(collector):
    before = time.time()
    snapshot = collector.poll_metrics()
    after = time.time()
    assert before <= snapshot.timestamp <= after


def test_poll_metrics_snapshot_conpty_count_is_int(collector):
    snapshot = collector.poll_metrics()
    assert isinstance(snapshot.conpty_count, int)


def test_poll_metrics_snapshot_conpty_count_non_negative(collector):
    snapshot = collector.poll_metrics()
    assert snapshot.conpty_count >= 0


def test_poll_metrics_snapshot_process_count_is_int(collector):
    snapshot = collector.poll_metrics()
    assert isinstance(snapshot.process_count, int)


def test_poll_metrics_snapshot_process_count_non_negative(collector):
    snapshot = collector.poll_metrics()
    assert snapshot.process_count >= 0


def test_poll_metrics_snapshot_memory_percent_is_float(collector):
    snapshot = collector.poll_metrics()
    assert isinstance(snapshot.memory_percent, float)


def test_poll_metrics_snapshot_memory_percent_in_range(collector):
    snapshot = collector.poll_metrics()
    assert 0.0 <= snapshot.memory_percent <= 100.0


def test_poll_metrics_snapshot_handle_count_is_int(collector):
    snapshot = collector.poll_metrics()
    assert isinstance(snapshot.handle_count, int)


def test_poll_metrics_snapshot_handle_count_non_negative(collector):
    snapshot = collector.poll_metrics()
    assert snapshot.handle_count >= 0


def test_poll_metrics_snapshot_unleashed_sessions_is_int(collector):
    snapshot = collector.poll_metrics()
    assert isinstance(snapshot.unleashed_sessions, int)


def test_poll_metrics_snapshot_unleashed_sessions_non_negative(collector):
    snapshot = collector.poll_metrics()
    assert snapshot.unleashed_sessions >= 0


def test_poll_metrics_snapshot_driver_is_str(collector):
    snapshot = collector.poll_metrics()
    assert isinstance(snapshot.driver, str)


def test_poll_metrics_snapshot_driver_in_valid_set(collector):
    snapshot = collector.poll_metrics()
    assert snapshot.driver in ("conpty", "memory", "process", "handles")


def test_poll_metrics_snapshot_composite_value_is_float(collector):
    snapshot = collector.poll_metrics()
    assert isinstance(snapshot.composite_value, float)


def test_poll_metrics_snapshot_composite_value_in_range(collector):
    snapshot = collector.poll_metrics()
    assert 0.0 <= snapshot.composite_value <= 100.0


def test_start_stop_thread_lifecycle(collector):
    collector.start()
    assert collector._thread is not None
    assert collector._thread.is_alive()
    collector.stop(timeout=1.0)
    assert not collector._thread.is_alive()


def test_start_idempotent(collector):
    collector.start()
    thread_id = collector._thread.ident
    collector.start()
    assert collector._thread.ident == thread_id
    collector.stop(timeout=1.0)


def test_stop_before_start_no_error(collector):
    collector.stop(timeout=0.1)


def test_background_thread_pushes_snapshots_to_queue(collector):
    q: queue.Queue[SystemSnapshot] = queue.Queue(maxsize=10)
    collector.snapshot_queue = q
    collector.start()
    time.sleep(0.2)
    collector.stop(timeout=1.0)

    assert q.qsize() >= 1
    snapshot = q.get_nowait()
    assert isinstance(snapshot, SystemSnapshot)


def test_queue_receives_multiple_snapshots(collector):
    q: queue.Queue[SystemSnapshot] = queue.Queue(maxsize=20)
    collector.snapshot_queue = q
    collector.start()
    time.sleep(0.25)
    collector.stop(timeout=1.0)

    assert q.qsize() >= 2


def test_queue_overflow_does_not_block(mock_psutil):
    q: queue.Queue[SystemSnapshot] = queue.Queue(maxsize=2)
    col = WindowsCollector(
        config={"poll_interval": 0.02, "_allow_non_windows_for_testing": True},
        snapshot_queue=q,
    )
    col.start()
    time.sleep(0.15)
    col.stop(timeout=1.0)

    assert q.qsize() == 2


def test_collector_contract_full_interface(mock_psutil):
    q: queue.Queue[SystemSnapshot] = queue.Queue()
    collector = WindowsCollector(
        config={"poll_interval": 0.05, "_allow_non_windows_for_testing": True},
        snapshot_queue=q,
    )

    assert hasattr(collector, "start")
    assert hasattr(collector, "stop")
    assert hasattr(collector, "poll_metrics")

    snapshot = collector.poll_metrics()
    assert isinstance(snapshot, SystemSnapshot)
    assert isinstance(snapshot.timestamp, float)
    assert isinstance(snapshot.conpty_count, int)
    assert isinstance(snapshot.process_count, int)
    assert isinstance(snapshot.memory_percent, float)
    assert isinstance(snapshot.handle_count, int)
    assert isinstance(snapshot.unleashed_sessions, int)
    assert isinstance(snapshot.driver, str)
    assert isinstance(snapshot.composite_value, float)