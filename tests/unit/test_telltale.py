"""Unit test suite for pure Telltale peak-hold needle logic.

Issue #41: Telltale peak-hold needle logic (pure, no GUI)
Ref: docs/design/0001-test-strategy.md (Option C / unit tier compliance)
"""

from __future__ import annotations

import pytest

from boostgauge.telltale import Telltale, TelltaleManager


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


def test_t010_mgr_initialization() -> None:
    """T010_mgr: TelltaleManager creates 4 window keys (m1, m10, h1, all)."""
    mgr = TelltaleManager()
    assert set(mgr.telltales.keys()) == {"m1", "m10", "h1", "all"}
    assert mgr.get_peaks() == {"m1": None, "m10": None, "h1": None, "all": None}


def test_t020_mgr_update_distribution() -> None:
    """T020_mgr: update(t, v) routes samples to all four windows."""
    mgr = TelltaleManager()
    mgr.update(100.0, 75.0)
    peaks = mgr.get_peaks()
    assert peaks == {"m1": 75.0, "m10": 75.0, "h1": 75.0, "all": 75.0}


def test_t030_mgr_sliding_window_drop() -> None:
    """T030_mgr: 1m peak drops after 60 seconds, while 10m/1h/all persist."""
    mgr = TelltaleManager()
    mgr.update(0.0, 90.0)
    mgr.update(65.0, 30.0)
    peaks = mgr.get_peaks(65.0)
    assert peaks["m1"] == 30.0
    assert peaks["m10"] == 90.0
    assert peaks["h1"] == 90.0
    assert peaks["all"] == 90.0


def test_t040_mgr_all_time_persistence() -> None:
    """T040_mgr: All-time window holds peak permanently past 3600 seconds."""
    mgr = TelltaleManager()
    mgr.update(0.0, 95.0)
    mgr.update(4000.0, 10.0)
    peaks = mgr.get_peaks(4000.0)
    assert peaks["m1"] == 10.0
    assert peaks["m10"] == 10.0
    assert peaks["h1"] == 10.0
    assert peaks["all"] == 95.0


def test_t050_mgr_individual_and_global_reset() -> None:
    """T050_mgr: Test individual window reset and reset_all()."""
    mgr = TelltaleManager()
    mgr.update(100.0, 80.0)
    mgr.reset("m1")
    assert mgr.get_peaks()["m1"] is None
    assert mgr.get_peaks()["m10"] == 80.0

    mgr.reset("all_windows")
    assert mgr.get_peaks() == {"m1": None, "m10": None, "h1": None, "all": None}


def test_t060_mgr_invalid_reset_key() -> None:
    """T060_mgr: ValueError raised on unknown reset key."""
    mgr = TelltaleManager()
    with pytest.raises(ValueError, match="Unknown window key: invalid_key"):
        mgr.reset("invalid_key")


def test_t070_mgr_window_configurations() -> None:
    """T070_mgr: Verify each window has the correct duration configured."""
    mgr = TelltaleManager()
    assert mgr.telltales["m1"].window == 60.0
    assert mgr.telltales["m10"].window == 600.0
    assert mgr.telltales["h1"].window == 3600.0
    assert mgr.telltales["all"].window == float("inf")


def test_t080_mgr_reset_none_resets_all() -> None:
    """T080_mgr: reset(None) resets all windows via reset_all()."""
    mgr = TelltaleManager()
    mgr.update(100.0, 55.0)
    assert mgr.get_peaks() == {"m1": 55.0, "m10": 55.0, "h1": 55.0, "all": 55.0}
    mgr.reset(None)
    assert mgr.get_peaks() == {"m1": None, "m10": None, "h1": None, "all": None}


def test_t090_mgr_individual_window_resets() -> None:
    """T090_mgr: Each individual window can be reset independently."""
    mgr = TelltaleManager()
    mgr.update(100.0, 70.0)

    for key in ("m1", "m10", "h1", "all"):
        mgr2 = TelltaleManager()
        mgr2.update(100.0, 70.0)
        mgr2.reset(key)
        peaks = mgr2.get_peaks()
        assert peaks[key] is None
        for other_key in ("m1", "m10", "h1", "all"):
            if other_key != key:
                assert peaks[other_key] == 70.0


def test_t100_mgr_negative_timestamp_raises() -> None:
    """T100_mgr: Negative timestamp raises ValueError."""
    mgr = TelltaleManager()
    with pytest.raises(ValueError, match="Timestamp must be non-negative"):
        mgr.update(-1.0, 50.0)


def test_t110_mgr_non_monotonic_timestamp_raises() -> None:
    """T110_mgr: Non-monotonic timestamp raises ValueError."""
    mgr = TelltaleManager()
    mgr.update(100.0, 50.0)
    with pytest.raises(ValueError, match="Timestamp must be monotonically non-decreasing"):
        mgr.update(99.0, 60.0)


def test_t120_mgr_get_peaks_with_explicit_timestamp() -> None:
    """T120_mgr: get_peaks() with explicit timestamp evaluates peaks at that time."""
    mgr = TelltaleManager()
    mgr.update(0.0, 80.0)
    mgr.update(61.0, 20.0)
    # At t=65.0, m1 window [5.0, 65.0] excludes t=0.0, so m1 peak is 20.0
    peaks = mgr.get_peaks(timestamp=65.0)
    assert peaks["m1"] == 20.0
    assert peaks["all"] == 80.0


def test_t130_mgr_reset_all_method() -> None:
    """T130_mgr: reset_all() clears all four windows."""
    mgr = TelltaleManager()
    mgr.update(0.0, 60.0)
    mgr.update(100.0, 40.0)
    mgr.reset_all()
    assert mgr.get_peaks() == {"m1": None, "m10": None, "h1": None, "all": None}


def test_t140_mgr_repeated_reset_all_safe() -> None:
    """T140_mgr: reset_all() is safe to call repeatedly on empty manager."""
    mgr = TelltaleManager()
    mgr.reset_all()
    mgr.reset_all()
    assert mgr.get_peaks() == {"m1": None, "m10": None, "h1": None, "all": None}