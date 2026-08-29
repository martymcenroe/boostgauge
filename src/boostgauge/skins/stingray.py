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
    draw = ImageDraw.Draw(img)

    R = 0.40 * size
    cx = size / 2.0
    cy = size / 2.0

    def polar_to_xy(r, angle_deg):
        rad = math.radians(angle_deg)
        return (cx + r * math.cos(rad), cy - r * math.sin(rad))

    def val_to_angle(v):
        return 225 - 2.7 * v

    # S7: Chrome housing — gradient square with chamfered corners
    chamfer = 0.13 * size
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=chamfer, fill=255)

    chrome = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    chrome_draw = ImageDraw.Draw(chrome)
    for x in range(size):
        v = 50 + int((x / size) * 180)
        chrome_draw.line([(x, 0), (x, size)], fill=(v, v, v, 255))

    img.paste(chrome, (0, 0), mask=mask)

    # S9: Bezel seat — dark annulus just outside dial edge
    seat_r = 1.01 * R
    draw.ellipse(
        [cx - seat_r, cy - seat_r, cx + seat_r, cy + seat_r],
        fill=(60, 60, 60, 255),
    )

    # S1: Dial face — flat #0A0A0C
    draw.ellipse([cx - R, cy - R, cx + R, cy + R], fill="#0A0A0C")

    # S2: Redline band — #AA0F19, inner 0.88R to outer R, values 60–100
    # angle(60)=63°, angle(100)=-45°(=315°); PIL pieslice is clockwise from +x
    bbox_outer = [cx - R, cy - R, cx + R, cy + R]
    bbox_inner = [cx - 0.88 * R, cy - 0.88 * R, cx + 0.88 * R, cy + 0.88 * R]

    band_mask = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    band_draw = ImageDraw.Draw(band_mask)
    band_draw.pieslice(bbox_outer, -63, 45, fill="#AA0F19")
    band_draw.ellipse(bbox_inner, fill=(0, 0, 0, 0))
    img.alpha_composite(band_mask)

    # Recreate draw after alpha_composite to ensure it references the current buffer
    draw = ImageDraw.Draw(img)

    # S3 & S4: Ticks — white strokes at R, radiating inward
    # Width uses ceil-rounding so the fat-line polygon covers the midpoint sample pixel
    # even at 45° diagonals where Bresenham's integer rasterization skips a corner pixel.
    for v in range(101):
        angle_deg = val_to_angle(v)
        if v % 10 == 0:
            length = 0.10 * R
            width = max(3, math.ceil(0.025 * R))
        elif v % 2 == 0:
            length = 0.05 * R
            width = max(2, math.ceil(0.012 * R))
        else:
            continue

        outer_pt = polar_to_xy(R, angle_deg)
        inner_pt = polar_to_xy(R - length, angle_deg)
        draw.line([inner_pt, outer_pt], fill="#FFFFFF", width=width)

    # S5 & S6: Font — Bahnschrift preferred, default fallback for CI
    try:
        font_num = ImageFont.truetype(r"C:\Windows\Fonts\bahnschrift.ttf", int(0.11 * R))
        font_word = ImageFont.truetype(r"C:\Windows\Fonts\bahnschrift.ttf", int(0.09 * R))
    except IOError:
        font_num = ImageFont.load_default()
        font_word = ImageFont.load_default()

    # S5: Numerals at 0.72R
    for v in range(0, 101, 10):
        angle_deg = val_to_angle(v)
        num_pt = polar_to_xy(0.72 * R, angle_deg)
        text = str(v)
        bbox = draw.textbbox((0, 0), text, font=font_num)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text(
            (num_pt[0] - tw / 2, num_pt[1] - th / 2),
            text,
            font=font_num,
            fill="#FFFFFF",
        )

    # S6: Wordmark centred 0.67R below pivot
    word_pt = polar_to_xy(0.67 * R, 270)
    text = "BOOSTGAUGE"
    bbox = draw.textbbox((0, 0), text, font=font_word)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text(
        (word_pt[0] - tw / 2, word_pt[1] - th / 2),
        text,
        font=font_word,
        fill="#FFFFFF",
    )

    # S8: Screws at ±0.25R from pivot, radius 0.020R, flat #1A1A1C
    screw_r = 0.020 * R
    for offset in [-0.25 * R, 0.25 * R]:
        sx = cx + offset
        sy = cy
        draw.ellipse(
            [sx - screw_r, sy - screw_r, sx + screw_r, sy + screw_r],
            fill="#1A1A1C",
        )

    _FACE_CACHE[cache_key] = img
    return img