"""Unit test suite for configuration file loading, saving, CLI parsing, validation, and geometry updates.

Issue #7: Feature: Configuration File and CLI Arguments
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import pytest

from boostgauge.app import main
from boostgauge.config import (
    CLIArgs,
    GaugeConfig,
    PositionConfig,
    ThresholdsConfig,
    get_default_config,
    get_default_config_path,
    load_config,
    merge_config_and_args,
    parse_cli_args,
    reset_config_to_defaults,
    save_config,
    update_window_geometry,
    validate_config,
)


def test_t010_auto_create_default_config_on_first_launch(tmp_path: Path) -> None:
    """T010: Auto-create default config on first launch if missing."""
    config_file = tmp_path / "boostgauge" / "config.json"
    assert not config_file.exists()

    config = load_config(config_file)
    assert config_file.exists()
    assert config == get_default_config()


def test_t020_load_config_from_custom_path(tmp_path: Path) -> None:
    """T020: Load config from custom file path via load_config."""
    config_file = tmp_path / "custom" / "my_config.json"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    custom_data = {
        "polling_interval_seconds": 3.5,
        "theme": "neon",
        "size": 450,
        "opacity": 0.85,
        "always_on_top": False,
    }
    config_file.write_text(json.dumps(custom_data), encoding="utf-8")

    config = load_config(config_file)
    assert config.theme == "neon"
    assert config.size == 450
    assert config.polling_interval_seconds == 3.5
    assert config.opacity == 0.85
    assert config.always_on_top is False


def test_t030_reset_config_using_reset_flag(tmp_path: Path) -> None:
    """T030: Reset existing config file to defaults via reset_config_to_defaults."""
    config_file = tmp_path / "config.json"
    modified_config = GaugeConfig(theme="neon", size=500)
    save_config(modified_config, config_file)

    loaded = load_config(config_file)
    assert loaded.theme == "neon"

    reset_cfg = reset_config_to_defaults(config_file)
    assert reset_cfg.theme == "dark"

    reloaded = load_config(config_file)
    assert reloaded.theme == "dark"
    assert reloaded.size == 300


def test_t040_override_config_via_cli_args() -> None:
    """T040: Override config settings using parse_cli_args and merge_config_and_args."""
    cli_args = parse_cli_args(
        ["--theme", "light", "--size", "400", "--poll", "5.0", "--opacity", "0.8", "--no-topmost"]
    )
    base_config = get_default_config()
    merged = merge_config_and_args(base_config, cli_args)

    assert merged.theme == "light"
    assert merged.size == 400
    assert merged.polling_interval_seconds == 5.0
    assert merged.opacity == 0.8
    assert merged.always_on_top is False


def test_t050_save_and_restore_window_geometry(tmp_path: Path) -> None:
    """T050: update_window_geometry updates DTO and writes updated values to disk."""
    config_file = tmp_path / "config.json"
    config = get_default_config()
    save_config(config, config_file)

    updated = update_window_geometry(config, (250, 350), 400, config_file)
    assert updated.position.x == 250
    assert updated.position.y == 350
    assert updated.size == 400

    reloaded = load_config(config_file)
    assert reloaded.position.x == 250
    assert reloaded.position.y == 350
    assert reloaded.size == 400


def test_t060_dynamic_threshold_update_in_memory() -> None:
    """T060: Modifying threshold dictionary updates active configuration immediately."""
    config = get_default_config()
    assert config.thresholds.conpty["yellow"] == 30.0

    config.thresholds.conpty["yellow"] = 45.0
    assert config.thresholds.conpty["yellow"] == 45.0


def test_t070_validation_failure_on_out_of_range_opacity() -> None:
    """T070: validate_config returns error string for opacity outside 0.0-1.0 range."""
    config = get_default_config()
    config.opacity = 1.5
    errors = validate_config(config)

    assert len(errors) > 0
    assert any("opacity" in err for err in errors)


def test_t080_validation_failure_on_invalid_theme_or_poll_interval() -> None:
    """T080: validate_config returns descriptive errors for invalid inputs."""
    config = get_default_config()
    config.theme = "invalid_theme"
    config.polling_interval_seconds = -1.0
    config.thresholds.conpty = {"yellow": 80.0, "red": 50.0}

    errors = validate_config(config)
    assert len(errors) == 3
    assert any("theme" in err for err in errors)
    assert any("polling_interval_seconds" in err for err in errors)
    assert any("threshold yellow value" in err for err in errors)


def test_default_config_path_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test platform-dependent default config path resolution comparing pathlib.Path objects."""
    monkeypatch.setattr(sys, "platform", "linux")
    posix_path = get_default_config_path()
    assert posix_path == Path.home() / ".boostgauge" / "config.json"

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(Path("C:/Users/TestUser/AppData/Roaming")))
    win_path = get_default_config_path()
    assert win_path == Path("C:/Users/TestUser/AppData/Roaming") / "boostgauge" / "config.json"


