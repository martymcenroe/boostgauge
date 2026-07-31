"""Stingray skin rendering logic for analog tachometer gauge face.

Issue #1: Core Gauge Renderer — Analog Tachometer with Arc, Needle, and Tick Marks
"""

from __future__ import annotations

import math
from typing import Any
from PIL import Image, ImageDraw, ImageFont

_BACKGROUND_CACHE: dict[tuple[int, int], Image.Image] = {}

TELLTALE_COLORS: dict[str, tuple[int, int, int, int]] = {
    "window_1m": (0, 229, 255, 166),
    "window_10m": (255, 145, 0, 166),
    "window_1h": (224, 64, 251, 166),
    "window_all": (255, 23, 68, 166),
}


def _val_to_angle(value: float, min_angle: float = 225.0, max_angle: float = -45.0) -> float:
    """Map gauge metric value (0-100) to dial sweep angle in degrees."""
    sweep = max_angle - min_angle
    return min_angle + (value / 100.0) * sweep


def _load_skin_font(font_size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load Eurostile-adjacent font with dynamic platform fallback chain."""
    font_candidates = [
        "Eurostile",
        "Eurostile Bold",
        "Arial Bold",
        "DejaVu Sans Bold",
        "Liberation Sans Bold",
        "arial.ttf",
        "DejaVuSans-Bold.ttf",
    ]
    for font_name in font_candidates:
        try:
            return ImageFont.truetype(font_name, font_size)
        except (OSError, ImportError):
            continue
    return ImageFont.load_default()


def _draw_bezel_and_dial(draw: ImageDraw.ImageDraw, size: tuple[int, int]) -> None:
    """Draw square chromed bezel, chamfered corners, specular highlights, and recessed round dial face."""
    w, h = size

    draw.rectangle([0, 0, w, h], fill=(20, 22, 26, 255))

    bezel_margin = int(w * 0.02)
    draw.rectangle(
        [bezel_margin, bezel_margin, w - bezel_margin, h - bezel_margin],
        outline=(180, 185, 195, 255),
        width=int(w * 0.015),
    )

    corner_len = int(w * 0.08)
    draw.line([(0, corner_len), (corner_len, 0)], fill=(220, 225, 235, 255), width=int(w * 0.01))
    draw.line([(w - corner_len, 0), (w, corner_len)], fill=(220, 225, 235, 255), width=int(w * 0.01))
    draw.line([(0, h - corner_len), (corner_len, h)], fill=(100, 105, 115, 255), width=int(w * 0.01))
    draw.line([(w - corner_len, h), (w, h - corner_len)], fill=(100, 105, 115, 255), width=int(w * 0.01))

    dial_margin = int(w * 0.06)
    dial_bbox = [dial_margin, dial_margin, w - dial_margin, h - dial_margin]

    draw.ellipse(dial_bbox, fill=(10, 10, 12, 255), outline=(60, 65, 75, 255), width=int(w * 0.01))

    inner_margin = int(w * 0.07)
    inner_bbox = [inner_margin, inner_margin, w - inner_margin, h - inner_margin]
    draw.ellipse(inner_bbox, fill=(15, 15, 18, 255))


def _draw_ticks_and_numerals(draw: ImageDraw.ImageDraw, center: tuple[float, float], radius: float) -> None:
    """Draw 11 major and 40 minor white tick marks and Eurostile-adjacent numerals (0-100)."""
    cx, cy = center
    font = _load_skin_font(int(radius * 0.12))

    for i in range(51):
        val = i * 2.0
        angle = _val_to_angle(val)
        rad = math.radians(angle)

        is_major = (i % 5 == 0)
        tick_length = radius * 0.10 if is_major else radius * 0.05
        tick_width = max(2, int(radius * 0.015)) if is_major else max(1, int(radius * 0.008))

        outer_r = radius * 0.88
        inner_r = outer_r - tick_length

        x1 = cx + outer_r * math.cos(rad)
        y1 = cy - outer_r * math.sin(rad)
        x2 = cx + inner_r * math.cos(rad)
        y2 = cy - inner_r * math.sin(rad)

        draw.line([(x1, y1), (x2, y2)], fill=(255, 255, 255, 255), width=tick_width)

        if is_major:
            numeral_val = int(val)
            numeral_text = str(numeral_val)
            text_r = outer_r - tick_length - (radius * 0.10)
            tx = cx + text_r * math.cos(rad)
            ty = cy - text_r * math.sin(rad)

            bbox = font.getbbox(numeral_text)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            draw.text((tx - tw / 2.0, ty - th / 2.0), numeral_text, fill=(255, 255, 255, 255), font=font)


def _draw_redline_arc(draw: ImageDraw.ImageDraw, center: tuple[float, float], radius: float) -> None:
    """Draw redline arc hugging outer tick ring from metric value 60 to 100."""
    cx, cy = center
    outer_r = radius * 0.89
    bbox = [cx - outer_r, cy - outer_r, cx + outer_r, cy + outer_r]

    start_pil_angle = -_val_to_angle(60.0)
    end_pil_angle = -_val_to_angle(100.0)

    arc_width = max(3, int(radius * 0.025))
    draw.arc(bbox, start=start_pil_angle, end=end_pil_angle, fill=(230, 57, 70, 255), width=arc_width)


def _draw_wordmark(draw: ImageDraw.ImageDraw, center: tuple[float, float], radius: float) -> None:
    """Draw BOOSTGAUGE small-caps white wordmark below central pivot cap."""
    cx, cy = center
    font = _load_skin_font(int(radius * 0.08))
    text = "BOOSTGAUGE"

    wordmark_y = cy + (radius * 0.40)
    bbox = font.getbbox(text)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    draw.text((cx - tw / 2.0, wordmark_y - th / 2.0), text, fill=(220, 225, 235, 200), font=font)


def _draw_needle(
    draw: ImageDraw.ImageDraw,
    center: tuple[float, float],
    radius: float,
    angle: float,
    color: tuple[int, int, int, int] | str,
    width: float,
    length_factor: float,
    has_counterweight: bool = True,
) -> None:
    """Draw a gauge needle (main or telltale) pointing at specified angle."""
    cx, cy = center
    rad = math.radians(angle)

    needle_len = radius * length_factor
    tip_x = cx + needle_len * math.cos(rad)
    tip_y = cy - needle_len * math.sin(rad)

    perp_rad = rad + math.pi / 2.0
    half_w = width / 2.0

    base_left_x = cx + half_w * math.cos(perp_rad)
    base_left_y = cy - half_w * math.sin(perp_rad)
    base_right_x = cx - half_w * math.cos(perp_rad)
    base_right_y = cy + half_w * math.sin(perp_rad)

    polygon_pts = [(tip_x, tip_y), (base_left_x, base_left_y), (base_right_x, base_right_y)]

    if has_counterweight:
        cw_len = radius * 0.18
        cw_x = cx - cw_len * math.cos(rad)
        cw_y = cy + cw_len * math.sin(rad)
        polygon_pts.append((cw_x, cw_y))

    draw.polygon(polygon_pts, fill=color)


def _get_cached_background(size: tuple[int, int], skin_name: str = "stingray") -> Image.Image:
    """Retrieve or render static gauge background (bezel, dial, ticks, numerals, wordmark, redline)."""
    if size in _BACKGROUND_CACHE:
        return _BACKGROUND_CACHE[size].copy()

    bg = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(bg)

    cx, cy = size[0] / 2.0, size[1] / 2.0
    radius = min(size[0], size[1]) / 2.0

    _draw_bezel_and_dial(draw, size)
    _draw_ticks_and_numerals(draw, (cx, cy), radius)
    _draw_redline_arc(draw, (cx, cy), radius)
    _draw_wordmark(draw, (cx, cy), radius)

    _BACKGROUND_CACHE[size] = bg
    return bg.copy()


def render_stingray(
    value: float,
    telltales: dict[str, float | None] | None = None,
    size: tuple[int, int] = (256, 256),
    config: dict[str, Any] | None = None,
) -> Image.Image:
    """Stingray skin implementation rendering to PIL Image with 4x supersampling."""
    supersample = (config or {}).get("supersample_factor", 4)
    canvas_size = (size[0] * supersample, size[1] * supersample)

    canvas = _get_cached_background(canvas_size, skin_name="stingray")
    draw = ImageDraw.Draw(canvas)

    cx, cy = canvas_size[0] / 2.0, canvas_size[1] / 2.0
    radius = min(canvas_size[0], canvas_size[1]) / 2.0

    if telltales:
        for key in ["window_1m", "window_10m", "window_1h", "window_all"]:
            peak_val = telltales.get(key)
            if peak_val is not None:
                clamped_peak = max(0.0, min(100.0, float(peak_val)))
                peak_angle = _val_to_angle(clamped_peak)
                tt_color = TELLTALE_COLORS[key]
                _draw_needle(
                    draw=draw,
                    center=(cx, cy),
                    radius=radius,
                    angle=peak_angle,
                    color=tt_color,
                    width=float(radius * 0.025),
                    length_factor=0.75,
                    has_counterweight=False,
                )

    main_angle = _val_to_angle(value)
    main_color = (230, 57, 70, 255)
    _draw_needle(
        draw=draw,
        center=(cx, cy),
        radius=radius,
        angle=main_angle,
        color=main_color,
        width=float(radius * 0.035),
        length_factor=0.78,
        has_counterweight=True,
    )

    cap_r = radius * 0.08
    cap_bbox = [cx - cap_r, cy - cap_r, cx + cap_r, cy + cap_r]
    draw.ellipse(cap_bbox, fill=(180, 185, 195, 255), outline=(50, 55, 65, 255), width=max(1, int(radius * 0.01)))

    return canvas.resize(size, resample=Image.Resampling.LANCZOS)