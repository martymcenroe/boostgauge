"""Headless unit tests for Telltale peak-hold needle logic.

Issue #41: Feature: Telltale peak-hold needle logic (pure, no GUI)
"""

import pytest

from boostgauge.telltale import Telltale


def test_t010_instantiation_and_config_validation():
    """T010: Accepts valid window/decay; raises ValueError on non-positive window or negative decay."""
    tt = Telltale(window=10.0, decay_rate=15.0)
    assert tt._window == 10.0
    assert tt._decay_rate == 15.0

    with pytest.raises(ValueError, match="Window duration must be positive"):
        Telltale(window=0.0)

    with pytest.raises(ValueError, match="Window duration must be positive"):
        Telltale(window=-5.0)

    with pytest.raises(ValueError, match="Decay rate must be non-negative"):
        Telltale(window=10.0, decay_rate=-1.0)


def test_t020_pre_first_update_return():
    """T020: current_peak() returns None before any sample update."""
    tt = Telltale(window=10.0, decay_rate=5.0)
    assert tt.current_peak() is None
    assert tt.current_peak(current_time=5.0) is None


def test_t030_single_sample_peak():
    """T030: current_peak() returns single value when one sample is recorded."""
    tt = Telltale(window=10.0)
    tt.update(timestamp=1.0, value=42.0)
    assert tt.current_peak() == 42.0
    assert tt.current_peak(current_time=5.0) == 42.0


def test_t040_monotonic_timestamp_validation():
    """T040: update() and current_peak() raise ValueError on timestamp regression."""
    tt = Telltale(window=10.0)
    tt.update(timestamp=10.0, value=50.0)

    with pytest.raises(ValueError, match="Timestamp cannot be earlier than previous sample timestamp"):
        tt.update(timestamp=9.0, value=60.0)

    with pytest.raises(ValueError, match="current_time cannot be earlier than latest sample timestamp"):
        tt.current_peak(current_time=8.0)


def test_t050_rising_sample_series():
    """T050: Peak resets upward immediately on new high."""
    tt = Telltale(window=10.0)
    tt.update(timestamp=0.0, value=50.0)
    assert tt.current_peak() == 50.0

    tt.update(timestamp=1.0, value=80.0)
    assert tt.current_peak() == 80.0

    tt.update(timestamp=2.0, value=60.0)
    assert tt.current_peak() == 80.0


def test_t060_hard_hold_window_drop():
    """T060: Peak drops instantly to window max when former high ages out (no decay)."""
    tt = Telltale(window=10.0, decay_rate=None)
    tt.update(timestamp=0.0, value=100.0)
    tt.update(timestamp=5.0, value=30.0)

    assert tt.current_peak(current_time=9.0) == 100.0
    assert tt.current_peak(current_time=11.0) == 30.0


def test_t070_linear_decay_tracking():
    """T070: Peak decays linearly at decay_rate from departed high."""
    tt = Telltale(window=10.0, decay_rate=15.0)
    tt.update(timestamp=0.0, value=100.0)
    tt.update(timestamp=9.0, value=40.0)

    # At t=12.0, sample 1 (t=0.0, v=100) departed window at t=10.0. Elapsed decay = 2.0s.
    # Decayed value = 100.0 - (15.0 * 2.0) = 70.0. Window max = 40.0.
    assert tt.current_peak(current_time=12.0) == 70.0


def test_t080_decay_floor_bound():
    """T080: Peak decay stops at active window maximum floor."""
    tt = Telltale(window=10.0, decay_rate=15.0)
    tt.update(timestamp=0.0, value=100.0)
    tt.update(timestamp=9.0, value=40.0)

    # At t=15.0, decay would be 100 - 15*5 = 25.0, but window max is 40.0.
    assert tt.current_peak(current_time=15.0) == 40.0


def test_t090_reset_behavior():
    """T090: reset() clears all state; subsequent current_peak() returns None."""
    tt = Telltale(window=10.0, decay_rate=5.0)
    tt.update(timestamp=0.0, value=100.0)
    assert tt.current_peak() == 100.0

    tt.reset()
    assert tt.current_peak() is None

    tt.update(timestamp=1.0, value=50.0)
    assert tt.current_peak() == 50.0


def test_t100_negative_sample_pruning_retention():
    """T100: Negative sample values are retained for full window duration."""
    tt = Telltale(window=10.0, decay_rate=15.0)
    tt.update(timestamp=0.0, value=-20.0)
    assert tt.current_peak(current_time=5.0) == -20.0


def test_t110_expired_decay_query_without_update():
    """T110: Querying current_peak long after sample decay returns None rather than negative infinity."""
    tt = Telltale(window=10.0, decay_rate=15.0)
    tt.update(timestamp=0.0, value=100.0)
    assert tt.current_peak(current_time=100.0) is None