def test_app_main_success(tmp_path: Path) -> None:
    """Test main entry point executing successfully with CLI options."""
    config_file = tmp_path / "config.json"
    args = ["--config", str(config_file), "--theme", "neon"]
    exit_code = main(args)
    assert exit_code == 0
    loaded = load_config(config_file)
    assert loaded.theme == "neon"


def test_app_main_invalid_config(tmp_path: Path) -> None:
    """Test main entry point handling invalid configuration options."""
    config_file = tmp_path / "config.json"
    args = ["--config", str(config_file), "--size", "-50"]
    exit_code = main(args)
    assert exit_code == 1


def test_t001_verify_get_default_config_path_os_path_r(monkeypatch: pytest.MonkeyPatch) -> None:
    """T001: Verify get_default_config_path() OS path resolution."""
    monkeypatch.setattr(sys, "platform", "linux")
    posix_path = get_default_config_path()
    assert posix_path == Path.home() / ".boostgauge" / "config.json"

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(Path("C:/Users/mcwiz/AppData/Roaming")))
    win_path = get_default_config_path()
    assert win_path == Path("C:/Users/mcwiz/AppData/Roaming") / "boostgauge" / "config.json"


def test_t002_verify_automatic_creation_of_default_con(tmp_path: Path) -> None:
    """T002: Verify automatic creation of default configuration file when non-existent."""
    config_file = tmp_path / "boostgauge" / "config.json"
    assert not config_file.exists()

    config = load_config(config_file)
    assert config_file.exists()

    data = json.loads(config_file.read_text(encoding="utf-8"))
    assert data["theme"] == "dark"
    assert data["size"] == 300
    assert config == get_default_config()


def test_t003_verify_loading_custom_configuration_file(tmp_path: Path) -> None:
    """T003: Verify loading custom configuration file specified via --config PATH CLI argument."""
    config_file = tmp_path / "custom_config.json"
    custom_data = {"theme": "classic", "size": 200, "polling_interval_seconds": 1.0}
    config_file.write_text(json.dumps(custom_data), encoding="utf-8")

    cli_args = parse_cli_args(["--config", str(config_file)])
    config_path = Path(cli_args.config)
    config = load_config(config_path)

    assert config.theme == "classic"
    assert config.size == 200
    assert config.polling_interval_seconds == 1.0


def test_t004_verify_resetting_configuration_file_to_d(tmp_path: Path) -> None:
    """T004: Verify resetting configuration file to defaults using --reset-config CLI flag."""
    config_file = tmp_path / "config.json"
    modified = GaugeConfig(theme="neon", size=999, opacity=0.5)
    save_config(modified, config_file)

    reset_cfg = reset_config_to_defaults(config_file)
    assert reset_cfg == get_default_config()

    reloaded = load_config(config_file)
    assert reloaded.theme == "dark"
    assert reloaded.size == 300
    assert reloaded.opacity == 0.9


