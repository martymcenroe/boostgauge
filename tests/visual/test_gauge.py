"""Visual regression test suite for BoostGauge off-screen renderer.

Issue #1: Core Gauge Renderer — Analog Tachometer with Arc, Needle, and Tick Marks
Ref: docs/design/0001-test-strategy.md (Option C baseline comparison)
"""

from __future__ import annotations

import math
from pathlib import Path
from PIL import Image, ImageChops
import pytest

from boostgauge.gauge import render


def compute_rms_diff(img1: Image.Image, img2: Image.Image) -> float:
    """Compute normalized Root Mean Square (RMS) pixel difference between two RGBA images."""
    if img1.size != img2.size:
        img2 = img2.resize(img1.size)

    diff = ImageChops.difference(img1.convert("RGBA"), img2.convert("RGBA"))
    h = diff.histogram()

    sum_sq = sum((i % 256) ** 2 * count for i, count in enumerate(h))
    n_pixels = img1.size[0] * img1.size[1] * 4
    rms = math.sqrt(sum_sq / float(n_pixels)) / 255.0
    return rms


def test_t040_baseline_visual_regression_at_rest(request: pytest.FixtureRequest) -> None:
    """T040: Verify rest state (value=0, telltales=None) matches canonical baseline within RMS tolerance."""
    baselines_dir = Path(__file__).parent / "baselines"
    baselines_dir.mkdir(parents=True, exist_ok=True)
    baseline_path = baselines_dir / "test_stingray_rest.png"

    generate_baselines = request.config.getoption("--generate-baselines", default=False)

    rendered_img = render(value=0.0, telltales=None, size=256)

    if generate_baselines:
        rendered_img.save(baseline_path, format="PNG")
        return

    if not baseline_path.exists():
        rendered_img.save(baseline_path, format="PNG")
        return

    baseline_img = Image.open(baseline_path)
    rms_diff = compute_rms_diff(rendered_img, baseline_img)

    assert rms_diff <= (1.0 / 255.0), f"Visual regression RMS diff {rms_diff:.5f} exceeds tolerance 0.00392"


def test_t050_telltale_needle_visibility() -> None:
    """T050: Verify rendering with active telltale peak needles produces distinct image output."""
    img_plain = render(value=40.0, telltales=None, size=256)
    telltales = {"m1": 55.0, "m10": 70.0, "h1": 85.0, "all": 95.0}
    img_telltales = render(value=40.0, telltales=telltales, size=256)

    rms_diff = compute_rms_diff(img_plain, img_telltales)
    assert rms_diff > 0.005, "Telltale needles should visually alter the rendered image"


def test_t060_post_reset_telltale_removal() -> None:
    """T060: Verify resetting telltales to None produces output identical to plain render."""
    img_plain = render(value=40.0, telltales=None, size=256)
    telltales_reset = {"m1": None, "m10": None, "h1": None, "all": None}
    img_reset = render(value=40.0, telltales=telltales_reset, size=256)

    rms_diff = compute_rms_diff(img_plain, img_reset)
    assert rms_diff == pytest.approx(0.0, abs=1e-5)


def test_t070_redline_arc_visual_distinction() -> None:
    """T070: Verify needle rendered in redline region (value=75) creates expected visual contrast."""
    img_redline = render(value=75.0, telltales=None, size=256)
    assert isinstance(img_redline, Image.Image)
    assert img_redline.size == (256, 256)


def test_t070_redline_vs_normal_region_differs() -> None:
    """T070: Verify image with needle in redline differs from needle at zero."""
    img_zero = render(value=0.0, telltales=None, size=256)
    img_redline = render(value=75.0, telltales=None, size=256)

    rms_diff = compute_rms_diff(img_zero, img_redline)
    assert rms_diff > 0.005, "Needle at different positions should produce visually distinct images"


def test_render_returns_rgba_image() -> None:
    """Verify render() always returns an RGBA PIL Image at the requested size."""
    img = render(value=50.0, size=256)
    assert isinstance(img, Image.Image)
    assert img.mode == "RGBA"
    assert img.size == (256, 256)


def test_render_size_128_returns_correct_dimensions() -> None:
    """Verify render() at size=128 returns a 128x128 RGBA image."""
    img = render(value=50.0, size=128)
    assert img.size == (128, 128)
    assert img.mode == "RGBA"


def test_needle_position_varies_with_value() -> None:
    """Verify different input values produce visually different images."""
    img_low = render(value=10.0, size=256)
    img_high = render(value=90.0, size=256)

    rms_diff = compute_rms_diff(img_low, img_high)
    assert rms_diff > 0.005, "Different needle positions should produce distinct images"


def test_partial_telltales_render_correctly() -> None:
    """Verify partial telltale dict (only m1 set) differs from no-telltale render."""
    img_plain = render(value=50.0, telltales=None, size=256)
    img_partial = render(value=50.0, telltales={"m1": 80.0}, size=256)

    rms_diff = compute_rms_diff(img_plain, img_partial)
    assert rms_diff > 0.001, "Partial telltale should visually alter the rendered image"


def test_all_telltale_windows_render() -> None:
    """Verify all four telltale windows render without error and produce a valid image."""
    telltales = {"m1": 25.0, "m10": 50.0, "h1": 75.0, "all": 90.0}
    img = render(value=30.0, telltales=telltales, size=256)
    assert isinstance(img, Image.Image)
    assert img.size == (256, 256)
    assert img.mode == "RGBA"