"""Stingray skin — the static face and the main-needle primitive.

Ported verbatim from ``data/scratch-2026-08-25-facecheck/facecheck.py``, the
script that produced the operator-approved render (``variant-crimson-1024.png``,
approved 2026-08-25). Every value below is quoted from
``docs/design/0002-aesthetic-v1-stingray.md`` (the numeric render contract,
ruling #265) and issue #331's decision table. Nothing is invented. Issue #402
made this script the shipped module and pinned the approved render as the
visual baseline under ``tests/visual/baselines/``.

Render architecture (ruling #329): ``render_face`` bakes the static face once;
``add_needle`` is the main-needle primitive of the dynamic layer. The full
dynamic layer — the four telltales and the proximity ramp — is #332's.

Font: the contract lists DIN, with Bahnschrift as the substitute family. The
Windows path below is what produced the approved render; on a machine without
it the renderer falls back to Pillow's default face and the baselines will not
match (tracked separately — see the follow-up filed from #402).
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont

# ---- contract values, verbatim ----------------------------------------------
FACE = (10, 10, 12)          # #0A0A0C
WHITE = (255, 255, 255)      # #FFFFFF
NEEDLE = (247, 57, 35)       # #F73923 candy-apple
BAND = (170, 15, 25)         # #AA0F19 crimson — operator ruling 2026-08-25
SCREW = (26, 26, 28)         # #1A1A1C
HOT = (255, 238, 214)        # #FFEED6 hot core

TELLTALE_COLORS = (          # dynamic layer (#332), ruling #267 — order 1m, 10m, 1h, all-time
    (59, 215, 240),          # #3BD7F0 cyan, 1 minute
    (255, 154, 46),          # #FF9A2E orange, 10 minutes
    (212, 91, 232),          # #D45BE8 magenta, 1 hour
    (255, 110, 122),         # #FF6E7A coral red, all-time
)
TELLTALE_WIDTH_RATIO = 0.45  # x the main needle's 0.035 R (contract)
TELLTALE_BASE_ALPHA = 166    # 65% baseline opacity (contract)
TELLTALE_RAMP_FAR = 3.0      # scale units: baseline holds at and beyond this (rulings #232/#242/#245)
TELLTALE_RAMP_NEAR = 2.0     # scale units: 100% at and inside this

ENV = [                       # chrome environment strip, ruling #328
    (0.00, (255, 255, 255)),
    (0.18, (196, 214, 238)),
    (0.40, (238, 246, 255)),
    (0.485, (255, 255, 255)),
    (0.500, (18, 19, 22)),    # horizon: a STEP, never a ramp
    (0.58, (44, 46, 48)),
    (0.74, (110, 108, 104)),
    (0.88, (196, 190, 178)),
    (1.00, (255, 252, 244)),
]

FONT = r"C:\Windows\Fonts\bahnschrift.ttf"   # DIN — listed substitute family

BAND_INNER = 0.88          # operator 2026-08-25: thinner band, start further out
WORDMARK_Y = 0.67          # operator 2026-08-25: in line with the 0/100 ticks


def env_at(t):
    t = min(max(t, 0.0), 1.0)
    for i in range(len(ENV) - 1):
        t0, c0 = ENV[i]
        t1, c1 = ENV[i + 1]
        if t0 <= t <= t1:
            f = (t - t0) / max(t1 - t0, 1e-9)
            return tuple(int(c0[k] + (c1[k] - c0[k]) * f) for k in range(3))
    return ENV[-1][1]


def angle(v):
    """ruling #255: angle(value) = 225 - 2.7 x value, math convention."""
    return 225.0 - 2.7 * v


def screen(v):
    """PIL angle (y-down, clockwise-positive) for a scale value."""
    return -angle(v)


def polar(cx, cy, r, deg):
    a = math.radians(deg)
    return cx + r * math.cos(a), cy - r * math.sin(a)


def font(px):
    try:
        return ImageFont.truetype(FONT, int(px))
    except OSError:
        return ImageFont.load_default()


def bloom(layer, passes):
    rgb = layer.convert("RGB")
    lit = Image.composite(rgb, Image.new("RGB", layer.size, (0, 0, 0)),
                          layer.split()[3])
    out = Image.new("RGB", layer.size, (0, 0, 0))
    for radius, weight in passes:
        b = ImageEnhance.Brightness(
            lit.filter(ImageFilter.GaussianBlur(radius))).enhance(weight)
        out = ImageChops.add(out, b)
    return out


