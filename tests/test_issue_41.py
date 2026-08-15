"""Test file for Issue #41.

Emitted by AssemblyZero from the implementation spec's Section 10
test functions. Bodies are the spec's own, verbatim (#2316).
"""

# TDD: this import fails until the implementation exists (RED phase)
from boostgauge.telltale import *  # noqa: F401, F403


def test_req_5_t010_fresh_construction():
    # Freshly constructed returns None (REQ-5)
    # Expected: None
    t = Telltale(10.0)
    assert t.current_peak() is None


def test_req_3_t020_reset_clears_history():
    # Reset clears history to None (REQ-3)
    # Expected: None
    t = Telltale(10.0)
    t.update(0.0, 100.0)
    t.reset()
    assert t.current_peak() is None


def test_req_6_t030_single_sample():
    # Single sample (REQ-6)
    # Expected: 42.5
    t = Telltale(10.0)
    t.update(3.0, 42.5)
    assert t.current_peak() == 42.5


def test_req_6_t040_rising_series():
    # Rising series (REQ-6)
    # Expected: 30.0
    t = Telltale(10.0)
    t.update(0.0, 10.0)
    t.update(1.0, 20.0)
    t.update(2.0, 30.0)
    assert t.current_peak() == 30.0


def test_req_9_t050_in_window_values_never_decay():
    # In-window values never decay (REQ-9)
    # Expected: 100.0
    t = Telltale(10.0, 15.0)
    t.update(0.0, 100.0)
    t.update(5.0, 0.0)
    assert t.current_peak() == 100.0


def test_req_6_t060_closed_boundary():
    # Closed boundary (REQ-6)
    # Expected: 100.0
    t = Telltale(10.0)
    t.update(0.0, 100.0)
    t.update(10.0, 0.0)
    assert t.current_peak() == 100.0


def test_req_13_t070_equal_timestamps():
    # Equal timestamps (REQ-13)
    # Expected: 3.0
    t = Telltale(10.0)
    t.update(5.0, 1.0)
    t.update(5.0, 3.0)
    assert t.current_peak() == 3.0


def test_req_3_t080_reset_discards_tracks():
    # Reset discards decay tracks (REQ-3)
    # Expected: 7.0
    t = Telltale(10.0, 15.0)
    t.update(0.0, 100.0)
    t.reset()
    t.update(10.5, 7.0)
    assert t.current_peak() == 7.0


def test_req_10_t090_reject_protects_history():
    # Rejected update protects history (REQ-10)
    # Expected: 1.0
    t = Telltale(10.0)
    t.update(5.0, 1.0)
    with pytest.raises(ValueError):
        t.update(4.9, 9.0)
    assert t.current_peak() == 1.0


def test_req_2_t100_contract_restarts_at_reset():
    # Restart monotonic contract (REQ-2)
    # Expected: 7.0 (no exception)
    t = Telltale(10.0)
    t.update(100.0, 1.0)
    t.reset()
    t.update(10.0, 7.0)
    assert t.current_peak() == 7.0


def test_req_8_t110_hard_hold_drop():
    # Hard hold drop - sample drops cleanly without decay (REQ-8)
    # Expected: 40.0
    t = Telltale(10.0)
    t.update(0.0, 100.0)
    t.update(9.0, 40.0)
    t.update(10.5, 0.0)
    assert t.current_peak() == 40.0


def test_req_8_t120_exclusion_not_a_zero():
    # Exclusion is not a zero (REQ-8)
    # Expected: -20.0
    t = Telltale(10.0)
    t.update(0.0, -5.0)
    t.update(11.0, -20.0)
    assert t.current_peak() == -20.0


def test_req_9_t130_decay_track():
    # Decay track (REQ-9)
    # Expected: 70.0
    t = Telltale(10.0, 15.0)
    t.update(0.0, 100.0)
    t.update(9.0, 40.0)
    t.update(12.0, 0.0)
    # Elapsed departure: 12 - 10 = 2 seconds
    # Decay: 2 * 15.0 = 30.0 -> 100 - 30 = 70.0
    assert t.current_peak() == 70.0


def test_req_6_t140_decay_floor():
    # Decay floor (REQ-6)
    # Expected: 40.0
    t = Telltale(10.0, 15.0)
    t.update(0.0, 100.0)
    t.update(9.0, 40.0)
    t.update(12.0, 0.0)
    t.update(15.0, 0.0)
    # At 15: 100 decays by 5*15=75 -> 25.0. But 40.0 is in window (age=6). Peak=40.0.
    assert t.current_peak() == 40.0


def test_req_6_t150_new_high_beats_track():
    # New high beats track (REQ-6)
    # Expected: 80.0
    t = Telltale(10.0, 15.0)
    t.update(0.0, 100.0)
    t.update(9.0, 40.0)
    t.update(12.0, 0.0)
    t.update(12.5, 80.0)
    # At 12.5: 100 decays by 2.5*15=37.5 -> 62.5. Peak=80.0.
    assert t.current_peak() == 80.0


def test_req_9_t160_departed_highs_keep_tracks():
    # Departed highs keep tracks (REQ-9)
    # Expected: 75.0
    t = Telltale(10.0, 15.0)
    t.update(0.0, 100.0)
    t.update(5.0, 90.0)
    t.update(16.0, 0.0)
    # At 16:
    # 100 left at 10. Elapsed 6. 6*15=90. Contribution 10.
    # 90 left at 15. Elapsed 1. 1*15=15. Contribution 75.
    assert t.current_peak() == 75.0


def test_req_4_t170_purity_under_decay():
    # Purity under decay (REQ-4)
    # Expected: 70.0 (consecutively)
    t = Telltale(10.0, 15.0)
    t.update(0.0, 100.0)
    t.update(9.0, 40.0)
    t.update(12.0, 0.0)
    v1 = t.current_peak()
    v2 = t.current_peak()
    v3 = t.current_peak()
    assert v1 == v2 == v3 == 70.0


def test_req_1_t180_all_time_window():
    # All-time window (REQ-1)
    # Expected: 100.0
    t = Telltale(None)
    t.update(0.0, 100.0)
    t.update(1_000_000.0, 5.0)
    assert t.current_peak() == 100.0


def test_req_7_t190_all_time_ignores_decay():
    # All-time ignores decay (REQ-7)
    # Expected: 100.0
    t = Telltale(None, 15.0)
    t.update(0.0, 100.0)
    t.update(1_000_000.0, 5.0)
    assert t.current_peak() == 100.0


def test_req_11_t200_invalid_window():
    # Invalid window (REQ-11)
    # Expected: ValueError
    with pytest.raises(ValueError):
        Telltale(0.0)


def test_req_12_t210_invalid_decay_rate():
    # Invalid decay_rate (REQ-12)
    # Expected: ValueError
    with pytest.raises(ValueError):
        Telltale(10.0, -3.0)


def test_req_10_t220_rejected_update_raises():
    # Rejected update raises (REQ-10)
    # Expected: ValueError
    t = Telltale(10.0)
    t.update(5.0, 1.0)
    with pytest.raises(ValueError):
        t.update(4.9, 1.0)


def test_req_13_t230_equal_update_accepted():
    # Equal update accepted (REQ-13)
    # Expected: 3.0 (no exception)
    t = Telltale(10.0)
    t.update(5.0, 1.0)
    t.update(5.0, 3.0)
    assert t.current_peak() == 3.0
