"""Unit tests for DataCollector base class, metric normalization, composite load calculation, and queue lifecycle.

Issue #4: Windows data collector — ConPTY, processes, memory, handles
"""

import queue
import time
import pytest

from boostgauge.collector import (
    DataCollector,
    SystemSnapshot,
    calculate_composite_metric,
    normalize_metric,
)


def test_normalize_metric_basic():
    assert normalize_metric(5.0, 10.0) == 50.0
    assert normalize_metric(10.0, 10.0) == 100.0
    assert normalize_metric(15.0, 10.0) == 100.0
    assert normalize_metric(0.0, 10.0) == 0.0
    assert normalize_metric(-5.0, 10.0) == 0.0
    assert normalize_metric(5.0, 0.0) == 0.0


def test_normalize_metric_negative_threshold():
    assert normalize_metric(5.0, -1.0) == 0.0


def test_normalize_metric_fractional():
    assert abs(normalize_metric(3.0, 12.0) - 25.0) < 0.001


def test_calculate_composite_metric_conpty_driver():
    thresholds = {
        "conpty": {"critical": 10.0},
        "memory": {"critical": 100.0},
        "process": {"critical": 500.0},
        "handle": {"critical": 100000.0},
    }
    score, driver = calculate_composite_metric(
        conpty=8, memory_pct=50.0, process_cnt=100, handle_cnt=20000, thresholds=thresholds
    )
    assert score == 80.0
    assert driver == "conpty"


def test_calculate_composite_metric_memory_driver():
    thresholds = {
        "conpty": {"critical": 10.0},
        "memory": {"critical": 100.0},
        "process": {"critical": 500.0},
        "handle": {"critical": 100000.0},
    }
    score, driver = calculate_composite_metric(
        conpty=2, memory_pct=95.0, process_cnt=100, handle_cnt=20000, thresholds=thresholds
    )
    assert score == 95.0
    assert driver == "memory"


def test_calculate_composite_metric_default_thresholds():
    score, driver = calculate_composite_metric(
        conpty=0, memory_pct=0.0, process_cnt=0, handle_cnt=0, thresholds=None
    )
    assert score == 0.0


def test_calculate_composite_metric_empty_thresholds():
    score, driver = calculate_composite_metric(
        conpty=5, memory_pct=50.0, process_cnt=250, handle_cnt=50000, thresholds={}
    )
    assert isinstance(score, float)
    assert driver in ("conpty", "memory", "process", "handle")


def test_calculate_composite_metric_tie_picks_first():
    thresholds = {
        "conpty": {"critical": 10.0},
        "memory": {"critical": 100.0},
        "process": {"critical": 500.0},
        "handle": {"critical": 100000.0},
    }
    score, driver = calculate_composite_metric(
        conpty=10, memory_pct=100.0, process_cnt=500, handle_cnt=100000, thresholds=thresholds
    )
    assert score == 100.0
    assert driver == "conpty"


def test_collector_instantiation_defaults():
    collector = DataCollector()
    assert collector.poll_interval == 2.0
    assert collector.heavy_sample_ratio == 3
    assert collector.snapshot_queue is None
    assert not collector.is_running()


def test_collector_instantiation_with_config():
    config = {"poll_interval": 5.0, "heavy_sample_ratio": 5}
    collector = DataCollector(config=config)
    assert collector.poll_interval == 5.0
    assert collector.heavy_sample_ratio == 5


def test_collector_instantiation_missing_poll_interval():
    collector = DataCollector(config={})
    assert collector.poll_interval == 2.0


def test_collector_instantiation_missing_heavy_sample_ratio():
    collector = DataCollector(config={})
    assert collector.heavy_sample_ratio == 3


def test_collector_with_queue():
    q = queue.Queue(maxsize=10)
    collector = DataCollector(snapshot_queue=q)
    assert collector.snapshot_queue is q


def test_collector_collect_snapshot_returns_system_snapshot():
    collector = DataCollector()
    snapshot = collector.collect_snapshot()
    assert isinstance(snapshot, SystemSnapshot)
    assert snapshot.conpty_count == 0
    assert snapshot.process_count == 0
    assert snapshot.memory_percent == 0.0
    assert snapshot.handle_count == 0
    assert snapshot.unleashed_sessions == 0
    assert isinstance(snapshot.timestamp, float)
    assert isinstance(snapshot.composite_value, float)
    assert isinstance(snapshot.driver, str)


def test_collector_start_sets_is_running():
    collector = DataCollector(config={"poll_interval": 0.5})
    assert not collector.is_running()
    collector.start()
    assert collector.is_running()
    collector.stop()


def test_collector_stop_clears_is_running():
    collector = DataCollector(config={"poll_interval": 0.5})
    collector.start()
    assert collector.is_running()
    collector.stop()
    assert not collector.is_running()


def test_collector_thread_lifecycle_with_queue():
    q = queue.Queue(maxsize=10)
    collector = DataCollector(config={"poll_interval": 0.05}, snapshot_queue=q)

    assert not collector.is_running()
    collector.start()
    assert collector.is_running()

    time.sleep(0.15)
    collector.stop()
    assert not collector.is_running()
    assert q.qsize() > 0


def test_collector_start_noop_when_already_running():
    collector = DataCollector(config={"poll_interval": 0.5})
    collector.start()
    thread_before = collector._thread
    collector.start()
    assert collector._thread is thread_before
    collector.stop()


def test_collector_stop_noop_when_not_running():
    collector = DataCollector()
    assert not collector.is_running()
    collector.stop()
    assert not collector.is_running()


def test_collector_queue_eviction_on_overflow():
    q = queue.Queue(maxsize=2)
    collector = DataCollector(config={"poll_interval": 0.02}, snapshot_queue=q)

    collector.start()
    time.sleep(0.15)
    collector.stop()

    assert q.qsize() == 2


def test_collector_snapshots_in_queue_are_system_snapshots():
    q = queue.Queue(maxsize=5)
    collector = DataCollector(config={"poll_interval": 0.05}, snapshot_queue=q)
    collector.start()
    time.sleep(0.15)
    collector.stop()

    while not q.empty():
        snapshot = q.get_nowait()
        assert isinstance(snapshot, SystemSnapshot)


def test_collector_no_queue_does_not_crash():
    collector = DataCollector(config={"poll_interval": 0.05}, snapshot_queue=None)
    collector.start()
    time.sleep(0.1)
    collector.stop()
    assert not collector.is_running()


def test_system_snapshot_fields():
    snapshot = SystemSnapshot(
        timestamp=1774924800.125,
        conpty_count=8,
        process_count=240,
        memory_percent=68.5,
        handle_count=45200,
        unleashed_sessions=2,
        driver="conpty",
        composite_value=80.0,
    )
    assert snapshot.timestamp == 1774924800.125
    assert snapshot.conpty_count == 8
    assert snapshot.process_count == 240
    assert snapshot.memory_percent == 68.5
    assert snapshot.handle_count == 45200
    assert snapshot.unleashed_sessions == 2
    assert snapshot.driver == "conpty"
    assert snapshot.composite_value == 80.0


def test_collector_thread_daemon():
    collector = DataCollector(config={"poll_interval": 0.5})
    collector.start()
    assert collector._thread.daemon
    collector.stop()


def test_collector_restart_after_stop():
    collector = DataCollector(config={"poll_interval": 0.1})
    collector.start()
    assert collector.is_running()
    collector.stop()
    assert not collector.is_running()
    collector.start()
    assert collector.is_running()
    collector.stop()
    assert not collector.is_running()