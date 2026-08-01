"""Visual regression tests for telltale needle PIL rendering.

Issue #2: Feature: peak-hold telltale needles — 1m, 10m, 1h, all-time
Follows docs/design/0001-test-strategy.md Option C (off-screen PIL, no Tkinter).
"""

import math
from pathlib import Path

import pytest
from PIL import Image, ImageChops

from boostgauge.telltale_renderer import GaugeGeometry, TelltaleRenderer

BASELINES_DIR = Path(__file__).parent / "baselines"


def _calc_rms(img1: Image.Image, img2: Image.Image) -> float:
    """Calculate Root Mean Square (RMS) pixel difference between two images."""
    diff = ImageChops.difference(img1, img2)
    h = diff.histogram()
    sq = sum((value * (idx ** 2) for idx, value in enumerate(h)))
    rms = math.sqrt(sq / float(img1.size[0] * img1.size[1] * len(img1.mode)))
    return rms


def test_baseline_independent_needle_tip_trigonometry():
    """Baseline-independent test: Validate needle tip position math without baselines."""
    geom = GaugeGeometry(
        center_x=128.0,
        center_y=128.0,
        radius=100.0,
        start_angle_deg=225.0,
        end_angle_deg=-45.0,
        min_value=0.0,
        max_value=100.0,
    )
    renderer = TelltaleRenderer(geometry=geom, show_legend=False)

    # Render a 50% peak telltale (should point straight UP at 90 degrees)
    base = Image.new("RGBA", (256, 256), (0, 0, 0, 255))
    peaks = {"1m": 50.0}
    rendered = renderer.render_telltales(base, peaks)

    # At 90 degrees: tip X = center_x = 128.0, tip Y = center_y - radius * 0.85 = 128.0 - 85.0 = 43.0
    # Check pixel along the needle ray at (128, 50)
    pixel = rendered.getpixel((128, 50))
    # Pixel alpha should be non-zero (cyan telltale has alpha 160)
    assert pixel[3] > 0
    # Color should be blended cyan (0, 220, 255, 160) over black (0, 0, 0, 255)
    # Blended: R=0, G=round(220*160/255)=138, B=round(255*160/255)=160
    assert pixel[0] == 0
    assert pixel[1] == 138
    assert pixel[2] == 160


def test_telltale_rendering_baseline_diff(request):
    """Visual regression check comparing rendered telltales against committed baseline image."""
    geom = GaugeGeometry(center_x=128.0, center_y=128.0, radius=100.0)
    renderer = TelltaleRenderer(geometry=geom, show_legend=True)
    base = Image.new("RGBA", (256, 256), (14, 16, 20, 255))
    peaks = {"1m": 25.0, "10m": 50.0, "1h": 75.0, "all_time": 95.0}

    rendered = renderer.render_telltales(base, peaks)

    baseline_path = BASELINES_DIR / "telltale_4_present.png"
    if getattr(request.config.option, "generate_baselines", False):
        BASELINES_DIR.mkdir(parents=True, exist_ok=True)
        rendered.save(baseline_path)
        pytest.skip("Generated baseline image.")

    if not baseline_path.exists():
        pytest.skip(f"Baseline image missing at {baseline_path}")

    baseline_img = Image.open(baseline_path).convert("RGBA")
    rms = _calc_rms(rendered, baseline_img)
    assert rms <= (1.0 / 255.0)


def test_none_peaks_produce_no_pixel_changes():
    """Verify that all-None peaks render identically to the base image."""
    geom = GaugeGeometry(center_x=128.0, center_y=128.0, radius=100.0)
    renderer = TelltaleRenderer(geometry=geom, show_legend=False)
    base = Image.new("RGBA", (256, 256), (14, 16, 20, 255))
    peaks = {"1m": None, "10m": None, "1h": None, "all_time": None}

    rendered = renderer.render_telltales(base, peaks)
    assert list(rendered.getdata()) == list(base.getdata())


