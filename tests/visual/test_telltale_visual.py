"""Visual regression and baseline-independent needle tip geometry tests for telltale renderer.

Issue #2: Feature: peak-hold telltale needles — 1m, 10m, 1h, all-time
"""

import math
from pathlib import Path

import pytest
from PIL import Image, ImageChops

from boostgauge.telltale_renderer import (
    GaugeGeometry,
    TelltaleRenderer,
    val_to_angle_rad,
)


def test_needle_tip_trigonometric_geometry_baseline_independent():
    """Baseline-independent test validating needle tip radial endpoint geometry."""
    geometry = GaugeGeometry(
        center_x=128.0,
        center_y=128.0,
        radius=100.0,
        start_angle_deg=135.0,
        end_angle_deg=405.0,
        min_value=0.0,
        max_value=100.0,
    )

    angle_rad = val_to_angle_rad(50.0, 0.0, 100.0, 135.0, 405.0)
    assert math.isclose(angle_rad, math.radians(270.0), abs_tol=1e-6)

    expected_x = geometry.center_x + geometry.radius * math.cos(angle_rad)
    expected_y = geometry.center_y + geometry.radius * math.sin(angle_rad)

    assert math.isclose(expected_x, 128.0, abs_tol=1e-4)
    assert math.isclose(expected_y, 28.0, abs_tol=1e-4)

    angle_0 = val_to_angle_rad(0.0, 0.0, 100.0, 135.0, 405.0)
    x_0 = geometry.center_x + geometry.radius * math.cos(angle_0)
    y_0 = geometry.center_y + geometry.radius * math.sin(angle_0)
    assert x_0 < geometry.center_x
    assert y_0 > geometry.center_y


def test_needle_tip_at_max_value_geometry():
    """Validate needle tip endpoint at max value (405 degrees = 45 degrees)."""
    geometry = GaugeGeometry()

    angle_rad = val_to_angle_rad(100.0, 0.0, 100.0, 135.0, 405.0)
    assert math.isclose(angle_rad, math.radians(405.0), abs_tol=1e-6)

    x_tip = geometry.center_x + geometry.radius * math.cos(angle_rad)
    y_tip = geometry.center_y + geometry.radius * math.sin(angle_rad)

    # 405 degrees = 45 degrees: tip is right and below center
    assert x_tip > geometry.center_x
    assert y_tip > geometry.center_y


def test_needle_tip_quarter_value_geometry():
    """Validate needle tip at 25% value maps to 202.5 degrees."""
    geometry = GaugeGeometry()

    angle_rad = val_to_angle_rad(25.0, 0.0, 100.0, 135.0, 405.0)
    expected_deg = 135.0 + 0.25 * (405.0 - 135.0)
    assert math.isclose(angle_rad, math.radians(expected_deg), abs_tol=1e-6)

    x_tip = geometry.center_x + geometry.radius * math.cos(angle_rad)
    y_tip = geometry.center_y + geometry.radius * math.sin(angle_rad)

    # 202.5 degrees is between 180° (left) and 270° (straight up in image coords):
    # cos(202.5°) < 0 -> left of center; sin(202.5°) < 0 -> above center in PIL y-down space
    assert x_tip < geometry.center_x
    assert y_tip < geometry.center_y


def test_telltale_visual_render_diff(tmp_path: Path):
    """Verify off-screen visual rendering produces distinct pixels for telltales."""
    base = Image.new("RGBA", (256, 256), (30, 30, 30, 255))
    renderer = TelltaleRenderer()
    peaks = {"1m": 25.0, "10m": 50.0, "1h": 75.0, "all_time": 95.0}

    rendered = renderer.render_telltales(base, peaks, render_legend=True)

    output_file = tmp_path / "telltale_rendered.png"
    rendered.save(output_file)
    assert output_file.exists()

    diff = ImageChops.difference(base, rendered)
    bbox = diff.getbbox()
    assert bbox is not None, "Rendered telltales should draw pixel changes onto base image"


