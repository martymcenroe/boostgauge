"""Integration tests for boostgauge.config module.

Issue #7: Feature: Configuration File and CLI Arguments
"""

import json
from pathlib import Path
import pytest

from boostgauge.config import (
    BoostGaugeConfig,
    CLIArgs,
    ConfigValidationError,
    load_config,
    merge_config_and_cli,
    notify_config_listeners,
    parse_cli_args,
    register_config_listener,
    reset_config_to_defaults,
    save_config,
    update_window_state,
    _CONFIG_LISTENERS,
)


@pytest.fixture(autouse=True)
def clear_listeners():
    _CONFIG_LISTENERS.clear()
    yield
    _CONFIG_LISTENERS.clear()


def test_auto_create_default_config_file(tmp_path):
    """Test auto-creation of default config file when path does not exist (REQ-1)."""
    target_config = tmp_path / "boostgauge" / "config.json"
    assert not target_config.exists()

    config = load_config(target_config)
    assert target_config.exists()
    assert config.theme == "dark"
    assert config.size == 300

    with open(target_config, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["theme"] == "dark"
    assert data["size"] == 300


def test_auto_created_config_matches_defaults(tmp_path):
    """Test auto-created config equals BoostGaugeConfig() defaults."""
    target_config = tmp_path / "config.json"
    config = load_config(target_config)
    assert config == BoostGaugeConfig()


def test_save_and_restore_window_state(tmp_path):
    """Test saving and restoring window position and size on exit/launch (REQ-3)."""
    config_file = tmp_path / "config.json"
    initial_config = load_config(config_file)

    updated_config = update_window_state(initial_config, x=450, y=250, size=500, config_path=config_file)
    assert updated_config.position.x == 450
    assert updated_config.position.y == 250
    assert updated_config.size == 500

    restored_config = load_config(config_file)
    assert restored_config.position.x == 450
    assert restored_config.position.y == 250
    assert restored_config.size == 500


def test_window_state_save_restore_specific_values(tmp_path):
    """Test window state save/restore with spec-referenced values (REQ-3)."""
    config_file = tmp_path / "config.json"
    config = load_config(config_file)

    update_window_state(config, x=150, y=200, size=350, config_path=config_file)

    restored = load_config(config_file)
    assert restored.position.x == 150
    assert restored.position.y == 200
    assert restored.size == 350


def test_dynamic_listener_notifications():
    """Test dynamic registration and notification of config observers (REQ-4)."""
    received_configs = []

    def observer(cfg: BoostGaugeConfig):
        received_configs.append(cfg)

    register_config_listener(observer)

    test_cfg = BoostGaugeConfig(theme="light", size=400)
    notify_config_listeners(test_cfg)

    assert len(received_configs) == 1
    assert received_configs[0].theme == "light"
    assert received_configs[0].size == 400


def test_dynamic_listener_threshold_update():
    """Test observer receives updated threshold values (REQ-4)."""
    received = []

    def observer(cfg: BoostGaugeConfig):
        received.append(cfg)

    register_config_listener(observer)

    from boostgauge.config import ThresholdRange, ThresholdsConfig
    cfg = BoostGaugeConfig()
    cfg.thresholds.conpty = ThresholdRange(yellow=35.0, red=70.0)
    notify_config_listeners(cfg)

    assert len(received) == 1
    assert received[0].thresholds.conpty.yellow == 35.0


def test_register_same_listener_once():
    """Test registering same callback multiple times only registers once."""
    call_count = []

    def observer(cfg: BoostGaugeConfig):
        call_count.append(1)

    register_config_listener(observer)
    register_config_listener(observer)
    register_config_listener(observer)

    notify_config_listeners(BoostGaugeConfig())
    assert len(call_count) == 1


def test_notify_no_listeners_is_noop():
    """Test notify with no listeners is a no-op."""
    notify_config_listeners(BoostGaugeConfig())


def test_multiple_listeners_all_called():
    """Test all registered listeners are called."""
    results = []

    register_config_listener(lambda cfg: results.append("a"))
    register_config_listener(lambda cfg: results.append("b"))
    register_config_listener(lambda cfg: results.append("c"))

    notify_config_listeners(BoostGaugeConfig())
    assert sorted(results) == ["a", "b", "c"]


def test_corrupted_json_file_handling(tmp_path):
    """Test graceful failure when loading malformed JSON file (REQ-5)."""
    corrupt_file = tmp_path / "corrupt.json"
    corrupt_file.write_text("{invalid_json_content:", encoding="utf-8")

    with pytest.raises(ConfigValidationError, match="Failed to parse JSON configuration file"):
        load_config(corrupt_file)


def test_reset_config_to_defaults(tmp_path):
    """Test resetting config file to factory defaults via reset_config_to_defaults (REQ-7)."""
    config_file = tmp_path / "config.json"
    custom_cfg = BoostGaugeConfig(theme="light", size=500)
    save_config(custom_cfg, config_file)

    reset_cfg = reset_config_to_defaults(config_file)
    assert reset_cfg.theme == "dark"
    assert reset_cfg.size == 300

    reloaded = load_config(config_file)
    assert reloaded.theme == "dark"
    assert reloaded.size == 300


def test_reset_config_returns_boostgauge_defaults(tmp_path):
    """Test reset_config_to_defaults returns object equal to BoostGaugeConfig()."""
    config_file = tmp_path / "config.json"
    save_config(BoostGaugeConfig(theme="light", opacity=0.5, size=800), config_file)

    reset_cfg = reset_config_to_defaults(config_file)
    assert reset_cfg == BoostGaugeConfig()


def test_reset_config_file_content_is_defaults(tmp_path):
    """Test reset_config_to_defaults writes default JSON to disk."""
    config_file = tmp_path / "config.json"
    save_config(BoostGaugeConfig(theme="light", size=700), config_file)

    reset_config_to_defaults(config_file)

    with open(config_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["theme"] == "dark"
    assert data["size"] == 300


def test_custom_config_path_loaded(tmp_path):
    """Test custom config path is loaded instead of default (REQ-6)."""
    custom_path = tmp_path / "custom_config.json"
    custom_cfg = BoostGaugeConfig(theme="light", size=450)
    save_config(custom_cfg, custom_path)

    loaded = load_config(custom_path)
    assert loaded.theme == "light"
    assert loaded.size == 450


def test_cli_args_override_config_values(tmp_path):
    """Test CLI arguments take precedence over file config values (REQ-2)."""
    config_file = tmp_path / "config.json"
    base_cfg = BoostGaugeConfig(theme="dark", size=300)
    save_config(base_cfg, config_file)

    loaded = load_config(config_file)
    cli_args = parse_cli_args(["--theme", "light", "--size", "400"])
    merged = merge_config_and_cli(loaded, cli_args)

    assert merged.theme == "light"
    assert merged.size == 400


def test_cli_no_topmost_overrides_always_on_top(tmp_path):
    """Test --no-topmost CLI flag disables always_on_top from config."""
    config_file = tmp_path / "config.json"
    save_config(BoostGaugeConfig(always_on_top=True), config_file)

    loaded = load_config(config_file)
    cli_args = parse_cli_args(["--no-topmost"])
    merged = merge_config_and_cli(loaded, cli_args)

    assert merged.always_on_top is False


def test_full_config_lifecycle(tmp_path):
    """Test complete config lifecycle: create, modify, save, reload."""
    config_file = tmp_path / "lifecycle_config.json"

    # First launch: auto-create
    config = load_config(config_file)
    assert config == BoostGaugeConfig()

    # Merge CLI args
    cli_args = CLIArgs(theme="light", size=400, opacity=0.75)
    config = merge_config_and_cli(config, cli_args)
    assert config.theme == "light"
    assert config.size == 400

    # Save state on "exit"
    update_window_state(config, x=200, y=300, size=400, config_path=config_file)

    # Reload on "relaunch"
    reloaded = load_config(config_file)
    assert reloaded.theme == "light"
    assert reloaded.position.x == 200
    assert reloaded.position.y == 300
    assert reloaded.size == 400


def test_load_config_from_sample_fixture():
    """Test loading from the sample fixture file."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "sample_config.json"
    config = load_config(fixture_path)
    assert config.theme == "dark"
    assert config.size == 300
    assert config.opacity == 0.9
    assert config.thresholds.conpty.yellow == 30.0
    assert config.thresholds.conpty.red == 60.0
    assert config.telltale_windows.short == 60
    assert config.telltale_windows.medium == 600
    assert config.telltale_windows.long == 3600


def test_save_config_atomic_write(tmp_path):
    """Test that save_config does not leave .tmp files behind."""
    config_file = tmp_path / "config.json"
    save_config(BoostGaugeConfig(), config_file)

    tmp_file = config_file.with_suffix(".tmp")
    assert not tmp_file.exists()
    assert config_file.exists()


def test_update_window_state_persists_other_fields(tmp_path):
    """Test update_window_state preserves non-position/size fields."""
    config_file = tmp_path / "config.json"
    cfg = BoostGaugeConfig(theme="light", opacity=0.6)
    save_config(cfg, config_file)

    loaded = load_config(config_file)
    update_window_state(loaded, x=10, y=20, size=200, config_path=config_file)

    reloaded = load_config(config_file)
    assert reloaded.theme == "light"
    assert reloaded.opacity == 0.6
    assert reloaded.position.x == 10
    assert reloaded.size == 200