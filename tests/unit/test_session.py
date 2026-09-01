"""Unit tier for the telltale wiring (issue #2): W1–W3, RS1–RS6, U1, and the session glue.

Literal values throughout (ruling #270). No tkinter (strategy 0001, Option C).
"""

from __future__ import annotations

import json
import queue
from pathlib import Path

from boostgauge.collector import Band, DataCollector, SystemSnapshot, Thresholds
from boostgauge.config import DEFAULT_CONFIG
from boostgauge.session import Session, TelltaleSet, window_label

DEFAULT_WINDOWS = {"short": 60, "medium": 600, "long": 3600}
ODD_WINDOWS = {"short": 90, "medium": 900, "long": 7200}
CONFIG = json.loads(json.dumps(DEFAULT_CONFIG))   # size 300, the default windows and thresholds
assert CONFIG["size"] == 300 and CONFIG["telltale_windows"] == DEFAULT_WINDOWS


def _snap(ts: float, value: float) -> SystemSnapshot:
    """A snapshot whose recomputed composite (#416) equals ``value``.

    Counts are zero, so memory drives; ``memory_percent`` is the inverse of
    ``normalize`` on the 60/80 band. Values used here are chosen so the
    arithmetic is exact.
    """
    memory = value if value <= 60 else 60 + (value - 60) / 2
    return SystemSnapshot(timestamp=ts, conpty_count=0, process_count=0, memory_percent=memory,
                          handle_count=0, unleashed_sessions=0, driver="memory", composite_value=value)


# ---- W1: construction ---------------------------------------------------------------


def test_W1_four_instances_from_config():
    ts = TelltaleSet.from_config(CONFIG)
    assert ts.windows == (60.0, 600.0, 3600.0, None)
    assert [t.window for t in ts.telltales] == [60.0, 600.0, 3600.0, None]
    assert len(ts.telltales) == 4


# ---- W2: fan-out ----------------------------------------------------------------------


def test_W2_every_sample_reaches_all_four():
    ts = TelltaleSet(DEFAULT_WINDOWS)
    ts.feed(1.0, 42.0)
    ts.feed(2.0, 17.0)
    assert ts.peaks() == [42.0, 42.0, 42.0, 42.0]


def test_W2_session_ingest_fans_out_timestamp_and_value():
    s = Session(dict(CONFIG), "unused.json", renderer=lambda *a: a)
    s.ingest(_snap(5.0, 70.0))
    assert s.value == 70.0
    assert s.telltales.peaks() == [70.0, 70.0, 70.0, 70.0]
    # the window arithmetic saw 5.0 as the timestamp: a lower one now raises in #41's contract
    import pytest
    with pytest.raises(ValueError):
        s.ingest(_snap(4.0, 1.0))


def test_drain_ingests_every_queued_snapshot():
    q: queue.Queue = queue.Queue()
    for ts, v in [(1.0, 10.0), (2.0, 30.0), (3.0, 20.0)]:
        q.put(_snap(ts, v))
    s = Session(dict(CONFIG), "unused.json", renderer=lambda *a: a)
    assert s.drain(q) == 3
    assert s.value == 20.0 and s.telltales.peaks() == [30.0, 30.0, 30.0, 30.0]


# ---- W3: the four-slot argument with None passed through ---------------------------------


def test_W3_renderer_receives_four_slots_with_none_after_reset():
    calls = []

    def recording_renderer(value, telltales, size):
        calls.append((value, list(telltales), size))
        return "frame"

    s = Session(dict(CONFIG), "unused.json", renderer=recording_renderer)
    s.ingest(_snap(1.0, 40.0))
    s.telltales.reset(1)                       # the medium slot, no further samples
    assert s.frame(256) == "frame"
    assert calls == [(40.0, [40.0, None, 40.0, 40.0], 256)]
    assert s.frame() == "frame"
    assert calls[-1][2] == 300                 # config size when none given


def test_W3_before_any_sample_every_slot_is_none_and_value_is_zero():
    calls = []
    s = Session(dict(CONFIG), "unused.json", renderer=lambda v, t, size: calls.append((v, list(t))))
    s.frame(256)
    assert calls == [(0.0, [None, None, None, None])]


# ---- RS: reset dispatch -----------------------------------------------------------------


def _fed_set(windows=DEFAULT_WINDOWS):
    ts = TelltaleSet(windows)
    ts.feed(1.0, 50.0)
    return ts


def test_RS1_to_RS4_each_entry_resets_exactly_its_instance():
    for slot in range(4):
        ts = _fed_set()
        label, handler = ts.menu_entries()[slot]
        handler()
        expected = [50.0] * 4
        expected[slot] = None
        assert ts.peaks() == expected, label


def test_RS5_reset_all_resets_all_four():
    ts = _fed_set()
    label, handler = ts.menu_entries()[4]
    assert label == "Reset All"
    handler()
    assert ts.peaks() == [None, None, None, None]


def test_RS_labels_at_default_config():
    labels = [label for label, _ in _fed_set().menu_entries()]
    assert labels == ["Reset 1m", "Reset 10m", "Reset 1h", "Reset All-time", "Reset All"]


