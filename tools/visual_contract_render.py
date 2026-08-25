"""Render the Stingray static face DIRECTLY from the numeric render contract,
speaking the AZ visual-gate renderer protocol (boostgauge #357, AZ #2518).

Every default below is quoted from docs/design/0002-aesthetic-v1-stingray.md
(the numeric render contract) and the 2026-08-25 picture-driven rulings
(#356). Nothing is invented. The render code is the operator-approved
facecheck render of 2026-08-25, unchanged; this file adds the protocol:

    --out-dir <dir>          where the bundle lands (required)
    --set key=value          override a contract value (value is JSON);
                             repeatable -- this is how the gate's Modify
                             deltas reach the picture

Outputs into --out-dir:
    face-1024.png            the #331 deliverable: static face
    face-256.png             the same at the pinned test size
    face-needle75-1024.png   judging aid: main needle at 75 (#332 territory,
                             rendered so the LOOK is judgeable)
    manifest.json            the values used (with provenance and ruled
                             flags), the classification palette, and
                             contract-anchored sample points

Exit 3 with a stderr finding is the protocol's "contract too adjectival to
render" signal. This contract is numeric throughout, so the guard below only
fires if an override erases a value.
"""

import argparse
import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont

# ---- contract values, verbatim, with provenance ------------------------------
# key: (default, source, ruled) -- `ruled` means a landed ruling pinned it and
# the gate must halt rather than let a Modify delta silently override it.
CONTRACT = {
    "face_rgb":    ([10, 10, 12],   "measured from the canonical photograph", False),
    "white_rgb":   ([255, 255, 255], "measured from the canonical photograph", False),
    "needle_rgb":  ([247, 57, 35],  "ruling #228 (candy-apple #F73923)", True),
    "band_rgb":    ([170, 15, 25],  "operator ruling 2026-08-25 (crimson #AA0F19)", True),
    "screw_rgb":   ([26, 26, 28],   "contract S8 (#1A1A1C)", False),
    "hot_rgb":     ([255, 238, 214], "contract (#FFEED6 hot core)", False),
    "band_inner":  (0.88,           "operator ruling 2026-08-25 (thinned from 0.80 R)", True),
    "wordmark_y":  (0.67,           "operator ruling 2026-08-25 (level with 0/100 ticks)", True),
    "needle_value": (75.0,          "judging aid position, not a contract value", False),
}

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


def render_face(size, values, ss=3):
    S = size * ss
    cx = cy = S / 2
    R = 0.40 * S                        # dial radius, contract
    R_SEAT = 1.030 * R
    R_IN = 1.035 * R
    R_OUT = 1.26 * R
    CORNER = 0.13 * S

    FACE = tuple(values["face_rgb"])
    WHITE = tuple(values["white_rgb"])
    BAND = tuple(values["band_rgb"])
    SCREW = tuple(values["screw_rgb"])

    base = Image.new("RGB", (S, S), (3, 3, 4))

    env_img = Image.new("RGB", (S, S))
    ed = ImageDraw.Draw(env_img)
    for y in range(S):
        ed.line([(0, y), (S, y)], fill=env_at(y / (S - 1)))

    housing_mask = Image.new("L", (S, S), 0)
    hm = ImageDraw.Draw(housing_mask)
    hm.rounded_rectangle([0, 0, S - 1, S - 1], radius=int(CORNER), fill=255)
    hm.ellipse([cx - R_IN, cy - R_IN, cx + R_IN, cy + R_IN], fill=0)

    chrome = ImageEnhance.Brightness(env_img).enhance(1.02)
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

    bd.ellipse([cx - R_SEAT, cy - R_SEAT, cx + R_SEAT, cy + R_SEAT],
               fill=(8, 8, 10))

    d = ImageDraw.Draw(base)
    d.ellipse([cx - R, cy - R, cx + R, cy + R], fill=FACE)

    band_mask = Image.new("L", (S, S), 0)
    bm = ImageDraw.Draw(band_mask)
    bm.pieslice([cx - R, cy - R, cx + R, cy + R],
                start=screen(60), end=screen(100), fill=255)
    bi = float(values["band_inner"]) * R
    bm.ellipse([cx - bi, cy - bi, cx + bi, cy + bi], fill=0)
    base.paste(Image.new("RGB", (S, S), BAND), (0, 0), band_mask)
    d = ImageDraw.Draw(base)

    for v10 in range(0, 101, 10):
        a = angle(v10)
        d.line([polar(cx, cy, 1.00 * R, a), polar(cx, cy, 0.90 * R, a)],
               fill=WHITE, width=max(1, int(0.025 * R)))
    for dec in range(0, 100, 10):
        for m in (2, 4, 6, 8):
            a = angle(dec + m)
            d.line([polar(cx, cy, 1.00 * R, a), polar(cx, cy, 0.95 * R, a)],
                   fill=WHITE, width=max(1, int(0.012 * R)))

    fn = font(0.11 * R * 1.38)
    for n in range(0, 101, 10):
        d.text(polar(cx, cy, 0.72 * R, angle(n)), str(n), font=fn,
               fill=WHITE, anchor="mm")

    d.text((cx, cy + float(values["wordmark_y"]) * R), "BOOSTGAUGE",
           font=font(0.09 * R * 1.38), fill=WHITE, anchor="mm")

    for sxoff in (-0.25 * R, +0.25 * R):
        r = 0.020 * R
        d.ellipse([cx + sxoff - r, cy - r, cx + sxoff + r, cy + r], fill=SCREW)

    return base, S, cx, cy, R


