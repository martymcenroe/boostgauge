"""Unit tests for configuration manager and CLI argument mapping logic.

Ref: docs/design/0001-test-strategy.md
Constraint: No tkinter.Tk() in unit tests.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, mock_open, patch
import pytest

from boostgauge.config import (
    ConfigManager,
    get_default_config,
    get_default_config_path,
    load_config,
    override_config_with_cli,
    parse_cli_args,
    save_config,
    validate_config,
)


@pytest.fixture
def temp_config_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Provides a temporary config file path."""
    yield tmp_path / "config.json"


# ---- get_default_config_path ----

def test_default_config_path_returns_config_json() -> None:
    path = get_default_config_path()
    assert path.name == "config.json"


def test_default_config_path_contains_boostgauge() -> None:
    path = get_default_config_path()
    assert "boostgauge" in path.parts or ".boostgauge" in path.parts


def test_default_config_path_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(os, "name", "nt")
    monkeypatch.setenv("APPDATA", "C:\\Users\\testuser\\AppData\\Roaming")
    path = get_default_config_path()
    assert "boostgauge" in path.parts
    assert path.name == "config.json"


def test_default_config_path_windows_no_appdata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(os, "name", "nt")
    monkeypatch.delenv("APPDATA", raising=False)
    path = get_default_config_path()
    assert path.name == "config.json"
    assert "boostgauge" in str(path)


def test_default_config_path_unix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(os, "name", "posix")
    path = get_default_config_path()
    assert path.name == "config.json"
    assert "boostgauge" in str(path)


# ---- get_default_config ----

def test_default_config_structure() -> None:
    conf = get_default_config()
    assert conf["polling_interval_seconds"] == 2.0
    assert conf["theme"] == "dark"
    assert conf["size"] == 256
    assert conf["opacity"] == 0.85
    assert conf["always_on_top"] is True
    assert conf["position"]["x"] == 100
    assert conf["position"]["y"] == 100
    assert conf["thresholds"]["conpty"]["yellow"] == 4.0
    assert conf["thresholds"]["conpty"]["red"] == 8.0
    assert conf["thresholds"]["memory_percent"]["yellow"] == 80.0
    assert conf["thresholds"]["memory_percent"]["red"] == 90.0
    assert conf["thresholds"]["process_count"]["yellow"] == 10.0
    assert conf["thresholds"]["process_count"]["red"] == 20.0
    assert conf["thresholds"]["handle_count"]["yellow"] == 500.0
    assert conf["thresholds"]["handle_count"]["red"] == 1000.0
    assert conf["telltale_windows"]["short"] == 60
    assert conf["telltale_windows"]["medium"] == 600
    assert conf["telltale_windows"]["long"] == 3600
    assert conf["show_driver_label"] is True
    assert conf["show_digital_readout"] is True
    assert conf["show_session_count"] is True


def test_default_config_returns_fresh_dict() -> None:
    conf1 = get_default_config()
    conf2 = get_default_config()
    assert conf1 is not conf2
    conf1["theme"] = "mutated"
    assert conf2["theme"] == "dark"


# ---- validate_config ----

def test_validate_config_valid() -> None:
    valid_conf = get_default_config()
    validated = validate_config(valid_conf)
    assert validated == valid_conf


def test_validate_config_not_dict() -> None:
    with pytest.raises(TypeError):
        validate_config("not a dict")  # type: ignore[arg-type]


def test_validate_config_invalid_polling_interval_negative() -> None:
    conf = get_default_config()
    conf["polling_interval_seconds"] = -1.0
    with pytest.raises(ValueError):
        validate_config(conf)


def test_validate_config_invalid_polling_interval_zero() -> None:
    conf = get_default_config()
    conf["polling_interval_seconds"] = 0
    with pytest.raises(ValueError):
        validate_config(conf)


def test_validate_config_invalid_polling_interval_type() -> None:
    conf = get_default_config()
    conf["polling_interval_seconds"] = "invalid"
    with pytest.raises(TypeError):
        validate_config(conf)


def test_validate_config_invalid_polling_interval_bool() -> None:
    conf = get_default_config()
    conf["polling_interval_seconds"] = True
    with pytest.raises(TypeError):
        validate_config(conf)


