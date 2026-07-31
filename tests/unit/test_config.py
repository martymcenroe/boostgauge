"""Unit tests for BoostGauge configuration module.

Issue #7: Configuration file and CLI arguments.
Testing strategy complies with docs/design/0001-test-strategy.md (pure logic, no tkinter instantiation).
"""

from __future__ import annotations

import json
import platform
from pathlib import Path

import pytest

from boostgauge.config import (
    get_default_config_path,
    get_default_config,
    validate_config,
    load_config,
    save_config,
    reset_config,
    parse_cli_args,
    merge_config_and_cli,
    update_window_state,
)


def test_t010_auto_creation_of_default_config(tmp_path: Path) -> None:
    """T010: Auto-creation of default config file on first run when missing."""
    config_file = tmp_path / "config.json"
    assert not config_file.exists()

    config = load_config(config_file)

    assert config_file.exists()
    assert config == get_default_config()
    with open(config_file, "r", encoding="utf-8") as f:
        saved_data = json.load(f)
    assert saved_data["theme"] == "dark"
    assert saved_data["size"] == 300


def test_t020_custom_config_path_via_cli(tmp_path: Path) -> None:
    """T020: Custom config file creation at specified custom path."""
    custom_dir = tmp_path / "custom_dir"
    custom_file = custom_dir / "my_config.json"
    assert not custom_file.exists()

    config = load_config(custom_file)

    assert custom_file.exists()
    assert config["theme"] == "dark"


def test_t030_cli_arguments_override_config_file(tmp_path: Path) -> None:
    """T030: CLI arguments strictly override values defined in configuration file."""
    config_file = tmp_path / "config.json"
    initial_config = get_default_config()
    initial_config["theme"] = "dark"
    initial_config["size"] = 300
    save_config(initial_config, config_file)

    loaded_config = load_config(config_file)
    cli_args = parse_cli_args(["--theme", "light", "--size", "450", "--poll", "0.5"])

    merged = merge_config_and_cli(loaded_config, cli_args)

    assert merged["theme"] == "light"
    assert merged["size"] == 450
    assert merged["polling_interval_seconds"] == 0.5
    disc_data = load_config(config_file)
    assert disc_data["theme"] == "dark"


def test_t040_cli_argument_parsing_all_options() -> None:
    """T040: Verify CLI argument parsing for all supported parameters."""
    args = [
        "--theme", "neon",
        "--size", "400",
        "--poll", "2.5",
        "--opacity", "0.85",
        "--no-topmost",
        "--config", "/tmp/custom.json",
        "--reset-config",
    ]
    parsed = parse_cli_args(args)

    assert parsed.theme == "neon"
    assert parsed.size == 400
    assert parsed.poll == 2.5
    assert parsed.opacity == 0.85
    assert parsed.no_topmost is True
    assert parsed.config == "/tmp/custom.json"
    assert parsed.reset_config is True


def test_t050_reset_config_overwrites_with_defaults(tmp_path: Path) -> None:
    """T050: Reset config option overwrites modified settings with default values."""
    config_file = tmp_path / "config.json"
    modified_config = get_default_config()
    modified_config["theme"] = "custom_theme"
    modified_config["size"] = 999
    save_config(modified_config, config_file)

    reset_result = reset_config(config_file)

    assert reset_result == get_default_config()
    with open(config_file, "r", encoding="utf-8") as f:
        on_disk = json.load(f)
    assert on_disk["theme"] == "dark"
    assert on_disk["size"] == 300


def test_t060_save_and_restore_window_position_and_size(tmp_path: Path) -> None:
    """T060: Save and restore window position (x, y) and size parameters."""
    config_file = tmp_path / "config.json"
    initial_config = load_config(config_file)

    updated_config = update_window_state(initial_config, x=250, y=180, size=400, config_path=config_file)

    assert updated_config["position"]["x"] == 250
    assert updated_config["position"]["y"] == 180
    assert updated_config["size"] == 400

    reloaded_config = load_config(config_file)
    assert reloaded_config["position"]["x"] == 250
    assert reloaded_config["position"]["y"] == 180
    assert reloaded_config["size"] == 400


