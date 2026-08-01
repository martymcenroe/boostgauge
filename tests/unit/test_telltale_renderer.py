"""Unit tests for telltale angle mapping math, manager update dispatch, and window reset operations.

Issue #2: peak-hold telltale needles — 1m, 10m, 1h, all-time
"""

import math
import pytest

from boostgauge.telltale_renderer import TelltaleManager, TelltaleRenderer, DEFAULT_TELLTALE_STYLES


def test_t010_manager_initialization_default_windows():
    """T010: Manager creates 4 default Telltale instances (60s, 600s, 3600s, None)."""
    mgr = TelltaleManager()
    assert set(mgr.telltales.keys()) == {"1m", "10m", "1h", "all_time"}
    peaks = mgr.get_peaks()
    assert all(val is None for val in peaks.values())


def test_t020_forward_metric_updates():
    """T020: Metric updates are forwarded to all active window telltales."""
    mgr = TelltaleManager()
    t0 = 1000.0
    mgr.update(t0, 45.0)
    mgr.update(t0 + 10.0, 85.0)

    peaks = mgr.get_peaks(timestamp=t0 + 10.0)
    assert peaks["1m"] == 85.0
    assert peaks["10m"] == 85.0
    assert peaks["1h"] == 85.0
    assert peaks["all_time"] == 85.0


def test_t030_angle_mapping_math():
    """T030: Map metric values 0, 50, 100 to sweep angles 225°, 90°, -45° in radians."""
    renderer = TelltaleRenderer()

    angle_0 = renderer.val_to_angle_rad(0.0)
    assert math.isclose(angle_0, math.radians(225.0), rel_tol=1e-5)

    angle_50 = renderer.val_to_angle_rad(50.0)
    assert math.isclose(angle_50, math.radians(90.0), rel_tol=1e-5)

    angle_100 = renderer.val_to_angle_rad(100.0)
    assert math.isclose(angle_100, math.radians(-45.0), rel_tol=1e-5)


def test_t040_skip_rendering_none_peaks():
    """T040: Verify renderer omits telltale needles when peak value is None."""
    from PIL import Image

    renderer = TelltaleRenderer()
    base_img = Image.new("RGBA", (100, 100), (0, 0, 0, 255))
    peaks = {"1m": None, "10m": None, "1h": None, "all_time": None}

    result = renderer.draw_telltales(base_img, peaks, center=(50, 50), radius=40)
    assert result.getpixel((50, 50)) == (0, 0, 0, 255)
    assert result.getpixel((50, 10)) == (0, 0, 0, 255)


def test_t070_reset_window_and_reset_all():
    """T070: Test single window reset and reset_all operations."""
    mgr = TelltaleManager()
    t0 = 1000.0
    mgr.update(t0, 90.0)

    mgr.reset_window("1m")
    peaks_after_1m_reset = mgr.get_peaks(timestamp=t0)
    assert peaks_after_1m_reset["1m"] is None
    assert peaks_after_1m_reset["10m"] == 90.0

    mgr.reset_all()
    peaks_after_all_reset = mgr.get_peaks(timestamp=t0)
    assert all(v is None for v in peaks_after_all_reset.values())


def test_invalid_window_reset_raises_key_error():
    """Test resetting an unconfigured window raises KeyError."""
    mgr = TelltaleManager()
    with pytest.raises(KeyError, match="Unknown telltale window"):
        mgr.reset_window("invalid_window")


def test_invalid_window_duration_raises_value_error():
    """Test initializing manager with non-positive window duration raises ValueError."""
    with pytest.raises(ValueError, match="Window seconds must be positive"):
        TelltaleManager(custom_windows={"bad": -10.0})


def test_update_clamps_value_below_zero():
    """Metric values below 0 are clamped to 0.0 before dispatch."""
    mgr = TelltaleManager()
    t0 = 1000.0
    mgr.update(t0, -50.0)
    peaks = mgr.get_peaks(timestamp=t0)
    assert peaks["all_time"] == 0.0


def test_update_clamps_value_above_100():
    """Metric values above 100 are clamped to 100.0 before dispatch."""
    mgr = TelltaleManager()
    t0 = 1000.0
    mgr.update(t0, 150.0)
    peaks = mgr.get_peaks(timestamp=t0)
    assert peaks["all_time"] == 100.0


def test_val_to_angle_nan_maps_to_min():
    """NaN input to val_to_angle_rad defaults to min_val angle (225 degrees)."""
    renderer = TelltaleRenderer()
    angle = renderer.val_to_angle_rad(float("nan"))
    assert math.isclose(angle, math.radians(225.0), rel_tol=1e-5)


