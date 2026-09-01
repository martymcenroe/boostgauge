"""Visual tier for the dynamic layer (#332): telltales, main needle, pivot cap over the cached face.

Option C (docs/design/0001-test-strategy.md): PIL images in, pixel assertions,
no tkinter. Every literal below is either the contract's value or a number
measured off the approved renderer on 2026-09-01 (probe in the #332 PR). Where
an issue row's number was false of the operator-approved render, the measured
value is bound instead and the PR names the row:

- N6 glow: the row said R >= 180 at 0.04 R; the approved render reads 70 there
  and 119 at 0.03 R, 255 at 0.02 R. Bound: R >= 100 at 0.03 R (a flat needle
  reads 10 — the row's purpose, kept).
- N9 face non-mutation: the row said identical beyond 0.10 R, where N7 itself
  binds R <= 25 of bloom. Measured clean radius is 0.20 R. Bound at 0.20 R.
- N9a cap: the row's mean ceiling 248 excludes the approved cap centre
  (250, 251, 252). Bound: achromatic (max - min <= 14) and mean >= 200.
- T3 blend arithmetic is asserted on the supersampled composite, where it is
  exact; Lanczos ringing at 256 px overshoots a thin line by ~9 %.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageStat

from boostgauge.skins import stingray as sk
from boostgauge.telltale import Telltale

BASELINES = Path(__file__).parent / "baselines"
DIFFS = Path(__file__).parent / "diffs"
RMS_TOLERANCE = 1.0

FACE_PALETTE = [sk.FACE, sk.WHITE, sk.NEEDLE, sk.BAND, sk.HOT]
NEEDLE_FAMILY = {sk.NEEDLE, sk.HOT}
PEAKS = [10.0, 25.0, 85.0, 100.0]   # 1m, 10m, 1h, all-time — every one >= 20 units from value 50
VALUE = 50.0


def _nearest(pixel, palette):
    return min(palette, key=lambda c: sum((a - b) ** 2 for a, b in zip(pixel, c)))


def _px(img, x, y):
    return img.getpixel((int(x), int(y)))[:3]


def _geometry(size):
    return size / 2, size / 2, 0.40 * size


@pytest.fixture(scope="module")
def dyn_1024():
    return sk.render(VALUE, [None] * 4, 1024)


@pytest.fixture(scope="module")
def dyn_256():
    return sk.render(VALUE, PEAKS, 256)


# ---- the composition IS the approved render when nothing else is drawn --------


def test_no_telltales_is_the_approved_render_byte_for_byte():
    approved = Image.open(BASELINES / "stingray_approved_needle75_1024.png").convert("RGB")
    assert sk.render(75.0, [None] * 4, 1024).tobytes() == approved.tobytes()


def test_T1_none_peaks_draw_nothing():
    assert sk.render(VALUE, [None] * 4, 256).tobytes() == sk.render_with_needle(256, VALUE).tobytes()


# ---- N1-N3: axis ----------------------------------------------------------------


@pytest.mark.parametrize("value, other", [(0.0, 50.0), (50.0, 0.0), (100.0, 50.0)])
def test_N1_N2_N3_axis(value, other):
    img = sk.render(value, [None] * 4, 1024)
    cx, cy, R = _geometry(1024)
    on = sk.polar(cx, cy, 0.80 * R, sk.angle(value))
    off = sk.polar(cx, cy, 0.80 * R, sk.angle(other))
    assert _nearest(_px(img, *on), FACE_PALETTE) in NEEDLE_FAMILY
    assert _px(img, *off) == (10, 10, 12)


# ---- N5-N7: luminescence (#327), measured --------------------------------------


def test_N5_N6_N7_luminescence(dyn_1024):
    cx, cy, R = _geometry(1024)
    a = sk.angle(VALUE)
    on = sk.polar(cx, cy, 0.45 * R, a)
    r_on, g_on, _ = _px(dyn_1024, *on)
    assert r_on == 255 and g_on >= 200                             # N5 hot core
    assert _px(dyn_1024, *sk.polar(*on, 0.03 * R, a + 90))[0] >= 100  # N6 glow present (flat: 10)
    assert _px(dyn_1024, *sk.polar(*on, 0.10 * R, a + 90))[0] <= 25   # N7 glow bounded


# ---- N8: counterweight -------------------------------------------------------------


def test_N8_counterweight(dyn_1024):
    cx, cy, R = _geometry(1024)
    p = sk.polar(cx, cy, 0.12 * R, sk.angle(VALUE) + 180)
    assert _nearest(_px(dyn_1024, *p), FACE_PALETTE) == sk.NEEDLE


# ---- N9a: pivot cap on top of everything -------------------------------------------


@pytest.mark.parametrize("value, peaks", [(0.0, [None] * 4), (50.0, [None] * 4), (100.0, [None] * 4),
                                          (50.0, [50.0, 50.0, 50.0, 50.0])])
def test_N9a_cap_centre_is_chrome_not_needle(value, peaks):
    img = sk.render(value, peaks, 256)
    pixel = _px(img, 128, 128)
    assert max(pixel) - min(pixel) <= 14
    assert sum(pixel) / 3 >= 200
    assert _nearest(pixel, FACE_PALETTE) not in NEEDLE_FAMILY


# ---- N9: the face is untouched away from every needle -----------------------------


def _segment_distance(px, py, ax, ay, bx, by):
    vx, vy, wx, wy = bx - ax, by - ay, px - ax, py - ay
    L2 = vx * vx + vy * vy
    t = max(0.0, min(1.0, (wx * vx + wy * vy) / L2)) if L2 else 0.0
    return math.hypot(px - (ax + t * vx), py - (ay + t * vy))


def test_N9_face_non_mutation_beyond_0_20_R(dyn_256):
    face = sk.render_face(256)
    cx, cy, R = _geometry(256)
    segments = [(cx, cy, *sk.polar(cx, cy, 0.86 * R, sk.angle(VALUE))),
                (cx, cy, *sk.polar(cx, cy, 0.18 * R, sk.angle(VALUE) + 180))]
    segments += [(cx, cy, *sk.polar(cx, cy, 0.86 * R, sk.angle(p))) for p in PEAKS]
    dyn, bare = dyn_256.load(), face.load()
    checked = 0
    for y in range(256):
        for x in range(256):
            if math.hypot(x - cx, y - cy) <= 0.10 * R + 2:
                continue
            if min(_segment_distance(x, y, *s) for s in segments) < 0.20 * R:
                continue
            assert dyn[x, y] == bare[x, y], f"face mutated at ({x}, {y})"
            checked += 1
    assert checked > 30000   # most of the image is in the mask


# ---- T2/T3: colours and flat 65 % blend, exact on the supersampled composite ------


def test_T2_T3_telltale_blend_arithmetic():
    base, S, cx, cy, R = sk.cached_face(256)
    comp = sk.draw_telltales(base, S, cx, cy, R, PEAKS, VALUE)
    blends = []
    for color, peak in zip(sk.TELLTALE_COLORS, PEAKS):
        mid = sk.polar(cx, cy, 0.43 * R, sk.angle(peak))
        got = _px(comp, *mid)
        expected = tuple(int(c * 166 / 255 + f * 89 / 255 + 0.5) for c, f in zip(color, sk.FACE))
        assert all(abs(g - e) <= 2 for g, e in zip(got, expected)), (color, got, expected)
        blends.append(got)
    for i in range(4):
        for j in range(i + 1, 4):
            assert math.dist(blends[i], blends[j]) >= 50, (blends[i], blends[j])


# ---- T4: proximity ramp, pure ------------------------------------------------------


def test_T4_opacity_ramp():
    assert sk.telltale_opacity(1.9) == 255
    assert sk.telltale_opacity(2.0) == 255
    assert 210 <= sk.telltale_opacity(2.5) <= 212
    assert sk.telltale_opacity(3.0) == 166
    assert sk.telltale_opacity(3.1) == 166
    assert sk.telltale_opacity(40.0) == 166


def test_mid_ramp_telltale_is_present():
    with_it = sk.render(72.0, [None, 74.5, None, None], 256)
    without = sk.render(72.0, [None] * 4, 256)
    cx, cy, R = _geometry(256)
    p = sk.polar(cx, cy, 0.43 * R, sk.angle(74.5))
    assert max(abs(a - b) for a, b in zip(_px(with_it, *p), _px(without, *p))) >= 32


# ---- T5: width -------------------------------------------------------------------


def _run(img, face, angle_deg, radius, span, threshold=32):
    cx, cy, _R = _geometry(img.width)
    mid = sk.polar(cx, cy, radius, angle_deg)
    n = 0
    for k in range(-span, span + 1):
        p = sk.polar(*mid, k, angle_deg + 90)
        if max(abs(a - b) for a, b in zip(_px(img, *p), _px(face, *p))) >= threshold:
            n += 1
    return n


def test_T5_telltales_are_thinner_than_the_main_needle(dyn_256):
    face = sk.render_face(256)
    _cx, _cy, R = _geometry(256)
    runs = [_run(dyn_256, face, sk.angle(p), 0.43 * R, 8) for p in PEAKS]
    main = _run(dyn_256, face, sk.angle(VALUE), 0.45 * R, 30)
    assert all(1 <= r <= 3 for r in runs), runs
    assert all(main > r for r in runs), (main, runs)


# ---- the dynamic composition as a pinned baseline (eyeball artifact) ------------


def test_dynamic_256_matches_baseline(request, dyn_256):
    path = BASELINES / "stingray_dynamic_256.png"
    generate = request.config.getoption("--generate-baselines")
    if not path.exists():
        if generate:
            dyn_256.save(path)
            pytest.skip(f"baseline written to {path} — inspect and commit")
        pytest.fail(f"missing baseline {path}; run `pytest tests/visual/ --generate-baselines`")
    baseline = Image.open(path).convert("RGB")
    if dyn_256.tobytes() == baseline.tobytes():
        return
    rms = max(ImageStat.Stat(ImageChops.difference(dyn_256, baseline)).rms)
    if rms > RMS_TOLERANCE:
        DIFFS.mkdir(parents=True, exist_ok=True)
        ImageChops.difference(dyn_256, baseline).save(DIFFS / "stingray_dynamic_256.png")
        if generate:
            dyn_256.save(path)
        pytest.fail(f"dynamic composition drifted: rms={rms:.4f} > {RMS_TOLERANCE}")


# ---- API -----------------------------------------------------------------------


def test_render_reads_current_peak_from_telltale_instances():
    t = Telltale(60.0)
    t.update(0.0, 30.0)
    fresh = [Telltale(600.0), Telltale(3600.0), Telltale(None)]
    assert (sk.render(VALUE, [t, *fresh], 256).tobytes()
            == sk.render(VALUE, [30.0, None, None, None], 256).tobytes())


def test_render_requires_four_telltales():
    with pytest.raises(ValueError):
        sk.render(VALUE, [None, None, None], 256)
