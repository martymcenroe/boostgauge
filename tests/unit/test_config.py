"""Unit tests for boostgauge configuration management module.

Issue #7: Feature configuration file and CLI arguments
"""

import json
import os
from pathlib import Path
import pytest
from unittest.mock import patch

from boostgauge.config import (
    DEFAULT_CONFIG,
    get_default_config,
    get_default_config_path,
    load_config_file,
    load_effective_config,
    merge_config,
    parse_cli_args,
    reset_config_file,
    save_config_file,
    update_window_geometry,
    validate_config,
)


def test_t010_default_config_file_creation(tmp_path: Path):
    """T010: Auto-creates config.json with default keys on initial run."""
    config_file = tmp_path / "config.json"
    assert not config_file.exists()

    loaded = load_config_file(config_file)
    assert config_file.exists()
    assert loaded == DEFAULT_CONFIG

    with open(config_file, "r", encoding="utf-8") as f:
        file_data = json.load(f)
    assert file_data == DEFAULT_CONFIG


def test_t020_directory_creation_on_first_run(tmp_path: Path):
    """T020: Creates missing parent directories when writing default config."""
    config_file = tmp_path / "nested" / "subfolder" / "config.json"
    assert not config_file.parent.exists()

    loaded = load_config_file(config_file)
    assert config_file.exists()
    assert loaded == DEFAULT_CONFIG


def test_t030_cli_argument_parsing():
    """T030: Correctly parses all valid CLI flags."""
    args = parse_cli_args([
        "--theme", "cyberpunk",
        "--size", "500",
        "--poll", "0.5",
        "--opacity", "0.75",
        "--no-topmost",
        "--config", "custom/path.json",
        "--reset-config",
    ])
    assert args.theme == "cyberpunk"
    assert args.size == 500
    assert args.poll == 0.5
    assert args.opacity == 0.75
    assert args.no_topmost is True
    assert args.config == "custom/path.json"
    assert args.reset_config is True


def test_t040_cli_overrides_config_values():
    """T040: CLI values take precedence over values loaded from config.json."""
    file_config = get_default_config()
    file_config["theme"] = "dark"
    file_config["size"] = 300
    file_config["opacity"] = 1.0

    cli_args = parse_cli_args(["--theme", "light", "--size", "400", "--opacity", "0.8"])
    merged = merge_config(file_config, cli_args)

    assert merged["theme"] == "light"
    assert merged["size"] == 400
    assert merged["opacity"] == 0.8
    assert merged["always_on_top"] is True


def test_t050_custom_config_file_path(tmp_path: Path):
    """T050: Loads configuration from custom path passed via --config."""
    custom_path = tmp_path / "custom_config.json"
    custom_data = get_default_config()
    custom_data["theme"] = "stealth"
    save_config_file(custom_data, custom_path)

    effective = load_effective_config(["--config", str(custom_path)])
    assert effective["theme"] == "stealth"


def test_t060_invalid_theme_validation():
    """T060: Raises ValueError for unsupported theme string."""
    invalid_config = get_default_config()
    invalid_config["theme"] = "invalid_theme_name"

    with pytest.raises(ValueError, match="Invalid theme 'invalid_theme_name'"):
        validate_config(invalid_config)


def test_t070_invalid_opacity_validation():
    """T070: Raises ValueError for opacity out of 0.0-1.0 bounds."""
    invalid_config_high = get_default_config()
    invalid_config_high["opacity"] = 1.5
    with pytest.raises(ValueError, match="opacity must be between 0.0 and 1.0"):
        validate_config(invalid_config_high)

    invalid_config_low = get_default_config()
    invalid_config_low["opacity"] = -0.1
    with pytest.raises(ValueError, match="opacity must be between 0.0 and 1.0"):
        validate_config(invalid_config_low)


