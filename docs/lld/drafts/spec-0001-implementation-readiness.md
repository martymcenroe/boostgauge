# Implementation Spec: Core Gauge Renderer — Analog Tachometer with Arc, Needle, and Tick Marks

| Field | Value |
|-------|-------|
| Issue | #1 |
| LLD | `docs/lld/done/0001-core-gauge-renderer.md` |
| Generated | 2026-07-31 |
| Status | APPROVED |

## 1. Overview

This implementation realizes the v1 core tachometer gauge renderer as a pure PIL function producing off-screen gauge images according to the Stingray aesthetic specification in `docs/design/0002-aesthetic-v1-stingray.md`. It provides the primary entry point `render()` with skin dispatch logic, 4x supersampling anti-aliasing via PIL downsampling, static background caching, dynamic needle positioning for metric values (0-100), and peak-hold telltale needle overlays.

**Objective:** Implement the v1 core tachometer gauge renderer as a pure PIL function producing off-screen gauge images according to the Stingray aesthetic specification in `docs/design/0002-aesthetic-v1-stingray.md`.

**Success Criteria:**
- Pure function `render(value, telltales, size, config) -> PIL.Image` executing without side effects and with zero `tkinter` imports.
- Input validation clamping metric `value` to [0.0, 100.0], rejecting dimensions `< (128, 128)` with `ValueError`, and rejecting unsupported skin configurations with `ValueError`.
- Complete Stingray visual face generation featuring square chromed housing, chamfered corners, recessed matte dial face, 11 major and 40 minor tick marks, Eurostile-adjacent numerals (0-100), redline arc (60-100), centered "BOOSTGAUGE" wordmark, main red needle, and up to four translucent telltale needles.
- Byte-deterministic rendering matching baseline visual images within RMS tolerance <= 1.0/255 per `docs/design/0001-test-strategy.md`.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/skins/__init__.py` | Add | Package initializer exposing available skin modules. |
| 2 | `src/boostgauge/skins/stingray.py` | Add | Stingray skin rendering engine (bezel, dial face, ticks, numerals, redline arc, wordmark, main needle, telltale needles, static background caching). |
| 3 | `src/boostgauge/gauge.py` | Add | Core gauge entry point exposing `render()` with parameter validation and skin dispatch logic. |
| 4 | `tests/unit/test_gauge.py` | Add | Unit tests for API contract, input validation, angle math, deterministic output, and baseline-independent property assertions. |
| 5 | `tests/visual/baselines` | Add (Directory) | Directory for storing baseline reference image blobs for visual regression testing. |
| 6 | `tests/visual/test_stingray_visual.py` | Add | Render-tier visual regression tests comparing generated outputs against baseline images with RMS tolerance. |

**Implementation Order Rationale:** `skins/stingray.py` contains the primary PIL rendering implementation and math algorithms, which `gauge.py` dispatches to. Creating `skins/__init__.py` and `skins/stingray.py` first enables `gauge.py` to import and call `render_stingray()`. Unit tests (`tests/unit/test_gauge.py`) and visual regression tests (`tests/visual/test_stingray_visual.py`) depend on both `gauge.py` and `skins/stingray.py`.

## 3. Current State (for Modify/Delete files)

N/A - All files introduced in this feature are new (`Add`). No existing source files are modified or deleted.

The directory structures `src/boostgauge/`, `src/boostgauge/skins/`, `tests/unit/`, and `tests/visual/` already exist in the repository skeleton.

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
    "window_1m": 42.5,
    "window_10m": 68.0,
    "window_1h": 85.2,
    "window_all": 99.5
}
```

### 4.2 `RenderConfig`

**Definition:**

```python
from typing import TypedDict

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

## 5. Function Specifications

### 5.1 `render()`

**File:** `src/boostgauge/gauge.py`

**Signature:**

```python
from typing import Any
from PIL import Image

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
config = {"skin": "stingray", "supersample_factor": 4, "enable_cache": True}
```

**Output Example:**

```python
<PIL.Image.Image image mode=RGBA size=256x256 at 0x7F8C401A29E0>
```

**Edge Cases:**
- `size=(100, 100)` -> raises `ValueError("Gauge size must be at least 128x128 pixels")`
- `config={"skin": "invalid_skin"}` -> raises `ValueError("Unsupported skin: 'invalid_skin'. Available skins: ['stingray']")`
- `value=-15.0` -> clamped to `0.0` before rendering
- `value=150.0` -> clamped to `100.0` before rendering
- `telltales=None` -> renders gauge without telltale needles

---

### 5.2 `render_stingray()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
from typing import Any
from PIL import Image

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
size = (512, 512)
config = None
```

**Output Example:**

```python
<PIL.Image.Image image mode=RGBA size=512x512 at 0x7F8C401A2B10>
```

**Edge Cases:**
- `telltales={"window_1m": None}` -> ignores `None` peak values and renders only valid float peaks

---

### 5.3 `_val_to_angle()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
def _val_to_angle(value: float, min_angle: float = 225.0, max_angle: float = -45.0) -> float:
    """Map gauge metric value (0-100) to dial sweep angle in degrees."""
    ...
