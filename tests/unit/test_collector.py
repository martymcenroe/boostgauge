"""Unit tests for collector abstraction.

Issue #4
"""
import pytest
import psutil
from boostgauge.collector import DataCollector, SystemSnapshot, WindowsCollector


class DummyCollector(DataCollector):
    def collect(self):
        return SystemSnapshot(
            timestamp=1.0, conpty_count=0, process_count=0,
            memory_percent=0.0, handle_count=0, unleashed_sessions=0,
            driver="none", composite_value=0.0
        )


def test_normalize():
    collector = DummyCollector({})
    band = {"yellow": 60.0, "red": 80.0}
    assert collector._normalize(30.0, band) == 30.0
    assert collector._normalize(70.0, band) == 70.0
    assert collector._normalize(90.0, band) == 82.5


def test_compute_composite():
    thresholds = {
        "conpty": {"yellow": 10.0, "red": 20.0},
        "memory_percent": {"yellow": 60.0, "red": 80.0}
    }
    collector = DummyCollector(thresholds)

    val, driver = collector._compute_composite({
        "conpty": 15,
        "memory_percent": 50.0
    })
    assert val == 70.0
    assert driver == "conpty"


def test_req_5():
    collector = DummyCollector({}, poll_interval=0.01)
    collector.start()
    assert collector._thread.is_alive()
    collector.stop()


def test_req_9():
    collector = DummyCollector({"conpty": {"yellow": 10.0, "red": 20.0}})
    val, driver = collector._compute_composite({"conpty": 15.0})
    assert driver == "conpty"
    assert val == 70.0


def test_value_error():
    with pytest.raises(ValueError):
        DummyCollector({}, poll_interval=-1.0)


def test_not_implemented_error():
    with pytest.raises(NotImplementedError):
        DataCollector.collect(None)


def test_normalize_below_yellow():
    collector = DummyCollector({})
    band = {"yellow": 10.0, "red": 20.0}
    assert collector._normalize(0.0, band) == 0.0
    assert collector._normalize(5.0, band) == 30.0


def test_normalize_equal_yellow_red():
    collector = DummyCollector({})
    band = {"yellow": 50.0, "red": 50.0}
    assert collector._normalize(50.0, band) == 100.0
    assert collector._normalize(49.0, band) == 0.0


def test_compute_composite_empty():
    collector = DummyCollector({})
    val, driver = collector._compute_composite({})
    assert val == 0.0
    assert driver == "none"


def test_compute_composite_no_matching_thresholds():
    collector = DummyCollector({"conpty": {"yellow": 10.0, "red": 20.0}})
    val, driver = collector._compute_composite({"memory_percent": 90.0})
    assert val == 0.0
    assert driver == "none"


def test_get_latest_snapshot_before_start():
    collector = DummyCollector({})
    assert collector.get_latest_snapshot() is None


def test_start_idempotent():
    collector = DummyCollector({}, poll_interval=0.01)
    collector.start()
    thread1 = collector._thread
    collector.start()
    thread2 = collector._thread
    assert thread1 is thread2
    collector.stop()


def test_stop_when_not_running():
    collector = DummyCollector({})
    collector.stop()


def test_poll_loop_updates_snapshot():
    import time
    collector = DummyCollector({}, poll_interval=0.01)
    collector.start()
    time.sleep(0.05)
    collector.stop()
    assert collector.get_latest_snapshot() is not None


def test_normalize_above_red():
    collector = DummyCollector({})
    band = {"yellow": 10.0, "red": 20.0}
    result = collector._normalize(30.0, band)
    assert result > 80.0
    assert result <= 100.0


def test_normalize_capped_at_100():
    collector = DummyCollector({})
    band = {"yellow": 10.0, "red": 20.0}
    result = collector._normalize(1000.0, band)
    assert result == 100.0