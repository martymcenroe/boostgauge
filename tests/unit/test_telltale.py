"""Unit tests for telltale peak-hold needle logic module.

Issue #41: Feature: Telltale peak-hold needle logic (pure, no GUI)
"""

import time
import pytest

from boostgauge.telltale import Sample, Telltale


def test_t010_initialization_validation() -> None:
    """Test initialization parameters validation and attribute storage (REQ-1)."""
    t = Telltale(window=10.0, decay_rate=15.0)
    assert t.window == 10.0
    assert t.decay_rate == 15.0

    t_default = Telltale(window=5.0)
    assert t_default.window == 5.0
    assert t_default.decay_rate is None

    t_zero_decay = Telltale(window=5.0, decay_rate=0.0)
    assert t_zero_decay.decay_rate == 0.0

    with pytest.raises(ValueError, match="Window duration must be positive"):
        Telltale(window=0.0)

    with pytest.raises(ValueError, match="Window duration must be positive"):
        Telltale(window=-1.0)

    with pytest.raises(ValueError, match="Decay rate cannot be negative"):
        Telltale(window=10.0, decay_rate=-5.0)


def test_t020_stream_update_throughput() -> None:
    """Test high-frequency update stream throughput (REQ-2)."""
    t = Telltale(window=60.0, decay_rate=1.0)
    start_time = time.perf_counter()

    for i in range(10_000):
        t.update(timestamp=i * 0.01, value=float(i % 100))
        _ = t.current_peak()

    elapsed = time.perf_counter() - start_time
    assert elapsed < 0.5, f"10,000 updates took {elapsed:.4f}s (budget < 0.5s)"


def test_t030_instant_peak_elevation() -> None:
    """Test rising sample series immediately elevates peak (REQ-3)."""
    t = Telltale(window=10.0)
    t.update(0.0, 10.0)
    assert t.current_peak() == 10.0

    t.update(1.0, 20.0)
    assert t.current_peak() == 20.0

    t.update(2.0, 50.0)
    assert t.current_peak() == 50.0


def test_t031_new_sample_exceeding_decayed_peak_resets_upward() -> None:
    """Test new sample exceeding decayed peak resets peak upward immediately (REQ-3)."""
    t = Telltale(window=10.0, decay_rate=15.0)
    t.update(0.0, 100.0)
    assert t.current_peak(12.0) == 70.0  # Decayed from 100 to 70 at t=12

    t.update(12.1, 80.0)
    assert t.current_peak() == 80.0  # Resets upward immediately to 80


def test_t040_hard_hold_peak_drop_to_window_max() -> None:
    """Test peak drops instantly to window max when peak ages out with decay_rate=None (REQ-4)."""
    t = Telltale(window=10.0, decay_rate=None)
    t.update(0.0, 100.0)
    t.update(5.0, 40.0)
    assert t.current_peak(5.0) == 100.0

    t.update(10.1, 30.0)
    assert t.current_peak() == 40.0


def test_t041_hard_hold_single_sample_drops_to_none() -> None:
    """Test single sample peak drops to None when window expires (REQ-4)."""
    t = Telltale(window=10.0, decay_rate=None)
    t.update(0.0, 50.0)
    assert t.current_peak() == 50.0

    assert t.current_peak(10.1) is None


def test_t050_smooth_decay_from_departed_high() -> None:
    """Test smooth decay from departed high at decay_rate units/sec (REQ-5)."""
    t = Telltale(window=10.0, decay_rate=15.0)
    t.update(0.0, 100.0)
    t.update(9.0, 40.0)

    # At t=12.0, peak was at t=0, window ended at t=10.0. Elapsed decay time = 2.0s.
    # Decayed peak = 100.0 - 15.0 * 2.0 = 70.0
    assert t.current_peak(12.0) == 70.0


def test_t051_decay_floor_clamping() -> None:
    """Test decaying peak is strictly floored at active window maximum (REQ-5)."""
    t = Telltale(window=10.0, decay_rate=15.0)
    t.update(0.0, 100.0)
    t.update(9.0, 40.0)

    # At t=15.0, unfloored decay = 100.0 - 15.0 * (15.0 - 10.0) = 25.0
    # Active window max = 40.0 (from sample at 9.0). Peak must be floored at 40.0.
    assert t.current_peak(15.0) == 40.0


def test_t060_reset_clears_state() -> None:
    """Test reset clears all internal state and current_peak returns None (REQ-6)."""
    t = Telltale(window=10.0, decay_rate=10.0)
    t.update(0.0, 100.0)
    t.update(5.0, 50.0)
    assert t.current_peak() == 100.0

    t.reset()
    assert t.current_peak() is None
    assert len(t.samples) == 0
    assert len(t.max_deque) == 0
    assert t.latest_timestamp is None


def test_t061_update_after_reset_reinitializes() -> None:
    """Test update after reset re-initializes telltale state (REQ-6)."""
    t = Telltale(window=10.0)
    t.update(0.0, 100.0)
    t.reset()

    t.update(20.0, 15.0)
    assert t.current_peak() == 15.0


def test_t070_pre_first_update_returns_none() -> None:
    """Test current_peak returns None prior to first update (REQ-7)."""
    t = Telltale(window=10.0, decay_rate=5.0)
    assert t.current_peak() is None


def test_out_of_order_timestamps() -> None:
    """Test out-of-order timestamp rejection in update and current_peak."""
    t = Telltale(window=10.0)
    t.update(10.0, 50.0)

    with pytest.raises(ValueError, match="Timestamps must be non-decreasing"):
        t.update(9.0, 60.0)

    with pytest.raises(ValueError, match="Evaluation time cannot precede latest timestamp"):
        t.current_peak(8.0)


def test_sample_dataclass_immutability() -> None:
    """Test Sample dataclass creation and immutability."""
    s = Sample(timestamp=1.0, value=2.0)
    assert s.timestamp == 1.0
    assert s.value == 2.0
    with pytest.raises(AttributeError):
        s.value = 3.0  # type: ignore[misc]