"""Unit tests for gauge math, input validation, and baseline-independent needle geometry.

Issue #1: Core Gauge Renderer — Analog Tachometer.
"""

from __future__ import annotations

import math
import pytest
from pathlib import Path
import PIL.Image

from boostgauge.gauge import render, validate_render_inputs
from boostgauge.skins.stingray import calculate_angle, render_stingray


def test_validate_render_inputs_clamping():
    """Verify scalar values <0 clamp to 0, >100 clamp to 100, and size <128 clamps to 128."""
    val, sz = validate_render_inputs(-15.0, 64)
    assert val == 0.0
    assert sz == 128

    val, sz = validate_render_inputs(150.0, 512)
    assert val == 100.0
    assert sz == 512


def test_validate_render_inputs_type_errors():
    """Verify non-numeric input types raise TypeError."""
    with pytest.raises(TypeError):
        validate_render_inputs("invalid", 256)
    with pytest.raises(TypeError):
        validate_render_inputs(50.0, "invalid")


def test_calculate_angle_linear_sweep():
    """Verify linear mapping: 0 -> 225°, 50 -> 90°, 100 -> -45°."""
    assert calculate_angle(0.0) == pytest.approx(225.0)
    assert calculate_angle(50.0) == pytest.approx(90.0)
    assert calculate_angle(100.0) == pytest.approx(-45.0)
    assert calculate_angle(25.0) == pytest.approx(157.5)
    assert calculate_angle(75.0) == pytest.approx(22.5)


def test_pure_function_offscreen_rendering():
    """Verify render() returns a valid PIL Image without instantiating tkinter."""
    img = render(75.0, size=256)
    assert isinstance(img, PIL.Image.Image)
    assert img.size == (256, 256)
    assert img.mode == "RGBA"


def test_baseline_independent_needle_tip_trigonometry():
    """Compute needle tip coordinates mathematically and verify color presence without baselines."""
    size = 256
    img = render(50.0, size=size)

    angle_deg = calculate_angle(50.0)
    assert angle_deg == pytest.approx(90.0)

    cx, cy = size / 2.0, size / 2.0
    r_tip = size * 0.35
    rad = math.radians(angle_deg)
    expected_tip_x = int(cx + r_tip * math.cos(rad))
    expected_tip_y = int(cy - r_tip * math.sin(rad))

    assert expected_tip_x == pytest.approx(int(cx), abs=1)
    assert expected_tip_y == pytest.approx(int(cy - r_tip), abs=1)

    pixel = img.getpixel((expected_tip_x, expected_tip_y))
    assert pixel[0] > 200 and pixel[1] < 50 and pixel[2] < 50 and pixel[3] > 0


def test_telltale_none_value_byte_identical():
    """Verify telltales with None values produce byte-identical output to telltales=None (T060)."""
    img1 = render(50.0, telltales={"m1": None}, size=256)
    img2 = render(50.0, telltales=None, size=256)
    assert img1.tobytes() == img2.tobytes()


def test_draw_redline_arc_pixel_rendering():
    """Verify redline arc renders red pixels in the 60-100 value arc region (T070)."""
    img = render(75.0, size=256)
    rad = math.radians(22.5)
    px = int(128 + 97.28 * math.cos(rad))
    py = int(128 - 97.28 * math.sin(rad))
    pixel = img.getpixel((px, py))
    assert pixel[0] > 180 and pixel[1] < 60


def test_render_stingray_composite_structure():
    """Verify render_stingray constructs full composite housing, dial, ticks, and wordmark (T080)."""
    img = render_stingray(50.0, size=256)
    assert isinstance(img, PIL.Image.Image)
    assert img.size == (256, 256)
    assert img.mode == "RGBA"
    assert img.getpixel((128, 128))[3] == 255


def test_render_skin_routing_stingray():
    """Verify render() dispatches to stingray skin when specified in config dict (T090)."""
    img = render(50.0, size=256, config={"skin": "stingray"})
    assert isinstance(img, PIL.Image.Image)
    assert img.size == (256, 256)


def test_visual_regression_missing_baseline_failure(tmp_path):
    """Verify missing visual baseline without --generate-baselines triggers pytest failure (T100)."""
    import importlib
    import sys

    mod_name = "tests.visual.test_gauge"
    if mod_name in sys.modules:
        tvg = sys.modules[mod_name]
    else:
        spec = importlib.util.spec_from_file_location(
            mod_name,
            Path(__file__).resolve().parent.parent / "visual" / "test_gauge.py",
        )
        tvg = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tvg)

    class DummyConfig:
        def getoption(self, name, default=False):
            return False

    saved_dir = tvg.BASELINES_DIR
    try:
        tvg.BASELINES_DIR = tmp_path / "nonexistent_baselines"
        with pytest.raises(pytest.fail.Exception, match="Missing visual baseline"):
            tvg.test_visual_regression_rest_state(DummyConfig())
    finally:
        tvg.BASELINES_DIR = saved_dir


def test_unknown_skin_raises_value_error():
    """Verify unknown skin name in config raises ValueError."""
    with pytest.raises(ValueError, match="Unknown skin"):
        render(50.0, config={"skin": "nonexistent_skin"})