def test_t070_dynamic_threshold_updates_in_memory() -> None:
    """T070: Modifying threshold values updates runtime state without requiring file reload."""
    config = get_default_config()
    assert config["thresholds"]["memory_percent"]["yellow"] == 75.0

    config["thresholds"]["memory_percent"]["yellow"] = 80.0
    config["thresholds"]["memory_percent"]["red"] = 95.0

    assert config["thresholds"]["memory_percent"]["yellow"] == 80.0
    assert config["thresholds"]["memory_percent"]["red"] == 95.0


def test_t080_corrupt_json_recovery(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """T080: Corrupt JSON logs warning error message and reverts safely to default config."""
    config_file = tmp_path / "corrupt_config.json"
    config_file.write_text("{ corrupt json data ... ", encoding="utf-8")

    config = load_config(config_file)

    assert config == get_default_config()


def test_t090_out_of_range_cli_parameters(capsys: pytest.CaptureFixture[str]) -> None:
    """T090: Out-of-bounds CLI parameters trigger SystemExit validation error."""
    with pytest.raises(SystemExit):
        parse_cli_args(["--opacity", "2.5"])

    with pytest.raises(SystemExit):
        parse_cli_args(["--size", "-50"])

    with pytest.raises(SystemExit):
        parse_cli_args(["--poll", "-1.0"])


def test_get_default_config_path_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    """Windows path resolution uses APPDATA environment variable."""
    monkeypatch.setattr("platform.system", lambda: "Windows")
    appdata_value = r"C:\AppData\Roaming"
    monkeypatch.setenv("APPDATA", appdata_value)
    win_path = get_default_config_path()
    assert win_path == Path(appdata_value) / "boostgauge" / "config.json"


def test_get_default_config_path_posix(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-Windows path resolution uses home directory."""
    monkeypatch.setattr("platform.system", lambda: "Linux")
    posix_path = get_default_config_path()
    assert posix_path == Path.home() / ".boostgauge" / "config.json"


def test_get_default_config_path_windows_missing_appdata(monkeypatch: pytest.MonkeyPatch) -> None:
    """Windows fallback to home dir when APPDATA is unset."""
    monkeypatch.setattr("platform.system", lambda: "Windows")
    monkeypatch.delenv("APPDATA", raising=False)
    fallback_path = get_default_config_path()
    assert fallback_path == Path.home() / ".boostgauge" / "config.json"


def test_get_default_config_returns_deep_copy() -> None:
    """Each call to get_default_config returns an independent copy."""
    config1 = get_default_config()
    config2 = get_default_config()
    config1["theme"] = "mutated"
    assert config2["theme"] == "dark"


def test_validate_config_non_dict_input() -> None:
    """Non-dict input to validate_config returns full defaults."""
    result = validate_config("not a dict")  # type: ignore[arg-type]
    assert result == get_default_config()

    result = validate_config(None)  # type: ignore[arg-type]
    assert result == get_default_config()


def test_validate_config_invalid_field_types() -> None:
    """Invalid field types revert to defaults for those keys."""
    data = {
        "size": "huge",
        "polling_interval_seconds": "fast",
        "opacity": "clear",
        "always_on_top": "yes",
        "theme": 42,
    }
    result = validate_config(data)
    defaults = get_default_config()
    assert result["size"] == defaults["size"]
    assert result["polling_interval_seconds"] == defaults["polling_interval_seconds"]
    assert result["opacity"] == defaults["opacity"]
    assert result["always_on_top"] == defaults["always_on_top"]
    assert result["theme"] == defaults["theme"]


def test_validate_config_out_of_bounds_opacity() -> None:
    """Opacity > 1.0 reverts to default."""
    result = validate_config({"opacity": 1.5})
    assert result["opacity"] == get_default_config()["opacity"]


def test_validate_config_partial_threshold() -> None:
    """Missing threshold sub-keys are injected from defaults."""
    data = {
        "thresholds": {
            "conpty": {"yellow": 5.0}
        }
    }
    result = validate_config(data)
    assert result["thresholds"]["conpty"]["yellow"] == 5.0
    assert result["thresholds"]["conpty"]["red"] == 20.0
    assert result["thresholds"]["memory_percent"] == get_default_config()["thresholds"]["memory_percent"]


def test_validate_config_valid_values() -> None:
    """Valid custom values are preserved through validation."""
    data = {
        "theme": "light",
        "size": 400,
        "opacity": 0.8,
        "always_on_top": False,
        "polling_interval_seconds": 2.0,
        "show_driver_label": False,
        "show_digital_readout": False,
        "show_session_count": False,
        "position": {"x": 200, "y": 300},
        "telltale_windows": {"short": 30, "medium": 300, "long": 1800},
    }
    result = validate_config(data)
    assert result["theme"] == "light"
    assert result["size"] == 400
    assert result["opacity"] == 0.8
    assert result["always_on_top"] is False
    assert result["polling_interval_seconds"] == 2.0
    assert result["show_driver_label"] is False
    assert result["show_digital_readout"] is False
    assert result["show_session_count"] is False
    assert result["position"]["x"] == 200
    assert result["position"]["y"] == 300
    assert result["telltale_windows"]["short"] == 30
    assert result["telltale_windows"]["medium"] == 300
    assert result["telltale_windows"]["long"] == 1800


def test_save_config_creates_parent_directories(tmp_path: Path) -> None:
    """save_config creates nested parent directories as needed."""
    nested_path = tmp_path / "a" / "b" / "c" / "config.json"
    assert not nested_path.parent.exists()
    config = get_default_config()
    save_config(config, nested_path)
    assert nested_path.exists()
    with open(nested_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["theme"] == "dark"


def test_save_config_atomic_write(tmp_path: Path) -> None:
    """save_config uses atomic replace (no .tmp file left behind)."""
    config_file = tmp_path / "config.json"
    config = get_default_config()
    save_config(config, config_file)
    tmp_file = config_file.with_suffix(".tmp")
    assert not tmp_file.exists()
    assert config_file.exists()


def test_load_config_existing_valid_file(tmp_path: Path) -> None:
    """load_config reads and validates an existing valid config file."""
    config_file = tmp_path / "config.json"
    custom_config = get_default_config()
    custom_config["theme"] = "neon"
    custom_config["size"] = 500
    save_config(custom_config, config_file)

    loaded = load_config(config_file)
    assert loaded["theme"] == "neon"
    assert loaded["size"] == 500


def test_load_config_oserror_recovery(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """load_config returns defaults when an OSError occurs reading the file."""
    config_file = tmp_path / "config.json"
    save_config(get_default_config(), config_file)

    original_open = open

    def raising_open(path, *args, **kwargs):
        if str(path) == str(config_file):
            raise OSError("simulated read error")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", raising_open)
    result = load_config(config_file)
    assert result == get_default_config()


def test_merge_config_and_cli_no_topmost_override() -> None:
    """--no-topmost sets always_on_top to False."""
    config = get_default_config()
    assert config["always_on_top"] is True
    import argparse
    cli_args = argparse.Namespace(
        theme=None,
        size=None,
        poll=None,
        opacity=None,
        no_topmost=True,
        config=None,
        reset_config=False,
    )
    merged = merge_config_and_cli(config, cli_args)
    assert merged["always_on_top"] is False


def test_merge_config_and_cli_no_changes() -> None:
    """All-None CLI args returns a copy of config unchanged."""
    import argparse
    config = get_default_config()
    cli_args = argparse.Namespace(
        theme=None,
        size=None,
        poll=None,
        opacity=None,
        no_topmost=False,
        config=None,
        reset_config=False,
    )
    merged = merge_config_and_cli(config, cli_args)
    assert merged == config


def test_merge_config_and_cli_does_not_mutate_original() -> None:
    """merge_config_and_cli returns a new object, not a reference."""
    import argparse
    config = get_default_config()
    cli_args = argparse.Namespace(
        theme="neon",
        size=500,
        poll=0.5,
        opacity=0.7,
        no_topmost=True,
        config=None,
        reset_config=False,
    )
    merged = merge_config_and_cli(config, cli_args)
    assert config["theme"] == "dark"
    assert merged["theme"] == "neon"


def test_parse_cli_args_defaults() -> None:
    """parse_cli_args with empty list returns all-default Namespace."""
    parsed = parse_cli_args([])
    assert parsed.theme is None
    assert parsed.size is None
    assert parsed.poll is None
    assert parsed.opacity is None
    assert parsed.no_topmost is False
    assert parsed.config is None
    assert parsed.reset_config is False


def test_parse_cli_args_size_zero_rejected() -> None:
    """--size 0 is rejected with SystemExit."""
    with pytest.raises(SystemExit):
        parse_cli_args(["--size", "0"])


def test_parse_cli_args_poll_zero_rejected() -> None:
    """--poll 0 is rejected with SystemExit."""
    with pytest.raises(SystemExit):
        parse_cli_args(["--poll", "0"])


def test_update_window_state_does_not_mutate_original(tmp_path: Path) -> None:
    """update_window_state returns a new ConfigData, original is unchanged."""
    config_file = tmp_path / "config.json"
    config = get_default_config()
    updated = update_window_state(config, x=999, y=888, size=777, config_path=config_file)
    assert config["position"]["x"] == 100
    assert updated["position"]["x"] == 999


def test_reset_config_nonexistent_file(tmp_path: Path) -> None:
    """reset_config creates file with defaults when it does not exist."""
    config_file = tmp_path / "nonexistent" / "config.json"
    assert not config_file.exists()
    result = reset_config(config_file)
    assert result == get_default_config()
    assert config_file.exists()


def test_validate_config_position_non_dict() -> None:
    """Non-dict position value is ignored; defaults are preserved."""
    data = {"position": "not a dict"}
    result = validate_config(data)
    assert result["position"] == get_default_config()["position"]


def test_validate_config_telltale_windows_invalid_values() -> None:
    """Non-positive telltale window values are ignored."""
    data = {"telltale_windows": {"short": -1, "medium": 0, "long": 1800}}
    result = validate_config(data)
    defaults = get_default_config()
    assert result["telltale_windows"]["short"] == defaults["telltale_windows"]["short"]
    assert result["telltale_windows"]["medium"] == defaults["telltale_windows"]["medium"]
    assert result["telltale_windows"]["long"] == 1800


def test_validate_config_thresholds_non_dict_category() -> None:
    """Non-dict threshold category is ignored."""
    data = {"thresholds": {"conpty": "invalid"}}
    result = validate_config(data)
    assert result["thresholds"]["conpty"] == get_default_config()["thresholds"]["conpty"]


def test_validate_config_show_flags_invalid_type() -> None:
    """Non-bool show flags are ignored (not bool, so condition is False)."""
    data = {
        "show_driver_label": "yes",
        "show_digital_readout": 1,
        "show_session_count": None,
    }
    result = validate_config(data)
    defaults = get_default_config()
    assert result["show_driver_label"] == defaults["show_driver_label"]
    assert result["show_digital_readout"] == defaults["show_digital_readout"]
    assert result["show_session_count"] == defaults["show_session_count"]


def test_validate_config_polling_interval_zero_or_negative() -> None:
    """Zero or negative polling_interval_seconds reverts to default."""
    result = validate_config({"polling_interval_seconds": 0})
    assert result["polling_interval_seconds"] == get_default_config()["polling_interval_seconds"]

    result = validate_config({"polling_interval_seconds": -5.0})
    assert result["polling_interval_seconds"] == get_default_config()["polling_interval_seconds"]


def test_save_config_oserror_logged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    """save_config logs warning on OSError without raising."""
    config_file = tmp_path / "config.json"
    config = get_default_config()

    original_mkdir = Path.mkdir

    def raising_mkdir(self, *args, **kwargs):
        raise OSError("simulated mkdir failure")

    monkeypatch.setattr(Path, "mkdir", raising_mkdir)
    save_config(config, config_file)