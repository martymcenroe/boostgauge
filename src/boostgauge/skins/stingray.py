"""
Issue #331: static face renderer — bezel, chrome housing, dial, ticks, numerals, wordmark, screws
Issue #379: chrome bezel ring, environment strip housing, anti-aliased render
"""
import math
from typing import Dict, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont


def value_to_angle(v: float) -> float:
    """Convert gauge value (0-100) to math angle in degrees."""
    return 225 - 2.7 * v


def _sample_fracs(values: dict) -> dict:
    """Compute anchor points ensuring boundaries like 1.26 R are respected."""
    return {
        "bezel_inner": values.get("r_inner", 1.035),
        "bezel_outer": values.get("r_outer", 1.26),
    }


def render_face(size: int, values: Optional[dict] = None, ss: int = 3) -> Image.Image:
    """Render the Stingray static face with supersampling and Lanczos downscaling.
    Raises ValueError if size is less than 128."""
    if size < 128:
        raise ValueError("size must be at least 128")
    if ss < 1:
        raise ValueError("supersampling factor must be >= 1")
    if values is None:
        values = {}

    render_size = size * ss
    R = 0.40 * render_size
    cx = render_size / 2.0
    cy = render_size / 2.0

    stops = values.get("stops", [
        {"t": 0.08, "r": 232, "g": 240, "b": 251},
        {"t": 0.485, "r": 255, "g": 255, "b": 255},
        {"t": 0.500, "r": 24, "g": 24, "b": 24},
        {"t": 0.92, "r": 219, "g": 214, "b": 204},
    ])
    lift = values.get("lift", 1.02)

    env_strip = []
    for y in range(render_size):
        t = y / max(1, render_size - 1)
        if 0.485 < t < 0.500:
            t = 0.500
        below = [s for s in stops if s["t"] <= t]
        above = [s for s in stops if s["t"] > t]
        s0 = below[-1] if below else stops[0]
        s1 = above[0] if above else stops[-1]
        frac = (t - s0["t"]) / (s1["t"] - s0["t"]) if s1["t"] > s0["t"] else 0.0
        r = s0["r"] + (s1["r"] - s0["r"]) * frac
        g = s0["g"] + (s1["g"] - s0["g"]) * frac
        b = s0["b"] + (s1["b"] - s0["b"]) * frac
        color = (
            int(min(255, r * lift)),
            int(min(255, g * lift)),
            int(min(255, b * lift)),
            255,
        )
        env_strip.append(color)

    img = Image.new("RGBA", (render_size, render_size), (0, 0, 0, 0))

    chamfer = 0.13 * render_size
    mask = Image.new("L", (render_size, render_size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, render_size - 1, render_size - 1], radius=chamfer, fill=255
    )

    housing = Image.new("RGBA", (render_size, render_size), (0, 0, 0, 0))
    housing_draw = ImageDraw.Draw(housing)
    for y, color in enumerate(env_strip):
        housing_draw.line([(0, y), (render_size - 1, y)], fill=color)
    img.paste(housing, (0, 0), mask=mask)

    fracs = _sample_fracs(values)
    r_inner = fracs.get("bezel_inner", 1.035) * R
    r_outer = min(fracs.get("bezel_outer", 1.26) * R, render_size / 2.0)

    pixels = img.load()
    for py in range(render_size):
        dy = py - cy
        for px in range(render_size):
            dx = px - cx
            dist = math.hypot(dx, dy)
            if r_inner <= dist <= r_outer:
                frac = (dist - r_inner) / (r_outer - r_inner)
                strip_idx = int(frac * (render_size - 1))
                strip_idx = max(0, min(render_size - 1, strip_idx))
                pixels[px, py] = env_strip[strip_idx]

    draw = ImageDraw.Draw(img)

    seat_r = 1.01 * R
    draw.ellipse(
        [cx - seat_r, cy - seat_r, cx + seat_r, cy + seat_r],
        fill=(60, 60, 60, 255),
    )

    draw.ellipse([cx - R, cy - R, cx + R, cy + R], fill="#0A0A0C")

    bbox_outer = [cx - R, cy - R, cx + R, cy + R]
    bbox_inner = [cx - 0.88 * R, cy - 0.88 * R, cx + 0.88 * R, cy + 0.88 * R]

    band_mask = Image.new("RGBA", (render_size, render_size), (0, 0, 0, 0))
    band_draw = ImageDraw.Draw(band_mask)
    band_draw.pieslice(bbox_outer, -63, 45, fill="#AA0F19")
    band_draw.ellipse(bbox_inner, fill=(0, 0, 0, 0))
    img.alpha_composite(band_mask)

    draw = ImageDraw.Draw(img)

    def polar_to_xy(r, angle_deg):
        rad = math.radians(angle_deg)
        return (cx + r * math.cos(rad), cy - r * math.sin(rad))

    for v in range(101):
        angle_deg = value_to_angle(v)
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

    try:
        font_num = ImageFont.truetype(r"C:\Windows\Fonts\bahnschrift.ttf", int(0.11 * R))
        font_word = ImageFont.truetype(r"C:\Windows\Fonts\bahnschrift.ttf", int(0.09 * R))
    except IOError:
        font_num = ImageFont.load_default()
        font_word = ImageFont.load_default()

    for v in range(0, 101, 10):
        angle_deg = value_to_angle(v)
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

    screw_r = 0.020 * R
    for offset in [-0.25 * R, 0.25 * R]:
        sx = cx + offset
        sy = cy
        draw.ellipse(
            [sx - screw_r, sy - screw_r, sx + screw_r, sy + screw_r],
            fill="#1A1A1C",
        )

    if ss > 1:
        img = img.resize((size, size), Image.Resampling.LANCZOS)

    return img