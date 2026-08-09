"""Unit tests for TelltaleRenderer, TelltaleManager, and radial mapping math.

Issue #2: Feature: peak-hold telltale needles — 1m, 10m, 1h, all-time
"""

import math
from pathlib import Path
import pytest
from PIL import Image

from boostgauge.telltale_renderer import (
    GaugeGeometry,
    TelltaleManager,
    TelltaleRenderer,
    TelltaleStyle,
    val_to_angle_rad,
)


def test_val_to_angle_rad_midpoint():
    """Verify 50% value maps exactly to 270 degrees (3*pi/2 radians)."""
    angle = val_to_angle_rad(50.0, 0.0, 100.0, 135.0, 405.0)
    expected = math.radians(270.0)
    assert math.isclose(angle, expected, abs_tol=1e-6)


def test_val_to_angle_rad_min_and_max():
    """Verify 0.0 and 100.0 map to start_angle and end_angle respectively."""
    angle_min = val_to_angle_rad(0.0, 0.0, 100.0, 135.0, 405.0)
    assert math.isclose(angle_min, math.radians(135.0), abs_tol=1e-6)

    angle_max = val_to_angle_rad(100.0, 0.0, 100.0, 135.0, 405.0)
    assert math.isclose(angle_max, math.radians(405.0), abs_tol=1e-6)


def test_val_to_angle_rad_nan_inf_guards():
    """Verify NaN and Infinity default safely to start_angle."""
    nan_angle = val_to_angle_rad(float("nan"))
    assert math.isclose(nan_angle, math.radians(135.0), abs_tol=1e-6)

    inf_angle = val_to_angle_rad(float("inf"))
    assert math.isclose(inf_angle, math.radians(135.0), abs_tol=1e-6)

    neginf_angle = val_to_angle_rad(float("-inf"))
    assert math.isclose(neginf_angle, math.radians(135.0), abs_tol=1e-6)


def test_val_to_angle_rad_invalid_bounds():
    """Verify max_val <= min_val defaults to start_angle."""
    angle = val_to_angle_rad(50.0, min_val=100.0, max_val=0.0)
    assert math.isclose(angle, math.radians(135.0), abs_tol=1e-6)


def test_val_to_angle_rad_clamped_below_min():
    """Verify value below min is clamped to start_angle."""
    angle = val_to_angle_rad(-10.0, 0.0, 100.0, 135.0, 405.0)
    assert math.isclose(angle, math.radians(135.0), abs_tol=1e-6)


def test_val_to_angle_rad_clamped_above_max():
    """Verify value above max is clamped to end_angle."""
    angle = val_to_angle_rad(150.0, 0.0, 100.0, 135.0, 405.0)
    assert math.isclose(angle, math.radians(405.0), abs_tol=1e-6)


def test_val_to_angle_rad_quarter_point():
    """Verify 25% value maps to 202.5 degrees."""
    angle = val_to_angle_rad(25.0, 0.0, 100.0, 135.0, 405.0)
    expected = math.radians(135.0 + 0.25 * 270.0)
    assert math.isclose(angle, expected, abs_tol=1e-6)


def test_telltale_manager_initialization():
    """Verify TelltaleManager initializes four default windows (1m, 10m, 1h, all_time)."""
    mgr = TelltaleManager()
    assert set(mgr.telltales.keys()) == {"1m", "10m", "1h", "all_time"}
    peaks = mgr.current_peaks()
    assert peaks == {"1m": None, "10m": None, "1h": None, "all_time": None}


def test_telltale_manager_custom_windows():
    """Verify TelltaleManager accepts custom window specification."""
    mgr = TelltaleManager(custom_windows={"1m": 30.0})
    assert set(mgr.telltales.keys()) == {"1m"}


def test_telltale_manager_update_and_peaks():
    """Verify sample updates propagate to all telltales."""
    mgr = TelltaleManager()
    t0 = 1000.0
    mgr.update(t0, 75.0)
    peaks = mgr.current_peaks(t0)
    assert peaks == {"1m": 75.0, "10m": 75.0, "1h": 75.0, "all_time": 75.0}


def test_telltale_manager_update_multiple_samples():
    """Verify peak holds maximum value across multiple updates."""
    mgr = TelltaleManager()
    t0 = 1000.0
    mgr.update(t0, 50.0)
    mgr.update(t0 + 1, 85.0)
    mgr.update(t0 + 2, 40.0)
    peaks = mgr.current_peaks(t0 + 2)
    assert peaks["all_time"] == 85.0


def test_telltale_manager_reset_single_and_all():
    """Verify reset clears targeted or all window peak states."""
    mgr = TelltaleManager()
    t0 = 1000.0
    mgr.update(t0, 80.0)

    mgr.reset("1m")
    peaks = mgr.current_peaks(t0)
    assert peaks["1m"] is None
    assert peaks["10m"] == 80.0

    mgr.reset()
    assert mgr.current_peaks(t0) == {"1m": None, "10m": None, "1h": None, "all_time": None}


def test_telltale_manager_reset_invalid_key():
    """Verify resetting an unknown window raises KeyError."""
    mgr = TelltaleManager()
    with pytest.raises(KeyError, match="Unknown window name: invalid"):
        mgr.reset("invalid")