def test_t005_verify_cli_argument_parsing_for_theme_si() -> None:
    """T005: Verify CLI argument parsing for --theme, --size, --poll, --opacity, and --no-topmost."""
    cli_args = parse_cli_args([
        "--theme", "neon",
        "--size", "350",
        "--poll", "1.5",
        "--opacity", "0.75",
        "--no-topmost",
    ])
    base_config = get_default_config()
    config = merge_config_and_args(base_config, cli_args)

    assert config.theme == "neon"
    assert config.size == 350
    assert config.polling_interval_seconds == 1.5
    assert config.opacity == 0.75
    assert config.always_on_top is False


def test_t006_verify_persisting_window_position_x_y_an(tmp_path: Path) -> None:
    """T006: Verify persisting window position (x, y) and size to configuration file."""
    config_file = tmp_path / "config.json"
    config = get_default_config()
    save_config(config, config_file)

    updated = update_window_geometry(config, (120, 240), 450, config_file)
    assert updated.position.x == 120
    assert updated.position.y == 240
    assert updated.size == 450

    reloaded = load_config(config_file)
    assert reloaded.position.x == 120
    assert reloaded.position.y == 240
    assert reloaded.size == 450


def test_t007_verify_dynamic_runtime_updates_for_thres() -> None:
    """T007: Verify dynamic runtime updates for threshold configurations."""
    config = get_default_config()

    config.thresholds.conpty["yellow"] = 40.0
    config.thresholds.conpty["red"] = 70.0
    assert config.thresholds.conpty["yellow"] == 40.0
    assert config.thresholds.conpty["red"] == 70.0

    config.thresholds.memory_percent["yellow"] = 55.0
    assert config.thresholds.memory_percent["yellow"] == 55.0

    config.thresholds.process_count["red"] = 600.0
    assert config.thresholds.process_count["red"] == 600.0

    config.thresholds.handle_count["yellow"] = 25000.0
    assert config.thresholds.handle_count["yellow"] == 25000.0

    errors = validate_config(config)
    assert len(errors) == 0


def test_t008_verify_opacity_validation_logic_for_vali() -> None:
    """T008: Verify opacity validation logic for valid boundary values and out-of-range values."""
    config = get_default_config()

    config.opacity = 0.0
    assert validate_config(config) == []

    config.opacity = 1.0
    assert validate_config(config) == []

    config.opacity = -0.1
    errors = validate_config(config)
    assert len(errors) > 0
    assert any("opacity" in err for err in errors)

    config.opacity = 1.1
    errors = validate_config(config)
    assert len(errors) > 0
    assert any("opacity" in err for err in errors)


def test_t009_verify_size_validation_logic_for_invalid() -> None:
    """T009: Verify size validation logic for invalid edge cases size <= 0."""
    config = get_default_config()

    config.size = 0
    errors = validate_config(config)
    assert len(errors) > 0
    assert any("size" in err for err in errors)

    config.size = -10
    errors = validate_config(config)
    assert len(errors) > 0
    assert any("size" in err for err in errors)

    config.size = 1
    errors = validate_config(config)
    assert len(errors) == 0


def test_t010_verify_polling_interval_seconds_validati() -> None:
    """T010: Verify polling_interval_seconds validation logic for zero and negative values."""
    config = get_default_config()

    config.polling_interval_seconds = 0.0
    errors = validate_config(config)
    assert len(errors) > 0
    assert any("polling_interval_seconds" in err for err in errors)

    config.polling_interval_seconds = -1.0
    errors = validate_config(config)
    assert len(errors) > 0
    assert any("polling_interval_seconds" in err for err in errors)

    config.polling_interval_seconds = 0.1
    errors = validate_config(config)
    assert len(errors) == 0


def test_t011_verify_theme_validation_logic_when_an_in() -> None:
    """T011: Verify theme validation logic when an invalid theme name is provided."""
    config = get_default_config()
    config.theme = "unknown_theme"

    errors = validate_config(config)
    assert len(errors) > 0
    assert any("theme" in err for err in errors)
    assert any("unknown_theme" in err for err in errors)

    for valid_theme in ("dark", "light", "neon", "classic"):
        config.theme = valid_theme
        errors = validate_config(config)
        assert not any("theme" in err for err in errors)


