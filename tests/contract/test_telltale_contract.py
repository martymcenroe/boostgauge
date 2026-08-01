"""Contract tests for public TelltaleManager and TelltaleRenderer interfaces.

Issue #2: peak-hold telltale needles — 1m, 10m, 1h, all-time
"""

import inspect
from typing import Dict, Optional, Tuple
from PIL import Image

from boostgauge.telltale_renderer import TelltaleManager, TelltaleRenderer, TelltaleStyle, DEFAULT_TELLTALE_STYLES


def test_telltale_manager_interface_contract():
    """Contract check: Verify TelltaleManager signature methods and return types."""
    mgr = TelltaleManager()
    assert hasattr(mgr, "update")
    assert hasattr(mgr, "reset_window")
    assert hasattr(mgr, "reset_all")
    assert hasattr(mgr, "get_peaks")

    sig_update = inspect.signature(mgr.update)
    assert list(sig_update.parameters.keys()) == ["timestamp", "value"]

    peaks = mgr.get_peaks()
    assert isinstance(peaks, dict)
    assert set(peaks.keys()) == {"1m", "10m", "1h", "all_time"}


def test_telltale_renderer_interface_contract():
    """Contract check: Verify TelltaleRenderer method signatures and PIL outputs."""
    renderer = TelltaleRenderer()
    assert hasattr(renderer, "val_to_angle_rad")
    assert hasattr(renderer, "draw_telltales")
    assert hasattr(renderer, "draw_legend")

    angle = renderer.val_to_angle_rad(50.0)
    assert isinstance(angle, float)

    img = Image.new("RGBA", (200, 200), (0, 0, 0, 255))
    peaks = {"1m": 50.0, "10m": None, "1h": None, "all_time": None}

    out_telltales = renderer.draw_telltales(img, peaks, center=(100.0, 100.0), radius=80.0)
    assert isinstance(out_telltales, Image.Image)
    assert out_telltales.size == (200, 200)

    out_legend = renderer.draw_legend(img, peaks, origin=(10.0, 10.0))
    assert isinstance(out_legend, Image.Image)
    assert out_legend.size == (200, 200)


def test_telltale_manager_update_signature_contract():
    """Contract check: update() accepts timestamp and value as positional args."""
    mgr = TelltaleManager()
    sig = inspect.signature(mgr.update)
    params = list(sig.parameters.keys())
    assert "timestamp" in params
    assert "value" in params


def test_telltale_manager_reset_window_signature_contract():
    """Contract check: reset_window() accepts window_name parameter."""
    mgr = TelltaleManager()
    sig = inspect.signature(mgr.reset_window)
    assert "window_name" in sig.parameters


def test_telltale_manager_get_peaks_signature_contract():
    """Contract check: get_peaks() accepts optional timestamp parameter."""
    mgr = TelltaleManager()
    sig = inspect.signature(mgr.get_peaks)
    assert "timestamp" in sig.parameters
    assert sig.parameters["timestamp"].default is None


def test_telltale_manager_get_peaks_return_type_contract():
    """Contract check: get_peaks() returns Dict[str, Optional[float]]."""
    mgr = TelltaleManager()
    peaks = mgr.get_peaks()
    assert isinstance(peaks, dict)
    for key, value in peaks.items():
        assert isinstance(key, str)
        assert value is None or isinstance(value, float)


def test_telltale_renderer_val_to_angle_rad_return_type_contract():
    """Contract check: val_to_angle_rad() returns float."""
    renderer = TelltaleRenderer()
    result = renderer.val_to_angle_rad(0.0)
    assert isinstance(result, float)
    result = renderer.val_to_angle_rad(50.0)
    assert isinstance(result, float)
    result = renderer.val_to_angle_rad(100.0)
    assert isinstance(result, float)


def test_telltale_renderer_draw_telltales_return_type_contract():
    """Contract check: draw_telltales() returns PIL.Image in RGBA mode."""
    renderer = TelltaleRenderer()
    img = Image.new("RGBA", (100, 100), (0, 0, 0, 255))
    peaks = {"1m": 50.0, "10m": None, "1h": None, "all_time": None}
    result = renderer.draw_telltales(img, peaks, center=(50.0, 50.0), radius=40.0)
    assert isinstance(result, Image.Image)
    assert result.mode == "RGBA"


def test_telltale_renderer_draw_legend_return_type_contract():
    """Contract check: draw_legend() returns PIL.Image in RGBA mode."""
    renderer = TelltaleRenderer()
    img = Image.new("RGBA", (100, 100), (0, 0, 0, 255))
    peaks = {"1m": 50.0, "10m": 75.0, "1h": 80.0, "all_time": 95.0}
    result = renderer.draw_legend(img, peaks, origin=(10.0, 10.0))
    assert isinstance(result, Image.Image)
    assert result.mode == "RGBA"


