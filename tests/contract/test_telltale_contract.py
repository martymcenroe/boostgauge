"""Contract tests validating public interfaces and parameter contracts for TelltaleManager and TelltaleRenderer.

Issue #2: Feature: peak-hold telltale needles — 1m, 10m, 1h, all-time
"""

from typing import Dict, Optional

import pytest
from PIL import Image

from boostgauge.telltale_renderer import (
    GaugeGeometry,
    TelltaleManager,
    TelltaleRenderer,
    TelltaleStyle,
)


def test_telltale_manager_interface_contract():
    """Verify TelltaleManager input parameter contracts and return types."""
    mgr = TelltaleManager(windows={"1m": 60.0, "all_time": None})
    mgr.update(100.0, 50.0)

    peaks = mgr.get_peaks(current_time=100.0)
    assert isinstance(peaks, dict)
    assert "1m" in peaks
    assert "all_time" in peaks

    mgr.reset("1m")
    assert mgr.get_peaks()["1m"] is None


def test_telltale_renderer_interface_contract():
    """Verify TelltaleRenderer interface contract and PIL output mode/size."""
    geom = GaugeGeometry(center_x=100.0, center_y=100.0, radius=80.0)
    renderer = TelltaleRenderer(geometry=geom)
    base = Image.new("RGBA", (200, 200), (0, 0, 0, 255))
    peaks: Dict[str, Optional[float]] = {"1m": 30.0, "10m": 50.0, "1h": 70.0, "all_time": 90.0}

    out = renderer.render_telltales(base, peaks)
    assert isinstance(out, Image.Image)
    assert out.mode == "RGBA"
    assert out.size == (200, 200)


def test_telltale_manager_default_windows_contract():
    """Verify TelltaleManager default windows produce the canonical four keys."""
    mgr = TelltaleManager()
    peaks = mgr.get_peaks()
    assert set(peaks.keys()) == {"1m", "10m", "1h", "all_time"}
    assert all(v is None for v in peaks.values())


def test_telltale_manager_update_return_type():
    """Verify TelltaleManager.update() returns None."""
    mgr = TelltaleManager()
    result = mgr.update(1000.0, 42.0)
    assert result is None


def test_telltale_manager_reset_return_type():
    """Verify TelltaleManager.reset() returns None for both named and all-reset calls."""
    mgr = TelltaleManager()
    mgr.update(1000.0, 42.0)
    assert mgr.reset("1m") is None
    assert mgr.reset() is None


def test_telltale_manager_get_peaks_return_type():
    """Verify TelltaleManager.get_peaks() always returns a dict."""
    mgr = TelltaleManager()
    result = mgr.get_peaks()
    assert isinstance(result, dict)


def test_telltale_manager_get_peaks_values_are_float_or_none():
    """Verify get_peaks() values are float or None, never other types."""
    mgr = TelltaleManager()
    mgr.update(1000.0, 75.5)
    peaks = mgr.get_peaks(current_time=1000.0)
    for v in peaks.values():
        assert v is None or isinstance(v, float)


def test_telltale_manager_reset_unknown_window_raises_key_error():
    """Verify reset() raises KeyError for an unknown window name."""
    mgr = TelltaleManager()
    with pytest.raises(KeyError):
        mgr.reset("nonexistent")


def test_telltale_manager_custom_windows_contract():
    """Verify TelltaleManager accepts arbitrary custom window dicts."""
    custom = {"short": 5.0, "medium": 300.0, "long": None}
    mgr = TelltaleManager(windows=custom)
    peaks = mgr.get_peaks()
    assert set(peaks.keys()) == {"short", "medium", "long"}


def test_telltale_renderer_geometry_stored():
    """Verify TelltaleRenderer stores geometry as provided."""
    geom = GaugeGeometry(center_x=64.0, center_y=64.0, radius=50.0)
    renderer = TelltaleRenderer(geometry=geom)
    assert renderer.geometry is geom


def test_telltale_renderer_default_styles_contract():
    """Verify TelltaleRenderer default styles list has four entries with required fields."""
    geom = GaugeGeometry(center_x=128.0, center_y=128.0, radius=100.0)
    renderer = TelltaleRenderer(geometry=geom)
    assert len(renderer.styles) == 4
    for style in renderer.styles:
        assert isinstance(style, TelltaleStyle)
        assert isinstance(style.window_name, str)
        assert isinstance(style.color_rgba, tuple) and len(style.color_rgba) == 4
        assert isinstance(style.width_px, int) and style.width_px >= 1
        assert isinstance(style.legend_label, str)


def test_telltale_renderer_show_legend_stored():
    """Verify TelltaleRenderer stores show_legend as provided."""
    geom = GaugeGeometry(center_x=128.0, center_y=128.0, radius=100.0)
    renderer_on = TelltaleRenderer(geometry=geom, show_legend=True)
    renderer_off = TelltaleRenderer(geometry=geom, show_legend=False)
    assert renderer_on.show_legend is True
    assert renderer_off.show_legend is False


def test_telltale_renderer_render_telltales_returns_image():
    """Verify render_telltales() returns a PIL Image instance."""
    geom = GaugeGeometry(center_x=128.0, center_y=128.0, radius=100.0)
    renderer = TelltaleRenderer(geometry=geom, show_legend=False)
    base = Image.new("RGBA", (256, 256), (0, 0, 0, 255))
    out = renderer.render_telltales(base, {})
    assert isinstance(out, Image.Image)


