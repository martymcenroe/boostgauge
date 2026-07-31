"""Unit tests for abstract DataCollector base class, normalization, and queueing.

Issue #4: Windows data collector — ConPTY, processes, memory, handles
"""

import queue
import time
from typing import Any, Dict
import pytest

from boostgauge.collector import (
    DataCollector,
    SystemSnapshot,
    normalize_metric,
    calculate_composite_metric,
)


class DummyCollector(DataCollector):
    def __init__(self, raw_metrics=None, **kwargs):
        super().__init__(**kwargs)
        self.raw_metrics = raw_metrics or {
            "conpty_count": 10,
            "process_count": 100,
            "memory_percent": 50.0,
            "handle_count": 10000,
            "unleashed_sessions": 1,
        }

    def _collect_raw_metrics(self) -> Dict[str, Any]:
        return self.raw_metrics


def test_normalize_metric_zero_value():
    assert normalize_metric(0.0, 100.0) == 0.0


def test_normalize_metric_negative_value():
    assert normalize_metric(-10.0, 100.0) == 0.0


def test_normalize_metric_zero_threshold():
    assert normalize_metric(50.0, 0.0) == 0.0


def test_normalize_metric_negative_threshold():
    assert normalize_metric(50.0, -1.0) == 0.0


def test_normalize_metric_at_threshold():
    assert normalize_metric(100.0, 100.0) == 100.0


def test_normalize_metric_exceeds_threshold():
    assert normalize_metric(150.0, 100.0) == 100.0


def test_normalize_metric_sixty_percent():
    assert normalize_metric(60.0, 100.0) == 60.0


def test_normalize_metric_eighty_percent():
    assert normalize_metric(80.0, 100.0) == 80.0


def test_normalize_metric_half_threshold():
    result = normalize_metric(30.0, 50.0)
    assert result == 60.0


def test_calculate_composite_metric_conpty_driver():
    thresholds = {"conpty": 50.0, "memory": 90.0, "process": 500.0, "handles": 100000.0}
    comp, driver = calculate_composite_metric(40, 30.0, 100, 500, thresholds)
    assert comp == 80.0
    assert driver == "conpty"


def test_calculate_composite_metric_memory_driver():
    thresholds = {"conpty": 50.0, "memory": 90.0, "process": 500.0, "handles": 100000.0}
    comp, driver = calculate_composite_metric(10, 81.0, 100, 500, thresholds)
    assert comp == 90.0
    assert driver == "memory"


def test_calculate_composite_metric_process_driver():
    thresholds = {"conpty": 50.0, "memory": 90.0, "process": 500.0, "handles": 100000.0}
    comp, driver = calculate_composite_metric(0, 0.0, 500, 0, thresholds)
    assert comp == 100.0
    assert driver == "process"


def test_calculate_composite_metric_handle_driver():
    thresholds = {"conpty": 50.0, "memory": 90.0, "process": 500.0, "handles": 100000.0}
    comp, driver = calculate_composite_metric(0, 0.0, 0, 100000, thresholds)
    assert comp == 100.0
    assert driver == "handle"


def test_calculate_composite_metric_all_zero():
    thresholds = {"conpty": 50.0, "memory": 90.0, "process": 500.0, "handles": 100000.0}
    comp, driver = calculate_composite_metric(0, 0.0, 0, 0, thresholds)
    assert comp == 0.0
    assert driver == "conpty"


def test_calculate_composite_metric_tie_prefers_conpty():
    thresholds = {"conpty": 50.0, "memory": 90.0, "process": 500.0, "handles": 100000.0}
    # conpty norm = 100, memory norm = 100 — tie resolved by precedence
    comp, driver = calculate_composite_metric(50, 90.0, 0, 0, thresholds)
    assert comp == 100.0
    assert driver == "conpty"


def test_calculate_composite_metric_tie_prefers_memory_over_process():
    thresholds = {"conpty": 50.0, "memory": 90.0, "process": 500.0, "handles": 100000.0}
    # memory norm = 100, process norm = 100, conpty = 0 — memory wins
    comp, driver = calculate_composite_metric(0, 90.0, 500, 0, thresholds)
    assert comp == 100.0
    assert driver == "memory"


def test_calculate_composite_metric_specific_values():
    thresholds = {"conpty": 50.0, "memory": 90.0, "process": 500.0, "handles": 100000.0}
    # ConPTY=40 -> 80, Memory=30% -> 33.33, Proc=100 -> 20, Handles=500 -> 0.5
    comp, driver = calculate_composite_metric(40, 30.0, 100, 500, thresholds)
    assert comp == 80.0
    assert driver == "conpty"


def test_collector_poll_returns_snapshot():
    collector = DummyCollector()
    snapshot = collector.poll()
    assert isinstance(snapshot, SystemSnapshot)
    assert snapshot.conpty_count == 10
    assert snapshot.process_count == 100
    assert snapshot.memory_percent == 50.0
    assert snapshot.handle_count == 10000
    assert snapshot.unleashed_sessions == 1
    assert isinstance(snapshot.timestamp, float)
    assert isinstance(snapshot.driver, str)
    assert 0.0 <= snapshot.composite_value <= 100.0


