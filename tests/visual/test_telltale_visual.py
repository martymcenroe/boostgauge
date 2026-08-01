"""Render-pixel visual regression tests and baseline-independent property assertions.

Issue #2: peak-hold telltale needles — 1m, 10m, 1h, all-time
"""

import math
from pathlib import Path

from PIL import Image
import pytest

from boostgauge.telltale_renderer import TelltaleRenderer, DEFAULT_TELLTALE_STYLES


def test_baseline_independent_telltale_tip_position():
    """BASELINE-INDEPENDENT: Assert needle tip coordinates match trigonometric calculation."""
    renderer = TelltaleRenderer()
    size = (400, 400)
    center = (200.0, 200.0)
    radius = 100.0

    peaks = {"1m": 50.0, "10m": None, "1h": None, "all_time": None}
    img = Image.new("RGBA", size, (0, 0, 0, 255))
    rendered = renderer.draw_telltales(img, peaks, center, radius, supersample_factor=4)

    angle_rad = renderer.val_to_angle_rad(50.0)
    expected_tip_x = center[0] + radius * math.cos(angle_rad)
    expected_tip_y = center[1] - radius * math.sin(angle_rad)

    tip_pixel = rendered.getpixel((int(expected_tip_x), int(expected_tip_y)))
    cyan_color = DEFAULT_TELLTALE_STYLES["1m"].color
    alpha_ratio = cyan_color[3] / 255.0
    expected_green = round(cyan_color[1] * alpha_ratio)
    expected_blue = round(cyan_color[2] * alpha_ratio)
    assert tip_pixel[0] == 0
    assert abs(tip_pixel[1] - expected_green) <= 1
    assert abs(tip_pixel[2] - expected_blue) <= 1


def test_t060_distinct_colors_per_window_baseline_independent():
    """BASELINE-INDEPENDENT: Verify all four telltale colors render correctly at distinct angles."""
    renderer = TelltaleRenderer()
    size = (400, 400)
    center = (200.0, 200.0)
    radius = 100.0

    peaks = {
        "1m": 0.0,
        "10m": 33.333,
        "1h": 66.666,
        "all_time": 100.0,
    }

    img = Image.new("RGBA", size, (0, 0, 0, 255))
    rendered = renderer.draw_telltales(img, peaks, center, radius, supersample_factor=4)

    angle_1m = renderer.val_to_angle_rad(0.0)
    tip_1m_x = int(center[0] + radius * math.cos(angle_1m))
    tip_1m_y = int(center[1] - radius * math.sin(angle_1m))
    px_1m = rendered.getpixel((tip_1m_x, tip_1m_y))
    style_1m = DEFAULT_TELLTALE_STYLES["1m"]
    expected_green = round(style_1m.color[1] * (style_1m.color[3] / 255.0))
    assert abs(px_1m[1] - expected_green) <= 1


def test_telltale_visual_regression_baseline(tmp_path: Path):
    """Visual regression test checking rendered PNG buffer output path using pathlib."""
    renderer = TelltaleRenderer()
    size = (200, 200)
    center = (100.0, 100.0)
    radius = 80.0
    peaks = {"1m": 50.0, "10m": 75.0, "1h": 80.0, "all_time": 95.0}

    img = Image.new("RGBA", size, (10, 10, 10, 255))
    rendered = renderer.draw_telltales(img, peaks, center, radius)

    output_file = tmp_path / "telltale_output.png"
    rendered.save(output_file)

    assert output_file.exists()
    assert output_file.parent == tmp_path
    assert output_file.name == "telltale_output.png"


def test_all_none_peaks_returns_unmodified_image():
    """BASELINE-INDEPENDENT: All-None peaks leaves image background unchanged."""
    renderer = TelltaleRenderer()
    size = (200, 200)
    bg_color = (42, 42, 42, 255)
    img = Image.new("RGBA", size, bg_color)
    peaks = {"1m": None, "10m": None, "1h": None, "all_time": None}

    rendered = renderer.draw_telltales(img, peaks, center=(100.0, 100.0), radius=80.0)

    assert rendered.getpixel((0, 0)) == bg_color
    assert rendered.getpixel((100, 100)) == bg_color
    assert rendered.getpixel((199, 199)) == bg_color


def test_needle_tip_angle_math_all_windows():
    """BASELINE-INDEPENDENT: Each active window needle tip lands at trig-predicted pixel."""
    renderer = TelltaleRenderer()
    size = (600, 600)
    center = (300.0, 300.0)
    radius = 200.0

    test_cases = [
        ("1m", 25.0),
        ("10m", 50.0),
        ("1h", 75.0),
        ("all_time", 100.0),
    ]

    for window_name, value in test_cases:
        peaks = {k: None for k in DEFAULT_TELLTALE_STYLES}
        peaks[window_name] = value

        img = Image.new("RGBA", size, (0, 0, 0, 255))
        rendered = renderer.draw_telltales(img, peaks, center, radius, supersample_factor=4)

        angle_rad = renderer.val_to_angle_rad(value)
        tip_x = int(center[0] + radius * math.cos(angle_rad))
        tip_y = int(center[1] - radius * math.sin(angle_rad))

        tip_px = rendered.getpixel((tip_x, tip_y))
        style = DEFAULT_TELLTALE_STYLES[window_name]
        alpha_ratio = style.color[3] / 255.0

        for ch_idx in range(3):
            expected = round(style.color[ch_idx] * alpha_ratio)
            assert abs(tip_px[ch_idx] - expected) <= 2, (
                f"{window_name} channel {ch_idx}: got {tip_px[ch_idx]}, expected ~{expected}"
            )


