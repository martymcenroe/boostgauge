"""Stingray skin renderer implementation.

Renders a 2D PIL Image of an analog tachometer with square chromed housing,
round matte-black dial face, tick marks, numerals, redline arc, main pointer,
and telltale peak-hold needles.

Issue #1: Core Gauge Renderer
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional, Tuple, TypedDict
from PIL import Image, ImageDraw, ImageFont


class TelltaleDict(TypedDict, total=False):
    m1: Optional[float]
    m10: Optional[float]
    h1: Optional[float]
    all: Optional[float]


SKIN_NAME = "stingray"


def calculate_angle(
    value: float,
    min_angle: float = 225.0,
    max_angle: float = -45.0,
    min_val: float = 0.0,
    max_val: float = 100.0,
) -> float:
    """Map scalar metric value to angular position in degrees (clockwise sweep from lower-left)."""
    if min_val == max_val:
        return min_angle
    clamped_val = max(min_val, min(max_val, value))
    fraction = (clamped_val - min_val) / (max_val - min_val)
    return min_angle + fraction * (max_angle - min_angle)


def get_gauge_font(
    canvas_size: int, font_size_pct: float
) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    """Resolve period sans-serif font sized to canvas."""
    font_size = max(10, int(canvas_size * font_size_pct))
    font_names = ["eurostile.ttf", "helvetica.ttf", "arial.ttf", "dejavusans.ttf"]
    for font_name in font_names:
        try:
            return ImageFont.truetype(font_name, font_size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_housing_and_bezel(draw: ImageDraw.ImageDraw, canvas_size: int) -> None:
    """Draw square housing with rounded chamfered corners and polished chrome bezel gradient."""
    margin = int(canvas_size * 0.02)
    corner_radius = int(canvas_size * 0.08)

    draw.rounded_rectangle(
        [margin, margin, canvas_size - margin, canvas_size - margin],
        radius=corner_radius,
        fill=(30, 30, 30, 255),
        outline=(70, 70, 70, 255),
        width=int(canvas_size * 0.01),
    )

    bezel_margin = int(canvas_size * 0.05)
    draw.ellipse(
        [bezel_margin, bezel_margin, canvas_size - bezel_margin, canvas_size - bezel_margin],
        fill=(180, 180, 180, 255),
        outline=(230, 230, 230, 255),
        width=int(canvas_size * 0.015),
    )


def draw_dial_face(draw: ImageDraw.ImageDraw, canvas_size: int) -> None:
    """Draw recessed circular matte-black dial face centered inside housing."""
    dial_margin = int(canvas_size * 0.08)
    draw.ellipse(
        [dial_margin, dial_margin, canvas_size - dial_margin, canvas_size - dial_margin],
        fill=(18, 18, 18, 255),
        outline=(10, 10, 10, 255),
        width=int(canvas_size * 0.01),
    )


def draw_redline_arc(draw: ImageDraw.ImageDraw, canvas_size: int) -> None:
    """Draw redline arc band hugging outer tick ring from 60 to 100 value positions."""
    margin = int(canvas_size * 0.12)
    bbox = [margin, margin, canvas_size - margin, canvas_size - margin]

    # PIL arc angles: 0° = 3 o'clock, clockwise positive.
    # gauge angle 225° (value=0) is lower-left; gauge uses standard math angles (CCW).
    # PIL start/end: negate gauge angles to convert CCW->CW, then add 0° offset (3 o'clock = 0°).
    # gauge angle for value=100 is -45° -> PIL angle = 45°  (lower-right, past 3 o'clock)
    # gauge angle for value=60 is 225 + 0.6*(-270) = 225 - 162 = 63° -> PIL angle = -63° = 297°
    # Arc drawn from 315° (lower-right boundary) to 297° going clockwise wraps the short way,
    # so we draw from PIL 45° to 297° (the redline band from value=100 back to value=60).
    start_angle = 45   # PIL angle for gauge -45° (value=100, lower-right)
    end_angle = 297    # PIL angle for gauge 63° (value=60)
    draw.arc(bbox, start=start_angle, end=end_angle, fill=(230, 34, 20, 255), width=int(canvas_size * 0.025))


def draw_ticks_and_numerals(draw: ImageDraw.ImageDraw, canvas_size: int) -> None:
    """Draw 11 major tick marks (0-100), 40 minor tick marks, and white numerals."""
    cx, cy = canvas_size / 2.0, canvas_size / 2.0
    outer_r = canvas_size * 0.38
    major_len = canvas_size * 0.05
    minor_len = canvas_size * 0.025
    text_r = canvas_size * 0.30

    font = get_gauge_font(canvas_size, 0.04)

    for i in range(51):
        val = i * 2.0
        angle_deg = calculate_angle(val)
        angle_rad = math.radians(angle_deg)

        cos_a = math.cos(angle_rad)
        sin_a = -math.sin(angle_rad)  # Screen y is inverted relative to math y

        is_major = (i % 5 == 0)
        tick_len = major_len if is_major else minor_len
        tick_width = max(1, int(canvas_size * (0.008 if is_major else 0.004)))

        x_outer = cx + outer_r * cos_a
        y_outer = cy + outer_r * sin_a
        x_inner = cx + (outer_r - tick_len) * cos_a
        y_inner = cy + (outer_r - tick_len) * sin_a

        draw.line([(x_inner, y_inner), (x_outer, y_outer)], fill=(240, 240, 240, 255), width=tick_width)

        if is_major:
            numeral_str = str(int(val))
            x_text = cx + text_r * cos_a
            y_text = cy + text_r * sin_a

            bbox = font.getbbox(numeral_str)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            draw.text((x_text - w / 2.0, y_text - h / 2.0), numeral_str, fill=(240, 240, 240, 255), font=font)


def draw_wordmark(draw: ImageDraw.ImageDraw, canvas_size: int) -> None:
    """Draw white BOOSTGAUGE small-caps brand wordmark below center pivot."""
    cx, cy = canvas_size / 2.0, canvas_size / 2.0
    font = get_gauge_font(canvas_size, 0.035)
    wordmark = "BOOSTGAUGE"

    y_pos = cy + canvas_size * 0.18
    bbox = font.getbbox(wordmark)
    w = bbox[2] - bbox[0]
    draw.text((cx - w / 2.0, y_pos), wordmark, fill=(200, 200, 200, 200), font=font)


def draw_needle(
    draw: ImageDraw.ImageDraw,
    angle_deg: float,
    canvas_size: int,
    color: Tuple[int, int, int, int],
    width_pct: float = 1.0,
    is_dashed: bool = False,
) -> None:
    """Draw tapered pointer needle with counterweight at specified angle and style."""
    cx, cy = canvas_size / 2.0, canvas_size / 2.0
    angle_rad = math.radians(angle_deg)

    cos_a = math.cos(angle_rad)
    sin_a = -math.sin(angle_rad)

    pointer_r = canvas_size * 0.36
    counterweight_r = canvas_size * 0.08
    base_width = canvas_size * 0.015 * width_pct

    x_tip = cx + pointer_r * cos_a
    y_tip = cy + pointer_r * sin_a

    x_tail = cx - counterweight_r * cos_a
    y_tail = cy - counterweight_r * sin_a

    line_width = max(1, int(base_width))

    if is_dashed:
        # Approximate dashed line by drawing segments
        segments = 8
        for seg in range(segments):
            if seg % 2 == 0:
                t0 = seg / segments
                t1 = (seg + 0.6) / segments
                sx0 = x_tail + t0 * (x_tip - x_tail)
                sy0 = y_tail + t0 * (y_tip - y_tail)
                sx1 = x_tail + t1 * (x_tip - x_tail)
                sy1 = y_tail + t1 * (y_tip - y_tail)
                draw.line([(sx0, sy0), (sx1, sy1)], fill=color, width=line_width)
    else:
        draw.line([(x_tail, y_tail), (x_tip, y_tip)], fill=color, width=line_width)


def draw_telltales(
    base_img: Image.Image,
    telltales: Optional[TelltaleDict],
    canvas_size: int,
) -> Image.Image:
    """Overlay translucent telltale needles behind main needle."""
    if not telltales:
        return base_img

    telltale_layer = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    layer_draw = ImageDraw.Draw(telltale_layer)

    specs = [
        ("m1", (0, 220, 255, 170), 0.6, False),
        ("m10", (255, 165, 0, 170), 0.6, False),
        ("h1", (255, 0, 255, 170), 0.6, True),
        ("all", (230, 34, 20, 170), 0.6, False),
    ]

    for key, color, width_pct, is_dashed in specs:
        val = telltales.get(key)
        if val is not None:
            angle_deg = calculate_angle(val)
            draw_needle(
                layer_draw,
                angle_deg,
                canvas_size,
                color=color,
                width_pct=width_pct,
                is_dashed=is_dashed,
            )

    return Image.alpha_composite(base_img, telltale_layer)


def draw_pivot_cap(draw: ImageDraw.ImageDraw, canvas_size: int) -> None:
    """Draw polished chrome circular pivot cap and mounting detail dots at dial center."""
    cx, cy = canvas_size / 2.0, canvas_size / 2.0
    cap_r = canvas_size * 0.04

    draw.ellipse(
        [cx - cap_r, cy - cap_r, cx + cap_r, cy + cap_r],
        fill=(220, 220, 220, 255),
        outline=(50, 50, 50, 255),
        width=max(1, int(canvas_size * 0.005)),
    )

    dot_r = canvas_size * 0.005
    dot_offset = canvas_size * 0.015
    draw.ellipse(
        [cx - dot_offset - dot_r, cy - dot_r, cx - dot_offset + dot_r, cy + dot_r],
        fill=(40, 40, 40, 255),
    )
    draw.ellipse(
        [cx + dot_offset - dot_r, cy - dot_r, cx + dot_offset + dot_r, cy + dot_r],
        fill=(40, 40, 40, 255),
    )


def render_stingray(
    value: float,
    telltales: Optional[TelltaleDict] = None,
    size: int = 256,
    config: Optional[Dict[str, Any]] = None,
) -> Image.Image:
    """Render Stingray skin tachometer image at requested pixel size using 2x supersampling."""
    scale = 2
    canvas_size = size * scale

    img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    draw_housing_and_bezel(draw, canvas_size)
    draw_dial_face(draw, canvas_size)
    draw_redline_arc(draw, canvas_size)
    draw_ticks_and_numerals(draw, canvas_size)
    draw_wordmark(draw, canvas_size)

    img = draw_telltales(img, telltales, canvas_size)
    draw = ImageDraw.Draw(img)

    main_angle = calculate_angle(value)
    draw_needle(draw, main_angle, canvas_size, color=(230, 34, 20, 255), width_pct=1.0)

    draw_pivot_cap(draw, canvas_size)

    return img.resize((size, size), resample=Image.Resampling.LANCZOS)