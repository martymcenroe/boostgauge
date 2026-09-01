"""Unit tier for calibration (issue #416) — one test per decision-table row, literal values.

Readings are the operator's machine on 2026-09-01: 31 console hosts, 373
processes, 150,096 handles, 66 % memory. No renderer, no window (strategy 0001).
"""

from __future__ import annotations

import json

import pytest

from boostgauge.collector import Band, DataCollector, SystemSnapshot, Thresholds
from boostgauge.config import DEFAULT_CONFIG, ConfigError, load_config
from boostgauge.session import SEED_FLOORS, Session, bands_for, seeded_highs

MACHINE = dict(conpty=31, processes=373, handles=150096, memory=66.0)


def _snap(ts=1.0, conpty=31, processes=373, handles=150096, memory=66.0) -> SystemSnapshot:
    """A raw collector reading; composite_value/driver are placeholders the session recomputes."""
    return SystemSnapshot(timestamp=ts, conpty_count=conpty, process_count=processes,
                          memory_percent=memory, handle_count=handles, unleashed_sessions=0,
                          driver="placeholder", composite_value=-1.0)


def _config(**overrides) -> dict:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    cfg.update(overrides)
    return cfg


class _Collector(DataCollector):
    def collect(self) -> SystemSnapshot:
        return _snap()


@pytest.fixture
def cfg_path(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps(DEFAULT_CONFIG, indent=2) + "\n", encoding="utf-8")
    return p


