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

    # S7: Chrome housing — chamfered square with horizontal gradient
    chamfer = 0.13 * size
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=chamfer, fill=255)

    chrome = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    chrome_draw = ImageDraw.Draw(chrome)
    for x in range(size):
        v = 50 + int((x / size) * 180)
        chrome_draw.line([(x, 0), (x, size)], fill=(v, v, v, 255))

    img.paste(chrome, (0, 0), mask=mask)

    # S9: Bezel seat just outside dial edge at 1.01 R
    seat_r = 1.01 * R
    draw.ellipse(
        [cx - seat_r, cy - seat_r, cx + seat_r, cy + seat_r],
        fill=(60, 60, 60, 255),
    )

    # S1: Dial face — flat #0A0A0C, radius R
    draw.ellipse([cx - R, cy - R, cx + R, cy + R], fill=(10, 10, 12, 255))

    # S2: Redline band — #AA0F19, inner 0.88 R to outer 1.00 R, values 60–100
    # val=60 -> math angle 63 deg, val=100 -> math angle -45 deg (315 deg)
    # PIL pieslice: 0 = 3 o'clock, clockwise positive
    # math angle -> PIL angle: PIL_angle = -math_angle (mod 360) then shift
    # math 63 deg CCW = PIL -63 deg = PIL 297 deg (start)
    # math -45 deg CCW = PIL 45 deg (end)
    band_img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    band_draw = ImageDraw.Draw(band_img)
    bbox_outer = [cx - R, cy - R, cx + R, cy + R]
    bbox_inner_r = 0.88 * R
    bbox_inner = [
        cx - bbox_inner_r,
        cy - bbox_inner_r,
        cx + bbox_inner_r,
        cy + bbox_inner_r,
    ]
    # PIL pieslice start/end: clockwise from 3 o'clock
    # val=100 -> math -45 -> PIL 45 (start, rightmost point of band)
    # val=60  -> math 63  -> PIL -63 = 297 (end, leftmost point of band)
    band_draw.pieslice(bbox_outer, start=45, end=297, fill=(170, 15, 25, 255))
    band_draw.ellipse(bbox_inner, fill=(0, 0, 0, 0))
    img.alpha_composite(band_img)

    # Redraw dial face center to keep flat #0A0A0C inside the band cutout
    draw.ellipse(bbox_inner, fill=(10, 10, 12, 255))

    # S3 & S4: Ticks — major at multiples of 10, minor at even values
    for v in range(101):
        angle_deg = val_to_angle(v)
        if v % 10 == 0:
            length = 0.10 * R
            width = max(1, int(0.025 * R))
        elif v % 2 == 0:
            length = 0.05 * R
            width = max(1, int(0.012 * R))
        else:
            continue

        outer_pt = polar_to_xy(R, angle_deg)
        inner_pt = polar_to_xy(R - length, angle_deg)
        draw.line([inner_pt, outer_pt], fill=(255, 255, 255, 255), width=width)

    # S5 & S6: Font setup
    try:
        font_num = ImageFont.truetype("C:\\Windows\\Fonts\\bahnschrift.ttf", int(0.11 * R))
        font_word = ImageFont.truetype("C:\\Windows\\Fonts\\bahnschrift.ttf", int(0.09 * R))
    except (IOError, OSError):
        try:
            font_num = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(0.11 * R))
            font_word = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(0.09 * R))
        except (IOError, OSError):
            font_num = ImageFont.load_default()
            font_word = ImageFont.load_default()

    # S5: Numerals — #FFFFFF, values 0–100 step 10, centres at 0.72 R
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
            fill=(255, 255, 255, 255),
        )

    # S6: Wordmark — BOOSTGAUGE, #FFFFFF, centred 0.67 R below pivot
    word_pt = polar_to_xy(0.67 * R, 270)
    text = "BOOSTGAUGE"
    bbox = draw.textbbox((0, 0), text, font=font_word)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text(
        (word_pt[0] - tw / 2, word_pt[1] - th / 2),
        text,
        font=font_word,
        fill=(255, 255, 255, 255),
    )

    # S8: Screws — 2 centres at pivot ± 0.25 R horizontal, radius 0.020 R, flat #1A1A1C
    screw_r = 0.020 * R
    for offset in [-0.25 * R, 0.25 * R]:
        sx = cx + offset
        sy = cy
        draw.ellipse(
            [sx - screw_r, sy - screw_r, sx + screw_r, sy + screw_r],
            fill=(26, 26, 28, 255),
        )

    _FACE_CACHE[cache_key] = img
    return img