"""Contract tests for DataCollector implementation compliance.

Issue #4: Windows data collector — ConPTY, processes, memory, handles
"""

import queue

from boostgauge.collector import DataCollector, SystemSnapshot
from boostgauge.collectors import create_collector


def test_collector_contract_interface():
    """Verify create_collector returns a compliant DataCollector instance."""
    collector = create_collector()
    assert isinstance(collector, DataCollector)

    snapshot = collector.poll()
    assert isinstance(snapshot, SystemSnapshot)
    assert isinstance(snapshot.timestamp, float)
    assert isinstance(snapshot.conpty_count, int)
    assert isinstance(snapshot.process_count, int)
    assert isinstance(snapshot.memory_percent, float)
    assert isinstance(snapshot.handle_count, int)
    assert isinstance(snapshot.unleashed_sessions, int)
    assert isinstance(snapshot.driver, str)
    assert isinstance(snapshot.composite_value, float)
    assert 0.0 <= snapshot.composite_value <= 100.0


def test_collector_contract_driver_is_valid():
    """Verify poll() returns a snapshot with a valid driver string."""
    collector = create_collector()
    snapshot = collector.poll()
    assert snapshot.driver in ("conpty", "memory", "process", "handle")


def test_collector_contract_start_stop_lifecycle():
    """Verify start/stop lifecycle methods are available and functional."""
    collector = create_collector()
    assert hasattr(collector, "start")
    assert hasattr(collector, "stop")
    assert hasattr(collector, "is_running")

    assert not collector.is_running()
    collector.start()
    assert collector.is_running()
    collector.stop()
    assert not collector.is_running()


def test_collector_contract_start_idempotent():
    """Verify calling start() twice does not raise."""
    collector = create_collector()
    collector.start()
    collector.start()
    collector.stop()


def test_collector_contract_stop_when_not_running():
    """Verify calling stop() when not running does not raise."""
    collector = create_collector()
    collector.stop()


def test_collector_contract_with_queue():
    """Verify create_collector accepts a snapshot_queue and pushes snapshots to it."""
    import time
    q = queue.Queue(maxsize=10)
    collector = create_collector(config={"poll_interval": 0.05}, snapshot_queue=q)
    collector.start()
    time.sleep(0.2)
    collector.stop()

    assert not q.empty()
    item = q.get_nowait()
    assert isinstance(item, SystemSnapshot)


def test_collector_contract_with_config():
    """Verify create_collector accepts a config dict without error."""
    config = {
        "poll_interval": 1.0,
        "thresholds": {
            "conpty": 50.0,
            "memory": 90.0,
            "process": 500.0,
            "handles": 100000.0,
        },
    }
    collector = create_collector(config=config)
    assert isinstance(collector, DataCollector)


def test_collector_contract_poll_snapshot_counts_non_negative():
    """Verify all snapshot counts are non-negative."""
    collector = create_collector()
    snapshot = collector.poll()
    assert snapshot.conpty_count >= 0
    assert snapshot.process_count >= 0
    assert snapshot.memory_percent >= 0.0
    assert snapshot.handle_count >= 0
    assert snapshot.unleashed_sessions >= 0


def test_collector_contract_poll_timestamp_is_recent():
    """Verify snapshot timestamp is a recent Unix timestamp."""
    import time
    before = time.time()
    collector = create_collector()
    snapshot = collector.poll()
    after = time.time()
    assert before <= snapshot.timestamp <= after


def test_collector_contract_queue_eviction_on_full():
    """Verify queue full condition is handled without raising."""
    import time
    q = queue.Queue(maxsize=2)
    collector = create_collector(config={"poll_interval": 0.01}, snapshot_queue=q)
    collector.start()
    time.sleep(0.1)
    collector.stop()
    assert q.qsize() <= 2