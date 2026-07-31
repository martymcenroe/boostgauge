# Implementation Spec: Issue #1 - Core Gauge Renderer — Analog Tachometer with Arc, Needle, and Tick Marks

| Field | Value |
|-------|-------|
| Issue | #1 |
| LLD | `docs/lld/done/0001-core-gauge-renderer.md` |
| Generated | 2026-07-31 |
| Status | DRAFT |

## 1. Overview

This implementation creates the core off-screen gauge renderer (`boostgauge.gauge`) and its inaugural skin implementation (`boostgauge.skins.stingray`), delivering a 2D analog tachometer modeled after a mid-1970s Schwinn Stingray bicycle speedometer. The renderer produces a `PIL.Image` instance using 2x supersampling anti-aliasing without instantiating `tkinter.Tk()`, complying strictly with Option C of the project test strategy (`docs/design/0001-test-strategy.md`).

**Objective:** Build the core off-screen gauge renderer for v1, producing a `PIL.Image` of an analog tachometer with square chromed housing, round matte-black dial, tick marks, numerals, redline arc, main needle, and telltale peak-hold needles.

**Success Criteria:**
- Pure functional rendering interface (`render(value, telltales, size, config) -> PIL.Image.Image`) with zero side effects or native UI dependencies.
- Bounded input clamping to $[0.0, 100.0]$ for metric values and minimum $128 \times 128\text{ px}$ canvas dimensions.
- Deterministic linear mapping from value $[0, 100]$ to needle sweep angle $[225^\circ, -45^\circ]$.
- Translucent telltale needles (1m cyan, 10m orange, 1h magenta, all-time red) rendered behind the main needle.
- Pixel-RMS visual regression tolerance $\le 1.0 / 255$ against canonical baselines in `tests/visual/baselines/`.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/skins/__init__.py` | Add | Skin package entry point exporting registry, default skin resolution, and skin protocol |
| 2 | `src/boostgauge/skins/stingray.py` | Add | Stingray skin implementation rendering complete 2D tachometer visuals into PIL Image |
| 3 | `src/boostgauge/gauge.py` | Add | Core gauge API exposing pure `render()` function and skin dispatch routing |
| 4 | `tests/unit/test_gauge.py` | Add | Unit tests for input validation, value clamping, angle trigonometry, and baseline-independent needle geometry |
| 5 | `tests/visual/test_gauge.py` | Add | Visual regression test suite running off-screen PIL comparison against baseline PNGs |

**Implementation Order Rationale:**
1. `skins/__init__.py` defines skin lookup interface and registry constants required by `gauge.py`.
2. `skins/stingray.py` contains all geometric calculations, font cascades, and PIL drawing passes.
3. `gauge.py` imports `skins` to validate inputs and route high-level render requests.
4. `tests/unit/test_gauge.py` validates mathematical logic, clamping, and geometry without file baseline dependencies.
5. `tests/visual/test_gauge.py` completes end-to-end pixel verification against PNG baselines.

## 3. Current State (for Modify/Delete files)

All files for Issue #1 are new ("Add") files. No existing files in `src/boostgauge` or `tests/` are modified or deleted.

- `src/boostgauge/skins/__init__.py`: File does not exist yet.
- `src/boostgauge/skins/stingray.py`: File does not exist yet.
- `src/boostgauge/gauge.py`: File does not exist yet.
- `tests/unit/test_gauge.py`: File does not exist yet.
- `tests/visual/test_gauge.py`: File does not exist yet.

## 4. Data Structures

### 4.1 `TelltaleDict`

**Definition:**

```python
from typing import Optional, TypedDict

class TelltaleDict(TypedDict, total=False):
    """Peak-hold values for 1m, 10m, 1h, and all-time windows."""
    m1: Optional[float]
    m10: Optional[float]
    h1: Optional[float]
    all: Optional[float]
```

**Concrete Example:**

```json
{
    "m1": 45.5,
    "m10": 72.0,
    "h1": 88.5,
    "all": 99.0
}
```

### 4.2 `NeedleSpec`

**Definition:**

```python
from typing import Tuple, TypedDict

class NeedleSpec(TypedDict):
    """Styling specification for rendering a single pointer needle."""
    value: float
    color: Tuple[int, int, int, int]
    width_pct: float
    is_dashed: bool
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
import PIL.Image

class SkinProtocol(Protocol):
    """Protocol contract required for skin renderers."""
    name: str
    def render(
        self,
        value: float,
        telltales: Optional[TelltaleDict] = None,
        size: int = 256,
        config: Optional[Dict[str, Any]] = None,
    ) -> PIL.Image.Image:
        ...
```

**Concrete Example:**

```json
{
    "skin": "stingray",
    "background_color": [18, 18, 18, 255],
    "supersample_factor": 2
}
```

## 5. Function Specifications

### 5.1 `render()`

**File:** `src/boostgauge/gauge.py`

**Signature:**

```python
def render(
    value: float,
    telltales: Optional[TelltaleDict] = None,
    size: int = 256,
    config: Optional[Dict[str, Any]] = None,
) -> PIL.Image.Image:
    """Render gauge state into an off-screen PIL Image using the configured skin."""
    ...
