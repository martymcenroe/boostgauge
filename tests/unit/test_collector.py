"""Unit test suite for base DataCollector and composite metric calculations.

Issue #4: Feature: Windows data collector — ConPTY, processes, memory, handles
"""

import queue
import time
from typing import Any, Dict, Optional
import pytest

from boostgauge.collector import (
    DEFAULT_THRESHOLDS,
    DataCollector,
    SystemSnapshot,
    calculate_composite_metric,
    normalize_metric,
)


class DummyCollector(DataCollector):
    """Concrete DummyCollector for testing base class behavior."""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        snapshot_queue: Optional[queue.Queue[SystemSnapshot]] = None,
        fail_poll: bool = False,
    ) -> None:
        super().__init__(config=config, snapshot_queue=snapshot_queue)
        self.fail_poll = fail_poll
        self.poll_count = 0

    def poll_metrics(self) -> SystemSnapshot:
        self.poll_count += 1
        if self.fail_poll:
            raise RuntimeError("Simulated polling exception")
        return SystemSnapshot(
            timestamp=time.time(),
            conpty_count=10,
            process_count=100,
            memory_percent=45.0,
            handle_count=10000,
            unleashed_sessions=1,
            driver="conpty",
            composite_value=50.0,
        )


def test_normalize_metric_basic() -> None:
    assert normalize_metric(10.0, 20.0) == 50.0


def test_normalize_metric_zero_value() -> None:
    assert normalize_metric(0.0, 20.0) == 0.0


def test_normalize_metric_zero_threshold() -> None:
    assert normalize_metric(10.0, 0.0) == 0.0


def test_normalize_metric_negative_threshold() -> None:
    assert normalize_metric(10.0, -5.0) == 0.0


def test_normalize_metric_clamp_above_threshold() -> None:
    assert normalize_metric(25.0, 20.0) == 100.0


def test_normalize_metric_at_threshold() -> None:
    assert normalize_metric(20.0, 20.0) == 100.0


def test_calculate_composite_metric_conpty_driver() -> None:
    thresholds = {"conpty": 20.0, "memory": 100.0, "process": 500.0, "handles": 100000.0}
    val, driver = calculate_composite_metric(15, 50.0, 100, 10000, thresholds)
    assert val == 75.0
    assert driver == "conpty"


def test_calculate_composite_metric_memory_driver() -> None:
    thresholds = {"conpty": 20.0, "memory": 100.0, "process": 500.0, "handles": 100000.0}
    val, driver = calculate_composite_metric(5, 90.0, 100, 10000, thresholds)
    assert val == 90.0
    assert driver == "memory"


def test_calculate_composite_metric_process_driver() -> None:
    thresholds = {"conpty": 20.0, "memory": 90.0, "process": 200.0, "handles": 100000.0}
    val, driver = calculate_composite_metric(1, 10.0, 200, 10000, thresholds)
    assert val == 100.0
    assert driver == "process"


def test_calculate_composite_metric_handles_driver() -> None:
    thresholds = {"conpty": 20.0, "memory": 90.0, "process": 500.0, "handles": 10000.0}
    val, driver = calculate_composite_metric(1, 10.0, 50, 10000, thresholds)
    assert val == 100.0
    assert driver == "handles"


def test_calculate_composite_metric_tie_breaker_conpty_wins() -> None:
    # All equal normalized scores -> conpty wins by priority
    thresholds = {"conpty": 100.0, "memory": 100.0, "process": 100.0, "handles": 100.0}
    val, driver = calculate_composite_metric(50, 50.0, 50, 50, thresholds)
    assert val == 50.0
    assert driver == "conpty"


def test_calculate_composite_metric_missing_threshold_key() -> None:
    # Missing key falls back to DEFAULT_THRESHOLDS value
    val, driver = calculate_composite_metric(20, 45.0, 200, 30000, {})
    assert isinstance(val, float)
    assert driver in ("conpty", "memory", "process", "handles")


def test_calculate_composite_metric_all_zero() -> None:
    thresholds = {"conpty": 20.0, "memory": 90.0, "process": 500.0, "handles": 100000.0}
    val, driver = calculate_composite_metric(0, 0.0, 0, 0, thresholds)
    assert val == 0.0
    assert driver == "conpty"


def test_default_thresholds_keys() -> None:
    assert "conpty" in DEFAULT_THRESHOLDS
    assert "memory" in DEFAULT_THRESHOLDS
    assert "process" in DEFAULT_THRESHOLDS
    assert "handles" in DEFAULT_THRESHOLDS


