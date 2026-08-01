"""Contract tests verifying interface compliance for DataCollector subclasses.

Issue #4: Feature: Windows data collector — ConPTY, processes, memory, handles
"""

import queue
import time
from unittest.mock import patch

import pytest

from boostgauge.collector import DataCollector, SystemSnapshot
from boostgauge.collectors import WindowsCollector, create_collector


def test_collector_contract_subclass():
    with patch("psutil.process_iter", return_value=[]), \
         patch("psutil.pids", return_value=list(range(100))), \
         patch("psutil.virtual_memory") as mock_mem:
        mock_mem.return_value.percent = 50.0
        collector = WindowsCollector(config={"poll_interval": 0.1})
        assert isinstance(collector, DataCollector)

        snapshot = collector.collect()
        assert isinstance(snapshot, SystemSnapshot)
        assert isinstance(snapshot.timestamp, float)
        assert isinstance(snapshot.conpty_count, int)
        assert isinstance(snapshot.process_count, int)
        assert isinstance(snapshot.memory_percent, float)
        assert isinstance(snapshot.handle_count, int)
        assert isinstance(snapshot.unleashed_sessions, int)
        assert isinstance(snapshot.driver, str)
        assert snapshot.driver in ("conpty", "memory", "process", "handles")
        assert 0.0 <= snapshot.composite_value <= 100.0


def test_create_collector_factory_contract():
    collector = create_collector()
    assert isinstance(collector, DataCollector)


def test_collector_has_start_stop_is_running():
    collector = WindowsCollector(config={"poll_interval": 0.1})
    assert hasattr(collector, "start")
    assert hasattr(collector, "stop")
    assert hasattr(collector, "is_running")
    assert callable(collector.start)
    assert callable(collector.stop)


def test_collector_is_running_false_before_start():
    collector = WindowsCollector(config={"poll_interval": 0.1})
    assert collector.is_running is False


def test_collector_lifecycle_start_stop():
    with patch("psutil.process_iter", return_value=[]), \
         patch("psutil.pids", return_value=[]), \
         patch("psutil.virtual_memory") as mock_mem:
        mock_mem.return_value.percent = 0.0
        collector = WindowsCollector(config={"poll_interval": 0.05})

        assert not collector.is_running
        collector.start()
        assert collector.is_running
        time.sleep(0.1)
        collector.stop()
        assert not collector.is_running


def test_collector_start_idempotent():
    with patch("psutil.process_iter", return_value=[]), \
         patch("psutil.pids", return_value=[]), \
         patch("psutil.virtual_memory") as mock_mem:
        mock_mem.return_value.percent = 0.0
        collector = WindowsCollector(config={"poll_interval": 0.05})

        collector.start()
        thread_id = collector._thread.ident
        collector.start()
        assert collector._thread.ident == thread_id
        collector.stop()


def test_collector_stop_when_not_running():
    collector = WindowsCollector(config={"poll_interval": 0.1})
    collector.stop()
    assert not collector.is_running


def test_collector_pushes_snapshots_to_queue():
    sq = queue.Queue(maxsize=10)
    with patch("psutil.process_iter", return_value=[]), \
         patch("psutil.pids", return_value=list(range(50))), \
         patch("psutil.virtual_memory") as mock_mem:
        mock_mem.return_value.percent = 40.0
        collector = WindowsCollector(config={"poll_interval": 0.05}, snapshot_queue=sq)
        collector.start()
        time.sleep(0.2)
        collector.stop()

    assert not sq.empty()
    snapshot = sq.get(block=False)
    assert isinstance(snapshot, SystemSnapshot)


def test_collector_has_snapshot_queue():
    collector = WindowsCollector()
    assert hasattr(collector, "snapshot_queue")
    assert isinstance(collector.snapshot_queue, queue.Queue)


def test_collector_accepts_external_queue():
    sq = queue.Queue(maxsize=5)
    collector = WindowsCollector(snapshot_queue=sq)
    assert collector.snapshot_queue is sq


def test_collector_has_collect_method():
    collector = WindowsCollector()
    assert hasattr(collector, "collect")
    assert callable(collector.collect)


def test_collector_has_put_method():
    collector = WindowsCollector()
    assert hasattr(collector, "put")
    assert callable(collector.put)


