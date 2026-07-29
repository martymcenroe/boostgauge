"""Stingray skin renderer for BoostGauge.

Renders a 2D Schwinn-inspired analog tachometer with square chromed housing,
recessed matte-black dial, tick marks, numerals, redline arc, main pointer,
and translucent telltale needles.

Issue #1: Core Gauge Renderer — Analog Tachometer with Arc, Needle, and Tick Marks
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional, Protocol, Tuple, TypedDict
from PIL import Image, ImageDraw, ImageFont


class TelltaleDict(TypedDict, total=False):
    """Dictionary mapping telltale window names to peak values (0.0 to 100.0 or None)."""
    m1: Optional[float]
    m10: Optional[float]
    h1: Optional[float]
    all: Optional[float]


class NeedleSpec(TypedDict):
    """Configuration specification for a single needle rendering pass."""
    value: float
    color: Tuple[int, int, int, int]
    width_pct: float
    is_dashed: bool


class SkinProtocol(Protocol):
    """Protocol signature required for all boostgauge skin renderer implementations."""
    name: str

    def render(
        self,
        value: float,
        telltales: Optional[TelltaleDict] = None,
        size: int = 256,
        config: Optional[Dict[str, Any]] = None,
    ) -> Image.Image:
        ...


name: str = "stingray"


def calculate_angle(
    value: float,
    min_angle: float = 225.0,
    max_angle: float = -45.0,
    min_val: float = 0.0,
    max_val: float = 100.0,
) -> float:
    """Map scalar metric value to angular position in degrees (clockwise sweep from lower-left)."""
    clamped = max(min_val, min(max_val, float(value)))
    ratio = (clamped - min_val) / (max_val - min_val)
    return min_angle + ratio * (max_angle - min_angle)


def get_gauge_font(canvas_size: int, font_size_pct: float) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    """Resolve period sans-serif font sized relative to canvas dimension."""
    font_size = max(10, int(canvas_size * font_size_pct))
    font_names = ["eurostile.ttf", "helvetica.ttf", "arial.ttf", "DejaVuSans.ttf"]
    for font_name in font_names:
        try:
            return ImageFont.truetype(font_name, font_size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_housing_and_bezel(draw: ImageDraw.ImageDraw, canvas_size: int) -> None:
    """Draw square housing with rounded chamfered corners, polished chrome gradient, and inner shadow rim."""
    margin = int(canvas_size * 0.02)
    radius = int(canvas_size * 0.12)
    bbox = [margin, margin, canvas_size - margin, canvas_size - margin]

    draw.rounded_rectangle(bbox, radius=radius, fill=(35, 38, 42, 255), outline=(90, 95, 100, 255), width=3)

    bezel_margin = int(canvas_size * 0.04)
    bezel_bbox = [bezel_margin, bezel_margin, canvas_size - bezel_margin, canvas_size - bezel_margin]
    draw.rounded_rectangle(bezel_bbox, radius=radius - 4, fill=None, outline=(180, 185, 190, 255), width=4)


def draw_dial_face(draw: ImageDraw.ImageDraw, canvas_size: int) -> None:
    """Draw recessed circular matte-black dial face centered inside housing."""
    cx, cy = canvas_size / 2.0, canvas_size / 2.0
    r = canvas_size * 0.42
    bbox = [cx - r, cy - r, cx + r, cy + r]
    draw.ellipse(bbox, fill=(18, 18, 18, 255), outline=(50, 50, 50, 255), width=2)


def draw_redline_arc(draw: ImageDraw.ImageDraw, canvas_size: int) -> None:
    """Draw redline arc band hugging outer tick ring from 60 to 100 value positions."""
    cx, cy = canvas_size / 2.0, canvas_size / 2.0
    r = canvas_size * 0.36
    bbox = [cx - r, cy - r, cx + r, cy + r]
    # PIL arc angles: 0° = 3 o'clock, clockwise. Math angles: 0° = 3 o'clock, counter-clockwise.
    # value=60 -> math angle 108° -> PIL angle = -108° mod 360 = 252°
    # value=100 -> math angle -45° -> PIL angle = 45°
    draw.arc(bbox, start=252, end=315, fill=(230, 34, 20, 255), width=int(canvas_size * 0.025))


def draw_ticks_and_numerals(draw: ImageDraw.ImageDraw, canvas_size: int) -> None:
    """Draw 11 major tick marks (0-100), 40 minor tick marks, and white numerals."""
    cx, cy = canvas_size / 2.0, canvas_size / 2.0
    outer_r = canvas_size * 0.37
    major_len = canvas_size * 0.05
    minor_len = canvas_size * 0.025
    text_r = canvas_size * 0.28
    font = get_gauge_font(canvas_size, 0.045)

    for i in range(51):
        val = i * 2.0
        angle_deg = calculate_angle(val)
        rad = math.radians(angle_deg)

        cos_a = math.cos(rad)
        sin_a = -math.sin(rad)

        if i % 5 == 0:
            x1 = cx + outer_r * cos_a
            y1 = cy + outer_r * sin_a
            x2 = cx + (outer_r - major_len) * cos_a
            y2 = cy + (outer_r - major_len) * sin_a
            draw.line([(x1, y1), (x2, y2)], fill=(240, 240, 240, 255), width=int(canvas_size * 0.008))

            tx = cx + text_r * cos_a
            ty = cy + text_r * sin_a
            label = str(int(val))
            draw.text((tx, ty), label, fill=(240, 240, 240, 255), font=font, anchor="mm")
        else:
            x1 = cx + outer_r * cos_a
            y1 = cy + outer_r * sin_a
            x2 = cx + (outer_r - minor_len) * cos_a
            y2 = cy + (outer_r - minor_len) * sin_a
            draw.line([(x1, y1), (x2, y2)], fill=(160, 160, 160, 255), width=int(canvas_size * 0.004))


def draw_wordmark(draw: ImageDraw.ImageDraw, canvas_size: int) -> None:
    """Draw white BOOSTGAUGE small-caps brand wordmark below center pivot."""
    cx, cy = canvas_size / 2.0, canvas_size / 2.0
    font = get_gauge_font(canvas_size, 0.032)
    ty = cy + canvas_size * 0.16
    draw.text((cx, ty), "BOOSTGAUGE", fill=(200, 200, 200, 220), font=font, anchor="mm")


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
    tip_r = canvas_size * 0.36
    tail_r = canvas_size * 0.08
    base_w = (canvas_size * 0.012) * width_pct

    rad = math.radians(angle_deg)
    cos_a = math.cos(rad)
    sin_a = -math.sin(rad)

    px = -sin_a * base_w
    py = cos_a * base_w

    tip_x = cx + tip_r * cos_a
    tip_y = cy + tip_r * sin_a

    tail_x = cx - tail_r * cos_a
    tail_y = cy - tail_r * sin_a

    poly = [
        (tip_x, tip_y),
        (cx + px, cy + py),
        (tail_x, tail_y),
        (cx - px, cy - py),
    ]

    draw.polygon(poly, fill=color)

    cw_r = canvas_size * 0.025 * width_pct
    draw.ellipse([tail_x - cw_r, tail_y - cw_r, tail_x + cw_r, tail_y + cw_r], fill=color)


def draw_telltales(
    base_img: Image.Image,
    telltales: Optional[TelltaleDict],
    canvas_size: int,
) -> Image.Image:
    """Overlay translucent 1m, 10m, 1h, and all-time telltale needles behind main needle."""
    if not telltales:
        return base_img

    telltale_layer = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    t_draw = ImageDraw.Draw(telltale_layer)

    styles = [
        ("m1", (0, 229, 255, 166), 0.5, False),
        ("m10", (255, 145, 0, 166), 0.5, False),
        ("h1", (213, 0, 249, 166), 0.5, True),
        ("all", (255, 23, 68, 166), 0.5, False),
    ]

    for key, color, width_pct, is_dashed in styles:
        peak_val = telltales.get(key)  # type: ignore[literal-required]
        if peak_val is not None:
            angle = calculate_angle(peak_val)
            draw_needle(t_draw, angle, canvas_size, color=color, width_pct=width_pct, is_dashed=is_dashed)

    return Image.alpha_composite(base_img, telltale_layer)


def draw_pivot_cap(draw: ImageDraw.ImageDraw, canvas_size: int) -> None:
    """Draw polished chrome circular pivot cap and mounting detail dots at dial center."""
    cx, cy = canvas_size / 2.0, canvas_size / 2.0
    r = canvas_size * 0.045
    bbox = [cx - r, cy - r, cx + r, cy + r]
    draw.ellipse(bbox, fill=(200, 205, 210, 255), outline=(80, 85, 90, 255), width=2)

    dot_r = canvas_size * 0.006
    draw.ellipse([cx - r * 0.5 - dot_r, cy - dot_r, cx - r * 0.5 + dot_r, cy + dot_r], fill=(60, 60, 60, 255))
    draw.ellipse([cx + r * 0.5 - dot_r, cy - dot_r, cx + r * 0.5 + dot_r, cy + dot_r], fill=(60, 60, 60, 255))


def render_stingray(
    value: float,
    telltales: Optional[TelltaleDict] = None,
    size: int = 256,
    config: Optional[Dict[str, Any]] = None,
) -> Image.Image:
    """Render Stingray skin tachometer image at requested pixel size using 2x supersampling."""
    supersample_scale = 2
    canvas_size = size * supersample_scale

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
    draw_needle(draw, main_angle, canvas_size, color=(230, 34, 20, 255), width_pct=1.0, is_dashed=False)
    draw_pivot_cap(draw, canvas_size)

    if size != canvas_size:
        img = img.resize((size, size), resample=Image.Resampling.LANCZOS)

    return img