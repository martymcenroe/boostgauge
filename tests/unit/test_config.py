"""Unit tests for BoostGauge configuration system.

Issue #7: Configuration File and CLI Arguments
"""

import json
from pathlib import Path
import pytest

from boostgauge.config import (
    AppConfig,
    ConfigManager,
    ThresholdPair,
    ThresholdsConfig,
    WindowPosition,
    _validate_threshold_pair,
    get_default_config_path,
    load_config_file,
    merge_config,
    parse_cli_args,
    save_config_file,
    validate_config_dict,
)


def test_t010_auto_creation_of_missing_config_file(tmp_path: Path):
    """T010: Verify default config file is automatically created at destination when missing."""
    config_file = tmp_path / "sub" / "config.json"
    assert not config_file.exists()

    loaded_dict = load_config_file(config_file)
    assert config_file.exists()
    assert loaded_dict["theme"] == "dark"
    assert loaded_dict["size"] == 300
    assert loaded_dict["polling_interval_seconds"] == 2.0


def test_t020_cli_arguments_overriding_file_settings(tmp_path: Path):
    """T020: Verify CLI argument options take runtime precedence over file settings."""
    config_file = tmp_path / "config.json"
    initial_config = AppConfig(theme="dark", size=300, polling_interval_seconds=2.0)
    save_config_file(initial_config, config_file)

    cli_args = parse_cli_args(["--config", str(config_file), "--theme", "light", "--size", "450"])
    base_config = validate_config_dict(load_config_file(config_file))
    merged = merge_config(base_config, cli_args)

    assert merged.theme == "light"
    assert merged.size == 450
    assert merged.polling_interval_seconds == 2.0


def test_t030_geometry_preservation_across_exit_and_launch(tmp_path: Path):
    """T030: Verify window position and size geometry are persisted and restored correctly."""
    config_file = tmp_path / "config.json"
    manager = ConfigManager(config_path=config_file, cli_args=[])

    new_pos = WindowPosition(x=250, y=320)
    new_size = 400
    manager.save_geometry(new_pos, new_size)

    reloaded_manager = ConfigManager(config_path=config_file, cli_args=[])
    assert reloaded_manager.config.position.x == 250
    assert reloaded_manager.config.position.y == 320
    assert reloaded_manager.config.size == 400


def test_t040_dynamic_threshold_update_notifications(tmp_path: Path):
    """T040: Verify registered observers receive dynamic threshold update notifications."""
    config_file = tmp_path / "config.json"
    manager = ConfigManager(config_path=config_file, cli_args=[])

    notifications = []

    def observer(thresholds: ThresholdsConfig):
        notifications.append(thresholds.conpty.yellow)

    manager.register_threshold_observer(observer)
    manager.update_thresholds({"conpty": {"yellow": 45.0, "red": 80.0}})

    assert len(notifications) == 1
    assert notifications[0] == 45.0
    assert manager.config.thresholds.conpty.yellow == 45.0
    assert manager.config.thresholds.conpty.red == 80.0


