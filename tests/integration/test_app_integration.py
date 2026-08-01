"""Integration tests verifying component wiring, event queue polling, and configuration persistence round-trips.

Issue #5: Feature: always-on-top window with drag, minimize, and transparency
"""

import queue
from pathlib import Path

import pytest

from boostgauge.app import BoostGaugeApp
from boostgauge.config import WindowConfig, WindowConfigDict, VirtualScreenBounds


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Redirect default config path to tmp_path for each test to prevent cross-test state pollution."""
    config_path = tmp_path / "boostgauge_isolated" / "config.json"
    monkeypatch.setattr(
        "boostgauge.config.get_default_config_path",
        lambda: config_path,
    )
    yield config_path


def test_t100_app_tray_event_queue_processing(tmp_path):
    """T100: App polls tray event queue and updates state machine correctly."""
    app = BoostGaugeApp(root=None)
    assert app.controller.topmost is True

    app.event_queue.put({"event_type": "toggle_topmost", "payload": None})
    app.poll_event_queue()

    assert app.controller.topmost is False

    app.event_queue.put({"event_type": "reset", "payload": None})
    app.poll_event_queue()

    assert app.controller.x == 100
    assert app.controller.y == 100
    assert app.controller.size == 256


def test_t100_app_restore_event_no_window():
    """T100: Restore event with no window does not raise."""
    app = BoostGaugeApp(root=None)
    app.event_queue.put({"event_type": "restore", "payload": None})
    app.poll_event_queue()


def test_t100_app_quit_event_no_root():
    """T100: Quit event with no root does not raise."""
    app = BoostGaugeApp(root=None)
    app.event_queue.put({"event_type": "quit", "payload": None})
    app.poll_event_queue()


def test_t100_app_multiple_events_processed_in_order():
    """T100: Multiple queued events are all processed in one poll cycle."""
    app = BoostGaugeApp(root=None)
    app.event_queue.put({"event_type": "toggle_topmost", "payload": None})
    app.event_queue.put({"event_type": "toggle_topmost", "payload": None})
    app.poll_event_queue()

    assert app.controller.topmost is True


def test_t100_empty_queue_poll_does_not_raise():
    """T100: Polling an empty queue is a no-op without raising."""
    app = BoostGaugeApp(root=None)
    app.poll_event_queue()


def test_t110_config_round_trip(tmp_path):
    """T110: WindowConfig saves and reloads WindowConfigDict without data loss."""
    cfg_path = tmp_path / "config.json"
    wc = WindowConfig(config_path=cfg_path)

    updated: WindowConfigDict = {
        "x": 400,
        "y": 500,
        "size": 320,
        "topmost": False,
        "opacity": 0.9,
        "compact_mode": True,
    }
    wc.save(updated)
    restored = wc.load()

    assert restored["x"] == 400
    assert restored["y"] == 500
    assert restored["size"] == 320
    assert restored["topmost"] is False
    assert restored["opacity"] == pytest.approx(0.9)
    assert restored["compact_mode"] is True


def test_t110_config_load_defaults_when_missing(tmp_path):
    """T110: WindowConfig.load() returns safe defaults when file is absent."""
    cfg_path = tmp_path / "nonexistent" / "config.json"
    wc = WindowConfig(config_path=cfg_path)
    config = wc.load()

    assert config["size"] == 256
    assert config["topmost"] is True
    assert config["x"] == 100
    assert config["y"] == 100
    assert config["opacity"] == 1.0
    assert config["compact_mode"] is False


def test_t120_bounds_clamping_offscreen_right_bottom(tmp_path):
    """T120: validate_bounds clamps x=9999, y=9999 within 1920x1080 screen."""
    wc = WindowConfig(config_path=tmp_path / "cfg.json")
    bounds: VirtualScreenBounds = {"min_x": 0, "min_y": 0, "max_x": 1920, "max_y": 1080}
    config: WindowConfigDict = {
        "x": 9999,
        "y": 9999,
        "size": 256,
        "topmost": True,
        "opacity": 1.0,
        "compact_mode": False,
    }
    clamped = wc.validate_bounds(config, bounds)
    assert clamped["x"] == 1664
    assert clamped["y"] == 824


def test_t120_bounds_clamping_offscreen_left_top(tmp_path):
    """T120: validate_bounds clamps negative x/y to min_x/min_y."""
    wc = WindowConfig(config_path=tmp_path / "cfg.json")
    bounds: VirtualScreenBounds = {"min_x": 0, "min_y": 0, "max_x": 1920, "max_y": 1080}
    config: WindowConfigDict = {
        "x": -500,
        "y": -200,
        "size": 256,
        "topmost": True,
        "opacity": 1.0,
        "compact_mode": False,
    }
    clamped = wc.validate_bounds(config, bounds)
    assert clamped["x"] == 0
    assert clamped["y"] == 0


def test_t120_bounds_clamping_preserves_other_fields(tmp_path):
    """T120: validate_bounds does not mutate non-coordinate fields."""
    wc = WindowConfig(config_path=tmp_path / "cfg.json")
    bounds: VirtualScreenBounds = {"min_x": 0, "min_y": 0, "max_x": 1920, "max_y": 1080}
    config: WindowConfigDict = {
        "x": 2500,
        "y": 1500,
        "size": 256,
        "topmost": False,
        "opacity": 0.75,
        "compact_mode": True,
    }
    clamped = wc.validate_bounds(config, bounds)
    assert clamped["size"] == 256
    assert clamped["topmost"] is False
    assert clamped["opacity"] == pytest.approx(0.75)
    assert clamped["compact_mode"] is True


def test_app_controller_initialized_from_config():
    """App controller state reflects values loaded from config."""
    app = BoostGaugeApp(root=None)
    assert app.controller.size == 256
    assert isinstance(app.controller.topmost, bool)
    assert isinstance(app.controller.opacity, float)


def test_app_event_queue_is_queue_instance():
    """App event_queue is a thread-safe Queue instance."""
    app = BoostGaugeApp(root=None)
    assert isinstance(app.event_queue, queue.Queue)


def test_app_tray_controller_wired_to_event_queue():
    """App tray controller shares the same event_queue as the app."""
    app = BoostGaugeApp(root=None)
    assert app.tray.event_queue is app.event_queue


def test_app_config_manager_is_window_config():
    """App config_manager is a WindowConfig instance."""
    app = BoostGaugeApp(root=None)
    assert isinstance(app.config_manager, WindowConfig)


def test_app_reset_event_resets_geometry():
    """Reset event sets controller position to (100, 100) and size to 256."""
    app = BoostGaugeApp(root=None)
    app.controller.x = 999
    app.controller.y = 888
    app.controller.size = 512

    app.event_queue.put({"event_type": "reset", "payload": None})
    app.poll_event_queue()

    assert app.controller.x == 100
    assert app.controller.y == 100
    assert app.controller.size == 256


def test_app_toggle_topmost_twice_restores_original():
    """Two toggle_topmost events restore original topmost state."""
    app = BoostGaugeApp(root=None)
    original = app.controller.topmost

    app.event_queue.put({"event_type": "toggle_topmost", "payload": None})
    app.event_queue.put({"event_type": "toggle_topmost", "payload": None})
    app.poll_event_queue()

    assert app.controller.topmost is original


def test_config_persistence_after_reset_event(tmp_path):
    """Reset event triggers config save with reset geometry values."""
    cfg_path = tmp_path / "config.json"
    app = BoostGaugeApp(root=None)
    app.config_manager = WindowConfig(config_path=cfg_path)

    app.event_queue.put({"event_type": "reset", "payload": None})
    app.poll_event_queue()

    reloaded = app.config_manager.load()
    assert reloaded["x"] == 100
    assert reloaded["y"] == 100
    assert reloaded["size"] == 256


def test_config_persistence_after_toggle_topmost(tmp_path):
    """Toggle topmost event triggers config save with updated topmost state."""
    cfg_path = tmp_path / "config.json"
    app = BoostGaugeApp(root=None)
    app.config_manager = WindowConfig(config_path=cfg_path)
    original_topmost = app.controller.topmost

    app.event_queue.put({"event_type": "toggle_topmost", "payload": None})
    app.poll_event_queue()

    reloaded = app.config_manager.load()
    assert reloaded["topmost"] is (not original_topmost)


def test_window_config_save_and_load_multiple_times(tmp_path):
    """Multiple save/load cycles preserve most-recently-saved values."""
    cfg_path = tmp_path / "config.json"
    wc = WindowConfig(config_path=cfg_path)

    first: WindowConfigDict = {
        "x": 100, "y": 200, "size": 256,
        "topmost": True, "opacity": 1.0, "compact_mode": False,
    }
    wc.save(first)

    second: WindowConfigDict = {
        "x": 300, "y": 400, "size": 384,
        "topmost": False, "opacity": 0.8, "compact_mode": True,
    }
    wc.save(second)
    result = wc.load()

    assert result["x"] == 300
    assert result["y"] == 400
    assert result["size"] == 384
    assert result["topmost"] is False
    assert result["opacity"] == pytest.approx(0.8)
    assert result["compact_mode"] is True


def test_shutdown_does_not_raise():
    """App shutdown with no running tray does not raise."""
    app = BoostGaugeApp(root=None)
    app.shutdown()