def test_t080_malformed_json_file_handling(tmp_path: Path):
    """T080: Raises ValueError with clear message on invalid JSON."""
    corrupt_file = tmp_path / "corrupt.json"
    corrupt_file.write_text("{ invalid json syntax ...", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid JSON in configuration file"):
        load_config_file(corrupt_file)


def test_t090_reset_config_flag(tmp_path: Path):
    """T090: Overwrites config file with default settings when --reset-config passed."""
    config_file = tmp_path / "config.json"
    modified_data = get_default_config()
    modified_data["theme"] = "cyberpunk"
    modified_data["size"] = 600
    save_config_file(modified_data, config_file)

    effective = load_effective_config(["--config", str(config_file), "--reset-config"])
    assert effective["theme"] == "dark"
    assert effective["size"] == 300

    on_disk = load_config_file(config_file)
    assert on_disk["theme"] == "dark"


def test_t100_geometry_update_persistence(tmp_path: Path):
    """T100: Saves window position and size updates to config.json."""
    config_file = tmp_path / "config.json"
    save_config_file(get_default_config(), config_file)

    update_window_geometry(config_file, position=(250, 350), size=400)

    updated = load_config_file(config_file)
    assert updated["position"] == {"x": 250, "y": 350}
    assert updated["size"] == 400


def test_t110_geometry_restoration(tmp_path: Path):
    """T110: Restores saved position and size on configuration load."""
    config_file = tmp_path / "config.json"
    custom_data = get_default_config()
    custom_data["position"] = {"x": 180, "y": 220}
    custom_data["size"] = 380
    save_config_file(custom_data, config_file)

    effective = load_effective_config(["--config", str(config_file)])
    assert effective["position"] == {"x": 180, "y": 220}
    assert effective["size"] == 380


def test_t120_dynamic_threshold_update():
    """T120: Applies threshold modifications immediately in-memory."""
    config = get_default_config()
    config["thresholds"]["conpty"]["yellow"] = 15.0
    config["thresholds"]["conpty"]["red"] = 25.0

    validated = validate_config(config)
    assert validated["thresholds"]["conpty"]["yellow"] == 15.0
    assert validated["thresholds"]["conpty"]["red"] == 25.0


def test_t130_unified_effective_config_load(tmp_path: Path):
    """T130: Combines defaults, file settings, CLI flags, and returns valid config."""
    config_file = tmp_path / "config.json"
    file_data = get_default_config()
    file_data["theme"] = "stealth"
    save_config_file(file_data, config_file)

    effective = load_effective_config(["--config", str(config_file), "--size", "420"])
    assert effective["theme"] == "stealth"
    assert effective["size"] == 420
    assert effective["polling_interval_seconds"] == 1.0


def test_platform_default_config_path_unix():
    """Platform-independent check for Unix default path."""
    with patch("sys.platform", "linux"):
        expected = Path.home() / ".boostgauge" / "config.json"
        actual = get_default_config_path()
        assert actual == expected


def test_platform_default_config_path_windows():
    """Platform-independent check for Windows default path using pathlib."""
    with patch("sys.platform", "win32"), patch.dict(os.environ, {"APPDATA": r"C:\Users\test\AppData\Roaming"}):
        expected = Path(r"C:\Users\test\AppData\Roaming") / "boostgauge" / "config.json"
        actual = get_default_config_path()
        assert actual == expected


def test_platform_default_config_path_windows_no_appdata():
    """Windows fallback path when APPDATA env var is not set."""
    env_without_appdata = {k: v for k, v in os.environ.items() if k != "APPDATA"}
    with patch("sys.platform", "win32"), patch.dict(os.environ, env_without_appdata, clear=True):
        expected = Path.home() / "AppData" / "Roaming" / "boostgauge" / "config.json"
        actual = get_default_config_path()
        assert actual == expected


def test_additional_validation_errors():
    """Verify detailed validation failure branches."""
    cfg = get_default_config()
    cfg["polling_interval_seconds"] = 0
    with pytest.raises(ValueError, match="polling_interval_seconds"):
        validate_config(cfg)

    cfg = get_default_config()
    cfg["size"] = 50
    with pytest.raises(ValueError, match="size"):
        validate_config(cfg)

    cfg = get_default_config()
    cfg["always_on_top"] = "invalid_bool"
    with pytest.raises(ValueError, match="always_on_top"):
        validate_config(cfg)

    cfg = get_default_config()
    cfg["position"] = {"x": 10}
    with pytest.raises(ValueError, match="position"):
        validate_config(cfg)

    cfg = get_default_config()
    cfg["thresholds"]["conpty"]["yellow"] = 30.0
    cfg["thresholds"]["conpty"]["red"] = 20.0
    with pytest.raises(ValueError, match="0 <= yellow <= red"):
        validate_config(cfg)

    cfg = get_default_config()
    cfg["telltale_windows"]["short"] = -10
    with pytest.raises(ValueError, match="telltale_windows"):
        validate_config(cfg)


def test_get_default_config_returns_deep_copy():
    """Each call returns a fresh dict that does not share mutable state."""
    cfg1 = get_default_config()
    cfg2 = get_default_config()
    cfg1["thresholds"]["conpty"]["yellow"] = 999.0
    assert cfg2["thresholds"]["conpty"]["yellow"] == DEFAULT_CONFIG["thresholds"]["conpty"]["yellow"]


def test_save_and_load_roundtrip(tmp_path: Path):
    """Config written by save_config_file is faithfully restored by load_config_file."""
    config_file = tmp_path / "config.json"
    original = get_default_config()
    original["theme"] = "light"
    original["opacity"] = 0.5
    save_config_file(original, config_file)
    loaded = load_config_file(config_file)
    assert loaded == original


def test_merge_config_none_values_unchanged():
    """CLI args with None values leave file config untouched."""
    file_config = get_default_config()
    file_config["theme"] = "cyberpunk"
    file_config["size"] = 500

    cli_args = parse_cli_args([])
    merged = merge_config(file_config, cli_args)

    assert merged["theme"] == "cyberpunk"
    assert merged["size"] == 500


def test_merge_config_no_topmost_false_leaves_always_on_top():
    """no_topmost=False leaves always_on_top as set in file_config."""
    file_config = get_default_config()
    file_config["always_on_top"] = True

    cli_args = parse_cli_args([])
    assert cli_args.no_topmost is False
    merged = merge_config(file_config, cli_args)
    assert merged["always_on_top"] is True


def test_merge_config_no_topmost_sets_always_on_top_false():
    """no_topmost=True sets always_on_top=False regardless of file config."""
    file_config = get_default_config()
    file_config["always_on_top"] = True

    cli_args = parse_cli_args(["--no-topmost"])
    merged = merge_config(file_config, cli_args)
    assert merged["always_on_top"] is False


def test_update_window_geometry_position_only(tmp_path: Path):
    """update_window_geometry with only position does not change size."""
    config_file = tmp_path / "config.json"
    original = get_default_config()
    original["size"] = 300
    save_config_file(original, config_file)

    update_window_geometry(config_file, position=(10, 20))

    updated = load_config_file(config_file)
    assert updated["position"] == {"x": 10, "y": 20}
    assert updated["size"] == 300


def test_update_window_geometry_size_only(tmp_path: Path):
    """update_window_geometry with only size does not change position."""
    config_file = tmp_path / "config.json"
    original = get_default_config()
    original["position"] = {"x": 50, "y": 60}
    save_config_file(original, config_file)

    update_window_geometry(config_file, size=450)

    updated = load_config_file(config_file)
    assert updated["position"] == {"x": 50, "y": 60}
    assert updated["size"] == 450


def test_update_window_geometry_missing_file(tmp_path: Path):
    """update_window_geometry creates config from defaults when file does not exist."""
    config_file = tmp_path / "nonexistent" / "config.json"
    assert not config_file.exists()

    update_window_geometry(config_file, position=(5, 15), size=200)

    assert config_file.exists()
    updated = load_config_file(config_file)
    assert updated["position"] == {"x": 5, "y": 15}
    assert updated["size"] == 200


def test_update_window_geometry_corrupt_file(tmp_path: Path):
    """update_window_geometry falls back to defaults when existing file is corrupt."""
    config_file = tmp_path / "config.json"
    config_file.write_text("not valid json", encoding="utf-8")

    update_window_geometry(config_file, position=(77, 88))

    updated = load_config_file(config_file)
    assert updated["position"] == {"x": 77, "y": 88}


def test_reset_config_file_creates_directories(tmp_path: Path):
    """reset_config_file auto-creates missing parent directories."""
    config_file = tmp_path / "deep" / "dir" / "config.json"
    assert not config_file.parent.exists()

    result = reset_config_file(config_file)

    assert config_file.exists()
    assert result == DEFAULT_CONFIG


def test_reset_config_file_overwrites_existing(tmp_path: Path):
    """reset_config_file overwrites a modified file with defaults."""
    config_file = tmp_path / "config.json"
    modified = get_default_config()
    modified["theme"] = "light"
    modified["size"] = 999
    save_config_file(modified, config_file)

    result = reset_config_file(config_file)

    assert result["theme"] == "dark"
    assert result["size"] == 300
    on_disk = load_config_file(config_file)
    assert on_disk["theme"] == "dark"


def test_validate_config_passes_valid_config():
    """validate_config returns the config dict unchanged when all fields are valid."""
    cfg = get_default_config()
    result = validate_config(cfg)
    assert result == cfg


def test_validate_config_size_too_large():
    """validate_config raises ValueError when size exceeds 2000."""
    cfg = get_default_config()
    cfg["size"] = 2001
    with pytest.raises(ValueError, match="size"):
        validate_config(cfg)


def test_validate_config_negative_poll():
    """validate_config raises ValueError for negative polling_interval_seconds."""
    cfg = get_default_config()
    cfg["polling_interval_seconds"] = -1.0
    with pytest.raises(ValueError, match="polling_interval_seconds"):
        validate_config(cfg)


def test_validate_config_show_flags_not_bool():
    """validate_config raises ValueError when show_* flags are not booleans."""
    for key in ["show_driver_label", "show_digital_readout", "show_session_count"]:
        cfg = get_default_config()
        cfg[key] = "yes"
        with pytest.raises(ValueError, match=key):
            validate_config(cfg)


def test_validate_config_threshold_missing_metric():
    """validate_config raises ValueError when a required threshold metric is missing."""
    cfg = get_default_config()
    del cfg["thresholds"]["conpty"]
    with pytest.raises(ValueError, match="conpty"):
        validate_config(cfg)


def test_validate_config_threshold_negative_yellow():
    """validate_config raises ValueError when yellow threshold is negative."""
    cfg = get_default_config()
    cfg["thresholds"]["memory_percent"]["yellow"] = -5.0
    cfg["thresholds"]["memory_percent"]["red"] = 10.0
    with pytest.raises(ValueError, match="0 <= yellow <= red"):
        validate_config(cfg)


def test_validate_config_thresholds_not_dict():
    """validate_config raises ValueError when thresholds is not a dict."""
    cfg = get_default_config()
    cfg["thresholds"] = "bad"
    with pytest.raises(ValueError, match="thresholds must be a dictionary"):
        validate_config(cfg)


def test_validate_config_telltale_not_dict():
    """validate_config raises ValueError when telltale_windows is not a dict."""
    cfg = get_default_config()
    cfg["telltale_windows"] = None
    with pytest.raises(ValueError, match="telltale_windows must be a dictionary"):
        validate_config(cfg)


def test_validate_config_position_non_int_coords():
    """validate_config raises ValueError when position coords are not integers."""
    cfg = get_default_config()
    cfg["position"] = {"x": 1.5, "y": 2}
    with pytest.raises(ValueError, match="position"):
        validate_config(cfg)


def test_validate_config_position_missing_key():
    """validate_config raises ValueError when position dict lacks required keys."""
    cfg = get_default_config()
    cfg["position"] = {"x": 10}
    with pytest.raises(ValueError, match="position"):
        validate_config(cfg)


def test_load_config_file_non_dict_json(tmp_path: Path):
    """load_config_file raises ValueError when JSON root is not an object."""
    config_file = tmp_path / "config.json"
    config_file.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        load_config_file(config_file)


def test_cli_args_default_values():
    """parse_cli_args returns None/False defaults when no flags provided."""
    args = parse_cli_args([])
    assert args.theme is None
    assert args.size is None
    assert args.poll is None
    assert args.opacity is None
    assert args.no_topmost is False
    assert args.config is None
    assert args.reset_config is False