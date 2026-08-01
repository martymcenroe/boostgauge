"""Stingray skin implementation for boostgauge tachometer.

Renders high-contrast dark analog tachometer with 270-degree arc sweep,
chromed housing, redline arc, BOOSTGAUGE wordmark, telltales, and main red needle.

Issue #1: Feature: Core Gauge Renderer
"""

import math
from typing import Any, Dict, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont

COLOR_BEZEL_OUTER = (30, 32, 36, 255)
COLOR_BEZEL_INNER = (75, 80, 88, 255)
COLOR_BEZEL_HIGHLIGHT = (200, 210, 220, 255)
COLOR_DIAL_BG = (14, 16, 20, 255)
COLOR_TICK_MAJOR = (240, 242, 245, 255)
COLOR_TICK_MINOR = (160, 165, 175, 255)
COLOR_NUMERAL = (230, 235, 240, 255)
COLOR_REDLINE = (220, 38, 38, 255)
COLOR_WORDMARK = (180, 185, 195, 200)

COLOR_MAIN_NEEDLE = (235, 40, 40, 255)
COLOR_PIVOT_CAP = (45, 48, 55, 255)
COLOR_PIVOT_RING = (120, 125, 135, 255)

TELLTALE_COLORS: Dict[str, Tuple[int, int, int, int]] = {
    "window_1m": (6, 182, 212, 160),
    "window_10m": (249, 115, 22, 160),
    "window_1h": (217, 70, 239, 160),
    "window_all": (239, 68, 68, 160),
}


def _val_to_angle(value: float, min_angle: float = 225.0, max_angle: float = -45.0) -> float:
    """Map gauge metric value (0-100) to dial sweep angle in degrees."""
    clamped_val = max(0.0, min(100.0, float(value)))
    return min_angle + (clamped_val / 100.0) * (max_angle - min_angle)


def _draw_bezel_and_dial(draw: ImageDraw.ImageDraw, size: Tuple[int, int]) -> None:
    """Draw square chromed housing, chamfered corners, specular highlights, and recessed round dial."""
    w, h = size
    box = [0, 0, w, h]

    corner_radius = int(min(w, h) * 0.08)
    draw.rounded_rectangle(box, radius=corner_radius, fill=COLOR_BEZEL_OUTER)

    inset1 = int(min(w, h) * 0.03)
    draw.rounded_rectangle(
        [inset1, inset1, w - inset1, h - inset1],
        radius=int(corner_radius * 0.8),
        outline=COLOR_BEZEL_HIGHLIGHT,
        width=int(min(w, h) * 0.015),
    )

    margin = int(min(w, h) * 0.06)
    dial_box = [margin, margin, w - margin, h - margin]
    draw.ellipse(dial_box, fill=COLOR_DIAL_BG, outline=COLOR_BEZEL_INNER, width=int(min(w, h) * 0.02))


def _draw_ticks_and_numerals(draw: ImageDraw.ImageDraw, center: Tuple[float, float], radius: float) -> None:
    """Draw 11 major and 40 minor white tick marks and numerals 0 to 100."""
    cx, cy = center

    try:
        font = ImageFont.load_default()
    except Exception:
        font = None

    for i in range(51):
        val = i * 2.0
        angle_deg = _val_to_angle(val)
        angle_rad = math.radians(angle_deg)

        is_major = (i % 5 == 0)

        inner_r = radius * (0.82 if is_major else 0.88)
        outer_r = radius * 0.94

        x1 = cx + inner_r * math.cos(angle_rad)
        y1 = cy - inner_r * math.sin(angle_rad)
        x2 = cx + outer_r * math.cos(angle_rad)
        y2 = cy - outer_r * math.sin(angle_rad)

        color = COLOR_TICK_MAJOR if is_major else COLOR_TICK_MINOR
        width = max(1, int(radius * (0.025 if is_major else 0.012)))

        draw.line([(x1, y1), (x2, y2)], fill=color, width=width)

        if is_major:
            num_val = int(val)
            num_r = radius * 0.70
            nx = cx + num_r * math.cos(angle_rad)
            ny = cy - num_r * math.sin(angle_rad)

            label = str(num_val)
            draw.text((nx, ny), label, fill=COLOR_NUMERAL, font=font, anchor="mm")