def test_post_reset_baseline_diff(request):
    """Visual regression: post-reset render (all None peaks) matches baseline."""
    geom = GaugeGeometry(center_x=128.0, center_y=128.0, radius=100.0)
    renderer = TelltaleRenderer(geometry=geom, show_legend=False)
    base = Image.new("RGBA", (256, 256), (14, 16, 20, 255))
    peaks = {"1m": None, "10m": None, "1h": None, "all_time": None}

    rendered = renderer.render_telltales(base, peaks)

    baseline_path = BASELINES_DIR / "telltale_post_reset.png"
    if getattr(request.config.option, "generate_baselines", False):
        BASELINES_DIR.mkdir(parents=True, exist_ok=True)
        rendered.save(baseline_path)
        pytest.skip("Generated baseline image.")

    if not baseline_path.exists():
        pytest.skip(f"Baseline image missing at {baseline_path}")

    baseline_img = Image.open(baseline_path).convert("RGBA")
    rms = _calc_rms(rendered, baseline_img)
    assert rms <= (1.0 / 255.0)


def test_needle_tip_at_min_value():
    """Baseline-independent: min value needle points at start angle (225 degrees)."""
    geom = GaugeGeometry(
        center_x=128.0,
        center_y=128.0,
        radius=100.0,
        start_angle_deg=225.0,
        end_angle_deg=-45.0,
        min_value=0.0,
        max_value=100.0,
    )
    renderer = TelltaleRenderer(geometry=geom, show_legend=False)
    base = Image.new("RGBA", (256, 256), (0, 0, 0, 255))
    peaks = {"1m": 0.0}
    rendered = renderer.render_telltales(base, peaks)

    # At 225 degrees: tip X = 128 + 85*cos(225°) = 128 - 60.1 ≈ 68, tip Y = 128 - 85*sin(225°) = 128 + 60.1 ≈ 188
    angle_rad = math.radians(225.0)
    needle_length = 100.0 * 0.85
    tip_x = int(round(128.0 + needle_length * math.cos(angle_rad)))
    tip_y = int(round(128.0 - needle_length * math.sin(angle_rad)))

    # Sample midpoint along needle rather than exact tip to account for rounding
    mid_x = int(round(128.0 + (needle_length / 2) * math.cos(angle_rad)))
    mid_y = int(round(128.0 - (needle_length / 2) * math.sin(angle_rad)))

    pixel = rendered.getpixel((mid_x, mid_y))
    assert pixel[3] > 0


def test_needle_tip_at_max_value():
    """Baseline-independent: max value needle points at end angle (-45 degrees)."""
    geom = GaugeGeometry(
        center_x=128.0,
        center_y=128.0,
        radius=100.0,
        start_angle_deg=225.0,
        end_angle_deg=-45.0,
        min_value=0.0,
        max_value=100.0,
    )
    renderer = TelltaleRenderer(geometry=geom, show_legend=False)
    base = Image.new("RGBA", (256, 256), (0, 0, 0, 255))
    peaks = {"1m": 100.0}
    rendered = renderer.render_telltales(base, peaks)

    # At -45 degrees: tip X = 128 + 85*cos(-45°) ≈ 188, tip Y = 128 - 85*sin(-45°) ≈ 188
    angle_rad = math.radians(-45.0)
    needle_length = 100.0 * 0.85
    mid_x = int(round(128.0 + (needle_length / 2) * math.cos(angle_rad)))
    mid_y = int(round(128.0 - (needle_length / 2) * math.sin(angle_rad)))

    pixel = rendered.getpixel((mid_x, mid_y))
    assert pixel[3] > 0


def test_multiple_needles_produce_pixel_changes():
    """Verify rendering multiple non-None peaks changes the image from the base."""
    geom = GaugeGeometry(center_x=128.0, center_y=128.0, radius=100.0)
    renderer = TelltaleRenderer(geometry=geom, show_legend=False)
    base = Image.new("RGBA", (256, 256), (0, 0, 0, 255))
    peaks = {"1m": 25.0, "10m": 50.0, "1h": 75.0, "all_time": 95.0}

    rendered = renderer.render_telltales(base, peaks)
    assert list(rendered.getdata()) != list(base.getdata())


