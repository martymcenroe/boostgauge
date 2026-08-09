"""Contract tests validating TelltaleManager and TelltaleRenderer public interfaces.

Issue #2: Feature: peak-hold telltale needles — 1m, 10m, 1h, all-time
"""

import pytest
from PIL import Image

from boostgauge.telltale_renderer import (
    GaugeGeometry,
    TelltaleManager,
    TelltaleRenderer,
)


def test_telltale_manager_contract_methods():
    """Validate public method signatures and types for TelltaleManager."""
    mgr = TelltaleManager()
    assert hasattr(mgr, "update")
    assert hasattr(mgr, "current_peaks")
    assert hasattr(mgr, "reset")

    mgr.update(100.0, 50.0)
    peaks = mgr.current_peaks(100.0)
    assert isinstance(peaks, dict)
    assert set(peaks.keys()) == {"1m", "10m", "1h", "all_time"}

    mgr.reset("1m")
    assert mgr.current_peaks(100.0)["1m"] is None


def test_telltale_renderer_contract_methods():
    """Validate public method signatures and return types for TelltaleRenderer."""
    renderer = TelltaleRenderer(GaugeGeometry())
    assert hasattr(renderer, "render_telltales")

    base = Image.new("RGBA", (256, 256), (0, 0, 0, 255))
    peaks = {"1m": 25.0, "10m": 50.0, "1h": 75.0, "all_time": 100.0}

    out = renderer.render_telltales(base, peaks, render_legend=True)
    assert isinstance(out, Image.Image)
    assert out.mode == "RGBA"
    assert out.size == (256, 256)


def test_telltale_manager_default_windows_contract():
    """Validate TelltaleManager exposes exactly the four default windows."""
    mgr = TelltaleManager()
    assert isinstance(mgr.telltales, dict)
    assert set(mgr.telltales.keys()) == {"1m", "10m", "1h", "all_time"}


def test_telltale_manager_update_return_type():
    """Validate update() returns None."""
    mgr = TelltaleManager()
    result = mgr.update(0.0, 42.0)
    assert result is None


def test_telltale_manager_current_peaks_return_type():
    """Validate current_peaks() returns dict with string keys and float-or-None values."""
    mgr = TelltaleManager()
    peaks = mgr.current_peaks()
    assert isinstance(peaks, dict)
    for k, v in peaks.items():
        assert isinstance(k, str)
        assert v is None or isinstance(v, float)


def test_telltale_manager_current_peaks_with_time():
    """Validate current_peaks() accepts an optional float timestamp."""
    mgr = TelltaleManager()
    mgr.update(500.0, 33.0)
    peaks = mgr.current_peaks(500.0)
    assert isinstance(peaks, dict)
    assert peaks["all_time"] == 33.0


def test_telltale_manager_reset_none_contract():
    """Validate reset(None) resets all windows and returns None."""
    mgr = TelltaleManager()
    mgr.update(0.0, 99.0)
    result = mgr.reset(None)
    assert result is None
    peaks = mgr.current_peaks(0.0)
    assert all(v is None for v in peaks.values())


def test_telltale_manager_reset_named_contract():
    """Validate reset(name) clears only the named window."""
    mgr = TelltaleManager()
    mgr.update(0.0, 77.0)
    mgr.reset("10m")
    peaks = mgr.current_peaks(0.0)
    assert peaks["10m"] is None
    assert peaks["1m"] == 77.0
    assert peaks["1h"] == 77.0
    assert peaks["all_time"] == 77.0


def test_telltale_manager_reset_invalid_raises_keyerror():
    """Validate reset() raises KeyError for unknown window names."""
    mgr = TelltaleManager()
    with pytest.raises(KeyError):
        mgr.reset("nonexistent_window")


def test_telltale_renderer_accepts_geometry():
    """Validate TelltaleRenderer stores provided GaugeGeometry."""
    geo = GaugeGeometry(center_x=64.0, center_y=64.0, radius=50.0)
    renderer = TelltaleRenderer(geometry=geo)
    assert renderer.geometry is geo


def test_telltale_renderer_default_geometry():
    """Validate TelltaleRenderer uses default GaugeGeometry when none provided."""
    renderer = TelltaleRenderer()
    assert isinstance(renderer.geometry, GaugeGeometry)
    assert renderer.geometry.center_x == 128.0
    assert renderer.geometry.center_y == 128.0
    assert renderer.geometry.radius == 100.0


def test_telltale_renderer_render_telltales_return_type():
    """Validate render_telltales() returns a PIL Image."""
    renderer = TelltaleRenderer()
    base = Image.new("RGBA", (256, 256), (10, 10, 10, 255))
    peaks = {"1m": None, "10m": None, "1h": None, "all_time": None}
    out = renderer.render_telltales(base, peaks)
    assert isinstance(out, Image.Image)


def test_telltale_renderer_output_is_rgba():
    """Validate render_telltales() always returns RGBA mode image."""
    renderer = TelltaleRenderer()
    base_rgb = Image.new("RGB", (256, 256), (50, 50, 50))
    peaks = {"1m": 50.0, "10m": None, "1h": None, "all_time": None}
    out = renderer.render_telltales(base_rgb, peaks)
    assert out.mode == "RGBA"


def test_telltale_renderer_output_size_matches_input():
    """Validate render_telltales() preserves input image dimensions."""
    renderer = TelltaleRenderer()
    for size in [(256, 256), (128, 128), (512, 512)]:
        base = Image.new("RGBA", size, (0, 0, 0, 255))
        peaks = {"1m": 50.0, "10m": None, "1h": None, "all_time": None}
        out = renderer.render_telltales(base, peaks)
        assert out.size == size


def test_telltale_renderer_does_not_mutate_base():
    """Validate render_telltales() returns a new image, leaving base unchanged."""
    base = Image.new("RGBA", (256, 256), (77, 77, 77, 255))
    renderer = TelltaleRenderer()
    peaks = {"1m": 50.0, "10m": 60.0, "1h": 70.0, "all_time": 80.0}
    out = renderer.render_telltales(base, peaks)
    assert out is not base
    assert base.getpixel((128, 128)) == (77, 77, 77, 255)


def test_telltale_renderer_render_legend_flag_accepted():
    """Validate render_telltales() accepts render_legend keyword argument."""
    renderer = TelltaleRenderer()
    base = Image.new("RGBA", (256, 256), (0, 0, 0, 255))
    peaks = {"1m": 50.0, "10m": None, "1h": None, "all_time": None}
    out_with = renderer.render_telltales(base, peaks, render_legend=True)
    out_without = renderer.render_telltales(base, peaks, render_legend=False)
    assert isinstance(out_with, Image.Image)
    assert isinstance(out_without, Image.Image)


def test_telltale_manager_custom_windows_contract():
    """Validate TelltaleManager accepts custom_windows and reflects them in keys."""
    custom = {"fast": 10.0, "slow": 300.0}
    mgr = TelltaleManager(custom_windows=custom)
    assert set(mgr.telltales.keys()) == {"fast", "slow"}
    peaks = mgr.current_peaks()
    assert set(peaks.keys()) == {"fast", "slow"}