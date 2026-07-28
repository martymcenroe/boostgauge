"""Unit test suite for configuration management module.

Issue #7: Configuration File and CLI Arguments
Ref: docs/design/0001-test-strategy.md (Option C compliance)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from boostgauge.config import (
    ConfigError,
    GaugeConfigDict,
    apply_cli_overrides,
    get_default_config,
    get_default_config_path,
    load_config,
    parse_cli_args,
    save_config,
    update_window_geometry,
    validate_config,
)


def test_get_default_config_path_posix(monkeypatch: pytest.MonkeyPatch) -> None:
    """T020: Test path resolution on POSIX systems."""
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: Path("/home/testuser")))
    path = get_default_config_path()
    assert path == Path("/home/testuser") / ".boostgauge" / "config.json"


def test_get_default_config_path_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    """T020: Test path resolution on Windows systems with APPDATA environment variable."""
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", r"C:\Users\testuser\AppData\Roaming")
    path = get_default_config_path()
    assert path == Path(r"C:\Users\testuser\AppData\Roaming") / "boostgauge" / "config.json"


def test_get_default_config_path_windows_no_appdata(monkeypatch: pytest.MonkeyPatch) -> None:
    """T020: Test path resolution on Windows when APPDATA is missing."""
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: Path("/home/testuser")))
    path = get_default_config_path()
    assert path == Path("/home/testuser") / "AppData" / "Roaming" / "boostgauge" / "config.json"


def test_get_default_config_returns_deep_copy() -> None:
    """Mutations to returned dict must not affect subsequent calls."""
    cfg1 = get_default_config()
    cfg1["theme"] = "carbon"
    cfg1["position"]["x"] = 999

    cfg2 = get_default_config()
    assert cfg2["theme"] == "dark"
    assert cfg2["position"]["x"] == 100


def test_config_auto_creation_on_first_run(tmp_path: Path) -> None:
    """T010: Test config file auto-creation when file is missing."""
    cfg_file = tmp_path / "boostgauge" / "config.json"
    assert not cfg_file.exists()

    loaded = load_config(cfg_file)

    assert cfg_file.exists()
    assert loaded == get_default_config()


def test_config_auto_creation_writes_valid_json(tmp_path: Path) -> None:
    """Auto-created config file contains parseable JSON matching defaults."""
    cfg_file = tmp_path / "config.json"
    load_config(cfg_file)

    with open(cfg_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data == get_default_config()


def test_load_config_existing_file(tmp_path: Path) -> None:
    """Load returns correct values from an existing config file."""
    cfg_file = tmp_path / "config.json"
    cfg = get_default_config()
    cfg["theme"] = "amber"
    save_config(cfg, cfg_file)

    loaded = load_config(cfg_file)
    assert loaded["theme"] == "amber"


def test_cli_options_override_config_file(tmp_path: Path) -> None:
    """T030: Test CLI options overriding loaded configuration values."""
    cfg_file = tmp_path / "config.json"
    cfg = get_default_config()
    cfg["theme"] = "dark"
    cfg["size"] = 300
    save_config(cfg, cfg_file)

    parsed = parse_cli_args(["--theme", "light", "--size", "400", "--poll", "5.0"])
    overridden = apply_cli_overrides(cfg, parsed)

    assert overridden["theme"] == "light"
    assert overridden["size"] == 400
    assert overridden["polling_interval_seconds"] == 5.0


def test_cli_no_topmost_override() -> None:
    """T040: Test --no-topmost CLI flag overriding always_on_top setting."""
    cfg = get_default_config()
    assert cfg["always_on_top"] is True

    parsed = parse_cli_args(["--no-topmost"])
    overridden = apply_cli_overrides(cfg, parsed)

    assert overridden["always_on_top"] is False


def test_cli_none_args_preserve_defaults() -> None:
    """CLI args with None values leave config unchanged."""
    cfg = get_default_config()
    parsed = parse_cli_args([])
    overridden = apply_cli_overrides(cfg, parsed)

    assert overridden["theme"] == cfg["theme"]
    assert overridden["size"] == cfg["size"]
    assert overridden["opacity"] == cfg["opacity"]
    assert overridden["always_on_top"] == cfg["always_on_top"]


def test_cli_opacity_override() -> None:
    """T030: Test --opacity CLI override."""
    cfg = get_default_config()
    parsed = parse_cli_args(["--opacity", "0.7"])
    overridden = apply_cli_overrides(cfg, parsed)
    assert overridden["opacity"] == pytest.approx(0.7)


def test_cli_poll_and_size_override() -> None:
    """T030: Test --poll and --size CLI overrides."""
    cfg = get_default_config()
    parsed = parse_cli_args(["--poll", "2.5", "--size", "400"])
    overridden = apply_cli_overrides(cfg, parsed)
    assert overridden["polling_interval_seconds"] == pytest.approx(2.5)
    assert overridden["size"] == 400


def test_custom_config_path_argument(tmp_path: Path) -> None:
    """T050: Test custom --config PATH CLI argument."""
    custom_dir = tmp_path / "custom_dir"
    custom_dir.mkdir()
    custom_file = custom_dir / "my_config.json"

    custom_cfg = get_default_config()
    custom_cfg["theme"] = "amber"
    save_config(custom_cfg, custom_file)

    parsed = parse_cli_args(["--config", str(custom_file)])
    assert parsed.config == custom_file

    loaded = load_config(parsed.config)
    assert loaded["theme"] == "amber"


def test_reset_config_option(tmp_path: Path) -> None:
    """T060: Test --reset-config CLI option overwriting disk file with defaults."""
    cfg_file = tmp_path / "config.json"
    modified_cfg = get_default_config()
    modified_cfg["theme"] = "carbon"
    modified_cfg["size"] = 500
    save_config(modified_cfg, cfg_file)

    parsed = parse_cli_args(["--reset-config"])
    assert parsed.reset_config is True

    if parsed.reset_config:
        default_cfg = get_default_config()
        save_config(default_cfg, cfg_file)

    reloaded = load_config(cfg_file)
    assert reloaded["theme"] == "dark"
    assert reloaded["size"] == 300


def test_window_position_and_size_update_and_save(tmp_path: Path) -> None:
    """T070: Test geometry update and atomic persistence on exit."""
    cfg_file = tmp_path / "config.json"
    cfg = get_default_config()
    save_config(cfg, cfg_file)

    updated_geometry = update_window_geometry(cfg, x=250, y=300, size=350)
    save_config(updated_geometry, cfg_file)

    reloaded = load_config(cfg_file)
    assert reloaded["position"] == {"x": 250, "y": 300}
    assert reloaded["size"] == 350


def test_update_window_geometry_returns_copy() -> None:
    """update_window_geometry must not mutate the original config."""
    cfg = get_default_config()
    original_x = cfg["position"]["x"]
    original_size = cfg["size"]

    updated = update_window_geometry(cfg, x=999, y=888, size=777)

    assert cfg["position"]["x"] == original_x
    assert cfg["size"] == original_size
    assert updated["position"]["x"] == 999
    assert updated["position"]["y"] == 888
    assert updated["size"] == 777


def test_dynamic_in_memory_threshold_update() -> None:
    """T080: Test in-memory threshold update and re-validation."""
    cfg = get_default_config()
    cfg["thresholds"]["conpty"]["yellow"] = 40.0
    cfg["thresholds"]["conpty"]["red"] = 50.0

    validated = validate_config(cfg)
    assert validated["thresholds"]["conpty"]["yellow"] == 40.0
    assert validated["thresholds"]["conpty"]["red"] == 50.0


def test_invalid_json_config_file_error(tmp_path: Path) -> None:
    """T090: Test malformed JSON file raising ConfigError."""
    cfg_file = tmp_path / "corrupt.json"
    cfg_file.write_text("{ invalid json: ", encoding="utf-8")

    with pytest.raises(ConfigError, match="Failed to parse config JSON"):
        load_config(cfg_file)


def test_out_of_bounds_opacity_high() -> None:
    """T100: Test opacity > 1.0 raises ConfigError."""
    cfg = get_default_config()
    cfg["opacity"] = 1.5
    with pytest.raises(ConfigError, match="opacity must be between 0.0 and 1.0"):
        validate_config(cfg)


def test_out_of_bounds_opacity_low() -> None:
    """T100: Test opacity < 0.0 raises ConfigError."""
    cfg = get_default_config()
    cfg["opacity"] = -0.1
    with pytest.raises(ConfigError, match="opacity must be between 0.0 and 1.0"):
        validate_config(cfg)


def test_out_of_bounds_polling_interval() -> None:
    """T100: Test non-positive polling_interval_seconds raises ConfigError."""
    cfg = get_default_config()
    cfg["polling_interval_seconds"] = -1.0
    with pytest.raises(ConfigError, match="polling_interval_seconds must be a positive number"):
        validate_config(cfg)


def test_polling_interval_zero_raises() -> None:
    """T100: Test zero polling_interval_seconds raises ConfigError."""
    cfg = get_default_config()
    cfg["polling_interval_seconds"] = 0.0
    with pytest.raises(ConfigError, match="polling_interval_seconds must be a positive number"):
        validate_config(cfg)


def test_invalid_theme_validation_error() -> None:
    """T110: Test invalid theme name raising ConfigError."""
    cfg = get_default_config()
    cfg["theme"] = "invalid_theme"
    with pytest.raises(ConfigError, match="Invalid theme 'invalid_theme'"):
        validate_config(cfg)


def test_invalid_theme_lists_supported_themes() -> None:
    """ConfigError for bad theme must list all supported themes."""
    cfg = get_default_config()
    cfg["theme"] = "neon"
    with pytest.raises(ConfigError, match="Supported themes:"):
        validate_config(cfg)


def test_threshold_yellow_greater_than_red_error() -> None:
    """Test threshold yellow >= red raising ConfigError."""
    cfg = get_default_config()
    cfg["thresholds"]["conpty"]["yellow"] = 50.0
    cfg["thresholds"]["conpty"]["red"] = 40.0
    with pytest.raises(ConfigError, match="Threshold yellow must be strictly less than red"):
        validate_config(cfg)


def test_threshold_yellow_equal_to_red_error() -> None:
    """Test threshold yellow == red raising ConfigError."""
    cfg = get_default_config()
    cfg["thresholds"]["memory_percent"]["yellow"] = 70.0
    cfg["thresholds"]["memory_percent"]["red"] = 70.0
    with pytest.raises(ConfigError, match="Threshold yellow must be strictly less than red"):
        validate_config(cfg)


def test_validate_config_invalid_size_too_small() -> None:
    """size below minimum raises ConfigError."""
    cfg = get_default_config()
    cfg["size"] = 10
    with pytest.raises(ConfigError, match="size must be an integer"):
        validate_config(cfg)


def test_validate_config_invalid_size_too_large() -> None:
    """size above maximum raises ConfigError."""
    cfg = get_default_config()
    cfg["size"] = 9999
    with pytest.raises(ConfigError, match="size must be an integer"):
        validate_config(cfg)


def test_validate_config_invalid_always_on_top() -> None:
    """Non-boolean always_on_top raises ConfigError."""
    cfg: dict = get_default_config()  # type: ignore[assignment]
    cfg["always_on_top"] = "yes"
    with pytest.raises(ConfigError, match="always_on_top must be a boolean"):
        validate_config(cfg)


def test_validate_config_missing_position_key() -> None:
    """Position missing 'x' key raises ConfigError."""
    cfg: dict = get_default_config()  # type: ignore[assignment]
    cfg["position"] = {"y": 100}
    with pytest.raises(ConfigError, match="position must be an object"):
        validate_config(cfg)


def test_validate_config_non_integer_position() -> None:
    """Float position coordinates raise ConfigError."""
    cfg: dict = get_default_config()  # type: ignore[assignment]
    cfg["position"] = {"x": 1.5, "y": 100}
    with pytest.raises(ConfigError, match="position 'x' and 'y' must be integers"):
        validate_config(cfg)


def test_validate_config_telltale_windows_ordering() -> None:
    """telltale_windows short >= medium raises ConfigError."""
    cfg = get_default_config()
    cfg["telltale_windows"]["short"] = 600
    cfg["telltale_windows"]["medium"] = 60
    with pytest.raises(ConfigError, match="telltale_windows values must satisfy"):
        validate_config(cfg)


def test_validate_config_boolean_display_flags() -> None:
    """Non-boolean display flag raises ConfigError."""
    cfg: dict = get_default_config()  # type: ignore[assignment]
    cfg["show_driver_label"] = 1
    with pytest.raises(ConfigError, match="show_driver_label must be a boolean"):
        validate_config(cfg)


def test_save_config_creates_parent_directories(tmp_path: Path) -> None:
    """save_config creates missing parent directories automatically."""
    cfg_file = tmp_path / "nested" / "dirs" / "config.json"
    assert not cfg_file.parent.exists()

    save_config(get_default_config(), cfg_file)

    assert cfg_file.exists()


def test_save_config_atomic_write(tmp_path: Path) -> None:
    """No .tmp file left behind after successful save."""
    cfg_file = tmp_path / "config.json"
    save_config(get_default_config(), cfg_file)

    tmp_files = list(tmp_path.glob("*.tmp*"))
    assert tmp_files == []


def test_parse_cli_args_defaults() -> None:
    """parse_cli_args with no args produces None/False defaults."""
    parsed = parse_cli_args([])
    assert parsed.theme is None
    assert parsed.size is None
    assert parsed.poll is None
    assert parsed.opacity is None
    assert parsed.no_topmost is False
    assert parsed.config is None
    assert parsed.reset_config is False


def test_parse_cli_args_all_flags() -> None:
    """parse_cli_args correctly parses all supported flags."""
    parsed = parse_cli_args(
        ["--theme", "amber", "--size", "400", "--poll", "2.0", "--opacity", "0.8", "--no-topmost"]
    )
    assert parsed.theme == "amber"
    assert parsed.size == 400
    assert parsed.poll == pytest.approx(2.0)
    assert parsed.opacity == pytest.approx(0.8)
    assert parsed.no_topmost is True


def test_parse_cli_args_reset_config_flag() -> None:
    """--reset-config sets reset_config to True."""
    parsed = parse_cli_args(["--reset-config"])
    assert parsed.reset_config is True


def test_validate_config_returns_deep_copy() -> None:
    """validate_config must return a copy, not the original dict."""
    cfg = get_default_config()
    validated = validate_config(cfg)
    validated["theme"] = "carbon"
    assert cfg["theme"] == "dark"


def test_load_config_validates_on_load(tmp_path: Path) -> None:
    """load_config raises ConfigError when saved file has invalid values."""
    cfg_file = tmp_path / "config.json"
    bad = get_default_config()
    with open(cfg_file, "w", encoding="utf-8") as f:
        bad_dict = dict(bad)
        bad_dict["opacity"] = 99.0
        json.dump(bad_dict, f)

    with pytest.raises(ConfigError):
        load_config(cfg_file)


def test_all_valid_themes_accepted() -> None:
    """All themes in VALID_THEMES pass validation."""
    from boostgauge.config import VALID_THEMES

    for theme in VALID_THEMES:
        cfg = get_default_config()
        cfg["theme"] = theme
        result = validate_config(cfg)
        assert result["theme"] == theme


def test_threshold_all_metrics_validated() -> None:
    """ConfigError names the offending metric when threshold is invalid."""
    for metric in ("conpty", "memory_percent", "process_count", "handle_count"):
        cfg = get_default_config()
        cfg["thresholds"][metric]["yellow"] = cfg["thresholds"][metric]["red"] + 1.0
        with pytest.raises(ConfigError, match=metric):
            validate_config(cfg)