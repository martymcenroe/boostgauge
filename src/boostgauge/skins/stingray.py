"""Stingray skin renderer for boostgauge.

Implements visual spec from docs/design/0002-aesthetic-v1-stingray.md.
Issue #1: Core Gauge Renderer — Analog Tachometer.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional, Tuple
import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont


def calculate_angle(
    value: float,
    min_angle: float = 225.0,
    max_angle: float = -45.0,
    min_val: float = 0.0,
    max_val: float = 100.0,
) -> float:
    """Map scalar metric value to angular position in degrees (clockwise sweep from lower-left)."""
    clamped_val = max(min_val, min(max_val, value))
    fraction = (clamped_val - min_val) / (max_val - min_val)
    return min_angle + fraction * (max_angle - min_angle)


def get_gauge_font(canvas_size: int, font_size_pct: float) -> Any:
    """Resolve period sans-serif font sized to canvas with fallback to default font."""
    target_px = max(10, int(canvas_size * font_size_pct))
    font_names = [
        "eurostile.ttf",
        "Eurostile.ttf",
        "HelveticaNeue-Bold.ttf",
        "arialbd.ttf",
        "arial.ttf",
    ]
    for font_name in font_names:
        try:
            return PIL.ImageFont.truetype(font_name, target_px)
        except OSError:
            continue
    return PIL.ImageFont.load_default()


def draw_housing_and_bezel(draw: Any, canvas_size: int) -> None:
    """Draw square housing with rounded chamfered corners and chrome specular highlights."""
    if canvas_size <= 0:
        raise ValueError("canvas_size must be positive")

    margin = 4
    corner_radius = int(canvas_size * 0.08)

    draw.rounded_rectangle(
        [margin, margin, canvas_size - margin, canvas_size - margin],
        radius=corner_radius,
        fill=(30, 30, 32, 255),
        outline=(150, 150, 155, 255),
        width=3,
    )

    bezel_margin = int(canvas_size * 0.04)
    bezel_radius = int(corner_radius * 0.8)
    draw.rounded_rectangle(
        [bezel_margin, bezel_margin, canvas_size - bezel_margin, canvas_size - bezel_margin],
        radius=bezel_radius,
        fill=(180, 182, 185, 255),
        outline=(230, 232, 235, 255),
        width=int(canvas_size * 0.02),
    )


def draw_dial_face(draw: Any, canvas_size: int) -> None:
    """Draw recessed circular matte-black dial face centered inside housing."""
    cx, cy = canvas_size / 2.0, canvas_size / 2.0
    r = canvas_size * 0.40

    draw.ellipse(
        [cx - r - 2, cy - r - 2, cx + r + 2, cy + r + 2],
        fill=(10, 10, 12, 255),
    )

    draw.ellipse(
        [cx - r, cy - r, cx + r, cy + r],
        fill=(18, 18, 18, 255),
        outline=(40, 40, 42, 255),
        width=2,
    )


def draw_redline_arc(draw: Any, canvas_size: int) -> None:
    """Draw redline arc band hugging outer tick ring from value 60 to 100."""
    cx, cy = canvas_size / 2.0, canvas_size / 2.0
    r = canvas_size * 0.38

    start_val, end_val = 60.0, 100.0
    steps = 40
    arc_points = []

    for i in range(steps + 1):
        v = start_val + (end_val - start_val) * (i / steps)
        angle_deg = calculate_angle(v)
        rad = math.radians(angle_deg)
        x = cx + r * math.cos(rad)
        y = cy - r * math.sin(rad)
        arc_points.append((x, y))

    width = max(3, int(canvas_size * 0.018))
    for i in range(len(arc_points) - 1):
        draw.line([arc_points[i], arc_points[i + 1]], fill=(230, 34, 20, 255), width=width)


def draw_ticks_and_numerals(draw: Any, canvas_size: int) -> None:
    """Draw 11 major tick marks (0-100), 40 minor tick marks, and white numerals."""
    cx, cy = canvas_size / 2.0, canvas_size / 2.0
    r_outer = canvas_size * 0.37
    r_major_inner = canvas_size * 0.31
    r_minor_inner = canvas_size * 0.34
    r_numeral = canvas_size * 0.25

    font = get_gauge_font(canvas_size, 0.045)

    for i in range(51):
        val = i * 2.0
        angle_deg = calculate_angle(val)
        rad = math.radians(angle_deg)
        cos_a, sin_a = math.cos(rad), math.sin(rad)

        x_out = cx + r_outer * cos_a
        y_out = cy - r_outer * sin_a

        if i % 5 == 0:
            x_in = cx + r_major_inner * cos_a
            y_in = cy - r_major_inner * sin_a
            draw.line(
                [(x_in, y_in), (x_out, y_out)],
                fill=(255, 255, 255, 255),
                width=max(2, int(canvas_size * 0.008)),
            )

            num_str = str(int(val))
            x_num = cx + r_numeral * cos_a
            y_num = cy - r_numeral * sin_a

            bbox = font.getbbox(num_str)
            w_text = bbox[2] - bbox[0]
            h_text = bbox[3] - bbox[1]
            draw.text(
                (x_num - w_text / 2.0, y_num - h_text / 2.0),
                num_str,
                fill=(255, 255, 255, 255),
                font=font,
            )
        else:
            x_in = cx + r_minor_inner * cos_a
            y_in = cy - r_minor_inner * sin_a
            draw.line(
                [(x_in, y_in), (x_out, y_out)],
                fill=(220, 220, 220, 225),
                width=max(1, int(canvas_size * 0.004)),
            )


def draw_wordmark(draw: Any, canvas_size: int) -> None:
    """Draw white BOOSTGAUGE small-caps brand wordmark below center pivot."""
    cx, cy = canvas_size / 2.0, canvas_size / 2.0
    font = get_gauge_font(canvas_size, 0.035)
    wordmark = "BOOSTGAUGE"

    bbox = font.getbbox(wordmark)
    w_text = bbox[2] - bbox[0]
    h_text = bbox[3] - bbox[1]

    y_pos = cy + canvas_size * 0.14
    draw.text(
        (cx - w_text / 2.0, y_pos - h_text / 2.0),
        wordmark,
        fill=(240, 240, 240, 230),
        font=font,
    )


def draw_needle(
    draw: Any,
    angle_deg: float,
    canvas_size: int,
    color: Tuple[int, int, int, int],
    width_pct: float = 1.0,
    is_dashed: bool = False,
) -> None:
    """Draw tapered pointer needle with counterweight at specified angle and style."""
    cx, cy = canvas_size / 2.0, canvas_size / 2.0
    r_tip = canvas_size * 0.35
    r_tail = -canvas_size * 0.08
    w_base = max(2.0, canvas_size * 0.015 * width_pct)

    rad = math.radians(angle_deg)
    cos_a, sin_a = math.cos(rad), math.sin(rad)
    cos_perp = math.cos(rad + math.pi / 2.0)
    sin_perp = math.sin(rad + math.pi / 2.0)

    p_tip = (cx + r_tip * cos_a, cy - r_tip * sin_a)
    p_tail = (cx + r_tail * cos_a, cy - r_tail * sin_a)

    if is_dashed:
        steps = 10
        for i in range(0, steps, 2):
            t1 = i / steps
            t2 = (i + 1) / steps
            x1 = cx + (r_tail + t1 * (r_tip - r_tail)) * cos_a
            y1 = cy - (r_tail + t1 * (r_tip - r_tail)) * sin_a
            x2 = cx + (r_tail + t2 * (r_tip - r_tail)) * cos_a
            y2 = cy - (r_tail + t2 * (r_tip - r_tail)) * sin_a
            draw.line([(x1, y1), (x2, y2)], fill=color, width=max(1, int(w_base)))
    else:
        p_left = (cx + w_base * cos_perp, cy - w_base * sin_perp)
        p_right = (cx - w_base * cos_perp, cy + w_base * sin_perp)
        draw.polygon([p_tip, p_left, p_tail, p_right], fill=color)


def draw_telltales(
    base_img: PIL.Image.Image,
    telltales: Optional[Dict[str, Optional[float]]],
    canvas_size: int,
) -> PIL.Image.Image:
    """Overlay translucent 1m, 10m, 1h, and all-time telltale needles behind main needle."""
    if not telltales or all(v is None for v in telltales.values()):
        return base_img

    overlay = PIL.Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = PIL.ImageDraw.Draw(overlay)

    styles: Dict[str, Any] = {
        "m1": {"color": (0, 220, 255, 170), "width_pct": 0.5, "is_dashed": False},
        "m10": {"color": (255, 150, 0, 170), "width_pct": 0.5, "is_dashed": False},
        "h1": {"color": (230, 0, 230, 170), "width_pct": 0.5, "is_dashed": True},
        "all": {"color": (230, 34, 20, 170), "width_pct": 0.5, "is_dashed": False},
    }

    key_aliases = {"1m": "m1", "10m": "m10", "1h": "h1", "all": "all"}

    for window, key in key_aliases.items():
        val = telltales.get(key)
        if val is None:
            val = telltales.get(window)
        if val is not None:
            angle_deg = calculate_angle(val)
            style = styles[key]
            draw_needle(
                draw,
                angle_deg,
                canvas_size,
                color=style["color"],
                width_pct=style["width_pct"],
                is_dashed=style["is_dashed"],
            )

    return PIL.Image.alpha_composite(base_img, overlay)


def draw_pivot_cap(draw: Any, canvas_size: int) -> None:
    """Draw polished chrome circular pivot cap and mounting screw details at dial center."""
    cx, cy = canvas_size / 2.0, canvas_size / 2.0
    r_cap = canvas_size * 0.05

    draw.ellipse(
        [cx - r_cap, cy - r_cap, cx + r_cap, cy + r_cap],
        fill=(200, 202, 205, 255),
        outline=(80, 80, 85, 255),
        width=2,
    )

    r_inner = r_cap * 0.6
    draw.ellipse(
        [cx - r_inner, cy - r_inner, cx + r_inner, cy + r_inner],
        fill=(240, 242, 245, 255),
    )

    r_dot = max(1.5, canvas_size * 0.006)
    offset = r_cap * 0.55
    draw.ellipse(
        [cx - offset - r_dot, cy - r_dot, cx - offset + r_dot, cy + r_dot],
        fill=(50, 50, 55, 255),
    )
    draw.ellipse(
        [cx + offset - r_dot, cy - r_dot, cx + offset + r_dot, cy + r_dot],
        fill=(50, 50, 55, 255),
    )


def render_stingray(
    value: float,
    telltales: Optional[Dict[str, Optional[float]]] = None,
    size: int = 256,
    config: Optional[Dict[str, Any]] = None,
) -> PIL.Image.Image:
    """Render Stingray skin tachometer image at requested pixel size using 2x supersampling."""
    supersample_factor = 2
    canvas_size = size * supersample_factor

    img = PIL.Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = PIL.ImageDraw.Draw(img)

    draw_housing_and_bezel(draw, canvas_size)
    draw_dial_face(draw, canvas_size)
    draw_redline_arc(draw, canvas_size)
    draw_ticks_and_numerals(draw, canvas_size)
    draw_wordmark(draw, canvas_size)

    img = draw_telltales(img, telltales, canvas_size)

    draw = PIL.ImageDraw.Draw(img)
    main_angle = calculate_angle(value)
    draw_needle(draw, main_angle, canvas_size, color=(230, 34, 20, 255), width_pct=1.0, is_dashed=False)
    draw_pivot_cap(draw, canvas_size)

    return img.resize((size, size), resample=PIL.Image.Resampling.LANCZOS)


class StingraySkin:
    """Class wrapper implementing SkinProtocol interface."""

    name = "stingray"

    def render(
        self,
        value: float,
        telltales: Optional[Dict[str, Optional[float]]] = None,
        size: int = 256,
        config: Optional[Dict[str, Any]] = None,
    ) -> PIL.Image.Image:
        return render_stingray(value, telltales, size, config)