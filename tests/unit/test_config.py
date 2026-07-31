"""Unit test suite for configuration file resolution, validation, CLI overrides, and geometry persistence.

Issue #7: Configuration File and CLI Arguments
Option C compliant: No GUI/tkinter initialization.
"""

import json
from pathlib import Path
import pytest

from boostgauge.config import (
    ConfigError,
    get_default_config,
    get_default_config_path,
    load_config_file,
    load_effective_config,
    merge_cli_overrides,
    parse_cli_args,
    save_config_file,
    update_window_geometry,
    validate_config,
)
from boostgauge.app import BoostGaugeApp
from boostgauge.__main__ import main


def test_default_config_path_resolution_windows(monkeypatch):
    """T020: Windows path uses APPDATA env var."""
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setenv("APPDATA", r"C:\Users\test\AppData\Roaming")
    win_path = get_default_config_path()
    assert win_path == Path(r"C:\Users\test\AppData\Roaming") / "boostgauge" / "config.json"


def test_default_config_path_resolution_windows_no_appdata(monkeypatch):
    """T020: Windows path falls back to home when APPDATA is missing."""
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: Path("/home/test")))
    win_path = get_default_config_path()
    assert win_path == Path("/home/test") / "AppData" / "Roaming" / "boostgauge" / "config.json"


def test_default_config_path_resolution_posix(monkeypatch):
    """T020: POSIX path uses home directory."""
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr(Path, "home", staticmethod(lambda: Path("/home/test")))
    posix_path = get_default_config_path()
    assert posix_path == Path("/home/test") / ".boostgauge" / "config.json"


def test_default_config_creation_on_missing_file(tmp_path):
    """T010: Missing file is created automatically with default schema."""
    config_file = tmp_path / "sub" / "config.json"
    assert not config_file.exists()

    cfg = load_config_file(config_file)
    assert config_file.exists()
    assert cfg == get_default_config()

    with open(config_file, "r", encoding="utf-8") as f:
        on_disk = json.load(f)
    assert on_disk["theme"] == "dark"
    assert on_disk["size"] == 300


def test_get_default_config_returns_correct_values():
    """Verify default config has all required keys with correct values."""
    cfg = get_default_config()
    assert cfg["polling_interval_seconds"] == 1.0
    assert cfg["theme"] == "dark"
    assert cfg["size"] == 300
    assert cfg["opacity"] == 0.9
    assert cfg["always_on_top"] is True
    assert cfg["position"] == {"x": 100, "y": 100}
    assert cfg["show_driver_label"] is True
    assert cfg["show_digital_readout"] is True
    assert cfg["show_session_count"] is True


def test_get_default_config_returns_deep_copy():
    """Mutating returned dict does not affect subsequent calls."""
    cfg1 = get_default_config()
    cfg1["theme"] = "neon"
    cfg2 = get_default_config()
    assert cfg2["theme"] == "dark"


def test_cli_theme_override(tmp_path):
    """T002: --theme CLI flag overrides config file theme."""
    config_file = tmp_path / "config.json"
    cfg = get_default_config()
    save_config_file(cfg, config_file)

    effective, _ = load_effective_config(["--config", str(config_file), "--theme", "neon"])
    assert effective["theme"] == "neon"

    on_disk = load_config_file(config_file)
    assert on_disk["theme"] == "dark"


def test_cli_size_override(tmp_path):
    """T003: --size CLI flag overrides config file size."""
    config_file = tmp_path / "config.json"
    save_config_file(get_default_config(), config_file)

    effective, _ = load_effective_config(["--config", str(config_file), "--size", "500"])
    assert effective["size"] == 500

    on_disk = load_config_file(config_file)
    assert on_disk["size"] == 300


def test_cli_poll_override(tmp_path):
    """T004: --poll CLI flag overrides polling_interval_seconds."""
    config_file = tmp_path / "config.json"
    save_config_file(get_default_config(), config_file)

    effective, _ = load_effective_config(["--config", str(config_file), "--poll", "0.5"])
    assert effective["polling_interval_seconds"] == 0.5

    on_disk = load_config_file(config_file)
    assert on_disk["polling_interval_seconds"] == 1.0


