"""Test file for Issue #1.

Emitted by AssemblyZero from the implementation spec's Section 10
test functions. Bodies are the spec's own, verbatim (#2316).
"""

import sys
import math
from pathlib import Path
import pytest
from PIL import Image

# Use platform-independent paths per Issue #1841
BASELINE_DIR = Path(__file__).resolve().parent / "baselines"

class MockTelltale:
    def __init__(self, peak: float | None):
        self._peak = peak
    def current_peak(self) -> float | None:
        return self._peak

def _load_baseline(request, name: str, img: Image.Image) -> Image.Image:
    path = BASELINE_DIR / f"{name}.png"
    if request.config.getoption("--generate-baselines"):
        path.parent.mkdir(parents=True, exist_ok=True)
        img.save(path)
    return Image.open(path)

# TDD: this import fails until the implementation exists (RED phase)
from boostgauge.skins.stingray import *  # noqa: F401, F403


def test_req_1_pure_function():
    # REQ-1: The renderer shall produce a PIL.Image ... with no tkinter imports.
    from boostgauge.skins.stingray import render
    img = render(0, [])
    assert isinstance(img, Image.Image)
    assert "tkinter" not in sys.modules


def test_req_2_determinism():
    # REQ-2: The renderer shall produce byte-identical images for identical inputs.
    from boostgauge.skins.stingray import render
    img1 = render(50, [])
    img2 = render(50, [])
    assert img1.tobytes() == img2.tobytes()


def test_req_3_baseline_zero(request):
    # REQ-3: Baseline comparison value=0
    from boostgauge.skins.stingray import render
    img = render(0, [])
    baseline = _load_baseline(request, "value_0", img)
    assert img.tobytes() == baseline.tobytes()


def test_req_4_static_equivalence():
    # REQ-4: The image at value=100 with no telltales shall render every static element identically to the value=0 image.
    from boostgauge.skins.stingray import render
    img_0 = render(0, [])
    img_100 = render(100, [])
    matching_pixels = sum(1 for p1, p2 in zip(img_0.getdata(), img_100.getdata()) if p1 == p2)
    assert matching_pixels > (256 * 256 * 0.95)

# [baseline-independent]


def test_req_5_needle_angles():
    # REQ-5: The main needle shall render on the axis angle(value) = 225° - 2.7° * value.
    from boostgauge.skins.stingray import render
    size = 256
    cx, cy = size/2, size/2
    r_base = size/2 * 0.95
    r_test = r_base * 0.8
    
    for value, expected_angle in [(0, 225.0), (50, 90.0), (100, -45.0)]:
        img = render(value, [])
        rad = math.radians(expected_angle)
        px, py = int(cx + r_test*math.cos(rad)), int(cy - r_test*math.sin(rad))
        pixel_color = img.getpixel((px, py))[:3]
        assert math.dist(pixel_color, (247, 57, 35)) < 64 # Tolerate anti-aliasing

# [baseline-independent]


def test_req_6_hue_distinction():
    # REQ-6: At value=75, the main needle's tip lies inside the redline band; tip pixels and band pixels must be distinct.
    from boostgauge.skins.stingray import render
    img = render(75, [])
    angle = 225.0 - (2.7 * 75.0)
    rad = math.radians(angle)
    r_base = 256/2 * 0.95
    
    # Check a point inside both the redline band and the needle
    r_needle_in_band = 105.2
    px, py = int(128 + r_needle_in_band*math.cos(rad)), int(128 - r_needle_in_band*math.sin(rad))
    needle_pixel = img.getpixel((px, py))[:3]
    assert math.dist(needle_pixel, (247, 57, 35)) < 64
    
    # Check a point inside the redline band but beyond the needle tip
    r_band_only = 115.2
    band_color = (155, 48, 32)
    px_b, py_b = int(128 + r_band_only*math.cos(rad)), int(128 - r_band_only*math.sin(rad))
    band_pixel = img.getpixel((px_b, py_b))[:3]
    assert math.dist(band_pixel, band_color) < 64


