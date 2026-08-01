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

    assert CANONICAL_BASELINE.exists(), (
        f"Baseline missing at {CANONICAL_BASELINE}. Run with --generate-baselines to create."
    )
    img_baseline = Image.open(CANONICAL_BASELINE)

    rms = _compute_rms_diff(img_rendered, img_baseline)
    assert rms <= (1.0 / 255.0), (
        f"Visual regression RMS diff {rms:.6f} exceeds tolerance {1.0 / 255.0:.6f}"
    )


def test_baseline_independent_needle_geometry() -> None:
    """REQ-8 (Baseline-Independent): Assert main needle tip position at value=50 (12 o'clock).

    At value=50, angle = 225 - 2.7*50 = 90° (straight up).
    For size=256, center=(128,128), needle radius=256*0.38=97.28 -> tip near (128, ~31).
    """
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
    # Arc at ~30° from horizontal: x=128+102*cos(30°)≈216, y=128-102*sin(30°)≈77
    r, g, b, a = img.getpixel((216, 77))
    assert r > 180 and g < 80 and b < 80, (
        f"Expected red arc pixel at (216, 77), got ({r},{g},{b},{a})"
    )


def test_output_mode_and_size() -> None:
    """Assert rendered image is RGBA mode with correct dimensions."""
    img = render(0.0, size=256)
    assert img.mode == "RGBA"
    assert img.size == (256, 256)


def test_output_mode_and_size_custom() -> None:
    """Assert custom size returns correct dimensions."""
    img = render(50.0, size=512)
    assert img.mode == "RGBA"
    assert img.size == (512, 512)


def test_deterministic_identical_inputs() -> None:
    """REQ-9: Two renders with identical inputs produce byte-identical output."""
    img1 = render(75.0, telltales={"m1": 25.0, "all_time": 90.0}, size=256)
    img2 = render(75.0, telltales={"m1": 25.0, "all_time": 90.0}, size=256)
    assert img1.tobytes() == img2.tobytes()


def test_telltale_none_omitted_matches_no_telltales() -> None:
    """REQ-10: Telltale key set to None produces same output as omitting telltales entirely."""
    img_none_val = render(30.0, telltales={"m10": None}, size=256)
    img_no_tell = render(30.0, telltales=None, size=256)
    assert img_none_val.tobytes() == img_no_tell.tobytes()


def test_telltale_presence_changes_output() -> None:
    """REQ-7: Rendering with a telltale value differs from rendering without."""
    img_with = render(30.0, telltales={"m1": 50.0}, size=256)
    img_without = render(30.0, telltales=None, size=256)
    assert img_with.tobytes() != img_without.tobytes()


def test_needle_value_zero_differs_from_fifty() -> None:
    """Assert different metric values produce visually distinct outputs."""
    img_zero = render(0.0, size=256)
    img_fifty = render(50.0, size=256)
    assert img_zero.tobytes() != img_fifty.tobytes()


def test_needle_value_hundred_differs_from_zero() -> None:
    """Assert value=100 and value=0 produce distinct outputs."""
    img_zero = render(0.0, size=256)
    img_hundred = render(100.0, size=256)
    assert img_zero.tobytes() != img_hundred.tobytes()


def test_needle_at_value_zero_angle() -> None:
    """REQ-8 (Baseline-Independent): At value=0, needle points to 225° (lower-left, ~7:30 o'clock).

    For size=256, center=(128,128), needle radius=256*0.38=97.28.
    225° in standard math (CCW from east): cos(225°)≈-0.707, sin(225°)≈-0.707
    Screen coords (Y inverted): tip_x=128+97.28*(-0.707)≈59, tip_y=128-97.28*(-0.707)≈197
    """
    size = 256
    img = render(0.0, telltales=None, size=size)

    # Sample near lower-left tip area
    pixel = img.getpixel((62, 194))
    r, g, b, a = pixel
    assert r > 150 and g < 60 and b < 60, (
        f"Expected red needle pixel near value=0 tip at (62, 194), got RGBA=({r},{g},{b},{a})"
    )


def test_needle_at_value_hundred_angle() -> None:
    """REQ-8 (Baseline-Independent): At value=100, needle points to -45° (lower-right, ~4:30 o'clock).

    For size=256, center=(128,128), needle radius=256*0.38=97.28.
    -45° in standard math: cos(-45°)≈0.707, sin(-45°)≈-0.707
    Screen coords (Y inverted): tip_x=128+97.28*0.707≈197, tip_y=128-97.28*(-0.707)≈197
    """
    size = 256
    img = render(100.0, telltales=None, size=size)

    pixel = img.getpixel((194, 194))
    r, g, b, a = pixel
    assert r > 150 and g < 60 and b < 60, (
        f"Expected red needle pixel near value=100 tip at (194, 194), got RGBA=({r},{g},{b},{a})"
    )


def test_needle_overlays_redline_at_value_75() -> None:
    """REQ-11: At value=75, needle renders over redline arc — needle pixel dominates at tip.

    value=75 -> angle=225-2.7*75=22.5°
    tip_x=128+97.28*cos(22.5°)≈218, tip_y=128-97.28*sin(22.5°)≈91
    Needle (red) should dominate over arc in that region.
    """
    size = 256
    img = render(75.0, telltales=None, size=size)

    pixel = img.getpixel((214, 94))
    r, g, b, a = pixel
    assert r > 150 and g < 80 and b < 80, (
        f"Expected red needle pixel at (214, 94) for value=75, got RGBA=({r},{g},{b},{a})"
    )


def test_all_four_telltales_produce_distinct_output() -> None:
    """REQ-7: Rendering all 4 telltales differs from rendering with none."""
    img_all = render(50.0, telltales={"m1": 20.0, "m10": 40.0, "h1": 60.0, "all_time": 80.0}, size=256)
    img_none = render(50.0, telltales=None, size=256)
    assert img_all.tobytes() != img_none.tobytes()


def test_image_not_fully_transparent() -> None:
    """Assert rendered image is not entirely transparent (sanity check for rendering)."""
    img = render(50.0, size=256)
    pixels = list(img.getdata())
    non_transparent = [p for p in pixels if p[3] > 0]
    assert len(non_transparent) > 0, "Rendered image is entirely transparent"


def test_image_contains_non_black_pixels() -> None:
    """Assert rendered image has visible non-black content."""
    img = render(50.0, size=256)
    pixels = list(img.getdata())
    bright_pixels = [p for p in pixels if p[0] > 50 or p[1] > 50 or p[2] > 50]
    assert len(bright_pixels) > 100, "Rendered image contains too few visible pixels"