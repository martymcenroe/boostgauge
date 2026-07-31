"""Unit tests for Telltale peak-hold sliding window and decay tracking.

Issue #41: Telltale peak-hold needle logic (pure, no GUI)
"""

import pytest

from boostgauge.telltale import Sample, Telltale


def test_scenario_010_expose_telltale_class():
    """Scenario 010: Expose Telltale class in src/boostgauge/telltale.py (REQ-1)."""
    tt = Telltale(window=10.0)
    assert isinstance(tt, Telltale)
    sample = Sample(timestamp=1.0, value=50.0)
    assert sample.timestamp == 1.0
    assert sample.value == 50.0


def test_scenario_020_valid_initialization():
    """Scenario 020: Valid window and decay_rate initialization (REQ-2)."""
    tt = Telltale(window=10.0, decay_rate=5.0)
    assert tt._window == 10.0
    assert tt._decay_rate == 5.0

    tt_no_decay = Telltale(window=60.0)
    assert tt_no_decay._window == 60.0
    assert tt_no_decay._decay_rate is None


def test_scenario_021_invalid_window_raises_value_error():
    """Scenario 021: Invalid window <= 0 raises ValueError (REQ-2)."""
    with pytest.raises(ValueError, match="Window must be positive"):
        Telltale(window=0.0)

    with pytest.raises(ValueError, match="Window must be positive"):
        Telltale(window=-1.0)


def test_scenario_022_invalid_negative_decay_rate_raises_value_error():
    """Scenario 022: Invalid negative decay_rate raises ValueError (REQ-2)."""
    with pytest.raises(ValueError, match="Decay rate must be non-negative"):
        Telltale(window=10.0, decay_rate=-5.0)


def test_scenario_030_single_sample_update():
    """Scenario 030: Single sample update (REQ-3)."""
    tt = Telltale(window=10.0)
    tt.update(timestamp=1.0, value=25.0)
    assert len(tt._samples) == 1
    assert tt._last_update_time == 1.0


def test_scenario_031_monotonic_timestamp_progression():
    """Scenario 031: Monotonic timestamp progression (REQ-3)."""
    tt = Telltale(window=10.0)
    tt.update(timestamp=1.0, value=10.0)
    tt.update(timestamp=2.0, value=20.0)
    tt.update(timestamp=2.0, value=25.0)  # Same timestamp allowed
    assert tt._last_update_time == 2.0


def test_scenario_032_decreasing_timestamp_raises_value_error():
    """Scenario 032: Decreasing timestamp update raises ValueError (REQ-3)."""
    tt = Telltale(window=10.0)
    tt.update(timestamp=10.0, value=50.0)
    with pytest.raises(ValueError, match="Timestamps must be non-decreasing"):
        tt.update(timestamp=9.5, value=60.0)


def test_scenario_040_pre_first_update_current_peak_returns_none():
    """Scenario 040: Pre-first-update current_peak returns None (REQ-4)."""
    tt = Telltale(window=10.0)
    assert tt.current_peak() is None
    assert tt.current_peak(timestamp=5.0) is None


def test_scenario_041_single_sample_current_peak_equals_value():
    """Scenario 041: Single sample current_peak equals sample value (REQ-4)."""
    tt = Telltale(window=10.0)
    tt.update(timestamp=5.0, value=42.0)
    assert tt.current_peak() == 42.0
    assert tt.current_peak(timestamp=5.0) == 42.0


def test_scenario_042_rising_series_peak_equals_maximum():
    """Scenario 042: Rising series peak equals maximum value so far (REQ-4)."""
    tt = Telltale(window=10.0)
    tt.update(timestamp=1.0, value=10.0)
    assert tt.current_peak() == 10.0
    tt.update(timestamp=2.0, value=30.0)
    assert tt.current_peak() == 30.0
    tt.update(timestamp=3.0, value=20.0)
    assert tt.current_peak() == 30.0  # Max remains 30.0


def test_scenario_043_window_expiration_without_decay_drops_peak():
    """Scenario 043: Window expiration without decay drops peak to active window maximum (REQ-4)."""
    tt = Telltale(window=10.0)
    tt.update(timestamp=0.0, value=100.0)
    tt.update(timestamp=5.0, value=40.0)
    assert tt.current_peak(timestamp=5.0) == 100.0

    # At t=10.1, sample at t=0.0 (value=100.0) is expired (cutoff=0.1)
    assert tt.current_peak(timestamp=10.1) == 40.0


