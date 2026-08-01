"""Headless unit tests for GaugeWindow state math, geometry persistence, screen boundary clamping, and event handlers.

Issue #5: Always-on-top window with drag, minimize, and transparency.
"""

from __future__ import annotations

from typing import Dict
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image as PILImage

from boostgauge.window import GaugeWindow


def test_topmost_attribute_toggle() -> None:
    """T010: Topmost attribute configuration and toggle."""
    win = GaugeWindow(config={"topmost": True})
    assert win.topmost is True

    new_state = win.toggle_topmost()
    assert new_state is False
    assert win.topmost is False

    restored = win.toggle_topmost()
    assert restored is True
    assert win.topmost is True


def test_toggle_topmost_with_root() -> None:
    """Toggle topmost propagates to root when root is set."""
    win = GaugeWindow(config={"topmost": True})
    mock_root = MagicMock()
    win.root = mock_root

    result = win.toggle_topmost()
    assert result is False
    mock_root.attributes.assert_called_once_with("-topmost", False)


def test_toggle_topmost_headless_no_root() -> None:
    """Toggle topmost works cleanly without root (headless mode)."""
    win = GaugeWindow(config={"topmost": False})
    assert win.root is None

    result = win.toggle_topmost()
    assert result is True
    assert win.topmost is True


def test_drag_motion_coordinate_calculation() -> None:
    """T020: Drag motion coordinate delta calculation."""
    win = GaugeWindow(config={"x": 100, "y": 100, "size": 256})
    win.handle_drag_start(event_x=50, event_y=30)

    new_x, new_y = win.handle_drag_motion(
        root_x=500, root_y=300, virtual_screen=(0, 0, 1920, 1080)
    )
    assert new_x == 450
    assert new_y == 270


def test_drag_motion_updates_internal_state() -> None:
    """handle_drag_motion updates self.x and self.y."""
    win = GaugeWindow(config={"x": 0, "y": 0, "size": 256})
    win.handle_drag_start(event_x=10, event_y=20)
    win.handle_drag_motion(root_x=110, root_y=120, virtual_screen=(0, 0, 1920, 1080))

    assert win.x == 100
    assert win.y == 100


def test_drag_motion_clamped_out_of_bounds() -> None:
    """Dragging to extreme coordinates clamps to screen bounds."""
    win = GaugeWindow(config={"size": 256})
    win.handle_drag_start(event_x=0, event_y=0)

    cx, cy = win.handle_drag_motion(root_x=5000, root_y=5000, virtual_screen=(0, 0, 1920, 1080))
    assert cx == 1664
    assert cy == 824


def test_handle_drag_start_sets_offsets() -> None:
    """handle_drag_start stores offset and sets is_dragging."""
    win = GaugeWindow()
    win.handle_drag_start(event_x=42, event_y=17)

    assert win.drag_offset_x == 42
    assert win.drag_offset_y == 17
    assert win.is_dragging is True


def test_double_click_toggle_compact_expanded() -> None:
    """T030: Double-click mode toggle compact/expanded (128px <-> 256px)."""
    win = GaugeWindow(config={"size": 256})
    new_size = win.toggle_compact_expanded()
    assert new_size == 128
    assert win.size == 128

    restored_size = win.toggle_compact_expanded()
    assert restored_size == 256
    assert win.size == 256


def test_toggle_compact_expanded_from_non_256() -> None:
    """Any size other than 256 toggles to 256."""
    win = GaugeWindow(config={"size": 128})
    result = win.toggle_compact_expanded()
    assert result == 256

    win2 = GaugeWindow(config={"size": 300})
    result2 = win2.toggle_compact_expanded()
    assert result2 == 256


def test_chroma_key_transparency_constant() -> None:
    """T040: Window chroma-key transparency setup constant."""
    win = GaugeWindow()
    assert win.CHROMA_KEY_BG == "#000001"


def test_default_config_values() -> None:
    """Default config initializes with expected fallback values."""
    win = GaugeWindow()
    assert win.x == 100
    assert win.y == 100
    assert win.size == 256
    assert win.topmost is True
    assert win.opacity == 1.0
    assert win.hover_opacity == 1.0


def test_config_values_applied() -> None:
    """Explicit config values override defaults."""
    win = GaugeWindow(config={"x": 50, "y": 75, "size": 128, "topmost": False, "opacity": 0.7, "hover_opacity": 0.9})
    assert win.x == 50
    assert win.y == 75
    assert win.size == 128
    assert win.topmost is False
    assert win.opacity == pytest.approx(0.7)
    assert win.hover_opacity == pytest.approx(0.9)