def test_telltale_renderer_render_telltales_preserves_size():
    """Verify render_telltales() output size matches input size."""
    geom = GaugeGeometry(center_x=64.0, center_y=64.0, radius=50.0)
    renderer = TelltaleRenderer(geometry=geom, show_legend=False)
    base = Image.new("RGBA", (128, 128), (10, 10, 10, 255))
    out = renderer.render_telltales(base, {"1m": 50.0})
    assert out.size == (128, 128)


def test_telltale_renderer_render_telltales_output_rgba():
    """Verify render_telltales() always returns RGBA mode image."""
    geom = GaugeGeometry(center_x=128.0, center_y=128.0, radius=100.0)
    renderer = TelltaleRenderer(geometry=geom, show_legend=False)
    base = Image.new("RGBA", (256, 256), (0, 0, 0, 255))
    out = renderer.render_telltales(base, {"1m": 25.0})
    assert out.mode == "RGBA"


def test_telltale_renderer_none_peaks_no_pixel_change():
    """Verify None peaks leave image pixels unchanged."""
    geom = GaugeGeometry(center_x=128.0, center_y=128.0, radius=100.0)
    renderer = TelltaleRenderer(geometry=geom, show_legend=False)
    base = Image.new("RGBA", (256, 256), (14, 16, 20, 255))
    peaks: Dict[str, Optional[float]] = {"1m": None, "10m": None, "1h": None, "all_time": None}
    out = renderer.render_telltales(base, peaks)
    assert list(out.getdata()) == list(base.getdata())


def test_telltale_renderer_empty_peaks_no_pixel_change():
    """Verify empty peaks dict leaves image pixels unchanged."""
    geom = GaugeGeometry(center_x=128.0, center_y=128.0, radius=100.0)
    renderer = TelltaleRenderer(geometry=geom, show_legend=False)
    base = Image.new("RGBA", (256, 256), (14, 16, 20, 255))
    out = renderer.render_telltales(base, {})
    assert list(out.getdata()) == list(base.getdata())


def test_telltale_renderer_render_legend_returns_image():
    """Verify render_legend() returns a PIL Image instance."""
    geom = GaugeGeometry(center_x=128.0, center_y=128.0, radius=100.0)
    renderer = TelltaleRenderer(geometry=geom)
    base = Image.new("RGBA", (256, 256), (0, 0, 0, 255))
    out = renderer.render_legend(base)
    assert isinstance(out, Image.Image)


def test_telltale_renderer_render_legend_preserves_size():
    """Verify render_legend() output size matches input size."""
    geom = GaugeGeometry(center_x=128.0, center_y=128.0, radius=100.0)
    renderer = TelltaleRenderer(geometry=geom)
    base = Image.new("RGBA", (256, 256), (0, 0, 0, 255))
    out = renderer.render_legend(base)
    assert out.size == (256, 256)


def test_telltale_renderer_render_legend_output_rgba():
    """Verify render_legend() returns RGBA mode image."""
    geom = GaugeGeometry(center_x=128.0, center_y=128.0, radius=100.0)
    renderer = TelltaleRenderer(geometry=geom)
    base = Image.new("RGBA", (256, 256), (0, 0, 0, 255))
    out = renderer.render_legend(base)
    assert out.mode == "RGBA"


def test_telltale_style_fields_contract():
    """Verify TelltaleStyle dataclass accepts and stores all required fields."""
    style = TelltaleStyle(
        window_name="test",
        window_seconds=120.0,
        color_rgba=(100, 200, 50, 180),
        width_px=2,
        dash_pattern=(4, 4),
        legend_label="Test",
    )
    assert style.window_name == "test"
    assert style.window_seconds == 120.0
    assert style.color_rgba == (100, 200, 50, 180)
    assert style.width_px == 2
    assert style.dash_pattern == (4, 4)
    assert style.legend_label == "Test"


def test_telltale_style_none_window_seconds_contract():
    """Verify TelltaleStyle accepts None for window_seconds (all-time window)."""
    style = TelltaleStyle(
        window_name="all_time",
        window_seconds=None,
        color_rgba=(255, 50, 50, 220),
        width_px=1,
        dash_pattern=None,
        legend_label="All",
    )
    assert style.window_seconds is None
    assert style.dash_pattern is None


def test_gauge_geometry_fields_contract():
    """Verify GaugeGeometry dataclass stores all fields with defaults."""
    geom = GaugeGeometry(center_x=64.0, center_y=64.0, radius=50.0)
    assert geom.center_x == 64.0
    assert geom.center_y == 64.0
    assert geom.radius == 50.0
    assert geom.start_angle_deg == 225.0
    assert geom.end_angle_deg == -45.0
    assert geom.min_value == 0.0
    assert geom.max_value == 100.0


def test_gauge_geometry_custom_fields_contract():
    """Verify GaugeGeometry accepts custom angle and value range overrides."""
    geom = GaugeGeometry(
        center_x=100.0,
        center_y=100.0,
        radius=80.0,
        start_angle_deg=180.0,
        end_angle_deg=0.0,
        min_value=10.0,
        max_value=200.0,
    )
    assert geom.start_angle_deg == 180.0
    assert geom.end_angle_deg == 0.0
    assert geom.min_value == 10.0
    assert geom.max_value == 200.0