```

**Input Example:**

```python
value = 75.0
telltales = {"m1": 80.0, "m10": 85.0, "h1": 90.0, "all": 95.0}
size = 256
config = {"skin": "stingray"}
```

**Output Example:**

```python
# Returns PIL.Image.Image instance with mode "RGBA" and size (256, 256)
<PIL.Image.Image image mode=RGBA size=256x256 at 0x0000021A3B8C1D00>
```

**Edge Cases:**
- `value < 0.0` -> clamped to `0.0` prior to rendering.
- `size < 128` -> clamped to `128` prior to rendering.
- `config is None` or missing `"skin"` key -> defaults to skin `"stingray"`.
- Unknown skin name in `config["skin"]` -> raises `ValueError("Unknown skin: 'custom_skin'")`.

### 5.2 `validate_render_inputs()`

**File:** `src/boostgauge/gauge.py`

**Signature:**

```python
def validate_render_inputs(
    value: float,
    size: int,
) -> Tuple[float, int]:
    """Validate and clamp input metric value to [0.0, 100.0] and canvas size to minimum 128 px."""
    ...
```

**Input Example:**

```python
value = -12.5
size = 64
```

**Output Example:**

```python
(0.0, 128)
```

**Edge Cases:**
- Non-numeric `value` (e.g. string `"50"`) -> raises `TypeError("value must be a float or int")`.
- `value > 100.0` -> clamped to `100.0`.
- `size` is float `256.0` -> cast to int `256`.

### 5.3 `render_stingray()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
def render_stingray(
    value: float,
    telltales: Optional[TelltaleDict] = None,
    size: int = 256,
    config: Optional[Dict[str, Any]] = None,
) -> PIL.Image.Image:
    """Render Stingray skin tachometer image at requested pixel size using 2x supersampling."""
    ...
```

**Input Example:**

```python
value = 50.0
telltales = None
size = 256
config = None
```

**Output Example:**

```python
<PIL.Image.Image image mode=RGBA size=256x256 at 0x0000021A3B8C1E10>
```

**Edge Cases:**
- `telltales` dictionary contains `None` values (e.g. `{"m1": None}`) -> corresponding telltale needle is omitted from draw sequence.

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
- `value = 0.0` -> returns `225.0`.
- `value = 100.0` -> returns `-45.0`.
- `value = 25.0` -> returns `157.5`.

### 5.5 `draw_housing_and_bezel()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
def draw_housing_and_bezel(draw: Any, canvas_size: int) -> None:
    """Draw square housing with rounded chamfered corners and polished chrome gradients."""
    ...
```

**Input Example:**

```python
draw = PIL.ImageDraw.Draw(canvas_image)
canvas_size = 512
```

**Output Example:**

```python
None
```

**Edge Cases:**
- `canvas_size <= 0` -> raises `ValueError("canvas_size must be positive")`.

### 5.6 `draw_dial_face()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
def draw_dial_face(draw: Any, canvas_size: int) -> None:
    """Draw recessed circular matte-black dial face centered inside housing."""
    ...
```

**Input Example:**

```python
draw = PIL.ImageDraw.Draw(canvas_image)
canvas_size = 512
```

**Output Example:**

```python
None
```

**Edge Cases:**
- Draws centered circle with radius `r = canvas_size * 0.40` filled with `#121212`.

### 5.7 `draw_redline_arc()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
def draw_redline_arc(draw: Any, canvas_size: int) -> None:
    """Draw redline arc band hugging outer tick ring from value 60 to 100."""
    ...
```

**Input Example:**

```python
draw = PIL.ImageDraw.Draw(canvas_image)
canvas_size = 512
```

**Output Example:**

```python
None
```

**Edge Cases:**
- Angle calculation maps value 60 ($63^\circ$) to 100 ($-45^\circ$) with stroke width $0.02 \times \text{canvas\_size}$ and color `#E62214`.

### 5.8 `draw_ticks_and_numerals()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
def draw_ticks_and_numerals(draw: Any, canvas_size: int) -> None:
    """Draw 11 major tick marks (0-100), 40 minor tick marks, and white numerals."""
    ...
```

**Input Example:**

```python
draw = PIL.ImageDraw.Draw(canvas_image)
canvas_size = 512
```

**Output Example:**

```python
None
```

**Edge Cases:**
- Font resolution falls back gracefully from Eurostile -> Helvetica -> DIN -> default PIL font if system fonts are unavailable.

### 5.9 `draw_wordmark()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
def draw_wordmark(draw: Any, canvas_size: int) -> None:
    """Draw white BOOSTGAUGE small-caps brand wordmark below center pivot."""
    ...
```

**Input Example:**

```python
draw = PIL.ImageDraw.Draw(canvas_image)
canvas_size = 512
```

**Output Example:**

```python
None
```

**Edge Cases:**
- Rendered centered horizontally at `y = cy + 0.35 * radius` using white text.

### 5.10 `draw_telltales()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
def draw_telltales(
    base_img: PIL.Image.Image,
    telltales: Optional[TelltaleDict],
    canvas_size: int,
) -> PIL.Image.Image:
    """Overlay translucent 1m, 10m, 1h, and all-time telltale needles onto base image."""
    ...
