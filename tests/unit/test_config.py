"""Unit tests for BoostGauge configuration and CLI argument management.

Issue #7: Configuration file and CLI arguments
"""

import json
from pathlib import Path
import pytest

from boostgauge.config import (
    get_default_config,
    get_default_config_path,
    load_config,
    merge_config_and_cli,
    parse_cli_args,
    reset_config,
    save_config,
    update_window_state,
    validate_config,
)


def test_t010_auto_create_default_config_on_first_run(tmp_path: Path) -> None:
    """T010: Ensure load_config creates default config file if missing."""
    config_file = tmp_path / "boostgauge" / "config.json"
    assert not config_file.exists()

    config = load_config(config_file)

    assert config_file.exists()
    assert config == get_default_config()

    with open(config_file, "r", encoding="utf-8") as f:
        saved_data = json.load(f)
    assert saved_data["theme"] == "dark"
    assert saved_data["size"] == 300


def test_t020_cli_arguments_override_config_file_values() -> None:
    """T020: Merged config prioritizes non-None CLI options over config values."""
    base_config = get_default_config()
    base_config["theme"] = "dark"
    base_config["size"] = 300
    base_config["polling_interval_seconds"] = 1.0

    cli_args = parse_cli_args(["--theme", "neon", "--size", "450", "--no-topmost"])
    merged = merge_config_and_cli(base_config, cli_args)

    assert merged["theme"] == "neon"
    assert merged["size"] == 450
    assert merged["always_on_top"] is False
    assert merged["polling_interval_seconds"] == 1.0
    assert base_config["theme"] == "dark"


def test_t030_all_supported_cli_flags_parsed_correctly() -> None:
    """T030: Parser extracts theme, size, poll, opacity, topmost, config, reset."""
    args = [
        "--theme", "cyberpunk",
        "--size", "500",
        "--poll", "0.5",
        "--opacity", "0.85",
        "--no-topmost",
        "--config", "/custom/path.json",
        "--reset-config",
    ]
    parsed = parse_cli_args(args)

    assert parsed.theme == "cyberpunk"
    assert parsed.size == 500
    assert parsed.poll == 0.5
    assert parsed.opacity == 0.85
    assert parsed.no_topmost is True
    assert parsed.config == "/custom/path.json"
    assert parsed.reset_config is True


def test_t040_reset_config_flag_overwrites_file_with_defaults(tmp_path: Path) -> None:
    """T040: Reset config overwrites an existing file with defaults."""
    config_file = tmp_path / "config.json"
    custom_data = get_default_config()
    custom_data["theme"] = "custom_theme"
    custom_data["size"] = 800
    save_config(custom_data, config_file)

    reset_result = reset_config(config_file)

    assert reset_result == get_default_config()
    with open(config_file, "r", encoding="utf-8") as f:
        reloaded = json.load(f)
    assert reloaded["theme"] == "dark"
    assert reloaded["size"] == 300


def test_t050_save_and_restore_window_position_and_size(tmp_path: Path) -> None:
    """T050: Update window state updates memory dict and persists to JSON file."""
    config_file = tmp_path / "config.json"
    initial_config = get_default_config()

    updated = update_window_state(initial_config, x=250, y=175, size=400, config_path=config_file)

    assert updated["position"]["x"] == 250
    assert updated["position"]["y"] == 175
    assert updated["size"] == 400

    reloaded = load_config(config_file)
    assert reloaded["position"]["x"] == 250
    assert reloaded["position"]["y"] == 175
    assert reloaded["size"] == 400


def test_t060_in_memory_threshold_update_without_restart() -> None:
    """T060: Modifying threshold dict updates memory state dynamically."""
    config = get_default_config()
    assert config["thresholds"]["memory_percent"]["yellow"] == 70.0

    config["thresholds"]["memory_percent"]["yellow"] = 80.0
    config["thresholds"]["memory_percent"]["red"] = 92.0

    assert config["thresholds"]["memory_percent"]["yellow"] == 80.0
    assert config["thresholds"]["memory_percent"]["red"] == 92.0


def test_t070_graceful_handling_of_corrupt_config_json(tmp_path: Path) -> None:
    """T070: Corrupt JSON syntax falls back to default values without raising crash."""
    config_file = tmp_path / "corrupt_config.json"
    config_file.write_text("{ corrupt json syntax ...", encoding="utf-8")

    config = load_config(config_file)

    assert config == get_default_config()


def test_t080_validation_of_out_of_range_cli_values() -> None:
    """T080: Out-of-bounds CLI opacity or size raises SystemExit from argparse."""
    with pytest.raises(SystemExit):
        parse_cli_args(["--opacity", "2.5"])

    with pytest.raises(SystemExit):
        parse_cli_args(["--size", "30"])