def test_load_config_raises_on_malformed_json(tmp_path: Path) -> None:
    """load_config raises ValueError on malformed JSON."""
    config_file = tmp_path / "bad.json"
    config_file.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(ValueError, match="Failed to parse configuration JSON"):
        load_config(config_file)


def test_load_config_raises_on_non_object_json(tmp_path: Path) -> None:
    """load_config raises ValueError when top-level JSON is not an object."""
    config_file = tmp_path / "bad.json"
    config_file.write_text("[1, 2, 3]", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid configuration schema"):
        load_config(config_file)


def test_save_config_atomic_write(tmp_path: Path) -> None:
    """save_config writes atomically via temp file and no leftover .tmp file remains."""
    config_file = tmp_path / "config.json"
    config = get_default_config()
    save_config(config, config_file)

    assert config_file.exists()
    temp_file = config_file.with_name(f".{config_file.name}.tmp")
    assert not temp_file.exists()

    data = json.loads(config_file.read_text(encoding="utf-8"))
    assert data["theme"] == "dark"


def test_save_config_creates_parent_directories(tmp_path: Path) -> None:
    """save_config creates missing parent directories."""
    config_file = tmp_path / "a" / "b" / "c" / "config.json"
    assert not config_file.parent.exists()

    save_config(get_default_config(), config_file)
    assert config_file.exists()


def test_parse_cli_args_defaults() -> None:
    """parse_cli_args returns all-None/False CLIArgs when no args given."""
    cli_args = parse_cli_args([])
    assert cli_args.theme is None
    assert cli_args.size is None
    assert cli_args.poll is None
    assert cli_args.opacity is None
    assert cli_args.no_topmost is False
    assert cli_args.config is None
    assert cli_args.reset_config is False


def test_parse_cli_args_reset_config() -> None:
    """parse_cli_args correctly parses --reset-config flag."""
    cli_args = parse_cli_args(["--reset-config"])
    assert cli_args.reset_config is True


def test_merge_config_and_args_preserves_unset_fields() -> None:
    """merge_config_and_args preserves original values for None CLI args."""
    config = GaugeConfig(theme="classic", size=200, opacity=0.5)
    cli_args = CLIArgs(theme="neon")
    merged = merge_config_and_args(config, cli_args)

    assert merged.theme == "neon"
    assert merged.size == 200
    assert merged.opacity == 0.5
    assert merged.always_on_top is True


def test_validate_config_threshold_yellow_must_be_less_than_red() -> None:
    """validate_config returns error when threshold yellow >= red."""
    config = get_default_config()
    config.thresholds.memory_percent = {"yellow": 90.0, "red": 80.0}

    errors = validate_config(config)
    assert any("memory_percent" in err for err in errors)
    assert any("threshold yellow value" in err for err in errors)


def test_validate_config_equal_thresholds_invalid() -> None:
    """validate_config returns error when threshold yellow == red."""
    config = get_default_config()
    config.thresholds.process_count = {"yellow": 300.0, "red": 300.0}

    errors = validate_config(config)
    assert any("process_count" in err for err in errors)


def test_app_main_reset_config(tmp_path: Path) -> None:
    """main() with --reset-config resets file and returns 0."""
    config_file = tmp_path / "config.json"
    modified = GaugeConfig(theme="neon", size=999)
    save_config(modified, config_file)

    exit_code = main(["--config", str(config_file), "--reset-config"])
    assert exit_code == 0

    reloaded = load_config(config_file)
    assert reloaded.theme == "dark"
    assert reloaded.size == 300


def test_app_main_returns_1_on_validation_error(tmp_path: Path) -> None:
    """main() returns 1 when merged config fails validation."""
    config_file = tmp_path / "config.json"
    exit_code = main(["--config", str(config_file), "--opacity", "2.0"])
    assert exit_code == 1


def test_get_default_config_path_fallback_no_appdata(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_default_config_path falls back to Path.home()/AppData/Roaming when APPDATA unset on Windows."""
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delenv("APPDATA", raising=False)
    path = get_default_config_path()
    assert path == Path.home() / "AppData" / "Roaming" / "boostgauge" / "config.json"