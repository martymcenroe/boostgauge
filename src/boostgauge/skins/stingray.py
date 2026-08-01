"""Stingray v1 analog tachometer skin renderer.

Issue #1: Core gauge renderer — analog tachometer with arc, needle, and tick marks
"""

import math
from typing import Any, Dict, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont

from boostgauge.skins import register_skin

TELLTALE_COLORS: Dict[str, Tuple[int, int, int, int]] = {
    "m1": (76, 201, 240, 180),
    "m10": (114, 9, 183, 180),
    "h1": (247, 37, 133, 180),
    "all_time": (255, 183, 3, 180),
}


def _get_font(size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    font_names = ["Eurostile", "DejaVuSans", "LiberationSans-Regular", "arial"]
    for font_name in font_names:
        try:
            return ImageFont.truetype(font_name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _val_to_angle(val: float) -> float:
    clamped = max(0.0, min(100.0, float(val)))
    return 225.0 - (2.7 * clamped)


def render_stingray(
    value: float,
    telltales: Optional[Dict[str, Optional[float]]] = None,
    size: int = 256,
    config: Optional[Dict[str, Any]] = None,
) -> Image.Image:
    """Stingray v1 analog tachometer renderer using 2x supersampled Pillow drawing."""
    dim = size * 2
    cx, cy = dim / 2.0, dim / 2.0

    img = Image.new("RGBA", (dim, dim), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Housing
    corner_rad = int(dim * 0.08)
    draw.rounded_rectangle(
        [0, 0, dim - 1, dim - 1],
        radius=corner_rad,
        fill=(30, 34, 42, 255),
        outline=(58, 63, 77, 255),
        width=int(dim * 0.015),
    )

    # Dial face
    r_face = dim * 0.44
    draw.ellipse(
        [cx - r_face, cy - r_face, cx + r_face, cy + r_face],
        fill=(14, 16, 19, 255),
        outline=(35, 39, 48, 255),
        width=int(dim * 0.01),
    )

    # Redline arc (values 60 to 100)
    # Standard math angle for value 60: 225 - 162 = 63° (CCW from east)
    # Pillow uses CW from east: standard 63° CCW = Pillow 360-63 = 297°
    # Standard math angle for value 100: 225 - 270 = -45° (CCW from east)
    # Pillow: -45° CCW = 45° CW from east
    r_arc = dim * 0.40
    arc_width = max(2, int(dim * 0.035))
    draw.arc(
        [cx - r_arc, cy - r_arc, cx + r_arc, cy + r_arc],
        start=297,
        end=405,
        fill=(230, 57, 70, 255),
        width=arc_width,
    )

    # Fonts
    font_numeral = _get_font(int(dim * 0.045))
    font_wordmark = _get_font(int(dim * 0.030))

    r_tick_outer = dim * 0.41
    r_tick_major_inner = dim * 0.34
    r_tick_minor_inner = dim * 0.37
    r_numeral = dim * 0.27

    # Major ticks and numerals
    for i in range(11):
        v = i * 10.0
        angle_deg = _val_to_angle(v)
        angle_rad = math.radians(angle_deg)
        cos_a = math.cos(angle_rad)
        sin_a = -math.sin(angle_rad)

        x1 = cx + r_tick_major_inner * cos_a
        y1 = cy + r_tick_major_inner * sin_a
        x2 = cx + r_tick_outer * cos_a
        y2 = cy + r_tick_outer * sin_a
        draw.line([(x1, y1), (x2, y2)], fill=(255, 255, 255, 255), width=max(2, int(dim * 0.012)))

        nx = cx + r_numeral * cos_a
        ny = cy + r_numeral * sin_a
        num_str = str(int(v))
        bbox = draw.textbbox((0, 0), num_str, font=font_numeral)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text((nx - tw / 2.0, ny - th / 2.0), num_str, fill=(240, 242, 245, 255), font=font_numeral)

        # Minor ticks (4 per interval)
        if i < 10:
            for m in range(1, 5):
                sub_v = v + m * 2.0
                sub_angle_rad = math.radians(_val_to_angle(sub_v))
                s_cos = math.cos(sub_angle_rad)
                s_sin = -math.sin(sub_angle_rad)
                mx1 = cx + r_tick_minor_inner * s_cos
                my1 = cy + r_tick_minor_inner * s_sin
                mx2 = cx + r_tick_outer * s_cos
                my2 = cy + r_tick_outer * s_sin
                draw.line([(mx1, my1), (mx2, my2)], fill=(160, 165, 181, 255), width=max(1, int(dim * 0.006)))

    # Wordmark
    wordmark = "BOOSTGAUGE"
    w_bbox = draw.textbbox((0, 0), wordmark, font=font_wordmark)
    ww = w_bbox[2] - w_bbox[0]
    wh = w_bbox[3] - w_bbox[1]
    draw.text((cx - ww / 2.0, cy + dim * 0.18 - wh / 2.0), wordmark, fill=(138, 145, 160, 255), font=font_wordmark)

    # Telltale needles
    if telltales:
        for key in ["m1", "m10", "h1", "all_time"]:
            peak_val = telltales.get(key)
            if peak_val is not None:
                t_angle = math.radians(_val_to_angle(peak_val))
                t_cos = math.cos(t_angle)
                t_sin = -math.sin(t_angle)
                r_tell = dim * 0.36
                tx = cx + r_tell * t_cos
                ty = cy + r_tell * t_sin
                color = TELLTALE_COLORS.get(key, (255, 255, 255, 180))
                draw.line([(cx, cy), (tx, ty)], fill=color, width=max(2, int(dim * 0.01)))

    # Main needle
    main_angle_rad = math.radians(_val_to_angle(value))
    main_cos = math.cos(main_angle_rad)
    main_sin = -math.sin(main_angle_rad)

    r_needle = dim * 0.38
    tip_x = cx + r_needle * main_cos
    tip_y = cy + r_needle * main_sin

    perp_cos = -main_sin
    perp_sin = main_cos
    base_w = dim * 0.015

    b1_x = cx + perp_cos * base_w
    b1_y = cy + perp_sin * base_w
    b2_x = cx - perp_cos * base_w
    b2_y = cy - perp_sin * base_w

    draw.polygon([(b1_x, b1_y), (tip_x, tip_y), (b2_x, b2_y)], fill=(255, 0, 51, 255))

    # Pivot cap
    r_cap_outer = dim * 0.06
    r_cap_inner = dim * 0.045
    draw.ellipse([cx - r_cap_outer, cy - r_cap_outer, cx + r_cap_outer, cy + r_cap_outer], fill=(74, 80, 97, 255))
    draw.ellipse([cx - r_cap_inner, cy - r_cap_inner, cx + r_cap_inner, cy + r_cap_inner], fill=(18, 20, 24, 255))

    return img.resize((size, size), resample=Image.Resampling.LANCZOS)


register_skin("stingray", render_stingray)