def test_scenario_050_decay_enabled_former_high_descends():
    """Scenario 050: Decay enabled former high ages out descending at decay_rate (REQ-5)."""
    tt = Telltale(window=10.0, decay_rate=15.0)
    tt.update(timestamp=0.0, value=100.0)
    tt.update(timestamp=9.0, value=40.0)

    # At t=12.0, sample (0.0, 100.0) expired at t=10.0.
    # Expired duration = 12.0 - 10.0 = 2.0s.
    # Decayed value = 100.0 - (15.0 * 2.0) = 70.0.
    assert tt.current_peak(timestamp=12.0) == 70.0


def test_scenario_051_decay_floor_bounded_by_active_window_max():
    """Scenario 051: Decay floor bounded strictly by active window maximum (REQ-5)."""
    tt = Telltale(window=10.0, decay_rate=15.0)
    tt.update(timestamp=0.0, value=100.0)
    tt.update(timestamp=9.0, value=40.0)

    # At t=15.0, sample (0.0, 100.0) decay = 100 - 15*(15-10) = 25.0.
    # Active window max from (9.0, 40.0) is 40.0.
    # MAX(40.0, 25.0) = 40.0 (floored by active window max).
    assert tt.current_peak(timestamp=15.0) == 40.0


def test_scenario_052_new_higher_sample_resets_decaying_peak():
    """Scenario 052: New higher sample immediately resets decaying peak upward (REQ-5)."""
    tt = Telltale(window=10.0, decay_rate=15.0)
    tt.update(timestamp=0.0, value=100.0)
    assert tt.current_peak(timestamp=12.0) == 70.0

    # Ingest new spike of 120.0 at t=12.5
    tt.update(timestamp=12.5, value=120.0)
    assert tt.current_peak(timestamp=12.5) == 120.0


def test_scenario_060_reset_clears_sample_history_and_decay():
    """Scenario 060: Reset clears sample history and decay state returning None (REQ-6)."""
    tt = Telltale(window=10.0, decay_rate=15.0)
    tt.update(timestamp=0.0, value=100.0)
    tt.update(timestamp=5.0, value=50.0)
    assert tt.current_peak() == 100.0

    tt.reset()
    assert tt.current_peak() is None
    assert len(tt._samples) == 0
    assert len(tt._max_deque) == 0
    assert tt._decay_peak is None
    assert tt._last_update_time is None


def test_scenario_061_update_after_reset_reestablishes_tracking():
    """Scenario 061: Update following reset re-establishes peak tracking (REQ-6)."""
    tt = Telltale(window=10.0, decay_rate=15.0)
    tt.update(timestamp=0.0, value=100.0)
    tt.reset()

    tt.update(timestamp=20.0, value=80.0)
    assert tt.current_peak() == 80.0
    assert tt.current_peak(timestamp=20.0) == 80.0


def test_query_behind_latest_update_raises_value_error():
    """Edge case: Query timestamp earlier than latest sample update timestamp."""
    tt = Telltale(window=10.0)
    tt.update(timestamp=10.0, value=50.0)
    with pytest.raises(ValueError, match="Query timestamp cannot be behind latest sample update"):
        tt.current_peak(timestamp=9.0)


def test_decay_peak_persists_after_active_window_empties():
    """Decaying peak returned when all samples have expired from the active window."""
    tt = Telltale(window=10.0, decay_rate=5.0)
    tt.update(timestamp=0.0, value=100.0)
    # At t=15.0, cutoff=5.0 so Sample(0,100) expires; no active samples remain.
    # Decay = 100.0 - 5.0 * (15.0 - 10.0) = 75.0
    assert tt.current_peak(timestamp=15.0) == 75.0


def test_decay_peak_replaced_by_later_higher_value_expired_sample():
    """Second expired sample with higher decayed value replaces first as decay peak."""
    tt = Telltale(window=10.0, decay_rate=5.0)
    tt.update(timestamp=0.0, value=80.0)
    tt.update(timestamp=1.0, value=100.0)
    # At t=15.0, cutoff=5.0; both samples expire.
    # Sample(0,80): decay = 80 - 5*(15-10) = 55.0 -> initial decay_peak
    # Sample(1,100): decay = 100 - 5*(15-11) = 80.0 -> replaces as better candidate
    # No active samples; decayed_val = 80.0
    assert tt.current_peak(timestamp=15.0) == 80.0