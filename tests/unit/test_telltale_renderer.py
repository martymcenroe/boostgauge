"""Unit tests for TelltaleRenderer, TelltaleManager, and val_to_angle_rad.

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
    val_to_angle_rad,
)


def test_val_to_angle_rad_midpoint():
    """Test val_to_angle_rad maps 50% value to 90 degrees in radians."""
    rad = val_to_angle_rad(50.0, 0.0, 100.0, 225.0, -45.0)
    expected_deg = 90.0
    assert pytest.approx(rad, abs=1e-5) == math.radians(expected_deg)


def test_val_to_angle_rad_bounds():
    """Test val_to_angle_rad clamps min and max values."""
    min_rad = val_to_angle_rad(-10.0, 0.0, 100.0, 225.0, -45.0)
    max_rad = val_to_angle_rad(110.0, 0.0, 100.0, 225.0, -45.0)
    assert pytest.approx(min_rad, abs=1e-5) == math.radians(225.0)
    assert pytest.approx(max_rad, abs=1e-5) == math.radians(-45.0)


def test_val_to_angle_rad_nan_inf():
    """Test NaN and Inf handling in val_to_angle_rad."""
    nan_rad = val_to_angle_rad(float("nan"), 0.0, 100.0, 225.0, -45.0)
    inf_rad = val_to_angle_rad(float("inf"), 0.0, 100.0, 225.0, -45.0)
    neginf_rad = val_to_angle_rad(float("-inf"), 0.0, 100.0, 225.0, -45.0)

    assert pytest.approx(nan_rad, abs=1e-5) == math.radians(225.0)
    assert pytest.approx(inf_rad, abs=1e-5) == math.radians(-45.0)
    assert pytest.approx(neginf_rad, abs=1e-5) == math.radians(225.0)


def test_val_to_angle_rad_min_value():
    """Test val_to_angle_rad returns start angle for min value."""
    rad = val_to_angle_rad(0.0, 0.0, 100.0, 225.0, -45.0)
    assert pytest.approx(rad, abs=1e-5) == math.radians(225.0)


def test_val_to_angle_rad_max_value():
    """Test val_to_angle_rad returns end angle for max value."""
    rad = val_to_angle_rad(100.0, 0.0, 100.0, 225.0, -45.0)
    assert pytest.approx(rad, abs=1e-5) == math.radians(-45.0)


def test_val_to_angle_rad_zero_range():
    """Test val_to_angle_rad with zero range returns start angle."""
    rad = val_to_angle_rad(50.0, 50.0, 50.0, 225.0, -45.0)
    assert pytest.approx(rad, abs=1e-5) == math.radians(225.0)


def test_telltale_manager_default_init():
    """Test TelltaleManager default initialization creates four telltales."""
    mgr = TelltaleManager()
    assert len(mgr.telltales) == 4
    assert set(mgr.telltales.keys()) == {"1m", "10m", "1h", "all_time"}


def test_telltale_manager_custom_windows():
    """Test TelltaleManager with custom windows dict."""
    mgr = TelltaleManager(windows={"fast": 10.0, "slow": 300.0})
    assert set(mgr.telltales.keys()) == {"fast", "slow"}


def test_telltale_manager_init_and_update():
    """Test TelltaleManager updates peaks across all four windows."""
    mgr = TelltaleManager()
    t0 = 1000.0
    mgr.update(t0, 42.0)
    peaks = mgr.get_peaks(current_time=t0)

    assert len(peaks) == 4
    assert set(peaks.keys()) == {"1m", "10m", "1h", "all_time"}
    for k in peaks:
        assert peaks[k] == 42.0


def test_telltale_manager_update_multiple_samples():
    """Test TelltaleManager tracks the peak across multiple updates."""
    mgr = TelltaleManager()
    t0 = 1000.0
    mgr.update(t0, 50.0)
    mgr.update(t0 + 1, 80.0)
    mgr.update(t0 + 2, 60.0)
    peaks = mgr.get_peaks(current_time=t0 + 2)

    for k in peaks:
        assert peaks[k] == 80.0


def test_telltale_manager_reset_single_and_all():
    """Test resetting single window and resetting all windows."""
    mgr = TelltaleManager()
    t0 = 1000.0
    mgr.update(t0, 85.0)

    mgr.reset("1m")
    peaks = mgr.get_peaks(current_time=t0)
    assert peaks["1m"] is None
    assert peaks["10m"] == 85.0

    mgr.reset()
    all_peaks = mgr.get_peaks(current_time=t0)
    for k in all_peaks:
        assert all_peaks[k] is None


def test_telltale_manager_reset_invalid_key():
    """Test resetting an unknown window name raises KeyError."""
    mgr = TelltaleManager()
    with pytest.raises(KeyError):
        mgr.reset("nonexistent_window")


def test_telltale_manager_get_peaks_no_samples():
    """Test get_peaks returns None for all windows with no samples."""
    mgr = TelltaleManager()
    peaks = mgr.get_peaks()
    for k in peaks:
        assert peaks[k] is None


def test_telltale_manager_all_time_window():
    """Test all_time window uses infinity so samples never expire."""
    mgr = TelltaleManager()
    t0 = 1000.0
    mgr.update(t0, 99.0)
    # Query far in the future; all_time should still hold the peak
    peaks = mgr.get_peaks(current_time=t0 + 1_000_000)
    assert peaks["all_time"] == 99.0


def test_telltale_renderer_init_defaults():
    """Test TelltaleRenderer initializes with default styles when None provided."""
    geom = GaugeGeometry(center_x=128.0, center_y=128.0, radius=100.0)
    renderer = TelltaleRenderer(geometry=geom)
    assert renderer.geometry is geom
    assert len(renderer.styles) == 4
    assert renderer.show_legend is True


def test_telltale_renderer_none_peaks_skipped():
    """Test that None peak values produce identical image to base canvas."""
    geom = GaugeGeometry(center_x=128.0, center_y=128.0, radius=100.0)
    renderer = TelltaleRenderer(geometry=geom, show_legend=False)
    base = Image.new("RGBA", (256, 256), (14, 16, 20, 255))
    peaks = {"1m": None, "10m": None, "1h": None, "all_time": None}

    res = renderer.render_telltales(base, peaks)
    assert list(res.getdata()) == list(base.getdata())


def test_telltale_renderer_draws_needle_when_peak_set():
    """Test that a non-None peak value causes pixel changes in the rendered image."""
    geom = GaugeGeometry(center_x=128.0, center_y=128.0, radius=100.0)
    renderer = TelltaleRenderer(geometry=geom, show_legend=False)
    base = Image.new("RGBA", (256, 256), (0, 0, 0, 255))
    peaks = {"1m": 50.0, "10m": None, "1h": None, "all_time": None}

    res = renderer.render_telltales(base, peaks)
    assert list(res.getdata()) != list(base.getdata())


def test_telltale_renderer_output_mode_and_size():
    """Test render_telltales returns RGBA image of same size as input."""
    geom = GaugeGeometry(center_x=128.0, center_y=128.0, radius=100.0)
    renderer = TelltaleRenderer(geometry=geom, show_legend=False)
    base = Image.new("RGBA", (256, 256), (0, 0, 0, 255))
    peaks = {"1m": 50.0}

    res = renderer.render_telltales(base, peaks)
    assert isinstance(res, Image.Image)
    assert res.mode == "RGBA"
    assert res.size == (256, 256)


def test_telltale_renderer_raises_on_non_rgba_input():
    """Test render_telltales raises ValueError for non-RGBA base image."""
    geom = GaugeGeometry(center_x=128.0, center_y=128.0, radius=100.0)
    renderer = TelltaleRenderer(geometry=geom, show_legend=False)
    base = Image.new("RGB", (256, 256), (0, 0, 0))
    peaks = {"1m": 50.0}

    with pytest.raises(ValueError, match="RGBA"):
        renderer.render_telltales(base, peaks)


def test_telltale_renderer_legend_changes_image():
    """Test render_legend modifies the base image."""
    geom = GaugeGeometry(center_x=128.0, center_y=128.0, radius=100.0)
    renderer = TelltaleRenderer(geometry=geom, show_legend=True)
    base = Image.new("RGBA", (256, 256), (0, 0, 0, 255))

    with_legend = renderer.render_legend(base)
    assert list(with_legend.getdata()) != list(base.getdata())


def test_telltale_renderer_legend_output_size():
    """Test render_legend returns same-size RGBA image."""
    geom = GaugeGeometry(center_x=128.0, center_y=128.0, radius=100.0)
    renderer = TelltaleRenderer(geometry=geom)
    base = Image.new("RGBA", (256, 256), (0, 0, 0, 255))

    result = renderer.render_legend(base)
    assert result.mode == "RGBA"
    assert result.size == (256, 256)


def test_telltale_renderer_missing_peak_key_skipped():
    """Test that a missing key in peaks dict skips that needle without error."""
    geom = GaugeGeometry(center_x=128.0, center_y=128.0, radius=100.0)
    renderer = TelltaleRenderer(geometry=geom, show_legend=False)
    base = Image.new("RGBA", (256, 256), (0, 0, 0, 255))
    peaks = {}  # No keys at all

    res = renderer.render_telltales(base, peaks)
    assert list(res.getdata()) == list(base.getdata())


def test_telltale_renderer_custom_styles():
    """Test TelltaleRenderer uses provided styles instead of defaults."""
    from boostgauge.telltale_renderer import TelltaleStyle

    custom_style = TelltaleStyle(
        window_name="custom",
        window_seconds=120.0,
        color_rgba=(255, 0, 0, 255),
        width_px=3,
        dash_pattern=None,
        legend_label="Custom",
    )
    geom = GaugeGeometry(center_x=128.0, center_y=128.0, radius=100.0)
    renderer = TelltaleRenderer(geometry=geom, styles=[custom_style], show_legend=False)
    assert renderer.styles == [custom_style]


def test_platform_independent_path_check():
    """Platform-independent path comparison check."""
    p = Path("tests/unit/test_telltale_renderer.py")
    expected = Path("tests") / "unit" / "test_telltale_renderer.py"
    assert p.name == expected.name