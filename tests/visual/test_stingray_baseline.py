"""Visual-regression tier for the Stingray skin — docs/design/0001-test-strategy.md §3.

Option C: the renderer returns a ``PIL.Image``; ``tkinter.Tk()`` is never
instantiated. Baselines under ``tests/visual/baselines/`` are self-generated
from the first accepted render (ruling #262) and regenerate only under an
explicit ``pytest --generate-baselines`` (ruling #271; flag registered in
``tests/conftest.py``).

The 1024 baseline is the approved render itself: ``variant-crimson-1024.png``,
produced by this exact code on 2026-08-25 and approved by the operator. It is
copied, never regenerated — it is the picture these tests exist to protect
(#402).

Failure rule, quoted from §3: identical bytes → pass; byte-different but
pixel-RMS ≤ 1.0/255 → pass with a warning; pixel-RMS > 1.0/255 → fail and write
the diff to ``tests/visual/diffs/{test_id}.png``. ``ImageStat.Stat(...).rms``
reports on the 0–255 scale, so §3's 1.0/255 is 1.0 here.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageStat

from boostgauge.skins import stingray

BASELINES = Path(__file__).parent / "baselines"
DIFFS = Path(__file__).parent / "diffs"
RMS_TOLERANCE = 1.0  # §3: 1.0/255 on the unit interval == 1.0 on Pillow's 0–255 rms


def _rms(a: Image.Image, b: Image.Image) -> float:
    """Worst-channel RMS of the pixel difference, 0–255 scale."""
    diff = ImageChops.difference(a.convert("RGB"), b.convert("RGB"))
    return max(ImageStat.Stat(diff).rms)


def _assert_matches_baseline(request, image: Image.Image, test_id: str,
                             regenerable: bool = True) -> float:
    """Apply §3's rule against ``baselines/{test_id}.png``; return the RMS.

    ``regenerable=False`` marks a baseline that ``--generate-baselines`` must
    never overwrite — the operator-approved render.
    """
    path = BASELINES / f"{test_id}.png"
    generate = request.config.getoption("--generate-baselines") and regenerable

    if not path.exists():
        if generate:
            BASELINES.mkdir(parents=True, exist_ok=True)
            image.save(path)
            warnings.warn(f"{test_id}: baseline written to {path} — inspect and commit")
            return 0.0
        pytest.fail(f"{test_id}: missing baseline {path}; "
                    "run `pytest tests/visual/ --generate-baselines` to write it")

    baseline = Image.open(path).convert("RGB")
    assert baseline.size == image.size, (
        f"{test_id}: size {image.size} != baseline {baseline.size}")

    if image.convert("RGB").tobytes() == baseline.tobytes():
        return 0.0

    rms = _rms(image, baseline)
    if rms <= RMS_TOLERANCE:
        warnings.warn(f"{test_id}: byte-different, rms={rms:.4f} <= {RMS_TOLERANCE} "
                      "(anti-aliasing noise)")
        return rms

    DIFFS.mkdir(parents=True, exist_ok=True)
    ImageChops.difference(image.convert("RGB"), baseline).save(DIFFS / f"{test_id}.png")
    if generate:
        image.save(path)
        warnings.warn(f"{test_id}: baseline OVERWRITTEN at {path} (rms was {rms:.4f}) "
                      "— inspect and commit")
        return rms
    pytest.fail(f"{test_id}: rms={rms:.4f} > {RMS_TOLERANCE}; "
                f"diff written to {DIFFS / (test_id + '.png')}")
    return rms  # unreachable; keeps the signature honest for type checkers


@pytest.fixture(scope="module")
def face_1024() -> Image.Image:
    return stingray.render_face(1024)


def test_face_256_matches_baseline(request):
    _assert_matches_baseline(request, stingray.render_face(256), "stingray_face_256")


def test_face_needle75_256_matches_baseline(request):
    _assert_matches_baseline(request, stingray.render_with_needle(256, 75.0),
                             "stingray_face_needle75_256")


def test_needle75_1024_matches_approved_render(request):
    """The picture the operator approved on 2026-08-25, byte for byte."""
    rms = _assert_matches_baseline(request, stingray.render_with_needle(1024, 75.0),
                                   "stingray_approved_needle75_1024",
                                   regenerable=False)
    assert rms == 0.0, f"approved render drifted: rms={rms:.4f}"


def test_literal_values_1024(face_1024):
    """Contract values, sampled ≥ 2 px inside their features (ruling #270)."""
    px = face_1024.load()
    cx = cy = 512.0
    R = 0.40 * 1024

    assert px[512, 512] == (10, 10, 12)                       # S1 dial face #0A0A0C

    x, y = stingray.polar(cx, cy, 0.94 * R, stingray.angle(85))  # between minor ticks
    assert px[int(x), int(y)] == (170, 15, 25)                # S2 band #AA0F19

    x, y = stingray.polar(cx, cy, 0.95 * R, stingray.angle(50))  # major-tick midpoint
    assert px[int(x), int(y)] == (255, 255, 255)              # S3 tick #FFFFFF

    x, y = stingray.polar(cx, cy, 0.94 * R, stingray.angle(35))  # face between ticks
    assert px[int(x), int(y)] == (10, 10, 12)                 # no band below 60
