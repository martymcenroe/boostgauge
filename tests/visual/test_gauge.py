"""Visual regression tests for gauge rendering.

Issue #1: Feature: core gauge renderer
"""

import pytest
from pathlib import Path
from PIL import Image, ImageChops
from boostgauge.gauge import render


def test_req_120_visual(request, tmp_path):
    generate = request.config.getoption("--generate-baselines", False)
    img = render(0, [], 256)
    baseline_path = Path("tests/visual/baselines/baseline_0.png")
    if generate:
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(baseline_path)
    else:
        assert baseline_path.exists(), "Baseline missing, run with --generate-baselines"
        baseline = Image.open(baseline_path)
        diff = ImageChops.difference(img, baseline)
        assert not diff.getbbox(), "Visual regression detected"