def test_collector_put_enqueues_snapshot():
    sq = queue.Queue(maxsize=10)
    collector = WindowsCollector(snapshot_queue=sq)
    snapshot = SystemSnapshot(
        timestamp=time.time(),
        conpty_count=0,
        process_count=100,
        memory_percent=50.0,
        handle_count=10000,
        unleashed_sessions=0,
        driver="memory",
        composite_value=50.0,
    )
    collector.put(snapshot)
    assert sq.qsize() == 1
    assert sq.get(block=False) is snapshot


def test_collector_put_evicts_on_overflow():
    sq = queue.Queue(maxsize=2)
    collector = WindowsCollector(snapshot_queue=sq)

    for i in range(3):
        snapshot = SystemSnapshot(
            timestamp=float(i),
            conpty_count=i,
            process_count=100,
            memory_percent=50.0,
            handle_count=10000,
            unleashed_sessions=0,
            driver="memory",
            composite_value=50.0,
        )
        collector.put(snapshot)

    assert sq.qsize() == 2


def test_collector_thresholds_attribute():
    collector = WindowsCollector()
    assert hasattr(collector, "thresholds")
    assert isinstance(collector.thresholds, dict)
    for key in ("conpty", "memory", "process", "handles"):
        assert key in collector.thresholds
        assert isinstance(collector.thresholds[key], float)
        assert collector.thresholds[key] > 0.0


def test_collector_poll_interval_attribute():
    collector = WindowsCollector(config={"poll_interval": 1.5})
    assert hasattr(collector, "poll_interval")
    assert collector.poll_interval == 1.5


def test_create_collector_returns_correct_type_on_windows():
    collector = create_collector(config={"poll_interval": 0.5})
    assert isinstance(collector, DataCollector)
    assert isinstance(collector, WindowsCollector)


def test_create_collector_accepts_snapshot_queue():
    sq = queue.Queue(maxsize=10)
    collector = create_collector(snapshot_queue=sq)
    assert collector.snapshot_queue is sq


def test_snapshot_field_types_from_collect():
    with patch("psutil.process_iter", return_value=[]), \
         patch("psutil.pids", return_value=list(range(200))), \
         patch("psutil.virtual_memory") as mock_mem:
        mock_mem.return_value.percent = 75.0
        collector = WindowsCollector()
        snapshot = collector.collect()

    assert snapshot.conpty_count >= 0
    assert snapshot.process_count >= 0
    assert 0.0 <= snapshot.memory_percent <= 100.0
    assert snapshot.handle_count >= 0
    assert snapshot.unleashed_sessions >= 0
    assert snapshot.timestamp > 0.0


def test_collector_put_handles_queue_empty_race():
    """Covers except queue.Empty branch: queue empties between Full check and get()."""
    sq = queue.Queue(maxsize=1)
    collector = WindowsCollector(snapshot_queue=sq)
    snapshot = SystemSnapshot(
        timestamp=time.time(),
        conpty_count=0,
        process_count=100,
        memory_percent=50.0,
        handle_count=10000,
        unleashed_sessions=0,
        driver="memory",
        composite_value=50.0,
    )

    put_calls = [0]

    def mock_put(item, block=True, timeout=None):
        put_calls[0] += 1
        if put_calls[0] == 1:
            raise queue.Full

    with patch.object(sq, "put", mock_put), \
         patch.object(sq, "get", side_effect=queue.Empty):
        collector.put(snapshot)


def test_collector_put_handles_still_full_after_eviction():
    """Covers inner except queue.Full branch: queue remains full after eviction attempt."""
    sq = queue.Queue(maxsize=1)
    collector = WindowsCollector(snapshot_queue=sq)
    snapshot = SystemSnapshot(
        timestamp=time.time(),
        conpty_count=0,
        process_count=100,
        memory_percent=50.0,
        handle_count=10000,
        unleashed_sessions=0,
        driver="memory",
        composite_value=50.0,
    )

    with patch.object(sq, "put", side_effect=queue.Full):
        collector.put(snapshot)


def test_poll_loop_continues_after_collect_exception():
    """Covers except Exception branch in _poll_loop when collect() raises."""
    with patch("psutil.process_iter", return_value=[]), \
         patch("psutil.pids", return_value=[]), \
         patch("psutil.virtual_memory") as mock_mem:
        mock_mem.return_value.percent = 0.0
        collector = WindowsCollector(config={"poll_interval": 0.05})

        with patch.object(collector, "collect", side_effect=RuntimeError("simulated poll error")):
            collector.start()
            time.sleep(0.15)
            collector.stop()
            assert not collector.is_running