def _file(path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ---- C1 / C2: first run seeds with headroom, needle at exactly 40 ------------------------


def test_C1_first_run_seeds_from_the_first_reading():
    collector = _Collector()
    s = Session(_config(), "unused.json", collector=collector, renderer=lambda *a: a)
    assert s.bands is None                                    # nothing to compute before a reading
    s.ingest(_snap(memory=30.0))                              # memory 30 -> 30, so the seeded counts drive
    assert s.bands == Thresholds(conpty=Band(46.5, 77.5), memory_percent=Band(60, 80),
                                 process_count=Band(559.5, 932.5), handle_count=Band(225144.0, 375240.0))
    assert collector.thresholds == s.bands                   # pushed to the running collector
    assert s.value == 40.0
    assert s.driver == "conpty"                               # three-way tie resolves in metric order
    assert s.telltales.peaks() == [40.0, 40.0, 40.0, 40.0]


def test_C1_on_this_machine_memory_outranks_the_seeded_counts():
    s = Session(_config(), "unused.json", renderer=lambda *a: a)
    s.ingest(_snap())                                         # memory 66 % -> 72.0 beats the counts' 40.0
    assert s.value == 72.0 and s.driver == "memory"


def test_C2_first_run_seed_persists_at_quit(cfg_path):
    s = Session(load_config(cfg_path), cfg_path, renderer=lambda *a: a)
    s.ingest(_snap())
    assert s.exit_write() is True
    assert _file(cfg_path)["calibration"] == {
        "mode": "auto", "highs": {"conpty": 77.5, "process_count": 932.5, "handle_count": 375240.0}}
    assert _file(cfg_path)["thresholds"] == DEFAULT_CONFIG["thresholds"]   # untouched
    assert _file(cfg_path)["position"] == {"x": 100, "y": 100}


# ---- C3 / C4 / C5 / C6: auto bands from stored highs, learning, never lowering ------------

STORED = {"conpty": 60, "process_count": 500, "handle_count": 250000}


def test_C3_auto_bands_from_stored_highs():
    cfg = _config(calibration={"mode": "auto", "highs": dict(STORED)})
    s = Session(cfg, "unused.json", renderer=lambda *a: a)
    assert s.bands.handle_count == Band(150000.0, 250000.0)  # computed at launch, no reading needed
    assert s.bands.conpty == Band(36.0, 60.0)
    s.ingest(_snap(memory=30.0))
    # handles 150096 against 150000 / 250000 read 60.0; processes 373 against 300 / 500 read 74.6 and win
    assert round(s.value, 1) == 74.6
    assert s.driver == "processes"
    s.ingest(_snap(ts=2.0, memory=30.0, processes=100))       # with processes cool, handles drive at 60.0
    assert round(s.value, 1) == 60.0
    assert s.driver == "handles"


def test_C4_a_new_high_pins_the_needle_and_is_learned_without_moving_the_bands():
    cfg = _config(calibration={"mode": "auto", "highs": dict(STORED)})
    s = Session(cfg, "unused.json", renderer=lambda *a: a)
    s.ingest(_snap(ts=1.0))
    s.ingest(_snap(ts=2.0, handles=300000))
    assert s.value == 100.0
    assert s.session_highs["handle_count"] == 300000.0
    assert s.bands.handle_count == Band(150000.0, 250000.0)  # fixed for the session


def test_C5_learning_persists_only_the_metric_that_rose(cfg_path):
    data = _file(cfg_path)
    data["calibration"] = {"mode": "auto", "highs": dict(STORED)}
    cfg_path.write_text(json.dumps(data), encoding="utf-8")
    s = Session(load_config(cfg_path), cfg_path, renderer=lambda *a: a)
    s.ingest(_snap(ts=1.0, handles=300000))                   # conpty 31 < 60, processes 373 < 500
    assert s.exit_write() is True
    assert _file(cfg_path)["calibration"]["highs"] == {
        "conpty": 60, "process_count": 500, "handle_count": 300000.0}


def test_C6_learning_never_lowers_a_stored_high(cfg_path):
    data = _file(cfg_path)
    data["calibration"] = {"mode": "auto", "highs": dict(STORED)}
    cfg_path.write_text(json.dumps(data), encoding="utf-8")
    s = Session(load_config(cfg_path), cfg_path, renderer=lambda *a: a)
    s.ingest(_snap())                                          # 150096 < 250000
    before = cfg_path.read_bytes()
    assert s.exit_write() is False                             # nothing rose, nothing hand-changed: no write
    assert cfg_path.read_bytes() == before
    assert _file(cfg_path)["calibration"]["highs"]["handle_count"] == 250000


# ---- C7 / C8: Mark this as redline --------------------------------------------------------


def test_C7_mark_this_as_redline(cfg_path):
    s = Session(load_config(cfg_path), cfg_path, renderer=lambda *a: a)
    s.ingest(_snap(ts=1.0, conpty=40, processes=400, handles=200000))
    assert s.mark_redline() is True
    assert s.config["thresholds"]["conpty"] == {"yellow": 24.0, "red": 40.0}
    assert s.config["thresholds"]["process_count"] == {"yellow": 240.0, "red": 400.0}
    assert s.config["thresholds"]["handle_count"] == {"yellow": 120000.0, "red": 200000.0}
    assert s.config["thresholds"]["memory_percent"] == {"yellow": 60, "red": 80}
    assert s.calibration_mode == "manual"
    assert s.value == 100.0                                    # this tick is, by definition, red
    assert s.exit_write() is True
    on_disk = _file(cfg_path)
    assert on_disk["calibration"]["mode"] == "manual"
    assert on_disk["thresholds"]["handle_count"] == {"yellow": 120000.0, "red": 200000.0}


def test_C8_manual_mode_uses_thresholds():
    cfg = _config(calibration={"mode": "manual", "highs": {}})
    cfg["thresholds"]["handle_count"] = {"yellow": 120000, "red": 200000}
    s = Session(cfg, "unused.json", renderer=lambda *a: a)
    s.ingest(_snap(handles=100000, conpty=0, processes=0, memory=0.0))
    assert s.value == 50.0
    assert s.driver == "handles"


def test_mark_before_any_reading_does_nothing():
    s = Session(_config(), "unused.json", renderer=lambda *a: a)
    assert s.mark_redline() is False
    assert s.calibration_mode == "auto"


# ---- C9: Reset calibration ---------------------------------------------------------------


def test_C9_reset_calibration_reseeds(cfg_path):
    s = Session(load_config(cfg_path), cfg_path, renderer=lambda *a: a)
    s.ingest(_snap(ts=1.0, conpty=40, processes=400, handles=200000, memory=30.0))
    s.mark_redline()
    s.reset_calibration()
    assert s.calibration_mode == "auto"
    assert s.bands == Thresholds(conpty=Band(60.0, 100.0), memory_percent=Band(60, 80),
                                 process_count=Band(600.0, 1000.0), handle_count=Band(300000.0, 500000.0))
    assert s.value == 40.0
    assert s.exit_write() is True
    on_disk = _file(cfg_path)
    assert on_disk["calibration"] == {"mode": "auto", "highs": {"conpty": 100.0, "process_count": 1000.0,
                                                                  "handle_count": 500000.0}}


# ---- C10 / C11: memory is outside calibration; direct edits wait for the next launch --------


def test_C10_memory_is_outside_calibration():
    s = Session(_config(calibration={"mode": "auto", "highs": dict(STORED)}), "unused.json",
                renderer=lambda *a: a)
    s.ingest(_snap(conpty=0, processes=0, handles=0, memory=66.0))
    assert s.value == 72.0 and s.driver == "memory"


def test_C11_a_direct_edit_to_highs_waits_for_the_next_launch(cfg_path):
    data = _file(cfg_path)
    data["calibration"] = {"mode": "auto", "highs": dict(STORED)}
    cfg_path.write_text(json.dumps(data), encoding="utf-8")
    s = Session(load_config(cfg_path), cfg_path, renderer=lambda *a: a)
    s.ingest(_snap())
    data["calibration"]["highs"]["handle_count"] = 999999
    cfg_path.write_text(json.dumps(data), encoding="utf-8")
    s.reread_thresholds()
    assert s.bands.handle_count == Band(150000.0, 250000.0)   # unchanged mid-session
    s.exit_write()
    assert _file(cfg_path)["calibration"]["highs"]["handle_count"] == 999999   # never lowered
    relaunched = Session(load_config(cfg_path), cfg_path, renderer=lambda *a: a)
    assert relaunched.bands.handle_count == Band(599999.4, 999999.0)


def test_auto_mode_hot_reload_applies_to_memory_only(cfg_path):
    data = _file(cfg_path)
    data["calibration"] = {"mode": "auto", "highs": dict(STORED)}
    cfg_path.write_text(json.dumps(data), encoding="utf-8")
    collector = _Collector()
    s = Session(load_config(cfg_path), cfg_path, collector=collector, renderer=lambda *a: a)
    data["thresholds"]["memory_percent"] = {"yellow": 50, "red": 70}
    data["thresholds"]["conpty"] = {"yellow": 1, "red": 2}
    cfg_path.write_text(json.dumps(data), encoding="utf-8")
    assert s.reread_thresholds() is True
    assert s.bands.memory_percent == Band(50.0, 70.0)
    assert s.bands.conpty == Band(36.0, 60.0)                  # from the highs, not the file's thresholds
    assert collector.thresholds == s.bands


# ---- C12: validation ----------------------------------------------------------------------


def test_C12_invalid_calibration_mode_names_the_key(cfg_path):
    data = _file(cfg_path)
    data["calibration"] = {"mode": "sometimes", "highs": {}}
    cfg_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ConfigError) as err:
        load_config(cfg_path)
    assert str(err.value) == "config key 'calibration.mode': expected one of auto, manual, got 'sometimes'"


def test_invalid_high_names_the_metric(cfg_path):
    data = _file(cfg_path)
    data["calibration"] = {"mode": "auto", "highs": {"handle_count": -1}}
    cfg_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ConfigError, match="calibration.highs.handle_count"):
        load_config(cfg_path)


def test_a_1_0_0_config_file_without_calibration_still_loads(cfg_path):
    data = _file(cfg_path)
    del data["calibration"]
    cfg_path.write_text(json.dumps(data), encoding="utf-8")
    cfg = load_config(cfg_path)
    assert cfg["calibration"] == {"mode": "auto", "highs": {}}


# ---- the seed floor -----------------------------------------------------------------------


def test_seed_floor_keeps_red_above_zero():
    assert seeded_highs({"conpty": 0, "process_count": 0, "handle_count": 0}) == {
        "conpty": 2.5 * SEED_FLOORS["conpty"], "process_count": 2.5 * SEED_FLOORS["process_count"],
        "handle_count": 2.5 * SEED_FLOORS["handle_count"]}
    bands = bands_for(_config(), {"conpty": 0, "process_count": 0, "handle_count": 0})
    assert bands.conpty == Band(6.0, 10.0)                     # floor 4: yellow 1.5 x 4, red 2.5 x 4