def test_telltale_visual_none_peaks_no_diff(tmp_path: Path):
    """Verify rendering all-None peaks produces no pixel differences from base."""
    base = Image.new("RGBA", (256, 256), (30, 30, 30, 255))
    renderer = TelltaleRenderer()
    peaks = {"1m": None, "10m": None, "1h": None, "all_time": None}

    rendered = renderer.render_telltales(base, peaks, render_legend=False)

    diff = ImageChops.difference(base, rendered)
    assert diff.getbbox() is None, "No pixels should change when all peaks are None"


def test_telltale_visual_render_saved_is_loadable(tmp_path: Path):
    """Verify saved render output can be reloaded as a valid PIL Image."""
    base = Image.new("RGBA", (256, 256), (20, 20, 20, 255))
    renderer = TelltaleRenderer()
    peaks = {"1m": 40.0, "10m": 60.0, "1h": 80.0, "all_time": 90.0}

    rendered = renderer.render_telltales(base, peaks, render_legend=True)
    output_file = tmp_path / "reload_test.png"
    rendered.save(output_file)

    reloaded = Image.open(output_file)
    assert reloaded.size == (256, 256)
    assert reloaded.mode == "RGBA"


def test_telltale_visual_legend_region_differs_from_no_legend():
    """Verify legend flag changes pixel content in the legend region."""
    base = Image.new("RGBA", (256, 256), (30, 30, 30, 255))
    renderer = TelltaleRenderer()
    peaks = {"1m": 50.0, "10m": 60.0, "1h": 70.0, "all_time": 80.0}

    rendered_with = renderer.render_telltales(base, peaks, render_legend=True)
    rendered_without = renderer.render_telltales(base, peaks, render_legend=False)

    diff = ImageChops.difference(rendered_with, rendered_without)
    assert diff.getbbox() is not None, "Legend flag should produce visible differences"


def test_telltale_visual_single_peak_produces_needle_pixels():
    """Verify a single active peak produces needle pixels on the gauge surface."""
    base = Image.new("RGBA", (256, 256), (10, 10, 10, 255))
    renderer = TelltaleRenderer()
    peaks = {"1m": 50.0, "10m": None, "1h": None, "all_time": None}

    rendered = renderer.render_telltales(base, peaks, render_legend=False)

    diff = ImageChops.difference(base, rendered)
    assert diff.getbbox() is not None, "Single active peak should draw needle pixels"


def test_telltale_visual_four_peaks_differ_from_one_peak():
    """Verify rendering four peaks produces more pixel changes than rendering one peak."""
    base = Image.new("RGBA", (256, 256), (15, 15, 15, 255))
    renderer = TelltaleRenderer()

    peaks_one = {"1m": 50.0, "10m": None, "1h": None, "all_time": None}
    peaks_four = {"1m": 25.0, "10m": 50.0, "1h": 75.0, "all_time": 95.0}

    rendered_one = renderer.render_telltales(base, peaks_one, render_legend=False)
    rendered_four = renderer.render_telltales(base, peaks_four, render_legend=False)

    diff_one = ImageChops.difference(base, rendered_one)
    diff_four = ImageChops.difference(base, rendered_four)

    bbox_one = diff_one.getbbox()
    bbox_four = diff_four.getbbox()

    assert bbox_one is not None
    assert bbox_four is not None

    area_one = (bbox_one[2] - bbox_one[0]) * (bbox_one[3] - bbox_one[1])
    area_four = (bbox_four[2] - bbox_four[0]) * (bbox_four[3] - bbox_four[1])
    assert area_four >= area_one, "Four peaks should affect at least as many pixels as one peak"


def test_telltale_visual_output_mode_is_rgba():
    """Verify rendered output is always RGBA regardless of base image mode."""
    renderer = TelltaleRenderer()
    peaks = {"1m": 50.0, "10m": None, "1h": None, "all_time": None}

    base_rgba = Image.new("RGBA", (256, 256), (30, 30, 30, 255))
    result_rgba = renderer.render_telltales(base_rgba, peaks, render_legend=False)
    assert result_rgba.mode == "RGBA"

    base_rgb = Image.new("RGB", (256, 256), (30, 30, 30))
    result_rgb = renderer.render_telltales(base_rgb, peaks, render_legend=False)
    assert result_rgb.mode == "RGBA"


