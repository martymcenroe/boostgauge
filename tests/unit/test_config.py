"""Unit tests for boostgauge.config module."""

import json
from pathlib import Path
import pytest
import sys

from boostgauge.config import (
    BoostGaugeConfig,
    CLIArgs,
    ConfigValidationError,
    PositionConfig,
    ThresholdRange,
    ThresholdsConfig,
    get_default_config_path,
    load_config,
    merge_config_and_cli,
    parse_cli_args,
    save_config,
    validate_config_dict,
)


def test_default_config_path_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", "C:\\Users\\TestUser\\AppData\\Roaming")
    path = get_default_config_path()
    assert path.parts[-1] == "config.json"
    assert path.parts[-2] == "boostgauge"
    assert "Roaming" in str(path)


def test_default_config_path_windows_no_appdata(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delenv("APPDATA", raising=False)
    path = get_default_config_path()
    assert path.parts[-1] == "config.json"
    assert path.parts[-2] == "boostgauge"
    assert "Roaming" in str(path)


def test_default_config_path_posix(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    path = get_default_config_path()
    assert str(path).endswith(".boostgauge/config.json")


def test_parse_cli_args_all_flags():
    args = [
        "--theme", "light",
        "--size", "450",
        "--poll", "1.0",
        "--opacity", "0.8",
        "--no-topmost",
        "--config", "/tmp/custom.json",
        "--reset-config",
    ]
    parsed = parse_cli_args(args)
    assert parsed.theme == "light"
    assert parsed.size == 450
    assert parsed.poll == 1.0
    assert parsed.opacity == 0.8
    assert parsed.no_topmost is True
    assert parsed.config == Path("/tmp/custom.json")
    assert parsed.reset_config is True


def test_parse_cli_args_empty_defaults():
    parsed = parse_cli_args([])
    assert parsed.theme is None
    assert parsed.size is None
    assert parsed.poll is None
    assert parsed.opacity is None
    assert parsed.no_topmost is None
    assert parsed.config is None
    assert parsed.reset_config is False


def test_parse_cli_args_theme_dark():
    parsed = parse_cli_args(["--theme", "dark"])
    assert parsed.theme == "dark"


def test_parse_cli_args_invalid_theme_rejected():
    with pytest.raises(SystemExit):
        parse_cli_args(["--theme", "neon"])


def test_merge_config_and_cli_theme_override():
    base = BoostGaugeConfig(theme="dark", size=300, always_on_top=True)
    cli = CLIArgs(theme="light")
    merged = merge_config_and_cli(base, cli)
    assert merged.theme == "light"
    assert merged.size == 300
    assert merged.always_on_top is True


def test_merge_config_and_cli_no_topmost():
    base = BoostGaugeConfig(always_on_top=True)
    cli = CLIArgs(no_topmost=True)
    merged = merge_config_and_cli(base, cli)
    assert merged.always_on_top is False


def test_merge_config_and_cli_poll_maps_to_interval():
    base = BoostGaugeConfig(polling_interval_seconds=2.0)
    cli = CLIArgs(poll=0.5)
    merged = merge_config_and_cli(base, cli)
    assert merged.polling_interval_seconds == 0.5


def test_merge_config_and_cli_none_args_unchanged():
    base = BoostGaugeConfig(theme="dark", size=300, opacity=0.9)
    cli = CLIArgs()
    merged = merge_config_and_cli(base, cli)
    assert merged.theme == "dark"
    assert merged.size == 300
    assert merged.opacity == 0.9


def test_merge_config_and_cli_size_and_opacity():
    base = BoostGaugeConfig(size=300, opacity=0.9)
    cli = CLIArgs(size=600, opacity=0.5)
    merged = merge_config_and_cli(base, cli)
    assert merged.size == 600
    assert merged.opacity == 0.5


def test_validate_config_dict_valid_full():
    data = {
        "polling_interval_seconds": 2.0,
        "theme": "dark",
        "size": 300,
        "opacity": 0.9,
        "always_on_top": True,
        "position": {"x": 100, "y": 100},
        "thresholds": {
            "conpty": {"yellow": 30.0, "red": 60.0},
            "memory_percent": {"yellow": 60.0, "red": 80.0},
            "process_count": {"yellow": 300.0, "red": 500.0},
            "handle_count": {"yellow": 30000.0, "red": 50000.0},
        },
        "telltale_windows": {"short": 60, "medium": 600, "long": 3600},
        "show_driver_label": True,
        "show_digital_readout": True,
        "show_session_count": True,
    }
    config = validate_config_dict(data)
    assert config.theme == "dark"
    assert config.size == 300
    assert config.opacity == 0.9
    assert config.position.x == 100
    assert config.thresholds.conpty.yellow == 30.0


def test_validate_config_dict_partial_uses_defaults():
    data = {"theme": "light", "size": 500, "opacity": 0.75, "polling_interval_seconds": 1.0}
    config = validate_config_dict(data)
    assert config.theme == "light"
    assert config.size == 500
    assert config.opacity == 0.75
    assert config.polling_interval_seconds == 1.0
    assert config.always_on_top is True


def test_validate_config_dict_invalid_theme():
    with pytest.raises(ConfigValidationError, match="Invalid theme"):
        validate_config_dict({"theme": "neon_green"})


def test_validate_config_dict_invalid_opacity_high():
    with pytest.raises(ConfigValidationError, match="Invalid opacity"):
        validate_config_dict({"opacity": 1.5})


def test_validate_config_dict_invalid_opacity_negative():
    with pytest.raises(ConfigValidationError, match="Invalid opacity"):
        validate_config_dict({"opacity": -0.1})


def test_validate_config_dict_invalid_size_too_small():
    with pytest.raises(ConfigValidationError, match="Invalid size"):
        validate_config_dict({"size": 50})


def test_validate_config_dict_invalid_size_too_large():
    with pytest.raises(ConfigValidationError, match="Invalid size"):
        validate_config_dict({"size": 9999})


def test_validate_config_dict_invalid_threshold_order():
    data = {"thresholds": {"conpty": {"yellow": 80.0, "red": 50.0}}}
    with pytest.raises(ConfigValidationError, match="must be <= red threshold"):
        validate_config_dict(data)


def test_validate_config_dict_invalid_polling_interval():
    with pytest.raises(ConfigValidationError, match="Invalid polling_interval_seconds"):
        validate_config_dict({"polling_interval_seconds": 0.0})


def test_validate_config_dict_negative_threshold():
    data = {"thresholds": {"conpty": {"yellow": -5.0, "red": 60.0}}}
    with pytest.raises(ConfigValidationError):
        validate_config_dict(data)


def test_validate_config_dict_not_a_dict():
    with pytest.raises(ConfigValidationError, match="Configuration root"):
        validate_config_dict("not a dict")


def test_save_and_load_config_roundtrip(tmp_path):
    config_file = tmp_path / "config.json"
    original = BoostGaugeConfig(theme="light", size=450, opacity=0.7)
    save_config(original, config_file)

    assert config_file.exists()
    loaded = load_config(config_file)
    assert loaded.theme == "light"
    assert loaded.size == 450
    assert loaded.opacity == 0.7


def test_save_config_creates_parent_directories(tmp_path):
    config_file = tmp_path / "nested" / "deep" / "config.json"
    save_config(BoostGaugeConfig(), config_file)
    assert config_file.exists()


def test_save_config_writes_valid_json(tmp_path):
    config_file = tmp_path / "config.json"
    save_config(BoostGaugeConfig(), config_file)
    with open(config_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["theme"] == "dark"
    assert data["size"] == 300


def test_load_config_auto_creates_missing_file(tmp_path):
    config_file = tmp_path / "missing" / "config.json"
    assert not config_file.exists()
    config = load_config(config_file)
    assert config_file.exists()
    assert config == BoostGaugeConfig()


def test_load_config_returns_defaults_on_creation(tmp_path):
    config_file = tmp_path / "config.json"
    config = load_config(config_file)
    assert config.theme == "dark"
    assert config.size == 300
    assert config.polling_interval_seconds == 2.0


def test_load_config_invalid_json(tmp_path):
    config_file = tmp_path / "bad.json"
    config_file.write_text("{not valid json:", encoding="utf-8")
    with pytest.raises(ConfigValidationError, match="Failed to parse JSON configuration file"):
        load_config(config_file)


def test_load_config_from_sample_fixture():
    fixture_path = Path(__file__).parent.parent / "fixtures" / "sample_config.json"
    config = load_config(fixture_path)
    assert config.theme == "dark"
    assert config.size == 300
    assert config.opacity == 0.9
    assert config.thresholds.conpty.yellow == 30.0
    assert config.thresholds.conpty.red == 60.0
    assert config.telltale_windows.short == 60


def test_boostgauge_config_default_values():
    config = BoostGaugeConfig()
    assert config.polling_interval_seconds == 2.0
    assert config.theme == "dark"
    assert config.size == 300
    assert config.opacity == 0.9
    assert config.always_on_top is True
    assert config.position.x == 100
    assert config.position.y == 100
    assert config.show_driver_label is True
    assert config.show_digital_readout is True
    assert config.show_session_count is True


def test_threshold_defaults():
    config = BoostGaugeConfig()
    assert config.thresholds.conpty.yellow == 30.0
    assert config.thresholds.conpty.red == 60.0
    assert config.thresholds.memory_percent.yellow == 60.0
    assert config.thresholds.memory_percent.red == 80.0
    assert config.thresholds.process_count.yellow == 300.0
    assert config.thresholds.process_count.red == 500.0
    assert config.thresholds.handle_count.yellow == 30000.0
    assert config.thresholds.handle_count.red == 50000.0


def test_telltale_windows_defaults():
    config = BoostGaugeConfig()
    assert config.telltale_windows.short == 60
    assert config.telltale_windows.medium == 600
    assert config.telltale_windows.long == 3600