def test_hover_opacity_transition_calculation() -> None:
    """T050: Hover opacity transition value bounded setup."""
    win = GaugeWindow(config={"opacity": 0.8, "hover_opacity": 1.0})
    assert win.opacity == pytest.approx(0.8)
    assert win.hover_opacity == pytest.approx(1.0)

    win.set_opacity(0.5)
    assert win.opacity == pytest.approx(0.5)

    win.set_opacity(-0.5)
    assert win.opacity == pytest.approx(0.1)

    win.set_opacity(1.5)
    assert win.opacity == pytest.approx(1.0)


def test_set_opacity_with_root() -> None:
    """set_opacity propagates alpha to root when set."""
    win = GaugeWindow(config={"opacity": 1.0})
    mock_root = MagicMock()
    win.root = mock_root

    win.set_opacity(0.6)
    mock_root.attributes.assert_called_once_with("-alpha", pytest.approx(0.6))


def test_set_opacity_root_exception_suppressed() -> None:
    """set_opacity does not propagate exception from root.attributes."""
    win = GaugeWindow()
    mock_root = MagicMock()
    mock_root.attributes.side_effect = Exception("alpha not supported")
    win.root = mock_root

    win.set_opacity(0.5)
    assert win.opacity == pytest.approx(0.5)


def test_screen_bounds_clamping_upper_right() -> None:
    """T080: Clamping upper-right out-of-bounds position."""
    win = GaugeWindow(config={"size": 256})
    virtual_screen = (0, 0, 1920, 1080)

    cx, cy = win.clamp_to_screen_bounds(2000, 2000, 256, 256, virtual_screen)
    assert cx == 1664
    assert cy == 824


def test_screen_bounds_clamping_negative_coords() -> None:
    """T080: Clamping lower-left out-of-bounds (negative) position."""
    win = GaugeWindow(config={"size": 256})
    virtual_screen = (0, 0, 1920, 1080)

    cx, cy = win.clamp_to_screen_bounds(-100, -100, 256, 256, virtual_screen)
    assert cx == 0
    assert cy == 0


def test_screen_bounds_clamping_within_bounds() -> None:
    """Position already within bounds is returned unchanged."""
    win = GaugeWindow()
    cx, cy = win.clamp_to_screen_bounds(100, 200, 256, 256, (0, 0, 1920, 1080))
    assert cx == 100
    assert cy == 200


def test_screen_bounds_non_zero_origin() -> None:
    """Virtual screen with non-zero origin clamps correctly."""
    win = GaugeWindow()
    cx, cy = win.clamp_to_screen_bounds(-100, -100, 256, 256, (200, 150, 2120, 1230))
    assert cx == 200
    assert cy == 150


def test_screen_bounds_window_larger_than_display() -> None:
    """Window larger than display clamps position to virtual origin."""
    win = GaugeWindow()
    cx, cy = win.clamp_to_screen_bounds(100, 100, 2000, 2000, (0, 0, 1920, 1080))
    assert cx == 0
    assert cy == 0


def test_mouse_wheel_resize_scroll_up() -> None:
    """T090: Mouse wheel scroll up increments size by 16px."""
    win = GaugeWindow(config={"size": 256})
    new_size = win.handle_wheel_resize(120)
    assert new_size == 272


def test_mouse_wheel_resize_scroll_down() -> None:
    """T090: Mouse wheel scroll down decrements size by 16px."""
    win = GaugeWindow(config={"size": 256})
    new_size = win.handle_wheel_resize(-120)
    assert new_size == 240


def test_mouse_wheel_resize_max_bound() -> None:
    """Scrolling up beyond 512px clamps to max."""
    win = GaugeWindow(config={"size": 512})
    new_size = win.handle_wheel_resize(120)
    assert new_size == 512


def test_mouse_wheel_resize_min_bound() -> None:
    """Scrolling down beyond 64px clamps to min."""
    win = GaugeWindow(config={"size": 64})
    new_size = win.handle_wheel_resize(-120)
    assert new_size == 64


def test_mouse_wheel_resize_triggers_callback() -> None:
    """handle_wheel_resize fires on_geometry_change callback."""
    calls: list = []
    win = GaugeWindow(config={"size": 256}, on_geometry_change=lambda x, y, s: calls.append((x, y, s)))
    win.handle_wheel_resize(120)
    assert len(calls) == 1
    assert calls[0][2] == 272


