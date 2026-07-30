"""Unit tests for TrayManager system tray component.

Issue #5: always-on-top window with drag, minimize, and transparency (#5)
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PIL import Image

from boostgauge.tray import TrayManager, determine_tray_status, STATUS_COLORS


def make_tray(**kwargs) -> TrayManager:
    defaults = {
        "on_restore": MagicMock(),
        "on_quit": MagicMock(),
    }
    defaults.update(kwargs)
    return TrayManager(**defaults)


def test_t070_determine_tray_status_green() -> None:
    assert determine_tray_status(45.0) == "green"


def test_t070_determine_tray_status_yellow() -> None:
    assert determine_tray_status(75.0) == "yellow"


def test_t070_determine_tray_status_red() -> None:
    assert determine_tray_status(92.0) == "red"


def test_t070_determine_tray_status_at_warning_threshold() -> None:
    assert determine_tray_status(60.0) == "yellow"


def test_t070_determine_tray_status_at_danger_threshold() -> None:
    assert determine_tray_status(85.0) == "red"


def test_t070_determine_tray_status_below_zero() -> None:
    assert determine_tray_status(-10.0) == "green"


def test_t070_determine_tray_status_above_100() -> None:
    assert determine_tray_status(110.0) == "red"


def test_t070_determine_tray_status_custom_thresholds() -> None:
    assert determine_tray_status(50.0, warning_thresh=70.0, danger_thresh=90.0) == "green"
    assert determine_tray_status(80.0, warning_thresh=70.0, danger_thresh=90.0) == "yellow"
    assert determine_tray_status(95.0, warning_thresh=70.0, danger_thresh=90.0) == "red"


def test_t070_create_status_icon_green_size() -> None:
    tray = make_tray()
    img = tray.create_status_icon("green")
    assert img.size == (16, 16)


def test_t070_create_status_icon_green_mode() -> None:
    tray = make_tray()
    img = tray.create_status_icon("green")
    assert img.mode == "RGBA"


def test_t070_create_status_icon_green_center_pixel() -> None:
    tray = make_tray()
    img = tray.create_status_icon("green")
    assert img.getpixel((8, 8)) == STATUS_COLORS["green"]


def test_t070_create_status_icon_yellow_center_pixel() -> None:
    tray = make_tray()
    img = tray.create_status_icon("yellow")
    assert img.getpixel((8, 8)) == STATUS_COLORS["yellow"]


def test_t070_create_status_icon_red_center_pixel() -> None:
    tray = make_tray()
    img = tray.create_status_icon("red")
    assert img.getpixel((8, 8)) == STATUS_COLORS["red"]


def test_t070_create_status_icon_invalid_status_defaults_green() -> None:
    tray = make_tray()
    img = tray.create_status_icon("invalid")  # type: ignore[arg-type]
    assert img.getpixel((8, 8)) == STATUS_COLORS["green"]


def test_t070_create_status_icon_returns_pil_image() -> None:
    tray = make_tray()
    img = tray.create_status_icon("red")
    assert isinstance(img, Image.Image)


def test_t090_tray_callbacks_on_restore_invoked() -> None:
    on_restore = MagicMock()
    tray = make_tray(on_restore=on_restore)
    tray.on_restore()
    on_restore.assert_called_once()


def test_t090_tray_callbacks_on_quit_invoked() -> None:
    on_quit = MagicMock()
    tray = make_tray(on_quit=on_quit)
    tray.on_quit()
    on_quit.assert_called_once()


def test_t090_tray_callbacks_on_reset_telltales_invoked() -> None:
    on_reset = MagicMock()
    tray = make_tray(on_reset_telltales=on_reset)
    tray.on_reset_telltales()
    on_reset.assert_called_once()


def test_t090_tray_callbacks_on_toggle_topmost_invoked() -> None:
    on_toggle = MagicMock()
    tray = make_tray(on_toggle_topmost=on_toggle)
    tray.on_toggle_topmost()
    on_toggle.assert_called_once()


def test_safe_invoke_with_none_does_not_raise() -> None:
    tray = make_tray()
    tray._safe_invoke(None)


def test_safe_invoke_calls_callback() -> None:
    tray = make_tray()
    callback = MagicMock()
    tray._safe_invoke(callback)
    callback.assert_called_once()


def test_update_status_changes_current_status() -> None:
    tray = make_tray()
    assert tray.current_status == "green"
    tray.update_status("red")
    assert tray.current_status == "red"


def test_update_status_updates_icon_image() -> None:
    tray = make_tray()
    tray.update_status("yellow")
    assert tray.icon.icon.getpixel((8, 8)) == STATUS_COLORS["yellow"]


def test_update_status_to_red_updates_icon() -> None:
    tray = make_tray()
    tray.update_status("red")
    assert tray.icon.icon.getpixel((8, 8)) == STATUS_COLORS["red"]


def test_initial_tray_status_is_green() -> None:
    tray = make_tray()
    assert tray.current_status == "green"
    assert tray.icon.icon.getpixel((8, 8)) == STATUS_COLORS["green"]


def test_tray_optional_callbacks_none_by_default() -> None:
    on_restore = MagicMock()
    on_quit = MagicMock()
    tray = TrayManager(on_restore=on_restore, on_quit=on_quit)
    assert tray.on_reset_telltales is None
    assert tray.on_toggle_topmost is None


def test_stop_does_not_raise() -> None:
    tray = make_tray()
    tray.stop()


def test_start_sets_thread() -> None:
    tray = make_tray()
    assert tray._thread is None
    tray.start()
    assert tray._thread is not None
    assert tray._thread.is_alive()
    tray.stop()


def test_start_idempotent_when_already_running() -> None:
    tray = make_tray()
    tray.start()
    thread_before = tray._thread
    tray.start()
    assert tray._thread is thread_before
    tray.stop()


def test_status_colors_values() -> None:
    assert STATUS_COLORS["green"] == (46, 204, 113, 255)
    assert STATUS_COLORS["yellow"] == (241, 196, 15, 255)
    assert STATUS_COLORS["red"] == (231, 76, 60, 255)


def test_determine_tray_status_boundary_just_below_warning() -> None:
    assert determine_tray_status(59.9) == "green"


def test_determine_tray_status_boundary_just_below_danger() -> None:
    assert determine_tray_status(84.9) == "yellow"


def test_tray_manager_icon_title() -> None:
    tray = make_tray()
    assert tray.icon.title == "BoostGauge Monitor"


def test_tray_manager_icon_name() -> None:
    tray = make_tray()
    assert tray.icon.name == "boostgauge"