def test_cli_opacity_override(tmp_path):
    """T005: --opacity CLI flag overrides opacity."""
    config_file = tmp_path / "config.json"
    save_config_file(get_default_config(), config_file)

    effective, _ = load_effective_config(["--config", str(config_file), "--opacity", "0.5"])
    assert effective["opacity"] == 0.5

    on_disk = load_config_file(config_file)
    assert on_disk["opacity"] == 0.9


def test_cli_no_topmost_override(tmp_path):
    """T006: --no-topmost CLI flag sets always_on_top to False."""
    config_file = tmp_path / "config.json"
    save_config_file(get_default_config(), config_file)

    effective, _ = load_effective_config(["--config", str(config_file), "--no-topmost"])
    assert effective["always_on_top"] is False

    on_disk = load_config_file(config_file)
    assert on_disk["always_on_top"] is True


def test_cli_options_override_file(tmp_path):
    """T030: Multiple CLI flags override config file settings without mutating disk."""
    config_file = tmp_path / "config.json"
    default_cfg = get_default_config()
    save_config_file(default_cfg, config_file)

    cli_input = ["--config", str(config_file), "--theme", "neon", "--poll", "0.5", "--no-topmost"]
    effective_cfg, path = load_effective_config(cli_input)

    assert path == config_file
    assert effective_cfg["theme"] == "neon"
    assert effective_cfg["polling_interval_seconds"] == 0.5
    assert effective_cfg["always_on_top"] is False

    on_disk_cfg = load_config_file(config_file)
    assert on_disk_cfg["theme"] == "dark"
    assert on_disk_cfg["polling_interval_seconds"] == 1.0
    assert on_disk_cfg["always_on_top"] is True


def test_custom_config_path_via_cli(tmp_path):
    """T007/T040: --config flag loads settings from custom file path."""
    custom_dir = tmp_path / "custom_dir"
    custom_file = custom_dir / "custom_config.json"
    cli_input = ["--config", str(custom_file)]

    effective_cfg, path = load_effective_config(cli_input)
    assert path.resolve() == custom_file.resolve()
    assert custom_file.exists()
    assert effective_cfg == get_default_config()


def test_save_and_restore_geometry(tmp_path):
    """T050/T060: Geometry persistence on update and restoration on subsequent launch."""
    config_file = tmp_path / "config.json"
    cfg = get_default_config()
    save_config_file(cfg, config_file)

    updated_cfg = update_window_geometry(cfg, config_file, x=250, y=350, size=500)
    assert updated_cfg["position"]["x"] == 250
    assert updated_cfg["position"]["y"] == 350
    assert updated_cfg["size"] == 500

    restored_cfg, _ = load_effective_config(["--config", str(config_file)])
    assert restored_cfg["position"] == {"x": 250, "y": 350}
    assert restored_cfg["size"] == 500


def test_dynamic_threshold_updates(tmp_path):
    """T070: Threshold updates validate correctly in memory."""
    cfg = get_default_config()
    cfg["thresholds"]["conpty"]["yellow"] = 12.0
    cfg["thresholds"]["conpty"]["red"] = 25.0

    validated = validate_config(cfg)
    assert validated["thresholds"]["conpty"]["yellow"] == 12.0
    assert validated["thresholds"]["conpty"]["red"] == 25.0


def test_validation_invalid_opacity():
    """T080/T011: Opacity out of bounds raises ConfigError."""
    cfg = get_default_config()
    cfg["opacity"] = 1.5
    with pytest.raises(ConfigError, match="Invalid 'opacity'"):
        validate_config(cfg)

    cfg = get_default_config()
    cfg["opacity"] = 0.05
    with pytest.raises(ConfigError, match="Invalid 'opacity'"):
        validate_config(cfg)


def test_validation_invalid_size():
    """T080/T011: Size out of bounds raises ConfigError."""
    cfg = get_default_config()
    cfg["size"] = 50
    with pytest.raises(ConfigError, match="Invalid 'size'"):
        validate_config(cfg)

    cfg = get_default_config()
    cfg["size"] = 2001
    with pytest.raises(ConfigError, match="Invalid 'size'"):
        validate_config(cfg)


