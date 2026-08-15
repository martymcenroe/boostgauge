"""Core gauge renderer (Stingray skin).

Issue #1: Feature: core gauge renderer — analog tachometer with arc, needle, and tick marks
"""

import math
from typing import Any, Callable, TypedDict

from PIL import Image, ImageDraw


class SkinConfig(TypedDict):
    size: int
    baseline_translucency: float


def _draw_supersampled(size: int, draw_instructions: Callable[[Image.Image], None], supersample_factor: int = 4) -> Image.Image:
    """Creates a supersampled image to mitigate lack of sub-pixel drawing primitives."""
    super_size = size * supersample_factor
    img = Image.new("RGBA", (super_size, super_size), (0, 0, 0, 0))
    draw_instructions(img)
    return img.resize((size, size), Image.Resampling.LANCZOS)


def _get_angle(value: float) -> float:
    return 225.0 - (2.7 * value)


def render(value: float, telltales: list[Any], size: int = 256, config: Any = None) -> Image.Image:
    """Renders the Stingray tachometer face and needles as a PIL Image."""
    size = max(128, size)
    baseline_translucency = config.get("baseline_translucency", 0.2) if config else 0.2

    def _draw(img: Image.Image) -> None:
        draw = ImageDraw.Draw(img, "RGBA")
        w, h = img.size
        cx, cy = w / 2, h / 2
        r = min(cx, cy) * 0.95

        bbox = [cx - r, cy - r, cx + r, cy + r]

        draw.ellipse([cx - r * 1.05, cy - r * 1.05, cx + r * 1.05, cy + r * 1.05], fill="#111111")
        draw.ellipse(bbox, fill="#222222")

        # Redline band spans values 60-100.
        # _get_angle(60) = 225 - 162 = 63 degrees (math convention, CCW from east)
        # _get_angle(100) = 225 - 270 = -45 degrees
        # Pillow arc: angles measured CW from 3 o'clock (east), so math angle -> pillow angle = -math_angle
        # math angle 63 -> pillow -63; math angle -45 -> pillow 45
        # Pillow draws arc from start to end CW, so start=-63, end=45
        band_width = int(r * 0.2)
        draw.arc(bbox, start=-63, end=45, fill="#9B3020", width=band_width)

        # Draw wordmark
        draw.text((cx, cy + r * 0.5), "STINGRAY", fill="#FFFFFF", anchor="mm")

        # Draw telltale needles
        for telltale in telltales:
            peak = telltale.current_peak()
            if peak is None:
                continue

            d = abs(peak - value)
            if d >= 3:
                opacity = baseline_translucency
            elif d <= 2:
                opacity = 1.0
            else:
                # Linear interpolation between d=2 (full) and d=3 (baseline)
                opacity = 1.0 - (1.0 - baseline_translucency) * (d - 2.0)

            alpha_val = int(255 * opacity)
            angle = _get_angle(peak)
            rad = math.radians(angle)
            nx = cx + r * 0.8 * math.cos(rad)
            ny = cy - r * 0.8 * math.sin(rad)
            needle_width = max(1, int(w * 0.01))
            draw.line([(cx, cy), (nx, ny)], fill=(200, 200, 200, alpha_val), width=needle_width)

        # Draw main needle
        main_angle = _get_angle(value)
        m_rad = math.radians(main_angle)
        mx = cx + r * 0.9 * math.cos(m_rad)
        my = cy - r * 0.9 * math.sin(m_rad)
        main_width = max(1, int(w * 0.02))
        draw.line([(cx, cy), (mx, my)], fill=(247, 57, 35, 255), width=main_width)

    return _draw_supersampled(size, _draw)