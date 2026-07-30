"""Unit tests for GaugeWindow window manager component.

Issue #5: always-on-top window with drag, minimize, and transparency (#5)
"""

from __future__ import annotations

import sys
from typing import Any
from unittest.mock import MagicMock

import pytest

from boostgauge.window import (
    DEFAULT_EXPANDED_SIZE,
    MAX_WINDOW_SIZE,
    MIN_WINDOW_SIZE,
    TRANSPARENT_COLOR,
    GaugeWindow,
)


class DummyTkRoot:
    """Mock Tk root for headless testing without GUI display."""

    def __init__(self) -> None:
        self.attrs: dict = {}
        self.geom: str = ""
        self.overridden: bool = False
        self.bg: str = ""
        self.withdrawn: bool = False
        self.deiconified: bool = False
        self.lifted: bool = False
        self.destroyed: bool = False
        self._title: str = "BoostGauge"

    def overrideredirect(self, flag: bool) -> None:
        self.overridden = flag

    def attributes(self, key: str, value: Any = None) -> Any:
        if value is not None:
            self.attrs[key] = value
            return None
        return self.attrs.get(key)

    def geometry(self, geom_str: str) -> None:
        self.geom = geom_str

    def configure(self, **kwargs: Any) -> None:
        if "bg" in kwargs:
            self.bg = kwargs["bg"]

    def winfo_vrootx(self) -> int:
        return 0

    def winfo_vrooty(self) -> int:
        return 0

    def winfo_vrootwidth(self) -> int:
        return 1920

    def winfo_vrootheight(self) -> int:
        return 1080

    def winfo_x(self) -> int:
        return self._parse_geom_x()

    def winfo_y(self) -> int:
        return self._parse_geom_y()

    def _parse_geom_x(self) -> int:
        if "+" in self.geom:
            parts = self.geom.split("+")
            if len(parts) >= 2:
                try:
                    return int(parts[1])
                except ValueError:
                    pass
        return 100

    def _parse_geom_y(self) -> int:
        if "+" in self.geom:
            parts = self.geom.split("+")
            if len(parts) >= 3:
                try:
                    return int(parts[2])
                except ValueError:
                    pass
        return 100

    def title(self, t: str = "") -> str:
        self._title = t
        return self._title

    def withdraw(self) -> None:
        self.withdrawn = True

    def deiconify(self) -> None:
        self.deiconified = True

    def lift(self) -> None:
        self.lifted = True

    def destroy(self) -> None:
        self.destroyed = True

    def protocol(self, name: str, callback: Any) -> None:
        pass

    def mainloop(self) -> None:
        pass

    def quit(self) -> None:
        pass

    def after(self, ms: int, callback: Any = None) -> None:
        if callback:
            callback()


def make_event(**kwargs: Any) -> Any:
    return type("Event", (), kwargs)()


def make_window(config: dict | None = None, **kwargs: Any) -> tuple[GaugeWindow, DummyTkRoot]:
    root = DummyTkRoot()
    win = GaugeWindow(config=config, root=root, **kwargs)
    return win, root


def test_t010_topmost_toggle() -> None:
    win, root = make_window(config={"always_on_top": True})
    assert root.attrs.get("-topmost") is True

    new_state = win.toggle_topmost()
    assert new_state is False
    assert root.attrs.get("-topmost") is False

    new_state = win.toggle_topmost()
    assert new_state is True
    assert root.attrs.get("-topmost") is True


def test_t020_drag_motion_geometry() -> None:
    win, root = make_window(config={"position": {"x": 100, "y": 100}, "size": 256})
    root.geom = "256x256+100+100"

    win.handle_drag_start(make_event(x=10, y=10))
    win.handle_drag_motion(make_event(x=60, y=40))

    assert win.x == 150
    assert win.y == 130
    assert root.geom == "256x256+150+130"


def test_t030_double_click_compact_expanded_toggle() -> None:
    win, root = make_window(config={"size": 256})

    new_size = win.toggle_compact_expanded()
    assert new_size == MIN_WINDOW_SIZE
    assert win.is_expanded is False

    restored_size = win.toggle_compact_expanded()
    assert restored_size == 256
    assert win.is_expanded is True


def test_t030_custom_expanded_size_preserved() -> None:
    win, root = make_window(config={"size": 512})

    new_size = win.toggle_compact_expanded()
    assert new_size == MIN_WINDOW_SIZE

    restored_size = win.toggle_compact_expanded()
    assert restored_size == 512


def test_t040_transparent_background_setup() -> None:
    win, root = make_window()
    assert root.bg == TRANSPARENT_COLOR
    if sys.platform == "win32":
        assert root.attrs.get("-transparentcolor") == TRANSPARENT_COLOR


def test_t050_opacity_adjustment() -> None:
    win, root = make_window(config={"opacity": 0.8})
    assert root.attrs.get("-alpha") == 0.8

    win.set_opacity(1.0)
    assert root.attrs.get("-alpha") == 1.0


def test_t050_opacity_clamped_low() -> None:
    win, root = make_window()
    win.set_opacity(-0.5)
    assert root.attrs.get("-alpha") == 0.1


def test_t050_opacity_clamped_high() -> None:
    win, root = make_window()
    win.set_opacity(2.0)
    assert root.attrs.get("-alpha") == 1.0


def test_t060_minimize_to_tray() -> None:
    win, root = make_window()
    win.minimize_to_tray()
    assert root.withdrawn is True
    assert win.is_minimized_to_tray is True


def test_t080_restore_from_tray() -> None:
    win, root = make_window()
    win.minimize_to_tray()
    assert win.is_minimized_to_tray is True

    win.restore_from_tray()
    assert root.deiconified is True
    assert root.lifted is True
    assert win.is_minimized_to_tray is False


