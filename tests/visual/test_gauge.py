"""Visual regression test suite for boostgauge renderer.

Issue #1: Core Gauge Renderer — Analog Tachometer.
"""

from __future__ import annotations

from pathlib import Path
import pytest
import PIL.Image
import PIL.ImageChops
import PIL.ImageStat

from boostgauge.gauge import render

BASELINES_DIR = Path(__file__).resolve().parent / "baselines"
DIFFS_DIR = Path(__file__).resolve().parent / "diffs"


def test_visual_regression_rest_state(pytestconfig):
    """Assert pixel-RMS tolerance <= 1.0/255 against canonical rest baseline (value=0)."""
    BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    baseline_path = BASELINES_DIR / "test_stingray_rest.png"

    rendered_img = render(0.0, telltales=None, size=256)

    generate_baselines = pytestconfig.getoption("--generate-baselines", default=False)
    if generate_baselines or not baseline_path.exists():
        if not generate_baselines:
            pytest.fail(f"Missing visual baseline at {baseline_path}. Run pytest --generate-baselines to create.")
        rendered_img.save(baseline_path)
        return

    baseline_img = PIL.Image.open(baseline_path).convert("RGBA")
    diff = PIL.ImageChops.difference(rendered_img, baseline_img)
    stat = PIL.ImageStat.Stat(diff)
    rms = sum(stat.rms) / len(stat.rms)

    if rms > 1.0:
        DIFFS_DIR.mkdir(parents=True, exist_ok=True)
        rendered_img.save(DIFFS_DIR / "test_stingray_rest_diff.png")
        pytest.fail(f"Visual regression failed for rest state: RMS difference {rms:.4f} > 1.0")


def test_visual_regression_telltales_present(pytestconfig):
    """Assert rendering with 4 telltale peaks renders non-transparent needles."""
    telltales = {"m1": 50.0, "m10": 70.0, "h1": 85.0, "all": 95.0}
    img_with_telltales = render(25.0, telltales=telltales, size=256)
    img_without_telltales = render(25.0, telltales=None, size=256)

    diff = PIL.ImageChops.difference(img_with_telltales, img_without_telltales)
    stat = PIL.ImageStat.Stat(diff)
    rms = sum(stat.rms) / len(stat.rms)

    assert rms > 2.0, "Telltale needles did not produce detectable pixel changes"