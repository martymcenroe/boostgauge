"""Unit tier for the config module — named by issue #7's criteria, literal values throughout.

L (launch), H (threshold hot-reload), E (exit write), B (byte-identical), P
(position table), S (size table), V (validation), N (non-threshold reload),
plus the CLI parser, the default path, and the bridge to the collector's
``Thresholds``. No window exists in this tier; "the window opens at" is
asserted as the values the launch read hands the app.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from boostgauge.config import (DEFAULT_CONFIG, ConfigError, apply_threshold_updates,
                               default_config_path, load_config, parse_cli,
                               save_session_changes, thresholds_from_config)

DEFAULT_POSITION = {"x": 100, "y": 100}
DEFAULT_SIZE = 300


def _write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def cfg(tmp_path) -> Path:
    return tmp_path / "config.json"


@pytest.fixture
def existing(cfg) -> Path:
    """A config file with a non-default position and size, as a returning user would have."""
    data = json.loads(json.dumps(DEFAULT_CONFIG))
    data["position"] = {"x": 5, "y": 6}
    data["size"] = 200
    _write(cfg, data)
    return cfg


# ---- L: launch ---------------------------------------------------------------------


def test_L1_first_run_creates_the_file_with_defaults(cfg):
    config = load_config(cfg)
    assert cfg.exists()
    assert _read(cfg) == DEFAULT_CONFIG
    assert config == DEFAULT_CONFIG
    assert _read(cfg)["thresholds"] == {
        "conpty": {"yellow": 30, "red": 60},
        "memory_percent": {"yellow": 60, "red": 80},
        "process_count": {"yellow": 300, "red": 500},
        "handle_count": {"yellow": 30000, "red": 50000},
    }


def test_L2_launch_order_and_overrides_never_written(existing):
    config = load_config(existing, reset_flag=False, cli_overrides={"size": 400, "theme": "neon"})
    assert config["size"] == 400 and config["theme"] == "neon"
    assert _read(existing)["size"] == 200 and _read(existing)["theme"] == "dark"

    config = load_config(existing, reset_flag=True, cli_overrides={"size": 500})
    assert config["size"] == 500                      # override governs the session
    assert _read(existing)["size"] == DEFAULT_SIZE    # the reset wrote defaults, not 500


def test_L3_no_overrides_opens_at_the_files_geometry(existing):
    config = load_config(existing)
    assert config["position"] == {"x": 5, "y": 6}
    assert config["size"] == 200


def test_L4_reset_opens_at_defaults_unless_size_is_given(existing):
    config = load_config(existing, reset_flag=True)
    assert config["position"] == DEFAULT_POSITION and config["size"] == DEFAULT_SIZE
    _write(existing, {**_read(existing), "position": {"x": 5, "y": 6}, "size": 200})
    config = load_config(existing, reset_flag=True, cli_overrides={"size": 444})
    assert config["position"] == DEFAULT_POSITION and config["size"] == 444
    assert _read(existing)["size"] == DEFAULT_SIZE    # at that launch moment the file holds the default


def test_L5_size_override_without_reset_keeps_the_files_position(existing):
    config = load_config(existing, cli_overrides={"size": 444})
    assert config["position"] == {"x": 5, "y": 6} and config["size"] == 444


# ---- H / N: mid-session re-read ------------------------------------------------------


def test_H1_threshold_edits_apply_without_restart_and_reads_never_write(existing):
    config = load_config(existing)
    before = existing.read_bytes()
    data = _read(existing)
    data["thresholds"]["conpty"] = {"yellow": 10, "red": 20}
    _write(existing, data)
    edited = existing.read_bytes()

    updated = apply_threshold_updates(existing, config)
    assert updated["thresholds"]["conpty"] == {"yellow": 10, "red": 20}
    assert updated["thresholds"]["memory_percent"] == {"yellow": 60, "red": 80}
    assert config["thresholds"]["conpty"] == {"yellow": 30, "red": 60}   # the input is not mutated
    assert existing.read_bytes() == edited                               # the re-read wrote nothing
    assert before != edited                                              # (the edit itself, not the app)


def test_H1_invalid_threshold_edit_is_ignored_and_logged(existing, caplog):
    config = load_config(existing)
    data = _read(existing)
    data["thresholds"]["conpty"] = {"yellow": 90, "red": 10}   # yellow >= red
    _write(existing, data)
    with caplog.at_level(logging.ERROR):
        updated = apply_threshold_updates(existing, config)
    assert updated is config
    assert "thresholds.conpty" in caplog.text


def test_N1_non_threshold_edits_wait_for_the_next_launch(existing):
    config = load_config(existing)
    data = _read(existing)
    data["theme"] = "light"
    data["telltale_windows"]["short"] = 90
    _write(existing, data)

    updated = apply_threshold_updates(existing, config)
    assert updated["theme"] == "dark"                        # unchanged mid-session
    assert updated["telltale_windows"]["short"] == 60

    relaunched = load_config(existing)
    assert relaunched["theme"] == "light"                    # applied at the next launch
    assert relaunched["telltale_windows"]["short"] == 90


# ---- E / B: the exit write -------------------------------------------------------------


def test_E1_exit_write_touches_only_hand_changed_keys(existing):
    load_config(existing)
    data = _read(existing)
    data["theme"] = "classic"                                # a direct edit during the session
    _write(existing, data)
    assert save_session_changes(existing, hand_changed_position={"x": 50, "y": 60}) is True
    after = _read(existing)
    assert after["position"] == {"x": 50, "y": 60}
    assert after["theme"] == "classic"                       # the direct edit survived
    assert after["size"] == 200                              # not hand-changed, untouched


def test_E2_hand_made_value_wins_a_same_key_collision(existing):
    load_config(existing)
    data = _read(existing)
    data["size"] = 999                                       # direct edit to size
    data["opacity"] = 0.5                                    # direct edit to another key
    _write(existing, data)
    save_session_changes(existing, hand_changed_size=250)
    after = _read(existing)
    assert after["size"] == 250                              # hand-made wins
    assert after["opacity"] == 0.5                           # the other edit survives


def test_B1_untouched_session_writes_nothing(existing):
    load_config(existing)
    before = existing.read_bytes()
    assert save_session_changes(existing) is False
    assert existing.read_bytes() == before


# ---- P / S: the persistence tables -----------------------------------------------------

MOVED = {"x": 50, "y": 60}
RESIZED = 250
CLI_SIZE = 444


@pytest.mark.parametrize("row, reset, moved, expected", [
    ("P1", False, False, {"x": 5, "y": 6}),
    ("P2", False, True, MOVED),
    ("P3", True, False, DEFAULT_POSITION),
    ("P4", True, True, MOVED),
])
def test_position_table(existing, row, reset, moved, expected):
    load_config(existing, reset_flag=reset)
    save_session_changes(existing, hand_changed_position=MOVED if moved else None)
    assert _read(existing)["position"] == expected, row


@pytest.mark.parametrize("row, reset, cli, resized, expected", [
    ("S1", False, False, False, 200),
    ("S2", False, False, True, RESIZED),
    ("S3", False, True, False, 200),
    ("S4", False, True, True, RESIZED),
    ("S5", True, False, False, DEFAULT_SIZE),
    ("S6", True, False, True, RESIZED),
    ("S7", True, True, False, DEFAULT_SIZE),
    ("S8", True, True, True, RESIZED),
])
def test_size_table(existing, row, reset, cli, resized, expected):
    config = load_config(existing, reset_flag=reset, cli_overrides={"size": CLI_SIZE} if cli else None)
    if cli:
        assert config["size"] == CLI_SIZE                    # the session runs at the CLI size
    save_session_changes(existing, hand_changed_size=RESIZED if resized else None)
    assert _read(existing)["size"] == expected, row
    assert _read(existing)["size"] != CLI_SIZE               # the CLI value is never written


# ---- V: validation --------------------------------------------------------------------


@pytest.mark.parametrize("key, bad, fragment", [
    ("opacity", 5, "expected a number between 0.0 and 1.0, got 5"),
    ("theme", "sepia", "expected one of dark, light, neon, classic, got 'sepia'"),
    ("size", "big", "expected an integer number of pixels >= 64, got 'big'"),
    ("polling_interval_seconds", 0, "expected a number of seconds > 0, got 0"),
    ("always_on_top", "yes", "expected true or false, got 'yes'"),
])
def test_V1_invalid_values_name_the_key_expectation_and_value(cfg, key, bad, fragment):
    data = json.loads(json.dumps(DEFAULT_CONFIG))
    data[key] = bad
    _write(cfg, data)
    with pytest.raises(ConfigError) as err:
        load_config(cfg)
    assert f"config key {key!r}" in str(err.value)
    assert fragment in str(err.value)


def test_V1_nested_invalid_values_name_the_path(cfg):
    data = json.loads(json.dumps(DEFAULT_CONFIG))
    data["thresholds"]["handle_count"] = {"yellow": 50000, "red": 30000}
    _write(cfg, data)
    with pytest.raises(ConfigError, match="thresholds.handle_count"):
        load_config(cfg)
    data = json.loads(json.dumps(DEFAULT_CONFIG))
    data["telltale_windows"]["medium"] = -1
    _write(cfg, data)
    with pytest.raises(ConfigError, match="telltale_windows.medium"):
        load_config(cfg)


def test_V1_cli_override_values_are_validated_too(cfg):
    with pytest.raises(ConfigError, match="'opacity'"):
        load_config(cfg, cli_overrides={"opacity": 1.5})


def test_V1_corrupt_json_is_moved_aside_logged_and_recreated(cfg, caplog):
    cfg.write_text("{not json", encoding="utf-8")
    with caplog.at_level(logging.ERROR):
        config = load_config(cfg)
    assert config == DEFAULT_CONFIG
    assert _read(cfg) == DEFAULT_CONFIG
    assert (cfg.parent / "config.json.corrupt").read_text(encoding="utf-8") == "{not json"
    assert "not valid JSON" in caplog.text and "config.json.corrupt" in caplog.text


def test_exit_write_never_clobbers_a_file_that_is_not_json(existing, caplog):
    load_config(existing)
    existing.write_text("{user was mid-edit", encoding="utf-8")
    with caplog.at_level(logging.ERROR):
        assert save_session_changes(existing, hand_changed_size=250) is False
    assert existing.read_text(encoding="utf-8") == "{user was mid-edit"
    assert "exit write skipped" in caplog.text


def test_exit_write_and_reread_survive_a_deleted_file(existing, caplog):
    config = load_config(existing)
    existing.unlink()
    with caplog.at_level(logging.ERROR):
        assert apply_threshold_updates(existing, config) is config
        assert save_session_changes(existing, hand_changed_position={"x": 1, "y": 2}) is False
    assert not existing.exists()
    assert "could not re-read config" in caplog.text
    assert "could not read config" in caplog.text


def test_atomic_write_cleans_its_temp_file_when_replace_fails(cfg, monkeypatch):
    import os

    def refuse(src, dst):
        raise PermissionError("disk full")

    monkeypatch.setattr(os, "replace", refuse)
    with pytest.raises(PermissionError, match="disk full"):
        load_config(cfg)
    assert list(cfg.parent.iterdir()) == []          # no temp file left behind, no config either


# ---- CLI --------------------------------------------------------------------------


def test_cli_full_set():
    path, reset, overrides = parse_cli(["--theme", "neon", "--size", "400", "--poll", "1.5",
                                        "--opacity", "0.5", "--no-topmost",
                                        "--config", "x/y.json", "--reset-config"])
    assert path == Path("x/y.json")
    assert reset is True
    assert overrides == {"theme": "neon", "size": 400, "polling_interval_seconds": 1.5,
                         "opacity": 0.5, "always_on_top": False}


def test_cli_nothing_given_means_default_path_and_no_overrides(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr("boostgauge.config.sys.platform", "win32")
    path, reset, overrides = parse_cli([])
    assert path == tmp_path / "boostgauge" / "config.json"
    assert reset is False and overrides == {}


def test_cli_rejects_an_unknown_theme():
    with pytest.raises(SystemExit):
        parse_cli(["--theme", "sepia"])


def test_default_path_off_windows(monkeypatch, tmp_path):
    monkeypatch.setattr("boostgauge.config.sys.platform", "linux")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    assert default_config_path() == tmp_path / ".boostgauge" / "config.json"


# ---- bridge to the collector ----------------------------------------------------------


def test_thresholds_from_config_matches_the_collector_defaults():
    collector = pytest.importorskip("boostgauge.collector")  # pre-seeded before #4; the collector lands later in the arc
    Band, Thresholds = collector.Band, collector.Thresholds
    assert thresholds_from_config(DEFAULT_CONFIG) == Thresholds()
    assert thresholds_from_config(DEFAULT_CONFIG) == Thresholds(
        conpty=Band(30, 60), memory_percent=Band(60, 80),
        process_count=Band(300, 500), handle_count=Band(30000, 50000))