def test_validate_config_invalid_theme_type() -> None:
    conf = get_default_config()
    conf["theme"] = 42
    with pytest.raises(TypeError):
        validate_config(conf)


def test_validate_config_invalid_theme_empty() -> None:
    conf = get_default_config()
    conf["theme"] = "   "
    with pytest.raises(ValueError):
        validate_config(conf)


def test_validate_config_invalid_size_too_small() -> None:
    conf = get_default_config()
    conf["size"] = 100
    with pytest.raises(ValueError):
        validate_config(conf)


def test_validate_config_invalid_size_too_large() -> None:
    conf = get_default_config()
    conf["size"] = 2048
    with pytest.raises(ValueError):
        validate_config(conf)


def test_validate_config_invalid_size_type() -> None:
    conf = get_default_config()
    conf["size"] = 256.5
    with pytest.raises(TypeError):
        validate_config(conf)


def test_validate_config_invalid_size_bool() -> None:
    conf = get_default_config()
    conf["size"] = True
    with pytest.raises(TypeError):
        validate_config(conf)


def test_validate_config_invalid_opacity_too_high() -> None:
    conf = get_default_config()
    conf["opacity"] = 1.5
    with pytest.raises(ValueError):
        validate_config(conf)


def test_validate_config_invalid_opacity_too_low() -> None:
    conf = get_default_config()
    conf["opacity"] = 0.05
    with pytest.raises(ValueError):
        validate_config(conf)


def test_validate_config_invalid_opacity_type() -> None:
    conf = get_default_config()
    conf["opacity"] = "high"
    with pytest.raises(TypeError):
        validate_config(conf)


def test_validate_config_invalid_opacity_bool() -> None:
    conf = get_default_config()
    conf["opacity"] = False
    with pytest.raises(TypeError):
        validate_config(conf)


def test_validate_config_invalid_always_on_top_type() -> None:
    conf = get_default_config()
    conf["always_on_top"] = "yes"
    with pytest.raises(TypeError):
        validate_config(conf)


def test_validate_config_invalid_position_type() -> None:
    conf = get_default_config()
    conf["position"] = "100,200"
    with pytest.raises(TypeError):
        validate_config(conf)


def test_validate_config_invalid_position_x_type() -> None:
    conf = get_default_config()
    conf["position"]["x"] = 1.5
    with pytest.raises(TypeError):
        validate_config(conf)


def test_validate_config_invalid_position_y_type() -> None:
    conf = get_default_config()
    conf["position"]["y"] = "200"
    with pytest.raises(TypeError):
        validate_config(conf)


def test_validate_config_negative_position_allowed() -> None:
    conf = get_default_config()
    conf["position"]["x"] = -100
    conf["position"]["y"] = -200
    validated = validate_config(conf)
    assert validated["position"]["x"] == -100
    assert validated["position"]["y"] == -200


def test_validate_config_invalid_thresholds_type() -> None:
    conf = get_default_config()
    conf["thresholds"] = "bad"
    with pytest.raises(TypeError):
        validate_config(conf)


def test_validate_config_invalid_threshold_key_type() -> None:
    conf = get_default_config()
    conf["thresholds"]["conpty"] = "bad"
    with pytest.raises(TypeError):
        validate_config(conf)


def test_validate_config_invalid_threshold_subkey_type() -> None:
    conf = get_default_config()
    conf["thresholds"]["conpty"]["yellow"] = "high"
    with pytest.raises(TypeError):
        validate_config(conf)


def test_validate_config_threshold_negative_value() -> None:
    conf = get_default_config()
    conf["thresholds"]["conpty"]["yellow"] = -1.0
    with pytest.raises(ValueError):
        validate_config(conf)


def test_validate_config_threshold_yellow_gte_red() -> None:
    conf = get_default_config()
    conf["thresholds"]["conpty"]["yellow"] = 10.0
    conf["thresholds"]["conpty"]["red"] = 5.0
    with pytest.raises(ValueError):
        validate_config(conf)


def test_validate_config_threshold_yellow_equal_red() -> None:
    conf = get_default_config()
    conf["thresholds"]["conpty"]["yellow"] = 8.0
    conf["thresholds"]["conpty"]["red"] = 8.0
    with pytest.raises(ValueError):
        validate_config(conf)


