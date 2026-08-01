"""Headless unit tests for TrayManager status dot image generation, context menu construction, and thread-safe event dispatching.

Issue #5: Always-on-top window with drag, minimize, and transparency.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from boostgauge.tray import STATUS_COLORS, TrayManager


def _make_tray(**kwargs) -> TrayManager:
    defaults = dict(
        on_restore=lambda: None,
        on_toggle_topmost=lambda: None,
        on_quit=lambda: None,
    )
    defaults.update(kwargs)
    return TrayManager(**defaults)


def test_tray_status_dot_green() -> None:
    """T060: Green status dot is 16x16 RGBA with green center pixel."""
    tray = _make_tray()
    img = tray.create_status_dot("green")
    assert isinstance(img, Image.Image)
    assert img.size == (16, 16)
    assert img.mode == "RGBA"
    assert img.getpixel((8, 8)) == (0, 255, 0, 255)


def test_tray_status_dot_red() -> None:
    """Red status dot has red center pixel."""
    tray = _make_tray()
    img = tray.create_status_dot("red")
    assert img.getpixel((8, 8)) == (255, 0, 0, 255)


def test_tray_status_dot_yellow() -> None:
    """Yellow status dot has yellow center pixel."""
    tray = _make_tray()
    img = tray.create_status_dot("yellow")
    assert img.getpixel((8, 8)) == (255, 255, 0, 255)


def test_tray_status_dot_unknown_defaults_yellow() -> None:
    """Unknown status string defaults to yellow dot."""
    tray = _make_tray()
    img = tray.create_status_dot("unknown")  # type: ignore[arg-type]
    assert img.getpixel((8, 8)) == (255, 255, 0, 255)


def test_tray_status_dot_background_color() -> None:
    """Status dot background corner pixel is dark gray."""
    tray = _make_tray()
    img = tray.create_status_dot("green")
    assert img.getpixel((0, 0)) == (30, 30, 30, 255)


def test_tray_status_dot_size_always_16x16() -> None:
    """All status dots are exactly 16x16."""
    tray = _make_tray()
    for status in ("green", "yellow", "red"):
        img = tray.create_status_dot(status)  # type: ignore[arg-type]
        assert img.size == (16, 16)


def test_restore_callback_dispatch() -> None:
    """T070: _handle_restore invokes on_restore callback."""
    restored = False

    def on_restore() -> None:
        nonlocal restored
        restored = True

    tray = _make_tray(on_restore=on_restore)
    tray._handle_restore(icon=None, item=None)
    assert restored is True


def test_toggle_topmost_callback_dispatch() -> None:
    """_handle_toggle_topmost invokes on_toggle_topmost callback."""
    toggled = False

    def on_toggle() -> None:
        nonlocal toggled
        toggled = True

    tray = _make_tray(on_toggle_topmost=on_toggle)
    tray._handle_toggle_topmost(icon=None, item=None)
    assert toggled is True


def test_quit_callback_dispatch() -> None:
    """_handle_quit stops tray and invokes on_quit callback."""
    quit_called = False

    def on_quit() -> None:
        nonlocal quit_called
        quit_called = True

    tray = _make_tray(on_quit=on_quit)
    tray._is_running = False
    tray._handle_quit(icon=None, item=None)
    assert quit_called is True


def test_initial_state() -> None:
    """TrayManager initializes with expected default state."""
    tray = _make_tray()
    assert tray.current_status == "green"
    assert tray.icon is None
    assert tray.thread is None
    assert tray._is_running is False


def test_start_sets_running_and_spawns_thread() -> None:
    """start() sets _is_running and launches a daemon thread."""
    tray = _make_tray()

    mock_icon = MagicMock()
    mock_icon.run = MagicMock()

    with patch("pystray.Icon", return_value=mock_icon):
        tray.start()

    assert tray._is_running is True
    assert tray.thread is not None
    assert tray.thread.daemon is True


def test_start_twice_logs_warning_and_skips() -> None:
    """start() called when already running logs warning and does not spawn another thread."""
    tray = _make_tray()
    tray._is_running = True

    with patch("boostgauge.tray.logger") as mock_logger, patch("pystray.Icon") as mock_icon_cls:
        tray.start()
        mock_logger.warning.assert_called_once()
        mock_icon_cls.assert_not_called()


def test_stop_clears_icon_and_running_flag() -> None:
    """stop() clears _is_running and icon reference."""
    tray = _make_tray()
    mock_icon = MagicMock()
    tray.icon = mock_icon
    tray._is_running = True

    tray.stop()

    assert tray._is_running is False
    assert tray.icon is None
    mock_icon.stop.assert_called_once()


def test_stop_when_not_running_is_noop() -> None:
    """stop() does nothing when _is_running is False."""
    tray = _make_tray()
    tray.stop()
    assert tray.icon is None
    assert tray._is_running is False


def test_stop_suppresses_icon_stop_exception() -> None:
    """stop() suppresses exceptions raised by icon.stop()."""
    tray = _make_tray()
    mock_icon = MagicMock()
    mock_icon.stop.side_effect = Exception("stop error")
    tray.icon = mock_icon
    tray._is_running = True

    tray.stop()
    assert tray._is_running is False
    assert tray.icon is None


def test_update_status_changes_current_status() -> None:
    """update_status updates current_status attribute."""
    tray = _make_tray()
    tray.update_status("red")
    assert tray.current_status == "red"


def test_update_status_updates_icon_image_when_running() -> None:
    """update_status pushes new icon image when running."""
    tray = _make_tray()
    mock_icon = MagicMock()
    tray.icon = mock_icon
    tray._is_running = True

    tray.update_status("yellow")

    assert mock_icon.icon is not None
    assert isinstance(mock_icon.icon, Image.Image)
    assert mock_icon.icon.size == (16, 16)


def test_update_status_skips_icon_update_when_not_running() -> None:
    """update_status does not touch icon when not running."""
    tray = _make_tray()
    mock_icon = MagicMock()
    tray.icon = mock_icon
    tray._is_running = False

    tray.update_status("red")
    assert not isinstance(mock_icon.icon, Image.Image)


def test_update_status_no_icon_is_noop() -> None:
    """update_status does nothing when icon is None."""
    tray = _make_tray()
    tray._is_running = True
    tray.icon = None
    tray.update_status("green")
    assert tray.current_status == "green"


def test_run_icon_with_none_icon_is_noop() -> None:
    """_run_icon does nothing when self.icon is None."""
    tray = _make_tray()
    tray._run_icon()


def test_run_icon_calls_icon_run() -> None:
    """_run_icon calls icon.run() when icon is set."""
    tray = _make_tray()
    mock_icon = MagicMock()
    tray.icon = mock_icon

    tray._run_icon()
    mock_icon.run.assert_called_once()


def test_status_colors_constant() -> None:
    """STATUS_COLORS maps all expected statuses to RGBA tuples."""
    assert STATUS_COLORS["green"] == (0, 255, 0, 255)
    assert STATUS_COLORS["yellow"] == (255, 255, 0, 255)
    assert STATUS_COLORS["red"] == (255, 0, 0, 255)


def test_handle_quit_stops_tray_before_calling_quit() -> None:
    """_handle_quit calls stop() then on_quit."""
    call_order: list = []

    tray = _make_tray(on_quit=lambda: call_order.append("quit"))
    original_stop = tray.stop

    def tracking_stop() -> None:
        call_order.append("stop")
        original_stop()

    tray.stop = tracking_stop  # type: ignore[method-assign]
    tray._handle_quit(icon=None, item=None)

    assert call_order == ["stop", "quit"]


def test_start_creates_pystray_icon_with_correct_name() -> None:
    """start() creates pystray.Icon named 'boostgauge'."""
    tray = _make_tray()

    created_names: list = []

    def capture_icon(name, *args, **kwargs):
        created_names.append(name)
        mock = MagicMock()
        mock.run = MagicMock()
        return mock

    with patch("pystray.Icon", side_effect=capture_icon):
        tray.start()

    assert created_names == ["boostgauge"]


def test_create_status_dot_returns_new_image_each_call() -> None:
    """create_status_dot returns a fresh Image instance on each call."""
    tray = _make_tray()
    img1 = tray.create_status_dot("green")
    img2 = tray.create_status_dot("green")
    assert img1 is not img2