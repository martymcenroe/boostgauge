"""Unit tests for base DataCollector, composite value calculation, and metric normalization.

Issue #4: Feature: Windows Data Collector — ConPTY, Processes, Memory, Handles
"""

from __future__ import annotations

import time
import pytest
from boostgauge.collector import (
    DataCollector,
    SystemSnapshot,
    calculate_composite_value,
    normalize_metric,
)


def test_normalize_metric_scaling_and_clamping() -> None:
    assert normalize_metric(45.0, 90.0) == 50.0
    assert normalize_metric(10.0, 10.0) == 100.0
    assert normalize_metric(15.0, 10.0) == 100.0
    assert normalize_metric(0.0, 90.0) == 0.0
    assert normalize_metric(-5.0, 90.0) == 0.0
    assert normalize_metric(50.0, 0.0) == 0.0


def test_calculate_composite_value_driver_selection() -> None:
    val, driver = calculate_composite_value(
        conpty_count=8,
        memory_percent=45.0,
        process_count=200,
        handle_count=20000,
    )
    assert val == 80.0
    assert driver == "conpty"

    val, driver = calculate_composite_value(
        conpty_count=2,
        memory_percent=81.0,
        process_count=100,
        handle_count=10000,
    )
    assert val == 90.0
    assert driver == "memory"


def test_calculate_composite_value_tie_breaking() -> None:
    val, driver = calculate_composite_value(
        conpty_count=5,
        memory_percent=45.0,
        process_count=100,
        handle_count=10000,
        thresholds={"conpty": 10.0, "memory": 90.0},
    )
    assert val == 50.0
    assert driver == "conpty"


def test_calculate_composite_value_all_zero_returns_conpty_driver() -> None:
    val, driver = calculate_composite_value(
        conpty_count=0,
        memory_percent=0.0,
        process_count=0,
        handle_count=0,
    )
    assert val == 0.0
    assert driver == "conpty"


def test_calculate_composite_value_missing_threshold_uses_defaults() -> None:
    val, driver = calculate_composite_value(
        conpty_count=9,
        memory_percent=0.0,
        process_count=0,
        handle_count=0,
        thresholds={},
    )
    assert val == 90.0
    assert driver == "conpty"


def test_calculate_composite_value_clamped_at_100() -> None:
    val, driver = calculate_composite_value(
        conpty_count=100,
        memory_percent=0.0,
        process_count=0,
        handle_count=0,
    )
    assert val == 100.0
    assert driver == "conpty"


def test_queue_overflow_drops_oldest_snapshot() -> None:
    collector = DataCollector(poll_interval=0.05)
    for i in range(15):
        snap = SystemSnapshot(
            timestamp=float(i),
            conpty_count=i,
            process_count=100,
            memory_percent=50.0,
            handle_count=1000,
            unleashed_sessions=0,
            driver="memory",
            composite_value=50.0,
        )
        collector._push_snapshot(snap)

    latest = collector.get_latest_snapshot()
    assert latest is not None
    assert latest.conpty_count == 14


def test_get_latest_snapshot_returns_none_before_first_collection() -> None:
    collector = DataCollector(poll_interval=60.0)
    assert collector.get_latest_snapshot() is None


def test_lifecycle_start_stop() -> None:
    collector = DataCollector(config={"poll_interval": 0.1})
    assert not collector.is_running()

    collector.start()
    assert collector.is_running()

    time.sleep(0.3)
    snapshot = collector.get_latest_snapshot()
    assert snapshot is not None
    assert isinstance(snapshot, SystemSnapshot)

    collector.stop()
    assert not collector.is_running()


def test_start_idempotent() -> None:
    collector = DataCollector(config={"poll_interval": 0.1})
    collector.start()
    collector.start()
    assert collector.is_running()
    collector.stop()


def test_config_poll_interval_override() -> None:
    collector = DataCollector(config={"poll_interval": 5.0})
    assert collector.poll_interval == 5.0


def test_system_snapshot_is_frozen() -> None:
    snap = SystemSnapshot(
        timestamp=1.0,
        conpty_count=0,
        process_count=0,
        memory_percent=0.0,
        handle_count=0,
        unleashed_sessions=0,
        driver="conpty",
        composite_value=0.0,
    )
    with pytest.raises((AttributeError, TypeError)):
        snap.conpty_count = 5  # type: ignore[misc]


def test_collect_snapshot_returns_system_snapshot() -> None:
    collector = DataCollector()
    now = time.time()
    snapshot = collector.collect_snapshot(now)

    assert isinstance(snapshot, SystemSnapshot)
    assert snapshot.timestamp == pytest.approx(now, abs=1.0)
    assert snapshot.conpty_count == 0
    assert snapshot.process_count >= 0
    assert 0.0 <= snapshot.memory_percent <= 100.0
    assert snapshot.handle_count >= 0
    assert snapshot.unleashed_sessions == 0
    assert snapshot.driver in ("conpty", "memory", "process", "handle")
    assert 0.0 <= snapshot.composite_value <= 100.0


def test_slow_metrics_staggered_after_5s() -> None:
    collector = DataCollector(config={"poll_interval": 0.1})

    early_ts = time.time()
    snapshot1 = collector.collect_snapshot(early_ts)

    later_ts = early_ts + 6.0
    snapshot2 = collector.collect_snapshot(later_ts)

    assert isinstance(snapshot1, SystemSnapshot)
    assert isinstance(snapshot2, SystemSnapshot)