def test_validation_invalid_poll_interval():
    """T080/T011: Poll interval below minimum raises ConfigError."""
    cfg = get_default_config()
    cfg["polling_interval_seconds"] = 0.05
    with pytest.raises(ConfigError, match="Invalid 'polling_interval_seconds'"):
        validate_config(cfg)


def test_validation_invalid_theme():
    """T080/T011: Unrecognized theme raises ConfigError."""
    cfg = get_default_config()
    cfg["theme"] = "unknown_theme"
    with pytest.raises(ConfigError, match="Invalid 'theme'"):
        validate_config(cfg)


def test_validation_invalid_threshold_order():
    """T080/T011: Yellow >= red threshold raises ConfigError."""
    cfg = get_default_config()
    cfg["thresholds"]["memory_percent"]["yellow"] = 95.0
    cfg["thresholds"]["memory_percent"]["red"] = 80.0
    with pytest.raises(ConfigError, match="must be strictly less than"):
        validate_config(cfg)


def test_validation_missing_key():
    """T011: Missing required config key raises ConfigError."""
    cfg = get_default_config()
    del cfg["thresholds"]
    with pytest.raises(ConfigError, match="Missing required config key"):
        validate_config(cfg)


def test_validation_missing_position_key():
    """T011: Missing position keys raise ConfigError."""
    cfg = get_default_config()
    cfg["position"] = {"x": 100}
    with pytest.raises(ConfigError, match="Invalid 'position'"):
        validate_config(cfg)


def test_validation_invalid_boolean_field():
    """T011: Non-boolean value for boolean field raises ConfigError."""
    cfg = get_default_config()
    cfg["always_on_top"] = "yes"
    with pytest.raises(ConfigError, match="Invalid 'always_on_top'"):
        validate_config(cfg)


def test_validation_invalid_threshold_missing_metric():
    """T011: Missing threshold metric raises ConfigError."""
    cfg = get_default_config()
    del cfg["thresholds"]["conpty"]
    with pytest.raises(ConfigError, match="Invalid threshold metric"):
        validate_config(cfg)


def test_validation_invalid_threshold_missing_yellow_red():
    """T011: Threshold missing yellow/red keys raises ConfigError."""
    cfg = get_default_config()
    cfg["thresholds"]["conpty"] = {"yellow": 5.0}
    with pytest.raises(ConfigError, match="must specify 'yellow' and 'red'"):
        validate_config(cfg)


def test_validation_invalid_telltale_window():
    """T011: Non-positive telltale window raises ConfigError."""
    cfg = get_default_config()
    cfg["telltale_windows"]["short"] = 0
    with pytest.raises(ConfigError, match="Invalid telltale window"):
        validate_config(cfg)


def test_validation_non_dict_config():
    """T011: Non-dict config root raises ConfigError."""
    with pytest.raises(ConfigError, match="must be a JSON object"):
        validate_config("not a dict")


def test_validation_non_dict_thresholds():
    """T011: Non-dict thresholds raises ConfigError."""
    cfg = get_default_config()
    cfg["thresholds"] = "invalid"
    with pytest.raises(ConfigError, match="Invalid 'thresholds'"):
        validate_config(cfg)


def test_validation_non_dict_telltale_windows():
    """T011: Non-dict telltale_windows raises ConfigError."""
    cfg = get_default_config()
    cfg["telltale_windows"] = "invalid"
    with pytest.raises(ConfigError, match="Invalid 'telltale_windows'"):
        validate_config(cfg)


def test_validation_non_numeric_threshold_values():
    """T011: Non-numeric threshold values raise ConfigError."""
    cfg = get_default_config()
    cfg["thresholds"]["conpty"]["yellow"] = "high"
    with pytest.raises(ConfigError, match="must be numeric"):
        validate_config(cfg)


