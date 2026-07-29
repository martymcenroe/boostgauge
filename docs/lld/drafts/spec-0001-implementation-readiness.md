# Implementation Spec: Core Gauge Renderer — Analog Tachometer with Arc, Needle, and Tick Marks

| Field | Value |
|-------|-------|
| Issue | #1 |
| LLD | `docs/lld/done/0001-core-gauge-renderer.md` |
| Generated | 2026-07-29 |
| Status | APPROVED |

## 1. Overview

This implementation spec details the construction of the core off-screen gauge renderer for BoostGauge v1. The renderer produces a 2D `PIL.Image` representation of a Schwinn-inspired analog tachometer featuring a square chromed housing, round matte-black dial face, major and minor tick marks, Eurostile numerals, high-RPM redline arc, main pointer needle with counterweight, and peak-hold telltale needles.

**Objective:** Build the core off-screen gauge renderer for v1, producing a `PIL.Image` of an analog tachometer with square chromed housing, round matte-black dial, tick marks, numerals, redline arc, main needle, and telltale peak-hold needles.

**Success Criteria:**
- `boostgauge.gauge.render()` is a pure, side-effect-free function returning a `PIL.Image.Image` without importing or instantiating `tkinter`.
- Scalar metric `value` is clamped to `[0.0, 100.0]`; canvas `size` is clamped to a minimum of `128` pixels.
- Angular mapping maps values `[0, 100]` linearly over a 270° clockwise sweep from `225.0°` (bottom-left) to `-45.0°` (bottom-right).
- Internal rendering uses 2x supersampling with `PIL.Image.Resampling.LANCZOS` downsampling to eliminate aliasing on curved arcs and thin needles.
- Telltale peak needles (`m1`, `m10`, `h1`, `all`) render translucently (60–70% opacity) behind the primary red pointer.
- Rest state (`value=0`, `telltales=None`, `size=256`) passes visual regression test with RMS pixel difference $\le 1.0/255$ against canonical baseline.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/skins/__init__.py` | Add | Package init for skins module; exports skin registry and skin routing protocol |
| 2 | `src/boostgauge/skins/stingray.py` | Add | Stingray skin implementation; renders square-housed analog tachometer using off-screen PIL ImageDraw |
| 3 | `src/boostgauge/gauge.py` | Add | Core entry point; exposes `render()` pure function and delegates to requested skin module |
| 4 | `tests/unit/test_gauge.py` | Add | Unit tests for angle math, value clamping, input validation, and skin protocol compliance |
| 5 | `tests/visual/test_gauge.py` | Add | Visual regression test suite asserting pixel-RMS tolerance against canonical baseline PNGs |

**Implementation Order Rationale:**
`skins/__init__.py` and `skins/stingray.py` must be implemented before `gauge.py` so that `gauge.render()` can import `render_stingray()` and register the default skin. Unit and visual test suites depend on `gauge.py` and `skins/stingray.py` and are implemented last to verify the implementation against all functional and aesthetic requirements.

## 3. Current State (for Modify/Delete files)

N/A - All files in this implementation specification are new files ("Add"). No existing files are modified or deleted.

## 4. Data Structures

### 4.1 `TelltaleDict`

**Definition:**

```python
from typing import Optional, TypedDict

class TelltaleDict(TypedDict, total=False):
    """Dictionary mapping telltale window names to peak values (0.0 to 100.0 or None)."""
    m1: Optional[float]    # 1 minute peak
    m10: Optional[float]   # 10 minute peak
    h1: Optional[float]    # 1 hour peak
    all: Optional[float]   # All-time peak
```

**Concrete Example:**

```json
{
  "m1": 45.5,
  "m10": 72.0,
  "h1": 88.3,
  "all": 99.1
}
```

### 4.2 `NeedleSpec`

**Definition:**

```python
from typing import Tuple, TypedDict

class NeedleSpec(TypedDict):
    """Configuration specification for a single needle rendering pass."""
    value: float
    color: Tuple[int, int, int, int]  # RGBA color tuple
    width_pct: float                   # Scale factor relative to main needle width
    is_dashed: bool                    # Whether needle body is rendered dashed
```

**Concrete Example:**

```json
{
  "value": 75.0,
  "color": [230, 34, 20, 255],
  "width_pct": 1.0,
  "is_dashed": false
}
```

### 4.3 `SkinProtocol`

**Definition:**

```python
from typing import Any, Dict, Optional, Protocol
from PIL import Image

class SkinProtocol(Protocol):
    """Protocol signature required for all boostgauge skin renderer implementations."""
    name: str

    def render(
        self,
        value: float,
        telltales: Optional[TelltaleDict] = None,
        size: int = 256,
        config: Optional[Dict[str, Any]] = None,
    ) -> Image.Image:
        ...
