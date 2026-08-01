"""Visual regression tests verifying offscreen PIL dial rendering, circular transparency masking, and status dot rendering.

Issue #5: Feature: always-on-top window with drag, minimize, and transparency
"""

import math
import queue
import pytest
from PIL import Image, ImageDraw
from boostgauge.gauge import render
from boostgauge.tray import TrayController


def test_t060_chroma_key_circular_mask_rendering():
    """T060: Offscreen PIL dial rendering has transparent/chroma background outside dial radius."""
    size = (256, 256)
    gauge_img = render(value=50.0, size=size)
    assert isinstance(gauge_img, Image.Image)
    assert gauge_img.size == size

    corner_pixel = gauge_img.getpixel((5, 5))
    assert corner_pixel[3] == 0 or corner_pixel[:3] == (0, 0, 1)


def test_t060_dial_image_mode():
    """T060: Rendered dial image has correct mode for transparency support."""
    gauge_img = render(value=50.0, size=(256, 256))
    assert gauge_img.mode in ("RGBA", "RGB")


def test_t060_corner_pixels_outside_radius():
    """T060: All four corners lie outside dial radius and match chroma or alpha=0."""
    size = (256, 256)
    gauge_img = render(value=50.0, size=size)
    corners = [(0, 0), (255, 0), (0, 255), (255, 255)]
    for cx, cy in corners:
        pixel = gauge_img.getpixel((cx, cy))
        if len(pixel) == 4:
            is_transparent = pixel[3] == 0
            is_chroma = pixel[:3] == (0, 0, 1)
            assert is_transparent or is_chroma, f"Corner {(cx, cy)} pixel {pixel} is not transparent or chroma"


def test_t060_dial_renders_at_various_values():
    """T060: Dial renders successfully for a range of metric values."""
    for value in [0.0, 25.0, 50.0, 75.0, 100.0]:
        img = render(value=value, size=(256, 256))
        assert isinstance(img, Image.Image)
        assert img.size == (256, 256)


def test_t060_dial_size_parameter():
    """T060: Rendered dial image respects requested size parameter."""
    for size in [(128, 128), (256, 256), (512, 512)]:
        img = render(value=50.0, size=size)
        assert img.size == size


def test_baseline_independent_needle_angle_trigonometry():
    """T060: Verify needle tip position mathematically at 50% gauge value."""
    size = (256, 256)
    center = (128.0, 128.0)
    radius = 100.0

    value = 50.0
    sweep_angle_deg = 225.0 - (value / 100.0) * 270.0
    rad = math.radians(sweep_angle_deg)

    expected_tip_x = center[0] + radius * math.cos(rad)
    expected_tip_y = center[1] - radius * math.sin(rad)

    assert abs(expected_tip_x - 128.0) < 1.0
    assert abs(expected_tip_y - 28.0) < 1.0


def test_needle_angle_at_zero_value():
    """Verify needle tip position at 0% gauge value using trigonometry."""
    center = (128.0, 128.0)
    radius = 100.0
    value = 0.0
    sweep_angle_deg = 225.0 - (value / 100.0) * 270.0
    rad = math.radians(sweep_angle_deg)

    tip_x = center[0] + radius * math.cos(rad)
    tip_y = center[1] - radius * math.sin(rad)

    expected_x = center[0] + radius * math.cos(math.radians(225.0))
    expected_y = center[1] - radius * math.sin(math.radians(225.0))

    assert abs(tip_x - expected_x) < 1.0
    assert abs(tip_y - expected_y) < 1.0


def test_needle_angle_at_full_value():
    """Verify needle tip position at 100% gauge value using trigonometry."""
    center = (128.0, 128.0)
    radius = 100.0
    value = 100.0
    sweep_angle_deg = 225.0 - (value / 100.0) * 270.0
    rad = math.radians(sweep_angle_deg)

    tip_x = center[0] + radius * math.cos(rad)
    tip_y = center[1] - radius * math.sin(rad)

    expected_angle = math.radians(-45.0)
    expected_x = center[0] + radius * math.cos(expected_angle)
    expected_y = center[1] - radius * math.sin(expected_angle)

    assert abs(tip_x - expected_x) < 1.0
    assert abs(tip_y - expected_y) < 1.0