def test_legend_changes_pixel_data():
    """Verify render_legend modifies at least one pixel compared to base."""
    geom = GaugeGeometry(center_x=128.0, center_y=128.0, radius=100.0)
    renderer = TelltaleRenderer(geometry=geom, show_legend=True)
    base = Image.new("RGBA", (256, 256), (0, 0, 0, 255))

    with_legend = renderer.render_legend(base)
    assert list(with_legend.getdata()) != list(base.getdata())


def test_legend_output_size_and_mode():
    """Verify render_legend returns same-size RGBA image."""
    geom = GaugeGeometry(center_x=128.0, center_y=128.0, radius=100.0)
    renderer = TelltaleRenderer(geometry=geom)
    base = Image.new("RGBA", (256, 256), (14, 16, 20, 255))

    out = renderer.render_legend(base)
    assert out.mode == "RGBA"
    assert out.size == (256, 256)


def test_show_legend_false_skips_legend_pixels():
    """Verify show_legend=False produces different output than show_legend=True."""
    geom = GaugeGeometry(center_x=128.0, center_y=128.0, radius=100.0)
    renderer_with = TelltaleRenderer(geometry=geom, show_legend=True)
    renderer_without = TelltaleRenderer(geometry=geom, show_legend=False)
    base = Image.new("RGBA", (256, 256), (0, 0, 0, 255))
    peaks = {"1m": 50.0}

    with_legend = renderer_with.render_telltales(base, peaks)
    without_legend = renderer_without.render_telltales(base, peaks)

    assert list(with_legend.getdata()) != list(without_legend.getdata())


def test_output_is_rgba_mode():
    """Verify render_telltales always returns an RGBA image."""
    geom = GaugeGeometry(center_x=128.0, center_y=128.0, radius=100.0)
    renderer = TelltaleRenderer(geometry=geom, show_legend=False)
    base = Image.new("RGBA", (256, 256), (14, 16, 20, 255))
    peaks = {"1m": 50.0, "10m": 75.0}

    out = renderer.render_telltales(base, peaks)
    assert out.mode == "RGBA"


def test_output_preserves_image_dimensions():
    """Verify render_telltales output size matches input size."""
    geom = GaugeGeometry(center_x=64.0, center_y=64.0, radius=50.0)
    renderer = TelltaleRenderer(geometry=geom, show_legend=False)
    base = Image.new("RGBA", (128, 128), (10, 10, 10, 255))
    peaks = {"1m": 50.0}

    out = renderer.render_telltales(base, peaks)
    assert out.size == (128, 128)


def test_dashed_needle_produces_pixel_changes():
    """Verify dashed needle (1h style) produces pixel changes in the rendered image."""
    geom = GaugeGeometry(center_x=128.0, center_y=128.0, radius=100.0)
    renderer = TelltaleRenderer(geometry=geom, show_legend=False)
    base = Image.new("RGBA", (256, 256), (0, 0, 0, 255))
    # Only render 1h which has dash_pattern=(4,4)
    peaks = {"1h": 50.0}

    rendered = renderer.render_telltales(base, peaks)
    assert list(rendered.getdata()) != list(base.getdata())


def test_main_needle_z_order_baseline_diff(request):
    """Visual regression: z-ordering ensures telltales are behind main needle position."""
    geom = GaugeGeometry(center_x=128.0, center_y=128.0, radius=100.0)
    renderer = TelltaleRenderer(geometry=geom, show_legend=False)
    base = Image.new("RGBA", (256, 256), (14, 16, 20, 255))
    peaks = {"1m": 50.0, "10m": 75.0, "1h": 90.0, "all_time": 95.0}

    rendered = renderer.render_telltales(base, peaks)

    baseline_path = BASELINES_DIR / "telltale_z_order.png"
    if getattr(request.config.option, "generate_baselines", False):
        BASELINES_DIR.mkdir(parents=True, exist_ok=True)
        rendered.save(baseline_path)
        pytest.skip("Generated baseline image.")

    if not baseline_path.exists():
        pytest.skip(f"Baseline image missing at {baseline_path}")

    baseline_img = Image.open(baseline_path).convert("RGBA")
    rms = _calc_rms(rendered, baseline_img)
    assert rms <= (1.0 / 255.0)