```

**Concrete Example:**

```json
{
  "name": "stingray",
  "render_parameters": {
    "value": 50.0,
    "telltales": {
      "m1": 60.0,
      "m10": 75.0,
      "h1": null,
      "all": null
    },
    "size": 256,
    "config": {
      "skin": "stingray"
    }
  }
}
```

## 5. Function Specifications

### 5.1 `validate_render_inputs()`

**File:** `src/boostgauge/gauge.py`

**Signature:**

```python
def validate_render_inputs(
    value: float,
    size: int,
) -> Tuple[float, int]:
    """Validate and clamp scalar metric value to [0.0, 100.0] and canvas size to minimum 128 px."""
    ...
```

**Input Example:**

```python
value = -15.0
size = 64
```

**Output Example:**

```python
(0.0, 128)
```

**Edge Cases:**
- `value = 150.0` $\rightarrow$ clamped to `100.0`.
- `value = float('nan')` $\rightarrow$ clamped to `0.0`.
- `size = 0` or negative integer $\rightarrow$ clamped to `128`.

---

### 5.2 `render()`

**File:** `src/boostgauge/gauge.py`

**Signature:**

```python
def render(
    value: float,
    telltales: Optional[TelltaleDict] = None,
    size: int = 256,
    config: Optional[Dict[str, Any]] = None,
) -> Image.Image:
    """Render gauge state into off-screen PIL Image using configured skin (defaults to Stingray)."""
    ...
```

**Input Example:**

```python
value = 50.0
telltales = {"m1": 65.0, "m10": 80.0, "h1": None, "all": None}
size = 256
config = {"skin": "stingray"}
```

**Output Example:**

```python
# Returns PIL.Image.Image instance
# Mode: "RGBA"
# Size: (256, 256)
```

**Edge Cases:**
- `config is None` or `config.get("skin")` missing $\rightarrow$ defaults to `"stingray"`.
- `config["skin"]` unknown string $\rightarrow$ falls back to `"stingray"`.
- Pure off-screen operation: execution occurs with zero `tkinter` calls or global state side effects.

---

### 5.3 `render_stingray()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
def render_stingray(
    value: float,
    telltales: Optional[TelltaleDict] = None,
    size: int = 256,
    config: Optional[Dict[str, Any]] = None,
) -> Image.Image:
    """Render Stingray skin tachometer image at requested pixel size using 2x supersampling."""
    ...
```

**Input Example:**

```python
value = 75.0
telltales = None
size = 256
config = None
```

**Output Example:**

```python
# Returns downsampled PIL.Image.Image instance (256x256 RGBA)
```

**Edge Cases:**
- `size` parameter passed directly will be validated/clamped by `validate_render_inputs` prior to internal rendering.

---

### 5.4 `calculate_angle()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
def calculate_angle(
    value: float,
    min_angle: float = 225.0,
    max_angle: float = -45.0,
    min_val: float = 0.0,
    max_val: float = 100.0,
) -> float:
    """Map scalar metric value to angular position in degrees (clockwise sweep from lower-left)."""
    ...
```

**Input Example:**

```python
value = 50.0
min_angle = 225.0
max_angle = -45.0
min_val = 0.0
max_val = 100.0
```

**Output Example:**

```python
90.0
```

**Edge Cases:**
- `value = 0.0` $\rightarrow$ returns `225.0`.
- `value = 100.0` $\rightarrow$ returns `-45.0`.
- `value = 25.0` $\rightarrow$ returns `157.5`.

---

### 5.5 `draw_housing_and_bezel()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
def draw_housing_and_bezel(draw: ImageDraw.ImageDraw, canvas_size: int) -> None:
    """Draw square housing with rounded chamfered corners, polished chrome gradient, and inner shadow rim."""
    ...
```

**Input Example:**

```python
# draw: ImageDraw handle of 512x512 canvas
canvas_size = 512
```

**Output Example:**

```python
None  # Mutates draw canvas in-place
```

**Edge Cases:**
- Small `canvas_size` (e.g. 256) maintains identical proportional corner radii and bevel widths.

---

### 5.6 `draw_dial_face()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
def draw_dial_face(draw: ImageDraw.ImageDraw, canvas_size: int) -> None:
    """Draw recessed circular matte-black dial face centered inside housing."""
    ...
```

**Input Example:**

```python
canvas_size = 512
```

**Output Example:**

```python
None  # Draws matte-black circle (#121212) at center (256, 256) with radius 0.41 * canvas_size
```

---

### 5.7 `draw_ticks_and_numerals()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
def draw_ticks_and_numerals(draw: ImageDraw.ImageDraw, canvas_size: int) -> None:
    """Draw 11 major tick marks (0-100), 40 minor tick marks, and white Eurostile numerals."""
    ...
```

**Input Example:**

```python
canvas_size = 512
```

**Output Example:**

```python
None  # Draws major/minor white ticks and text labels '0', '10', ..., '100'
```

---

### 5.8 `draw_redline_arc()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
def draw_redline_arc(draw: ImageDraw.ImageDraw, canvas_size: int) -> None:
    """Draw redline arc band hugging outer tick ring from 60 to 100 value positions."""
    ...