def test_t080_restore_reasserts_topmost() -> None:
    win, root = make_window(config={"always_on_top": True})
    win.minimize_to_tray()
    root.attrs["-topmost"] = False

    win.restore_from_tray()
    assert root.attrs.get("-topmost") is True


def test_t110_virtual_multimonitor_bounds_clamping() -> None:
    win, root = make_window()

    cx, cy = win.clamp_to_screen(5000, 5000, 256)
    assert cx == 1920 - 256
    assert cy == 1080 - 256


def test_t110_negative_coordinate_clamping() -> None:
    win, root = make_window()

    cx, cy = win.clamp_to_screen(-100, -200, 256)
    assert cx == 0
    assert cy == 0


def test_t110_clamping_applied_on_init() -> None:
    win, root = make_window(config={"position": {"x": 9999, "y": 9999}, "size": 256})
    assert win.x <= 1920 - 256
    assert win.y <= 1080 - 256


def test_t120_mouse_wheel_aspect_ratio_resize() -> None:
    win, root = make_window(config={"size": 256})

    win.handle_mouse_wheel(make_event(delta=120, num=0))
    assert win.size == 288

    win.handle_mouse_wheel(make_event(delta=-120, num=0))
    assert win.size == 256


def test_t120_mouse_wheel_linux_button4_5() -> None:
    win, root = make_window(config={"size": 256})

    win.handle_mouse_wheel(make_event(delta=0, num=4))
    assert win.size == 288

    win.handle_mouse_wheel(make_event(delta=0, num=5))
    assert win.size == 256


def test_t130_mouse_wheel_out_of_bounds_clamping_min() -> None:
    win, root = make_window(config={"size": MIN_WINDOW_SIZE})

    win.handle_mouse_wheel(make_event(delta=-120, num=0))
    assert win.size == MIN_WINDOW_SIZE


def test_t130_mouse_wheel_out_of_bounds_clamping_max() -> None:
    win, root = make_window(config={"size": MAX_WINDOW_SIZE})

    win.handle_mouse_wheel(make_event(delta=120, num=0))
    assert win.size == MAX_WINDOW_SIZE


def test_mouse_wheel_updates_geometry_string() -> None:
    win, root = make_window(config={"size": 256})

    win.handle_mouse_wheel(make_event(delta=120, num=0))
    assert "288x288" in root.geom


def test_mouse_wheel_noop_on_zero_delta() -> None:
    win, root = make_window(config={"size": 256})
    original_size = win.size

    win.handle_mouse_wheel(make_event(delta=0, num=0))
    assert win.size == original_size


def test_geometry_change_callback_on_drag() -> None:
    callback = MagicMock()
    win, root = make_window(
        config={"position": {"x": 100, "y": 100}, "size": 256},
        on_geometry_change=callback,
    )
    root.geom = "256x256+100+100"

    win.handle_drag_start(make_event(x=0, y=0))
    win.handle_drag_motion(make_event(x=50, y=30))

    callback.assert_called_once_with(win.x, win.y, win.size)


def test_geometry_change_callback_on_toggle() -> None:
    callback = MagicMock()
    win, root = make_window(config={"size": 256}, on_geometry_change=callback)

    win.toggle_compact_expanded()
    callback.assert_called_once()


def test_geometry_change_callback_on_wheel() -> None:
    callback = MagicMock()
    win, root = make_window(config={"size": 256}, on_geometry_change=callback)

    win.handle_mouse_wheel(make_event(delta=120, num=0))
    callback.assert_called_once()


def test_on_close_callback_called_on_destroy() -> None:
    callback = MagicMock()
    win, root = make_window(on_close=callback)

    win.destroy()
    callback.assert_called_once()


def test_destroy_calls_root_destroy() -> None:
    win, root = make_window()
    win.destroy()
    assert root.destroyed is True


def test_default_config_values() -> None:
    win, root = make_window()
    assert win.x == 100
    assert win.y == 100
    assert win.size == DEFAULT_EXPANDED_SIZE
    assert win.topmost is True
    assert win.opacity == 0.8
    assert win.hover_opacity == 1.0
    assert win.is_expanded is True
    assert win.is_minimized_to_tray is False


def test_config_position_parsed() -> None:
    win, root = make_window(config={"position": {"x": 300, "y": 200}})
    assert win.x == 300
    assert win.y == 200


def test_saved_expanded_size_preserved_through_toggle() -> None:
    win, root = make_window(config={"size": 384})

    win.toggle_compact_expanded()
    assert win.size == MIN_WINDOW_SIZE
    assert win.saved_expanded_size == 384

    win.toggle_compact_expanded()
    assert win.size == 384


def test_wheel_up_sets_saved_expanded_size() -> None:
    win, root = make_window(config={"size": 256})

    win.handle_mouse_wheel(make_event(delta=120, num=0))
    assert win.saved_expanded_size == 288
    assert win.is_expanded is True


def test_drag_start_records_position() -> None:
    win, root = make_window()
    win.handle_drag_start(make_event(x=42, y=77))
    assert win._drag_start_x == 42
    assert win._drag_start_y == 77


def test_geometry_string_format_on_init() -> None:
    win, root = make_window(config={"position": {"x": 50, "y": 75}, "size": 256})
    assert root.geom == "256x256+50+75"


def test_toggle_compact_updates_geometry() -> None:
    win, root = make_window(config={"size": 256})
    win.toggle_compact_expanded()
    assert "128x128" in root.geom


def test_overrideredirect_called() -> None:
    win, root = make_window()
    assert root.overridden is True