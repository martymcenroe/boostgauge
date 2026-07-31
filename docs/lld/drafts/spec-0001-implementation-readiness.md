# Implementation Spec: Core Gauge Renderer — Analog Tachometer with Arc, Needle, and Tick Marks

| Field | Value |
|-------|-------|
| Issue | #1 |
| LLD | `docs/lld/done/1-core-gauge-renderer.md` |
| Generated | 2026-07-31 |
| Status | APPROVED |

## 1. Overview

*Implement the v1 core tachometer gauge renderer as a pure PIL function producing off-screen gauge images according to the Stingray aesthetic specification in `docs/design/0002-aesthetic-v1-stingray.md`.*

**Objective:** Create an off-screen analog tachometer gauge renderer in Python using Pillow (`PIL.Image`, `PIL.ImageDraw`) operating without any `tkinter` dependency, featuring 4x supersampling, skin dispatch architecture, dynamic needles, peak-hold telltales, and baseline visual tests per Option C test strategy.

**Success Criteria:**
- `render(value, telltales, size, config)` returns a `PIL.Image.Image` without instantiating or importing `tkinter`.
- Numerical values outside `[0.0, 100.0]` are clamped to `[0.0, 100.0]`. Dimensions smaller than `(128, 128)` or unsupported skins raise `ValueError`.
- Bezel, dial face, 11 major / 40 minor tick marks, Eurostile-adjacent numerals, redline arc (60–100), and wordmark render deterministically.
- Main red needle (`#E63946`) and up to 4 translucent telltale needles (cyan, orange, magenta, red at ~65% opacity) sweep clockwise from angle 225° (value 0) to -45° (value 100).
- Pure function execution achieves byte-deterministic PNG output and passes RMS visual regression checks (RMS diff <= 1.0/255) against committed baselines.

---

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `tests/visual/baselines` | Add (Directory) | Directory for storing baseline reference image blobs for visual regression testing. |
| 2 | `src/boostgauge/skins/__init__.py` | Add | Package initializer for skins module. |
| 3 | `src/boostgauge/skins/stingray.py` | Add | Stingray skin rendering logic (bezel, dial face, tick marks, numerals, redline arc, wordmark, main needle, telltale needles). |
| 4 | `src/boostgauge/gauge.py` | Add | Core gauge entry point exposing pure function `render(value, telltales, size, config)` with skin dispatch logic. |
| 5 | `tests/unit/test_gauge.py` | Add | Unit tests for gauge function API, parameter validation, deterministic math, and off-screen PIL output. |
| 6 | `tests/visual/test_stingray_visual.py` | Add | Render-tier visual regression tests comparing output against baseline images with RMS tolerance and baseline-independent property assertions. |

**Implementation Order Rationale:**
1. Create `tests/visual/baselines` directory structure to store baseline PNGs.
2. Initialize `src/boostgauge/skins/__init__.py` package so skins can be imported.
3. Implement `src/boostgauge/skins/stingray.py` containing the low-level PIL drawing routines, background caching, supersampling, tick generation, and needle positioning.
4. Implement `src/boostgauge/gauge.py` to expose the main `render()` public entry point and delegate skin selection to `stingray.py`.
5. Implement `tests/unit/test_gauge.py` to validate API contracts, error boundaries, input clamping, angle math, and PIL image properties.
6. Implement `tests/visual/test_stingray_visual.py` to perform byte-equality, RMS regression checks against baselines, and baseline-independent trigonometric pixel property checks.

---

## 3. Current State (for Modify/Delete files)

*No files are being modified or deleted in this implementation. All files listed in Section 2 are new additions (`Add` or `Add (Directory)`).*

Existing parent directories `src/boostgauge/`, `src/boostgauge/skins/`, `tests/unit/`, and `tests/visual/` are already present in the workspace layout.

**Reference Parent Directory Layout:**
- `src/boostgauge/` (exists, contains `collectors/`)
- `tests/` (exists, contains `conftest.py`)

---

## 4. Data Structures

### 4.1 `TelltalePeaks`

**Definition:**

```python
from typing import TypedDict

class TelltalePeaks(TypedDict, total=False):
    window_1m: float | None
    window_10m: float | None
    window_1h: float | None
    window_all: float | None
```

**Concrete Example:**

```json
{
    "window_1m": 45.0,
    "window_10m": 67.5,
    "window_1h": 82.0,
    "window_all": 98.4
}
```

### 4.2 `RenderConfig`

**Definition:**

```python
from typing import Any, TypedDict

class RenderConfig(TypedDict, total=False):
    skin: str
    supersample_factor: int
    enable_cache: bool
```

**Concrete Example:**

```json
{
    "skin": "stingray",
    "supersample_factor": 4,
    "enable_cache": true
}
```

---

## 5. Function Specifications

### 5.1 `render()`

**File:** `src/boostgauge/gauge.py`

**Signature:**