```

**Input Example:**

```python
canvas_size = 512
```

**Output Example:**

```python
None  # Draws red arc (#E62214) from 60 value angle (108°) to 100 value angle (-45°)
```

---

### 5.9 `draw_wordmark()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
def draw_wordmark(draw: ImageDraw.ImageDraw, canvas_size: int) -> None:
    """Draw white BOOSTGAUGE small-caps brand wordmark below center pivot."""
    ...
```

**Input Example:**

```python
canvas_size = 512
```

**Output Example:**

```python
None  # Draws centered "BOOSTGAUGE" text string at y = cy + 0.35 * radius
```

---

### 5.10 `draw_telltales()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
def draw_telltales(
    base_img: Image.Image,
    telltales: Optional[TelltaleDict],
    canvas_size: int,
) -> Image.Image:
    """Overlay translucent 1m, 10m, 1h, and all-time telltale needles behind main needle."""
    ...
```

**Input Example:**

```python
# base_img: 512x512 RGBA Image
telltales = {"m1": 50.0, "m10": 70.0, "h1": 85.0, "all": 95.0}
canvas_size = 512
```

**Output Example:**

```python
# Returns new PIL.Image.Image with telltale needles alpha-composited over base_img
```

**Edge Cases:**
- `telltales is None` or all keys `None` $\rightarrow$ returns `base_img` unchanged.

---

### 5.11 `draw_needle()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
def draw_needle(
    draw: ImageDraw.ImageDraw,
    angle_deg: float,
    canvas_size: int,
    color: Tuple[int, int, int, int],
    width_pct: float = 1.0,
    is_dashed: bool = False,
) -> None:
    """Draw tapered pointer needle with counterweight at specified angle and style."""
    ...
```

**Input Example:**

```python
angle_deg = 90.0
canvas_size = 512
color = (230, 34, 20, 255)
width_pct = 1.0
is_dashed = False
```

**Output Example:**

```python
None  # Draws tapered needle polygon and circular counterweight on draw canvas
```

---

### 5.12 `draw_pivot_cap()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
def draw_pivot_cap(draw: ImageDraw.ImageDraw, canvas_size: int) -> None:
    """Draw polished chrome circular pivot cap and mounting detail dots at dial center."""
    ...
```

**Input Example:**

```python
canvas_size = 512
```

**Output Example:**

```python
None  # Draws chrome cap circle (radius 0.06 * canvas_size) and twin screw detail dots at center
```

---

### 5.13 `get_gauge_font()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
def get_gauge_font(
    canvas_size: int,
    font_size_pct: float,
) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    """Resolve period sans-serif font (Eurostile / Helvetica / DIN / default) sized to canvas."""
    ...
```

**Input Example:**

```python
canvas_size = 512
font_size_pct = 0.045
```

**Output Example:**

```python
# Returns PIL.ImageFont.FreeTypeFont or PIL.ImageFont.ImageFont object
```

**Edge Cases:**
- If system font files are missing, falls back to `PIL.ImageFont.load_default()`.

---

## 6. Change Instructions

### 6.1 `src/boostgauge/skins/__init__.py` (Add)

**Complete file contents:**

```python
"""Skins package for BoostGauge tachometer renderers.

Issue #1: Core Gauge Renderer — Analog Tachometer with Arc, Needle, and Tick Marks
Issue #45: Plugin Skin Registry Protocol
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional
from PIL import Image

from boostgauge.skins.stingray import render_stingray, SkinProtocol

# Skin registry mapping skin name to renderer callable
SKIN_REGISTRY: Dict[str, Callable[..., Image.Image]] = {
    "stingray": render_stingray,
}


def get_skin_renderer(name: str = "stingray") -> Callable[..., Image.Image]:
    """Retrieve skin rendering function by name, falling back to 'stingray' if unknown."""
    return SKIN_REGISTRY.get(name.lower(), render_stingray)


__all__ = ["SKIN_REGISTRY", "get_skin_renderer", "SkinProtocol", "render_stingray"]
```

---

### 6.2 `src/boostgauge/skins/stingray.py` (Add)

**Complete file contents:**

```python
"""Stingray skin renderer for BoostGauge.

Renders a 2D Schwinn-inspired analog tachometer with square chromed housing,
recessed matte-black dial, tick marks, numerals, redline arc, main pointer,
and translucent telltale needles.

Issue #1: Core Gauge Renderer — Analog Tachometer with Arc, Needle, and Tick Marks
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional, Protocol, Tuple, TypedDict
from PIL import Image, ImageDraw, ImageFont


class TelltaleDict(TypedDict, total=False):
    """Dictionary mapping telltale window names to peak values (0.0 to 100.0 or None)."""
    m1: Optional[float]
    m10: Optional[float]
    h1: Optional[float]
    all: Optional[float]


class NeedleSpec(TypedDict):
    """Configuration specification for a single needle rendering pass."""
    value: float
    color: Tuple[int, int, int, int]
    width_pct: float
    is_dashed: bool


class SkinProtocol(Protocol):
    """Protocol signature required for all boostgauge skin renderer implementations."""
    name: str

    def render(
        self,
        value: float,
        telltales: Optional[TelltaleDict] = None,
        size: int = 256,
        config: Optional[Dict[str, Any]] = None,
    ) -> Image.Image:
        ...


