"""Unit test suite for pure Telltale peak-hold needle logic.

Issue #41: Telltale peak-hold needle logic (pure, no GUI)
Ref: docs/design/0001-test-strategy.md (Option C / unit tier compliance)
"""

from __future__ import annotations

import pytest

from boostgauge.telltale import Telltale


def test_t010_initialization_and_module_exposure() -> None:
    """T010: Test Telltale initialization and parameter storage."""
    tt = Telltale(window=10.0, decay_rate=15.0)
    assert isinstance(tt, Telltale)
    assert tt.window == 10.0
    assert tt.decay_rate == 15.0


def test_t020_pre_update_peak_return() -> None:
    """T020: Verify current_peak() returns None before any update calls."""
    tt = Telltale(window=10.0)
    assert tt.current_peak() is None
    assert tt.current_peak(timestamp=5.0) is None


def test_t030_single_sample_update() -> None:
    """T030: Verify single sample update returns the exact sample value."""
    tt = Telltale(window=10.0)
    tt.update(timestamp=0.0, value=50.0)
    assert tt.current_peak() == 50.0
    assert tt.current_peak(timestamp=0.0) == 50.0


def test_t040_rising_series_tracking() -> None:
    """T040: Verify peak updates immediately when new maximum sample arrives."""
    tt = Telltale(window=10.0)
    tt.update(timestamp=0.0, value=50.0)
    assert tt.current_peak() == 50.0
    tt.update(timestamp=1.0, value=75.0)
    assert tt.current_peak() == 75.0


def test_t050_window_drop_without_decay() -> None:
    """T050: Verify instant drop to active window max when high ages out without decay."""
    tt = Telltale(window=10.0, decay_rate=None)
    tt.update(timestamp=0.0, value=100.0)
    tt.update(timestamp=9.0, value=40.0)
    assert tt.current_peak(timestamp=9.0) == 100.0
    # At t=11.0, sample at t=0.0 (100.0) is expired (> 10.0 window). Peak drops to 40.0.
    assert tt.current_peak(timestamp=11.0) == 40.0


def test_t060_monotonic_decay_from_expired_high() -> None:
    """T060: Verify linear decay at decay_rate units/sec from departed peak."""
    tt = Telltale(window=10.0, decay_rate=15.0)
    tt.update(timestamp=0.0, value=100.0)
    tt.update(timestamp=9.0, value=40.0)
    # At t=12.0, sample at t=0.0 (100.0) expired at t=10.0.
    # Decayed value at t=12.0 = 100.0 - 15.0 * (12.0 - 10.0) = 70.0.
    assert tt.current_peak(timestamp=12.0) == 70.0


def test_t070_active_window_decay_floor() -> None:
    """T070: Verify active window max acts as floor for linear decay."""
    tt = Telltale(window=10.0, decay_rate=15.0)
    tt.update(timestamp=0.0, value=100.0)
    tt.update(timestamp=9.0, value=40.0)
    # At t=15.0, decayed peak from t=0.0 would be 100.0 - 15.0 * 5.0 = 25.0.
    # However, sample at t=9.0 (40.0) is active in window [5.0, 15.0], flooring peak at 40.0.
    assert tt.current_peak(timestamp=15.0) == 40.0


def test_t080_reset_behavior() -> None:
    """T080: Verify reset clears all historical state and sample queues."""
    tt = Telltale(window=10.0, decay_rate=15.0)
    tt.update(timestamp=0.0, value=100.0)
    assert tt.current_peak() == 100.0

    tt.reset()
    assert tt.current_peak() is None

    # Subsequent update after reset works cleanly
    tt.update(timestamp=20.0, value=30.0)
    assert tt.current_peak() == 30.0


def test_t090_invalid_window_duration_parameter() -> None:
    """T090: Verify ValueError raised when window duration <= 0."""
    with pytest.raises(ValueError, match="window must be positive"):
        Telltale(window=0.0)

    with pytest.raises(ValueError, match="window must be positive"):
        Telltale(window=-5.0)


def test_t100_invalid_decay_rate_parameter() -> None:
    """T100: Verify ValueError raised when decay_rate < 0."""
    with pytest.raises(ValueError, match="decay_rate must be non-negative"):
        Telltale(window=10.0, decay_rate=-1.0)