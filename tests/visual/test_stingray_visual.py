"""Render-tier visual regression tests for Stingray skin gauge face.

Issue #1: Core Gauge Renderer — Analog Tachometer with Arc, Needle, and Tick Marks
"""

from __future__ import annotations

import math
from pathlib import Path
import pytest
from PIL import Image, ImageChops

from boostgauge.gauge import render

BASELINES_DIR = Path(__file__).resolve().parent / "baselines"


def _compute_rms_diff(img1: Image.Image, img2: Image.Image) -> float:
    """Compute Root Mean Square (RMS) difference per channel between two PIL images."""
    if img1.size != img2.size or img1.mode != img2.mode:
        return 1.0

    diff = ImageChops.difference(img1, img2)
    h = diff.histogram()

    sum_sq = 0.0
    total_pixels = img1.size[0] * img1.size[1] * len(img1.getbands())

    for i in range(len(h)):
        count = h[i]
        val = i % 256
        sum_sq += count * (val * val)

    rms = math.sqrt(sum_sq / float(total_pixels)) / 255.0
    return rms


def test_visual_baseline_value_0(pytestconfig):
    """T130: Compare rendered gauge output at value=0 against baseline image."""
    BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    baseline_path = BASELINES_DIR / "test_stingray_value_0.png"

    rendered_img = render(0.0, telltales=None, size=(256, 256))

    if pytestconfig.getoption("generate_baselines", default=False) or not baseline_path.exists():
        rendered_img.save(baseline_path)
        pytest.skip(f"Generated baseline image at {baseline_path}")

    baseline_img = Image.open(baseline_path).convert("RGBA")
    rms_error = _compute_rms_diff(rendered_img, baseline_img)

    assert rms_error <= (1.0 / 255.0), f"Visual RMS error {rms_error:.6f} exceeded tolerance 1/255"


def test_visual_baseline_value_100(pytestconfig):
    """Compare rendered gauge output at value=100 against baseline image."""
    BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    baseline_path = BASELINES_DIR / "test_stingray_value_100.png"

    rendered_img = render(100.0, telltales=None, size=(256, 256))

    if pytestconfig.getoption("generate_baselines", default=False) or not baseline_path.exists():
        rendered_img.save(baseline_path)
        pytest.skip(f"Generated baseline image at {baseline_path}")

    baseline_img = Image.open(baseline_path).convert("RGBA")
    rms_error = _compute_rms_diff(rendered_img, baseline_img)

    assert rms_error <= (1.0 / 255.0), f"Visual RMS error {rms_error:.6f} exceeded tolerance 1/255"


def test_visual_baseline_telltales(pytestconfig):
    """Compare rendered gauge output with active telltales against baseline image."""
    BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    baseline_path = BASELINES_DIR / "test_stingray_telltales.png"

    telltales = {
        "window_1m": 35.0,
        "window_10m": 60.0,
        "window_1h": 85.0,
        "window_all": 95.0,
    }
    rendered_img = render(25.0, telltales=telltales, size=(256, 256))

    if pytestconfig.getoption("generate_baselines", default=False) or not baseline_path.exists():
        rendered_img.save(baseline_path)
        pytest.skip(f"Generated baseline image at {baseline_path}")

    baseline_img = Image.open(baseline_path).convert("RGBA")
    rms_error = _compute_rms_diff(rendered_img, baseline_img)

    assert rms_error <= (1.0 / 255.0), f"Visual RMS error {rms_error:.6f} exceeded tolerance 1/255"