def test_validate_config_invalid_telltale_type() -> None:
    conf = get_default_config()
    conf["telltale_windows"] = "bad"
    with pytest.raises(TypeError):
        validate_config(conf)


def test_validate_config_invalid_telltale_key_type() -> None:
    conf = get_default_config()
    conf["telltale_windows"]["short"] = 1.5
    with pytest.raises(TypeError):
        validate_config(conf)


def test_validate_config_invalid_telltale_negative() -> None:
    conf = get_default_config()
    conf["telltale_windows"]["short"] = -60
    with pytest.raises(ValueError):
        validate_config(conf)


def test_validate_config_invalid_telltale_order_short_medium() -> None:
    conf = get_default_config()
    conf["telltale_windows"]["short"] = 600
    conf["telltale_windows"]["medium"] = 60
    with pytest.raises(ValueError):
        validate_config(conf)


def test_validate_config_invalid_telltale_order_medium_long() -> None:
    conf = get_default_config()
    conf["telltale_windows"]["medium"] = 3600
    conf["telltale_windows"]["long"] = 600
    with pytest.raises(ValueError):
        validate_config(conf)


def test_validate_config_invalid_show_flag_type() -> None:
    conf = get_default_config()
    conf["show_driver_label"] = "yes"
    with pytest.raises(TypeError):
        validate_config(conf)


def test_validate_config_invalid_show_digital_readout_type() -> None:
    conf = get_default_config()
    conf["show_digital_readout"] = 1
    with pytest.raises(TypeError):
        validate_config(conf)


def test_validate_config_invalid_show_session_count_type() -> None:
    conf = get_default_config()
    conf["show_session_count"] = None
    with pytest.raises(TypeError):
        validate_config(conf)


# ---- load_config ----

def test_load_config_creates_file_if_missing(temp_config_dir: Path) -> None:
    assert not temp_config_dir.exists()
    config = load_config(temp_config_dir)
    assert temp_config_dir.exists()
    assert config["theme"] == "dark"


def test_load_config_returns_defaults_on_creation(temp_config_dir: Path) -> None:
    config = load_config(temp_config_dir)
    assert config == get_default_config()


def test_load_config_reads_existing_file(temp_config_dir: Path) -> None:
    original = get_default_config()
    original["theme"] = "light"
    save_config(original, temp_config_dir)
    loaded = load_config(temp_config_dir)
    assert loaded["theme"] == "light"