def test_req_7_telltale_none():
    # REQ-7: A telltale whose peak is None shall not be rendered.
    from boostgauge.skins.stingray import render
    img1 = render(50, [])
    img2 = render(50, [MockTelltale(None)])
    assert img1.tobytes() == img2.tobytes()


def test_req_8_telltale_far():
    # REQ-8: d >= 3 renders at baseline translucency.
    from boostgauge.skins.stingray import render
    img = render(70, [MockTelltale(30)])
    angle = 225.0 - (2.7 * 30.0)
    rad = math.radians(angle)
    px, py = int(128 + 60*math.cos(rad)), int(128 - 60*math.sin(rad))
    assert 50 < img.getpixel((px, py))[0] < 90


def test_req_9_telltale_mid():
    # REQ-9: 2 < d < 3 renders exactly halfway at 2.5 distance.
    from boostgauge.skins.stingray import render
    img = render(70, [MockTelltale(72.5)])
    angle = 225.0 - (2.7 * 72.5)
    rad = math.radians(angle)
    px, py = int(128 + 60*math.cos(rad)), int(128 - 60*math.sin(rad))
    assert 120 < img.getpixel((px, py))[0] < 180


def test_req_10_telltale_close():
    # REQ-10: d <= 2 renders at 100% opacity.
    from boostgauge.skins.stingray import render
    img = render(70, [MockTelltale(72)])
    angle = 225.0 - (2.7 * 72.0)
    rad = math.radians(angle)
    px, py = int(128 + 60*math.cos(rad)), int(128 - 60*math.sin(rad))
    assert img.getpixel((px, py))[0] > 180


def test_req_11_four_telltales():
    # REQ-11: With all four telltales at varying non-coincident peak values, four distinct needles visible.
    from boostgauge.skins.stingray import render
    telltales = [MockTelltale(10), MockTelltale(20), MockTelltale(80), MockTelltale(90)]
    img = render(50, telltales)
    for peak in (10, 20, 80, 90):
        angle = 225.0 - (2.7 * peak)
        rad = math.radians(angle)
        px, py = int(128 + 60*math.cos(rad)), int(128 - 60*math.sin(rad))
        assert img.getpixel((px, py))[0] > 40

@pytest.mark.parametrize("value,peaks,name", [
    (0, [], "value_0_clean"),
    (50, [], "value_50_clean"),
    (75, [80, 100], "value_75_complex"),
    (80, [80], "value_80_telltale_coincident"),
    (100, [], "value_100_clean"),
    (70, [72], "value_70_t2_distance"),
    (70, [72.5], "value_70_t3_distance"),
    (70, [30], "value_70_t4_distance"),
    (0, [10, 20], "value_0_telltales_post_reset")
])


def test_req_12_full_baseline(request, value, peaks, name):
    # REQ-12: Full matrix of baselines
    from boostgauge.skins.stingray import render
    telltales = [MockTelltale(p) for p in peaks]
    img = render(value, telltales)
    baseline = _load_baseline(request, name, img)
    assert img.tobytes() == baseline.tobytes()


def test_req_13_resolution():
    # REQ-13: Resolution dynamic allocation correctly produces square bounded boxes.
    from boostgauge.skins.stingray import render
    img = render(0, [], size=128)
    assert img.size == (128, 128)

# [baseline-independent]


def test_req_14_band_geometry():
    # REQ-14: Redline band is drawn from 80-100% radius on 60-100 values.
    from boostgauge.skins.stingray import render
    img = render(0, [])
    rad = math.radians(9)
    cx, cy = 128, 128
    
    r_in = 128 * 0.90
    px_in, py_in = int(cx + r_in*math.cos(rad)), int(cy - r_in*math.sin(rad))
    pixel_in = img.getpixel((px_in, py_in))[:3]
    assert math.dist(pixel_in, (155, 48, 32)) < 64
    
    r_out = 128 * 0.70
    px_out, py_out = int(cx + r_out*math.cos(rad)), int(cy - r_out*math.sin(rad))
    pixel_out = img.getpixel((px_out, py_out))[:3]
    assert math.dist(pixel_out, (155, 48, 32)) > 64