def test_geometry_callback_triggering() -> None:
    """T100: Config save callback integration for window geometry."""
    saved_state: Dict[str, int] = {}

    def mock_callback(x: int, y: int, size: int) -> None:
        saved_state["x"] = x
        saved_state["y"] = y
        saved_state["size"] = size

    win = GaugeWindow(
        config={"x": 100, "y": 100, "size": 256},
        on_geometry_change=mock_callback,
    )
    win.toggle_compact_expanded()
    assert saved_state == {"x": 100, "y": 100, "size": 128}


def test_offscreen_position_fallback_recovery() -> None:
    """T110: Off-screen position fallback recovery math."""
    win = GaugeWindow(config={"x": -5000, "y": -5000, "size": 256})
    cx, cy = win.clamp_to_screen_bounds(win.x, win.y, win.size, win.size, (0, 0, 1920, 1080))
    assert cx == 0
    assert cy == 0


def test_on_button_press_sets_drag_state() -> None:
    """_on_button_press delegates to handle_drag_start."""
    win = GaugeWindow()
    event = MagicMock()
    event.x = 25
    event.y = 35

    win._on_button_press(event)
    assert win.drag_offset_x == 25
    assert win.drag_offset_y == 35
    assert win.is_dragging is True


def test_on_button_release_fires_callback() -> None:
    """_on_button_release triggers on_geometry_change when dragging."""
    calls: list = []
    win = GaugeWindow(
        config={"x": 50, "y": 60, "size": 256},
        on_geometry_change=lambda x, y, s: calls.append((x, y, s)),
    )
    win.is_dragging = True

    event = MagicMock()
    win._on_button_release(event)

    assert win.is_dragging is False
    assert len(calls) == 1
    assert calls[0] == (50, 60, 256)


def test_on_button_release_no_callback_when_not_dragging() -> None:
    """_on_button_release does nothing when is_dragging is False."""
    calls: list = []
    win = GaugeWindow(on_geometry_change=lambda x, y, s: calls.append((x, y, s)))
    win.is_dragging = False

    event = MagicMock()
    win._on_button_release(event)
    assert len(calls) == 0


def test_on_double_click_toggles_size() -> None:
    """_on_double_click calls toggle_compact_expanded."""
    win = GaugeWindow(config={"size": 256})
    event = MagicMock()
    win._on_double_click(event)
    assert win.size == 128


def test_on_mouse_wheel_zero_delta_ignored() -> None:
    """_on_mouse_wheel with delta=0 does not resize."""
    win = GaugeWindow(config={"size": 256})
    event = MagicMock()
    event.delta = 0
    win._on_mouse_wheel(event)
    assert win.size == 256


def test_on_mouse_wheel_positive_delta() -> None:
    """_on_mouse_wheel with positive delta resizes up."""
    win = GaugeWindow(config={"size": 256})
    event = MagicMock()
    event.delta = 120
    win._on_mouse_wheel(event)
    assert win.size == 272


def test_on_mouse_enter_applies_hover_opacity() -> None:
    """_on_mouse_enter sets hover opacity on root when values differ."""
    win = GaugeWindow(config={"opacity": 0.7, "hover_opacity": 1.0})
    mock_root = MagicMock()
    win.root = mock_root

    event = MagicMock()
    win._on_mouse_enter(event)
    mock_root.attributes.assert_called_once_with("-alpha", pytest.approx(1.0))


def test_on_mouse_enter_no_change_when_same_opacity() -> None:
    """_on_mouse_enter does nothing when hover_opacity equals opacity."""
    win = GaugeWindow(config={"opacity": 1.0, "hover_opacity": 1.0})
    mock_root = MagicMock()
    win.root = mock_root

    event = MagicMock()
    win._on_mouse_enter(event)
    mock_root.attributes.assert_not_called()


def test_on_mouse_leave_restores_opacity() -> None:
    """_on_mouse_leave restores base opacity on root when values differ."""
    win = GaugeWindow(config={"opacity": 0.7, "hover_opacity": 1.0})
    mock_root = MagicMock()
    win.root = mock_root

    event = MagicMock()
    win._on_mouse_leave(event)
    mock_root.attributes.assert_called_once_with("-alpha", pytest.approx(0.7))


def test_on_mouse_leave_suppresses_exception() -> None:
    """_on_mouse_leave does not propagate root.attributes exception."""
    win = GaugeWindow(config={"opacity": 0.7, "hover_opacity": 1.0})
    mock_root = MagicMock()
    mock_root.attributes.side_effect = Exception("boom")
    win.root = mock_root

    event = MagicMock()
    win._on_mouse_leave(event)