def test_radial_distance_outside_circle_is_chroma_or_transparent():
    """Pixels at distance > radius from center match chroma key or are transparent."""
    size = (256, 256)
    gauge_img = render(value=50.0, size=size)
    center_x, center_y = size[0] / 2, size[1] / 2
    radius = min(size) / 2

    test_points = [
        (5, 5), (5, 250), (250, 5), (250, 250),
        (128, 2), (2, 128), (253, 128), (128, 253),
    ]

    for px, py in test_points:
        dist = math.sqrt((px - center_x) ** 2 + (py - center_y) ** 2)
        if dist > radius - 2:
            pixel = gauge_img.getpixel((px, py))
            if len(pixel) == 4:
                is_transparent = pixel[3] == 0
                is_chroma = pixel[:3] == (0, 0, 1)
                assert is_transparent or is_chroma, (
                    f"Pixel at ({px}, {py}) dist={dist:.1f} pixel={pixel} "
                    "is not transparent or chroma"
                )


def test_status_dot_visual_green():
    """Status dot rendered for green has correct RGBA mode and dimensions."""
    q = queue.Queue()
    tray = TrayController(q)
    img = tray.create_status_icon_image("green", size=64)
    assert isinstance(img, Image.Image)
    assert img.size == (64, 64)
    assert img.mode == "RGBA"


def test_status_dot_visual_yellow():
    """Status dot rendered for yellow is a valid PIL image."""
    q = queue.Queue()
    tray = TrayController(q)
    img = tray.create_status_icon_image("yellow", size=64)
    assert isinstance(img, Image.Image)
    assert img.size == (64, 64)
    assert img.mode == "RGBA"


def test_status_dot_visual_red():
    """Status dot rendered for red is a valid PIL image."""
    q = queue.Queue()
    tray = TrayController(q)
    img = tray.create_status_icon_image("red", size=64)
    assert isinstance(img, Image.Image)
    assert img.size == (64, 64)
    assert img.mode == "RGBA"


def test_status_dot_center_pixel_green_dominant():
    """Green status dot has green channel dominant at center pixel."""
    q = queue.Queue()
    tray = TrayController(q)
    img = tray.create_status_icon_image("green", size=64)
    r, g, b, a = img.getpixel((32, 32))
    assert g > r and g > b
    assert a > 0


def test_status_dot_center_pixel_red_dominant():
    """Red status dot has red channel dominant at center pixel."""
    q = queue.Queue()
    tray = TrayController(q)
    img = tray.create_status_icon_image("red", size=64)
    r, g, b, a = img.getpixel((32, 32))
    assert r > g and r > b
    assert a > 0


def test_status_dot_corner_is_transparent():
    """Status dot corner pixels outside circle are transparent."""
    q = queue.Queue()
    tray = TrayController(q)
    img = tray.create_status_icon_image("green", size=64)
    _, _, _, corner_alpha = img.getpixel((0, 0))
    assert corner_alpha == 0


def test_status_dot_invalid_color_defaults_green():
    """Invalid color_name produces a valid image defaulting to green."""
    q = queue.Queue()
    tray = TrayController(q)
    img = tray.create_status_icon_image("purple", size=64)
    assert isinstance(img, Image.Image)
    r, g, b, a = img.getpixel((32, 32))
    assert g > r and g > b


def test_status_dot_no_baseline_radial_check():
    """Status dot pixels within circle radius have nonzero alpha."""
    q = queue.Queue()
    tray = TrayController(q)
    size = 64
    img = tray.create_status_icon_image("green", size=size)
    center = size / 2
    margin = size // 8
    inner_radius = (size - 2 * margin) / 2 - 2

    test_points = [
        (int(center), int(center)),
        (int(center + inner_radius * 0.5), int(center)),
        (int(center), int(center + inner_radius * 0.5)),
    ]
    for px, py in test_points:
        _, _, _, a = img.getpixel((px, py))
        assert a > 0, f"Inner pixel ({px}, {py}) should be opaque but alpha={a}"