def test_telltale_renderer_draw_telltales_signature_contract():
    """Contract check: draw_telltales() accepts required and optional parameters."""
    renderer = TelltaleRenderer()
    sig = inspect.signature(renderer.draw_telltales)
    params = sig.parameters
    assert "image" in params
    assert "peaks" in params
    assert "center" in params
    assert "radius" in params
    assert "supersample_factor" in params
    assert params["supersample_factor"].default == 4


def test_telltale_renderer_draw_legend_signature_contract():
    """Contract check: draw_legend() accepts required and optional parameters."""
    renderer = TelltaleRenderer()
    sig = inspect.signature(renderer.draw_legend)
    params = sig.parameters
    assert "image" in params
    assert "peaks" in params
    assert "origin" in params
    assert "supersample_factor" in params
    assert params["supersample_factor"].default == 4


def test_telltale_style_dataclass_contract():
    """Contract check: TelltaleStyle is a frozen dataclass with required fields."""
    style = TelltaleStyle(
        window_name="1m",
        window_seconds=60.0,
        color=(0, 225, 255, 180),
        width=3,
        line_style="solid",
        description="1 Min Peak",
    )
    assert style.window_name == "1m"
    assert style.window_seconds == 60.0
    assert style.color == (0, 225, 255, 180)
    assert style.width == 3
    assert style.line_style == "solid"
    assert style.description == "1 Min Peak"


def test_telltale_style_is_immutable_contract():
    """Contract check: TelltaleStyle instances are immutable (frozen dataclass)."""
    import pytest

    style = TelltaleStyle(
        window_name="test",
        window_seconds=120.0,
        color=(255, 0, 0, 180),
        width=3,
        line_style="solid",
        description="Test",
    )
    with pytest.raises((AttributeError, TypeError)):
        style.width = 10  # type: ignore[misc]


def test_default_telltale_styles_contract():
    """Contract check: DEFAULT_TELLTALE_STYLES has all four required window keys."""
    assert set(DEFAULT_TELLTALE_STYLES.keys()) == {"1m", "10m", "1h", "all_time"}
    for key, style in DEFAULT_TELLTALE_STYLES.items():
        assert isinstance(style, TelltaleStyle)
        assert style.window_name == key
        assert len(style.color) == 4
        assert all(0 <= c <= 255 for c in style.color)


def test_telltale_manager_telltales_attribute_contract():
    """Contract check: TelltaleManager exposes telltales as a dict attribute."""
    mgr = TelltaleManager()
    assert hasattr(mgr, "telltales")
    assert isinstance(mgr.telltales, dict)
    assert len(mgr.telltales) == 4


def test_telltale_manager_custom_windows_contract():
    """Contract check: TelltaleManager accepts custom_windows dict."""
    mgr = TelltaleManager(custom_windows={"short": 30.0, "long": 1800.0})
    assert set(mgr.telltales.keys()) == {"short", "long"}
    peaks = mgr.get_peaks()
    assert isinstance(peaks, dict)
    assert set(peaks.keys()) == {"short", "long"}


def test_telltale_manager_reset_all_contract():
    """Contract check: reset_all() clears all window peaks."""
    mgr = TelltaleManager()
    t0 = 2000.0
    mgr.update(t0, 75.0)

    peaks_before = mgr.get_peaks(timestamp=t0)
    assert any(v is not None for v in peaks_before.values())

    mgr.reset_all()
    peaks_after = mgr.get_peaks(timestamp=t0)
    assert all(v is None for v in peaks_after.values())


def test_telltale_renderer_init_signature_contract():
    """Contract check: TelltaleRenderer accepts min/max val and angle parameters."""
    sig = inspect.signature(TelltaleRenderer.__init__)
    params = sig.parameters
    assert "min_val" in params
    assert "max_val" in params
    assert "min_angle_deg" in params
    assert "max_angle_deg" in params
    assert "styles" in params
    assert params["min_val"].default == 0.0
    assert params["max_val"].default == 100.0
    assert params["min_angle_deg"].default == 225.0
    assert params["max_angle_deg"].default == -45.0


def test_telltale_renderer_preserves_image_size_contract():
    """Contract check: Both draw methods return image with same dimensions as input."""
    renderer = TelltaleRenderer()
    for size in [(100, 100), (200, 300), (512, 512)]:
        img = Image.new("RGBA", size, (0, 0, 0, 255))
        peaks = {"1m": 50.0, "10m": None, "1h": None, "all_time": None}
        result_telltales = renderer.draw_telltales(img, peaks, center=(size[0] / 2, size[1] / 2), radius=40.0)
        assert result_telltales.size == size
        result_legend = renderer.draw_legend(img, peaks, origin=(10.0, 10.0))
        assert result_legend.size == size


def test_telltale_manager_update_clamps_value_contract():
    """Contract check: update() sanitizes values outside [0, 100] range."""
    mgr = TelltaleManager()
    t0 = 1000.0
    mgr.update(t0, -999.0)
    peaks_low = mgr.get_peaks(timestamp=t0)
    assert peaks_low["all_time"] == 0.0

    mgr.reset_all()
    mgr.update(t0, 999.0)
    peaks_high = mgr.get_peaks(timestamp=t0)
    assert peaks_high["all_time"] == 100.0