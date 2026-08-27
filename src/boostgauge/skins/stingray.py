from PIL import Image, ImageDraw, ImageFont
import math

_FACE_CACHE: dict[int, Image.Image] = {}


def render_face(size: int) -> Image.Image:
    if size not in _FACE_CACHE:
        _FACE_CACHE[size] = _render_face_uncached(size)
    return _FACE_CACHE[size]


def _polar(cx: float, cy: float, r: float, deg: float) -> tuple[float, float]:
    rad = math.radians(deg)
    return cx + r * math.sin(rad), cy - r * math.cos(rad)


def _val_to_deg(val: float) -> float:
    return -135.0 + (val / 100.0) * 270.0


def _get_font(size: int) -> ImageFont.FreeTypeFont:
    for font_name in ("arial.ttf", "DejaVuSans.ttf", "FreeSans.ttf"):
        try:
            return ImageFont.truetype(font_name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _render_face_uncached(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = size / 2.0, size / 2.0
    R = 0.40 * size

    draw.ellipse([cx - 1.15 * R, cy - 1.15 * R, cx + 1.15 * R, cy + 1.15 * R], fill=(220, 220, 220))
    draw.ellipse([cx - 1.05 * R, cy - 1.05 * R, cx + 1.05 * R, cy + 1.05 * R], fill=(40, 40, 40))

    draw.ellipse([cx - R, cy - R, cx + R, cy + R], fill=(10, 10, 12))

    bbox = [cx - 0.94 * R, cy - 0.94 * R, cx + 0.94 * R, cy + 0.94 * R]
    start_angle = _val_to_deg(65) - 90
    end_angle = _val_to_deg(100) - 90
    draw.arc(bbox, start=start_angle, end=end_angle, fill=(170, 15, 25), width=int(0.02 * R))

    font = _get_font(int(0.12 * R))
    for val in range(0, 101, 2):
        deg = _val_to_deg(val)
        is_major = val % 10 == 0
        r_inner = 0.85 * R if is_major else 0.91 * R
        r_outer = 0.97 * R if is_major else 0.95 * R

        p1 = _polar(cx, cy, r_inner, deg)
        p2 = _polar(cx, cy, r_outer, deg)
        draw.line([p1, p2], fill=(200, 200, 200), width=3 if is_major else 1)

        if is_major:
            nx, ny = _polar(cx, cy, 0.72 * R, deg)
            text = str(val)
            try:
                draw.text((nx, ny), text, fill=(255, 255, 255), font=font, anchor="mm")
            except TypeError:
                draw.text((nx - 10, ny - 10), text, fill=(255, 255, 255), font=font)

    wy = cy + 0.67 * R
    try:
        draw.text((cx, wy), "STINGRAY", fill=(255, 255, 255), font=font, anchor="mm")
    except TypeError:
        draw.text((cx - 30, wy - 10), "STINGRAY", fill=(255, 255, 255), font=font)

    for dx in (-0.25 * R, 0.25 * R):
        sx, sy = cx + dx, cy
        sr = 0.03 * R
        draw.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=(26, 26, 28))

    return img