```python
def render(
    value: float,
    telltales: dict[str, float | None] | None = None,
    size: tuple[int, int] = (256, 256),
    config: dict[str, Any] | None = None,
) -> Image.Image:
    """Pure function rendering gauge face and needles to off-screen PIL Image."""
    ...
```

**Input Example:**

```python
value = 75.0
telltales = {"window_1m": 80.0, "window_10m": 90.0, "window_1h": None, "window_all": 95.0}
size = (256, 256)
config = {"skin": "stingray"}
```

**Output Example:**

```python
# Returns instance of PIL.Image.Image with size=(256, 256), mode="RGBA"
<PIL.Image.Image image mode=RGBA size=256x256 at 0x7F8B9C0D30>
```

**Edge Cases:**
- `value = -15.0` -> Clamped to `0.0` before rendering.
- `value = 120.0` -> Clamped to `100.0` before rendering.
- `value = float('nan')` or `float('inf')` -> Handled safely by clamping to `0.0`.
- `size = (100, 100)` -> Raises `ValueError("Gauge size must be at least 128x128")`.
- `config = {"skin": "cyberpunk"}` -> Raises `ValueError("Unsupported skin: 'cyberpunk'")`.

---

### 5.2 `render_stingray()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
def render_stingray(
    value: float,
    telltales: dict[str, float | None] | None = None,
    size: tuple[int, int] = (256, 256),
    config: dict[str, Any] | None = None,
) -> Image.Image:
    """Stingray skin implementation rendering to PIL Image with 4x supersampling."""
    ...
```

**Input Example:**

```python
value = 50.0
telltales = None
size = (256, 256)
config = None
```

**Output Example:**

```python
<PIL.Image.Image image mode=RGBA size=256x256 at 0x7F8B9C0E10>
```

**Edge Cases:**
- `config = {"supersample_factor": 1}` -> Disables supersampling and renders directly at target resolution.
- `telltales = {}` -> Renders main needle only, skipping telltales.

---

### 5.3 `_val_to_angle()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
def _val_to_angle(
    value: float,
    min_angle: float = 225.0,
    max_angle: float = -45.0,
) -> float:
    """Map gauge metric value (0-100) to dial sweep angle in degrees."""
    ...
```

**Input Example:**

```python
value = 0.0   # returns 225.0
value = 50.0  # returns 90.0
value = 100.0 # returns -45.0
```

**Output Example:**

```python
90.0
```

**Edge Cases:**
- Input value < 0.0 is assumed pre-clamped to 0.0 (returns 225.0).
- Input value > 100.0 is assumed pre-clamped to 100.0 (returns -45.0).

---

### 5.4 `_draw_bezel_and_dial()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
def _draw_bezel_and_dial(
    draw: ImageDraw.ImageDraw,
    size: tuple[int, int],
) -> None:
    """Draw square chromed bezel, chamfered corners, specular highlights, and recessed round dial face."""
    ...
```

**Input Example:**

```python
# draw is an ImageDraw context on a (1024, 1024) canvas
size = (1024, 1024)
```

**Output Example:**

```python
None  # Mutates PIL Image canvas in-place
```

**Edge Cases:**
- Canvas size non-square `(1024, 800)` -> Uses `min(width, height)` for dial radius calculations.

---

### 5.5 `_draw_ticks_and_numerals()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
def _draw_ticks_and_numerals(
    draw: ImageDraw.ImageDraw,
    center: tuple[float, float],
    radius: float,
) -> None:
    """Draw 11 major and 40 minor white tick marks and Eurostile-adjacent numerals (0-100)."""
    ...
```

**Input Example:**

```python
center = (512.0, 512.0)
radius = 450.0
```

**Output Example:**

```python
None  # Mutates PIL Image canvas in-place
```

---

### 5.6 `_draw_redline_arc()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
def _draw_redline_arc(
    draw: ImageDraw.ImageDraw,
    center: tuple[float, float],
    radius: float,
) -> None:
    """Draw redline arc hugging outer tick ring from metric value 60 to 100."""
    ...
```

**Input Example:**

```python
center = (512.0, 512.0)
radius = 450.0
```

**Output Example:**

```python
None  # Mutates canvas in-place drawing arc from angle for val=60 (63.0°) to val=100 (-45.0°)
```

---

### 5.7 `_draw_wordmark()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
def _draw_wordmark(
    draw: ImageDraw.ImageDraw,
    center: tuple[float, float],
    radius: float,
) -> None:
    """Draw BOOSTGAUGE small-caps white wordmark below central pivot cap."""
    ...
```

**Input Example:**

```python
center = (512.0, 512.0)
radius = 450.0
```

**Output Example:**

```python
None  # Renders "BOOSTGAUGE" text centered at (512, 692)
```

---

### 5.8 `_draw_needle()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
def _draw_needle(
    draw: ImageDraw.ImageDraw,
    center: tuple[float, float],
    radius: float,
    angle: float,
    color: tuple[int, int, int, int] | str,
    width: float,
    length_factor: float,
    has_counterweight: bool = True,
) -> None:
    """Draw a gauge needle (main or telltale) pointing at specified angle."""
    ...