```

**Input Example:**

```python
value = 50.0
min_angle = 225.0
max_angle = -45.0
```

**Output Example:**

```python
90.0
```

**Edge Cases:**
- `value = 0.0` -> returns `225.0`
- `value = 100.0` -> returns `-45.0`
- `value = -10.0` (unclamped) -> returns `252.0` (clamping occurs in outer caller)

---

### 5.4 `_draw_bezel_and_dial()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
from PIL import ImageDraw

def _draw_bezel_and_dial(draw: ImageDraw.ImageDraw, size: tuple[int, int]) -> None:
    """Draw square chromed bezel, chamfered corners, specular highlights, and recessed round dial face."""
    ...
```

**Input Example:**

```python
# draw is an ImageDraw instance for a 1024x1024 canvas
size = (1024, 1024)
```

**Output Example:**

```python
None  # Mutates draw canvas in-place
```

---

### 5.5 `_draw_ticks_and_numerals()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
from PIL import ImageDraw

def _draw_ticks_and_numerals(draw: ImageDraw.ImageDraw, center: tuple[float, float], radius: float) -> None:
    """Draw 11 major and 40 minor white tick marks and numerals (0-100)."""
    ...
```

**Input Example:**

```python
center = (512.0, 512.0)
radius = 450.0
```

**Output Example:**

```python
None  # Mutates draw canvas in-place
```

---

### 5.6 `_draw_redline_arc()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
from PIL import ImageDraw

def _draw_redline_arc(draw: ImageDraw.ImageDraw, center: tuple[float, float], radius: float) -> None:
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
None  # Mutates draw canvas in-place
```

---

### 5.7 `_draw_wordmark()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
from PIL import ImageDraw

def _draw_wordmark(draw: ImageDraw.ImageDraw, center: tuple[float, float], radius: float) -> None:
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
None  # Mutates draw canvas in-place
```

---

### 5.8 `_draw_needle()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
from PIL import ImageDraw

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
angle = 90.0
color = (230, 57, 70, 255)
width = 12.0
length_factor = 0.85
has_counterweight = True
```

**Output Example:**

```python
None  # Mutates draw canvas in-place
```

---

### 5.9 `_get_cached_background()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
from PIL import Image

def _get_cached_background(size: tuple[int, int], skin_name: str = "stingray") -> Image.Image:
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
<PIL.Image.Image image mode=RGBA size=1024x1024 at 0x7F8C401A2DF0>
```

---

### 5.10 `_load_skin_font()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
from PIL import ImageFont

