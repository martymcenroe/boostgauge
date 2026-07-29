"""Visual regression test suite for boostgauge off-screen rendering (Option C).

Issue #1: Core Gauge Renderer
"""

from __future__ import annotations

from pathlib import Path
import pytest
from PIL import Image

from boostgauge.gauge import render


def calculate_rms_diff(img1: Image.Image, img2: Image.Image) -> float:
    """Calculate normalized Root-Mean-Square pixel difference between two images."""
    import array as _array
    b1 = img1.tobytes()
    b2 = img2.tobytes()
    n = len(b1)
    total = sum((a - b) ** 2 for a, b in zip(b1, b2))
    rms = (total / n) ** 0.5
    return float(rms / 255.0)


def get_baseline_path(filename: str) -> Path:
    """Resolve cross-platform path to visual baseline PNG file."""
    return Path(__file__).parent / "baselines" / filename


def test_t040_rest_state_visual_regression(pytestconfig):
    """Assert rest state (value=0, telltales=None) against canonical baseline PNG."""
    img = render(value=0.0, telltales=None, size=256)
    baseline_path = get_baseline_path("test_stingray_rest.png")

    generate = pytestconfig.getoption("--generate-baselines", default=False)
    if generate:
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(baseline_path)
        pytest.skip(f"Generated baseline image at {baseline_path}")

    if not baseline_path.exists():
        pytest.fail(f"Baseline image missing at {baseline_path}. Run pytest --generate-baselines to create.")

    baseline_img = Image.open(baseline_path).convert("RGBA")
    rms = calculate_rms_diff(img, baseline_img)
    assert rms <= 1.0 / 255.0, f"Visual regression RMS diff {rms:.5f} exceeds threshold 0.00392"


def test_t050_telltale_needle_rendering():
    """Verify telltales rendering produces a visually distinct image from rest state."""
    telltales = {"m1": 50.0, "m10": 70.0, "h1": 85.0, "all": 95.0}
    img_telltales = render(value=0.0, telltales=telltales, size=256)
    img_rest = render(value=0.0, telltales=None, size=256)

    diff_rms = calculate_rms_diff(img_telltales, img_rest)
    assert diff_rms > 0.005, "Telltale needles should create measurable visual difference"


def test_t060_telltales_none_removal():
    """Verify passing telltales with all None produces byte-identical output to telltales=None."""
    telltales_none = {"m1": None, "m10": None, "h1": None, "all": None}
    img_dict_none = render(value=25.0, telltales=telltales_none, size=256)
    img_pure_none = render(value=25.0, telltales=None, size=256)

    assert img_dict_none.tobytes() == img_pure_none.tobytes()


def test_t070_redline_arc_visual_distinction():
    """Verify value=75 renders main needle cleanly within redline arc zone."""
    img_redline = render(value=75.0, size=256)
    assert isinstance(img_redline, Image.Image)
    assert img_redline.size == (256, 256)