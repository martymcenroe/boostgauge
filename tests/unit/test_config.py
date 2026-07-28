"""Unit tests for configuration loading, saving, validation, and threshold updates.

Issue #7: Configuration File and CLI Arguments
"""

import json
import os
import sys
from pathlib import Path
import pytest
from boostgauge.config import (
    GaugeConfig,
    PositionConfig,
    ThresholdConfig,
    ThresholdLevel,
    get_default_config,
    get_default_config_path,
    load_config,
    save_config,
    save_window_state,
    update_thresholds,
    validate_config,
)


def test_get_default_config_path():
    path = get_default_config_path()
    assert isinstance(path, Path)
    assert path.name == "config.json"


def test_get_default_config_path_windows(monkeypatch):
    monkeypatch.setenv("APPDATA", r"C:\Users\testuser\AppData\Roaming")
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(os, "name", "nt")
    path = get_default_config_path()
    assert path.name == "config.json"
    assert path.parent.name == "boostgauge"


def test_get_default_config_path_windows_no_appdata(monkeypatch):
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(os, "name", "nt")
    path = get_default_config_path()
    assert path.name == "config.json"
    assert path.parent.name == "boostgauge"


def test_get_default_config_path_posix(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(os, "name", "posix")
    path = get_default_config_path()
    assert path.name == "config.json"
    assert path.parent.name == "boostgauge"


def test_get_default_config():
    config = get_default_config()
    assert config.polling_interval_seconds == 2
    assert config.theme == "dark"
    assert config.size == 300
    assert config.opacity == 0.9
    assert config.always_on_top is True
    assert config.position.x == 100
    assert config.position.y == 100
    assert config.show_driver_label is True
    assert config.show_digital_readout is True
    assert config.show_session_count is True


def test_get_default_config_thresholds():
    config = get_default_config()
    assert config.thresholds.conpty.yellow == 30.0
    assert config.thresholds.conpty.red == 60.0
    assert config.thresholds.memory_percent.yellow == 60.0
    assert config.thresholds.memory_percent.red == 80.0
    assert config.thresholds.process_count.yellow == 300.0
    assert config.thresholds.process_count.red == 500.0
    assert config.thresholds.handle_count.yellow == 30000.0
    assert config.thresholds.handle_count.red == 50000.0


def test_get_default_config_telltale_windows():
    config = get_default_config()
    assert config.telltale_windows.short == 60
    assert config.telltale_windows.medium == 600
    assert config.telltale_windows.long == 3600


def test_auto_create_config_file(tmp_path):
    target = tmp_path / "sub" / "config.json"
    assert not target.exists()
    config = load_config(target)
    assert target.exists()
    assert config.theme == "dark"


def test_auto_create_config_file_contents(tmp_path):
    target = tmp_path / "sub" / "config.json"
    load_config(target)
    with open(target, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["theme"] == "dark"
    assert data["polling_interval_seconds"] == 2


def test_save_and_load_config(tmp_path):
    target = tmp_path / "config.json"
    config = get_default_config()
    config.theme = "light"
    config.size = 450
    save_config(config, target)

    loaded = load_config(target)
    assert loaded.theme == "light"
    assert loaded.size == 450


def test_save_config_creates_parent_dirs(tmp_path):
    target = tmp_path / "nested" / "deep" / "config.json"
    config = get_default_config()
    save_config(config, target)
    assert target.exists()


def test_save_config_atomic_write(tmp_path):
    target = tmp_path / "config.json"
    config = get_default_config()
    save_config(config, target)
    tmp_file = target.with_name(target.name + ".tmp")
    assert not tmp_file.exists()
    assert target.exists()


def test_load_config_invalid_json(tmp_path):
    target = tmp_path / "config.json"
    target.write_text("{invalid json content", encoding="utf-8")
    with pytest.raises(ValueError, match="Failed to decode JSON config at"):
        load_config(target)


def test_save_window_state(tmp_path):
    target = tmp_path / "config.json"
    config = get_default_config()
    save_window_state(config, (250, 350), 400, target)

    loaded = load_config(target)
    assert loaded.position.x == 250
    assert loaded.position.y == 350
    assert loaded.size == 400


def test_save_window_state_updates_config_in_place(tmp_path):
    target = tmp_path / "config.json"
    config = get_default_config()
    save_window_state(config, (500, 600), 700, target)
    assert config.position.x == 500
    assert config.position.y == 600
    assert config.size == 700


def test_validate_config_valid():
    raw = {
        "polling_interval_seconds": 2,
        "theme": "dark",
        "size": 300,
        "opacity": 0.9,
        "always_on_top": True,
    }
    result = validate_config(raw)
    assert result["theme"] == "dark"


def test_validate_config_invalid_theme():
    raw = {"theme": "cyberpunk"}
    with pytest.raises(ValueError, match="theme must be one of"):
        validate_config(raw)


def test_validate_config_invalid_opacity_too_high():
    raw = {"opacity": 1.5}
    with pytest.raises(ValueError, match="opacity must be between"):
        validate_config(raw)


def test_validate_config_invalid_opacity_too_low():
    raw = {"opacity": 0.0}
    with pytest.raises(ValueError, match="opacity must be between"):
        validate_config(raw)


def test_validate_config_polling_too_low():
    raw = {"polling_interval_seconds": 0}
    with pytest.raises(ValueError, match="polling_interval_seconds"):
        validate_config(raw)


def test_validate_config_size_too_small():
    raw = {"size": 50}
    with pytest.raises(ValueError, match="size"):
        validate_config(raw)


def test_validate_config_size_too_large():
    raw = {"size": 3000}
    with pytest.raises(ValueError, match="size"):
        validate_config(raw)


def test_validate_config_threshold_yellow_ge_red():
    raw = {
        "thresholds": {
            "conpty": {"yellow": 80.0, "red": 50.0}
        }
    }
    with pytest.raises(ValueError, match="yellow threshold .* must be less than red threshold"):
        validate_config(raw)


def test_validate_config_threshold_yellow_eq_red():
    raw = {
        "thresholds": {
            "memory_percent": {"yellow": 70.0, "red": 70.0}
        }
    }
    with pytest.raises(ValueError, match="yellow threshold .* must be less than red threshold"):
        validate_config(raw)


def test_validate_config_null_position():
    raw = {"position": None}
    with pytest.raises(ValueError, match="position must be a dictionary or omitted"):
        validate_config(raw)


def test_validate_config_partial_threshold_yellow_ge_default_red():
    raw = {
        "thresholds": {
            "conpty": {"yellow": 80.0}
        }
    }
    with pytest.raises(ValueError, match="yellow threshold .* must be less than red threshold"):
        validate_config(raw)


def test_validate_config_invalid_always_on_top_type():
    raw = {"always_on_top": "yes"}
    with pytest.raises(ValueError, match="always_on_top must be a boolean"):
        validate_config(raw)


def test_update_thresholds_dynamic(tmp_path):
    target = tmp_path / "config.json"
    config = get_default_config()
    save_config(config, target)

    updated = update_thresholds(
        config,
        {"conpty": {"yellow": 40.0, "red": 70.0}},
        config_path=target,
    )
    assert updated.thresholds.conpty.yellow == 40.0
    assert updated.thresholds.conpty.red == 70.0

    loaded = load_config(target)
    assert loaded.thresholds.conpty.yellow == 40.0
    assert loaded.thresholds.conpty.red == 70.0


def test_update_thresholds_partial_update(tmp_path):
    target = tmp_path / "config.json"
    config = get_default_config()

    updated = update_thresholds(
        config,
        {"memory_percent": {"yellow": 50.0, "red": 75.0}},
        config_path=target,
    )
    assert updated.thresholds.memory_percent.yellow == 50.0
    assert updated.thresholds.memory_percent.red == 75.0
    assert updated.thresholds.conpty.yellow == 30.0
    assert updated.thresholds.conpty.red == 60.0


def test_update_thresholds_yellow_ge_red_raises():
    config = get_default_config()
    with pytest.raises(ValueError, match="yellow threshold .* must be less than red threshold"):
        update_thresholds(config, {"conpty": {"yellow": 70.0, "red": 40.0}})


def test_update_thresholds_no_persist_when_no_path():
    config = get_default_config()
    updated = update_thresholds(config, {"conpty": {"yellow": 40.0, "red": 70.0}})
    assert updated.thresholds.conpty.yellow == 40.0


def test_update_thresholds_multiple_metrics(tmp_path):
    target = tmp_path / "config.json"
    config = get_default_config()

    updated = update_thresholds(
        config,
        {
            "conpty": {"yellow": 40.0, "red": 70.0},
            "process_count": {"yellow": 250.0, "red": 450.0},
        },
        config_path=target,
    )
    assert updated.thresholds.conpty.yellow == 40.0
    assert updated.thresholds.process_count.yellow == 250.0
    assert updated.thresholds.process_count.red == 450.0


def test_load_config_roundtrip_preserves_all_fields(tmp_path):
    target = tmp_path / "config.json"
    config = get_default_config()
    config.theme = "light"
    config.opacity = 0.7
    config.always_on_top = False
    config.position.x = 200
    config.position.y = 300
    config.telltale_windows.short = 30
    config.show_driver_label = False
    save_config(config, target)

    loaded = load_config(target)
    assert loaded.theme == "light"
    assert loaded.opacity == 0.7
    assert loaded.always_on_top is False
    assert loaded.position.x == 200
    assert loaded.position.y == 300
    assert loaded.telltale_windows.short == 30
    assert loaded.show_driver_label is False