def test_RS6_labels_come_from_the_formatter_at_non_default_config():
    labels = [label for label, _ in _fed_set(ODD_WINDOWS).menu_entries()]
    assert labels == ["Reset 90s", "Reset 15m", "Reset 2h", "Reset All-time", "Reset All"]


# ---- U1: tooltip text ---------------------------------------------------------------------


def test_U1_tooltip_default_config():
    assert TelltaleSet(DEFAULT_WINDOWS).tooltip_text() == (
        "1m — cyan\n10m — orange\n1h — magenta\nAll-time — coral red")


def test_U1_tooltip_non_default_config_every_branch():
    assert TelltaleSet(ODD_WINDOWS).tooltip_lines() == [
        "90s — cyan", "15m — orange", "2h — magenta", "All-time — coral red"]


def test_window_label_branches():
    assert window_label(None) == "All-time"
    assert window_label(60) == "1m"
    assert window_label(600) == "10m"
    assert window_label(3600) == "1h"
    assert window_label(7200) == "2h"
    assert window_label(5400) == "90m"       # whole minutes, not whole hours
    assert window_label(90) == "90s"
    assert window_label(2.5) == "2.5s"


# ---- V1: composed image through the real renderer -----------------------------------------


def test_V1_presence_and_absence_through_the_real_renderer():
    from boostgauge.skins import stingray as sk

    s = Session(dict(CONFIG), "unused.json")
    # distinct peaks: feed a descending series so each window keeps its own maximum
    # (all four share the same samples here, so give them distinct peaks by resetting between feeds)
    s.ingest(_snap(0.0, 100.0))          # all four at 100
    s.telltales.reset(0)
    s.telltales.reset(1)
    s.telltales.reset(2)
    s.ingest(_snap(1.0, 85.0))           # short/medium/long at 85, all-time still 100
    s.telltales.reset(0)
    s.telltales.reset(1)
    s.ingest(_snap(2.0, 25.0))           # short/medium at 25
    s.telltales.reset(0)
    s.ingest(_snap(3.0, 10.0))           # short at 10; value now 10
    assert s.telltales.peaks() == [10.0, 25.0, 85.0, 100.0]

    img = s.frame(256)
    bare = sk.render_face(256)
    cx = cy = 128.0
    R = 0.40 * 256
    for peak in (25.0, 85.0, 100.0):                       # present: each family's pixel differs
        x, y = sk.polar(cx, cy, 0.43 * R, sk.angle(peak))
        a, b = img.getpixel((int(x), int(y))), bare.getpixel((int(x), int(y)))
        assert max(abs(p - q) for p, q in zip(a, b)) >= 32, peak

    s.telltales.reset(2)                                   # the 1h slot, no samples after
    img2 = s.frame(256)
    x, y = sk.polar(cx, cy, 0.43 * R, sk.angle(85.0))
    assert img2.getpixel((int(x), int(y))) == bare.getpixel((int(x), int(y)))   # absent
    x, y = sk.polar(cx, cy, 0.43 * R, sk.angle(100.0))
    assert img2.getpixel((int(x), int(y))) != bare.getpixel((int(x), int(y)))   # others still there


# ---- config glue: thresholds hot-reload, hand changes, exit write -----------------------------


class _Collector(DataCollector):
    def collect(self) -> SystemSnapshot:
        return _snap(0.0, 0.0)


def test_reread_thresholds_updates_the_running_collector(tmp_path):
    path = tmp_path / "config.json"
    manual = json.loads(json.dumps(CONFIG))
    manual["calibration"]["mode"] = "manual"               # #416: typed thresholds govern only manual mode
    path.write_text(json.dumps(manual), encoding="utf-8")
    collector = _Collector(Thresholds())
    s = Session(json.loads(json.dumps(manual)), path, collector=collector, renderer=lambda *a: a)

    assert s.reread_thresholds() is False                  # nothing changed on disk
    data = json.loads(path.read_text(encoding="utf-8"))
    data["thresholds"]["conpty"] = {"yellow": 5, "red": 9}
    path.write_text(json.dumps(data), encoding="utf-8")
    assert s.reread_thresholds() is True
    assert collector.thresholds.conpty == Band(5, 9)
    assert collector.thresholds.memory_percent == Band(60, 80)


def test_hand_changes_reach_the_exit_write_and_nothing_else(tmp_path):
    path = tmp_path / "config.json"
    data = json.loads(json.dumps(CONFIG))
    data["theme"] = "dark"
    path.write_text(json.dumps(data), encoding="utf-8")
    s = Session(json.loads(json.dumps(CONFIG)), path, renderer=lambda *a: a)
    assert s.exit_write() is False                         # untouched session: no write
    s.moved(40, 50)
    s.resized(320)
    assert s.config["size"] == 320                         # the running session follows the resize
    assert s.exit_write() is True
    after = json.loads(Path(path).read_text(encoding="utf-8"))
    assert after["position"] == {"x": 40, "y": 50} and after["size"] == 320
    assert after["theme"] == "dark" and after["telltale_windows"] == DEFAULT_WINDOWS