def test_on_mouse_enter_suppresses_exception() -> None:
    """_on_mouse_enter does not propagate root.attributes exception."""
    win = GaugeWindow(config={"opacity": 0.7, "hover_opacity": 1.0})
    mock_root = MagicMock()
    mock_root.attributes.side_effect = Exception("boom")
    win.root = mock_root

    event = MagicMock()
    win._on_mouse_enter(event)


def test_on_drag_motion_skipped_when_not_dragging() -> None:
    """_on_drag_motion does nothing when is_dragging is False."""
    win = GaugeWindow(config={"x": 100, "y": 100, "size": 256})
    win.is_dragging = False
    mock_root = MagicMock()
    win.root = mock_root

    event = MagicMock()
    event.x_root = 500
    event.y_root = 400
    win._on_drag_motion(event)

    mock_root.geometry.assert_not_called()
    assert win.x == 100
    assert win.y == 100


def test_on_drag_motion_updates_geometry() -> None:
    """_on_drag_motion updates root geometry when dragging."""
    win = GaugeWindow(config={"x": 100, "y": 100, "size": 256})
    win.is_dragging = True
    win.drag_offset_x = 10
    win.drag_offset_y = 10
    mock_root = MagicMock()
    mock_root.winfo_screenwidth.return_value = 1920
    mock_root.winfo_screenheight.return_value = 1080
    win.root = mock_root

    event = MagicMock()
    event.x_root = 210
    event.y_root = 310
    win._on_drag_motion(event)

    mock_root.geometry.assert_called_once_with("256x256+200+300")


def test_on_right_click_is_noop() -> None:
    """_on_right_click placeholder does not raise."""
    win = GaugeWindow()
    event = MagicMock()
    win._on_right_click(event)


def test_update_image_noop_without_root() -> None:
    """update_image does nothing when root is None."""
    win = GaugeWindow()
    img = PILImage.new("RGBA", (256, 256), (0, 0, 0, 255))
    win.update_image(img)
    assert win.photo_image is None


def test_apply_geometry_noop_without_root() -> None:
    """_apply_geometry does not raise when root and canvas are None."""
    win = GaugeWindow(config={"x": 50, "y": 50, "size": 128})
    win._apply_geometry()


def test_apply_geometry_updates_root_and_canvas() -> None:
    """_apply_geometry calls root.geometry and canvas.config."""
    win = GaugeWindow(config={"x": 50, "y": 75, "size": 128})
    mock_root = MagicMock()
    mock_canvas = MagicMock()
    win.root = mock_root
    win.canvas = mock_canvas

    win._apply_geometry()
    mock_root.geometry.assert_called_once_with("128x128+50+75")
    mock_canvas.config.assert_called_once_with(width=128, height=128)


def test_get_virtual_screen_bounds_without_root() -> None:
    """_get_virtual_screen_bounds returns fallback when root is None."""
    win = GaugeWindow()
    bounds = win._get_virtual_screen_bounds()
    assert bounds == (0, 0, 1920, 1080)


def test_get_virtual_screen_bounds_with_root() -> None:
    """_get_virtual_screen_bounds reads from root winfo methods."""
    win = GaugeWindow()
    mock_root = MagicMock()
    mock_root.winfo_screenwidth.return_value = 2560
    mock_root.winfo_screenheight.return_value = 1440
    win.root = mock_root

    bounds = win._get_virtual_screen_bounds()
    assert bounds == (0, 0, 2560, 1440)


def test_get_virtual_screen_bounds_exception_fallback() -> None:
    """_get_virtual_screen_bounds falls back on root exception."""
    win = GaugeWindow()
    mock_root = MagicMock()
    mock_root.winfo_screenwidth.side_effect = Exception("display error")
    win.root = mock_root

    bounds = win._get_virtual_screen_bounds()
    assert bounds == (0, 0, 1920, 1080)


def test_on_mouse_enter_no_root_is_noop() -> None:
    """_on_mouse_enter does nothing when root is None."""
    win = GaugeWindow(config={"opacity": 0.5, "hover_opacity": 1.0})
    event = MagicMock()
    win._on_mouse_enter(event)


def test_on_mouse_leave_no_root_is_noop() -> None:
    """_on_mouse_leave does nothing when root is None."""
    win = GaugeWindow(config={"opacity": 0.5, "hover_opacity": 1.0})
    event = MagicMock()
    win._on_mouse_leave(event)