def test_collector_poll_timestamp_is_recent():
    collector = DummyCollector()
    before = time.time()
    snapshot = collector.poll()
    after = time.time()
    assert before <= snapshot.timestamp <= after


def test_collector_not_running_before_start():
    collector = DummyCollector()
    assert not collector.is_running()


def test_collector_thread_start():
    collector = DummyCollector(config={"poll_interval": 0.1})
    collector.start()
    try:
        assert collector.is_running()
    finally:
        collector.stop()


def test_collector_thread_stop():
    collector = DummyCollector(config={"poll_interval": 0.05})
    collector.start()
    collector.stop()
    assert not collector.is_running()


def test_collector_start_idempotent():
    collector = DummyCollector(config={"poll_interval": 0.1})
    collector.start()
    thread_before = collector._thread
    collector.start()
    thread_after = collector._thread
    try:
        assert thread_before is thread_after
    finally:
        collector.stop()


def test_collector_stop_when_not_running():
    collector = DummyCollector()
    # Should not raise
    collector.stop()
    assert not collector.is_running()


def test_collector_thread_pushes_to_queue():
    q = queue.Queue(maxsize=10)
    collector = DummyCollector(config={"poll_interval": 0.05}, snapshot_queue=q)

    collector.start()
    time.sleep(0.2)
    collector.stop()

    assert not q.empty()
    item = q.get_nowait()
    assert isinstance(item, SystemSnapshot)
    assert item.conpty_count == 10


def test_collector_no_queue_does_not_raise():
    collector = DummyCollector(config={"poll_interval": 0.05}, snapshot_queue=None)
    collector.start()
    time.sleep(0.15)
    collector.stop()
    assert not collector.is_running()


def test_snapshot_queue_full_eviction():
    q = queue.Queue(maxsize=2)
    collector = DummyCollector(config={"poll_interval": 0.01}, snapshot_queue=q)

    collector.start()
    time.sleep(0.1)
    collector.stop()

    assert q.qsize() == 2


def test_snapshot_queue_eviction_keeps_newest():
    q = queue.Queue(maxsize=1)
    collector = DummyCollector(config={"poll_interval": 0.01}, snapshot_queue=q)

    collector.start()
    time.sleep(0.08)
    collector.stop()

    assert q.qsize() == 1
    snapshot = q.get_nowait()
    assert isinstance(snapshot, SystemSnapshot)


def test_collector_worker_loop_exception_resilience():
    call_count = 0

    class FlakyCollector(DataCollector):
        def _collect_raw_metrics(self) -> Dict[str, Any]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("transient failure")
            return {
                "conpty_count": 5,
                "process_count": 50,
                "memory_percent": 25.0,
                "handle_count": 5000,
                "unleashed_sessions": 0,
            }

    q = queue.Queue(maxsize=10)
    collector = FlakyCollector(config={"poll_interval": 0.03}, snapshot_queue=q)

    collector.start()
    time.sleep(0.15)
    collector.stop()

    assert not q.empty()
    snapshot = q.get_nowait()
    assert snapshot.conpty_count == 5


def test_collector_default_thresholds():
    collector = DummyCollector()
    assert collector.thresholds["conpty"] == 50.0
    assert collector.thresholds["memory"] == 90.0
    assert collector.thresholds["process"] == 500.0
    assert collector.thresholds["handles"] == 100000.0


def test_collector_custom_thresholds():
    config = {"thresholds": {"conpty": 20.0, "memory": 80.0}}
    collector = DummyCollector(config=config)
    assert collector.thresholds["conpty"] == 20.0
    assert collector.thresholds["memory"] == 80.0
    assert collector.thresholds["process"] == 500.0
    assert collector.thresholds["handles"] == 100000.0


def test_collector_custom_poll_interval():
    config = {"poll_interval": 5.0}
    collector = DummyCollector(config=config)
    assert collector.poll_interval == 5.0


def test_collector_default_poll_interval():
    collector = DummyCollector()
    assert collector.poll_interval == 2.0


def test_system_snapshot_fields():
    snapshot = SystemSnapshot(
        timestamp=1000.0,
        conpty_count=5,
        process_count=200,
        memory_percent=65.0,
        handle_count=30000,
        unleashed_sessions=2,
        driver="memory",
        composite_value=72.2,
    )
    assert snapshot.timestamp == 1000.0
    assert snapshot.conpty_count == 5
    assert snapshot.process_count == 200
    assert snapshot.memory_percent == 65.0
    assert snapshot.handle_count == 30000
    assert snapshot.unleashed_sessions == 2
    assert snapshot.driver == "memory"
    assert snapshot.composite_value == 72.2


def test_collector_composite_value_in_range():
    raw_metrics = {
        "conpty_count": 100,
        "process_count": 1000,
        "memory_percent": 99.9,
        "handle_count": 200000,
        "unleashed_sessions": 10,
    }
    collector = DummyCollector(raw_metrics=raw_metrics)
    snapshot = collector.poll()
    assert 0.0 <= snapshot.composite_value <= 100.0


def test_collector_driver_is_valid_string():
    collector = DummyCollector()
    snapshot = collector.poll()
    assert snapshot.driver in ("conpty", "memory", "process", "handle")