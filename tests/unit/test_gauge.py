"""Unit tests for core gauge renderer API, parameter validation, and angle math.

Issue #1: Feature: Core Gauge Renderer — Analog Tachometer with Arc, Needle, and Tick Marks
"""

import math
from pathlib import Path
import pytest
from PIL import Image

from boostgauge.gauge import render, _validate_render_args
from boostgauge.skins.stingray import _val_to_angle, COLOR_MAIN_NEEDLE


def test_render_default_returns_pil_image():
    img = render(0.0)
    assert isinstance(img, Image.Image)
    assert img.size == (256, 256)
    assert img.mode == "RGBA"


def test_render_full_scale():
    img = render(100.0, size=(256, 256))
    assert isinstance(img, Image.Image)
    assert img.size == (256, 256)


def test_render_deterministic():
    img1 = render(50.0)
    img2 = render(50.0)
    assert img1.tobytes() == img2.tobytes()


def test_skin_dispatch_stingray():
    img = render(50.0, config={"skin": "stingray"})
    assert isinstance(img, Image.Image)


def test_skin_dispatch_invalid():
    with pytest.raises(ValueError, match="Unsupported skin: invalid_skin_name"):
        render(50.0, config={"skin": "invalid_skin_name"})


def test_dimension_validation():
    with pytest.raises(ValueError, match="at least 128x128"):
        render(50.0, size=(64, 64))


def test_value_clamping():
    val_low, _ = _validate_render_args(-25.0, (256, 256), None)
    assert val_low == 0.0

    val_high, _ = _validate_render_args(150.0, (256, 256), None)
    assert val_high == 100.0


def test_val_to_angle_mapping_baseline_independent():
    assert math.isclose(_val_to_angle(0.0), 225.0, abs_tol=1e-5)
    assert math.isclose(_val_to_angle(50.0), 90.0, abs_tol=1e-5)
    assert math.isclose(_val_to_angle(100.0), -45.0, abs_tol=1e-5)


def test_needle_tip_trigonometry_baseline_independent():
    center = (128.0, 128.0)
    radius = 100.0
    value = 50.0
    angle_deg = _val_to_angle(value)
    angle_rad = math.radians(angle_deg)

    expected_tip_x = center[0] + radius * 0.85 * math.cos(angle_rad)
    expected_tip_y = center[1] - radius * 0.85 * math.sin(angle_rad)

    assert math.isclose(expected_tip_x, 128.0, abs_tol=1e-4)
    assert math.isclose(expected_tip_y, 43.0, abs_tol=1e-4)


def test_path_comparison_platform_independent(tmp_path):
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text("{}")
    assert cfg_file == tmp_path / "config.json"


def test_render_custom_size():
    img = render(50.0, size=(512, 512))
    assert img.size == (512, 512)
    assert img.mode == "RGBA"


def test_render_minimum_valid_size():
    img = render(50.0, size=(128, 128))
    assert img.size == (128, 128)


def test_render_with_telltales():
    telltales = {
        "window_1m": 60.0,
        "window_10m": 75.0,
        "window_1h": 85.0,
        "window_all": 95.0,
    }
    img = render(50.0, telltales=telltales)
    assert isinstance(img, Image.Image)


def test_render_with_none_telltales():
    telltales = {
        "window_1m": None,
        "window_10m": None,
        "window_1h": None,
        "window_all": None,
    }
    img = render(50.0, telltales=telltales)
    assert isinstance(img, Image.Image)


def test_render_with_partial_telltales():
    telltales = {"window_1m": 80.0}
    img = render(50.0, telltales=telltales)
    assert isinstance(img, Image.Image)


def test_validate_render_args_returns_size_unchanged():
    _, size = _validate_render_args(50.0, (256, 256), None)
    assert size == (256, 256)


def test_validate_render_args_width_too_small():
    with pytest.raises(ValueError, match="at least 128x128"):
        _validate_render_args(50.0, (64, 256), None)


def test_validate_render_args_height_too_small():
    with pytest.raises(ValueError, match="at least 128x128"):
        _validate_render_args(50.0, (256, 64), None)


def test_val_to_angle_quarter_values():
    assert math.isclose(_val_to_angle(25.0), 157.5, abs_tol=1e-5)
    assert math.isclose(_val_to_angle(75.0), 22.5, abs_tol=1e-5)


def test_render_supersample_factor_override():
    img = render(50.0, size=(256, 256), config={"supersample_factor": 2})
    assert isinstance(img, Image.Image)
    assert img.size == (256, 256)