def add_needle(base, S, cx, cy, R, values):
    NEEDLE = tuple(values["needle_rgb"])
    HOT = tuple(values["hot_rgb"])
    value = float(values["needle_value"])
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

    pv = ImageDraw.Draw(base)
    pr = 0.10 * R
    pv.ellipse([cx - pr, cy - pr, cx + pr, cy + pr], fill=(58, 60, 60))
    pv.ellipse([cx - pr * .74, cy - pr * .74, cx + pr * .74, cy + pr * .74],
               fill=(206, 208, 206))
    pv.ellipse([cx - pr * .70, cy - pr * .70, cx + pr * .70, cy + pr * .18],
               fill=(250, 251, 252))
    return base


def _sample_fracs(values):
    """Contract-anchored sample points as image fractions, computed from the
    same constants the render uses -- no drift possible."""
    def at(value, r_frac):
        a = math.radians(angle(value))
        return (0.5 + 0.40 * r_frac * math.cos(a),
                0.5 - 0.40 * r_frac * math.sin(a))

    band_mid = (float(values["band_inner"]) + 1.0) / 2.0
    # Value 75, not 80 (#359): 80 is a major-tick angle and ticks render ON
    # TOP of the band (the #351 ruling's geometry), so the band-mid radius
    # lands on white there. 75 carries no major and no minor (minors sit at
    # +2/+4/+6/+8 per decade) -- the sample measures the band itself. Found
    # by the gate's own measurement step reading white off the picture.
    bx, by = at(75, band_mid)
    fx, fy = at(30, 0.50)                       # clear dial face, upper-left
    return [
        {"name": "band-mid-at-75", "x_frac": bx, "y_frac": by, "expect": "band"},
        {"name": "face-clear-at-30", "x_frac": fx, "y_frac": fy, "expect": "face"},
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--set", action="append", default=[], metavar="KEY=JSON")
    args = parser.parse_args()

    values = {key: default for key, (default, _s, _r) in CONTRACT.items()}
    overridden = set()
    for pair in args.set:
        key, _, raw = pair.partition("=")
        if key not in CONTRACT:
            print(f"unknown contract key: {key}", file=sys.stderr)
            return 2
        values[key] = json.loads(raw)
        overridden.add(key)

    missing = [k for k, v in values.items() if v is None]
    if missing:
        # The protocol's adjectival-contract finding: a value that cannot be
        # drawn from. This contract is numeric, so only an override gets here.
        print(f"unrenderable: no numeric value for {', '.join(missing)}",
              file=sys.stderr)
        return 3

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    base, S, cx, cy, R = render_face(1024, values)
    face_1024 = base.resize((1024, 1024), Image.Resampling.LANCZOS)
    face_1024.save(out / "face-1024.png")
    base.resize((256, 256), Image.Resampling.LANCZOS).save(out / "face-256.png")

    withn = add_needle(base.copy(), S, cx, cy, R, values)
    withn.resize((1024, 1024), Image.Resampling.LANCZOS).save(
        out / "face-needle75-1024.png"
    )

    manifest = {
        "values": {
            key: {
                "value": values[key],
                "source": ("gate override" if key in overridden else source),
                "ruled": ruled,
            }
            for key, (_default, source, ruled) in CONTRACT.items()
        },
        "palette": {
            "needle": list(values["needle_rgb"]),
            "band": list(values["band_rgb"]),
            "white": list(values["white_rgb"]),
            "face": list(values["face_rgb"]),
        },
        "samples": _sample_fracs(values),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2),
                                       encoding="utf-8")
    print(f"wrote face-1024.png, face-256.png, face-needle75-1024.png, "
          f"manifest.json to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