def test_val_to_angle_clamps_above_max():
    """Values above 100 clamp to max_val angle (-45 degrees)."""
    renderer = TelltaleRenderer()
    angle = renderer.val_to_angle_rad(200.0)
    assert math.isclose(angle, math.radians(-45.0), rel_tol=1e-5)


def test_val_to_angle_clamps_below_min():
    """Values below 0 clamp to min_val angle (225 degrees)."""
    renderer = TelltaleRenderer()
    angle = renderer.val_to_angle_rad(-50.0)
    assert math.isclose(angle, math.radians(225.0), rel_tol=1e-5)


def test_custom_windows_manager():
    """Manager initializes with custom window names and durations."""
    mgr = TelltaleManager(custom_windows={"fast": 30.0, "slow": 300.0})
    assert set(mgr.telltales.keys()) == {"fast", "slow"}
    peaks = mgr.get_peaks()
    assert all(v is None for v in peaks.values())


def test_get_peaks_no_samples_returns_all_none():
    """get_peaks with no prior updates returns None for all windows."""
    mgr = TelltaleManager()
    peaks = mgr.get_peaks()
    assert peaks == {"1m": None, "10m": None, "1h": None, "all_time": None}


def test_draw_telltales_returns_rgba_image():
    """draw_telltales returns an RGBA PIL Image of the same size as input."""
    from PIL import Image

    renderer = TelltaleRenderer()
    img = Image.new("RGBA", (200, 200), (10, 10, 10, 255))
    peaks = {"1m": 50.0, "10m": None, "1h": None, "all_time": None}
    result = renderer.draw_telltales(img, peaks, center=(100.0, 100.0), radius=80.0)
    assert result.mode == "RGBA"
    assert result.size == (200, 200)


def test_draw_telltales_converts_rgb_input():
    """draw_telltales accepts RGB input and converts to RGBA."""
    from PIL import Image

    renderer = TelltaleRenderer()
    img = Image.new("RGB", (100, 100), (0, 0, 0))
    peaks = {"1m": 25.0, "10m": None, "1h": None, "all_time": None}
    result = renderer.draw_telltales(img, peaks, center=(50.0, 50.0), radius=40.0)
    assert result.mode == "RGBA"


def test_draw_legend_returns_rgba_image():
    """draw_legend returns an RGBA PIL Image of the same size as input."""
    from PIL import Image

    renderer = TelltaleRenderer()
    img = Image.new("RGBA", (200, 200), (10, 10, 10, 255))
    peaks = {"1m": 50.0, "10m": 75.0, "1h": 80.0, "all_time": 95.0}
    result = renderer.draw_legend(img, peaks, origin=(10.0, 10.0))
    assert result.mode == "RGBA"
    assert result.size == (200, 200)


def test_reset_window_preserves_other_windows():
    """reset_window clears only the target window, leaving others intact."""
    mgr = TelltaleManager()
    t0 = 5000.0
    mgr.update(t0, 70.0)

    mgr.reset_window("10m")
    peaks = mgr.get_peaks(timestamp=t0)
    assert peaks["10m"] is None
    assert peaks["1m"] == 70.0
    assert peaks["1h"] == 70.0
    assert peaks["all_time"] == 70.0


def test_peak_tracks_maximum_not_latest():
    """Peak returns the maximum value seen, not the most recent."""
    mgr = TelltaleManager()
    t0 = 1000.0
    mgr.update(t0, 80.0)
    mgr.update(t0 + 1.0, 40.0)
    peaks = mgr.get_peaks(timestamp=t0 + 1.0)
    assert peaks["all_time"] == 80.0


def test_default_telltale_styles_have_expected_colors():
    """DEFAULT_TELLTALE_STYLES contains correct RGBA colors for each window."""
    assert DEFAULT_TELLTALE_STYLES["1m"].color == (0, 225, 255, 180)
    assert DEFAULT_TELLTALE_STYLES["10m"].color == (255, 140, 0, 180)
    assert DEFAULT_TELLTALE_STYLES["1h"].color == (220, 0, 220, 180)
    assert DEFAULT_TELLTALE_STYLES["all_time"].color == (255, 40, 40, 180)


def test_default_telltale_styles_window_seconds():
    """DEFAULT_TELLTALE_STYLES has correct window_seconds for each key."""
    assert DEFAULT_TELLTALE_STYLES["1m"].window_seconds == 60.0
    assert DEFAULT_TELLTALE_STYLES["10m"].window_seconds == 600.0
    assert DEFAULT_TELLTALE_STYLES["1h"].window_seconds == 3600.0
    assert DEFAULT_TELLTALE_STYLES["all_time"].window_seconds is None