def test_t050_fail_closed_validation_for_invalid_config(tmp_path: Path):
    """T050: Verify strict fail-closed validation raises ValueError on invalid inputs."""
    with pytest.raises(ValueError, match="opacity must be between 0.0 and 1.0"):
        validate_config_dict({"opacity": 1.5})

    with pytest.raises(ValueError, match="size must be positive integer"):
        validate_config_dict({"size": -50})

    with pytest.raises(ValueError, match="yellow threshold .* must be less than red threshold"):
        validate_config_dict({
            "thresholds": {
                "conpty": {"yellow": 70.0, "red": 50.0}
            }
        })

    corrupt_file = tmp_path / "corrupt.json"
    corrupt_file.write_text("{invalid json", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid JSON in configuration file"):
        load_config_file(corrupt_file)


def test_t060_reset_configuration_flag_operation(tmp_path: Path):
    """T060: Verify --reset-config flag resets modified configuration file to defaults."""
    config_file = tmp_path / "config.json"
    custom_config = AppConfig(theme="light", size=500)
    save_config_file(custom_config, config_file)

    manager = ConfigManager(config_path=config_file, cli_args=["--reset-config"])
    assert manager.config.theme == "dark"
    assert manager.config.size == 300

    reloaded_dict = load_config_file(config_file)
    assert reloaded_dict["theme"] == "dark"
    assert reloaded_dict["size"] == 300


def test_default_config_path_resolution(monkeypatch):
    """Verify platform-specific default path resolution using pathlib comparison."""
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setenv("APPDATA", r"C:\Users\TestUser\AppData\Roaming")
    win_path = get_default_config_path()
    assert win_path == Path(r"C:\Users\TestUser\AppData\Roaming") / "boostgauge" / "config.json"

    monkeypatch.setattr("sys.platform", "linux")
    posix_path = get_default_config_path()
    assert posix_path == Path.home() / ".boostgauge" / "config.json"


def test_load_config_file_returns_dict_for_valid_json(tmp_path: Path):
    """Verify load_config_file returns parsed dict for a valid existing JSON file."""
    config_file = tmp_path / "config.json"
    data = {"theme": "light", "size": 400, "polling_interval_seconds": 1.0}
    config_file.write_text(json.dumps(data), encoding="utf-8")

    result = load_config_file(config_file)
    assert result["theme"] == "light"
    assert result["size"] == 400


def test_save_config_file_creates_parent_dirs(tmp_path: Path):
    """Verify save_config_file creates parent directories if they don't exist."""
    config_file = tmp_path / "nested" / "deep" / "config.json"
    config = AppConfig()
    save_config_file(config, config_file)

    assert config_file.exists()
    loaded = json.loads(config_file.read_text(encoding="utf-8"))
    assert loaded["theme"] == "dark"


def test_save_config_file_is_atomic(tmp_path: Path):
    """Verify save_config_file does not leave a .tmp file on success."""
    config_file = tmp_path / "config.json"
    config = AppConfig()
    save_config_file(config, config_file)

    tmp_file = config_file.with_suffix(".tmp")
    assert not tmp_file.exists()
    assert config_file.exists()


def test_validate_config_dict_defaults():
    """Verify validate_config_dict returns AppConfig with defaults for empty dict."""
    config = validate_config_dict({})
    assert config.theme == "dark"
    assert config.size == 300
    assert config.opacity == 0.9
    assert config.polling_interval_seconds == 2.0
    assert config.always_on_top is True
    assert config.position.x == 100
    assert config.position.y == 100


def test_validate_config_dict_invalid_theme():
    """Verify validate_config_dict raises ValueError for unsupported theme."""
    with pytest.raises(ValueError, match="Invalid theme 'neon'"):
        validate_config_dict({"theme": "neon"})


def test_validate_config_dict_invalid_polling_interval():
    """Verify validate_config_dict raises ValueError for non-positive polling interval."""
    with pytest.raises(ValueError, match="polling_interval_seconds must be positive"):
        validate_config_dict({"polling_interval_seconds": 0.0})

    with pytest.raises(ValueError, match="polling_interval_seconds must be positive"):
        validate_config_dict({"polling_interval_seconds": -1.0})


def test_validate_config_dict_threshold_equal_yellow_red():
    """Verify validate_config_dict raises ValueError when yellow equals red threshold."""
    with pytest.raises(ValueError, match="yellow threshold"):
        validate_config_dict({
            "thresholds": {
                "memory_percent": {"yellow": 50.0, "red": 50.0}
            }
        })


def test_parse_cli_args_defaults():
    """Verify parse_cli_args returns None defaults when no arguments provided."""
    args = parse_cli_args([])
    assert args.theme is None
    assert args.size is None
    assert args.opacity is None
    assert args.polling_interval is None
    assert args.config is None
    assert args.reset_config is False


def test_parse_cli_args_all_options():
    """Verify parse_cli_args correctly parses all supported CLI flags."""
    args = parse_cli_args([
        "--theme", "light",
        "--size", "400",
        "--opacity", "0.75",
        "--polling-interval", "1.5",
        "--config", "/tmp/custom.json",
        "--reset-config",
    ])
    assert args.theme == "light"
    assert args.size == 400
    assert args.opacity == 0.75
    assert args.polling_interval == 1.5
    assert args.config == "/tmp/custom.json"
    assert args.reset_config is True


def test_merge_config_no_overrides():
    """Verify merge_config returns config identical to file_config when all CLI args are None."""
    file_config = AppConfig(theme="light", size=500, opacity=0.8)
    cli_args = parse_cli_args([])
    merged = merge_config(file_config, cli_args)

    assert merged.theme == "light"
    assert merged.size == 500
    assert merged.opacity == 0.8


def test_merge_config_partial_overrides():
    """Verify merge_config only overrides values explicitly set in CLI args."""
    file_config = AppConfig(theme="dark", size=300, opacity=0.9, polling_interval_seconds=2.0)
    cli_args = parse_cli_args(["--opacity", "0.5"])
    merged = merge_config(file_config, cli_args)

    assert merged.theme == "dark"
    assert merged.size == 300
    assert merged.opacity == 0.5
    assert merged.polling_interval_seconds == 2.0


def test_merge_config_polling_interval_override():
    """Verify merge_config overrides polling_interval_seconds when --polling-interval is provided."""
    file_config = AppConfig(polling_interval_seconds=2.0)
    cli_args = parse_cli_args(["--polling-interval", "0.5"])
    merged = merge_config(file_config, cli_args)

    assert merged.polling_interval_seconds == 0.5
    assert merged.theme == "dark"


def test_config_manager_uses_default_path_when_none(tmp_path: Path, monkeypatch):
    """Verify ConfigManager uses get_default_config_path() when config_path is None."""
    expected_path = tmp_path / "config.json"
    monkeypatch.setattr("boostgauge.config.get_default_config_path", lambda: expected_path)

    manager = ConfigManager(cli_args=[])
    assert manager.config_path == expected_path


def test_config_manager_cli_config_overrides_path(tmp_path: Path):
    """Verify ConfigManager uses --config CLI path over the config_path argument."""
    cli_config_file = tmp_path / "cli_config.json"
    save_config_file(AppConfig(theme="light"), cli_config_file)

    other_path = tmp_path / "other_config.json"
    manager = ConfigManager(config_path=other_path, cli_args=["--config", str(cli_config_file)])

    assert manager.config_path == cli_config_file
    assert manager.config.theme == "light"


def test_config_manager_multiple_observers(tmp_path: Path):
    """Verify all registered observers are called on threshold update."""
    config_file = tmp_path / "config.json"
    manager = ConfigManager(config_path=config_file, cli_args=[])

    results_a = []
    results_b = []

    manager.register_threshold_observer(lambda t: results_a.append(t.conpty.red))
    manager.register_threshold_observer(lambda t: results_b.append(t.memory_percent.yellow))

    manager.update_thresholds({"conpty": {"yellow": 20.0, "red": 55.0}})

    assert results_a == [55.0]
    assert results_b == [60.0]


def test_config_manager_update_thresholds_invalid_does_not_call_observers(tmp_path: Path):
    """Verify observers are not called when threshold update has invalid values."""
    config_file = tmp_path / "config.json"
    manager = ConfigManager(config_path=config_file, cli_args=[])

    called = []
    manager.register_threshold_observer(lambda t: called.append(True))

    with pytest.raises(ValueError):
        manager.update_thresholds({"conpty": {"yellow": 90.0, "red": 10.0}})

    assert called == []


def test_config_manager_update_thresholds_persists_to_disk(tmp_path: Path):
    """Verify update_thresholds writes updated thresholds to disk."""
    config_file = tmp_path / "config.json"
    manager = ConfigManager(config_path=config_file, cli_args=[])
    manager.update_thresholds({"process_count": {"yellow": 150.0, "red": 350.0}})

    on_disk = json.loads(config_file.read_text(encoding="utf-8"))
    assert on_disk["thresholds"]["process_count"]["yellow"] == 150.0
    assert on_disk["thresholds"]["process_count"]["red"] == 350.0


def test_config_manager_save_geometry_persists(tmp_path: Path):
    """Verify save_geometry updates config and writes to disk."""
    config_file = tmp_path / "config.json"
    manager = ConfigManager(config_path=config_file, cli_args=[])
    manager.save_geometry(WindowPosition(x=800, y=600), 450)

    on_disk = json.loads(config_file.read_text(encoding="utf-8"))
    assert on_disk["position"]["x"] == 800
    assert on_disk["position"]["y"] == 600
    assert on_disk["size"] == 450
    assert manager.config.position.x == 800
    assert manager.config.size == 450


def test_config_manager_save_geometry_invalid_size(tmp_path: Path):
    """Verify save_geometry raises ValueError for non-positive size."""
    config_file = tmp_path / "config.json"
    manager = ConfigManager(config_path=config_file, cli_args=[])

    with pytest.raises(ValueError, match="size must be positive integer"):
        manager.save_geometry(WindowPosition(), 0)


def test_load_config_file_invalid_json_type(tmp_path: Path):
    """Verify load_config_file raises ValueError when JSON root is not an object."""
    config_file = tmp_path / "config.json"
    config_file.write_text("[1, 2, 3]", encoding="utf-8")

    with pytest.raises(ValueError, match="Configuration file root must be a JSON object"):
        load_config_file(config_file)


def test_validate_config_dict_full_config():
    """Verify validate_config_dict correctly parses a complete valid configuration dict."""
    raw = {
        "polling_interval_seconds": 1.5,
        "theme": "light",
        "size": 256,
        "opacity": 0.85,
        "always_on_top": False,
        "position": {"x": 120, "y": 140},
        "thresholds": {
            "conpty": {"yellow": 25.0, "red": 50.0},
            "memory_percent": {"yellow": 50.0, "red": 75.0},
            "process_count": {"yellow": 200.0, "red": 400.0},
            "handle_count": {"yellow": 20000.0, "red": 40000.0},
        },
        "telltale_windows": {"short": 30, "medium": 300, "long": 1800},
        "show_driver_label": True,
        "show_digital_readout": False,
        "show_session_count": True,
    }
    config = validate_config_dict(raw)

    assert config.polling_interval_seconds == 1.5
    assert config.theme == "light"
    assert config.size == 256
    assert config.opacity == 0.85
    assert config.always_on_top is False
    assert config.position.x == 120
    assert config.position.y == 140
    assert config.thresholds.conpty.yellow == 25.0
    assert config.thresholds.conpty.red == 50.0
    assert config.thresholds.memory_percent.yellow == 50.0
    assert config.thresholds.handle_count.red == 40000.0
    assert config.telltale_windows.short == 30
    assert config.telltale_windows.medium == 300
    assert config.telltale_windows.long == 1800
    assert config.show_driver_label is True
    assert config.show_digital_readout is False
    assert config.show_session_count is True


def test_default_config_path_win32_no_appdata(monkeypatch):
    """Verify fallback path on Windows when APPDATA env var is missing."""
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.delenv("APPDATA", raising=False)
    path = get_default_config_path()
    assert path == Path.home() / "AppData" / "Roaming" / "boostgauge" / "config.json"


def test_validate_threshold_pair_missing_keys():
    """Verify _validate_threshold_pair raises ValueError when yellow or red key is missing."""
    with pytest.raises(ValueError, match="must contain 'yellow' and 'red' values"):
        _validate_threshold_pair({"yellow": 10.0}, "conpty")

    with pytest.raises(ValueError, match="must contain 'yellow' and 'red' values"):
        _validate_threshold_pair({"red": 50.0}, "conpty")


def test_validate_threshold_pair_negative_values():
    """Verify _validate_threshold_pair raises ValueError for negative threshold values."""
    with pytest.raises(ValueError, match="must be non-negative"):
        _validate_threshold_pair({"yellow": -5.0, "red": 10.0}, "conpty")

    with pytest.raises(ValueError, match="must be non-negative"):
        _validate_threshold_pair({"yellow": 5.0, "red": -1.0}, "conpty")