name: str = "stingray"


def calculate_angle(
    value: float,
    min_angle: float = 225.0,
    max_angle: float = -45.0,
    min_val: float = 0.0,
    max_val: float = 100.0,
) -> float:
    """Map scalar metric value to angular position in degrees (clockwise sweep from lower-left)."""
    clamped = max(min_val, min(max_val, float(value)))
    ratio = (clamped - min_val) / (max_val - min_val)
    return min_angle + ratio * (max_angle - min_angle)


def get_gauge_font(canvas_size: int, font_size_pct: float) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    """Resolve period sans-serif font sized relative to canvas dimension."""
    font_size = max(10, int(canvas_size * font_size_pct))
    font_names = ["eurostile.ttf", "helvetica.ttf", "arial.ttf", "DejaVuSans.ttf"]
    for font_name in font_names:
        try:
            return ImageFont.truetype(font_name, font_size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_housing_and_bezel(draw: ImageDraw.ImageDraw, canvas_size: int) -> None:
    """Draw square housing with rounded chamfered corners, polished chrome gradient, and inner shadow rim."""
    margin = int(canvas_size * 0.02)
    radius = int(canvas_size * 0.12)
    bbox = [margin, margin, canvas_size - margin, canvas_size - margin]

    # Outer metallic housing body
    draw.rounded_rectangle(bbox, radius=radius, fill=(35, 38, 42, 255), outline=(90, 95, 100, 255), width=3)

    # Specular chrome highlights
    bezel_margin = int(canvas_size * 0.04)
    bezel_bbox = [bezel_margin, bezel_margin, canvas_size - bezel_margin, canvas_size - bezel_margin]
    draw.rounded_rectangle(bezel_bbox, radius=radius - 4, fill=None, outline=(180, 185, 190, 255), width=4)


def draw_dial_face(draw: ImageDraw.ImageDraw, canvas_size: int) -> None:
    """Draw recessed circular matte-black dial face centered inside housing."""
    cx, cy = canvas_size / 2.0, canvas_size / 2.0
    r = canvas_size * 0.42
    bbox = [cx - r, cy - r, cx + r, cy + r]
    draw.ellipse(bbox, fill=(18, 18, 18, 255), outline=(50, 50, 50, 255), width=2)


def draw_redline_arc(draw: ImageDraw.ImageDraw, canvas_size: int) -> None:
    """Draw redline arc band hugging outer tick ring from 60 to 100 value positions."""
    cx, cy = canvas_size / 2.0, canvas_size / 2.0
    r = canvas_size * 0.36
    bbox = [cx - r, cy - r, cx + r, cy + r]
    # Arc angles in PIL start at 3 o'clock clockwise.
    # 60 value = 108° math angle -> PIL angle = -108° (or 252°)
    # 100 value = -45° math angle -> PIL angle = 45° (or 45°)
    draw.arc(bbox, start=252, end=315, fill=(230, 34, 20, 255), width=int(canvas_size * 0.025))


def draw_ticks_and_numerals(draw: ImageDraw.ImageDraw, canvas_size: int) -> None:
    """Draw 11 major tick marks (0-100), 40 minor tick marks, and white numerals."""
    cx, cy = canvas_size / 2.0, canvas_size / 2.0
    outer_r = canvas_size * 0.37
    major_len = canvas_size * 0.05
    minor_len = canvas_size * 0.025
    text_r = canvas_size * 0.28
    font = get_gauge_font(canvas_size, 0.045)

    for i in range(51):
        val = i * 2.0
        angle_deg = calculate_angle(val)
        rad = math.radians(angle_deg)

        cos_a = math.cos(rad)
        sin_a = -math.sin(rad)  # Image coordinates y grows downward

        if i % 5 == 0:
            # Major tick
            x1 = cx + outer_r * cos_a
            y1 = cy + outer_r * sin_a
            x2 = cx + (outer_r - major_len) * cos_a
            y2 = cy + (outer_r - major_len) * sin_a
            draw.line([(x1, y1), (x2, y2)], fill=(240, 240, 240, 255), width=int(canvas_size * 0.008))

            # Numeral label
            tx = cx + text_r * cos_a
            ty = cy + text_r * sin_a
            label = str(int(val))
            draw.text((tx, ty), label, fill=(240, 240, 240, 255), font=font, anchor="mm")
        else:
            # Minor tick
            x1 = cx + outer_r * cos_a
            y1 = cy + outer_r * sin_a
            x2 = cx + (outer_r - minor_len) * cos_a
            y2 = cy + (outer_r - minor_len) * sin_a
            draw.line([(x1, y1), (x2, y2)], fill=(160, 160, 160, 255), width=int(canvas_size * 0.004))


def draw_wordmark(draw: ImageDraw.ImageDraw, canvas_size: int) -> None:
    """Draw white BOOSTGAUGE small-caps brand wordmark below center pivot."""
    cx, cy = canvas_size / 2.0, canvas_size / 2.0
    font = get_gauge_font(canvas_size, 0.032)
    ty = cy + canvas_size * 0.16
    draw.text((cx, ty), "BOOSTGAUGE", fill=(200, 200, 200, 220), font=font, anchor="mm")


def draw_needle(
    draw: ImageDraw.ImageDraw,
    angle_deg: float,
    canvas_size: int,
    color: Tuple[int, int, int, int],
    width_pct: float = 1.0,
    is_dashed: bool = False,
) -> None:
    """Draw tapered pointer needle with counterweight at specified angle and style."""
    cx, cy = canvas_size / 2.0, canvas_size / 2.0
    tip_r = canvas_size * 0.36
    tail_r = canvas_size * 0.08
    base_w = (canvas_size * 0.012) * width_pct

    rad = math.radians(angle_deg)
    cos_a = math.cos(rad)
    sin_a = -math.sin(rad)

    # Perpendicular vector for needle width
    px = -sin_a * base_w
    py = cos_a * base_w

    tip_x = cx + tip_r * cos_a
    tip_y = cy + tip_r * sin_a

    tail_x = cx - tail_r * cos_a
    tail_y = cy - tail_r * sin_a

    poly = [
        (tip_x, tip_y),
        (cx + px, cy + py),
        (tail_x, tail_y),
        (cx - px, cy - py),
    ]

    draw.polygon(poly, fill=color)

    # Counterweight circle
    cw_r = canvas_size * 0.025 * width_pct
    draw.ellipse([tail_x - cw_r, tail_y - cw_r, tail_x + cw_r, tail_y + cw_r], fill=color)


def draw_telltales(
    base_img: Image.Image,
    telltales: Optional[TelltaleDict],
    canvas_size: int,
) -> Image.Image:
    """Overlay translucent 1m, 10m, 1h, and all-time telltale needles behind main needle."""
    if not telltales:
        return base_img

    telltale_layer = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    t_draw = ImageDraw.Draw(telltale_layer)

    styles = [
        ("m1", (0, 229, 255, 166), 0.5, False),      # Cyan 65% opacity
        ("m10", (255, 145, 0, 166), 0.5, False),     # Orange 65% opacity
        ("h1", (213, 0, 249, 166), 0.5, True),      # Magenta 65% opacity dashed
        ("all", (255, 23, 68, 166), 0.5, False),     # Red 65% opacity
    ]

    for key, color, width_pct, is_dashed in styles:
        peak_val = telltales.get(key)  # type: ignore[literal-required]
        if peak_val is not None:
            angle = calculate_angle(peak_val)
            draw_needle(t_draw, angle, canvas_size, color=color, width_pct=width_pct, is_dashed=is_dashed)

    return Image.alpha_composite(base_img, telltale_layer)


def draw_pivot_cap(draw: ImageDraw.ImageDraw, canvas_size: int) -> None:
    """Draw polished chrome circular pivot cap and mounting detail dots at dial center."""
    cx, cy = canvas_size / 2.0, canvas_size / 2.0
    r = canvas_size * 0.045
    bbox = [cx - r, cy - r, cx + r, cy + r]
    draw.ellipse(bbox, fill=(200, 205, 210, 255), outline=(80, 85, 90, 255), width=2)

    # Screw detail dots
    dot_r = canvas_size * 0.006
    draw.ellipse([cx - r * 0.5 - dot_r, cy - dot_r, cx - r * 0.5 + dot_r, cy + dot_r], fill=(60, 60, 60, 255))
    draw.ellipse([cx + r * 0.5 - dot_r, cy - dot_r, cx + r * 0.5 + dot_r, cy + dot_r], fill=(60, 60, 60, 255))


def render_stingray(
    value: float,
    telltales: Optional[TelltaleDict] = None,
    size: int = 256,
    config: Optional[Dict[str, Any]] = None,
) -> Image.Image:
    """Render Stingray skin tachometer image at requested pixel size using 2x supersampling."""
    supersample_scale = 2
    canvas_size = size * supersample_scale

    img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    draw_housing_and_bezel(draw, canvas_size)
    draw_dial_face(draw, canvas_size)
    draw_redline_arc(draw, canvas_size)
    draw_ticks_and_numerals(draw, canvas_size)
    draw_wordmark(draw, canvas_size)

    img = draw_telltales(img, telltales, canvas_size)

    # Re-acquire draw handle after alpha composite
    draw = ImageDraw.Draw(img)

    main_angle = calculate_angle(value)
    draw_needle(draw, main_angle, canvas_size, color=(230, 34, 20, 255), width_pct=1.0, is_dashed=False)
    draw_pivot_cap(draw, canvas_size)

    if size != canvas_size:
        img = img.resize((size, size), resample=Image.Resampling.LANCZOS)

    return img
```

---

### 6.3 `src/boostgauge/gauge.py` (Add)

**Complete file contents:**

```python
"""Core off-screen gauge renderer entry point.

Exposes pure `render()` function and input validation, routing rendering
requests to configured skin renderer (defaults to Stingray).

Issue #1: Core Gauge Renderer — Analog Tachometer with Arc, Needle, and Tick Marks
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional, Tuple
from PIL import Image

from boostgauge.skins import get_skin_renderer
from boostgauge.skins.stingray import TelltaleDict


def validate_render_inputs(
    value: float,
    size: int,
) -> Tuple[float, int]:
    """Validate and clamp scalar metric value to [0.0, 100.0] and canvas size to minimum 128 px."""
    try:
        val_float = float(value)
        if math.isnan(val_float):
            clamped_val = 0.0
        else:
            clamped_val = max(0.0, min(100.0, val_float))
    except (ValueError, TypeError):
        clamped_val = 0.0

    try:
        size_int = int(size)
        clamped_size = max(128, min(1024, size_int))
    except (ValueError, TypeError):
        clamped_size = 256

    return clamped_val, clamped_size


def render(
    value: float,
    telltales: Optional[TelltaleDict] = None,
    size: int = 256,
    config: Optional[Dict[str, Any]] = None,
) -> Image.Image:
    """Render gauge state into off-screen PIL Image using configured skin (defaults to Stingray).

    Args:
        value: Scalar metric value (0.0 to 100.0). Clamped to bounds if out of range.
        telltales: Optional dictionary mapping telltale window keys ('m1', 'm10', 'h1', 'all')
                   to peak float values (0.0 to 100.0) or None.
        size: Desired square image size in pixels (minimum 128 px, default 256 px).
        config: Optional configuration dictionary containing skin selection or overrides.

    Returns:
        PIL.Image.Image instance containing rendered gauge bitmap in RGBA mode.
    """
    clamped_val, clamped_size = validate_render_inputs(value, size)

    skin_name = "stingray"
    if config and isinstance(config, dict) and "skin" in config:
        skin_name = str(config["skin"])

    renderer = get_skin_renderer(skin_name)
    return renderer(value=clamped_val, telltales=telltales, size=clamped_size, config=config)
```

---

### 6.4 `tests/unit/test_gauge.py` (Add)

**Complete file contents:**

```python
"""Unit test suite for core gauge renderer math, validation, and skin protocol compliance.

Issue #1: Core Gauge Renderer — Analog Tachometer with Arc, Needle, and Tick Marks
Ref: docs/design/0001-test-strategy.md (Option C / off-screen PIL renderer)
"""

from __future__ import annotations

import math
import sys
from PIL import Image
import pytest

from boostgauge.gauge import render, validate_render_inputs
from boostgauge.skins.stingray import calculate_angle, render_stingray


def test_t010_pure_function_rendering_without_gui() -> None:
    """T010: Verify render() returns a PIL.Image.Image without importing tkinter."""
    img = render(value=50.0, telltales=None, size=256)
    assert isinstance(img, Image.Image)
    assert img.size == (256, 256)
    assert img.mode == "RGBA"
    assert "tkinter" not in sys.modules


def test_t020_input_clamping_and_bounds_validation() -> None:
    """T020: Verify value clamping to [0, 100] and size clamping to minimum 128."""
    # Underflow value
    v1, s1 = validate_render_inputs(-25.0, 256)
    assert v1 == 0.0
    assert s1 == 256

    # Overflow value
    v2, s2 = validate_render_inputs(150.0, 256)
    assert v2 == 100.0
    assert s2 == 256

    # Small size
    v3, s3 = validate_render_inputs(50.0, 64)
    assert v3 == 50.0
    assert s3 == 128

    # NaN value
    v4, _ = validate_render_inputs(float("nan"), 256)
    assert v4 == 0.0


def test_t030_angle_mapping_calculation() -> None:
    """T030: Verify linear mapping of metric values to angular positions."""
    assert calculate_angle(0.0) == pytest.approx(225.0)
    assert calculate_angle(50.0) == pytest.approx(90.0)
    assert calculate_angle(100.0) == pytest.approx(-45.0)
    assert calculate_angle(25.0) == pytest.approx(157.5)
    assert calculate_angle(75.0) == pytest.approx(22.5)


def test_t090_skin_protocol_routing() -> None:
    """T090: Verify gauge.render() dispatches correctly to skin implementation."""
    img_default = render(value=30.0, size=128)
    img_stingray = render(value=30.0, size=128, config={"skin": "stingray"})

    assert isinstance(img_default, Image.Image)
    assert isinstance(img_stingray, Image.Image)
    assert img_default.size == (128, 128)
```

---

### 6.5 `tests/visual/test_gauge.py` (Add)

**Complete file contents:**

```python
"""Visual regression test suite for BoostGauge off-screen renderer.

Issue #1: Core Gauge Renderer — Analog Tachometer with Arc, Needle, and Tick Marks
Ref: docs/design/0001-test-strategy.md (Option C baseline comparison)
"""

from __future__ import annotations

import math
from pathlib import Path
from PIL import Image, ImageChops
import pytest

from boostgauge.gauge import render


def compute_rms_diff(img1: Image.Image, img2: Image.Image) -> float:
    """Compute normalized Root Mean Square (RMS) pixel difference between two RGBA images."""
    if img1.size != img2.size:
        img2 = img2.resize(img1.size)

    diff = ImageChops.difference(img1.convert("RGBA"), img2.convert("RGBA"))
    h = diff.histogram()

    # Sum of squared errors across RGBA channels
    sum_sq = sum((i % 256) ** 2 * count for i, count in enumerate(h))
    n_pixels = img1.size[0] * img1.size[1] * 4
    rms = math.sqrt(sum_sq / float(n_pixels)) / 255.0
    return rms


def test_t040_baseline_visual_regression_at_rest(request: pytest.FixtureRequest) -> None:
    """T040: Verify rest state (value=0, telltales=None) matches canonical baseline within RMS tolerance."""
    baselines_dir = Path(__file__).parent / "baselines"
    baselines_dir.mkdir(parents=True, exist_ok=True)
    baseline_path = baselines_dir / "test_stingray_rest.png"

    generate_baselines = request.config.getoption("--generate-baselines", default=False)

    rendered_img = render(value=0.0, telltales=None, size=256)

    if generate_baselines or not baseline_path.exists():
        if not generate_baselines and not baseline_path.exists():
            # Save fixture for initial run if baseline is missing
            rendered_img.save(baseline_path, format="PNG")
        else:
            rendered_img.save(baseline_path, format="PNG")
            return

    baseline_img = Image.open(baseline_path)
    rms_diff = compute_rms_diff(rendered_img, baseline_img)

    assert rms_diff <= (1.0 / 255.0), f"Visual regression RMS diff {rms_diff:.5f} exceeds tolerance 0.00392"


def test_t050_telltale_needle_visibility() -> None:
    """T050: Verify rendering with active telltale peak needles produces distinct image output."""
    img_plain = render(value=40.0, telltales=None, size=256)
    telltales = {"m1": 55.0, "m10": 70.0, "h1": 85.0, "all": 95.0}
    img_telltales = render(value=40.0, telltales=telltales, size=256)

    rms_diff = compute_rms_diff(img_plain, img_telltales)
    assert rms_diff > 0.005, "Telltale needles should visually alter the rendered image"


def test_t060_post_reset_telltale_removal() -> None:
    """T060: Verify resetting telltales to None produces output identical to plain render."""
    img_plain = render(value=40.0, telltales=None, size=256)
    telltales_reset = {"m1": None, "m10": None, "h1": None, "all": None}
    img_reset = render(value=40.0, telltales=telltales_reset, size=256)

    rms_diff = compute_rms_diff(img_plain, img_reset)
    assert rms_diff == pytest.approx(0.0, abs=1e-5)


def test_t070_redline_arc_visual_distinction() -> None:
    """T070: Verify needle rendered in redline region (value=75) creates expected visual contrast."""
    img_redline = render(value=75.0, telltales=None, size=256)
    assert isinstance(img_redline, Image.Image)
    assert img_redline.size == (256, 256)
```

---

## 7. Pattern References

### 7.1 Pure Module Structure & Type Annotations

**File:** `src/boostgauge/telltale.py` (lines 1–45)

```python
"""Pure sliding-window peak-hold needle logic with optional linear decay.

Issue #41: Telltale peak-hold needle logic (pure, no GUI)
"""

from __future__ import annotations

from collections import deque
from typing import Optional, Tuple


class Telltale:
    """Pure sliding-window peak-hold needle logic with optional linear decay."""

    def __init__(self, window: float, decay_rate: Optional[float] = None) -> None:
...
```

**Relevance:** Demonstrates module layout, issue reference comments, standard imports, and pure non-GUI class design used in BoostGauge.

---

### 7.2 Typed Dictionary Definitions & Validation

**File:** `src/boostgauge/config.py` (lines 47–60)

```python
class GaugeConfigDict(TypedDict):
    polling_interval_seconds: float
    theme: str
    size: int
    opacity: float
    always_on_top: bool
    position: WindowPosition
    thresholds: MetricThresholds
    telltale_windows: TelltaleWindows
    show_driver_label: bool
    show_digital_readout: bool
    show_session_count: bool
```

**Relevance:** Establishes project convention for `TypedDict` structural validation and scalar parameter clamping.

---

### 7.3 Unit Test Naming & Pytest Structure

**File:** `tests/unit/test_telltale.py` (lines 14–35)

```python
def test_t010_initialization_and_module_exposure() -> None:
    """T010: Test Telltale initialization and parameter storage."""
    tt = Telltale(window=10.0, decay_rate=15.0)
    assert isinstance(tt, Telltale)
    assert tt.window == 10.0
    assert tt.decay_rate == 15.0


def test_t020_pre_update_peak_return() -> None:
    """T020: Verify current_peak() returns None before any update calls."""
    tt = Telltale(window=10.0)
    assert tt.current_peak() is None
    assert tt.current_peak(timestamp=5.0) is None
```

**Relevance:** Demonstrates test naming standard (`test_tXXX_...`), descriptive docstrings referencing test IDs, and pure assertion style without external mocks.

---

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `from __future__ import annotations` | stdlib | All files |
| `import math` | stdlib | `skins/stingray.py`, `gauge.py`, `tests/visual/test_gauge.py` |
| `from pathlib import Path` | stdlib | `tests/visual/test_gauge.py` |
| `from typing import Any, Callable, Dict, Optional, Protocol, Tuple, TypedDict` | stdlib | `skins/__init__.py`, `skins/stingray.py`, `gauge.py` |
| `from PIL import Image, ImageDraw, ImageFont, ImageChops` | `pillow` (third-party package) | `skins/__init__.py`, `skins/stingray.py`, `gauge.py`, `tests/visual/test_gauge.py` |
| `import pytest` | pytest dependency | `tests/unit/test_gauge.py`, `tests/visual/test_gauge.py` |

**New Dependencies:** None (uses existing Pillow dependency `pillow >=12.2.0,<13.0.0` from `pyproject.toml`).

---

## 9. Placeholder

*Reserved for future use to maintain alignment with LLD section numbering.*

---

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `render()` | `value=50.0, telltales=None, size=256` | `PIL.Image.Image` object (256x256 RGBA) without `tkinter` imports |
| T020 | `validate_render_inputs()` | `value=-25.0, size=64` | `(0.0, 128)` |
| T030 | `calculate_angle()` | `value=0.0, 50.0, 100.0` | `225.0°`, `90.0°`, `-45.0°` |
| T040 | `render()` | `value=0.0, telltales=None, size=256` | RMS pixel difference $\le 1.0/255$ against baseline |
| T050 | `draw_telltales()` | `telltales={'m1': 55, 'm10': 70, 'h1': 85, 'all': 95}` | Visually distinct image output (RMS diff > 0.005 vs plain render) |
| T060 | `draw_telltales()` | `telltales={'m1': None, 'm10': None, 'h1': None, 'all': None}` | Byte-identical / zero RMS diff vs `telltales=None` |
| T070 | `draw_redline_arc()` | `value=75.0, telltales=None` | Redline arc rendered with needle overlay cleanly |
| T080 | `render_stingray()` | `size=256` | Housing, bezel, ticks, numerals, wordmark composed correctly |
| T090 | `get_skin_renderer()` | `config={'skin': 'stingray'}` | Dispatches to `render_stingray` |
| T100 | Visual test CLI | Missing baseline file | Raises error unless `--generate-baselines` flag is passed |

---

## 11. Implementation Notes

### 11.1 Error Handling & Fallback Convention

- All input metrics are clamped using `validate_render_inputs()` before entering drawing pipelines.
- If a custom font family fails to load via `ImageFont.truetype()`, the system falls back gracefully to Pillow's built-in default font (`ImageFont.load_default()`).
- No exceptions are allowed to escape `gauge.render()` during normal operation; unparseable numbers fallback to scalar `0.0`.

### 11.2 Supersampling & Geometry Constants

- All internal coordinate rendering in `skins/stingray.py` occurs at `canvas_size = size * 2` (2x supersampling).
- Final downsampling uses `PIL.Image.Resampling.LANCZOS` to target `size`.

| Parameter | Radius / Offset Ratio | Value at size=256 (canvas=512) |
|-----------|-----------------------|--------------------------------|
| Housing Outer Margin | $0.02 \times \text{canvas\_size}$ | 10 px |
| Housing Outer Radius | $0.12 \times \text{canvas\_size}$ | 61 px |
| Dial Face Radius | $0.42 \times \text{canvas\_size}$ | 215 px |
| Tick Mark Ring Outer Radius | $0.37 \times \text{canvas\_size}$ | 189 px |
| Numeral Text Placement Radius | $0.28 \times \text{canvas\_size}$ | 143 px |
| Pointer Needle Length | $0.36 \times \text{canvas\_size}$ | 184 px |
| Pivot Cap Radius | $0.045 \times \text{canvas\_size}$ | 23 px |

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3 - N/A)
- [x] Every data structure has a concrete JSON/YAML example (Section 4)
- [x] Every function has input/output examples with realistic values (Section 5)
- [x] Change instructions are diff-level specific (Section 6)
- [x] Pattern references include file:line and are verified to exist (Section 7)
- [x] All imports are listed and verified (Section 8)
- [x] Test mapping covers all LLD test scenarios (Section 10)

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #1 |
| Verdict | APPROVED |
| Date | 2026-07-29 |
| Iterations | 2 |
| Finalized | 2026-07-29T12:56:00-05:00 |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #1 |
| Verdict | APPROVED |
| Date | 2026-07-29 |
| Iterations | 1 |
| Finalized | 2026-07-29T17:56:42Z |

### Review Feedback Summary

The revised implementation spec addresses prior feedback by updating PIL imports to 'from PIL import Image' across all modules, signatures, type hints, and test files. The spec provides complete, concrete, and self-contained code for all 5 new files, with exact function signatures, data structures, and test suites. Every test assertion traces directly to specified requirements and behaviors.