def _draw_redline_arc(draw: ImageDraw.ImageDraw, center: Tuple[float, float], radius: float) -> None:
    """Draw redline arc hugging outer tick ring from metric value 60 to 100."""
    cx, cy = center
    arc_r = radius * 0.95
    arc_box = [cx - arc_r, cy - arc_r, cx + arc_r, cy + arc_r]

    # PIL arc uses 0=3 o'clock, increasing clockwise.
    # Dial angle for val=60: _val_to_angle(60) = 225 + 0.6*(−270) = 225 − 162 = 63°
    # In PIL coords: −63° (counter-clockwise from 3 o'clock = negative in PIL)
    # Dial angle for val=100: _val_to_angle(100) = −45°
    # In PIL coords: 45°
    start_angle = -63.0
    end_angle = 45.0

    width = max(2, int(radius * 0.035))
    draw.arc(arc_box, start=start_angle, end=end_angle, fill=COLOR_REDLINE, width=width)


def _draw_wordmark(draw: ImageDraw.ImageDraw, center: Tuple[float, float], radius: float) -> None:
    """Draw BOOSTGAUGE small-caps white wordmark below central pivot cap."""
    cx, cy = center
    wy = cy + radius * 0.35
    font = ImageFont.load_default()
    draw.text((cx, wy), "BOOSTGAUGE", fill=COLOR_WORDMARK, font=font, anchor="mm")


def _draw_needle(
    draw: ImageDraw.ImageDraw,
    center: Tuple[float, float],
    radius: float,
    angle_deg: float,
    color: Tuple[int, int, int, int],
    width_ratio: float = 1.0,
    is_main: bool = False,
) -> None:
    """Draw pointer needle with pivot mounting and counterweight."""
    cx, cy = center
    angle_rad = math.radians(angle_deg)

    tip_r = radius * (0.85 if is_main else 0.80)
    tail_r = radius * 0.20

    tx = cx + tip_r * math.cos(angle_rad)
    ty = cy - tip_r * math.sin(angle_rad)

    bx = cx - tail_r * math.cos(angle_rad)
    by = cy + tail_r * math.sin(angle_rad)

    width = max(1, int(radius * 0.02 * width_ratio))
    draw.line([(bx, by), (tx, ty)], fill=color, width=width)

    if is_main:
        cap_r = radius * 0.12
        cap_box = [cx - cap_r, cy - cap_r, cx + cap_r, cy + cap_r]
        draw.ellipse(cap_box, fill=COLOR_PIVOT_CAP, outline=COLOR_PIVOT_RING, width=max(1, int(radius * 0.015)))


def render_stingray(
    value: float,
    telltales: Optional[Dict[str, Optional[float]]] = None,
    size: Tuple[int, int] = (256, 256),
    config: Optional[Dict[str, Any]] = None,
) -> Image.Image:
    """Stingray skin implementation rendering to PIL Image with 4x supersampling."""
    cfg = config or {}
    factor = int(cfg.get("supersample_factor", 4))

    target_w, target_h = size
    hires_size = (target_w * factor, target_h * factor)

    hires_img = Image.new("RGBA", hires_size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(hires_img)

    _draw_bezel_and_dial(draw, hires_size)

    cx = hires_size[0] / 2.0
    cy = hires_size[1] / 2.0
    radius = min(hires_size) * 0.42
    center = (cx, cy)

    _draw_ticks_and_numerals(draw, center, radius)
    _draw_redline_arc(draw, center, radius)
    _draw_wordmark(draw, center, radius)

    if telltales:
        for window_key in ["window_all", "window_1h", "window_10m", "window_1m"]:
            peak_val = telltales.get(window_key)
            if peak_val is not None:
                t_angle = _val_to_angle(peak_val)
                t_color = TELLTALE_COLORS.get(window_key, (200, 200, 200, 160))
                _draw_needle(draw, center, radius, t_angle, t_color, width_ratio=0.6, is_main=False)

    main_angle = _val_to_angle(value)
    _draw_needle(draw, center, radius, main_angle, COLOR_MAIN_NEEDLE, width_ratio=1.0, is_main=True)

    return hires_img.resize((target_w, target_h), resample=Image.Resampling.LANCZOS)