def render_face_supersampled(size, ss=3, band_rgb=BAND):
    """Render the static face at ``size * ss`` px.

    Returns ``(image, S, cx, cy, R)`` — the supersampled RGB image and the
    geometry ``add_needle`` needs to composite over it. ``render_face`` is the
    downscaled convenience wrapper.
    """
    S = size * ss
    cx = cy = S / 2
    R = 0.40 * S                        # dial radius, contract
    R_SEAT = 1.030 * R                  # bezel-seat shadow annulus outer edge
    R_IN = 1.035 * R                    # chrome roll meets the seat here
    R_OUT = 1.26 * R                    # outer edge of the rolled bezel
    CORNER = 0.13 * S                   # chamfer radius, S7

    base = Image.new("RGB", (S, S), (3, 3, 4))

    # ---- chrome housing: the environment, mirrored --------------------------
    env_img = Image.new("RGB", (S, S))
    ed = ImageDraw.Draw(env_img)
    for y in range(S):
        ed.line([(0, y), (S, y)], fill=env_at(y / (S - 1)))

    housing_mask = Image.new("L", (S, S), 0)
    hm = ImageDraw.Draw(housing_mask)
    hm.rounded_rectangle([0, 0, S - 1, S - 1], radius=int(CORNER), fill=255)
    hm.ellipse([cx - R_IN, cy - R_IN, cx + R_IN, cy + R_IN], fill=0)

    chrome = ImageEnhance.Brightness(env_img).enhance(1.02)

    # inner roll: normal sweeps through the strip; horizon reappears compressed
    cd = ImageDraw.Draw(chrome)
    rings = 220
    for i in range(rings):
        u = i / (rings - 1)
        rr = R_OUT + (R_IN - R_OUT) * u
        phase = abs(math.sin(u * math.pi * 1.15 + 0.10))
        samp = 0.5 + (phase - 0.5) * 1.55
        shade = 0.38 + 0.62 * math.sin(min(max(u, 0), 1) * math.pi) ** 0.5
        band = env_at(samp)
        c = tuple(min(255, int(band[k] * shade * 1.38)) for k in range(3))
        cd.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=c,
                   width=max(2, int(abs(R_OUT - R_IN) / rings) + 2))

    base.paste(chrome, (0, 0), housing_mask)

    # two specular hot spots, top-left and bottom-right (S7 / #328)
    spec = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    sd = ImageDraw.Draw(spec)
    for fx, fy, sx, sy in ((0.30, 0.19, 1.9, 0.7), (0.74, 0.83, 1.5, 0.6)):
        px, py = S * fx, S * fy
        k0 = S * 0.052
        for j in range(18, 0, -1):
            t = j / 18
            a = int(255 * (1 - t) ** 1.7)
            d0 = k0 * t
            sd.ellipse([px - d0 * sx, py - d0 * sy, px + d0 * sx, py + d0 * sy],
                       fill=(255, 255, 255, a))
    spec = spec.filter(ImageFilter.GaussianBlur(S * 0.004))
    spec.putalpha(ImageChops.multiply(spec.split()[3], housing_mask))
    base = Image.alpha_composite(base.convert("RGBA"), spec).convert("RGB")

    bd = ImageDraw.Draw(base)
    bd.rounded_rectangle([1, 1, S - 2, S - 2], radius=int(CORNER),
                         outline=(255, 255, 255), width=max(2, int(S * 0.0030)))
    bd.rounded_rectangle([int(S * 0.018), int(S * 0.018),
                          int(S * 0.982), int(S * 0.982)],
                         radius=int(CORNER * 0.86), outline=(206, 210, 214),
                         width=max(1, int(S * 0.0012)))
    bd.ellipse([cx - R_IN, cy - R_IN, cx + R_IN, cy + R_IN],
               outline=(255, 255, 255), width=max(2, int(S * 0.0022)))

    # ---- bezel seat (S9): shadow on the transition annulus, never the face --
    bd.ellipse([cx - R_SEAT, cy - R_SEAT, cx + R_SEAT, cy + R_SEAT],
               fill=(8, 8, 10))

    # ---- dial face (S1): one flat fill, zero overlays ------------------------
    d = ImageDraw.Draw(base)
    d.ellipse([cx - R, cy - R, cx + R, cy + R], fill=FACE)

    # ---- redline band (S2): ring sector, 0.88R-1.00R, values 60-100, flat ----
    band_mask = Image.new("L", (S, S), 0)
    bm = ImageDraw.Draw(band_mask)
    bm.pieslice([cx - R, cy - R, cx + R, cy + R],
                start=screen(60), end=screen(100), fill=255)
    bi = BAND_INNER * R
    bm.ellipse([cx - bi, cy - bi, cx + bi, cy + bi], fill=0)
    base.paste(Image.new("RGB", (S, S), band_rgb), (0, 0), band_mask)
    d = ImageDraw.Draw(base)

    # ---- ticks (S3/S4): white, on top of the band, from the dial edge inward -
    for v10 in range(0, 101, 10):                       # 11 majors
        a = angle(v10)
        d.line([polar(cx, cy, 1.00 * R, a), polar(cx, cy, 0.90 * R, a)],
               fill=WHITE, width=max(1, int(0.025 * R)))
    for dec in range(0, 100, 10):                       # 40 minors, 4 per gap
        for m in (2, 4, 6, 8):
            a = angle(dec + m)
            d.line([polar(cx, cy, 1.00 * R, a), polar(cx, cy, 0.95 * R, a)],
                   fill=WHITE, width=max(1, int(0.012 * R)))

    # ---- numerals (S5): 0-100 step 10, cap 0.11R, inside the tick ring -------
    fn = font(0.11 * R * 1.38)
    for n in range(0, 101, 10):
        d.text(polar(cx, cy, 0.72 * R, angle(n)), str(n), font=fn,
               fill=WHITE, anchor="mm")

    # ---- wordmark (S6): BOOSTGAUGE, cap 0.09R, level with the 0/100 ticks ----
    d.text((cx, cy + WORDMARK_Y * R), "BOOSTGAUGE", font=font(0.09 * R * 1.38),
           fill=WHITE, anchor="mm")

    # ---- screws (S8): 2, +/-0.25R horizontal, radius 0.020R, flat #1A1A1C ----
    for sxoff in (-0.25 * R, +0.25 * R):
        r = 0.020 * R
        d.ellipse([cx + sxoff - r, cy - r, cx + sxoff + r, cy + r], fill=SCREW)

    return base, S, cx, cy, R


