"""Contract tests for DataCollector interface and SystemSnapshot schema compliance.

Issue #4: Feature: Windows Data Collector — ConPTY, Processes, Memory, Handles
"""

from __future__ import annotations

import pytest
from boostgauge.collector import DataCollector, SystemSnapshot
from boostgauge.collectors import get_collector


def test_abstract_collector_instantiation_raises():
    """Verify instantiating DataCollector directly raises TypeError (T010 / REQ-1)."""
    with pytest.raises(TypeError):
        DataCollector()  # type: ignore


def test_get_collector_returns_datacollector_subclass():
    """Verify get_collector returns a valid DataCollector instance (REQ-1)."""
    collector = get_collector()
    assert isinstance(collector, DataCollector)
    assert hasattr(collector, "collect_snapshot")
    assert hasattr(collector, "start")
    assert hasattr(collector, "stop")
    assert hasattr(collector, "is_running")


def test_collect_snapshot_schema_contract():
    """Verify snapshot schema adheres strictly to SystemSnapshot structure (REQ-1)."""
    collector = get_collector()
    snapshot = collector.collect_snapshot()

    assert isinstance(snapshot, SystemSnapshot)
    assert isinstance(snapshot.timestamp, float)
    assert isinstance(snapshot.conpty_count, int)
    assert isinstance(snapshot.process_count, int)
    assert isinstance(snapshot.memory_percent, float)
    assert isinstance(snapshot.handle_count, int)
    assert isinstance(snapshot.unleashed_sessions, int)
    assert isinstance(snapshot.driver, str)
    assert isinstance(snapshot.composite_value, float)


def test_snapshot_driver_is_valid_metric_key():
    """Verify snapshot driver field is always one of the four valid metric keys."""
    collector = get_collector()
    snapshot = collector.collect_snapshot()

    assert snapshot.driver in ("conpty", "memory_percent", "process_count", "handle_count")


def test_snapshot_composite_value_within_bounds():
    """Verify snapshot composite_value is clamped to [0.0, 100.0]."""
    collector = get_collector()
    snapshot = collector.collect_snapshot()

    assert 0.0 <= snapshot.composite_value <= 100.0


def test_snapshot_is_immutable():
    """Verify SystemSnapshot is frozen and rejects field mutation."""
    collector = get_collector()
    snapshot = collector.collect_snapshot()

    with pytest.raises(AttributeError):
        snapshot.composite_value = 99.9  # type: ignore


def test_snapshot_timestamp_is_positive():
    """Verify snapshot timestamp is a positive Unix epoch float."""
    collector = get_collector()
    snapshot = collector.collect_snapshot()

    assert snapshot.timestamp > 0.0


def test_snapshot_counts_are_non_negative():
    """Verify all count fields in SystemSnapshot are non-negative integers."""
    collector = get_collector()
    snapshot = collector.collect_snapshot()

    assert snapshot.conpty_count >= 0
    assert snapshot.process_count >= 0
    assert snapshot.handle_count >= 0
    assert snapshot.unleashed_sessions >= 0


def test_snapshot_memory_percent_within_bounds():
    """Verify memory_percent field is within valid percentage range [0.0, 100.0]."""
    collector = get_collector()
    snapshot = collector.collect_snapshot()

    assert 0.0 <= snapshot.memory_percent <= 100.0


def test_get_collector_default_parameters():
    """Verify get_collector uses default poll_interval of 2.0 when not specified."""
    collector = get_collector()
    assert collector.poll_interval == 2.0


def test_get_collector_custom_poll_interval():
    """Verify get_collector respects custom poll_interval parameter."""
    collector = get_collector(poll_interval=5.0)
    assert collector.poll_interval == 5.0


def test_get_collector_with_custom_thresholds():
    """Verify get_collector passes custom thresholds to the underlying collector."""
    thresholds = {
        "conpty": {"yellow": 5.0, "red": 10.0},
        "memory_percent": {"yellow": 50.0, "red": 75.0},
        "process_count": {"yellow": 100.0, "red": 200.0},
        "handle_count": {"yellow": 5000.0, "red": 10000.0},
    }
    collector = get_collector(thresholds=thresholds)
    assert isinstance(collector, DataCollector)
    snapshot = collector.collect_snapshot()
    assert isinstance(snapshot, SystemSnapshot)


def test_collector_is_not_running_initially():
    """Verify collector background thread is not running before start() is called."""
    collector = get_collector()
    assert not collector.is_running()


def test_collector_stop_is_safe_before_start():
    """Verify stop() does not raise when called before start()."""
    collector = get_collector()
    collector.stop()
    assert not collector.is_running()


def test_successive_snapshots_have_increasing_timestamps():
    """Verify successive collect_snapshot calls produce non-decreasing timestamps."""
    import time
    collector = get_collector()
    snapshot1 = collector.collect_snapshot()
    time.sleep(0.01)
    snapshot2 = collector.collect_snapshot()

    assert snapshot2.timestamp >= snapshot1.timestamp