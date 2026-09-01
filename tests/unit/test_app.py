"""Unit tier for the window module's pure parts (issue #5) and the entry point's error path.

``tkinter.Tk()`` is never instantiated here (strategy 0001, Option C). What is
covered: the tray colour bands and image, the transparency keying of a frame,
screen clamping, wheel resize steps, and ``main`` refusing a bad config with
a clear message before any window exists.
"""

from __future__ import annotations

import pytest

from boostgauge import app
from boostgauge.skins import stingray


def test_tray_color_bands_are_the_composites_boundaries():
    assert app.tray_color(0) == app.GREEN
    assert app.tray_color(59.9) == app.GREEN
    assert app.tray_color(60) == app.YELLOW
    assert app.tray_color(79.9) == app.YELLOW
    assert app.tray_color(80) == app.RED
    assert app.tray_color(100) == app.RED


def test_tray_image_is_a_dot_on_transparency():
    img = app.tray_image(app.RED, 64)
    assert img.size == (64, 64) and img.mode == "RGBA"
    assert img.getpixel((0, 0)) == (0, 0, 0, 0)            # corner transparent
    assert img.getpixel((32, 32)) == app.RED + (255,)      # centre is the dot


def test_keyed_frame_keys_out_the_corners_and_keeps_the_face():
    frame = stingray.render_face(256)
    keyed = app.keyed_frame(frame)
    assert keyed.size == (256, 256)
    assert keyed.getpixel((0, 0)) == app.TRANSPARENT_KEY
    assert keyed.getpixel((255, 255)) == app.TRANSPARENT_KEY
    assert keyed.getpixel((128, 128)) == (10, 10, 12)      # dial centre untouched
    assert keyed.getpixel((128, 4)) == frame.getpixel((128, 4))   # housing edge untouched


def test_clamp_to_screen():
    assert app.clamp_to_screen(100, 100, 300, 1920, 1080) == (100, 100)
    assert app.clamp_to_screen(5000, 100, 300, 1920, 1080) == (1620, 100)   # off the right edge
    assert app.clamp_to_screen(-50, -50, 300, 1920, 1080) == (0, 0)
    assert app.clamp_to_screen(100, 900, 300, 1920, 1080) == (100, 780)     # off the bottom


def test_step_size_is_ten_percent_square_and_clamped():
    assert app.step_size(300, +1) == 330
    assert app.step_size(300, -1) == 273
    assert app.step_size(app.MAX_SIZE, +1) == app.MAX_SIZE
    assert app.step_size(app.MIN_SIZE, -1) == app.MIN_SIZE


def test_main_refuses_a_bad_config_value_before_any_window(tmp_path, capsys):
    status = app.main(["--config", str(tmp_path / "c.json"), "--opacity", "5"])
    assert status == 2
    err = capsys.readouterr().err
    assert "boostgauge: config key 'opacity': expected a number between 0.0 and 1.0, got 5" in err


def test_main_rejects_an_unknown_theme_via_argparse():
    with pytest.raises(SystemExit):
        app.main(["--theme", "sepia"])
