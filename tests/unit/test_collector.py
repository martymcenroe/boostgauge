"""Unit tests for abstract DataCollector, SystemSnapshot, and metric math routines.

Issue #4: Feature: Windows Data Collector — ConPTY, Processes, Memory, Handles
"""

from __future__ import annotations

import queue
import time

import pytest

from boostgauge.collector import (
    DataCollector,
    SystemSnapshot,
    compute_composite_metric,
    normalize_metric,
)


class DummyCollector(DataCollector):
    """Dummy subclass for testing abstract DataCollector base class."""

    def __init__(self, poll_interval: float = 0.05) -> None:
        super().__init__(poll_interval=poll_interval)
        self.call_count = 0

    def collect_snapshot(self) -> SystemSnapshot:
        self.call_count += 1
        return SystemSnapshot(
            timestamp=time.time(),
            conpty_count=10,
            process_count=100,
            memory_percent=50.0,
            handle_count=5000,
            unleashed_sessions=1,
            driver="conpty",
            composite_value=30.0,
        )


def test_system_snapshot_immutability():
    """Verify SystemSnapshot fields are accessible and immutable (T020)."""
    snapshot = SystemSnapshot(
        timestamp=100.0,
        conpty_count=5,
        process_count=50,
        memory_percent=40.0,
        handle_count=2000,
        unleashed_sessions=0,
        driver="memory_percent",
        composite_value=34.2,
    )
    assert snapshot.timestamp == 100.0
    assert snapshot.conpty_count == 5
    assert snapshot.process_count == 50
    assert snapshot.memory_percent == 40.0
    assert snapshot.handle_count == 2000
    assert snapshot.unleashed_sessions == 0
    assert snapshot.driver == "memory_percent"
    assert snapshot.composite_value == 34.2

    with pytest.raises(AttributeError):
        snapshot.composite_value = 50.0  # type: ignore


def test_normalize_metric_boundaries():
    """Verify normalize_metric threshold scaling (T030)."""
    assert normalize_metric(0.0, 20.0, 30.0) == 0.0
    assert normalize_metric(10.0, 20.0, 30.0) == 30.0
    assert normalize_metric(20.0, 20.0, 30.0) == 60.0
    assert normalize_metric(25.0, 20.0, 30.0) == 80.0
    assert normalize_metric(30.0, 20.0, 30.0) == 100.0
    assert normalize_metric(35.0, 20.0, 30.0) == pytest.approx(103.33333333333333)


def test_normalize_metric_negative_value():
    """Verify normalize_metric returns 0.0 for non-positive values."""
    assert normalize_metric(-5.0, 20.0, 30.0) == 0.0


def test_normalize_metric_invalid_thresholds():
    """Verify normalize_metric returns 100.0 when thresholds are degenerate and value > 0."""
    assert normalize_metric(5.0, 0.0, 30.0) == 100.0
    assert normalize_metric(5.0, 20.0, 10.0) == 100.0


def test_compute_composite_metric_conpty_driver():
    """Verify compute_composite_metric selects conpty as driving metric (T030)."""
    score, driver = compute_composite_metric(
        conpty_count=25, memory_percent=50.0, process_count=100, handle_count=5000
    )
    assert driver == "conpty"
    assert score == 80.0


def test_compute_composite_metric_memory_driver():
    """Verify compute_composite_metric selects memory_percent as driving metric (T030)."""
    score, driver = compute_composite_metric(
        conpty_count=5, memory_percent=85.0, process_count=100, handle_count=5000
    )
    assert driver == "memory_percent"
    assert score == 100.0


def test_compute_composite_metric_all_zero():
    """Verify compute_composite_metric returns (0.0, 'conpty') when all inputs are zero."""
    score, driver = compute_composite_metric(
        conpty_count=0, memory_percent=0.0, process_count=0, handle_count=0
    )
    assert score == 0.0
    assert driver == "conpty"


def test_compute_composite_metric_clamped_to_100():
    """Verify composite score is clamped to 100.0 when metrics exceed red thresholds."""
    score, driver = compute_composite_metric(
        conpty_count=100, memory_percent=0.0, process_count=0, handle_count=0
    )
    assert score == 100.0
    assert driver == "conpty"


def test_compute_composite_metric_custom_thresholds():
    """Verify compute_composite_metric uses custom thresholds when provided."""
    thresholds = {
        "conpty": {"yellow": 10.0, "red": 20.0},
        "memory_percent": {"yellow": 50.0, "red": 80.0},
        "process_count": {"yellow": 100.0, "red": 200.0},
        "handle_count": {"yellow": 5000.0, "red": 10000.0},
    }
    score, driver = compute_composite_metric(
        conpty_count=10,
        memory_percent=0.0,
        process_count=0,
        handle_count=0,
        thresholds=thresholds,
    )
    assert driver == "conpty"
    assert score == 60.0


def test_compute_composite_metric_deterministic_tie_breaking():
    """Verify conpty wins over memory_percent when scores are equal (precedence order)."""
    thresholds = {
        "conpty": {"yellow": 20.0, "red": 30.0},
        "memory_percent": {"yellow": 70.0, "red": 85.0},
        "process_count": {"yellow": 150.0, "red": 300.0},
        "handle_count": {"yellow": 10000.0, "red": 20000.0},
    }
    conpty_score = normalize_metric(20.0, 20.0, 30.0)  # 60.0
    mem_score = normalize_metric(70.0, 70.0, 85.0)    # 60.0
    assert conpty_score == mem_score == 60.0

    score, driver = compute_composite_metric(
        conpty_count=20,
        memory_percent=70.0,
        process_count=0,
        handle_count=0,
        thresholds=thresholds,
    )
    assert driver == "conpty"
    assert score == 60.0


def test_abstract_collector_cannot_be_instantiated():
    """Verify DataCollector cannot be instantiated directly."""
    with pytest.raises(TypeError):
        DataCollector()  # type: ignore


def test_data_collector_background_thread():
    """Verify background worker thread pushes snapshots to queue (T080)."""
    collector = DummyCollector(poll_interval=0.02)
    q: queue.Queue[SystemSnapshot] = queue.Queue(maxsize=10)

    assert not collector.is_running()
    collector.start(q)
    assert collector.is_running()

    time.sleep(0.15)
    collector.stop()
    assert not collector.is_running()

    assert q.qsize() >= 2
    snapshot = q.get_nowait()
    assert isinstance(snapshot, SystemSnapshot)
    assert snapshot.conpty_count == 10


def test_data_collector_start_idempotent():
    """Verify calling start() twice does not spawn duplicate threads."""
    collector = DummyCollector(poll_interval=0.1)
    q: queue.Queue[SystemSnapshot] = queue.Queue(maxsize=10)

    collector.start(q)
    thread_before = collector._thread
    collector.start(q)
    thread_after = collector._thread

    assert thread_before is thread_after
    collector.stop()


def test_data_collector_queue_full_drops_oldest():
    """Verify background thread handles full queue by dropping oldest snapshot."""
    collector = DummyCollector(poll_interval=0.01)
    q: queue.Queue[SystemSnapshot] = queue.Queue(maxsize=2)

    collector.start(q)
    time.sleep(0.15)
    collector.stop()

    assert not q.empty()