def test_validation_boolean_rejected_as_numeric():
    """T011: Boolean is rejected where numeric is expected."""
    cfg = get_default_config()
    cfg["polling_interval_seconds"] = True
    with pytest.raises(ConfigError, match="Invalid 'polling_interval_seconds'"):
        validate_config(cfg)

    cfg = get_default_config()
    cfg["size"] = True
    with pytest.raises(ConfigError, match="Invalid 'size'"):
        validate_config(cfg)

    cfg = get_default_config()
    cfg["opacity"] = True
    with pytest.raises(ConfigError, match="Invalid 'opacity'"):
        validate_config(cfg)


def test_validation_invalid_position_types():
    """T011: Non-integer position x/y raises ConfigError."""
    cfg = get_default_config()
    cfg["position"] = {"x": "left", "y": 100}
    with pytest.raises(ConfigError, match="must be integers"):
        validate_config(cfg)

    cfg = get_default_config()
    cfg["position"] = {"x": True, "y": 100}
    with pytest.raises(ConfigError, match="must be integers"):
        validate_config(cfg)


def test_malformed_json_error(tmp_path):
    """T090/T012: Malformed JSON triggers descriptive ConfigError."""
    config_file = tmp_path / "malformed.json"
    config_file.write_text("{ invalid json: ", encoding="utf-8")

    with pytest.raises(ConfigError, match="Malformed JSON"):
        load_config_file(config_file)


def test_reset_config_cli_option(tmp_path):
    """T100/T014: --reset-config resets config file to defaults."""
    config_file = tmp_path / "config.json"
    custom_cfg = get_default_config()
    custom_cfg["theme"] = "neon"
    custom_cfg["size"] = 800
    save_config_file(custom_cfg, config_file)

    assert load_config_file(config_file)["theme"] == "neon"

    effective_cfg, path = load_effective_config(["--config", str(config_file), "--reset-config"])
    assert path == config_file
    assert effective_cfg["theme"] == "dark"
    assert effective_cfg["size"] == 300

    on_disk = load_config_file(config_file)
    assert on_disk["theme"] == "dark"
    assert on_disk["size"] == 300


def test_reset_config_with_cli_override(tmp_path):
    """T014: --reset-config combined with --theme still applies theme override in memory."""
    config_file = tmp_path / "config.json"
    custom_cfg = get_default_config()
    custom_cfg["theme"] = "neon"
    save_config_file(custom_cfg, config_file)

    effective_cfg, _ = load_effective_config(["--config", str(config_file), "--reset-config", "--theme", "light"])
    assert effective_cfg["theme"] == "light"

    on_disk = load_config_file(config_file)
    assert on_disk["theme"] == "dark"


def test_main_entry_point_success(tmp_path):
    """main() returns 0 on valid config."""
    config_file = tmp_path / "config.json"
    exit_code = main(["--config", str(config_file)])
    assert exit_code == 0


def test_main_entry_point_error_exit(tmp_path, capsys):
    """T013: main() returns 1 and prints error on ConfigError."""
    config_file = tmp_path / "corrupt.json"
    config_file.write_text("{ corrupt ", encoding="utf-8")

    exit_code = main(["--config", str(config_file)])
    assert exit_code == 1

    captured = capsys.readouterr()
    assert "Error: Malformed JSON" in captured.err


def test_main_entry_point_invalid_size_cli(tmp_path, capsys):
    """T013: main() returns 1 on invalid CLI size value via config validation."""
    config_file = tmp_path / "config.json"
    save_config_file(get_default_config(), config_file)

    exit_code = main(["--config", str(config_file), "--size", "50"])
    assert exit_code == 1

    captured = capsys.readouterr()
    assert "Error:" in captured.err


def test_app_shutdown_persists_geometry(tmp_path):
    """T008/T009: BoostGaugeApp.shutdown() persists window geometry to disk."""
    config_file = tmp_path / "config.json"
    cfg, path = load_effective_config(["--config", str(config_file)])
    app = BoostGaugeApp(cfg, path)
    app.run()
    assert app._is_running is True

    app.shutdown(current_x=300, current_y=400, current_size=600)
    assert app._is_running is False

    disk_cfg = load_config_file(config_file)
    assert disk_cfg["position"] == {"x": 300, "y": 400}
    assert disk_cfg["size"] == 600


