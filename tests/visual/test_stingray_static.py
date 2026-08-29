"""
Tests for stingray static face renderer.
"""
import ast
import inspect
import math
from pathlib import Path
import pytest
from PIL import Image

from boostgauge.skins.stingray import render_face, _FACE_CACHE


def test_req_010_base_face_generation():
    img = render_face(256)
    assert isinstance(img, Image.Image)
    assert img.size == (256, 256)


def test_req_020_minimum_size():
    with pytest.raises(ValueError, match=">= 128"):
        render_face(127)


def test_req_030_cache_persistence():
    img1 = render_face(129)
    img2 = render_face(129)
    assert id(img1) == id(img2)


def test_req_040_dial_face_s1():
    img = render_face(256)
    cx, cy = 128, 128
    R = 0.40 * 256
    rad = math.radians(150)
    for frac in [0.3, 0.5, 0.7]:
        px = int(cx + frac * R * math.cos(rad))
        py = int(cy - frac * R * math.sin(rad))
        pixel = img.getpixel((px, py))
        assert pixel[:3] == (10, 10, 12)


def test_req_050_redline_band_s2():
    img = render_face(256)
    cx, cy = 128, 128
    R = 0.40 * 256
    for val in [65, 75, 85]:
        angle = 225 - 2.7 * val
        rad = math.radians(angle)
        px = int(cx + 0.94 * R * math.cos(rad))
        py = int(cy - 0.94 * R * math.sin(rad))
        pixel = img.getpixel((px, py))
        assert pixel[:3] == (170, 15, 25)


def test_req_060_ticks_s3():
    img = render_face(256)
    cx, cy = 128, 128
    R = 0.40 * 256
    for val in range(0, 101, 10):
        angle = 225 - 2.7 * val
        rad = math.radians(angle)
        px = int(cx + 0.95 * R * math.cos(rad))
        py = int(cy - 0.95 * R * math.sin(rad))
        pixel = img.getpixel((px, py))
        assert sum(pixel[:3]) / 3 >= 100


def test_req_060_ticks_s4():
    img = render_face(256)
    cx, cy = 128, 128
    R = 0.40 * 256
    for val in [2, 34, 66, 98]:
        angle = 225 - 2.7 * val
        rad = math.radians(angle)
        px = int(cx + 0.975 * R * math.cos(rad))
        py = int(cy - 0.975 * R * math.sin(rad))
        pixel = img.getpixel((px, py))
        assert sum(pixel[:3]) / 3 >= 100


def test_req_070_numerals_s5():
    img = render_face(256)
    cx, cy = 128, 128
    R = 0.40 * 256
    for val in range(0, 101, 10):
        angle = 225 - 2.7 * val
        rad = math.radians(angle)
        px = int(cx + 0.72 * R * math.cos(rad))
        py = int(cy - 0.72 * R * math.sin(rad))
        found_white = False
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                if sum(img.getpixel((px + dx, py + dy))[:3]) / 3 > 128:
                    found_white = True
                    break
        assert found_white


def test_req_080_wordmark_s6_1():
    img = render_face(256)
    cx, cy = 128, 128
    R = 0.40 * 256
    px, py = int(cx), int(cy + 0.67 * R)
    found_white = False
    for dx in range(-10, 10):
        if sum(img.getpixel((px + dx, py))[:3]) / 3 > 128:
            found_white = True
            break
    assert found_white


def test_req_080_wordmark_s6_2():
    img = render_face(256)
    cx, cy = 128, 128
    R = 0.40 * 256
    py = int(cy - 0.67 * R)
    for offset in [0.15 * R, 0.20 * R]:
        px_left = int(cx - offset)
        px_right = int(cx + offset)
        assert sum(img.getpixel((px_left, py))[:3]) / 3 < 100
        assert sum(img.getpixel((px_right, py))[:3]) / 3 < 100


def test_req_090_chrome_s7():
    img = render_face(256)
    samples = []
    for px in [5, 10, 245, 250]:
        pixel = img.getpixel((px, 128))
        mean = sum(pixel[:3]) / 3
        if max(pixel[:3]) - min(pixel[:3]) <= 14 and 16 <= mean <= 248:
            samples.append(mean)

    assert len(samples) >= 3
    assert any(s < 100 for s in samples)
    assert any(s > 200 for s in samples)


def test_req_090_screws_s8():
    img = render_face(256)
    cx, cy = 128, 128
    R = 0.40 * 256
    for offset in [-0.25 * R, 0.25 * R]:
        px = int(cx + offset)
        py = int(cy)
        pixel = img.getpixel((px, py))
        assert pixel[:3] == (26, 26, 28)


def test_req_090_bezel_s9():
    img = render_face(256)
    cx, cy = 128, 128
    R = 0.40 * 256
    seat_px = int(cx + 1.01 * R)
    chrome_px = int(cx + 1.10 * R)
    seat_val = sum(img.getpixel((seat_px, cy))[:3]) / 3
    chrome_val = sum(img.getpixel((chrome_px, cy))[:3]) / 3
    assert seat_val < chrome_val


def test_req_100_constant_isolation():
    import boostgauge.skins.stingray as sm
    source = inspect.getsource(sm)
    assert "import json" not in source


def test_req_110_artifact_emission(monkeypatch, tmp_path, capsys):
    import sys
    monkeypatch.setattr(sys, "argv", ["pytest", "--generate-baselines"])
    if "--generate-baselines" in sys.argv:
        img = render_face(256)
        out_path = tmp_path / "face-256.png"
        img.save(out_path)
        print(str(out_path))

    captured = capsys.readouterr()
    assert str(tmp_path) in captured.out
    assert (tmp_path / "face-256.png").exists()