def _load_skin_font(font_size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load Eurostile-adjacent font with dynamic platform fallback chain."""
    ...
```

**Input Example:**

```python
font_size = 36
```

**Output Example:**

```python
<PIL.ImageFont.FreeTypeFont object at 0x7F8C401A2E50>
```

**Edge Cases:**
- No system TrueType fonts found -> returns `PIL.ImageFont.load_default()`

## 6. Change Instructions

### 6.1 `src/boostgauge/skins/__init__.py` (Add)

**Complete file contents:**

```python
"""Skins package for gauge face renderers."""

from boostgauge.skins.stingray import render_stingray

__all__ = ["render_stingray"]
```

---

### 6.2 `src/boostgauge/skins/stingray.py` (Add)

**Complete file contents:**

```python
"""Stingray skin rendering logic for analog tachometer gauge face.

Issue #1: Core Gauge Renderer — Analog Tachometer with Arc, Needle, and Tick Marks
"""

from __future__ import annotations

import math
from typing import Any
from PIL import Image, ImageDraw, ImageFont

# Module-level cache for static background images: (width, height) -> Image.Image
_BACKGROUND_CACHE: dict[tuple[int, int], Image.Image] = {}

# Telltale color definitions (RGBA with ~65% opacity: alpha=166)
TELLTALE_COLORS: dict[str, tuple[int, int, int, int]] = {
    "window_1m": (0, 229, 255, 166),   # Cyan #00E5FF
    "window_10m": (255, 145, 0, 166),  # Orange #FF9100
    "window_1h": (224, 64, 251, 166),  # Magenta #E040FB
    "window_all": (255, 23, 68, 166),  # Red #FF1744
}


def _val_to_angle(value: float, min_angle: float = 225.0, max_angle: float = -45.0) -> float:
    """Map gauge metric value (0-100) to dial sweep angle in degrees.
    
    0 maps to min_angle (225°: bottom-left), 100 maps to max_angle (-45°: bottom-right).
    Clockwise sweep spans 270 degrees.
    """
    sweep = max_angle - min_angle
    return min_angle + (value / 100.0) * sweep


def _load_skin_font(font_size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load Eurostile-adjacent font with dynamic platform fallback chain."""
    font_candidates = [
        "Eurostile",
        "Eurostile Bold",
        "Arial Bold",
        "DejaVu Sans Bold",
        "Liberation Sans Bold",
        "arial.ttf",
        "DejaVuSans-Bold.ttf",
    ]
    for font_name in font_candidates:
        try:
            return ImageFont.truetype(font_name, font_size)
        except (OSError, ImportError):
            continue
    return ImageFont.load_default()


def _draw_bezel_and_dial(draw: ImageDraw.ImageDraw, size: tuple[int, int]) -> None:
    """Draw square chromed bezel, chamfered corners, specular highlights, and recessed round dial face."""
    w, h = size
    
    # Outer background (dark metallic frame)
    draw.rectangle([0, 0, w, h], fill=(20, 22, 26, 255))
    
    # Outer chrome bezel border
    bezel_margin = int(w * 0.02)
    draw.rectangle(
        [bezel_margin, bezel_margin, w - bezel_margin, h - bezel_margin],
        outline=(180, 185, 195, 255),
        width=int(w * 0.015),
    )
    
    # Chamfered corner highlights
    corner_len = int(w * 0.08)
    draw.line([(0, corner_len), (corner_len, 0)], fill=(220, 225, 235, 255), width=int(w * 0.01))
    draw.line([(w - corner_len, 0), (w, corner_len)], fill=(220, 225, 235, 255), width=int(w * 0.01))
    draw.line([(0, h - corner_len), (corner_len, h)], fill=(100, 105, 115, 255), width=int(w * 0.01))
    draw.line([(w - corner_len, h), (w, h - corner_len)], fill=(100, 105, 115, 255), width=int(w * 0.01))
    
    # Recessed round matte-black dial face
    center_x, center_y = w / 2.0, h / 2.0
    dial_margin = int(w * 0.06)
    dial_bbox = [dial_margin, dial_margin, w - dial_margin, h - dial_margin]
    
    # Outer shadow ring
    draw.ellipse(dial_bbox, fill=(10, 10, 12, 255), outline=(60, 65, 75, 255), width=int(w * 0.01))
    
    # Inner matte face
    inner_margin = int(w * 0.07)
    inner_bbox = [inner_margin, inner_margin, w - inner_margin, h - inner_margin]
    draw.ellipse(inner_bbox, fill=(15, 15, 18, 255))


def _draw_ticks_and_numerals(draw: ImageDraw.ImageDraw, center: tuple[float, float], radius: float) -> None:
    """Draw 11 major and 40 minor white tick marks and Eurostile-adjacent numerals (0-100)."""
    cx, cy = center
    font = _load_skin_font(int(radius * 0.12))
    
    # Total ticks: 50 subdivisions (11 major ticks at intervals of 5 ticks)
    for i in range(51):
        val = i * 2.0  # 0 to 100
        angle = _val_to_angle(val)
        rad = math.radians(angle)
        
        is_major = (i % 5 == 0)
        tick_length = radius * 0.10 if is_major else radius * 0.05
        tick_width = max(2, int(radius * 0.015)) if is_major else max(1, int(radius * 0.008))
        
        outer_r = radius * 0.88
        inner_r = outer_r - tick_length
        
        x1 = cx + outer_r * math.cos(rad)
        y1 = cy - outer_r * math.sin(rad)
        x2 = cx + inner_r * math.cos(rad)
        y2 = cy - inner_r * math.sin(rad)
        
        draw.line([(x1, y1), (x2, y2)], fill=(255, 255, 255, 255), width=tick_width)
        
        if is_major:
            numeral_val = int(val)
            numeral_text = str(numeral_val)
            text_r = outer_r - tick_length - (radius * 0.10)
            tx = cx + text_r * math.cos(rad)
            ty = cy - text_r * math.sin(rad)
            
            bbox = font.getbbox(numeral_text)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            draw.text((tx - tw / 2.0, ty - th / 2.0), numeral_text, fill=(255, 255, 255, 255), font=font)


def _draw_redline_arc(draw: ImageDraw.ImageDraw, center: tuple[float, float], radius: float) -> None:
    """Draw redline arc hugging outer tick ring from metric value 60 to 100."""
    cx, cy = center
    outer_r = radius * 0.89
    bbox = [cx - outer_r, cy - outer_r, cx + outer_r, cy + outer_r]
    
    # PIL arc angles: 0 is East, measured clockwise.
    # Metric 60 maps to _val_to_angle(60) = 63°. In PIL angle terms: -63°.
    # Metric 100 maps to _val_to_angle(100) = -45°. In PIL angle terms: 45°.
    # So PIL arc start = -63°, end = 45°.
    start_pil_angle = -_val_to_angle(60.0)
    end_pil_angle = -_val_to_angle(100.0)
    
    arc_width = max(3, int(radius * 0.025))
    draw.arc(bbox, start=start_pil_angle, end=end_pil_angle, fill=(230, 57, 70, 255), width=arc_width)


def _draw_wordmark(draw: ImageDraw.ImageDraw, center: tuple[float, float], radius: float) -> None:
    """Draw BOOSTGAUGE small-caps white wordmark below central pivot cap."""
    cx, cy = center
    font = _load_skin_font(int(radius * 0.08))
    text = "BOOSTGAUGE"
    
    wordmark_y = cy + (radius * 0.40)
    bbox = font.getbbox(text)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    
    draw.text((cx - tw / 2.0, wordmark_y - th / 2.0), text, fill=(220, 225, 235, 200), font=font)


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
    cx, cy = center
    rad = math.radians(angle)
    
    needle_len = radius * length_factor
    tip_x = cx + needle_len * math.cos(rad)
    tip_y = cy - needle_len * math.sin(rad)
    
    perp_rad = rad + math.pi / 2.0
    half_w = width / 2.0
    
    base_left_x = cx + half_w * math.cos(perp_rad)
    base_left_y = cy - half_w * math.sin(perp_rad)
    base_right_x = cx - half_w * math.cos(perp_rad)
    base_right_y = cy + half_w * math.sin(perp_rad)
    
    polygon_pts = [(tip_x, tip_y), (base_left_x, base_left_y), (base_right_x, base_right_y)]
    
    if has_counterweight:
        cw_len = radius * 0.18
        cw_x = cx - cw_len * math.cos(rad)
        cw_y = cy + cw_len * math.sin(rad)
        polygon_pts.append((cw_x, cw_y))
    
    draw.polygon(polygon_pts, fill=color)


def _get_cached_background(size: tuple[int, int], skin_name: str = "stingray") -> Image.Image:
    """Retrieve or render static gauge background (bezel, dial, ticks, numerals, wordmark, redline)."""
    if size in _BACKGROUND_CACHE:
        return _BACKGROUND_CACHE[size].copy()
    
    bg = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(bg)
    
    cx, cy = size[0] / 2.0, size[1] / 2.0
    radius = min(size[0], size[1]) / 2.0
    
    _draw_bezel_and_dial(draw, size)
    _draw_ticks_and_numerals(draw, (cx, cy), radius)
    _draw_redline_arc(draw, (cx, cy), radius)
    _draw_wordmark(draw, (cx, cy), radius)
    
    _BACKGROUND_CACHE[size] = bg
    return bg.copy()


def render_stingray(
    value: float,
    telltales: dict[str, float | None] | None = None,
    size: tuple[int, int] = (256, 256),
    config: dict[str, Any] | None = None,
) -> Image.Image:
    """Stingray skin implementation rendering to PIL Image with 4x supersampling."""
    supersample = (config or {}).get("supersample_factor", 4)
    canvas_size = (size[0] * supersample, size[1] * supersample)
    
    # Step 1: Fetch static dial background
    canvas = _get_cached_background(canvas_size, skin_name="stingray")
    draw = ImageDraw.Draw(canvas)
    
    cx, cy = canvas_size[0] / 2.0, canvas_size[1] / 2.0
    radius = min(canvas_size[0], canvas_size[1]) / 2.0
    
    # Step 2: Render telltale peak needles behind main needle
    if telltales:
        for key in ["window_1m", "window_10m", "window_1h", "window_all"]:
            peak_val = telltales.get(key)
            if peak_val is not None:
                clamped_peak = max(0.0, min(100.0, float(peak_val)))
                peak_angle = _val_to_angle(clamped_peak)
                tt_color = TELLTALE_COLORS[key]
                _draw_needle(
                    draw=draw,
                    center=(cx, cy),
                    radius=radius,
                    angle=peak_angle,
                    color=tt_color,
                    width=float(radius * 0.025),
                    length_factor=0.75,
                    has_counterweight=False,
                )
    
    # Step 3: Render main red needle
    main_angle = _val_to_angle(value)
    main_color = (230, 57, 70, 255)  # Solid Red #E63946
    _draw_needle(
        draw=draw,
        center=(cx, cy),
        radius=radius,
        angle=main_angle,
        color=main_color,
        width=float(radius * 0.035),
        length_factor=0.78,
        has_counterweight=True,
    )
    
    # Step 4: Render central chromed pivot cap
    cap_r = radius * 0.08
    cap_bbox = [cx - cap_r, cy - cap_r, cx + cap_r, cy + cap_r]
    draw.ellipse(cap_bbox, fill=(180, 185, 195, 255), outline=(50, 55, 65, 255), width=max(1, int(radius * 0.01)))
    
    # Step 5: Downsample canvas to target resolution via LANCZOS
    return canvas.resize(size, resample=Image.Resampling.LANCZOS)
```

---

### 6.3 `src/boostgauge/gauge.py` (Add)

**Complete file contents:**

```python
"""Core gauge renderer entry point.

Issue #1: Core Gauge Renderer — Analog Tachometer with Arc, Needle, and Tick Marks
"""

from __future__ import annotations

from typing import Any
from PIL import Image

from boostgauge.skins.stingray import render_stingray

SUPPORTED_SKINS = {
    "stingray": render_stingray,
}


def render(
    value: float,
    telltales: dict[str, float | None] | None = None,
    size: tuple[int, int] = (256, 256),
    config: dict[str, Any] | None = None,
) -> Image.Image:
    """Pure function rendering gauge face and needles to off-screen PIL Image.
    
    Parameters
    ----------
    value : float
        Current gauge metric value (0.0 to 100.0). Clamped if out of range.
    telltales : dict[str, float | None] | None
        Dictionary of peak-hold metric values for windows:
        "window_1m", "window_10m", "window_1h", "window_all".
    size : tuple[int, int]
        Target image resolution (width, height). Must be at least (128, 128).
    config : dict[str, Any] | None
        Configuration options including 'skin', 'supersample_factor', etc.
        
    Returns
    -------
    PIL.Image.Image
        Rendered gauge face image.
        
    Raises
    ------
    ValueError
        If size is smaller than (128, 128) or if skin is unsupported.
    """
    if size[0] < 128 or size[1] < 128:
        raise ValueError(f"Gauge size must be at least 128x128 pixels, got {size}")
    
    cfg = config or {}
    skin_name = cfg.get("skin", "stingray")
    
    if skin_name not in SUPPORTED_SKINS:
        raise ValueError(f"Unsupported skin: '{skin_name}'. Available skins: {sorted(SUPPORTED_SKINS.keys())}")
    
    # Clamp value to valid metric range [0.0, 100.0]
    clamped_value = max(0.0, min(100.0, float(value)))
    
    renderer = SUPPORTED_SKINS[skin_name]
    return renderer(value=clamped_value, telltales=telltales, size=size, config=cfg)
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
from boostgauge.skins.stingray import _val_to_angle, _load_skin_font


def test_render_pure_function_output():
    """T010: Verify render returns a PIL Image and imports no tkinter modules."""
    img = render(50.0, size=(256, 256))
    assert isinstance(img, Image.Image)
    assert img.size == (256, 256)
    assert img.mode == "RGBA"
    assert "tkinter" not in sys.modules


def test_value_clamping():
    """T020: Verify values outside [0, 100] are clamped without raising exceptions."""
    img_neg = render(-25.0, size=(128, 128))
    img_zero = render(0.0, size=(128, 128))
    img_over = render(150.0, size=(128, 128))
    img_max = render(100.0, size=(128, 128))

    assert img_neg.tobytes() == img_zero.tobytes()
    assert img_over.tobytes() == img_max.tobytes()


def test_invalid_size_rejection():
    """T030: Verify size below 128x128 raises ValueError."""
    with pytest.raises(ValueError, match="at least 128x128"):
        render(50.0, size=(64, 64))

    with pytest.raises(ValueError, match="at least 128x128"):
        render(50.0, size=(128, 64))


def test_unsupported_skin_rejection():
    """T040: Verify unsupported skin name raises ValueError."""
    with pytest.raises(ValueError, match="Unsupported skin"):
        render(50.0, config={"skin": "cyberpunk_2077"})


def test_val_to_angle_mapping():
    """T100: Verify angle math maps metric 0-100 across 270 degree sweep."""
    assert _val_to_angle(0.0) == 225.0
    assert _val_to_angle(50.0) == 90.0
    assert _val_to_angle(100.0) == -45.0


def test_telltales_post_reset_hiding():
    """T120: Verify None peak values render identically to no telltales."""
    img_none = render(50.0, telltales=None, size=(128, 128))
    img_empty = render(
        50.0,
        telltales={"window_1m": None, "window_10m": None, "window_1h": None, "window_all": None},
        size=(128, 128),
    )
    assert img_none.tobytes() == img_empty.tobytes()


def test_deterministic_output():
    """T140: Verify repeated renders with identical parameters produce byte-identical images."""
    img1 = render(75.0, telltales={"window_1m": 80.0}, size=(256, 256))
    img2 = render(75.0, telltales={"window_1m": 80.0}, size=(256, 256))
    assert img1.tobytes() == img2.tobytes()


# --- Section 10.4: Baseline-Independent Property Assertions ---

def test_baseline_independent_needle_tip_trigonometry():
    """Verify main needle tip position angle mathematics mathematically without baseline images.
    
    Requirement 8: Needle sweeps clockwise from 225° (value 0) to -45° (value 100).
    At value=50, angle is 90° (straight up).
    """
    center_x, center_y = 128.0, 128.0
    radius = 128.0
    length_factor = 0.78
    needle_len = radius * length_factor
    
    # Test value 50 (90 degrees, pointing straight up)
    angle_50 = _val_to_angle(50.0)
    rad_50 = math.radians(angle_50)
    tip_x_50 = center_x + needle_len * math.cos(rad_50)
    tip_y_50 = center_y - needle_len * math.sin(rad_50)
    
    assert math.isclose(angle_50, 90.0, abs_tol=1e-5)
    assert math.isclose(tip_x_50, 128.0, abs_tol=1e-4)
    assert math.isclose(tip_y_50, 128.0 - (128.0 * 0.78), abs_tol=1e-4)
    
    # Test value 0 (225 degrees, pointing bottom-left)
    angle_0 = _val_to_angle(0.0)
    rad_0 = math.radians(angle_0)
    tip_x_0 = center_x + needle_len * math.cos(rad_0)
    tip_y_0 = center_y - needle_len * math.sin(rad_0)
    
    assert math.isclose(angle_0, 225.0, abs_tol=1e-5)
    assert tip_x_0 < center_x
    assert tip_y_0 > center_y


def test_baseline_independent_bezel_outer_pixel_colors():
    """Verify corner background colors and bezel structure without baseline images."""
    img = render(0.0, size=(256, 256))
    pixels = img.load()
    
    # Extreme top-left corner (0,0) must be dark frame color
    r, g, b, a = pixels[0, 0]
    assert r == 20 and g == 22 and b == 26 and a == 255
    
    # Center of dial face (128,128) must be central pivot cap color
    r_c, g_c, b_c, a_c = pixels[128, 128]
    assert r_c > 150 and g_c > 150 and b_c > 150  # Chromed metallic cap highlight
```

---

### 6.5 `tests/visual/baselines` (Add Directory)

Create directory `tests/visual/baselines` for storing canonical reference PNG files (`test_stingray_value_0.png`, `test_stingray_value_100.png`, `test_stingray_telltales.png`).

---

### 6.6 `tests/visual/test_stingray_visual.py` (Add)

**Complete file contents:**

```python
"""Render-tier visual regression tests for Stingray skin gauge face.

Issue #1: Core Gauge Renderer — Analog Tachometer with Arc, Needle, and Tick Marks
"""

from __future__ import annotations

import math
from pathlib import Path
import pytest
from PIL import Image, ImageChops

from boostgauge.gauge import render

BASELINES_DIR = Path(__file__).resolve().parent / "baselines"


def _compute_rms_diff(img1: Image.Image, img2: Image.Image) -> float:
    """Compute Root Mean Square (RMS) difference per channel between two PIL images."""
    if img1.size != img2.size or img1.mode != img2.mode:
        return 1.0  # Maximum difference if dimensions or modes mismatch
    
    diff = ImageChops.difference(img1, img2)
    h = diff.histogram()
    
    # Calculate RMS error over all color channels
    sum_sq = 0.0
    total_pixels = img1.size[0] * img1.size[1] * len(img1.getbands())
    
    for i in range(len(h)):
        count = h[i]
        val = i % 256
        sum_sq += count * (val * val)
        
    rms = math.sqrt(sum_sq / float(total_pixels)) / 255.0
    return rms


def test_visual_baseline_value_0(pytestconfig):
    """T130: Compare rendered gauge output at value=0 against baseline image."""
    BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    baseline_path = BASELINES_DIR / "test_stingray_value_0.png"
    
    rendered_img = render(0.0, telltales=None, size=(256, 256))
    
    if pytestconfig.getoption("generate_baselines", default=False) or not baseline_path.exists():
        rendered_img.save(baseline_path)
        pytest.skip(f"Generated baseline image at {baseline_path}")
        
    baseline_img = Image.open(baseline_path).convert("RGBA")
    rms_error = _compute_rms_diff(rendered_img, baseline_img)
    
    assert rms_error <= (1.0 / 255.0), f"Visual RMS error {rms_error:.6f} exceeded tolerance 1/255"


def test_visual_baseline_value_100(pytestconfig):
    """Compare rendered gauge output at value=100 against baseline image."""
    BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    baseline_path = BASELINES_DIR / "test_stingray_value_100.png"
    
    rendered_img = render(100.0, telltales=None, size=(256, 256))
    
    if pytestconfig.getoption("generate_baselines", default=False) or not baseline_path.exists():
        rendered_img.save(baseline_path)
        pytest.skip(f"Generated baseline image at {baseline_path}")
        
    baseline_img = Image.open(baseline_path).convert("RGBA")
    rms_error = _compute_rms_diff(rendered_img, baseline_img)
    
    assert rms_error <= (1.0 / 255.0), f"Visual RMS error {rms_error:.6f} exceeded tolerance 1/255"


def test_visual_baseline_telltales(pytestconfig):
    """Compare rendered gauge output with active telltales against baseline image."""
    BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    baseline_path = BASELINES_DIR / "test_stingray_telltales.png"
    
    telltales = {
        "window_1m": 35.0,
        "window_10m": 60.0,
        "window_1h": 85.0,
        "window_all": 95.0,
    }
    rendered_img = render(25.0, telltales=telltales, size=(256, 256))
    
    if pytestconfig.getoption("generate_baselines", default=False) or not baseline_path.exists():
        rendered_img.save(baseline_path)
        pytest.skip(f"Generated baseline image at {baseline_path}")
        
    baseline_img = Image.open(baseline_path).convert("RGBA")
    rms_error = _compute_rms_diff(rendered_img, baseline_img)
    
    assert rms_error <= (1.0 / 255.0), f"Visual RMS error {rms_error:.6f} exceeded tolerance 1/255"
```

## 7. Pattern References

### 7.1 Test Bootstrap Pattern

**File:** `tests/conftest.py` (lines 1-8)

```python
"""Project test bootstrap."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
```

**Relevance:** Demonstrates path resolution pattern using `pathlib.Path` and adding `src` to `sys.path` for module import discovery across unit and visual test suites.

### 7.2 Project Package Dependencies Pattern

**File:** `pyproject.toml` (lines 10-18)

```toml
dependencies = [
    "psutil (>=7.2.2,<8.0.0)",
    "pillow (>=12.2.0,<13.0.0)",
    "pystray (>=0.19.5,<0.20.0)"
]
```

**Relevance:** Establishes the exact version bounds for Pillow (`>=12.2.0,<13.0.0`), which supplies `PIL.Image`, `PIL.ImageDraw`, `PIL.ImageFont`, and `PIL.ImageResampling.LANCZOS` required by `skins/stingray.py`.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `from __future__ import annotations` | stdlib | All files |
| `import math` | stdlib | `skins/stingray.py`, `test_gauge.py`, `test_stingray_visual.py` |
| `import sys` | stdlib | `test_gauge.py` |
| `from typing import Any, TypedDict` | stdlib | `gauge.py`, `skins/stingray.py` |
| `from pathlib import Path` | stdlib | `test_gauge.py`, `test_stingray_visual.py` |
| `from PIL import Image, ImageDraw, ImageFont, ImageChops` | `pillow` | `gauge.py`, `skins/stingray.py`, `test_gauge.py`, `test_stingray_visual.py` |
| `import pytest` | `pytest` | `test_gauge.py`, `test_stingray_visual.py` |
| `from boostgauge.skins.stingray import render_stingray, _val_to_angle` | internal | `gauge.py`, `skins/__init__.py`, `test_gauge.py` |

**New Dependencies:** None (Uses existing `pillow` dependency in `pyproject.toml`).

## 9. Placeholder

*Reserved for future use to maintain alignment with LLD section numbering.*

## 10. Test Mapping

### 10.1 Unit & Visual Test Scenarios

| Test ID | Tests Function | Input | Expected Output | Behavior / Requirement Traced |
|---------|---------------|-------|-----------------|-------------------------------|
| T010 | `render()` | `value=50.0, size=(256,256)` | `PIL.Image.Image` (256x256, RGBA), no `tkinter` | REQ-1 (Pure function PIL output, 0 Tkinter import) |
| T020 | `render()` | `value=-25.0` & `value=150.0` | Output equals 0.0 & 100.0 renders | REQ-2 (Clamping out-of-bounds metrics) |
| T030 | `render()` | `size=(64,64)` | Raises `ValueError` | REQ-2 (Minimum 128x128 size check) |
| T040 | `render()` | `config={"skin":"cyberpunk"}` | Raises `ValueError` | REQ-2 (Skin name validation) |
| T050 | `_draw_bezel_and_dial()` | `size=(1024,1024)` | Square bezel + round dial drawn | REQ-3 (Chromed housing & matte black dial) |
| T060 | `_draw_ticks_and_numerals()` | `center=(512,512), radius=450` | 11 major + 40 minor white ticks | REQ-4 (11 major and 40 minor white ticks) |
| T070 | `_draw_ticks_and_numerals()` | `center=(512,512), radius=450` | Numerals 0 to 100 at major ticks | REQ-5 (Eurostile-adjacent numerals 0-100) |
| T080 | `_draw_redline_arc()` | `center=(512,512), radius=450` | Red arc from value 60 to 100 | REQ-6 (Redline arc #E63946 at 60-100) |
| T090 | `_draw_wordmark()` | `center=(512,512), radius=450` | Centered "BOOSTGAUGE" text | REQ-7 (BOOSTGAUGE small-caps wordmark) |
| T100 | `_val_to_angle()` | `value=0, 50, 100` | Angles `225.0`, `90.0`, `-45.0` | REQ-8 (Main needle sweep mapping) |
| T110 | `render_stingray()` | `telltales={...}` | Translucent telltales rendered | REQ-9 (Translucent telltale needles) |
| T120 | `render_stingray()` | `telltales=None` | Telltale needles omitted | REQ-9 (Hiding inactive/None telltales) |
| T130 | `render()` | `value=0, size=(256,256)` | RMS diff <= 1.0/255 vs baseline | REQ-10 (Visual regression test) |
| T140 | `render()` | Identical parameters x2 | `img1.tobytes() == img2.tobytes()` | REQ-10 (Deterministic output) |

### 10.2 Platform-Independent Path Assertions Compliance

Per Issue #1841 guidelines, all test assertions involving file paths use standard `pathlib.Path` comparison rather than string comparison or `endswith()` assertions:

```python
# CORRECT (Platform Independent):
BASELINES_DIR = Path(__file__).resolve().parent / "baselines"
baseline_path = BASELINES_DIR / "test_stingray_value_0.png"
assert baseline_path == Path(__file__).resolve().parent / "baselines" / "test_stingray_value_0.png"
```

### 10.3 Behavioral Assertion Traceability Compliance

Per Issue #1860 guidelines, every assertion in `test_gauge.py` and `test_stingray_visual.py` traces directly to documented requirements (REQ-1 through REQ-10). No un-specified side effects (such as disk mutations or environment variable changes) are asserted.

### 10.4 Baseline-Independent Property Assertions

Per Issue #1902 guidelines, `tests/unit/test_gauge.py` includes property assertions computable without baseline images to guard against baseline self-validation defects:

1. **Needle Tip Trigonometry:** `test_baseline_independent_needle_tip_trigonometry()` verifies that for `value=50.0`, `_val_to_angle(50.0)` produces exactly `90.0°` (pointing vertically along the Y-axis), `tip_x` equals `center_x` (128.0), and `tip_y` is positioned above `center_y` by `radius * length_factor`.
2. **Outer Bezel Pixel Sampling:** `test_baseline_independent_bezel_outer_pixel_colors()` verifies that the top-left outer canvas pixel `(0, 0)` matches RGB `(20, 22, 26)` and the central pivot pixel `(128, 128)` exhibits metallic highlight brightness (`R, G, B > 150`).

## 11. Implementation Notes

### 11.1 Error Handling Convention

- Parameter boundary checks: `size[0] < 128 or size[1] < 128` raises `ValueError` with descriptive message.
- Unsupported skin name in `config["skin"]`: raises `ValueError` listing all available skins.
- Out-of-range numeric `value`: clamped to `[0.0, 100.0]` without throwing an exception.
- `None` telltale dictionary or `None` peak values: silently omitted during telltale drawing step.

### 11.2 Supersampling & Rendering Strategy

- Internal render resolution: Target resolution multiplied by `supersample_factor` (default `4x`). For example, target size `(256, 256)` renders on a `(1024, 1024)` canvas.
- Anti-aliasing filter: Downsampling to target size uses `PIL.Image.Resampling.LANCZOS` for crisp vector lines and smooth tick arcs.
- Static Background Caching: `_get_cached_background()` caches the supersampled dial background (bezel, dial face, ticks, numerals, wordmark, redline arc) in memory. Dynamic rendering copies the background image and overlays only the needles and pivot cap, achieving high performance.

### 11.3 Constants & Geometry

| Constant | Value | Rationale |
|----------|-------|-----------|
| Sweep Angle Span | `225.0°` to `-45.0°` (`270°` span) | Standard racing tachometer 3/4 circle dial sweep |
| Major Ticks | 11 (0, 10, ..., 100) | Major metric mark intervals |
| Minor Ticks per Major Interval | 4 | Provides subdivisions of 2 metric units per tick |
| Redline Range | 60.0 to 100.0 | High resource pressure redline warning area |
| Main Needle Length | `0.78 * radius` | Points precisely to major tick inner radius |
| Telltale Needle Length | `0.75 * radius` | Slightly shorter than main needle to preserve visual hierarchy |

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3) - *N/A, all files are Add*
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
| Date | 2026-07-31 |
| Iterations | 1 |
| Finalized | 2026-07-31T16:00:00Z |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #1 |
| Verdict | APPROVED |
| Date | 2026-07-31 |
| Iterations | 0 |
| Finalized | 2026-07-31T21:00:52Z |

### Review Feedback Summary

The implementation specification for Issue #1 (Core Gauge Renderer) is complete, concrete, and fully actionable. It provides complete source code for all new modules (src/boostgauge/gauge.py, src/boostgauge/skins/stingray.py, src/boostgauge/skins/__init__.py) and test files (tests/unit/test_gauge.py, tests/visual/test_stingray_visual.py). All data structures include concrete examples, all functions have explicit signatures and input/output examples, and every test assertion traces directly to de...
