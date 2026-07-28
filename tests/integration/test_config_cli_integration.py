"""Integration tests for configuration loading, CLI overrides, reset behavior, and disk state persistence.

Issue #7: Configuration File and CLI Arguments
"""

import json
from pathlib import Path
import pytest
from boostgauge.config import get_default_config, save_config, load_config, update_thresholds, save_window_state
from boostgauge.app import main


def test_integration_cli_overrides_memory_only(tmp_path):
    target = tmp_path / "config.json"
    config = get_default_config()
    config.theme = "dark"
    save_config(config, target)

    result = main(["--config", str(target), "--theme", "light"])
    assert result.theme == "light"

    loaded_from_disk = load_config(target)
    assert loaded_from_disk.theme == "dark"


def test_integration_reset_config_flag(tmp_path):
    target = tmp_path / "config.json"
    config = get_default_config()
    config.theme = "light"
    config.size = 500
    save_config(config, target)

    result = main(["--config", str(target), "--reset-config"])
    assert result.theme == "dark"
    assert result.size == 300

    loaded_from_disk = load_config(target)
    assert loaded_from_disk.theme == "dark"
    assert loaded_from_disk.size == 300


def test_integration_custom_config_path(tmp_path):
    custom_target = tmp_path / "custom_dir" / "my_config.json"
    config = get_default_config()
    config.opacity = 0.5
    save_config(config, custom_target)

    result = main(["--config", str(custom_target)])
    assert result.opacity == pytest.approx(0.5)
    assert custom_target.exists()


def test_integration_auto_create_on_missing_path(tmp_path):
    target = tmp_path / "new_dir" / "config.json"
    assert not target.exists()

    result = main(["--config", str(target)])
    assert target.exists()
    assert result.theme == "dark"

    disk_data = json.loads(target.read_text(encoding="utf-8"))
    assert disk_data["theme"] == "dark"


def test_integration_cli_size_override_not_persisted(tmp_path):
    target = tmp_path / "config.json"
    config = get_default_config()
    save_config(config, target)

    result = main(["--config", str(target), "--size", "800"])
    assert result.size == 800

    loaded_from_disk = load_config(target)
    assert loaded_from_disk.size == 300


def test_integration_cli_poll_override_not_persisted(tmp_path):
    target = tmp_path / "config.json"
    config = get_default_config()
    save_config(config, target)

    result = main(["--config", str(target), "--poll", "5"])
    assert result.polling_interval_seconds == 5

    loaded_from_disk = load_config(target)
    assert loaded_from_disk.polling_interval_seconds == 2


def test_integration_cli_opacity_override_not_persisted(tmp_path):
    target = tmp_path / "config.json"
    config = get_default_config()
    save_config(config, target)

    result = main(["--config", str(target), "--opacity", "0.6"])
    assert result.opacity == pytest.approx(0.6)

    loaded_from_disk = load_config(target)
    assert loaded_from_disk.opacity == pytest.approx(0.9)


def test_integration_cli_no_topmost_override_not_persisted(tmp_path):
    target = tmp_path / "config.json"
    config = get_default_config()
    save_config(config, target)

    result = main(["--config", str(target), "--no-topmost"])
    assert result.always_on_top is False

    loaded_from_disk = load_config(target)
    assert loaded_from_disk.always_on_top is True


def test_integration_save_window_state_persisted(tmp_path):
    target = tmp_path / "config.json"
    config = get_default_config()
    save_config(config, target)

    save_window_state(config, (150, 200), 350, target)

    restored = load_config(target)
    assert restored.position.x == 150
    assert restored.position.y == 200
    assert restored.size == 350


def test_integration_update_thresholds_persisted(tmp_path):
    target = tmp_path / "config.json"
    config = get_default_config()
    save_config(config, target)

    updated = update_thresholds(
        config,
        {"conpty": {"yellow": 40.0, "red": 70.0}},
        config_path=target,
    )
    assert updated.thresholds.conpty.yellow == pytest.approx(40.0)
    assert updated.thresholds.conpty.red == pytest.approx(70.0)

    restored = load_config(target)
    assert restored.thresholds.conpty.yellow == pytest.approx(40.0)
    assert restored.thresholds.conpty.red == pytest.approx(70.0)


def test_integration_full_lifecycle(tmp_path):
    target = tmp_path / "config.json"

    result = main(["--config", str(target)])
    assert result.theme == "dark"
    assert target.exists()

    update_thresholds(result, {"conpty": {"yellow": 45.0, "red": 75.0}}, config_path=target)
    save_window_state(result, (200, 300), 400, target)

    reloaded = load_config(target)
    assert reloaded.position.x == 200
    assert reloaded.position.y == 300
    assert reloaded.size == 400
    assert reloaded.thresholds.conpty.yellow == pytest.approx(45.0)
    assert reloaded.thresholds.conpty.red == pytest.approx(75.0)


def test_integration_reset_preserves_custom_path(tmp_path):
    target = tmp_path / "subdir" / "config.json"
    config = get_default_config()
    config.theme = "light"
    save_config(config, target)

    result = main(["--config", str(target), "--reset-config"])
    assert result.theme == "dark"
    assert target.exists()

    disk_data = json.loads(target.read_text(encoding="utf-8"))
    assert disk_data["theme"] == "dark"


def test_integration_multiple_cli_overrides(tmp_path):
    target = tmp_path / "config.json"
    config = get_default_config()
    save_config(config, target)

    result = main([
        "--config", str(target),
        "--theme", "light",
        "--size", "600",
        "--opacity", "0.7",
        "--no-topmost",
    ])
    assert result.theme == "light"
    assert result.size == 600
    assert result.opacity == pytest.approx(0.7)
    assert result.always_on_top is False

    loaded_from_disk = load_config(target)
    assert loaded_from_disk.theme == "dark"
    assert loaded_from_disk.size == 300
    assert loaded_from_disk.opacity == pytest.approx(0.9)
    assert loaded_from_disk.always_on_top is True