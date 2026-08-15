"""Stingray skin implementation.

Issue #1: Feature: core gauge renderer
"""

import math
from PIL import Image, ImageDraw


def render_skin(value: float, telltales: list[float | None], size: int) -> Image.Image:
    """Renders the Stingray aesthetic skin."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    center_x, center_y = size / 2, size / 2
    radius = size / 2

    draw.ellipse([0, 0, size, size], fill="#111111", outline="#333333", width=2)
    for v in range(0, 110, 10):
        t_angle = 225.0 - 2.7 * v
        r_rad = math.radians(t_angle)
        draw.line([
            (center_x + math.cos(r_rad) * radius * 0.8, center_y - math.sin(r_rad) * radius * 0.8),
            (center_x + math.cos(r_rad) * radius * 0.9, center_y - math.sin(r_rad) * radius * 0.9)
        ], fill="#FFFFFF", width=2)
        draw.text(
            (center_x + math.cos(r_rad) * radius * 0.7 - 5, center_y - math.sin(r_rad) * radius * 0.7 - 5),
            str(v), fill="#FFFFFF"
        )
    draw.text((center_x - 20, center_y + radius * 0.3), "BOOST", fill="#888888")

    redline_outer = radius * 1.0

    def val_to_angle(v: float) -> float:
        return 225.0 - 2.7 * v

    bbox = [
        center_x - redline_outer, center_y - redline_outer,
        center_x + redline_outer, center_y + redline_outer
    ]
    draw.arc(bbox, start=-val_to_angle(60), end=-val_to_angle(100), fill="#9B3020", width=int(radius * 0.2))

    for peak in telltales:
        if peak is not None:
            d = abs(peak - value)
            if d >= 3:
                opacity = int(255 * 0.2)
            elif d > 2:
                factor = 1.0 - ((d - 2.0) / 1.0) * 0.8
                opacity = int(255 * factor)
            else:
                opacity = 255

            t_angle = val_to_angle(peak)
            rad = math.radians(t_angle)
            end_x = center_x + math.cos(rad) * radius * 0.9
            end_y = center_y - math.sin(rad) * radius * 0.9
            draw.line([(center_x, center_y), (end_x, end_y)], fill=(255, 255, 255, opacity), width=2)

    m_angle = val_to_angle(value)
    rad = math.radians(m_angle)
    end_x = center_x + math.cos(rad) * radius * 0.95
    end_y = center_y - math.sin(rad) * radius * 0.95
    draw.line([(center_x, center_y), (end_x, end_y)], fill="#F73923", width=4)

    return img