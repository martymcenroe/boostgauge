"""Stingray v1 analog tachometer skin renderer.

Issue #1: Core gauge renderer — analog tachometer with arc, needle, and tick marks
"""

import math
from typing import Any, Dict, Optional, Tuple, Union
from PIL import Image, ImageDraw, ImageFont

from boostgauge.skins import register_skin

TELLTALE_COLORS: Dict[str, Tuple[int, int, int, int]] = {
    "m1": (76, 201, 240, 180),
    "m10": (114, 9, 183, 180),
    "h1": (247, 37, 133, 180),
    "all_time": (255, 183, 3, 180),
}


def _get_font(size: int) -> Union[ImageFont.ImageFont, ImageFont.FreeTypeFont]:
    for name in ["Eurostile", "DejaVuSans", "LiberationSans-Regular", "arial"]:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _val_to_angle(val: float) -> float:
    return 225.0 - (2.7 * max(0.0, min(100.0, float(val))))


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

    # Redline arc (values 60–100)
    # Standard math: v=60 -> 63°, v=100 -> -45°
    # Pillow CW from 3-o'clock: 63° std -> 297° Pillow; -45° std -> 45° (405° for clockwise wrap)
    r_arc = dim * 0.41
    arc_width = max(2, int(dim * 0.035))
    draw.arc(
        [cx - r_arc, cy - r_arc, cx + r_arc, cy + r_arc],
        start=297,
        end=405,
        fill=(230, 57, 70, 255),
        width=arc_width,
    )

    font_numeral = _get_font(int(dim * 0.045))
    font_wordmark = _get_font(int(dim * 0.030))

    r_tick_outer = dim * 0.41
    r_tick_major_inner = dim * 0.34
    r_tick_minor_inner = dim * 0.37
    r_numeral = dim * 0.27

    # Major ticks and numerals
    for i in range(11):
        v = i * 10.0
        angle_rad = math.radians(_val_to_angle(v))
        cos_a = math.cos(angle_rad)
        sin_a = -math.sin(angle_rad)

        draw.line(
            [
                (cx + r_tick_major_inner * cos_a, cy + r_tick_major_inner * sin_a),
                (cx + r_tick_outer * cos_a, cy + r_tick_outer * sin_a),
            ],
            fill=(255, 255, 255, 255),
            width=max(2, int(dim * 0.012)),
        )

        nx = cx + r_numeral * cos_a
        ny = cy + r_numeral * sin_a
        num_str = str(int(v))
        bbox = draw.textbbox((0, 0), num_str, font=font_numeral)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text(
            (nx - tw / 2.0, ny - th / 2.0),
            num_str,
            fill=(240, 242, 245, 255),
            font=font_numeral,
        )

        # Minor ticks (4 per interval)
        if i < 10:
            for m in range(1, 5):
                sub_angle_rad = math.radians(_val_to_angle(v + m * 2.0))
                s_cos = math.cos(sub_angle_rad)
                s_sin = -math.sin(sub_angle_rad)
                draw.line(
                    [
                        (cx + r_tick_minor_inner * s_cos, cy + r_tick_minor_inner * s_sin),
                        (cx + r_tick_outer * s_cos, cy + r_tick_outer * s_sin),
                    ],
                    fill=(160, 165, 181, 255),
                    width=max(1, int(dim * 0.006)),
                )

    # Wordmark
    wm = "BOOSTGAUGE"
    w_bbox = draw.textbbox((0, 0), wm, font=font_wordmark)
    ww = w_bbox[2] - w_bbox[0]
    wh = w_bbox[3] - w_bbox[1]
    draw.text(
        (cx - ww / 2.0, cy + dim * 0.18 - wh / 2.0),
        wm,
        fill=(138, 145, 160, 255),
        font=font_wordmark,
    )

    # Translucent telltale needles
    if telltales:
        for key in ["m1", "m10", "h1", "all_time"]:
            peak_val = telltales.get(key)
            if peak_val is not None:
                clamped_peak = max(0.0, min(100.0, float(peak_val)))
                t_rad = math.radians(_val_to_angle(clamped_peak))
                t_cos = math.cos(t_rad)
                t_sin = -math.sin(t_rad)
                r_tell = dim * 0.36
                color = TELLTALE_COLORS.get(key, (255, 255, 255, 180))
                draw.line(
                    [(cx, cy), (cx + r_tell * t_cos, cy + r_tell * t_sin)],
                    fill=color,
                    width=max(2, int(dim * 0.01)),
                )

    # Main needle (tapered polygon)
    main_rad = math.radians(_val_to_angle(value))
    m_cos = math.cos(main_rad)
    m_sin = -math.sin(main_rad)

    r_needle = dim * 0.38
    tip_x = cx + r_needle * m_cos
    tip_y = cy + r_needle * m_sin

    base_w = dim * 0.025
    perp_cos = -m_sin
    perp_sin = m_cos

    draw.polygon(
        [
            (cx + perp_cos * base_w, cy + perp_sin * base_w),
            (tip_x, tip_y),
            (cx - perp_cos * base_w, cy - perp_sin * base_w),
        ],
        fill=(255, 0, 51, 255),
    )

    # Pivot cap
    r_cap_outer = dim * 0.06
    r_cap_inner = dim * 0.045
    draw.ellipse(
        [cx - r_cap_outer, cy - r_cap_outer, cx + r_cap_outer, cy + r_cap_outer],
        fill=(74, 80, 97, 255),
    )
    draw.ellipse(
        [cx - r_cap_inner, cy - r_cap_inner, cx + r_cap_inner, cy + r_cap_inner],
        fill=(18, 20, 24, 255),
    )

    return img.resize((size, size), resample=Image.Resampling.LANCZOS)


register_skin("stingray", render_stingray)