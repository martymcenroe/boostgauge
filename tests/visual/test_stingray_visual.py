"""Visual regression test suite for Stingray skin tachometer.

Issue #1: Feature: Core Gauge Renderer — Analog Tachometer with Arc, Needle, and Tick Marks
"""

from pathlib import Path
import math
import pytest
from PIL import Image, ImageChops

from boostgauge.gauge import render

BASELINES_DIR = Path(__file__).resolve().parent / "baselines"


def _compute_rms_error(img1: Image.Image, img2: Image.Image) -> float:
    """Compute Root Mean Square (RMS) difference between two PIL Images."""
    diff = ImageChops.difference(img1.convert("RGB"), img2.convert("RGB"))
    histogram = diff.histogram()
    sq = sum(count * (i % 256) ** 2 for i, count in enumerate(histogram))
    rms = math.sqrt(sq / float(img1.size[0] * img1.size[1] * 3))
    return rms / 255.0


@pytest.fixture(autouse=True)
def ensure_baselines_dir():
    BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    return BASELINES_DIR


def _get_or_create_baseline(baseline_path: Path, rendered_img: Image.Image, request) -> Image.Image | None:
    """Return baseline image, creating it if absent or if --generate-baselines passed."""
    if getattr(request.config.option, "generate_baselines", False):
        rendered_img.save(baseline_path)
        pytest.skip(f"Generated baseline image at {baseline_path}")

    if not baseline_path.exists():
        rendered_img.save(baseline_path)
        pytest.skip(f"Created initial baseline image at {baseline_path}")

    return Image.open(baseline_path)


def _assert_rms(rendered_img: Image.Image, baseline_img: Image.Image) -> None:
    rms_error = _compute_rms_error(rendered_img, baseline_img)
    assert rms_error <= (1.0 / 255.0), (
        f"RMS error {rms_error:.6f} exceeded tolerance {1.0 / 255.0:.6f}"
    )


def test_visual_regression_stingray_at_rest(request):
    """T140: Visual regression check for gauge at rest (value=0.0)."""
    rendered_img = render(0.0, telltales=None, size=(256, 256))
    baseline_path = BASELINES_DIR / "stingray_at_rest.png"
    baseline_img = _get_or_create_baseline(baseline_path, rendered_img, request)
    _assert_rms(rendered_img, baseline_img)


def test_visual_regression_stingray_full_scale(request):
    """Visual regression check for gauge at full scale (value=100.0)."""
    rendered_img = render(100.0, telltales=None, size=(256, 256))
    baseline_path = BASELINES_DIR / "stingray_full_scale.png"
    baseline_img = _get_or_create_baseline(baseline_path, rendered_img, request)
    _assert_rms(rendered_img, baseline_img)


def test_visual_regression_stingray_mid_scale(request):
    """Visual regression check for gauge at mid-scale (value=50.0)."""
    rendered_img = render(50.0, telltales=None, size=(256, 256))
    baseline_path = BASELINES_DIR / "stingray_mid_scale.png"
    baseline_img = _get_or_create_baseline(baseline_path, rendered_img, request)
    _assert_rms(rendered_img, baseline_img)


def test_visual_regression_stingray_redline(request):
    """Visual regression check for gauge in redline region (value=75.0)."""
    rendered_img = render(75.0, telltales=None, size=(256, 256))
    baseline_path = BASELINES_DIR / "stingray_redline.png"
    baseline_img = _get_or_create_baseline(baseline_path, rendered_img, request)
    _assert_rms(rendered_img, baseline_img)


def test_visual_regression_stingray_with_telltales(request):
    """Visual regression check for gauge with all telltale needles active."""
    telltales = {
        "window_1m": 80.0,
        "window_10m": 60.0,
        "window_1h": 40.0,
        "window_all": 90.0,
    }
    rendered_img = render(50.0, telltales=telltales, size=(256, 256))
    baseline_path = BASELINES_DIR / "stingray_with_telltales.png"
    baseline_img = _get_or_create_baseline(baseline_path, rendered_img, request)
    _assert_rms(rendered_img, baseline_img)


def test_visual_regression_stingray_partial_telltales(request):
    """Visual regression check for gauge with partial telltales (only window_10m active)."""
    telltales = {
        "window_1m": None,
        "window_10m": 60.0,
        "window_1h": None,
        "window_all": None,
    }
    rendered_img = render(50.0, telltales=telltales, size=(256, 256))
    baseline_path = BASELINES_DIR / "stingray_partial_telltales.png"
    baseline_img = _get_or_create_baseline(baseline_path, rendered_img, request)
    _assert_rms(rendered_img, baseline_img)


def test_visual_regression_stingray_large_size(request):
    """Visual regression check for gauge rendered at 512x512."""
    rendered_img = render(50.0, telltales=None, size=(512, 512))
    baseline_path = BASELINES_DIR / "stingray_512x512.png"
    baseline_img = _get_or_create_baseline(baseline_path, rendered_img, request)
    _assert_rms(rendered_img, baseline_img)


def test_render_output_mode_and_size():
    """Verify rendered image has correct mode and size without baseline comparison."""
    img = render(0.0, telltales=None, size=(256, 256))
    assert isinstance(img, Image.Image)
    assert img.mode == "RGBA"
    assert img.size == (256, 256)


def test_render_deterministic_pixel_equality():
    """Verify identical inputs produce byte-identical outputs (no randomness)."""
    img1 = render(50.0, telltales=None, size=(256, 256))
    img2 = render(50.0, telltales=None, size=(256, 256))
    assert img1.tobytes() == img2.tobytes()


def test_rms_error_identical_images():
    """RMS error between identical images must be 0.0."""
    img = render(0.0, telltales=None, size=(256, 256))
    rms = _compute_rms_error(img, img)
    assert rms == 0.0


def test_rms_error_different_images():
    """RMS error between images at different values must be > 0.0."""
    img_rest = render(0.0, telltales=None, size=(256, 256))
    img_full = render(100.0, telltales=None, size=(256, 256))
    rms = _compute_rms_error(img_rest, img_full)
    assert rms > 0.0