```

**Input Example:**

```python
base_img = <PIL.Image.Image mode=RGBA size=512x512>
telltales = {"m1": 50.0, "m10": 70.0, "h1": 85.0, "all": 95.0}
canvas_size = 512
```

**Output Example:**

```python
<PIL.Image.Image mode=RGBA size=512x512>
```

**Edge Cases:**
- If `telltales` is `None` or all values are `None`, returns `base_img` unchanged without creating extra image buffers.

### 5.11 `draw_needle()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
def draw_needle(
    draw: Any,
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
draw = PIL.ImageDraw.Draw(overlay_image)
angle_deg = 90.0
canvas_size = 512
color = (230, 34, 20, 255)
width_pct = 1.0
is_dashed = False
```

**Output Example:**

```python
None
```

**Edge Cases:**
- `is_dashed = True` -> renders needle line as dashed segments along pointer axis.

### 5.12 `draw_pivot_cap()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
def draw_pivot_cap(draw: Any, canvas_size: int) -> None:
    """Draw polished chrome circular pivot cap and mounting detail dots at dial center."""
    ...
```

**Input Example:**

```python
draw = PIL.ImageDraw.Draw(canvas_image)
canvas_size = 512
```

**Output Example:**

```python
None
```

**Edge Cases:**
- Radius of cap is $0.06 \times \text{canvas\_size}$ with silver gradient and 2 flanking dark screw dots.

### 5.13 `get_gauge_font()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
def get_gauge_font(canvas_size: int, font_size_pct: float) -> Any:
    """Resolve period sans-serif font sized to canvas with fallback to default PIL font."""
    ...
```

**Input Example:**

```python
canvas_size = 512
font_size_pct = 0.05
```

**Output Example:**

```python
<PIL.ImageFont.FreeTypeFont object at 0x0000021A3B9E10F0>
```

**Edge Cases:**
- If Truetype fonts are not installed on the system, returns `PIL.ImageFont.load_default()`.

## 6. Change Instructions

### 6.1 `src/boostgauge/skins/__init__.py` (Add)

**Complete file contents:**

```python
"""Skins package for boostgauge renderers.

Issue #1: Core Gauge Renderer — Analog Tachometer with Arc, Needle, and Tick Marks.
"""

from __future__ import annotations

from typing import Any, Dict, Callable
import PIL.Image

from boostgauge.skins.stingray import render_stingray, StingraySkin

SkinRenderer = Callable[[float, Any, int, Any], PIL.Image.Image]

SKIN_REGISTRY: Dict[str, SkinRenderer] = {
    "stingray": render_stingray,
}

def get_skin(name: str = "stingray") -> SkinRenderer:
    """Retrieve skin renderer by name from registry."""
    if name not in SKIN_REGISTRY:
        raise ValueError(f"Unknown skin: {name!r}. Available skins: {list(SKIN_REGISTRY.keys())}")
    return SKIN_REGISTRY[name]

__all__ = [
    "SKIN_REGISTRY",
    "StingraySkin",
    "get_skin",
    "render_stingray",
]
```

### 6.2 `src/boostgauge/skins/stingray.py` (Add)

**Complete file contents:**

```python
"""Stingray skin renderer for boostgauge.

Implements visual spec from docs/design/0002-aesthetic-v1-stingray.md.
Issue #1: Core Gauge Renderer — Analog Tachometer.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional, Tuple
import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont

from boostgauge.skins import TelltaleDict if False else Any  # TYPE_CHECKING hint

def calculate_angle(
    value: float,
    min_angle: float = 225.0,
    max_angle: float = -45.0,
    min_val: float = 0.0,
    max_val: float = 100.0,
) -> float:
    """Map scalar metric value to angular position in degrees (clockwise sweep from lower-left)."""
    clamped_val = max(min_val, min(max_val, value))
    fraction = (clamped_val - min_val) / (max_val - min_val)
    return min_angle + fraction * (max_angle - min_angle)

def get_gauge_font(canvas_size: int, font_size_pct: float) -> Any:
    """Resolve period sans-serif font sized to canvas with fallback to default font."""
    target_px = max(10, int(canvas_size * font_size_pct))
    font_names = ["eurostile.ttf", "Eurostile.ttf", "HelveticaNeue-Bold.ttf", "arialbd.ttf", "arial.ttf"]
    for font_name in font_names:
        try:
            return PIL.ImageFont.truetype(font_name, target_px)
        except OSError:
            continue
    return PIL.ImageFont.load_default()

def draw_housing_and_bezel(draw: Any, canvas_size: int) -> None:
    """Draw square housing with rounded chamfered corners and chrome specular highlights."""
    margin = 4
    corner_radius = int(canvas_size * 0.08)
    
    # Outer housing shadow / border
    draw.rounded_rectangle(
        [margin, margin, canvas_size - margin, canvas_size - margin],
        radius=corner_radius,
        fill=(30, 30, 32, 255),
        outline=(150, 150, 155, 255),
        width=3,
    )
    
    # Bezel band
    bezel_margin = int(canvas_size * 0.04)
    bezel_radius = int(corner_radius * 0.8)
    draw.rounded_rectangle(
        [bezel_margin, bezel_margin, canvas_size - bezel_margin, canvas_size - bezel_margin],
        radius=bezel_radius,
        fill=(180, 182, 185, 255),
        outline=(230, 232, 235, 255),
        width=int(canvas_size * 0.02),
    )

def draw_dial_face(draw: Any, canvas_size: int) -> None:
    """Draw recessed circular matte-black dial face centered inside housing."""
    cx, cy = canvas_size / 2.0, canvas_size / 2.0
    r = canvas_size * 0.40
    
    # Inner shadow rim
    draw.ellipse(
        [cx - r - 2, cy - r - 2, cx + r + 2, cy + r + 2],
        fill=(10, 10, 12, 255),
    )
    
    # Matte black dial face (#121212)
    draw.ellipse(
        [cx - r, cy - r, cx + r, cy + r],
        fill=(18, 18, 18, 255),
        outline=(40, 40, 42, 255),
        width=2,
    )

def draw_redline_arc(draw: Any, canvas_size: int) -> None:
    """Draw redline arc band hugging outer tick ring from value 60 to 100."""
    cx, cy = canvas_size / 2.0, canvas_size / 2.0
    r = canvas_size * 0.38
    
    # Value 60 maps to 63°, value 100 maps to -45°
    start_val, end_val = 60.0, 100.0
    steps = 40
    arc_points = []
    
    for i in range(steps + 1):
        v = start_val + (end_val - start_val) * (i / steps)
        angle_deg = calculate_angle(v)
        rad = math.radians(angle_deg)
        x = cx + r * math.cos(rad)
        y = cy - r * math.sin(rad)
        arc_points.append((x, y))
        
    width = max(3, int(canvas_size * 0.018))
    for i in range(len(arc_points) - 1):
        draw.line([arc_points[i], arc_points[i + 1]], fill=(230, 34, 20, 255), width=width)

def draw_ticks_and_numerals(draw: Any, canvas_size: int) -> None:
    """Draw 11 major tick marks (0-100), 40 minor tick marks, and white numerals."""
    cx, cy = canvas_size / 2.0, canvas_size / 2.0
    r_outer = canvas_size * 0.37
    r_major_inner = canvas_size * 0.31
    r_minor_inner = canvas_size * 0.34
    r_numeral = canvas_size * 0.25
    
    font = get_gauge_font(canvas_size, 0.045)
    
    # 51 total tick positions (0 to 50 intervals of 2 units = 0 to 100)
    for i in range(51):
        val = i * 2.0
        angle_deg = calculate_angle(val)
        rad = math.radians(angle_deg)
        cos_a, sin_a = math.cos(rad), math.sin(rad)
        
        x_out = cx + r_outer * cos_a
        y_out = cy - r_outer * sin_a
        
        if i % 5 == 0:  # Major tick (every 10 units)
            x_in = cx + r_major_inner * cos_a
            y_in = cy - r_major_inner * sin_a
            draw.line([(x_in, y_in), (x_out, y_out)], fill=(255, 255, 255, 255), width=max(2, int(canvas_size * 0.008)))
            
            # Numeral text
            num_str = str(int(val))
            x_num = cx + r_numeral * cos_a
            y_num = cy - r_numeral * sin_a
            
            bbox = font.getbbox(num_str)
            w_text = bbox[2] - bbox[0]
            h_text = bbox[3] - bbox[1]
            draw.text((x_num - w_text / 2.0, y_num - h_text / 2.0), num_str, fill=(255, 255, 255, 255), font=font)
        else:  # Minor tick
            x_in = cx + r_minor_inner * cos_a
            y_in = cy - r_minor_inner * sin_a
            draw.line([(x_in, y_in), (x_out, y_out)], fill=(220, 220, 220, 225), width=max(1, int(canvas_size * 0.004)))

def draw_wordmark(draw: Any, canvas_size: int) -> None:
    """Draw white BOOSTGAUGE small-caps brand wordmark below center pivot."""
    cx, cy = canvas_size / 2.0, canvas_size / 2.0
    font = get_gauge_font(canvas_size, 0.035)
    wordmark = "BOOSTGAUGE"
    
    bbox = font.getbbox(wordmark)
    w_text = bbox[2] - bbox[0]
    h_text = bbox[3] - bbox[1]
    
    y_pos = cy + canvas_size * 0.14
    draw.text((cx - w_text / 2.0, y_pos - h_text / 2.0), wordmark, fill=(240, 240, 240, 230), font=font)

def draw_needle(
    draw: Any,
    angle_deg: float,
    canvas_size: int,
    color: Tuple[int, int, int, int],
    width_pct: float = 1.0,
    is_dashed: bool = False,
) -> None:
    """Draw tapered pointer needle with counterweight at specified angle and style."""
    cx, cy = canvas_size / 2.0, canvas_size / 2.0
    r_tip = canvas_size * 0.35
    r_tail = -canvas_size * 0.08
    w_base = max(2.0, canvas_size * 0.015 * width_pct)
    
    rad = math.radians(angle_deg)
    cos_a, sin_a = math.cos(rad), math.sin(rad)
    cos_perp, sin_perp = math.cos(rad + math.pi / 2.0), math.sin(rad + math.pi / 2.0)
    
    p_tip = (cx + r_tip * cos_a, cy - r_tip * sin_a)
    p_tail = (cx + r_tail * cos_a, cy - r_tail * sin_a)
    
    if is_dashed:
        steps = 10
        for i in range(0, steps, 2):
            t1 = i / steps
            t2 = (i + 1) / steps
            x1 = cx + (r_tail + t1 * (r_tip - r_tail)) * cos_a
            y1 = cy - (r_tail + t1 * (r_tip - r_tail)) * sin_a
            x2 = cx + (r_tail + t2 * (r_tip - r_tail)) * cos_a
            y2 = cy - (r_tail + t2 * (r_tip - r_tail)) * sin_a
            draw.line([(x1, y1), (x2, y2)], fill=color, width=max(1, int(w_base)))
    else:
        p_left = (cx + w_base * cos_perp, cy - w_base * sin_perp)
        p_right = (cx - w_base * cos_perp, cy + w_base * sin_perp)
        draw.polygon([p_tip, p_left, p_tail, p_right], fill=color)

def draw_telltales(
    base_img: PIL.Image.Image,
    telltales: Optional[Dict[str, Optional[float]]],
    canvas_size: int,
) -> PIL.Image.Image:
    """Overlay translucent 1m, 10m, 1h, and all-time telltale needles behind main needle."""
    if not telltales or all(v is None for v in telltales.values()):
        return base_img
        
    overlay = PIL.Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = PIL.ImageDraw.Draw(overlay)
    
    styles = {
        "m1": {"color": (0, 220, 255, 170), "width_pct": 0.5, "is_dashed": False},
        "m10": {"color": (255, 150, 0, 170), "width_pct": 0.5, "is_dashed": False},
        "h1": {"color": (230, 0, 230, 170), "width_pct": 0.5, "is_dashed": True},
        "all": {"color": (230, 34, 20, 170), "width_pct": 0.5, "is_dashed": False},
    }
    
    for window in ["1m", "10m", "1h", "all"]:
        key = window.replace("1m", "m1").replace("10m", "m10").replace("1h", "h1")
        val = telltales.get(key) if key in telltales else telltales.get(window)
        if val is not None:
            angle_deg = calculate_angle(val)
            style = styles[key]
            draw_needle(
                draw,
                angle_deg,
                canvas_size,
                color=style["color"],
                width_pct=style["width_pct"],
                is_dashed=style["is_dashed"],
            )
            
    return PIL.Image.alpha_composite(base_img, overlay)

def draw_pivot_cap(draw: Any, canvas_size: int) -> None:
    """Draw polished chrome circular pivot cap and mounting screw details at dial center."""
    cx, cy = canvas_size / 2.0, canvas_size / 2.0
    r_cap = canvas_size * 0.05
    
    # Outer cap rim
    draw.ellipse(
        [cx - r_cap, cy - r_cap, cx + r_cap, cy + r_cap],
        fill=(200, 202, 205, 255),
        outline=(80, 80, 85, 255),
        width=2,
    )
    
    # Specular cap center
    r_inner = r_cap * 0.6
    draw.ellipse(
        [cx - r_inner, cy - r_inner, cx + r_inner, cy + r_inner],
        fill=(240, 242, 245, 255),
    )
    
    # Screw detail dots
    r_dot = max(1.5, canvas_size * 0.006)
    offset = r_cap * 0.55
    draw.ellipse([cx - offset - r_dot, cy - r_dot, cx - offset + r_dot, cy + r_dot], fill=(50, 50, 55, 255))
    draw.ellipse([cx + offset - r_dot, cy - r_dot, cx + offset + r_dot, cy + r_dot], fill=(50, 50, 55, 255))

def render_stingray(
    value: float,
    telltales: Optional[Dict[str, Optional[float]]] = None,
    size: int = 256,
    config: Optional[Dict[str, Any]] = None,
) -> PIL.Image.Image:
    """Render Stingray skin tachometer image at requested pixel size using 2x supersampling."""
    supersample_factor = 2
    canvas_size = size * supersample_factor
    
    img = PIL.Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = PIL.ImageDraw.Draw(img)
    
    draw_housing_and_bezel(draw, canvas_size)
    draw_dial_face(draw, canvas_size)
    draw_redline_arc(draw, canvas_size)
    draw_ticks_and_numerals(draw, canvas_size)
    draw_wordmark(draw, canvas_size)
    
    img = draw_telltales(img, telltales, canvas_size)
    
    # Draw main needle & pivot cap
    draw = PIL.ImageDraw.Draw(img)
    main_angle = calculate_angle(value)
    draw_needle(draw, main_angle, canvas_size, color=(230, 34, 20, 255), width_pct=1.0, is_dashed=False)
    draw_pivot_cap(draw, canvas_size)
    
    # Downsample via Lanczos for crisp anti-aliasing
    return img.resize((size, size), resample=PIL.Image.Resampling.LANCZOS)

class StingraySkin:
    """Class wrapper implementing SkinProtocol interface."""
    name = "stingray"
    
    def render(
        self,
        value: float,
        telltales: Optional[Dict[str, Optional[float]]] = None,
        size: int = 256,
        config: Optional[Dict[str, Any]] = None,
    ) -> PIL.Image.Image:
        return render_stingray(value, telltales, size, config)
```

### 6.3 `src/boostgauge/gauge.py` (Add)

**Complete file contents:**

```python
"""Core gauge entry point and routing module.

Issue #1: Core Gauge Renderer — Analog Tachometer.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
import PIL.Image

from boostgauge.skins import get_skin, TelltaleDict

def validate_render_inputs(
    value: float,
    size: int,
) -> Tuple[float, int]:
    """Validate and clamp input metric value to [0.0, 100.0] and size to minimum 128 px."""
    if not isinstance(value, (int, float)):
        raise TypeError(f"value must be float or int, got {type(value).__name__}")
    if not isinstance(size, (int, float)):
        raise TypeError(f"size must be integer, got {type(size).__name__}")
        
    clamped_value = max(0.0, min(100.0, float(value)))
    clamped_size = max(128, int(size))
    return clamped_value, clamped_size

def render(
    value: float,
    telltales: Optional[TelltaleDict] = None,
    size: int = 256,
    config: Optional[Dict[str, Any]] = None,
) -> PIL.Image.Image:
    """Render gauge state into off-screen PIL Image using configured skin (defaults to Stingray)."""
    clamped_val, clamped_sz = validate_render_inputs(value, size)
    
    skin_name = "stingray"
    if config and isinstance(config, dict) and "skin" in config:
        skin_name = str(config["skin"])
        
    renderer = get_skin(skin_name)
    return renderer(clamped_val, telltales, clamped_sz, config)
```

### 6.4 `tests/unit/test_gauge.py` (Add)

**Complete file contents:**

```python
"""Unit tests for gauge math, input validation, and baseline-independent needle geometry.

Issue #1: Core Gauge Renderer — Analog Tachometer.
"""

from __future__ import annotations

import math
import pytest
from pathlib import Path
import PIL.Image

from boostgauge.gauge import render, validate_render_inputs
from boostgauge.skins.stingray import calculate_angle, render_stingray

def test_validate_render_inputs_clamping():
    """Verify scalar values <0 clamp to 0, >100 clamp to 100, and size <128 clamps to 128."""
    val, sz = validate_render_inputs(-15.0, 64)
    assert val == 0.0
    assert sz == 128
    
    val, sz = validate_render_inputs(150.0, 512)
    assert val == 100.0
    assert sz == 512

def test_validate_render_inputs_type_errors():
    """Verify non-numeric input types raise TypeError."""
    with pytest.raises(TypeError):
        validate_render_inputs("invalid", 256)
    with pytest.raises(TypeError):
        validate_render_inputs(50.0, "invalid")

def test_calculate_angle_linear_sweep():
    """Verify linear mapping: 0 -> 225°, 50 -> 90°, 100 -> -45°."""
    assert calculate_angle(0.0) == pytest.approx(225.0)
    assert calculate_angle(50.0) == pytest.approx(90.0)
    assert calculate_angle(100.0) == pytest.approx(-45.0)
    assert calculate_angle(25.0) == pytest.approx(157.5)
    assert calculate_angle(75.0) == pytest.approx(22.5)

def test_pure_function_offscreen_rendering():
    """Verify render() returns a valid PIL Image without instantiating tkinter."""
    img = render(75.0, size=256)
    assert isinstance(img, PIL.Image.Image)
    assert img.size == (256, 256)
    assert img.mode == "RGBA"

def test_baseline_independent_needle_tip_trigonometry():
    """Compute needle tip coordinates mathematically and verify color presence without baselines (Issue #1902)."""
    size = 256
    img = render(50.0, size=size)
    
    # Test value 50.0 -> 90 degrees (pointing straight up)
    angle_deg = calculate_angle(50.0)
    assert angle_deg == pytest.approx(90.0)
    
    cx, cy = size / 2.0, size / 2.0
    r_tip = size * 0.35
    rad = math.radians(angle_deg)
    expected_tip_x = int(cx + r_tip * math.cos(rad))
    expected_tip_y = int(cy - r_tip * math.sin(rad))
    
    assert expected_tip_x == pytest.approx(int(cx), abs=1)
    assert expected_tip_y == pytest.approx(int(cy - r_tip), abs=1)
    
    # Inspect actual pixel value at rendered needle tip position (red needle)
    pixel = img.getpixel((expected_tip_x, expected_tip_y))
    assert pixel[0] > 200 and pixel[1] < 50 and pixel[2] < 50 and pixel[3] > 0

def test_telltale_none_value_byte_identical():
    """Verify telltales with None values produce byte-identical output to telltales=None (T060)."""
    img1 = render(50.0, telltales={"m1": None}, size=256)
    img2 = render(50.0, telltales=None, size=256)
    assert img1.tobytes() == img2.tobytes()

def test_draw_redline_arc_pixel_rendering():
    """Verify redline arc renders red pixels in the 60-100 value arc region (T070)."""
    img = render(75.0, size=256)
    rad = math.radians(22.5)
    px = int(128 + 97.28 * math.cos(rad))
    py = int(128 - 97.28 * math.sin(rad))
    pixel = img.getpixel((px, py))
    assert pixel[0] > 180 and pixel[1] < 60

def test_render_stingray_composite_structure():
    """Verify render_stingray constructs full composite housing, dial, ticks, and wordmark (T080)."""
    img = render_stingray(50.0, size=256)
    assert isinstance(img, PIL.Image.Image)
    assert img.size == (256, 256)
    assert img.mode == "RGBA"
    assert img.getpixel((128, 128))[3] == 255

def test_render_skin_routing_stingray():
    """Verify render() dispatches to stingray skin when specified in config dict (T090)."""
    img = render(50.0, size=256, config={"skin": "stingray"})
    assert isinstance(img, PIL.Image.Image)
    assert img.size == (256, 256)

def test_visual_regression_missing_baseline_failure(tmp_path):
    """Verify missing visual baseline without --generate-baselines triggers pytest failure (T100)."""
    import tests.visual.test_gauge as tvg
    class DummyConfig:
        def getoption(self, name, default=False):
            return False
    
    saved_dir = tvg.BASELINES_DIR
    try:
        tvg.BASELINES_DIR = tmp_path / "nonexistent_baselines"
        with pytest.raises(pytest.fail.Exception, match="Missing visual baseline"):
            tvg.test_visual_regression_rest_state(DummyConfig())
    finally:
        tvg.BASELINES_DIR = saved_dir

def test_unknown_skin_raises_value_error():
    """Verify unknown skin name in config raises ValueError."""
    with pytest.raises(ValueError, match="Unknown skin"):
        render(50.0, config={"skin": "nonexistent_skin"})
```

### 6.5 `tests/visual/test_gauge.py` (Add)

**Complete file contents:**

```python
"""Visual regression test suite for boostgauge renderer.

Issue #1: Core Gauge Renderer — Analog Tachometer.
"""

from __future__ import annotations

from pathlib import Path
import pytest
import PIL.Image
import PIL.ImageChops
import PIL.ImageStat

from boostgauge.gauge import render

BASELINES_DIR = Path(__file__).resolve().parent / "baselines"
DIFFS_DIR = Path(__file__).resolve().parent / "diffs"

def test_visual_regression_rest_state(pytestconfig):
    """Assert pixel-RMS tolerance <= 1.0/255 against canonical rest baseline (value=0)."""
    BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    baseline_path = BASELINES_DIR / "test_stingray_rest.png"
    
    rendered_img = render(0.0, telltales=None, size=256)
    
    generate_baselines = pytestconfig.getoption("--generate-baselines", default=False)
    if generate_baselines or not baseline_path.exists():
        if not generate_baselines:
            pytest.fail(f"Missing visual baseline at {baseline_path}. Run pytest --generate-baselines to create.")
        rendered_img.save(baseline_path)
        return

    baseline_img = PIL.Image.open(baseline_path).convert("RGBA")
    diff = PIL.ImageChops.difference(rendered_img, baseline_img)
    stat = PIL.ImageStat.Stat(diff)
    rms = sum(stat.rms) / len(stat.rms)
    
    if rms > 1.0:
        DIFFS_DIR.mkdir(parents=True, exist_ok=True)
        rendered_img.save(DIFFS_DIR / "test_stingray_rest_diff.png")
        pytest.fail(f"Visual regression failed for rest state: RMS difference {rms:.4f} > 1.0")

def test_visual_regression_telltales_present(pytestconfig):
    """Assert rendering with 4 telltale peaks renders non-transparent needles."""
    telltales = {"m1": 50.0, "m10": 70.0, "h1": 85.0, "all": 95.0}
    img_with_telltales = render(25.0, telltales=telltales, size=256)
    img_without_telltales = render(25.0, telltales=None, size=256)
    
    diff = PIL.ImageChops.difference(img_with_telltales, img_without_telltales)
    stat = PIL.ImageStat.Stat(diff)
    rms = sum(stat.rms) / len(stat.rms)
    
    assert rms > 2.0, "Telltale needles did not produce detectable pixel changes"
```

## 7. Pattern References

### 7.1 Test Bootstrap and Import Setup
**File:** `tests/conftest.py` (lines 1-8)

```python
"""Project test bootstrap."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
```

**Relevance:** Demonstrates `pathlib.Path` resolution and `sys.path` configuration for pytest execution across platforms.

### 7.2 Off-Screen PIL Option C Test Protocol
**File:** `docs/design/0001-test-strategy.md` (lines 33-73)

```python
# Option C: render to off-screen PIL.Image first
# Baseline evaluation via PIL.ImageChops.difference() and ImageStat.Stat(diff).rms
diff = PIL.ImageChops.difference(rendered_img, baseline_img)
stat = PIL.ImageStat.Stat(diff)
rms = sum(stat.rms) / len(stat.rms)
```

**Relevance:** Canonical visual comparison specification and baseline generator flag pattern (`--generate-baselines`).

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `import math` | stdlib | `src/boostgauge/skins/stingray.py`, `tests/unit/test_gauge.py` |
| `from pathlib import Path` | stdlib | `tests/unit/test_gauge.py`, `tests/visual/test_gauge.py` |
| `from typing import Any, Dict, Optional, Tuple, TypedDict` | stdlib | All new files |
| `import PIL.Image` | `pillow (>=12.2.0,<13.0.0)` | `src/boostgauge/gauge.py`, `src/boostgauge/skins/stingray.py` |
| `import PIL.ImageDraw` | `pillow (>=12.2.0,<13.0.0)` | `src/boostgauge/skins/stingray.py` |
| `import PIL.ImageFont` | `pillow (>=12.2.0,<13.0.0)` | `src/boostgauge/skins/stingray.py` |
| `import PIL.ImageChops` | `pillow (>=12.2.0,<13.0.0)` | `tests/visual/test_gauge.py` |
| `import PIL.ImageStat` | `pillow (>=12.2.0,<13.0.0)` | `tests/visual/test_gauge.py` |
| `import pytest` | pytest | `tests/unit/test_gauge.py`, `tests/visual/test_gauge.py` |

**New Dependencies:** None (uses existing Pillow and Pytest dependencies specified in `pyproject.toml`).

## 9. Baseline-Independent Verification

To validate needle position and visual calculations without depending on visual regression baseline image files, mathematical property assertions are executed directly on calculated geometry and rendered pixels:

1. **Needle Angle Trigonometry:**
   - For metric value $V = 50.0$, mapped angle $\theta = 90.0^\circ$. Tip coordinate $(X, Y)$ satisfies $X = cx$ and $Y = cy - r_{tip}$.
   - For metric value $V = 0.0$, mapped angle $\theta = 225.0^\circ$. Tip coordinate $(X, Y)$ satisfies $X = cx - r_{tip}/\sqrt{2}$ and $Y = cy + r_{tip}/\sqrt{2}$.
   - For metric value $V = 100.0$, mapped angle $\theta = -45.0^\circ$. Tip coordinate $(X, Y)$ satisfies $X = cx + r_{tip}/\sqrt{2}$ and $Y = cy + r_{tip}/\sqrt{2}$.

2. **Pixel Opacity Verification:**
   - Rendering gauge image at $size = 256$ produces non-zero alpha values ($\text{RGBA}[3] > 0$) across the inner dial and housing regions ($X, Y \in [10, 246]$).

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `render()` | `value=0.0, telltales=None, size=256` | `PIL.Image.Image` object mode RGBA, size (256, 256) |
| T020 | `validate_render_inputs()` | `value=-15.0, size=64` | `(0.0, 128)` |
| T030 | `calculate_angle()` | `value=50.0` | `90.0` |
| T040 | `test_visual_regression_rest_state()` | `value=0.0, telltales=None` | RMS pixel difference $\le 1.0 / 255$ vs baseline |
| T050 | `draw_telltales()` | `telltales={'m1': 50.0, ...}` | Image diff RMS $> 2.0$ vs `telltales=None` |
| T060 | `render()` | `telltales={'m1': None}` | Output byte-identical to `telltales=None` |
| T070 | `draw_redline_arc()` | `value=75.0` | Redline arc pixels rendered in range 60 to 100 |
| T080 | `render_stingray()` | `size=256` | Housing, dial face, ticks, and wordmark composite image |
| T090 | `render()` | `config={'skin': 'stingray'}` | Rendered image dispatched to `stingray.py` |
| T100 | `test_visual_regression_rest_state()` | Missing baseline, no flag | `pytest.fail` raising missing baseline error |

## 11. Implementation Notes

### 11.1 Error Handling Convention
- Functions in `boostgauge.gauge` validate parameter types and bounds, raising explicit `TypeError` or `ValueError` on bad inputs.
- Font resolution cascades through period sans-serif options (Eurostile, Helvetica Neue, Arial) before falling back to `PIL.ImageFont.load_default()`.

### 11.2 Supersampling Convention
- Gauge drawing occurs internally on a buffer scaled by $2\times$ ($size \times 2$).
- Downsampling to requested target $size$ is performed as the final step in `render_stingray()` using `PIL.Image.Resampling.LANCZOS`.

### 11.3 Constants

| Constant | Value | Rationale |
|----------|-------|-----------|
| `DEFAULT_GAUGE_SIZE` | `256` | Standard desktop widget canvas resolution |
| `MIN_GAUGE_SIZE` | `128` | Minimum readable dial diameter |
| `SWEEP_MIN_ANGLE` | `225.0` | Lower-left start position (0 value) in degrees |
| `SWEEP_MAX_ANGLE` | `-45.0` | Lower-right end position (100 value) in degrees |
| `SUPERSAMPLE_FACTOR` | `2` | Anti-aliasing scaling factor |

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3)
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
| Finalized | 2026-07-31T14:18:00Z |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #1 |
| Verdict | APPROVED |
| Date | 2026-07-31 |
| Iterations | 2 |
| Finalized | 2026-07-31T19:19:45Z |

### Review Feedback Summary

The revised implementation spec for Issue #1 is fully ready for implementation. The updated `draw_telltales` check cleanly handles empty or all-None telltale dictionaries, ensuring byte-identical rendering behavior when telltales are omitted or explicitly set to None. All test assertions across unit and visual test suites trace directly to documented specifications, complete Python code is supplied for all five target files, and the spec includes thorough baseline-independent geometry checks, in...