def test_telltale_manager_reset_all_windows():
    """Verify reset(None) clears all windows."""
    mgr = TelltaleManager()
    t0 = 1000.0
    mgr.update(t0, 60.0)
    mgr.reset(None)
    peaks = mgr.current_peaks(t0)
    for v in peaks.values():
        assert v is None


def test_telltale_renderer_none_peaks_no_drawing():
    """Verify rendering with all None peaks produces an identical un-modified copy."""
    base = Image.new("RGBA", (256, 256), (50, 50, 50, 255))
    renderer = TelltaleRenderer()
    peaks = {"1m": None, "10m": None, "1h": None, "all_time": None}

    result = renderer.render_telltales(base, peaks, render_legend=False)
    assert result.size == (256, 256)
    assert result.getpixel((128, 128)) == (50, 50, 50, 255)


def test_telltale_renderer_returns_rgba():
    """Verify rendered result is always RGBA mode."""
    base = Image.new("RGB", (256, 256), (30, 30, 30))
    renderer = TelltaleRenderer()
    peaks = {"1m": 50.0, "10m": None, "1h": None, "all_time": None}
    result = renderer.render_telltales(base, peaks, render_legend=False)
    assert result.mode == "RGBA"


def test_telltale_renderer_size_preserved():
    """Verify output image dimensions match input dimensions."""
    base = Image.new("RGBA", (512, 512), (0, 0, 0, 255))
    renderer = TelltaleRenderer()
    peaks = {"1m": 50.0, "10m": 60.0, "1h": 70.0, "all_time": 80.0}
    result = renderer.render_telltales(base, peaks)
    assert result.size == (512, 512)


def test_telltale_renderer_draws_pixels():
    """Verify rendering active peaks modifies pixels relative to blank base."""
    base = Image.new("RGBA", (256, 256), (0, 0, 0, 255))
    renderer = TelltaleRenderer()
    peaks = {"1m": 50.0, "10m": None, "1h": None, "all_time": None}
    result = renderer.render_telltales(base, peaks, render_legend=False)

    from PIL import ImageChops
    diff = ImageChops.difference(base, result)
    assert diff.getbbox() is not None


def test_telltale_renderer_legend_drawn():
    """Verify legend box is rendered when render_legend=True and peaks are active."""
    base = Image.new("RGBA", (256, 256), (0, 0, 0, 255))
    renderer = TelltaleRenderer()
    peaks = {"1m": 50.0, "10m": None, "1h": None, "all_time": None}

    result_with_legend = renderer.render_telltales(base, peaks, render_legend=True)
    result_no_legend = renderer.render_telltales(base, peaks, render_legend=False)

    from PIL import ImageChops
    diff = ImageChops.difference(result_with_legend, result_no_legend)
    assert diff.getbbox() is not None, "Legend should add pixels when render_legend=True"


def test_telltale_renderer_no_legend_when_no_peaks():
    """Verify no legend is rendered when all peaks are None."""
    base = Image.new("RGBA", (256, 256), (20, 20, 20, 255))
    renderer = TelltaleRenderer()
    peaks = {"1m": None, "10m": None, "1h": None, "all_time": None}

    result = renderer.render_telltales(base, peaks, render_legend=True)
    assert result.getpixel((8, 8)) == (20, 20, 20, 255)


def test_telltale_style_frozen():
    """Verify TelltaleStyle is immutable (frozen dataclass)."""
    style = TelltaleStyle(
        window_name="1m",
        window_seconds=60.0,
        color_rgba=(0, 220, 255, 160),
        width_px=2,
        is_dashed=False,
        legend_label="1m Peak",
    )
    with pytest.raises((AttributeError, TypeError)):
        style.width_px = 5  # type: ignore[misc]


def test_gauge_geometry_defaults():
    """Verify GaugeGeometry uses documented default values."""
    geo = GaugeGeometry()
    assert geo.center_x == 128.0
    assert geo.center_y == 128.0
    assert geo.radius == 100.0
    assert geo.start_angle_deg == 135.0
    assert geo.end_angle_deg == 405.0
    assert geo.min_value == 0.0
    assert geo.max_value == 100.0


def test_gauge_geometry_frozen():
    """Verify GaugeGeometry is immutable (frozen dataclass)."""
    geo = GaugeGeometry()
    with pytest.raises((AttributeError, TypeError)):
        geo.radius = 200.0  # type: ignore[misc]


def test_telltale_manager_empty_peaks_before_update():
    """Verify all peaks are None before any update is called."""
    mgr = TelltaleManager()
    peaks = mgr.current_peaks(0.0)
    assert all(v is None for v in peaks.values())


def test_telltale_renderer_custom_geometry():
    """Verify TelltaleRenderer accepts custom GaugeGeometry."""
    geo = GaugeGeometry(center_x=64.0, center_y=64.0, radius=50.0)
    renderer = TelltaleRenderer(geometry=geo)
    assert renderer.geometry.center_x == 64.0
    assert renderer.geometry.radius == 50.0

    base = Image.new("RGBA", (128, 128), (10, 10, 10, 255))
    peaks = {"1m": 50.0, "10m": None, "1h": None, "all_time": None}
    result = renderer.render_telltales(base, peaks, render_legend=False)
    assert result.size == (128, 128)