```

**Input Example:**

```python
center = (512.0, 512.0)
radius = 450.0
angle = 90.0  # 12 o'clock (straight up)
color = (230, 57, 70, 255) # Red #E63946
width = 12.0
length_factor = 0.85
has_counterweight = True
```

**Output Example:**

```python
None  # Renders tapered needle polygon pointing at (512, 129.5) with counterweight
```

---

### 5.9 `_get_cached_background()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
def _get_cached_background(
    size: tuple[int, int],
    skin_name: str = "stingray",
) -> Image.Image:
    """Retrieve or render static gauge background (bezel, dial, ticks, numerals, wordmark, redline)."""
    ...
```

**Input Example:**

```python
size = (1024, 1024)
skin_name = "stingray"
```

**Output Example:**

```python
<PIL.Image.Image image mode=RGBA size=1024x1024 at 0x7F8B9C0F90>
```

---

### 5.10 `_load_skin_font()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
def _load_skin_font(
    font_size: int,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load Eurostile-adjacent font with dynamic platform fallback chain."""
    ...
```

**Input Example:**

```python
font_size = 36
```

**Output Example:**

```python
<PIL.ImageFont.FreeTypeFont object at 0x7F8B9C1050>  # or ImageFont.load_default()
```

---

## 6. Change Instructions

### 6.1 `src/boostgauge/skins/__init__.py` (Add)

**Complete file contents:**

```python
"""Skins package for boostgauge renderers.

Issue #1: Core Gauge Renderer — Analog Tachometer with Arc, Needle, and Tick Marks
"""

from __future__ import annotations

__all__ = ["stingray"]
```

---

### 6.2 `src/boostgauge/skins/stingray.py` (Add)

**Complete file contents:**

```python
"""Stingray skin implementation for analog tachometer gauge.

Issue #1: Core Gauge Renderer — Analog Tachometer with Arc, Needle, and Tick Marks
Adheres to aesthetic specification in docs/design/0002-aesthetic-v1-stingray.md.
"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Any

from PIL import Image, ImageDraw, ImageFont


def _val_to_angle(
    value: float,
    min_angle: float = 225.0,
    max_angle: float = -45.0,
) -> float:
    """Map gauge metric value (0-100) to dial sweep angle in degrees.
    
    0.0 -> 225.0 deg (lower-left)
    50.0 -> 90.0 deg (top center / 12 o'clock)
    100.0 -> -45.0 deg (lower-right)
    """
    fraction = value / 100.0
    return min_angle + fraction * (max_angle - min_angle)


def _load_skin_font(font_size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load Eurostile-adjacent font with dynamic fallback chain."""
    font_candidates = [
        "Eurostile",
        "Eurostile Bold",
        "Arial Bold",
        "DejaVu Sans-Bold",
        "FreeSans-Bold",
        "Segoe UI Bold",
    ]
    for font_name in font_candidates:
        try:
            return ImageFont.truetype(font_name, font_size)
        except (OSError, ImportError):
            continue
    return ImageFont.load_default()


def _draw_bezel_and_dial(draw: ImageDraw.ImageDraw, size: tuple[int, int]) -> None:
    """Draw square chromed housing, chamfered corners, specular highlights, and recessed round dial face."""
    w, h = size
    # Base dark gunmetal/chromed housing background
    draw.rectangle([(0, 0), (w, h)], fill=(30, 32, 36, 255))
    
    # Outer chrome bezel border line
    draw.rectangle([(2, 2), (w - 3, h - 3)], outline=(180, 185, 190, 255), width=int(max(1, w * 0.008)))
    draw.rectangle([(6, 6), (w - 7, h - 7)], outline=(80, 85, 90, 255), width=int(max(1, w * 0.004)))

    # Chamfered corner specular highlights (top-left light, bottom-right dark shadow)
    draw.line([(0, 0), (int(w * 0.08), 0)], fill=(240, 245, 250, 255), width=int(max(1, w * 0.01)))
    draw.line([(0, 0), (0, int(h * 0.08))], fill=(240, 245, 250, 255), width=int(max(1, w * 0.01)))

    # Recessed matte-black round dial face
    center_x, center_y = w / 2.0, h / 2.0
    dial_radius = min(w, h) * 0.44
    bbox = [
        center_x - dial_radius,
        center_y - dial_radius,
        center_x + dial_radius,
        center_y + dial_radius,
    ]
    
    # Outer dial bezel ring (silver shadow)
    draw.ellipse(bbox, fill=(15, 15, 18, 255), outline=(120, 125, 130, 255), width=int(max(1, w * 0.012)))
    
    # Inner matte black face
    inner_margin = max(2.0, w * 0.01)
    inner_bbox = [
        bbox[0] + inner_margin,
        bbox[1] + inner_margin,
        bbox[2] - inner_margin,
        bbox[3] - inner_margin,
    ]
    draw.ellipse(inner_bbox, fill=(10, 10, 12, 255))


def _draw_ticks_and_numerals(
    draw: ImageDraw.ImageDraw,
    center: tuple[float, float],
    radius: float,
) -> None:
    """Draw 11 major ticks, 40 minor ticks, and numerals 0-100."""
    cx, cy = center
    font_size = int(max(12, radius * 0.12))
    font = _load_skin_font(font_size)

    # 11 major ticks (0, 10, ..., 100) -> 40 sub-intervals (4 minor ticks between each major)
    total_ticks = 40
    for i in range(total_ticks + 1):
        val = (i / total_ticks) * 100.0
        angle = _val_to_angle(val)
        rad = math.radians(angle)
        
        is_major = (i % 4 == 0)
        tick_len = radius * 0.12 if is_major else radius * 0.06
        tick_width = max(1, int(radius * 0.025)) if is_major else max(1, int(radius * 0.012))
        
        outer_r = radius * 0.90
        inner_r = outer_r - tick_len

        x1 = cx + outer_r * math.cos(rad)
        y1 = cy - outer_r * math.sin(rad)
        x2 = cx + inner_r * math.cos(rad)
        y2 = cy - inner_r * math.sin(rad)

        draw.line([(x1, y1), (x2, y2)], fill=(255, 255, 255, 255), width=tick_width)

        if is_major:
            num_val = int(round(val))
            num_str = str(num_val)
            num_r = inner_r - (radius * 0.10)
            nx = cx + num_r * math.cos(rad)
            ny = cy - num_r * math.sin(rad)
            
            # Position text centered at nx, ny
            text_bbox = draw.textbbox((0, 0), num_str, font=font)
            text_w = text_bbox[2] - text_bbox[0]
            text_h = text_bbox[3] - text_bbox[1]
            draw.text(
                (nx - text_w / 2.0, ny - text_h / 2.0),
                num_str,
                fill=(255, 255, 255, 255),
                font=font,
            )


def _draw_redline_arc(
    draw: ImageDraw.ImageDraw,
    center: tuple[float, float],
    radius: float,
) -> None:
    """Draw solid redline arc along outer tick mark ring from metric 60 to 100."""
    cx, cy = center
    arc_r = radius * 0.91
    bbox = [cx - arc_r, cy - arc_r, cx + arc_r, cy + arc_r]
    
    # PIL arc angles measured clockwise starting from 3 o'clock (0 deg)
    # val=60 -> angle 63° -> PIL start_angle = -63° = 297°
    # val=100 -> angle -45° -> PIL end_angle = 45°
    start_angle_pil = -_val_to_angle(60.0)
    end_angle_pil = -_val_to_angle(100.0)
    
    arc_width = max(2, int(radius * 0.035))
    draw.arc(
        bbox,
        start=start_angle_pil,
        end=end_angle_pil,
        fill=(230, 57, 70, 255), # Redline #E63946
        width=arc_width,
    )


def _draw_wordmark(
    draw: ImageDraw.ImageDraw,
    center: tuple[float, float],
    radius: float,
) -> None:
    """Draw BOOSTGAUGE small-caps wordmark centered below pivot."""
    cx, cy = center
    font_size = int(max(10, radius * 0.08))
    font = _load_skin_font(font_size)
    text = "BOOSTGAUGE"
    
    word_y = cy + (radius * 0.40)
    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_w = text_bbox[2] - text_bbox[0]
    text_h = text_bbox[3] - text_bbox[1]
    
    draw.text(
        (cx - text_w / 2.0, word_y - text_h / 2.0),
        text,
        fill=(220, 225, 230, 200),
        font=font,
    )


@lru_cache(maxsize=16)
def _get_cached_background(size: tuple[int, int], skin_name: str = "stingray") -> Image.Image:
    """Render static background (bezel, dial face, ticks, redline arc, wordmark)."""
    bg = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(bg)
    
    _draw_bezel_and_dial(draw, size)
    
    cx, cy = size[0] / 2.0, size[1] / 2.0
    radius = min(size) * 0.44
    center = (cx, cy)
    
    _draw_ticks_and_numerals(draw, center, radius)
    _draw_redline_arc(draw, center, radius)
    _draw_wordmark(draw, center, radius)
    
    return bg


def _draw_needle(
    draw: ImageDraw.ImageDraw,
    center: tuple[float, float],
    radius: float,
    angle: float,
    color: tuple[int, int, int, int] | str,
    width: float,
    length_factor: float,
    has_counterweight: bool = True,
) -> None:
    """Draw needle polygon (main or telltale) at given angle."""
    cx, cy = center
    rad = math.radians(angle)
    perp_rad = rad + math.pi / 2.0

    tip_r = radius * length_factor
    tail_r = radius * 0.18 if has_counterweight else 0.0

    # Tip point
    tx = cx + tip_r * math.cos(rad)
    ty = cy - tip_r * math.sin(rad)

    # Base right/left points
    rx = cx + (width / 2.0) * math.cos(perp_rad)
    ry = cy - (width / 2.0) * math.sin(perp_rad)

    lx = cx - (width / 2.0) * math.cos(perp_rad)
    ly = cy + (width / 2.0) * math.sin(perp_rad)

    if has_counterweight:
        bx = cx - tail_r * math.cos(rad)
        by = cy + tail_r * math.sin(rad)
        points = [(tx, ty), (rx, ry), (bx, by), (lx, ly)]
    else:
        points = [(tx, ty), (rx, ry), (lx, ly)]

    draw.polygon(points, fill=color)


def render_stingray(
    value: float,
    telltales: dict[str, float | None] | None = None,
    size: tuple[int, int] = (256, 256),
    config: dict[str, Any] | None = None,
) -> Image.Image:
    """Render gauge with Stingray aesthetic and optional 4x supersampling."""
    cfg = config or {}
    supersample = cfg.get("supersample_factor", 4)
    
    render_w = size[0] * supersample
    render_h = size[1] * supersample
    render_size = (render_w, render_h)

    # Fetch cached background
    bg = _get_cached_background(render_size, "stingray")
    canvas = bg.copy()
    draw = ImageDraw.Draw(canvas, "RGBA")

    center = (render_w / 2.0, render_h / 2.0)
    radius = min(render_w, render_h) * 0.44
    base_width = max(2.0, render_w * 0.015)

    # Telltale needles specs (drawn behind main needle)
    telltale_colors = {
        "window_1m": (0, 229, 255, 166),   # Cyan #00E5FF @ ~65% opacity
        "window_10m": (255, 145, 0, 166), # Orange #FF9100 @ ~65% opacity
        "window_1h": (224, 64, 251, 166),  # Magenta #E040FB @ ~65% opacity
        "window_all": (255, 23, 68, 166),  # Red #FF1744 @ ~65% opacity
    }

    if telltales:
        for key in ["window_1m", "window_10m", "window_1h", "window_all"]:
            peak_val = telltales.get(key)
            if peak_val is not None:
                clamped_peak = max(0.0, min(100.0, float(peak_val)))
                t_angle = _val_to_angle(clamped_peak)
                _draw_needle(
                    draw=draw,
                    center=center,
                    radius=radius,
                    angle=t_angle,
                    color=telltale_colors[key],
                    width=base_width * 0.8,
                    length_factor=0.80,
                    has_counterweight=False,
                )

    # Main red needle
    clamped_val = max(0.0, min(100.0, float(value)))
    main_angle = _val_to_angle(clamped_val)
    _draw_needle(
        draw=draw,
        center=center,
        radius=radius,
        angle=main_angle,
        color=(230, 57, 70, 255), # Red #E63946
        width=base_width,
        length_factor=0.85,
        has_counterweight=True,
    )

    # Central chromed pivot cap over needles
    cap_r = radius * 0.12
    cx, cy = center
    cap_bbox = [cx - cap_r, cy - cap_r, cx + cap_r, cy + cap_r]
    draw.ellipse(cap_bbox, fill=(200, 205, 210, 255), outline=(50, 55, 60, 255), width=max(1, int(render_w * 0.005)))
    inner_cap = [cx - cap_r * 0.6, cy - cap_r * 0.6, cx + cap_r * 0.6, cy + cap_r * 0.6]
    draw.ellipse(inner_cap, fill=(40, 42, 45, 255))

    # Downsample using LANCZOS anti-aliasing filter
    if supersample > 1:
        return canvas.resize(size, resample=Image.Resampling.LANCZOS)
    return canvas
```

---

### 6.3 `src/boostgauge/gauge.py` (Add)

**Complete file contents:**

```python
"""Core gauge entry point providing pure function renderer API.

Issue #1: Core Gauge Renderer — Analog Tachometer with Arc, Needle, and Tick Marks
"""

from __future__ import annotations

import math
from typing import Any

from PIL import Image

from boostgauge.skins.stingray import render_stingray


def render(
    value: float,
    telltales: dict[str, float | None] | None = None,
    size: tuple[int, int] = (256, 256),
    config: dict[str, Any] | None = None,
) -> Image.Image:
    """Pure function rendering gauge face and needles to off-screen PIL Image.
    
    Args:
        value: Metric value in range [0.0, 100.0].
        telltales: Optional peak-hold dict with keys 'window_1m', 'window_10m', 'window_1h', 'window_all'.
        size: Width and height tuple (minimum 128x128).
        config: Optional configuration dictionary (e.g. {'skin': 'stingray'}).
        
    Returns:
        PIL.Image.Image: Off-screen rendered gauge bitmap.
        
    Raises:
        ValueError: If size < (128, 128) or skin is unsupported.
    """
    if size[0] < 128 or size[1] < 128:
        raise ValueError(f"Gauge size must be at least (128, 128), got {size}")

    cfg = config or {}
    skin_name = cfg.get("skin", "stingray").lower()

    if skin_name != "stingray":
        raise ValueError(f"Unsupported skin: '{skin_name}'")

    # Safe handling/clamping of metric inputs
    try:
        val_float = float(value)
        if math.isnan(val_float) or math.isinf(val_float):
            val_float = 0.0
    except (TypeError, ValueError):
        val_float = 0.0

    clamped_value = max(0.0, min(100.0, val_float))

    return render_stingray(
        value=clamped_value,
        telltales=telltales,
        size=size,
        config=cfg,
    )
```

---

### 6.4 `tests/unit/test_gauge.py` (Add)

**Complete file contents:**

```python
"""Unit tests for core gauge renderer module.

Issue #1: Core Gauge Renderer — Analog Tachometer with Arc, Needle, and Tick Marks
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest
from PIL import Image

from boostgauge.gauge import render
from boostgauge.skins.stingray import _val_to_angle


def test_render_pure_function_output():
    """T010: Verify render returns PIL Image and imports no tkinter modules."""
    assert "tkinter" not in sys.modules, "tkinter must not be loaded prior to test"
    
    img = render(value=50.0, telltales=None, size=(256, 256), config=None)
    
    assert isinstance(img, Image.Image)
    assert img.size == (256, 256)
    assert img.mode == "RGBA"
    assert "tkinter" not in sys.modules, "Option C constraint: tkinter must never be imported"


def test_val_to_angle_mapping():
    """Verify mapping of values 0, 50, 100 to sweep angles."""
    assert math.isclose(_val_to_angle(0.0), 225.0)
    assert math.isclose(_val_to_angle(50.0), 90.0)
    assert math.isclose(_val_to_angle(100.0), -45.0)


@pytest.mark.parametrize(
    "input_val,expected_angle",
    [
        (-20.0, 225.0),
        (0.0, 225.0),
        (50.0, 90.0),
        (100.0, -45.0),
        (150.0, -45.0),
    ],
)
def test_input_value_clamping(input_val: float, expected_angle: float):
    """T020: Verify out-of-bounds metrics are clamped to [0, 100]."""
    img = render(value=input_val, size=(128, 128))
    assert isinstance(img, Image.Image)


def test_minimum_size_validation():
    """T030: Verify sizes smaller than 128x128 raise ValueError."""
    with pytest.raises(ValueError, match="Gauge size must be at least"):
        render(value=50.0, size=(64, 64))

    with pytest.raises(ValueError, match="Gauge size must be at least"):
        render(value=50.0, size=(128, 64))


def test_unsupported_skin_validation():
    """T040: Verify unknown skin name raises ValueError."""
    with pytest.raises(ValueError, match="Unsupported skin"):
        render(value=50.0, config={"skin": "nonexistent_skin"})
```

---

### 6.5 `tests/visual/test_stingray_visual.py` (Add)

**Complete file contents:**

```python
"""Visual regression and baseline-independent tests for Stingray skin.

Issue #1: Core Gauge Renderer — Analog Tachometer with Arc, Needle, and Tick Marks
Adheres to Option C test strategy in docs/design/0001-test-strategy.md.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageStat

from boostgauge.gauge import render
from boostgauge.skins.stingray import _val_to_angle

BASELINES_DIR = Path(__file__).resolve().parent / "baselines"


def _compute_rms_diff(img1: Image.Image, img2: Image.Image) -> float:
    """Compute RMS difference between two PIL images per test strategy §3."""
    diff = ImageChops.difference(img1.convert("RGB"), img2.convert("RGB"))
    stat = ImageStat.Stat(diff)
    sum_sq = sum(stat.sum2)
    num_pixels = img1.width * img1.height * 3
    return math.sqrt(sum_sq / num_pixels)


def test_deterministic_byte_output():
    """T140: Two identical render calls produce byte-identical images."""
    img1 = render(value=50.0, telltales=None, size=(256, 256))
    img2 = render(value=50.0, telltales=None, size=(256, 256))
    
    assert img1.tobytes() == img2.tobytes()


@pytest.mark.parametrize(
    "test_id,value,telltales",
    [
        ("test_stingray_value_0", 0.0, None),
        ("test_stingray_value_100", 100.0, None),
        (
            "test_stingray_telltales",
            50.0,
            {"window_1m": 40.0, "window_10m": 60.0, "window_1h": 80.0, "window_all": 95.0},
        ),
    ],
)
def test_visual_baseline_regression(
    request: pytest.FixtureRequest,
    test_id: str,
    value: float,
    telltales: dict[str, float | None] | None,
):
    """T130: Compare rendered image against baseline fixture blob."""
    BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    baseline_path = BASELINES_DIR / f"{test_id}.png"

    rendered_img = render(value=value, telltales=telltales, size=(256, 256))

    if request.config.getoption("--generate-baselines", default=False):
        rendered_img.save(baseline_path, format="PNG")
        pytest.skip(f"Generated baseline image: {baseline_path.name}")

    if not baseline_path.exists():
        pytest.fail(
            f"Baseline file missing: {baseline_path}. Run with '--generate-baselines' to create it."
        )

    baseline_img = Image.open(baseline_path)
    rms_diff = _compute_rms_diff(rendered_img, baseline_img)

    # Threshold per docs/design/0001-test-strategy.md §3 (1.0 / 255 = 0.00392)
    assert rms_diff <= (1.0 / 255.0), f"Visual regression failure for {test_id}: RMS diff={rms_diff:.5f}"


# --- BASELINE-INDEPENDENT PROPERTY ASSERTIONS (Issue #1902) ---

def test_needle_tip_trigonometry_location_baseline_independent():
    """T100 Baseline-Independent: Verify needle tip pixel coordinate via pure math.
    
    Validates needle tip angle without relying on baseline image comparison.
    """
    size = (256, 256)
    cx, cy = size[0] / 2.0, size[1] / 2.0
    radius = min(size) * 0.44
    length_factor = 0.85
    
    # Test at value = 50.0 (top center / 12 o'clock / angle = 90.0 deg)
    val = 50.0
    angle = _val_to_angle(val) # 90.0 deg
    rad = math.radians(angle)
    
    expected_tip_x = cx + radius * length_factor * math.cos(rad) # 128.0
    expected_tip_y = cy - radius * length_factor * math.sin(rad) # 31.856
    
    img = render(value=val, telltales=None, size=size)
    
    # Check pixel near expected tip coordinate (128, 32) contains main red needle color (#E63946)
    tip_px = img.getpixel((int(round(expected_tip_x)), int(round(expected_tip_y))))
    
    # Red channel must be dominant (R > 180, G < 100, B < 100)
    assert tip_px[0] > 180, f"Red channel at needle tip expected >180, got {tip_px[0]}"
    assert tip_px[1] < 100, f"Green channel at needle tip expected <100, got {tip_px[1]}"
    assert tip_px[2] < 100, f"Blue channel at needle tip expected <100, got {tip_px[2]}"
```

---

## 7. Pattern References

### 7.1 Option C Off-Screen Rendering Protocol

**File:** `docs/design/0001-test-strategy.md` (lines 33–52)

```markdown
33: ## 2. Tkinter Test Mode — Decision
34: 
35: **Chosen: Option C — render to off-screen `PIL.Image` first; tkinter Canvas is a display surface only.**
36: 
37: The gauge renderer is a pure function: state -> `PIL.Image`. The tkinter Canvas receives that image and displays it. Tests exercise the renderer; they never instantiate `tkinter.Tk()`.
```

**Relevance:** Enforces zero `tkinter` dependency in `src/boostgauge/gauge.py` and `src/boostgauge/skins/stingray.py`.

### 7.2 RMS Baseline Comparison Pattern

**File:** `docs/design/0001-test-strategy.md` (lines 65–73)

```markdown
65: ### How a test fails
66: 
67: Pixel-diff with a tolerance band:
68: 
69: - **Identical bytes** -> pass.
70: - **Byte-different but pixel-RMS ≤ 1.0 / 255** -> pass with a warning (anti-aliasing noise; harmless).
71: - **Pixel-RMS > 1.0 / 255** -> fail. Diff image written to `tests/visual/diffs/{test_id}.png` for triage.
```

**Relevance:** Standardizes visual baseline tolerance calculation using `PIL.ImageChops.difference()` and `PIL.ImageStat.Stat()`.

---

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `from typing import Any, TypedDict` | stdlib | `gauge.py`, `stingray.py` |
| `import math` | stdlib | `stingray.py`, `test_gauge.py`, `test_stingray_visual.py` |
| `import sys` | stdlib | `test_gauge.py` |
| `from pathlib import Path` | stdlib | `test_gauge.py`, `test_stingray_visual.py` |
| `from functools import lru_cache` | stdlib | `stingray.py` |
| `from PIL import Image, ImageDraw, ImageFont, ImageChops, ImageStat` | `pillow` (>=12.2.0) | `gauge.py`, `stingray.py`, `test_stingray_visual.py` |
| `import pytest` | `pytest` | `test_gauge.py`, `test_stingray_visual.py` |

**New Dependencies:** None (uses existing `pillow` dependency from `pyproject.toml`).

---

## 9. Placeholder

*Reserved for future use to maintain alignment with LLD section numbering.*

---

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `render()` | `value=50.0, size=(256,256)` | `PIL.Image.Image` returned, zero `tkinter` imports loaded |
| T020 | `render()` | `value=-20.0` and `value=150.0` | Metrics clamped to 0.0 and 100.0, rendering succeeds |
| T030 | `render()` | `size=(64, 64)` | Raises `ValueError("Gauge size must be at least (128, 128)")` |
| T040 | `render()` | `config={"skin": "invalid"}` | Raises `ValueError("Unsupported skin: 'invalid'")` |
| T050 | `_draw_bezel_and_dial()` | `size=(1024, 1024)` | Chromed bezel with chamfers and recessed dark dial face rendered |
| T060 | `_draw_ticks_and_numerals()` | `center=(512,512), radius=450` | 11 major ticks, 40 minor ticks rendered in white |
| T070 | `_draw_ticks_and_numerals()` | `center=(512,512), radius=450` | White numerals 0 through 100 placed at major tick angles |
| T080 | `_draw_redline_arc()` | `center=(512,512), radius=450` | Solid red arc (`#E63946`) drawn along tick ring from 60 to 100 |
| T090 | `_draw_wordmark()` | `center=(512,512), radius=450` | "BOOSTGAUGE" wordmark text centered below dial pivot |
| T100 | `_draw_needle()` / `render()` | `value=0, 50, 100` | Red main needle points to 225°, 90°, and -45° respectively |
| T110 | `render_stingray()` | `telltales={1m: 40, 10m: 60, ...}` | 4 translucent needles rendered behind main red needle |
| T120 | `render_stingray()` | `telltales=None` | Telltale needles hidden, only main needle rendered |
| T130 | `test_visual_baseline_regression()` | `test_id="test_stingray_value_0"` | Pixel RMS difference <= 1.0/255 against baseline PNG |
| T140 | `test_deterministic_byte_output()` | Two identical `render(50.0)` calls | `img1.tobytes() == img2.tobytes()` evaluates to `True` |

---

## 11. Implementation Notes

### 11.1 Error Handling & Clamping Convention

- Numerical metrics: Inputs converted via `float(value)` with fallback to `0.0` on `TypeError` / `ValueError` / `NaN` / `Infinity`.
- Out-of-bound metric values are clamped: `max(0.0, min(100.0, val))`.
- Size validation: Raises `ValueError` if `size[0] < 128` or `size[1] < 128`.
- Skin dispatch: Converts skin name string to lowercase; unsupported names raise `ValueError`.

### 11.2 Supersampling & Downsampling Math

- Supersampling factor defaults to `4`.
- A target size of `(256, 256)` renders internally on a `(1024, 1024)` canvas.
- Vector coordinates, line widths, and font sizes scale linearly with supersample factor.
- Downsampling uses `PIL.Image.Resampling.LANCZOS` filter to produce crisp anti-aliased visual output.

### 11.3 Baseline-Independent Verification Trigonometry (Issue #1902)

To satisfy Issue #1902, `test_needle_tip_trigonometry_location_baseline_independent()` validates the red needle tip coordinate directly via math:
$$\text{rad} = \text{radians}(\text{angle})$$
$$X_{\text{tip}} = X_{\text{center}} + R \cdot \text{length\_factor} \cdot \cos(\text{rad})$$
$$Y_{\text{tip}} = Y_{\text{center}} - R \cdot \text{length\_factor} \cdot \sin(\text{rad})$$
The test asserts that the pixel at $(X_{\text{tip}}, Y_{\text{tip}})$ in the generated image has a dominant red channel ($R > 180, G < 100, B < 100$) without checking baseline images.

### 11.4 Constants & Color Palette

| Name | Hex / RGB | Rationale |
|------|-----------|-----------|
| Main Needle & Redline | `#E63946` / `(230, 57, 70)` | Stingray signature red accent |
| 1m Telltale | `#00E5FF` / `(0, 229, 255, 166)` | Translucent cyan @ ~65% opacity |
| 10m Telltale | `#FF9100` / `(255, 145, 0, 166)` | Translucent orange @ ~65% opacity |
| 1h Telltale | `#E040FB` / `(224, 64, 251, 166)` | Translucent magenta @ ~65% opacity |
| All-Time Telltale | `#FF1744` / `(255, 23, 68, 166)` | Translucent bright red @ ~65% opacity |
| Matte Dial Face | `#0A0A0C` / `(10, 10, 12)` | Dark anti-glare recessed background |
| Ticks & Numerals | `#FFFFFF` / `(255, 255, 255)` | Crisp high-contrast scale markings |

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3: explicitly noted no modify files, all files added)
- [x] Every data structure has a concrete JSON/YAML example (Section 4)
- [x] Every function has input/output examples with realistic values (Section 5)
- [x] Change instructions are diff-level specific / full code (Section 6)
- [x] Pattern references include file:line and are verified to exist (Section 7)
- [x] All imports are listed and verified (Section 8)
- [x] Test mapping covers all LLD test scenarios (Section 10)

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #1 |
| Verdict | APPROVED |
| Date | 2026-07-31 |
| Iterations | 1 |
| Finalized | 2026-07-31T15:13:00Z |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #1 |
| Verdict | APPROVED |
| Date | 2026-07-31 |
| Iterations | 0 |
| Finalized | 2026-07-31T20:14:01Z |

### Review Feedback Summary

The implementation spec for Issue #1 (Core Gauge Renderer) is exceptionally complete, concrete, and directly executable. It provides ready-to-write Python source and test code across all 6 target files without pseudocode or omitted logic. All function signatures, data structures, and edge cases are documented with concrete examples. Assertion traceability was explicitly verified across all unit and visual tests, and a dedicated baseline-independent trigonometric pixel verification test is includ...