def test_toggle_compact_expanded_calls_apply_geometry() -> None:
    """toggle_compact_expanded applies geometry via root."""
    win = GaugeWindow(config={"size": 256})
    mock_root = MagicMock()
    mock_canvas = MagicMock()
    win.root = mock_root
    win.canvas = mock_canvas

    win.toggle_compact_expanded()
    mock_root.geometry.assert_called_once_with("128x128+100+100")


def test_size_constants() -> None:
    """Class-level size constants match spec."""
    assert GaugeWindow.MIN_SIZE == 64
    assert GaugeWindow.MAX_SIZE == 512
    assert GaugeWindow.COMPACT_SIZE == 128
    assert GaugeWindow.EXPANDED_SIZE == 256
    assert GaugeWindow.RESIZE_STEP == 16


def test_initial_drag_state() -> None:
    """Drag state is initialized to not-dragging."""
    win = GaugeWindow()
    assert win.is_dragging is False
    assert win.drag_offset_x == 0
    assert win.drag_offset_y == 0


def test_on_mouse_wheel_missing_delta_attribute() -> None:
    """_on_mouse_wheel handles event with no delta attribute."""
    win = GaugeWindow(config={"size": 256})
    event = MagicMock(spec=[])
    win._on_mouse_wheel(event)
    assert win.size == 256


def test_setup_window_configures_root() -> None:
    """setup_window assigns root, creates canvas, and binds all mouse events."""
    win = GaugeWindow(config={"x": 10, "y": 20, "size": 256, "opacity": 1.0})
    mock_root = MagicMock()
    mock_canvas = MagicMock()

    with patch("tkinter.Canvas", return_value=mock_canvas):
        win.setup_window(mock_root)

    assert win.root is mock_root
    assert win.canvas is mock_canvas
    mock_root.overrideredirect.assert_called_once_with(True)
    mock_root.geometry.assert_called_once_with("256x256+10+20")
    mock_root.attributes.assert_any_call("-topmost", True)
    mock_canvas.pack.assert_called_once()


def test_setup_window_alpha_exception_suppressed() -> None:
    """setup_window logs and suppresses exceptions from alpha attribute."""
    win = GaugeWindow(config={"opacity": 0.9})
    mock_root = MagicMock()
    mock_canvas = MagicMock()

    def attrs_side_effect(*args):
        if args[0] == "-alpha":
            raise Exception("alpha not supported")
        return MagicMock()

    mock_root.attributes.side_effect = attrs_side_effect

    with patch("tkinter.Canvas", return_value=mock_canvas):
        win.setup_window(mock_root)

    assert win.canvas is mock_canvas


def test_setup_window_transparent_color_exception_suppressed() -> None:
    """setup_window logs and suppresses exceptions from transparentcolor on Windows."""
    win = GaugeWindow()
    mock_root = MagicMock()
    mock_canvas = MagicMock()

    def attrs_side_effect(*args):
        if args[0] == "-transparentcolor":
            raise Exception("not supported")
        return MagicMock()

    mock_root.attributes.side_effect = attrs_side_effect

    with patch("platform.system", return_value="Windows"), \
         patch("tkinter.Canvas", return_value=mock_canvas):
        win.setup_window(mock_root)

    assert win.canvas is mock_canvas


def test_setup_window_non_windows_canvas_bg() -> None:
    """setup_window uses root.cget('bg') for canvas background on non-Windows."""
    win = GaugeWindow()
    mock_root = MagicMock()
    mock_root.cget.return_value = "gray"
    mock_canvas = MagicMock()

    with patch("platform.system", return_value="Linux"), \
         patch("tkinter.Canvas", return_value=mock_canvas):
        win.setup_window(mock_root)

    assert win.canvas is mock_canvas
    mock_root.cget.assert_called_with("bg")


def test_update_image_with_root_and_canvas() -> None:
    """update_image updates canvas with PhotoImage when root and canvas are set."""
    win = GaugeWindow()
    mock_root = MagicMock()
    mock_canvas = MagicMock()
    win.root = mock_root
    win.canvas = mock_canvas

    img = PILImage.new("RGBA", (256, 256))
    mock_photo = MagicMock()

    with patch("boostgauge.window.ImageTk.PhotoImage", return_value=mock_photo):
        win.update_image(img)

    assert win.photo_image is mock_photo
    mock_canvas.delete.assert_called_once_with("all")
    mock_canvas.create_image.assert_called_once_with(0, 0, anchor="nw", image=mock_photo)