"""Headless unit tests for tray icon state generation and event queue dispatching.

Issue #5: Feature: always-on-top window with drag, minimize, and transparency
"""

import queue
import pytest
from PIL import Image
from boostgauge.tray import TrayController, STATUS_COLORS


@pytest.fixture
def tray() -> TrayController:
    return TrayController(queue.Queue())


def test_t080_status_icon_image_generation(tray: TrayController):
    """T080: Generates valid 64x64 PIL status dot image with RGBA mode."""
    img = tray.create_status_icon_image("green", size=64)
    assert isinstance(img, Image.Image)
    assert img.size == (64, 64)
    assert img.mode == "RGBA"


def test_t080_green_center_pixel_dominates(tray: TrayController):
    """T080: Green status dot has green channel dominant at center."""
    img = tray.create_status_icon_image("green", size=64)
    r, g, b, a = img.getpixel((32, 32))
    assert g > r and g > b
    assert a > 0


def test_t080_yellow_center_pixel(tray: TrayController):
    """T080: Yellow status dot has red and green channels dominant at center."""
    img = tray.create_status_icon_image("yellow", size=64)
    r, g, b, a = img.getpixel((32, 32))
    assert r > b and g > b
    assert a > 0


def test_t080_red_center_pixel(tray: TrayController):
    """T080: Red status dot has red channel dominant at center."""
    img = tray.create_status_icon_image("red", size=64)
    r, g, b, a = img.getpixel((32, 32))
    assert r > g and r > b
    assert a > 0


def test_t080_invalid_color_defaults_to_green(tray: TrayController):
    """T080: Invalid color_name defaults to green dot."""
    img = tray.create_status_icon_image("blue", size=64)
    assert isinstance(img, Image.Image)
    assert img.size == (64, 64)
    assert img.mode == "RGBA"
    r, g, b, a = img.getpixel((32, 32))
    assert g > r and g > b


def test_t080_corner_pixels_transparent(tray: TrayController):
    """T080: Corner pixels outside circle are transparent."""
    img = tray.create_status_icon_image("green", size=64)
    _, _, _, corner_alpha = img.getpixel((0, 0))
    assert corner_alpha == 0


def test_t080_custom_size(tray: TrayController):
    """T080: Custom size parameter produces correct image dimensions."""
    img = tray.create_status_icon_image("green", size=32)
    assert img.size == (32, 32)


def test_t080_status_colors_constant():
    """T080: STATUS_COLORS contains expected color keys."""
    assert "green" in STATUS_COLORS
    assert "yellow" in STATUS_COLORS
    assert "red" in STATUS_COLORS
    for key, rgba in STATUS_COLORS.items():
        assert len(rgba) == 4
        assert all(0 <= v <= 255 for v in rgba)


def test_t090_restore_click_enqueues_event(tray: TrayController):
    """T090: _on_restore_click puts restore event into queue."""
    tray._on_restore_click(None, None)
    event = tray.event_queue.get_nowait()
    assert event["event_type"] == "restore"
    assert event["payload"] is None


def test_t090_toggle_topmost_click_enqueues_event(tray: TrayController):
    """T090: _on_toggle_topmost_click puts toggle_topmost event into queue."""
    tray._on_toggle_topmost_click(None, None)
    event = tray.event_queue.get_nowait()
    assert event["event_type"] == "toggle_topmost"
    assert event["payload"] is None


def test_t090_reset_click_enqueues_event(tray: TrayController):
    """T090: _on_reset_click puts reset event into queue."""
    tray._on_reset_click(None, None)
    event = tray.event_queue.get_nowait()
    assert event["event_type"] == "reset"
    assert event["payload"] is None


def test_t090_quit_click_enqueues_event():
    """T090: _on_quit_click puts quit event into queue."""
    q = queue.Queue()
    tray = TrayController(q)
    tray._on_quit_click(None, None)
    event = q.get_nowait()
    assert event["event_type"] == "quit"
    assert event["payload"] is None


def test_t090_multiple_events_ordered(tray: TrayController):
    """T090: Multiple callback events are queued in order."""
    tray._on_restore_click(None, None)
    tray._on_toggle_topmost_click(None, None)
    tray._on_reset_click(None, None)

    assert tray.event_queue.get_nowait()["event_type"] == "restore"
    assert tray.event_queue.get_nowait()["event_type"] == "toggle_topmost"
    assert tray.event_queue.get_nowait()["event_type"] == "reset"


def test_tray_controller_initial_state():
    """TrayController initializes with no icon and default green color."""
    q = queue.Queue()
    tray = TrayController(q)
    assert tray.icon is None
    assert tray.thread is None
    assert tray._current_color == "green"
    assert tray.event_queue is q


def test_update_status_changes_current_color(tray: TrayController):
    """update_status changes the internal current color tracking."""
    tray.update_status("red", "Critical")
    assert tray._current_color == "red"


def test_update_status_with_no_icon_does_not_raise(tray: TrayController):
    """update_status with no active icon does not raise an exception."""
    assert tray.icon is None
    tray.update_status("yellow", "Warning")
    assert tray._current_color == "yellow"


def test_stop_with_no_icon_does_not_raise(tray: TrayController):
    """stop() with no active icon does not raise an exception."""
    assert tray.icon is None
    tray.stop()
    assert tray.icon is None


def test_event_queue_is_thread_safe():
    """TrayController event_queue is a Queue instance supporting thread-safe ops."""
    q = queue.Queue()
    tray = TrayController(q)
    assert isinstance(tray.event_queue, queue.Queue)
    tray._on_restore_click(None, None)
    assert not tray.event_queue.empty()
    event = tray.event_queue.get_nowait()
    assert event["event_type"] == "restore"
    assert tray.event_queue.empty()