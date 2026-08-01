"""Unit tests for DataCollector base class, normalization, and queue management.

Issue #4: Feature: Windows data collector — ConPTY, processes, memory, handles
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


class DummyCollector(DataCollector):
    """Dummy collector implementation for testing base class thread lifecycle."""

    def __init__(self, config=None, snapshot_queue=None, snapshot_value=50.0):
        super().__init__(config=config, snapshot_queue=snapshot_queue)
        self.snapshot_value = snapshot_value

    def collect(self) -> SystemSnapshot:
        return SystemSnapshot(
            timestamp=time.time(),
            conpty_count=5,
            process_count=100,
            memory_percent=50.0,
            handle_count=10000,
            unleashed_sessions=0,
            driver="memory",
            composite_value=self.snapshot_value,
        )


def test_normalize_metric_zero_value():
    assert normalize_metric(0.0, 100.0) == 0.0


def test_normalize_metric_negative_value():
    assert normalize_metric(-5.0, 100.0) == 0.0


def test_normalize_metric_at_threshold():
    assert normalize_metric(100.0, 100.0) == pytest.approx(100.0)


def test_normalize_metric_above_threshold():
    assert normalize_metric(120.0, 100.0) == 100.0


def test_normalize_metric_piecewise_segment_one():
    # 0 < value <= 0.6 * threshold: linear 0->60
    threshold = 100.0
    assert normalize_metric(30.0, threshold) == pytest.approx(30.0)
    assert normalize_metric(60.0, threshold) == pytest.approx(60.0)


def test_normalize_metric_piecewise_segment_two():
    # 0.6t < value <= 0.8t: linear 60->80
    threshold = 100.0
    assert normalize_metric(70.0, threshold) == pytest.approx(70.0)
    assert normalize_metric(80.0, threshold) == pytest.approx(80.0)


def test_normalize_metric_piecewise_segment_three():
    # 0.8t < value <= t: linear 80->100
    threshold = 100.0
    assert normalize_metric(90.0, threshold) == pytest.approx(90.0)
    assert normalize_metric(100.0, threshold) == pytest.approx(100.0)


def test_normalize_metric_invalid_threshold_zero():
    with pytest.raises(ValueError, match="Threshold must be positive"):
        normalize_metric(10.0, 0.0)


def test_normalize_metric_invalid_threshold_negative():
    with pytest.raises(ValueError, match="Threshold must be positive"):
        normalize_metric(10.0, -5.0)


def test_normalize_metric_conpty_example():
    # From spec: value=12.0, threshold=20.0 -> 60.0
    assert normalize_metric(12.0, 20.0) == pytest.approx(60.0)


def test_normalize_metric_mid_segment_one():
    threshold = 20.0
    # value = 6.0, t60 = 12.0 -> 6/12 * 60 = 30.0
    assert normalize_metric(6.0, 20.0) == pytest.approx(30.0)


def test_calculate_composite_metric_conpty_driver():
    thresholds = {"conpty": 20.0, "memory": 90.0, "process": 500.0, "handles": 100000.0}
    # conpty=16/20 -> 80%, memory=45/90 -> 30%
    score, driver = calculate_composite_metric(16, 45.0, 250, 30000, thresholds)
    assert score == pytest.approx(80.0)
    assert driver == "conpty"


def test_calculate_composite_metric_memory_driver():
    thresholds = {"conpty": 20.0, "memory": 90.0, "process": 500.0, "handles": 100000.0}
    # memory=81/90 -> 90%, everything else low
    score, driver = calculate_composite_metric(5, 81.0, 100, 10000, thresholds)
    assert score == pytest.approx(90.0)
    assert driver == "memory"


def test_calculate_composite_metric_process_driver():
    thresholds = {"conpty": 20.0, "memory": 90.0, "process": 500.0, "handles": 100000.0}
    # process=500/500 -> 100%
    score, driver = calculate_composite_metric(0, 0.0, 500, 0, thresholds)
    assert score == pytest.approx(100.0)
    assert driver == "process"


def test_calculate_composite_metric_handles_driver():
    thresholds = {"conpty": 20.0, "memory": 90.0, "process": 500.0, "handles": 100000.0}
    # handles=100000/100000 -> 100%
    score, driver = calculate_composite_metric(0, 0.0, 0, 100000, thresholds)
    assert score == pytest.approx(100.0)
    assert driver == "handles"


def test_calculate_composite_metric_tie_breaks_canonical_order():
    thresholds = {"conpty": 20.0, "memory": 90.0, "process": 500.0, "handles": 100000.0}
    # All at threshold -> all 100%, conpty wins (first in canonical order)
    score, driver = calculate_composite_metric(20, 90.0, 500, 100000, thresholds)
    assert score == pytest.approx(100.0)
    assert driver == "conpty"


def test_calculate_composite_metric_all_zero():
    thresholds = {"conpty": 20.0, "memory": 90.0, "process": 500.0, "handles": 100000.0}
    score, driver = calculate_composite_metric(0, 0.0, 0, 0, thresholds)
    assert score == pytest.approx(0.0)
    assert driver == "conpty"


def test_calculate_composite_metric_missing_key():
    thresholds = {"conpty": 20.0}
    with pytest.raises(KeyError):
        calculate_composite_metric(5, 50.0, 100, 10000, thresholds)


def test_calculate_composite_metric_missing_memory_key():
    thresholds = {"conpty": 20.0, "process": 500.0, "handles": 100000.0}
    with pytest.raises(KeyError):
        calculate_composite_metric(5, 50.0, 100, 10000, thresholds)


def test_collector_thread_starts_and_stops():
    collector = DummyCollector(config={"poll_interval": 0.05})
    assert not collector.is_running
    collector.start()
    assert collector.is_running
    collector.stop()
    assert not collector.is_running


def test_collector_start_idempotent():
    collector = DummyCollector(config={"poll_interval": 0.05})
    collector.start()
    assert collector.is_running
    collector.start()  # second call should be no-op
    assert collector.is_running
    collector.stop()


def test_collector_stop_when_not_running():
    collector = DummyCollector(config={"poll_interval": 0.05})
    assert not collector.is_running
    collector.stop()  # should not raise
    assert not collector.is_running


def test_collector_pushes_snapshots_to_queue():
    sq = queue.Queue(maxsize=10)
    collector = DummyCollector(config={"poll_interval": 0.05}, snapshot_queue=sq)
    collector.start()
    time.sleep(0.2)
    collector.stop()

    assert not sq.empty()
    snapshot = sq.get(block=False)
    assert isinstance(snapshot, SystemSnapshot)
    assert snapshot.composite_value == 50.0


def test_collector_queue_overflow_eviction():
    sq = queue.Queue(maxsize=2)
    collector = DummyCollector(config={"poll_interval": 0.02}, snapshot_queue=sq)
    collector.start()
    time.sleep(0.2)
    collector.stop()

    # Queue should have at most maxsize items (overflow eviction keeps it bounded)
    assert sq.qsize() <= 2


def test_collector_put_evicts_oldest_on_full():
    sq = queue.Queue(maxsize=2)
    collector = DummyCollector(snapshot_queue=sq)

    snap1 = SystemSnapshot(
        timestamp=1.0, conpty_count=1, process_count=10,
        memory_percent=10.0, handle_count=1000, unleashed_sessions=0,
        driver="conpty", composite_value=10.0,
    )
    snap2 = SystemSnapshot(
        timestamp=2.0, conpty_count=2, process_count=20,
        memory_percent=20.0, handle_count=2000, unleashed_sessions=0,
        driver="memory", composite_value=20.0,
    )
    snap3 = SystemSnapshot(
        timestamp=3.0, conpty_count=3, process_count=30,
        memory_percent=30.0, handle_count=3000, unleashed_sessions=0,
        driver="process", composite_value=30.0,
    )

    collector.put(snap1)
    collector.put(snap2)
    assert sq.qsize() == 2

    # Third put should evict snap1, leaving snap2 and snap3
    collector.put(snap3)
    assert sq.qsize() == 2

    first = sq.get(block=False)
    second = sq.get(block=False)
    assert first.composite_value == 20.0
    assert second.composite_value == 30.0


def test_collector_default_config():
    collector = DummyCollector()
    assert collector.poll_interval == 2.0
    assert collector.thresholds["conpty"] == 20.0
    assert collector.thresholds["memory"] == 90.0
    assert collector.thresholds["process"] == 500.0
    assert collector.thresholds["handles"] == 100000.0


def test_collector_custom_config():
    config = {
        "poll_interval": 1.5,
        "thresholds": {
            "conpty": 10.0,
            "memory": 80.0,
            "process": 300.0,
            "handles": 50000.0,
        },
    }
    collector = DummyCollector(config=config)
    assert collector.poll_interval == 1.5
    assert collector.thresholds["conpty"] == 10.0
    assert collector.thresholds["memory"] == 80.0
    assert collector.thresholds["process"] == 300.0
    assert collector.thresholds["handles"] == 50000.0


def test_collector_base_collect_raises():
    collector = DataCollector()
    with pytest.raises(NotImplementedError):
        collector.collect()


def test_snapshot_dataclass_fields():
    snap = SystemSnapshot(
        timestamp=1785584920.125,
        conpty_count=12,
        process_count=284,
        memory_percent=74.2,
        handle_count=45120,
        unleashed_sessions=3,
        driver="conpty",
        composite_value=80.0,
    )
    assert snap.timestamp == 1785584920.125
    assert snap.conpty_count == 12
    assert snap.process_count == 284
    assert snap.memory_percent == 74.2
    assert snap.handle_count == 45120
    assert snap.unleashed_sessions == 3
    assert snap.driver == "conpty"
    assert snap.composite_value == 80.0