def test_load_config_invalid_json(temp_config_dir: Path) -> None:
    temp_config_dir.write_text("{invalid json", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid JSON"):
        load_config(temp_config_dir)


# ---- save_config ----

def test_save_config_writes_file(temp_config_dir: Path) -> None:
    config = get_default_config()
    save_config(config, temp_config_dir)
    assert temp_config_dir.exists()
    with open(temp_config_dir, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded == config


def test_save_config_creates_parent_dirs(tmp_path: Path) -> None:
    nested_path = tmp_path / "nested" / "dir" / "config.json"
    config = get_default_config()
    save_config(config, nested_path)
    assert nested_path.exists()


def test_save_config_atomic_no_tmp_leftover(temp_config_dir: Path) -> None:
    config = get_default_config()
    save_config(config, temp_config_dir)
    tmp_path = temp_config_dir.with_suffix(".tmp")
    assert not tmp_path.exists()


def test_save_config_overwrites_existing(temp_config_dir: Path) -> None:
    config = get_default_config()
    save_config(config, temp_config_dir)
    config["theme"] = "updated"
    save_config(config, temp_config_dir)
    with open(temp_config_dir, "r", encoding="utf-8") as f:
        reloaded = json.load(f)
    assert reloaded["theme"] == "updated"


# ---- parse_cli_args ----

def test_parse_cli_args_all_options() -> None:
    parsed = parse_cli_args([
        "--theme", "light",
        "--size", "500",
        "--poll", "1.5",
        "--opacity", "0.7",
        "--no-topmost",
    ])
    assert parsed.theme == "light"
    assert parsed.size == 500
    assert parsed.poll == 1.5
    assert parsed.opacity == 0.7
    assert parsed.no_topmost is True


def test_parse_cli_args_config_and_reset() -> None:
    parsed = parse_cli_args([
        "--config", "/path/to/config.json",
        "--reset-config",
    ])
    assert parsed.config == "/path/to/config.json"
    assert parsed.reset_config is True


def test_parse_cli_args_defaults_when_empty() -> None:
    parsed = parse_cli_args([])
    assert parsed.theme is None
    assert parsed.size is None
    assert parsed.poll is None
    assert parsed.opacity is None
    assert parsed.no_topmost is False
    assert parsed.config is None
    assert parsed.reset_config is False


def test_parse_cli_args_invalid_size_exits(capsys: pytest.CaptureFixture) -> None:
    with pytest.raises(SystemExit) as exc_info:
        parse_cli_args(["--size", "abc"])
    assert exc_info.value.code == 2


def test_parse_cli_args_invalid_poll_exits() -> None:
    with pytest.raises(SystemExit) as exc_info:
        parse_cli_args(["--poll", "not_a_float"])
    assert exc_info.value.code == 2


def test_parse_cli_args_full_set() -> None:
    parsed = parse_cli_args([
        "--theme", "light",
        "--size", "512",
        "--poll", "1.5",
        "--opacity", "0.5",
        "--no-topmost",
        "--config", "/path/to/config.json",
        "--reset-config",
    ])
    assert parsed.theme == "light"
    assert parsed.size == 512
    assert parsed.poll == 1.5
    assert parsed.opacity == 0.5
    assert parsed.no_topmost is True
    assert parsed.config == "/path/to/config.json"
    assert parsed.reset_config is True


# ---- override_config_with_cli ----

def test_override_config_with_cli_all_overrides() -> None:
    config = get_default_config()
    cli = argparse.Namespace(
        theme="light", size=500, poll=1.5, opacity=0.9, no_topmost=True
    )
    overridden = override_config_with_cli(config, cli)
    assert overridden["theme"] == "light"
    assert overridden["size"] == 500
    assert overridden["polling_interval_seconds"] == 1.5
    assert overridden["opacity"] == 0.9
    assert overridden["always_on_top"] is False


def test_override_config_with_cli_none_values_preserved() -> None:
    config = get_default_config()
    cli = argparse.Namespace(
        theme=None, size=None, poll=None, opacity=None, no_topmost=False
    )
    overridden = override_config_with_cli(config, cli)
    assert overridden["theme"] == "dark"
    assert overridden["size"] == 256
    assert overridden["polling_interval_seconds"] == 2.0
    assert overridden["opacity"] == 0.85
    assert overridden["always_on_top"] is True


def test_override_config_with_cli_no_topmost_false_keeps_original() -> None:
    config = get_default_config()
    config["always_on_top"] = True
    cli = argparse.Namespace(
        theme=None, size=None, poll=None, opacity=None, no_topmost=False
    )
    overridden = override_config_with_cli(config, cli)
    assert overridden["always_on_top"] is True


def test_override_config_with_cli_does_not_mutate_original() -> None:
    config = get_default_config()
    original_theme = config["theme"]
    cli = argparse.Namespace(
        theme="light", size=None, poll=None, opacity=None, no_topmost=False
    )
    override_config_with_cli(config, cli)
    assert config["theme"] == original_theme


def test_override_config_with_cli_partial_overrides() -> None:
    config = get_default_config()
    cli = argparse.Namespace(
        theme="custom", size=None, poll=None, opacity=None, no_topmost=False
    )
    overridden = override_config_with_cli(config, cli)
    assert overridden["theme"] == "custom"
    assert overridden["size"] == 256


# ---- ConfigManager ----

def test_config_manager_load_creates_and_returns_config(temp_config_dir: Path) -> None:
    mgr = ConfigManager(config_path=temp_config_dir)
    loaded = mgr.load()
    assert loaded["theme"] == "dark"
    assert temp_config_dir.exists()


def test_config_manager_load_with_cli_overrides(temp_config_dir: Path) -> None:
    cli = argparse.Namespace(
        theme="custom-cli",
        size=None,
        poll=None,
        opacity=None,
        no_topmost=False,
        config=str(temp_config_dir),
    )
    mgr = ConfigManager(config_path=temp_config_dir, cli_args=cli)
    loaded = mgr.load()
    assert loaded["theme"] == "custom-cli"
    assert mgr.get("theme") == "custom-cli"


def test_config_manager_save_persists_changes(temp_config_dir: Path) -> None:
    mgr = ConfigManager(config_path=temp_config_dir)
    mgr.load()
    mgr.update_position_and_size(250, 350, 450)
    mgr.save()

    plain_mgr = ConfigManager(config_path=temp_config_dir)
    fresh = plain_mgr.load()
    assert fresh["position"]["x"] == 250
    assert fresh["position"]["y"] == 350
    assert fresh["size"] == 450


def test_config_manager_update_position_and_size(temp_config_dir: Path) -> None:
    mgr = ConfigManager(config_path=temp_config_dir)
    mgr.load()
    mgr.update_position_and_size(10, 20, 512)
    assert mgr.get("position")["x"] == 10
    assert mgr.get("position")["y"] == 20
    assert mgr.get("size") == 512


def test_config_manager_get_raises_on_missing_key(temp_config_dir: Path) -> None:
    mgr = ConfigManager(config_path=temp_config_dir)
    mgr.load()
    with pytest.raises(KeyError):
        mgr.get("nonexistent_key")


def test_config_manager_check_and_reload_detects_change(temp_config_dir: Path) -> None:
    mgr = ConfigManager(config_path=temp_config_dir)
    mgr.load()

    assert mgr.get("theme") == "dark"

    updated = get_default_config()
    updated["theme"] = "light"
    import time
    time.sleep(0.05)
    save_config(updated, temp_config_dir)

    reloaded = mgr.check_and_reload()
    assert reloaded is True
    assert mgr.get("theme") == "light"


def test_config_manager_check_and_reload_no_change(temp_config_dir: Path) -> None:
    mgr = ConfigManager(config_path=temp_config_dir)
    mgr.load()
    reloaded = mgr.check_and_reload()
    assert reloaded is False


def test_config_manager_check_and_reload_invalid_json(temp_config_dir: Path, capsys: pytest.CaptureFixture) -> None:
    mgr = ConfigManager(config_path=temp_config_dir)
    mgr.load()
    original_theme = mgr.get("theme")

    import time
    time.sleep(0.05)
    temp_config_dir.write_text("{invalid json", encoding="utf-8")

    result = mgr.check_and_reload()
    assert result is False
    assert mgr.get("theme") == original_theme
    captured = capsys.readouterr()
    assert "Warning" in captured.err


def test_config_manager_check_and_reload_invalid_values(temp_config_dir: Path, capsys: pytest.CaptureFixture) -> None:
    mgr = ConfigManager(config_path=temp_config_dir)
    mgr.load()
    original_opacity = mgr.get("opacity")

    invalid = get_default_config()
    invalid["opacity"] = "not a float"
    import time
    time.sleep(0.05)
    save_config(invalid, temp_config_dir)

    result = mgr.check_and_reload()
    assert result is False
    assert mgr.get("opacity") == original_opacity
    captured = capsys.readouterr()
    assert "Warning" in captured.err


def test_config_manager_check_and_reload_missing_file(temp_config_dir: Path) -> None:
    mgr = ConfigManager(config_path=temp_config_dir)
    mgr.load()
    temp_config_dir.unlink()
    result = mgr.check_and_reload()
    assert result is False


def test_config_manager_uses_default_path_when_none() -> None:
    mgr = ConfigManager()
    assert mgr.config_path.name == "config.json"
    assert "boostgauge" in str(mgr.config_path)


def test_config_manager_uses_cli_config_path(tmp_path: Path) -> None:
    custom_path = tmp_path / "custom.json"
    cli = argparse.Namespace(
        theme=None,
        size=None,
        poll=None,
        opacity=None,
        no_topmost=False,
        config=str(custom_path),
    )
    mgr = ConfigManager(cli_args=cli)
    assert mgr.config_path == custom_path.resolve()


def test_config_manager_explicit_path_takes_priority_over_cli(tmp_path: Path) -> None:
    explicit_path = tmp_path / "explicit.json"
    cli_path = tmp_path / "cli.json"
    cli = argparse.Namespace(
        theme=None,
        size=None,
        poll=None,
        opacity=None,
        no_topmost=False,
        config=str(cli_path),
    )
    mgr = ConfigManager(config_path=explicit_path, cli_args=cli)
    assert mgr.config_path == explicit_path.resolve()