def draw_main_needle(base, S, cx, cy, R, value):
    """Main needle at ``value`` — bloomed candy-apple body, hot core — over a supersampled face.

    Returns a new RGB image; ``base`` is not mutated. The pivot cap is drawn
    separately by ``draw_pivot_cap`` because it sits above every needle.
    """
    a = angle(value)
    half = 0.035 * R / 2
    tip = polar(cx, cy, 0.86 * R, a)

    body = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    nd = ImageDraw.Draw(body)
    nd.polygon([polar(cx, cy, half * 2.0, a - 90), polar(*tip, half * 0.30, a - 90),
                polar(*tip, half * 0.30, a + 90), polar(cx, cy, half * 2.0, a + 90)],
               fill=NEEDLE + (255,))
    nd.line([(cx, cy), polar(cx, cy, 0.18 * R, a + 180)], fill=NEEDLE + (255,),
            width=int(half * 3.0))
    passes = [(0.004 * R, 1.00), (0.012 * R, 0.78),
              (0.027 * R, 0.52), (0.061 * R, 0.34)]      # #327, verbatim
    base = ImageChops.add(base, bloom(body, passes))

    core = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(core).line([polar(cx, cy, half * 0.5, a + 180), tip],
                              fill=HOT + (255,), width=max(1, int(0.016 * R)))
    core_passes = [(0.002 * R, 1.00), (0.007 * R, 0.72), (0.022 * R, 0.36)]
    base = ImageChops.add(base, bloom(core, core_passes))
    base = Image.alpha_composite(base.convert("RGBA"), core).convert("RGB")
    return base


def draw_pivot_cap(base, S, cx, cy, R):
    """Chrome pivot cap, radius 0.10R, drawn LAST — above every needle (#333 ruling).

    Mutates and returns ``base``.
    """
    pv = ImageDraw.Draw(base)
    pr = 0.10 * R
    pv.ellipse([cx - pr, cy - pr, cx + pr, cy + pr], fill=(58, 60, 60))
    pv.ellipse([cx - pr * .74, cy - pr * .74, cx + pr * .74, cy + pr * .74],
               fill=(206, 208, 206))
    pv.ellipse([cx - pr * .70, cy - pr * .70, cx + pr * .70, cy + pr * .18],
               fill=(250, 251, 252))
    return base


def add_needle(base, S, cx, cy, R, value):
    """Main needle + pivot cap — the approved render's composition (``facecheck.emit_variants``)."""
    return draw_pivot_cap(draw_main_needle(base, S, cx, cy, R, value), S, cx, cy, R)


# ---- dynamic layer: telltales (#332) ----------------------------------------


def telltale_opacity(distance):
    """Alpha for a telltale whose peak sits ``distance`` scale units from the main needle.

    Baseline 166 at 3 units and beyond, 255 at 2 units and closer, linear in
    between — evaluated per needle and applied uniformly along its length
    (rulings #232, #242, #245).
    """
    if distance >= TELLTALE_RAMP_FAR:
        return TELLTALE_BASE_ALPHA
    if distance <= TELLTALE_RAMP_NEAR:
        return 255
    t = (TELLTALE_RAMP_FAR - distance) / (TELLTALE_RAMP_FAR - TELLTALE_RAMP_NEAR)
    return int(TELLTALE_BASE_ALPHA + (255 - TELLTALE_BASE_ALPHA) * t + 0.5)