def test_app_shutdown_uses_current_config_when_no_args(tmp_path):
    """BoostGaugeApp.shutdown() with no args persists existing config position/size."""
    config_file = tmp_path / "config.json"
    cfg = get_default_config()
    cfg["position"] = {"x": 50, "y": 75}
    cfg["size"] = 400
    save_config_file(cfg, config_file)

    loaded_cfg, path = load_effective_config(["--config", str(config_file)])
    app = BoostGaugeApp(loaded_cfg, path)
    app.run()
    app.shutdown()

    disk_cfg = load_config_file(config_file)
    assert disk_cfg["position"] == {"x": 50, "y": 75}
    assert disk_cfg["size"] == 400


def test_save_config_file_creates_parent_dirs(tmp_path):
    """save_config_file creates parent directories if missing."""
    config_file = tmp_path / "deep" / "nested" / "config.json"
    assert not config_file.parent.exists()

    save_config_file(get_default_config(), config_file)
    assert config_file.exists()

    with open(config_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["theme"] == "dark"


def test_save_config_file_is_valid_json(tmp_path):
    """save_config_file writes valid, formatted JSON."""
    config_file = tmp_path / "config.json"
    cfg = get_default_config()
    save_config_file(cfg, config_file)

    with open(config_file, "r", encoding="utf-8") as f:
        content = f.read()

    parsed = json.loads(content)
    assert parsed == cfg
    assert "    " in content


def test_parse_cli_args_defaults():
    """parse_cli_args returns None defaults for optional args."""
    ns = parse_cli_args([])
    assert ns.theme is None
    assert ns.size is None
    assert ns.poll is None
    assert ns.opacity is None
    assert ns.no_topmost is False
    assert ns.config is None
    assert ns.reset_config is False


def test_parse_cli_args_all_flags():
    """parse_cli_args correctly parses all supported flags."""
    ns = parse_cli_args(["--theme", "neon", "--size", "400", "--poll", "2.0",
                         "--opacity", "0.8", "--no-topmost", "--reset-config"])
    assert ns.theme == "neon"
    assert ns.size == 400
    assert ns.poll == 2.0
    assert ns.opacity == 0.8
    assert ns.no_topmost is True
    assert ns.reset_config is True


def test_merge_cli_overrides_no_overrides():
    """merge_cli_overrides with all-None args returns copy of original config."""
    cfg = get_default_config()
    ns = parse_cli_args([])
    result = merge_cli_overrides(cfg, ns)
    assert result == cfg
    assert result is not cfg


def test_merge_cli_overrides_partial():
    """merge_cli_overrides applies only specified overrides."""
    cfg = get_default_config()
    ns = parse_cli_args(["--theme", "light"])
    result = merge_cli_overrides(cfg, ns)
    assert result["theme"] == "light"
    assert result["size"] == cfg["size"]
    assert result["opacity"] == cfg["opacity"]


def test_load_config_file_validates_loaded_data(tmp_path):
    """load_config_file raises ConfigError for invalid schema in file."""
    config_file = tmp_path / "config.json"
    bad_cfg = get_default_config()
    bad_cfg["opacity"] = 2.0

    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(bad_cfg, f)

    with pytest.raises(ConfigError, match="Invalid 'opacity'"):
        load_config_file(config_file)


def test_update_window_geometry_validates_bounds(tmp_path):
    """update_window_geometry raises ConfigError if new size is out of bounds."""
    config_file = tmp_path / "config.json"
    cfg = get_default_config()
    save_config_file(cfg, config_file)

    with pytest.raises(ConfigError, match="Invalid 'size'"):
        update_window_geometry(cfg, config_file, x=0, y=0, size=99)


def test_load_effective_config_no_args_uses_default_path(monkeypatch, tmp_path):
    """load_effective_config with no --config uses platform default path."""
    fake_path = tmp_path / "boostgauge" / "config.json"
    monkeypatch.setattr("boostgauge.config.get_default_config_path", lambda: fake_path)

    cfg, path = load_effective_config([])
    assert path == fake_path
    assert fake_path.exists()
    assert cfg == get_default_config()