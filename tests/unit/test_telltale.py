"""Unit tier for `Telltale` — one test per acceptance criterion of issue #41.

Every value asserted here is the literal the criterion carries (ruling #270).
Timestamps and values are plain floats; no clock, no fixtures, no framework
objects (docs/design/0001-test-strategy.md, Option C — this class sits beneath
the render layer entirely).
"""

from __future__ import annotations

import pytest

from boostgauge.telltale import Telltale


def _fed(window, samples, decay_rate=None):
    t = Telltale(window, decay_rate=decay_rate)
    for ts, v in samples:
        t.update(ts, v)
    return t


# ---- N: the null state --------------------------------------------------------


def test_N1_fresh_instance_reads_none():
    assert Telltale(10.0).current_peak() is None


def test_N2_reset_reads_none():
    t = _fed(10.0, [(0.0, 100.0)])
    t.reset()
    assert t.current_peak() is None


# ---- A: the active window -----------------------------------------------------


def test_A1_single_sample():
    assert _fed(10.0, [(3.0, 42.5)]).current_peak() == 42.5


def test_A2_rising_series_registers_immediately():
    assert _fed(10.0, [(0.0, 10.0), (1.0, 20.0), (2.0, 30.0)]).current_peak() == 30.0


def test_A3_in_window_values_never_decay():
    t = _fed(10.0, [(0.0, 100.0), (5.0, 0.0)], decay_rate=15.0)
    assert t.current_peak() == 100.0  # not 25.0


def test_A4_closed_boundary_age_exactly_window_is_in_window():
    assert _fed(10.0, [(0.0, 100.0), (10.0, 0.0)]).current_peak() == 100.0


def test_A5_equal_timestamps_hold_both():
    assert _fed(10.0, [(5.0, 1.0), (5.0, 3.0)]).current_peak() == 3.0


def test_A6_reset_discards_decay_tracks():
    t = _fed(10.0, [(0.0, 100.0)], decay_rate=15.0)
    t.reset()
    t.update(10.5, 7.0)
    assert t.current_peak() == 7.0  # a surviving track would read 92.5


def test_A7_history_unchanged_after_rejected_update():
    t = _fed(10.0, [(5.0, 1.0)])
    with pytest.raises(ValueError):
        t.update(4.9, 9.0)
    assert t.current_peak() == 1.0


def test_A8_monotonic_contract_restarts_at_reset():
    t = _fed(10.0, [(100.0, 1.0)])
    t.reset()
    t.update(10.0, 7.0)  # must not raise
    assert t.current_peak() == 7.0


# ---- H: hard hold (decay unset) ----------------------------------------------


def test_H1_departed_high_is_dropped_instantly():
    assert _fed(10.0, [(0.0, 100.0), (9.0, 40.0), (10.5, 0.0)]).current_peak() == 40.0


def test_H2_exclusion_is_not_a_zero():
    assert _fed(10.0, [(0.0, -5.0), (11.0, -20.0)]).current_peak() == -20.0  # not 0.0


# ---- D: decay -----------------------------------------------------------------

D1_SAMPLES = [(0.0, 100.0), (9.0, 40.0), (12.0, 0.0)]


def test_D1_decay_track():
    assert _fed(10.0, D1_SAMPLES, decay_rate=15.0).current_peak() == 70.0


def test_D2_window_maximum_is_the_only_floor():
    t = _fed(10.0, D1_SAMPLES, decay_rate=15.0)
    t.update(15.0, 0.0)
    assert t.current_peak() == 40.0  # unfloored decay would read 25.0


def test_D3_new_high_beats_the_track():
    t = _fed(10.0, D1_SAMPLES, decay_rate=15.0)
    t.update(12.5, 80.0)
    assert t.current_peak() == 80.0  # the track reads 62.5


def test_D4_every_departed_high_keeps_its_own_track():
    t = _fed(10.0, [(0.0, 100.0), (5.0, 90.0), (16.0, 0.0)], decay_rate=15.0)
    assert t.current_peak() == 75.0  # the 90 track; the 100 track reads 10.0


def test_D5_reads_are_pure():
    t = _fed(10.0, D1_SAMPLES, decay_rate=15.0)
    assert [t.current_peak(), t.current_peak(), t.current_peak()] == [70.0, 70.0, 70.0]


# ---- T: all-time --------------------------------------------------------------


def test_T1_all_time_never_ages_out():
    assert _fed(None, [(0.0, 100.0), (1000000.0, 5.0)]).current_peak() == 100.0


def test_T2_all_time_ignores_decay():
    assert _fed(None, [(0.0, 100.0), (1000000.0, 5.0)], decay_rate=15.0).current_peak() == 100.0


# ---- V: validation ------------------------------------------------------------


def test_V1_window_must_be_positive():
    with pytest.raises(ValueError):
        Telltale(0)
    with pytest.raises(ValueError):
        Telltale(-5.0)


def test_V2_decay_rate_must_be_positive():
    with pytest.raises(ValueError):
        Telltale(10.0, decay_rate=0)
    with pytest.raises(ValueError):
        Telltale(10.0, decay_rate=-3.0)


def test_V3_decreasing_timestamp_raises():
    t = _fed(10.0, [(5.0, 1.0)])
    with pytest.raises(ValueError):
        t.update(4.9, 1.0)


def test_V4_equal_timestamp_is_accepted():
    t = _fed(10.0, [(5.0, 1.0)])
    t.update(5.0, 3.0)  # must not raise


# ---- configuration survives reset (the reset requirement) -----------------------


def test_reset_keeps_configuration():
    t = Telltale(10.0, decay_rate=15.0)
    t.update(0.0, 1.0)
    t.reset()
    assert (t.window, t.decay_rate) == (10.0, 15.0)
