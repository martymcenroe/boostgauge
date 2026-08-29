"""
Issue #331: static face renderer — bezel, chrome housing, dial, ticks, numerals, wordmark, screws
"""
import math
from typing import Dict, Tuple
from PIL import Image, ImageDraw, ImageFont

_FACE_CACHE: Dict[Tuple[int, str], Image.Image] = {}


def render_face(size: int, skin: str = "stingray") -> Image.Image:
    """
    Renders or retrieves the cached static face for the Stingray gauge.
    Raises ValueError if size is less than 128.
    """
    if size < 128:
        raise ValueError(f"Size {size} must be >= 128")

    cache_key = (size, skin)
    if cache_key in _FACE_CACHE:
        return _FACE_CACHE[cache_key]

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    R = 0.40 * size
    cx = size / 2.0
    cy = size / 2.0

    def val_to_angle(v: float) -> float:
        return 225.0 - 2.7 * v

    # S7: Chrome housing — chamfered square, horizontal brightness gradient
    chamfer = 0.13 * size
    chrome_mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(chrome_mask).rounded_rectangle(
        [0, 0, size - 1, size - 1], radius=chamfer, fill=255
    )
    chrome = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    chrome_draw = ImageDraw.Draw(chrome)
    for x in range(size):
        v = 50 + int((x / size) * 180)
        chrome_draw.line([(x, 0), (x, size)], fill=(v, v, v, 255))
    img.paste(chrome, (0, 0), mask=chrome_mask)

    draw = ImageDraw.Draw(img)

    # S9: Bezel seat — dark annulus at 1.01 R
    seat_r = 1.01 * R
    draw.ellipse(
        [cx - seat_r, cy - seat_r, cx + seat_r, cy + seat_r],
        fill=(60, 60, 60, 255),
    )

    # S1: Dial face — flat #0A0A0C
    draw.ellipse(
        [cx - R, cy - R, cx + R, cy + R],
        fill=(10, 10, 12, 255),
    )

    # S2: Redline band — #AA0F19, 0.88 R to 1.00 R, values 60–100
    # val_to_angle(60) = 63° (math CCW); val_to_angle(100) = -45° (math CCW)
    # PIL pieslice: 0° = 3 o'clock, CW positive -> math 63° = PIL -63°, math -45° = PIL 45°
    band = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    band_draw = ImageDraw.Draw(band)
    band_draw.pieslice(
        [cx - R, cy - R, cx + R, cy + R],
        start=-63,
        end=45,
        fill=(170, 15, 25, 255),
    )
    band_draw.ellipse(
        [cx - 0.88 * R, cy - 0.88 * R, cx + 0.88 * R, cy + 0.88 * R],
        fill=(0, 0, 0, 0),
    )
    img.alpha_composite(band)

    # Refresh draw context after alpha_composite
    draw = ImageDraw.Draw(img)

    # S3 & S4: Ticks — drawn as filled polygons (4-corner rotated rectangles)
    # draw.line with floating-point endpoints and sub-pixel widths is unreliable;
    # polygon fill guarantees pixel coverage at the sampled midpoint positions.
    for v in range(101):
        if v % 10 == 0:
            length = 0.10 * R
            hw = max(1.0, 0.025 * R / 2.0)
        elif v % 2 == 0:
            length = 0.05 * R
            hw = max(1.0, 0.012 * R / 2.0)
        else:
            continue

        ang = val_to_angle(v)
        rad = math.radians(ang)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)

        # Radial direction in image space: (cos_a, -sin_a)
        # Perpendicular in image space: (sin_a, cos_a)
        ox = cx + R * cos_a
        oy = cy - R * sin_a
        ix = cx + (R - length) * cos_a
        iy = cy - (R - length) * sin_a

        dx = sin_a * hw
        dy = cos_a * hw

        pts = [
            (ix - dx, iy - dy),
            (ix + dx, iy + dy),
            (ox + dx, oy + dy),
            (ox - dx, oy - dy),
        ]
        draw.polygon(pts, fill=(255, 255, 255, 255))

    # S5: Numerals — #FFFFFF at 0.72 R
    try:
        font_num = ImageFont.truetype(r"C:\Windows\Fonts\bahnschrift.ttf", int(0.11 * R))
        font_word = ImageFont.truetype(r"C:\Windows\Fonts\bahnschrift.ttf", int(0.09 * R))
    except (IOError, OSError):
        font_num = ImageFont.load_default()
        font_word = ImageFont.load_default()

    for v in range(0, 101, 10):
        ang = val_to_angle(v)
        rad = math.radians(ang)
        nx = cx + 0.72 * R * math.cos(rad)
        ny = cy - 0.72 * R * math.sin(rad)
        text = str(v)
        bb = draw.textbbox((0, 0), text, font=font_num)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        draw.text(
            (nx - tw / 2, ny - th / 2),
            text,
            font=font_num,
            fill=(255, 255, 255, 255),
        )

    # S6: Wordmark — "BOOSTGAUGE" centred at 0.67 R below pivot
    wr = math.radians(270)
    wx = cx + 0.67 * R * math.cos(wr)
    wy = cy - 0.67 * R * math.sin(wr)
    wtext = "BOOSTGAUGE"
    wbb = draw.textbbox((0, 0), wtext, font=font_word)
    wtw, wth = wbb[2] - wbb[0], wbb[3] - wbb[1]
    draw.text(
        (wx - wtw / 2, wy - wth / 2),
        wtext,
        font=font_word,
        fill=(255, 255, 255, 255),
    )

    # S8: Screws — flat #1A1A1C at ±0.25 R horizontal
    screw_r = 0.020 * R
    for offset in [-0.25 * R, 0.25 * R]:
        sx = cx + offset
        draw.ellipse(
            [sx - screw_r, cy - screw_r, sx + screw_r, cy + screw_r],
            fill=(26, 26, 28, 255),
        )

    _FACE_CACHE[cache_key] = img
    return img