def test_collector_default_config() -> None:
    collector = DummyCollector()
    assert collector.poll_interval == 2.0
    assert collector.thresholds == DEFAULT_THRESHOLDS
    assert collector.snapshot_queue.maxsize == 100


def test_collector_custom_poll_interval() -> None:
    collector = DummyCollector(config={"poll_interval": 1.5})
    assert collector.poll_interval == 1.5


def test_collector_custom_threshold_override() -> None:
    collector = DummyCollector(config={"thresholds": {"conpty": 25.0}})
    assert collector.thresholds["conpty"] == 25.0
    assert collector.thresholds["memory"] == DEFAULT_THRESHOLDS["memory"]


def test_collector_custom_queue() -> None:
    q: queue.Queue[SystemSnapshot] = queue.Queue(maxsize=50)
    collector = DummyCollector(snapshot_queue=q)
    assert collector.snapshot_queue is q
    assert collector.snapshot_queue.maxsize == 50


def test_collector_thread_lifecycle_and_queue() -> None:
    q: queue.Queue[SystemSnapshot] = queue.Queue(maxsize=10)
    collector = DummyCollector(config={"poll_interval": 0.05}, snapshot_queue=q)

    collector.start()
    time.sleep(0.15)
    collector.stop(timeout=1.0)

    assert not collector._thread.is_alive()
    assert q.qsize() >= 1
    snapshot = q.get_nowait()
    assert isinstance(snapshot, SystemSnapshot)
    assert snapshot.conpty_count == 10


def test_collector_start_idempotent() -> None:
    collector = DummyCollector(config={"poll_interval": 0.05})
    collector.start()
    thread_before = collector._thread
    collector.start()
    assert collector._thread is thread_before
    collector.stop(timeout=1.0)


def test_collector_stop_before_start() -> None:
    collector = DummyCollector()
    # Should not raise
    collector.stop(timeout=0.1)


def test_collector_queue_overflow_evicts_oldest() -> None:
    q: queue.Queue[SystemSnapshot] = queue.Queue(maxsize=2)
    collector = DummyCollector(config={"poll_interval": 0.02}, snapshot_queue=q)

    collector.start()
    time.sleep(0.1)
    collector.stop(timeout=1.0)

    assert q.qsize() == 2


def test_collector_unhandled_exception_resilience() -> None:
    collector = DummyCollector(config={"poll_interval": 0.02}, fail_poll=True)
    collector.start()
    time.sleep(0.08)
    collector.stop(timeout=1.0)

    assert collector.poll_count >= 2


def test_collector_poll_metrics_not_implemented() -> None:
    collector = DataCollector()
    with pytest.raises(NotImplementedError):
        collector.poll_metrics()


def test_collector_thread_stops_cleanly() -> None:
    collector = DummyCollector(config={"poll_interval": 0.05})
    collector.start()
    assert collector._thread is not None
    assert collector._thread.is_alive()
    collector.stop(timeout=1.0)
    assert not collector._thread.is_alive()


def test_collector_snapshot_fields() -> None:
    collector = DummyCollector(config={"poll_interval": 0.05})
    snapshot = collector.poll_metrics()

    assert isinstance(snapshot.timestamp, float)
    assert isinstance(snapshot.conpty_count, int)
    assert isinstance(snapshot.process_count, int)
    assert isinstance(snapshot.memory_percent, float)
    assert isinstance(snapshot.handle_count, int)
    assert isinstance(snapshot.unleashed_sessions, int)
    assert isinstance(snapshot.driver, str)
    assert isinstance(snapshot.composite_value, float)


def test_collector_invalid_threshold_type_ignored() -> None:
    # Non-numeric threshold values should be ignored, keeping defaults
    collector = DummyCollector(config={"thresholds": {"conpty": "bad_value"}})
    assert collector.thresholds["conpty"] == DEFAULT_THRESHOLDS["conpty"]


def test_collector_unknown_threshold_key_ignored() -> None:
    collector = DummyCollector(config={"thresholds": {"unknown_key": 42.0}})
    assert "unknown_key" not in collector.thresholds


def test_collector_queue_receives_valid_snapshot_data() -> None:
    q: queue.Queue[SystemSnapshot] = queue.Queue(maxsize=10)
    collector = DummyCollector(config={"poll_interval": 0.05}, snapshot_queue=q)

    collector.start()
    time.sleep(0.12)
    collector.stop(timeout=1.0)

    snapshot = q.get_nowait()
    assert snapshot.process_count == 100
    assert snapshot.memory_percent == 45.0
    assert snapshot.handle_count == 10000
    assert snapshot.unleashed_sessions == 1
    assert snapshot.driver == "conpty"
    assert snapshot.composite_value == 50.0