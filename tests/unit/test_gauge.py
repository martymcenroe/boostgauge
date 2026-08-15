"""Unit tests for gauge orchestration and pure functions.

Issue #1: Feature: core gauge renderer
"""

import math

import pytest
from PIL import Image, ImageChops

from boostgauge.gauge import render, _validate_inputs


def test_req_010():
    # Pure function check (REQ-1) -- expected: Returns PIL.Image, no tkinter import
    img = render(0, [], 256)
    assert isinstance(img, Image.Image)


def test_req_020():
    # Deterministic output (REQ-2) -- expected: ImageChops.difference(im1, im2) is exactly 0
    img1 = render(50, [10], 256)
    img2 = render(50, [10], 256)
    diff = ImageChops.difference(img1, img2)
    assert not diff.getbbox()


def test_req_030_baseline_independent():
    # Needle angle mapping (REQ-3) -- expected: Needle exactly at 225°, 90°, -45°
    def get_tip(v, size=256):
        angle = 225.0 - 2.7 * v
        rad = math.radians(angle)
        return (int(size/2 + math.cos(rad) * size/2 * 0.95), int(size/2 - math.sin(rad) * size/2 * 0.95))

    assert render(0, [], 256).getpixel(get_tip(0)) == (247, 57, 35, 255)
    assert render(50, [], 256).getpixel(get_tip(50)) == (247, 57, 35, 255)
    assert render(100, [], 256).getpixel(get_tip(100)) == (247, 57, 35, 255)


def test_req_040():
    # Static element consistency (REQ-4) -- expected: Images differ only in pixels occupied by the candy-apple #F73923 needle
    img_0 = render(0, [], 256)
    img_100 = render(100, [], 256)
    diff = ImageChops.difference(img_0, img_100)

    bbox = diff.getbbox()
    assert bbox is not None, "Images are identical"

    # Verify differences are restricted to expected needle areas (lower half)
    min_x, min_y, max_x, max_y = bbox
    assert min_y >= 120, f"Difference detected outside expected needle bounds: {bbox}"


def test_req_050():
    # Redline band bounds (REQ-5) -- expected: Band spans 60-100 at 0.8-1.0 R
    img = render(75, [], 256)
    angle = 225.0 - 2.7 * 80
    rad = math.radians(angle)
    px = (int(128 + math.cos(rad) * 128 * 0.9), int(128 - math.sin(rad) * 128 * 0.9))
    assert img.getpixel(px) == (155, 48, 32, 255)


def test_req_060():
    # Hidden missing telltales (REQ-6) -- expected: Telltale pixels are completely absent
    img_none = render(50, [None], 256)
    img_empty = render(50, [], 256)
    diff = ImageChops.difference(img_none, img_empty)
    assert not diff.getbbox()


def test_req_070():
    # Far telltale translucency (REQ-7) -- expected: d>=3 samples at baseline translucency
    img = render(70, [35], 256)
    angle = 225.0 - 2.7 * 35
    rad = math.radians(angle)
    px = (int(128 + math.cos(rad) * 128 * 0.9), int(128 - math.sin(rad) * 128 * 0.9))
    r, g, b, a = img.getpixel(px)
    assert 60 < r < 70  # ~20% of 255 + 80% of 17 (background)
    assert 60 < g < 70
    assert 60 < b < 70
    assert a == 255


def test_req_080():
    # Mid-fade telltale opacity (REQ-8) -- expected: d=2.5 samples strictly at linear midpoint opacity
    img = render(70, [72.5], 256)
    angle = 225.0 - 2.7 * 72.5
    rad = math.radians(angle)
    px = (int(128 + math.cos(rad) * 128 * 0.9), int(128 - math.sin(rad) * 128 * 0.9))
    r, g, b, a = img.getpixel(px)
    assert 210 < r < 220  # ~60% of 255 + 40% of 155 (redline band)
    assert 167 < g < 177  # ~60% of 255 + 40% of 48
    assert 160 < b < 170  # ~60% of 255 + 40% of 32
    assert a == 255


def test_req_090():
    # Near telltale opacity (REQ-9) -- expected: d<=2 samples at 100% opacity
    img = render(70, [72], 256)
    angle = 225.0 - 2.7 * 72
    rad = math.radians(angle)
    px = (int(128 + math.cos(rad) * 128 * 0.9), int(128 - math.sin(rad) * 128 * 0.9))
    assert img.getpixel(px) == (255, 255, 255, 255)


def test_req_100():
    # In-band distinctness (REQ-10) -- expected: Tip sampled at candy-apple #F73923, band sampled at brick #9B3020
    img = render(75, [], 256)
    angle = 225.0 - 2.7 * 75
    rad = math.radians(angle)
    tip_px = (int(128 + math.cos(rad) * 128 * 0.95), int(128 - math.sin(rad) * 128 * 0.95))
    band_angle = 225.0 - 2.7 * 80
    band_rad = math.radians(band_angle)
    band_px = (int(128 + math.cos(band_rad) * 128 * 0.9), int(128 - math.sin(band_rad) * 128 * 0.9))
    assert img.getpixel(tip_px) == (247, 57, 35, 255)
    assert img.getpixel(band_px) == (155, 48, 32, 255)


def test_req_110():
    # Aspect lock resizing (REQ-11) -- expected: Output is 128x128 and 512x512 with matching proportion
    img_128 = render(50, [], 128)
    img_512 = render(50, [], 512)
    assert img_128.size == (128, 128)
    assert img_512.size == (512, 512)


def test_req_130():
    # Multiple telltales (REQ-13) -- expected: Four distinct telltale needles rendered
    img_base = render(50, [], 256)
    img = render(50, [15, 25, 85, 95], 256)
    for v in [15, 25, 85, 95]:
        angle = 225.0 - 2.7 * v
        rad = math.radians(angle)
        px = (int(128 + math.cos(rad) * 128 * 0.9), int(128 - math.sin(rad) * 128 * 0.9))
        assert img.getpixel(px) != img_base.getpixel(px)


def test_value_errors():
    # ValueError tests -- expected: ValueErrors are raised
    with pytest.raises(ValueError):
        render(-1, [], 256)
    with pytest.raises(ValueError):
        render(50, [], 100)
    with pytest.raises(ValueError):
        render(50, [], 256, config={"skin_name": "unknown"})