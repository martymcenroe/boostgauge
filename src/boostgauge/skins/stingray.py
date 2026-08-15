"""Core gauge renderer (Stingray skin).

Issue #1: Feature: core gauge renderer — analog tachometer with arc, needle, and tick marks
"""

import math
from typing import Any, Callable, TypedDict

from PIL import Image, ImageDraw


class SkinConfig(TypedDict):
    size: int
    baseline_translucency: float


def _draw_supersampled(
    size: int,
    draw_instructions: Callable[[Image.Image], None],
    supersample_factor: int = 4,
) -> Image.Image:
    """Creates a supersampled image to mitigate lack of sub-pixel drawing primitives."""
    super_size = size * supersample_factor
    img = Image.new("RGBA", (super_size, super_size), (0, 0, 0, 0))
    draw_instructions(img)
    return img.resize((size, size), Image.Resampling.LANCZOS)


def _get_angle(value: float) -> float:
    return 225.0 - (2.7 * value)


def render(
    value: float, telltales: list[Any], size: int = 256, config: Any = None
) -> Image.Image:
    """Renders the Stingray tachometer face and needles as a PIL Image."""
    size = max(128, size)
    baseline_translucency = config.get("baseline_translucency", 0.2) if config else 0.2

    def _draw(img: Image.Image) -> None:
        draw = ImageDraw.Draw(img)
        w, h = img.size
        cx, cy = w / 2, h / 2
        r = min(cx, cy) * 0.95

        bbox = [cx - r, cy - r, cx + r, cy + r]

        draw.ellipse(
            [cx - r * 1.05, cy - r * 1.05, cx + r * 1.05, cy + r * 1.05],
            fill="#111111",
        )
        draw.ellipse(bbox, fill="#222222")
        draw.line(
            [(cx, cy - r), (cx, cy - r * 0.9)],
            fill="#FFFFFF",
            width=max(1, int(w * 0.005)),
        )
        draw.text((cx, cy - r * 0.8), "0", fill="#FFFFFF")
        draw.text((cx, cy + r * 0.5), "STINGRAY", fill="#FFFFFF")

        # Redline band: value 60->100 maps to math angles 63°->-45°
        # Pillow arc angles are CW from East: 297°->405° (sweeping through 0°/East)
        draw.arc(bbox, 297, 405, fill="#9B3020", width=int(r * 0.2))

        # Telltale needles drawn via alpha_composite so translucency blends correctly
        # over the already-opaque background (ImageDraw does not composite by default)
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
                opacity = 1.0 - (1.0 - baseline_translucency) * (d - 2.0)

            angle = _get_angle(peak)
            rad = math.radians(angle)
            nx = cx + r * 0.8 * math.cos(rad)
            ny = cy - r * 0.8 * math.sin(rad)

            overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(overlay)
            overlay_draw.line(
                [(cx, cy), (nx, ny)],
                fill=(200, 200, 200, 255),
                width=max(1, int(w * 0.01)),
            )
            r_ch, g_ch, b_ch, a_ch = overlay.split()
            a_ch = a_ch.point(lambda x, op=opacity: int(x * op))
            overlay = Image.merge("RGBA", (r_ch, g_ch, b_ch, a_ch))
            img.alpha_composite(overlay)

        main_angle = _get_angle(value)
        m_rad = math.radians(main_angle)
        mx = cx + r * 0.9 * math.cos(m_rad)
        my = cy - r * 0.9 * math.sin(m_rad)
        draw.line(
            [(cx, cy), (mx, my)],
            fill="#F73923",
            width=max(1, int(w * 0.02)),
        )

    return _draw_supersampled(size, _draw)