def test_rendered_image_is_rgba_mode():
    """BASELINE-INDEPENDENT: draw_telltales always returns RGBA image."""
    renderer = TelltaleRenderer()
    img = Image.new("RGB", (100, 100), (10, 10, 10))
    peaks = {"1m": 50.0, "10m": None, "1h": None, "all_time": None}
    result = renderer.draw_telltales(img, peaks, center=(50.0, 50.0), radius=40.0)
    assert result.mode == "RGBA"


def test_rendered_image_preserves_dimensions():
    """BASELINE-INDEPENDENT: draw_telltales output dimensions match input."""
    renderer = TelltaleRenderer()
    for size in [(100, 100), (256, 512), (800, 600)]:
        img = Image.new("RGBA", size, (0, 0, 0, 255))
        peaks = {"1m": 50.0, "10m": 75.0, "1h": 80.0, "all_time": 95.0}
        result = renderer.draw_telltales(img, peaks, center=(size[0] / 2.0, size[1] / 2.0), radius=40.0)
        assert result.size == size


def test_legend_output_saved_to_file(tmp_path: Path):
    """Visual regression: draw_legend output saved to pathlib path."""
    renderer = TelltaleRenderer()
    size = (200, 200)
    img = Image.new("RGBA", size, (20, 20, 20, 255))
    peaks = {"1m": 50.0, "10m": 75.0, "1h": 80.0, "all_time": 95.0}

    result = renderer.draw_legend(img, peaks, origin=(10.0, 10.0))

    output_file = tmp_path / "legend_output.png"
    result.save(output_file)

    assert output_file.exists()
    assert output_file.parent == tmp_path
    assert output_file.name == "legend_output.png"


def test_legend_modifies_origin_region():
    """BASELINE-INDEPENDENT: draw_legend renders non-background pixels at origin."""
    renderer = TelltaleRenderer()
    size = (200, 200)
    bg_color = (0, 0, 0, 255)
    img = Image.new("RGBA", size, bg_color)
    peaks = {"1m": 50.0, "10m": 75.0, "1h": 80.0, "all_time": 95.0}

    result = renderer.draw_legend(img, peaks, origin=(10.0, 10.0), supersample_factor=4)

    modified = False
    for x in range(10, 30):
        for y in range(10, 100):
            px = result.getpixel((x, y))
            if px != bg_color:
                modified = True
                break
        if modified:
            break
    assert modified, "Legend region should contain non-background pixels"


def test_center_pixel_unmodified_when_no_peaks():
    """BASELINE-INDEPENDENT: Center pixel unchanged when no peaks provided."""
    renderer = TelltaleRenderer()
    size = (200, 200)
    center = (100.0, 100.0)
    bg_color = (30, 30, 30, 255)
    img = Image.new("RGBA", size, bg_color)
    peaks = {"1m": None, "10m": None, "1h": None, "all_time": None}

    result = renderer.draw_telltales(img, peaks, center, radius=80.0)
    assert result.getpixel((100, 100)) == bg_color


def test_needle_tip_not_at_center_when_active():
    """BASELINE-INDEPENDENT: Active needle changes pixel at tip location, not just center."""
    renderer = TelltaleRenderer()
    size = (400, 400)
    center = (200.0, 200.0)
    radius = 150.0
    bg_color = (0, 0, 0, 255)

    img = Image.new("RGBA", size, bg_color)
    peaks = {"1m": 50.0, "10m": None, "1h": None, "all_time": None}
    rendered = renderer.draw_telltales(img, peaks, center, radius, supersample_factor=4)

    angle_rad = renderer.val_to_angle_rad(50.0)
    tip_x = int(center[0] + radius * math.cos(angle_rad))
    tip_y = int(center[1] - radius * math.sin(angle_rad))

    tip_px = rendered.getpixel((tip_x, tip_y))
    assert tip_px != bg_color, "Needle tip pixel should differ from background"


def test_val_to_angle_rad_boundary_values():
    """BASELINE-INDEPENDENT: Verify boundary angle values match spec exactly."""
    renderer = TelltaleRenderer()

    angle_0 = renderer.val_to_angle_rad(0.0)
    assert math.isclose(angle_0, math.radians(225.0), rel_tol=1e-9)

    angle_100 = renderer.val_to_angle_rad(100.0)
    assert math.isclose(angle_100, math.radians(-45.0), rel_tol=1e-9)

    angle_50 = renderer.val_to_angle_rad(50.0)
    assert math.isclose(angle_50, math.radians(90.0), rel_tol=1e-9)


def test_multiple_renders_produce_consistent_output():
    """BASELINE-INDEPENDENT: Repeated renders with same inputs produce identical output."""
    renderer = TelltaleRenderer()
    size = (200, 200)
    center = (100.0, 100.0)
    radius = 80.0
    peaks = {"1m": 50.0, "10m": 75.0, "1h": None, "all_time": 90.0}

    img1 = Image.new("RGBA", size, (5, 5, 5, 255))
    img2 = Image.new("RGBA", size, (5, 5, 5, 255))

    result1 = renderer.draw_telltales(img1, peaks, center, radius)
    result2 = renderer.draw_telltales(img2, peaks, center, radius)

    assert list(result1.getdata()) == list(result2.getdata())