"""Visual regression test suite for BoostGauge renderer.

Issue #1: Core gauge renderer — analog tachometer with arc, needle, and tick marks
"""

import math
from pathlib import Path
import pytest
from PIL import Image, ImageChops, ImageStat

from boostgauge.gauge import render

BASELINE_DIR = Path(__file__).parent / "baselines"
CANONICAL_BASELINE = BASELINE_DIR / "aesthetic-v1-stingray-canonical.png"


def _compute_rms_diff(img1: Image.Image, img2: Image.Image) -> float:
    """Compute Root Mean Square (RMS) difference per channel normalized to [0.0, 1.0]."""
    diff = ImageChops.difference(img1.convert("RGBA"), img2.convert("RGBA"))
    stat = ImageStat.Stat(diff)
    sum_sq = sum(rms ** 2 for rms in stat.rms)
    return math.sqrt(sum_sq / len(stat.rms)) / 255.0


def test_visual_baseline_canonical(request: pytest.FixtureRequest) -> None:
    """REQ-12: Compare value=0 output against canonical baseline within RMS tolerance <= 1.0 / 255."""
    img_rendered = render(0.0, telltales=None, size=256)

    if getattr(request.config.option, "generate_baselines", False):
        BASELINE_DIR.mkdir(parents=True, exist_ok=True)
        img_rendered.save(CANONICAL_BASELINE)
        pytest.skip(f"Updated baseline at {CANONICAL_BASELINE}")

    if not CANONICAL_BASELINE.exists():
        pytest.skip(f"Baseline missing at {CANONICAL_BASELINE}. Run with --generate-baselines to create.")

    img_baseline = Image.open(CANONICAL_BASELINE)

    rms = _compute_rms_diff(img_rendered, img_baseline)
    assert rms <= (1.0 / 255.0), (
        f"Visual regression RMS diff {rms:.6f} exceeds tolerance {1.0 / 255.0:.6f}"
    )


def test_baseline_independent_needle_geometry() -> None:
    """REQ-8 (Baseline-Independent): Assert main needle tip position at value=50 (12 o'clock)."""
    size = 256
    img = render(50.0, telltales=None, size=size)

    pixel = img.getpixel((128, 45))
    r, g, b, a = pixel
    assert r > 180 and g < 60 and b < 60, (
        f"Expected red needle pixel at (128, 45), got RGBA=({r},{g},{b},{a})"
    )


def test_baseline_independent_dial_center_background() -> None:
    """REQ-4 (Baseline-Independent): Assert center pivot region contains dark cap colors."""
    img = render(0.0, size=256)
    r, g, b, a = img.getpixel((128, 128))
    assert r < 40 and g < 40 and b < 40 and a == 255, (
        f"Expected dark pivot cap pixel at center (128, 128), got ({r},{g},{b},{a})"
    )


def test_baseline_independent_redline_region_color() -> None:
    """REQ-5 (Baseline-Independent): Assert redline arc sector contains red pixels."""
    img = render(0.0, size=256)
    r, g, b, a = img.getpixel((216, 77))
    assert r > 180 and g < 80 and b < 80, (
        f"Expected red arc pixel at (216, 77), got ({r},{g},{b},{a})"
    )


def test_output_mode_and_size() -> None:
    """Verify rendered image is RGBA and correct size."""
    img = render(0.0, size=256)
    assert img.mode == "RGBA"
    assert img.size == (256, 256)


def test_output_size_512() -> None:
    """Verify rendered image at size=512 is correct."""
    img = render(50.0, size=512)
    assert img.mode == "RGBA"
    assert img.size == (512, 512)


def test_deterministic_visual_output() -> None:
    """Verify two renders with identical args are byte-identical."""
    img1 = render(0.0, telltales=None, size=256)
    img2 = render(0.0, telltales=None, size=256)
    assert img1.tobytes() == img2.tobytes()


def test_needle_position_differs_across_values() -> None:
    """Verify that different metric values produce visually different images."""
    img_zero = render(0.0, size=256)
    img_full = render(100.0, size=256)
    rms = _compute_rms_diff(img_zero, img_full)
    assert rms > 0.0, "Images at value=0 and value=100 should differ visually"


def test_telltale_presence_affects_output() -> None:
    """Verify that adding a telltale needle changes the rendered image."""
    img_no_tell = render(50.0, telltales=None, size=256)
    img_with_tell = render(50.0, telltales={"m1": 25.0}, size=256)
    rms = _compute_rms_diff(img_no_tell, img_with_tell)
    assert rms > 0.0, "Image with telltale should differ from image without"


def test_needle_value_zero_at_bottom_left() -> None:
    """At value=0, needle points to 225° (7:30 o'clock, bottom-left quadrant)."""
    size = 256
    img = render(0.0, telltales=None, size=size)
    cx, cy = 128, 128
    angle_rad = math.radians(225.0)
    r = 256 * 0.38 / 2
    tip_x = int(cx + r * math.cos(angle_rad))
    tip_y = int(cy - r * math.sin(angle_rad))
    tip_x = max(0, min(size - 1, tip_x))
    tip_y = max(0, min(size - 1, tip_y))
    pixel = img.getpixel((tip_x, tip_y))
    r_val, g_val, b_val, a_val = pixel
    assert r_val > 150 and g_val < 80 and b_val < 80, (
        f"Expected red needle near value=0 tip ({tip_x},{tip_y}), got RGBA=({r_val},{g_val},{b_val},{a_val})"
    )


def test_needle_value_100_at_bottom_right() -> None:
    """At value=100, needle points to -45° (4:30 o'clock, bottom-right quadrant)."""
    size = 256
    img = render(100.0, telltales=None, size=size)
    cx, cy = 128, 128
    angle_rad = math.radians(-45.0)
    r = 256 * 0.38 / 2
    tip_x = int(cx + r * math.cos(angle_rad))
    tip_y = int(cy - r * math.sin(angle_rad))
    tip_x = max(0, min(size - 1, tip_x))
    tip_y = max(0, min(size - 1, tip_y))
    pixel = img.getpixel((tip_x, tip_y))
    r_val, g_val, b_val, a_val = pixel
    assert r_val > 150 and g_val < 80 and b_val < 80, (
        f"Expected red needle near value=100 tip ({tip_x},{tip_y}), got RGBA=({r_val},{g_val},{b_val},{a_val})"
    )


def test_image_not_fully_transparent() -> None:
    """Verify rendered image has non-transparent pixels (not a blank canvas)."""
    img = render(50.0, size=256)
    pixels = list(img.getdata())
    non_transparent = [p for p in pixels if p[3] > 0]
    assert len(non_transparent) > 1000, "Rendered image should contain substantial non-transparent content"


def test_center_region_opaque() -> None:
    """Verify the dial face center region is fully opaque."""
    img = render(50.0, size=256)
    _, _, _, a = img.getpixel((128, 128))
    assert a == 255, f"Center pivot cap should be fully opaque, got alpha={a}"