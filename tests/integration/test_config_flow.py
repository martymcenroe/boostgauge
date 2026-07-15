"""Integration tests checking multi-layer startup and reload configuration flow.

Ref: docs/design/0001-test-strategy.md
Constraint: No tkinter.Tk() in integration tests.
"""

import argparse
import json
import time
from pathlib import Path
from typing import Generator
import pytest

from boostgauge.config import ConfigManager, get_default_config, save_config


@pytest.fixture
def setup_config_file(tmp_path: Path) -> Generator[Path, None, None]:
    """Generates a reference configuration json on disk."""
    config_path = tmp_path / "config.json"
    conf = get_default_config()
    conf["theme"] = "integration-default"
    conf["opacity"] = 0.50
    save_config(conf, config_path)
    yield config_path


def test_integration_flow_startup_overrides(setup_config_file: Path) -> None:
    """Verifies startup combinations of config file and CLI argument overrides."""
    cli = argparse.Namespace(
        theme="cli-wins",
        size=512,
        poll=None,
        opacity=None,
        no_topmost=True,
        config=str(setup_config_file),
    )
    mgr = ConfigManager(config_path=setup_config_file, cli_args=cli)
    active_conf = mgr.load()

    assert active_conf["theme"] == "cli-wins"
    assert active_conf["size"] == 512
    assert active_conf["always_on_top"] is False
    assert active_conf["opacity"] == 0.50


def test_integration_flow_dynamic_reload(setup_config_file: Path) -> None:
    """Verifies check_and_reload identifies disk modifications and updates states."""
    cli = argparse.Namespace(
        theme=None,
        size=None,
        poll=None,
        opacity=None,
        no_topmost=False,
        config=str(setup_config_file),
    )
    mgr = ConfigManager(config_path=setup_config_file, cli_args=cli)
    mgr.load()

    assert mgr.get("opacity") == 0.50

    with open(setup_config_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["opacity"] = 0.95
    data["thresholds"]["conpty"]["yellow"] = 12.0
    data["thresholds"]["conpty"]["red"] = 15.0

    time.sleep(0.1)
    save_config(data, setup_config_file)

    reloaded = mgr.check_and_reload()
    assert reloaded is True
    assert mgr.get("opacity") == 0.95
    assert mgr.get("thresholds")["conpty"]["yellow"] == 12.0
    assert mgr.get("thresholds")["conpty"]["red"] == 15.0


def test_integration_flow_dynamic_reload_invalid(setup_config_file: Path) -> None:
    """Verifies that invalid configurations on disk do not crash the app and fall back."""
    mgr = ConfigManager(config_path=setup_config_file)
    mgr.load()

    original_opacity = mgr.get("opacity")

    time.sleep(0.1)
    with open(setup_config_file, "w", encoding="utf-8") as f:
        f.write("{invalid config contents")

    assert mgr.check_and_reload() is False
    assert mgr.get("opacity") == original_opacity

    invalid_data = get_default_config()
    invalid_data["opacity"] = "not a float"
    time.sleep(0.1)
    save_config(invalid_data, setup_config_file)

    assert mgr.check_and_reload() is False
    assert mgr.get("opacity") == original_opacity


def test_integration_flow_config_persistence(tmp_path: Path) -> None:
    """Verifies that position and size updates survive a save/reload cycle."""
    config_path = tmp_path / "config.json"
    mgr = ConfigManager(config_path=config_path)
    mgr.load()

    mgr.update_position_and_size(300, 400, 512)
    mgr.save()

    mgr2 = ConfigManager(config_path=config_path)
    loaded = mgr2.load()
    assert loaded["position"]["x"] == 300
    assert loaded["position"]["y"] == 400
    assert loaded["size"] == 512


def test_integration_flow_auto_create_defaults(tmp_path: Path) -> None:
    """Verifies that a missing config file is auto-created with defaults on first load."""
    config_path = tmp_path / "subdir" / "config.json"
    assert not config_path.exists()

    mgr = ConfigManager(config_path=config_path)
    loaded = mgr.load()

    assert config_path.exists()
    assert loaded == get_default_config()


def test_integration_flow_cli_poll_override(setup_config_file: Path) -> None:
    """Verifies that --poll CLI override correctly sets polling_interval_seconds."""
    cli = argparse.Namespace(
        theme=None,
        size=None,
        poll=5.0,
        opacity=None,
        no_topmost=False,
        config=str(setup_config_file),
    )
    mgr = ConfigManager(config_path=setup_config_file, cli_args=cli)
    active_conf = mgr.load()

    assert active_conf["polling_interval_seconds"] == 5.0


def test_integration_flow_cli_no_topmost_disables_always_on_top(setup_config_file: Path) -> None:
    """Verifies that --no-topmost CLI flag forces always_on_top to False."""
    cli = argparse.Namespace(
        theme=None,
        size=None,
        poll=None,
        opacity=None,
        no_topmost=True,
        config=str(setup_config_file),
    )
    mgr = ConfigManager(config_path=setup_config_file, cli_args=cli)
    active_conf = mgr.load()

    assert active_conf["always_on_top"] is False


def test_integration_flow_reload_preserves_cli_overrides(setup_config_file: Path) -> None:
    """Verifies CLI overrides are re-applied when check_and_reload merges new file content."""
    cli = argparse.Namespace(
        theme="cli-theme",
        size=None,
        poll=None,
        opacity=None,
        no_topmost=False,
        config=str(setup_config_file),
    )
    mgr = ConfigManager(config_path=setup_config_file, cli_args=cli)
    mgr.load()

    assert mgr.get("theme") == "cli-theme"

    updated = get_default_config()
    updated["theme"] = "file-theme"
    updated["opacity"] = 0.75
    time.sleep(0.1)
    save_config(updated, setup_config_file)

    reloaded = mgr.check_and_reload()
    assert reloaded is True
    assert mgr.get("theme") == "cli-theme"
    assert mgr.get("opacity") == 0.75


def test_integration_flow_no_reload_when_unchanged(setup_config_file: Path) -> None:
    """Verifies check_and_reload returns False when file has not changed."""
    mgr = ConfigManager(config_path=setup_config_file)
    mgr.load()

    result = mgr.check_and_reload()
    assert result is False


def test_integration_flow_negative_position_persists(tmp_path: Path) -> None:
    """Verifies that negative screen coordinates (multi-monitor) survive save/reload."""
    config_path = tmp_path / "config.json"
    mgr = ConfigManager(config_path=config_path)
    mgr.load()

    mgr.update_position_and_size(-1920, -200, 256)
    mgr.save()

    mgr2 = ConfigManager(config_path=config_path)
    loaded = mgr2.load()
    assert loaded["position"]["x"] == -1920
    assert loaded["position"]["y"] == -200