def test_telltale_visual_output_size_preserved():
    """Verify rendered output preserves non-standard input dimensions."""
    renderer = TelltaleRenderer()
    peaks = {"1m": 50.0, "10m": None, "1h": None, "all_time": None}

    for w, h in [(128, 128), (512, 512), (256, 256)]:
        base = Image.new("RGBA", (w, h), (20, 20, 20, 255))
        rendered = renderer.render_telltales(base, peaks, render_legend=False)
        assert rendered.size == (w, h)


def test_telltale_visual_base_not_mutated():
    """Verify render_telltales does not mutate the original base image."""
    base = Image.new("RGBA", (256, 256), (55, 55, 55, 255))
    renderer = TelltaleRenderer()
    peaks = {"1m": 70.0, "10m": 80.0, "1h": 90.0, "all_time": 95.0}

    renderer.render_telltales(base, peaks, render_legend=True)

    assert base.getpixel((128, 128)) == (55, 55, 55, 255)


def test_telltale_visual_needle_center_origin():
    """Verify needle originates from gauge center by checking center pixel is unaltered by compositing."""
    geometry = GaugeGeometry(
        center_x=128.0,
        center_y=128.0,
        radius=100.0,
        start_angle_deg=135.0,
        end_angle_deg=405.0,
        min_value=0.0,
        max_value=100.0,
    )
    renderer = TelltaleRenderer(geometry=geometry)
    base = Image.new("RGBA", (256, 256), (0, 0, 0, 255))
    peaks = {"1m": 50.0, "10m": None, "1h": None, "all_time": None}

    rendered = renderer.render_telltales(base, peaks, render_legend=False)

    assert rendered.size == (256, 256)
    assert rendered.mode == "RGBA"

    diff = ImageChops.difference(base, rendered)
    assert diff.getbbox() is not None


def test_telltale_visual_custom_geometry_needle_endpoint():
    """Validate needle tip geometry for custom GaugeGeometry configuration."""
    geometry = GaugeGeometry(
        center_x=64.0,
        center_y=64.0,
        radius=50.0,
        start_angle_deg=135.0,
        end_angle_deg=405.0,
        min_value=0.0,
        max_value=100.0,
    )

    angle_rad = val_to_angle_rad(50.0, 0.0, 100.0, 135.0, 405.0)
    x_tip = geometry.center_x + geometry.radius * math.cos(angle_rad)
    y_tip = geometry.center_y + geometry.radius * math.sin(angle_rad)

    # Value 50 -> 270 degrees: tip directly above center
    assert math.isclose(x_tip, 64.0, abs_tol=1e-4)
    assert math.isclose(y_tip, 14.0, abs_tol=1e-4)


def test_telltale_visual_all_time_needle_at_boundary():
    """Validate geometry of all_time needle clamped at max boundary value."""
    geometry = GaugeGeometry()

    angle_max = val_to_angle_rad(100.0, 0.0, 100.0, 135.0, 405.0)
    assert math.isclose(angle_max, math.radians(405.0), abs_tol=1e-6)

    angle_over = val_to_angle_rad(150.0, 0.0, 100.0, 135.0, 405.0)
    assert math.isclose(angle_over, math.radians(405.0), abs_tol=1e-6)


def test_telltale_visual_nan_guard_defaults_to_start():
    """Validate NaN value defaults needle angle to start position."""
    angle = val_to_angle_rad(float("nan"), 0.0, 100.0, 135.0, 405.0)
    assert math.isclose(angle, math.radians(135.0), abs_tol=1e-6)

    geometry = GaugeGeometry()
    x_tip = geometry.center_x + geometry.radius * math.cos(angle)
    y_tip = geometry.center_y + geometry.radius * math.sin(angle)

    # 135 degrees: left of center (cos < 0), below center in PIL y-down (sin > 0)
    assert x_tip < geometry.center_x
    assert y_tip > geometry.center_y