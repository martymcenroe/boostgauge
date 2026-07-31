"""Unit tests for core gauge renderer module.

Issue #1: Core Gauge Renderer — Analog Tachometer with Arc, Needle, and Tick Marks
"""

from __future__ import annotations

import math
import sys
import pytest
from PIL import Image

from boostgauge.gauge import render
from boostgauge.skins.stingray import _val_to_angle, _load_skin_font


def test_render_pure_function_output():
    """T010: Verify render returns a PIL Image and imports no tkinter modules."""
    img = render(50.0, size=(256, 256))
    assert isinstance(img, Image.Image)
    assert img.size == (256, 256)
    assert img.mode == "RGBA"
    assert "tkinter" not in sys.modules


def test_value_clamping():
    """T020: Verify values outside [0, 100] are clamped without raising exceptions."""
    img_neg = render(-25.0, size=(128, 128))
    img_zero = render(0.0, size=(128, 128))
    img_over = render(150.0, size=(128, 128))
    img_max = render(100.0, size=(128, 128))

    assert img_neg.tobytes() == img_zero.tobytes()
    assert img_over.tobytes() == img_max.tobytes()


def test_invalid_size_rejection():
    """T030: Verify size below 128x128 raises ValueError."""
    with pytest.raises(ValueError, match="at least 128x128"):
        render(50.0, size=(64, 64))

    with pytest.raises(ValueError, match="at least 128x128"):
        render(50.0, size=(128, 64))


def test_unsupported_skin_rejection():
    """T040: Verify unsupported skin name raises ValueError."""
    with pytest.raises(ValueError, match="Unsupported skin"):
        render(50.0, config={"skin": "cyberpunk_2077"})


def test_val_to_angle_mapping():
    """T100: Verify angle math maps metric 0-100 across 270 degree sweep."""
    assert _val_to_angle(0.0) == 225.0
    assert _val_to_angle(50.0) == 90.0
    assert _val_to_angle(100.0) == -45.0


def test_telltales_post_reset_hiding():
    """T120: Verify None peak values render identically to no telltales."""
    img_none = render(50.0, telltales=None, size=(128, 128))
    img_empty = render(
        50.0,
        telltales={"window_1m": None, "window_10m": None, "window_1h": None, "window_all": None},
        size=(128, 128),
    )
    assert img_none.tobytes() == img_empty.tobytes()


def test_deterministic_output():
    """T140: Verify repeated renders with identical parameters produce byte-identical images."""
    img1 = render(75.0, telltales={"window_1m": 80.0}, size=(256, 256))
    img2 = render(75.0, telltales={"window_1m": 80.0}, size=(256, 256))
    assert img1.tobytes() == img2.tobytes()


def test_baseline_independent_needle_tip_trigonometry():
    """Verify main needle tip position angle mathematics without baseline images.

    At value=50, angle is 90° (straight up).
    """
    center_x, center_y = 128.0, 128.0
    radius = 128.0
    length_factor = 0.78
    needle_len = radius * length_factor

    angle_50 = _val_to_angle(50.0)
    rad_50 = math.radians(angle_50)
    tip_x_50 = center_x + needle_len * math.cos(rad_50)
    tip_y_50 = center_y - needle_len * math.sin(rad_50)

    assert math.isclose(angle_50, 90.0, abs_tol=1e-5)
    assert math.isclose(tip_x_50, 128.0, abs_tol=1e-4)
    assert math.isclose(tip_y_50, 128.0 - (128.0 * 0.78), abs_tol=1e-4)

    angle_0 = _val_to_angle(0.0)
    rad_0 = math.radians(angle_0)
    tip_x_0 = center_x + needle_len * math.cos(rad_0)
    tip_y_0 = center_y - needle_len * math.sin(rad_0)

    assert math.isclose(angle_0, 225.0, abs_tol=1e-5)
    assert tip_x_0 < center_x
    assert tip_y_0 > center_y


def test_baseline_independent_bezel_outer_pixel_colors():
    """Verify corner background colors and bezel structure without baseline images."""
    img = render(0.0, size=(256, 256))
    pixels = img.load()

    r, g, b, a = pixels[0, 0]
    assert r == 20 and g == 22 and b == 26 and a == 255

    r_c, g_c, b_c, a_c = pixels[128, 128]
    assert r_c > 150 and g_c > 150 and b_c > 150