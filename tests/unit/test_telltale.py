"""Unit tests for the peak-hold telltale needle logic.

Issue #41: Feature: Telltale peak-hold needle logic (pure, no GUI)
"""

import time
import pytest
from boostgauge.telltale import Telltale


def test_telltale_init() -> None:
    """Verify class exposure and valid initialization (T010)."""
    t = Telltale(window=60.0, decay_rate=0.5)
    assert t.window == 60.0
    assert t.decay_rate == 0.5
    assert t.current_peak() is None


def test_telltale_invalid_init() -> None:
    """Verify initialization validation (T070)."""
    with pytest.raises(ValueError, match="Window must be positive."):
        Telltale(window=0.0)
    with pytest.raises(ValueError, match="Window must be positive."):
        Telltale(window=-5.0)
    with pytest.raises(ValueError, match="decay_rate must be non-negative."):
        Telltale(window=5.0, decay_rate=-1.0)


def test_telltale_pre_update_peak() -> None:
    """Verify pre-first-update peak returns None (T090)."""
    t = Telltale(window=10.0)
    assert t.current_peak() is None


def test_telltale_non_monotonic_timestamp() -> None:
    """Verify non-monotonic timestamp rejection (T100)."""
    t = Telltale(window=10.0)
    t.update(5.0, 10.0)
    with pytest.raises(ValueError, match="Timestamps must be monotonically increasing."):
        t.update(3.0, 5.0)


def test_telltale_reset_to_new_high() -> None:
    """Verify reset to new high value when exceeded (T030)."""
    t = Telltale(window=10.0)
    t.update(0.0, 5.0)
    assert t.current_peak() == 5.0
    t.update(1.0, 10.0)
    assert t.current_peak() == 10.0


def test_telltale_window_expiry() -> None:
    """Verify window expiry drops peak to next-highest value (T040)."""
    t = Telltale(window=10.0)
    t.update(0.0, 10.0)
    t.update(5.0, 5.0)
    assert t.current_peak() == 10.0
    t.update(11.0, 2.0)
    assert t.current_peak() == 5.0


def test_telltale_monotonic_decay() -> None:
    """Verify monotonic decay towards current value (T050)."""
    t = Telltale(window=10.0, decay_rate=1.0)
    t.update(0.0, 10.0)
    assert t.current_peak() == 10.0
    t.update(5.0, 3.0)
    assert t.current_peak() == 5.0


def test_telltale_decay_bounded_by_current() -> None:
    """Verify decay is bounded by the current value (T080)."""
    t = Telltale(window=10.0, decay_rate=1.0)
    t.update(0.0, 10.0)
    t.update(12.0, 5.0)
    assert t.current_peak() == 5.0


def test_telltale_reset_clears_state() -> None:
    """Verify reset clears all history and peak state (T060)."""
    t = Telltale(window=10.0, decay_rate=1.0)
    t.update(0.0, 10.0)
    assert t.current_peak() == 10.0
    t.reset()
    assert t.current_peak() is None
    t.update(5.0, 8.0)
    assert t.current_peak() == 8.0


def test_telltale_reset_idempotent() -> None:
    """Verify reset can be called multiple times without error."""
    t = Telltale(window=10.0)
    t.reset()
    t.reset()
    assert t.current_peak() is None


def test_telltale_window_boundary_exact() -> None:
    """Verify boundary condition when current_time - timestamp == window exactly (T007)."""
    t = Telltale(window=5.0)
    t.update(0.0, 10.0)
    t.update(5.0, 3.0)
    # At t=5.0, cutoff = 0.0; sample at t=0.0 has timestamp >= cutoff so it's kept
    assert t.current_peak() == 10.0
    t.update(5.0001, 3.0)
    # Now cutoff slightly > 0.0, so sample at t=0.0 is evicted
    assert t.current_peak() == 3.0


def test_telltale_decay_rate_zero() -> None:
    """Verify that decay_rate=0.0 keeps peak constant until window expiry (T008)."""
    t = Telltale(window=5.0, decay_rate=0.0)
    t.update(0.0, 10.0)
    t.update(4.0, 2.0)
    assert t.current_peak() == 10.0


def test_telltale_performance() -> None:
    """Verify O(1) amortized update and retrieval efficiency (T020)."""
    t = Telltale(window=10.0, decay_rate=0.5)
    start_time = time.perf_counter()
    for i in range(10000):
        t.update(float(i) * 0.001, float(i % 100))
        t.current_peak()
    end_time = time.perf_counter()
    assert end_time - start_time < 0.2


def test_telltale_o1_amortized_scaling() -> None:
    """Verify O(1) amortized complexity by checking linear scaling (T004)."""
    def measure(n: int) -> float:
        t = Telltale(window=10.0, decay_rate=0.5)
        start = time.perf_counter()
        for i in range(n):
            t.update(float(i) * 0.001, float(i % 100))
            t.current_peak()
        return time.perf_counter() - start

    small = measure(1000)
    large = measure(10000)
    # If O(1) amortized, scaling by 10x operations should scale time by < 15x
    assert large < small * 15 or large < 0.2