def draw_telltales(base, S, cx, cy, R, peaks, value):
    """Four thin flat-alpha needles, drawn before (so behind) the main needle.

    ``peaks``: four values or None in ``TELLTALE_COLORS`` order. A None peak
    draws nothing (T1). Flat alpha only — no bloom, no hot core: luminescence
    (#327) belongs to the main needle alone. Returns ``base`` untouched when
    nothing is drawn, else a new RGB image.
    """
    if all(p is None for p in peaks):
        return base
    out = base.convert("RGBA")
    width = max(1, int(TELLTALE_WIDTH_RATIO * 0.035 * R + 0.5))
    for color, peak in zip(TELLTALE_COLORS, peaks):
        if peak is None:
            continue
        alpha = telltale_opacity(abs(peak - value))
        layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        ImageDraw.Draw(layer).line([(cx, cy), polar(cx, cy, 0.86 * R, angle(peak))],
                                   fill=color + (alpha,), width=width)
        out = Image.alpha_composite(out, layer)
    return out.convert("RGB")


_FACE_CACHE = {}


def cached_face(size, ss=3, band_rgb=BAND):
    """The static face, baked once per (size, ss, band) and reused every refresh (#329)."""
    key = (size, ss, band_rgb)
    if key not in _FACE_CACHE:
        _FACE_CACHE[key] = render_face_supersampled(size, ss=ss, band_rgb=band_rgb)
    return _FACE_CACHE[key]


def _peak_of(telltale):
    if telltale is None:
        return None
    if hasattr(telltale, "current_peak"):
        return telltale.current_peak()
    return float(telltale)


def render(value, telltales, size, ss=3, band_rgb=BAND):
    """One refresh: telltales, then the main needle at ``value``, then the pivot cap.

    ``telltales`` holds four entries in 1m / 10m / 1h / all-time order, each a
    ``Telltale`` (its ``current_peak()`` is read), a plain number, or None.
    Composited over the cached face and returned at ``size`` px. With four
    Nones the result is byte-identical to ``render_with_needle``.
    """
    peaks = [_peak_of(t) for t in telltales]
    if len(peaks) != 4:
        raise ValueError(f"render() takes four telltales (1m, 10m, 1h, all-time), got {len(peaks)}")
    base, S, cx, cy, R = cached_face(size, ss=ss, band_rgb=band_rgb)
    img = draw_telltales(base, S, cx, cy, R, peaks, value)
    img = draw_main_needle(img, S, cx, cy, R, value)
    img = draw_pivot_cap(img, S, cx, cy, R)
    return img.resize((size, size), Image.Resampling.LANCZOS)


def render_face(size, ss=3, band_rgb=BAND):
    """The static face at ``size`` px: supersampled ``ss``x, Lanczos-downscaled."""
    base, _S, _cx, _cy, _R = render_face_supersampled(size, ss=ss, band_rgb=band_rgb)
    return base.resize((size, size), Image.Resampling.LANCZOS)


def render_with_needle(size, value, ss=3, band_rgb=BAND):
    """Face + main needle at ``value`` + pivot cap, at ``size`` px.

    This is exactly the composition that produced the approved render
    (``facecheck.emit_variants`` at value 75, crimson band).
    """
    base, S, cx, cy, R = render_face_supersampled(size, ss=ss, band_rgb=band_rgb)
    withn = add_needle(base, S, cx, cy, R, value)
    return withn.resize((size, size), Image.Resampling.LANCZOS)


def main(argv=None):
    """Render the face to a PNG so a human can look at it.

    ``python -m boostgauge.skins.stingray --size 1024 --value 75 --out face.png``
    """
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument("--size", type=int, default=1024, help="output edge in px")
    parser.add_argument("--value", type=float, default=None,
                        help="main-needle value 0-100; omit for the static face")
    parser.add_argument("--peaks", default=None,
                        help="four telltale peaks 1m,10m,1h,all — e.g. 10,25,85,100; "
                             "use - for a slot with no peak")
    parser.add_argument("--out", type=Path, required=True, help="PNG path to write")
    args = parser.parse_args(argv)

    if args.value is None:
        img = render_face(args.size)
    elif args.peaks is None:
        img = render_with_needle(args.size, args.value)
    else:
        peaks = [None if p.strip() == "-" else float(p) for p in args.peaks.split(",")]
        img = render(args.value, peaks, args.size)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    img.save(args.out)
    print(args.out)


if __name__ == "__main__":
    main()