def test_get_default_config_path_platform_handling(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify platform detection for default config path uses pathlib.Path comparison."""
    monkeypatch.setattr("platform.system", lambda: "Windows")
    monkeypatch.setenv("APPDATA", "C:/Users/MockUser/AppData/Roaming")
    win_path = get_default_config_path()
    expected_win = Path("C:/Users/MockUser/AppData/Roaming") / "boostgauge" / "config.json"
    assert win_path == expected_win

    monkeypatch.setattr("platform.system", lambda: "Linux")
    posix_path = get_default_config_path()
    expected_posix = Path.home() / ".boostgauge" / "config.json"
    assert posix_path == expected_posix


def test_validate_config_partial_and_corrupt_keys() -> None:
    """Verify partial validation retains valid fields and replaces invalid ones with defaults."""
    raw_data = {
        "polling_interval_seconds": -1.0,
        "theme": "vibrant",
        "opacity": 0.5,
        "thresholds": {
            "conpty": {"yellow": 8.0},
        },
    }
    validated = validate_config(raw_data)

    assert validated["polling_interval_seconds"] == 1.0
    assert validated["theme"] == "vibrant"
    assert validated["opacity"] == 0.5
    assert validated["thresholds"]["conpty"]["yellow"] == 8.0
    assert validated["thresholds"]["conpty"]["red"] == 10.0


def test_get_default_config_returns_deep_copy() -> None:
    """get_default_config must return independent copies to prevent global state mutation."""
    config_a = get_default_config()
    config_b = get_default_config()

    config_a["theme"] = "mutated"
    config_a["thresholds"]["conpty"]["yellow"] = 99.0

    assert config_b["theme"] == "dark"
    assert config_b["thresholds"]["conpty"]["yellow"] == 5.0


def test_validate_config_non_dict_input() -> None:
    """Non-dict input to validate_config returns full defaults."""
    result = validate_config("not a dict")  # type: ignore[arg-type]
    assert result == get_default_config()

    result = validate_config(None)  # type: ignore[arg-type]
    assert result == get_default_config()


def test_validate_config_invalid_size_type() -> None:
    """validate_config rejects non-int size and falls back to default."""
    validated = validate_config({"size": "invalid_type"})
    assert validated["size"] == 300


def test_validate_config_size_below_minimum() -> None:
    """validate_config rejects size < 50 and falls back to default."""
    validated = validate_config({"size": 40})
    assert validated["size"] == 300


def test_validate_config_opacity_out_of_range() -> None:
    """validate_config rejects opacity outside [0.1, 1.0] and falls back to default."""
    result_high = validate_config({"opacity": 1.5})
    assert result_high["opacity"] == 1.0

    result_low = validate_config({"opacity": 0.05})
    assert result_low["opacity"] == 1.0


def test_validate_config_all_thresholds() -> None:
    """validate_config handles all threshold keys correctly."""
    raw = {
        "thresholds": {
            "conpty": {"yellow": 3.0, "red": 7.0},
            "memory_percent": {"yellow": 60.0, "red": 80.0},
            "process_count": {"yellow": 40.0, "red": 90.0},
            "handle_count": {"yellow": 800.0, "red": 1500.0},
        }
    }
    validated = validate_config(raw)
    assert validated["thresholds"]["conpty"]["yellow"] == 3.0
    assert validated["thresholds"]["conpty"]["red"] == 7.0
    assert validated["thresholds"]["memory_percent"]["yellow"] == 60.0
    assert validated["thresholds"]["process_count"]["red"] == 90.0
    assert validated["thresholds"]["handle_count"]["yellow"] == 800.0


def test_validate_config_telltale_windows() -> None:
    """validate_config applies valid telltale_windows values."""
    raw = {"telltale_windows": {"short": 30, "medium": 300, "long": 1800}}
    validated = validate_config(raw)
    assert validated["telltale_windows"]["short"] == 30
    assert validated["telltale_windows"]["medium"] == 300
    assert validated["telltale_windows"]["long"] == 1800


def test_validate_config_telltale_windows_invalid_ignored() -> None:
    """validate_config ignores non-positive or non-int telltale_windows values."""
    raw = {"telltale_windows": {"short": 0, "medium": -10, "long": 3600}}
    validated = validate_config(raw)
    assert validated["telltale_windows"]["short"] == 60
    assert validated["telltale_windows"]["medium"] == 600
    assert validated["telltale_windows"]["long"] == 3600


def test_validate_config_boolean_fields() -> None:
    """validate_config applies valid boolean values and ignores non-boolean ones."""
    raw = {
        "always_on_top": False,
        "show_driver_label": False,
        "show_digital_readout": False,
        "show_session_count": False,
    }
    validated = validate_config(raw)
    assert validated["always_on_top"] is False
    assert validated["show_driver_label"] is False
    assert validated["show_digital_readout"] is False
    assert validated["show_session_count"] is False

    raw_invalid = {"always_on_top": "yes"}
    validated_invalid = validate_config(raw_invalid)
    assert validated_invalid["always_on_top"] is True


def test_validate_config_position() -> None:
    """validate_config applies valid position x/y coordinates."""
    raw = {"position": {"x": 500, "y": 300}}
    validated = validate_config(raw)
    assert validated["position"]["x"] == 500
    assert validated["position"]["y"] == 300


def test_validate_config_position_invalid_type_ignored() -> None:
    """validate_config ignores non-int position values and retains defaults."""
    raw = {"position": {"x": "left", "y": 200}}
    validated = validate_config(raw)
    assert validated["position"]["x"] == 100
    assert validated["position"]["y"] == 200


def test_save_config_creates_parent_directories(tmp_path: Path) -> None:
    """save_config creates missing parent directories recursively."""
    config_file = tmp_path / "a" / "b" / "c" / "config.json"
    assert not config_file.parent.exists()

    save_config(get_default_config(), config_file)

    assert config_file.exists()
    with open(config_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["theme"] == "dark"


def test_save_config_atomic_write(tmp_path: Path) -> None:
    """save_config does not leave behind a .tmp file after successful write."""
    config_file = tmp_path / "config.json"
    save_config(get_default_config(), config_file)

    tmp_file = config_file.with_suffix(".tmp")
    assert not tmp_file.exists()
    assert config_file.exists()


def test_merge_config_and_cli_none_values_not_overwritten() -> None:
    """merge_config_and_cli skips CLI options that are None."""
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


def test_merge_config_and_cli_does_not_mutate_input() -> None:
    """merge_config_and_cli returns a new copy without mutating the input config."""
    import argparse

    config = get_default_config()
    cli_args = argparse.Namespace(
        theme="electric",
        size=600,
        poll=0.5,
        opacity=0.7,
        no_topmost=True,
        config=None,
        reset_config=False,
    )
    merged = merge_config_and_cli(config, cli_args)

    assert config["theme"] == "dark"
    assert config["size"] == 300
    assert config["always_on_top"] is True
    assert merged["theme"] == "electric"
    assert merged["size"] == 600
    assert merged["always_on_top"] is False


def test_merge_config_and_cli_poll_override() -> None:
    """merge_config_and_cli applies --poll to polling_interval_seconds."""
    import argparse

    config = get_default_config()
    cli_args = argparse.Namespace(
        theme=None,
        size=None,
        poll=2.5,
        opacity=None,
        no_topmost=False,
        config=None,
        reset_config=False,
    )
    merged = merge_config_and_cli(config, cli_args)
    assert merged["polling_interval_seconds"] == 2.5


def test_parse_cli_args_defaults_when_no_args() -> None:
    """parse_cli_args with empty list returns all-None/False defaults."""
    parsed = parse_cli_args([])

    assert parsed.theme is None
    assert parsed.size is None
    assert parsed.poll is None
    assert parsed.opacity is None
    assert parsed.no_topmost is False
    assert parsed.config is None
    assert parsed.reset_config is False


def test_parse_cli_args_invalid_opacity_type_exits() -> None:
    """parse_cli_args raises SystemExit for non-numeric opacity."""
    with pytest.raises(SystemExit):
        parse_cli_args(["--opacity", "bright"])


def test_parse_cli_args_invalid_size_type_exits() -> None:
    """parse_cli_args raises SystemExit for non-integer size."""
    with pytest.raises(SystemExit):
        parse_cli_args(["--size", "large"])


def test_update_window_state_does_not_mutate_input(tmp_path: Path) -> None:
    """update_window_state returns new dict without mutating the input config."""
    config_file = tmp_path / "config.json"
    original = get_default_config()

    updated = update_window_state(original, x=999, y=888, size=700, config_path=config_file)

    assert original["position"]["x"] == 100
    assert original["position"]["y"] == 100
    assert original["size"] == 300
    assert updated["position"]["x"] == 999
    assert updated["position"]["y"] == 888
    assert updated["size"] == 700


def test_get_default_config_path_windows_no_appdata(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_default_config_path falls back to home/AppData/Roaming when APPDATA unset on Windows."""
    monkeypatch.setattr("platform.system", lambda: "Windows")
    monkeypatch.delenv("APPDATA", raising=False)

    path = get_default_config_path()
    expected = Path.home() / "AppData" / "Roaming" / "boostgauge" / "config.json"
    assert path == expected


def test_load_config_permission_error_falls_back_to_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """load_config returns defaults when file exists but cannot be opened."""
    config_file = tmp_path / "config.json"
    config_file.write_text("{}", encoding="utf-8")

    original_open = open

    def mock_open(path, *args, **kwargs):
        if Path(path) == config_file:
            raise PermissionError("Access denied")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", mock_open)

    config = load_config(config_file)
    assert config == get_default_config()


def test_validate_config_valid_polling_interval() -> None:
    """validate_config accepts valid positive polling interval."""
    validated = validate_config({"polling_interval_seconds": 0.5})
    assert validated["polling_interval_seconds"] == 0.5


def test_validate_config_zero_polling_interval_rejected() -> None:
    """validate_config rejects zero polling interval and falls back to default."""
    validated = validate_config({"polling_interval_seconds": 0})
    assert validated["polling_interval_seconds"] == 1.0


def test_validate_config_valid_theme_stripped() -> None:
    """validate_config strips whitespace from valid theme strings."""
    validated = validate_config({"theme": "  light  "})
    assert validated["theme"] == "light"


def test_validate_config_empty_theme_rejected() -> None:
    """validate_config rejects empty/whitespace-only theme and falls back to default."""
    validated = validate_config({"theme": "   "})
    assert validated["theme"] == "dark"