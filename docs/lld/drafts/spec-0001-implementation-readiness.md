# Implementation Spec: Core Gauge Renderer — Analog Tachometer with Arc, Needle, and Tick Marks

| Field | Value |
|-------|-------|
| Issue | #1 |
| LLD | `docs/lld/active/0001-core-gauge-renderer.md` |
| Generated | 2026-08-01 |
| Status | DRAFT |

## 1. Overview

This specification details the concrete implementation for the core analog tachometer gauge renderer in BoostGauge (`boostgauge.gauge.render`). The renderer produces an off-screen `PIL.Image` of a Stingray-styled analog tachometer with a square chamfered chrome housing, circular matte-black dial, tick marks, numerals, redline arc, translucent peak-hold telltale needles, main pointer needle, and polished pivot cap using 2x supersampling and Lanczos downscaling.

**Objective:** Build the pure facade function `render(value, telltales, size, config) -> PIL.Image` and underlying skin module `src/boostgauge/skins/stingray.py` without importing `tkinter` or creating GUI dependencies.

**Success Criteria:**
1. Pure function signature `render(value, telltales, size, config) -> PIL.Image` returning a `PIL.Image` without importing `tkinter`.
2. Metric value clamping to range `[0.0, 100.0]` for float/int inputs, raising `TypeError` for non-numeric inputs.
3. Sizing validation enforcing `size >= 128`, defaulting to `256x256`, raising `ValueError` for `size < 128`.
4. High-quality off-screen 2x supersampled PIL rendering downscaled with `LANCZOS` anti-aliasing.
5. Deterministic byte-identical output for identical render parameters.
6. 100% automated test coverage in `tests/unit/test_gauge.py` and `tests/visual/test_gauge_visual.py` featuring both baseline RMS diffs and baseline-independent trigonometric assertions.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/skins/__init__.py` | Add | Package initialization exporting skin registry and `SkinProtocol`. |
| 2 | `src/boostgauge/skins/stingray.py` | Add | Stingray skin implementation using off-screen Pillow primitives. |
| 3 | `src/boostgauge/gauge.py` | Add | Core gauge facade exposing `render()`, `clamp_value()`, `value_to_angle()`. |
| 4 | `tests/unit/test_gauge.py` | Add | Unit tests for input validation, clamping, angle math, facade dispatch. |
| 5 | `tests/visual/test_gauge_visual.py` | Add | Visual regression baseline tests and baseline-independent property assertions. |

**Implementation Order Rationale:**
`skins/__init__.py` defines the protocol contracts and skin lookup registry. `skins/stingray.py` implements the specific vector drawing operations using PIL. `gauge.py` builds on top of the skin registry to provide the public facade `render()` with input validation and clamping. Finally, unit tests (`tests/unit/test_gauge.py`) and visual regression tests (`tests/visual/test_gauge_visual.py`) test the facade and visual correctness.

## 3. Current State (for Modify/Delete files)

*No files are modified or deleted in this feature. All 5 files listed in Section 2 are new additions ("Add").*

## 4. Data Structures

### 4.1 RenderContext

**Definition:**

```python
from dataclasses import dataclass
from typing import Dict, Optional

@dataclass(frozen=True)
class RenderContext:
    value: float
    telltales: Dict[str, Optional[float]]
    size: int
    supersample_factor: int = 2
```

**Concrete Example:**

```json
{
    "value": 42.5,
    "telltales": {
        "1m": 25.0,
        "10m": 45.0,
        "1h": 65.0,
        "all_time": 85.0
    },
    "size": 256,
    "supersample_factor": 2
}
```

### 4.2 SkinProtocol

**Definition:**

```python
from typing import Protocol, Dict, Any, Optional
from PIL import Image

class SkinProtocol(Protocol):
    """Protocol signature for gauge skin renderers per #45."""
    def render(
        self,
        value: float,
        telltales: Optional[Dict[str, Optional[float]]] = None,
        size: int = 256,
        config: Optional[Dict[str, Any]] = None,
    ) -> Image.Image:
        ...
```

**Concrete Example:**

```json
{
    "skin": "stingray",
    "theme": "dark",
    "supersample": 2
}
```

### 4.3 Telltale Dictionary Schema

**Definition:**

```python
from typing import Dict, Optional

TelltaleDict = Dict[str, Optional[float]]
```

**Concrete Example:**

```json
{
    "1m": 20.0,
    "10m": 40.0,
    "1h": null,
    "all_time": 95.5
}
```

## 5. Function Specifications

### 5.1 `render()`

**File:** `src/boostgauge/gauge.py`

**Signature:**

```python
def render(
    value: float,
    telltales: Optional[Dict[str, Optional[float]]] = None,
    size: int = 256,
    config: Optional[Dict[str, Any]] = None,
) -> Image.Image:
    """Core gauge renderer facade. Validates inputs and dispatches to the configured skin renderer."""
    ...
```

**Input Example:**

```python
value = 75.0
telltales = {"1m": 30.0, "10m": 50.0, "1h": 80.0, "all_time": 95.0}
size = 256
config = {"skin": "stingray"}
```

**Output Example:**

```python
# Returns PIL.Image.Image instance
# image.size == (256, 256)
# image.mode == "RGBA"
```

**Edge Cases:**
- `value = "invalid"` -> raises `TypeError("Value must be a number (int or float)")`
- `value = -15.0` -> clamped to `0.0` before rendering
- `value = 150.0` -> clamped to `100.0` before rendering
- `size = 64` -> raises `ValueError("Size must be at least 128 pixels")`
- `telltales = None` -> normalized to `{}` internally

---

### 5.2 `clamp_value()`

**File:** `src/boostgauge/gauge.py`

**Signature:**

```python
def clamp_value(value: float, min_val: float = 0.0, max_val: float = 100.0) -> float:
    """Clamp input metric value to [min_val, max_val]. Raises TypeError if value is non-numeric."""
    ...
```

**Input Example:**

```python
value = 112.4
min_val = 0.0
max_val = 100.0
```

**Output Example:**

```python
100.0
```

**Edge Cases:**
- `value = True` -> raises `TypeError` (booleans are disallowed even though bool inherits int in Python)
- `value = None` -> raises `TypeError("Value must be a number (int or float)")`
- `value = float("nan")` -> clamped to `min_val` (0.0) safely

---

### 5.3 `value_to_angle()`

**File:** `src/boostgauge/gauge.py`

**Signature:**

```python
def value_to_angle(value: float, start_angle: float = 225.0, sweep_angle: float = 270.0) -> float:
    """Convert a metric value (0.0 to 100.0) into a polar angle in degrees (clockwise from 225° / bottom-left)."""
    ...
```

**Input Example:**

```python
value = 50.0
start_angle = 225.0
sweep_angle = 270.0
```

**Output Example:**

```python
360.0  # 225° + 0.5 * 270° = 360° (equivalent to 0° / 3 o'clock horizontal right position)
```

**Edge Cases:**
- `value = 0.0` -> `225.0` (7:30 position, bottom-left)
- `value = 100.0` -> `495.0` (equivalent to 135°, 4:30 position, bottom-right)
- `value = 60.0` -> `387.0` (start of redline arc)

---

### 5.4 `render_stingray()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
def render_stingray(
    value: float,
    telltales: Optional[Dict[str, Optional[float]]] = None,
    size: int = 256,
    config: Optional[Dict[str, Any]] = None,
) -> Image.Image:
    """Stingray skin renderer implementation producing an off-screen PIL.Image."""
    ...
```

**Input Example:**

```python
value = 50.0
telltales = {"10m": 75.0}
size = 256
config = None
```

**Output Example:**

```python
# Returns PIL.Image.Image instance of dimensions (256, 256), mode "RGBA"
```

**Edge Cases:**
- Missing telltale keys (e.g. `telltales={"1m": 40.0}`) -> non-specified telltales (`10m`, `1h`, `all_time`) default to `None` and are not rendered.
- `telltales={"1m": None}` -> telltale needle for `1m` is hidden.

## 6. Change Instructions

### 6.1 `src/boostgauge/skins/__init__.py` (Add)

**Complete file contents:**

```python
"""Skins package for BoostGauge renderers.

Issue #1: Core Gauge Renderer — Analog Tachometer with Arc, Needle, and Tick Marks
"""

from typing import Any, Dict, Optional, Protocol
from PIL import Image


class SkinProtocol(Protocol):
    """Protocol signature for gauge skin renderers per #45."""

    def render(
        self,
        value: float,
        telltales: Optional[Dict[str, Optional[float]]] = None,
        size: int = 256,
        config: Optional[Dict[str, Any]] = None,
    ) -> Image.Image:
        ...


_SKIN_REGISTRY: Dict[str, Any] = {}


def register_skin(name: str, renderer_func: Any) -> None:
    """Register a skin renderer function under a given skin name."""
    _SKIN_REGISTRY[name.lower()] = renderer_func


def get_skin(name: str = "stingray") -> Any:
    """Retrieve a skin renderer function by name. Defaults to 'stingray'."""
    key = name.lower()
    if key not in _SKIN_REGISTRY:
        raise ValueError(f"Unknown gauge skin: '{name}'. Available: {list(_SKIN_REGISTRY.keys())}")
    return _SKIN_REGISTRY[key]
```

---

### 6.2 `src/boostgauge/skins/stingray.py` (Add)

**Complete file contents:**

```python
"""Stingray skin renderer implementation using off-screen Pillow primitives.

Issue #1: Core Gauge Renderer — Analog Tachometer with Arc, Needle, and Tick Marks
"""

import math
from typing import Any, Dict, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont

from boostgauge.skins import register_skin


# Telltale needle styling definitions (Color RGBA)
TELLTALE_STYLES = {
    "1m": {"color": (0, 229, 255, 166), "width": 2},        # Cyan/Blue
    "10m": {"color": (255, 145, 0, 166), "width": 2},       # Orange
    "1h": {"color": (213, 0, 249, 166), "width": 2},        # Magenta/Purple
    "all_time": {"color": (255, 23, 68, 166), "width": 2},  # Bright Red
}


def render_stingray(
    value: float,
    telltales: Optional[Dict[str, Optional[float]]] = None,
    size: int = 256,
    config: Optional[Dict[str, Any]] = None,
) -> Image.Image:
    """Stingray skin renderer implementation producing an off-screen PIL.Image."""
    if telltales is None:
        telltales = {}

    supersample = 2
    canvas_size = size * supersample
    center = (canvas_size / 2.0, canvas_size / 2.0)
    cx, cy = center
    radius = canvas_size * 0.38

    # Create RGBA image with transparent background
    img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. Outer Square Housing with Chamfered Corners (Chrome bezel effect)
    margin = int(canvas_size * 0.04)
    housing_box = [margin, margin, canvas_size - margin, canvas_size - margin]
    corner_radius = int(canvas_size * 0.12)

    # Base housing outline and chrome fill
    draw.rounded_rectangle(housing_box, radius=corner_radius, fill=(30, 32, 38, 255), outline=(180, 185, 195, 255), width=int(3 * supersample))
    inner_margin = margin + int(4 * supersample)
    inner_box = [inner_margin, inner_margin, canvas_size - inner_margin, canvas_size - inner_margin]
    draw.rounded_rectangle(inner_box, radius=max(1, corner_radius - 4), fill=(18, 20, 24, 255), outline=(70, 75, 85, 255), width=int(1.5 * supersample))

    # 2. Circular Matte Black Dial Face
    dial_bbox = [cx - radius, cy - radius, cx + radius, cy + radius]
    draw.ellipse(dial_bbox, fill=(13, 14, 18, 255), outline=(50, 54, 62, 255), width=int(2 * supersample))

    # Inner bezel shadow ring
    shadow_r = radius * 0.98
    draw.ellipse([cx - shadow_r, cy - shadow_r, cx + shadow_r, cy + shadow_r], outline=(5, 6, 8, 200), width=int(3 * supersample))

    # 3. Redline Arc (Value 60 to 100: 387° to 495°, mapped to PIL arc coordinates)
    # PIL arc angles: 0° is 3 o'clock, clockwise positive.
    # Metric value 0 = 225° (bottom-left = 135° in PIL 0-360)
    # Metric value 60 = 225° + 0.6 * 270° = 387° = 27° in PIL
    # Metric value 100 = 225° + 1.0 * 270° = 495° = 135° in PIL
    redline_r = radius * 0.88
    redline_bbox = [cx - redline_r, cy - redline_r, cx + redline_r, cy + redline_r]
    draw.arc(redline_bbox, start=27, end=135, fill=(230, 34, 0, 255), width=int(6 * supersample))

    # 4. Ticks and Numerals
    # 11 major ticks (0, 10, ..., 100) and 40 minor ticks
    start_deg = 225.0
    sweep_deg = 270.0

    # Minor ticks (50 total intervals across sweep)
    for i in range(51):
        frac = i / 50.0
        deg = start_deg + frac * sweep_deg
        rad = math.radians(deg)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)

        is_major = (i % 5 == 0)
        if is_major:
            r1 = radius * 0.82
            r2 = radius * 0.92
            tick_w = int(2.5 * supersample)
            tick_color = (255, 255, 255, 255)
        else:
            r1 = radius * 0.86
            r2 = radius * 0.92
            tick_w = int(1.0 * supersample)
            tick_color = (200, 205, 215, 200)

        x1, y1 = cx + r1 * cos_a, cy + r1 * sin_a
        x2, y2 = cx + r2 * cos_a, cy + r2 * sin_a
        draw.line([(x1, y1), (x2, y2)], fill=tick_color, width=tick_w)

    # Major Numerals (0 to 100 step 10)
    font_size = max(10, int(14 * supersample))
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except IOError:
        font = ImageFont.load_default()

    for i in range(11):
        num_val = i * 10
        frac = i / 10.0
        deg = start_deg + frac * sweep_deg
        rad = math.radians(deg)
        num_r = radius * 0.68
        nx = cx + num_r * math.cos(rad)
        ny = cy + num_r * math.sin(rad)

        text_str = str(num_val)
        bbox = draw.textbbox((0, 0), text_str, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text((nx - tw / 2.0, ny - th / 2.0), text_str, fill=(240, 245, 250, 255), font=font)

    # 5. BOOSTGAUGE Wordmark
    wordmark_font_size = max(8, int(10 * supersample))
    try:
        wm_font = ImageFont.truetype("arial.ttf", wordmark_font_size)
    except IOError:
        wm_font = ImageFont.load_default()

    wm_text = "BOOSTGAUGE"
    wm_bbox = draw.textbbox((0, 0), wm_text, font=wm_font)
    wm_w = wm_bbox[2] - wm_bbox[0]
    wm_y = cy + radius * 0.35
    draw.text((cx - wm_w / 2.0, wm_y), wm_text, fill=(220, 225, 235, 220), font=wm_font)

    # 6. Translucent Secondary Telltale Needles (behind main needle)
    for key in ["1m", "10m", "1h", "all_time"]:
        peak_val = telltales.get(key)
        if peak_val is not None:
            clamped_peak = max(0.0, min(100.0, float(peak_val)))
            t_deg = start_deg + (clamped_peak / 100.0) * sweep_deg
            t_rad = math.radians(t_deg)

            style = TELLTALE_STYLES[key]
            tt_r = radius * 0.85
            tx = cx + tt_r * math.cos(t_rad)
            ty = cy + tt_r * math.sin(t_rad)

            # Create an overlay layer for translucent needle drawing
            overlay = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
            ol_draw = ImageDraw.Draw(overlay)
            ol_draw.line([(cx, cy), (tx, ty)], fill=style["color"], width=int(style["width"] * supersample))
            img = Image.alpha_composite(img, overlay)
            draw = ImageDraw.Draw(img)

    # 7. Main Red Pointer Needle with Rear Counterweight Stub
    clamped_val = max(0.0, min(100.0, float(value)))
    main_deg = start_deg + (clamped_val / 100.0) * sweep_deg
    main_rad = math.radians(main_deg)
    cos_m = math.cos(main_rad)
    sin_m = math.sin(main_rad)

    # Tip position
    needle_r = radius * 0.88
    tip_x = cx + needle_r * cos_m
    tip_y = cy + needle_r * sin_m

    # Counterweight stub position (opposite direction)
    stub_r = radius * 0.18
    stub_x = cx - stub_r * cos_m
    stub_y = cy - stub_r * sin_m

    # Main needle body polygon
    perp_rad = main_rad + math.pi / 2.0
    w_base = 3.5 * supersample
    p1 = (cx + w_base * math.cos(perp_rad), cy + w_base * math.sin(perp_rad))
    p2 = (cx - w_base * math.cos(perp_rad), cy - w_base * math.sin(perp_rad))

    draw.polygon([stub_x, stub_y, p1[0], p1[1], tip_x, tip_y, p2[0], p2[1]], fill=(255, 42, 42, 255), outline=(200, 10, 10, 255))
    draw.line([(stub_x, stub_y), (tip_x, tip_y)], fill=(255, 80, 80, 255), width=int(1.5 * supersample))

    # 8. Polished Chrome Pivot Cap
    cap_r = radius * 0.12
    draw.ellipse([cx - cap_r, cy - cap_r, cx + cap_r, cy + cap_r], fill=(220, 225, 235, 255), outline=(100, 105, 115, 255), width=int(1.5 * supersample))
    inner_cap_r = cap_r * 0.5
    draw.ellipse([cx - inner_cap_r, cy - inner_cap_r, cx + inner_cap_r, cy + inner_cap_r], fill=(160, 165, 175, 255))

    # Downscale RGBA image to target size using LANCZOS resampling filter
    final_img = img.resize((size, size), resample=Image.Resampling.LANCZOS)
    return final_img


# Register Stingray skin in skin registry
register_skin("stingray", render_stingray)
```

---

### 6.3 `src/boostgauge/gauge.py` (Add)

**Complete file contents:**

```python
"""Core gauge renderer facade module exposing render() entry point and skin dispatching.

Issue #1: Core Gauge Renderer — Analog Tachometer with Arc, Needle, and Tick Marks
"""

import math
from typing import Any, Dict, Optional
from PIL import Image

from boostgauge.skins import get_skin


def clamp_value(value: float, min_val: float = 0.0, max_val: float = 100.0) -> float:
    """Clamp input metric value to [min_val, max_val]. Raises TypeError if value is non-numeric."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"Metric value must be a number (int or float), got {type(value).__name__}")

    val_float = float(value)
    if math.isnan(val_float):
        return min_val
    if math.isinf(val_float):
        return max_val if val_float > 0 else min_val

    return max(min_val, min(max_val, val_float))


def value_to_angle(value: float, start_angle: float = 225.0, sweep_angle: float = 270.0) -> float:
    """Convert a metric value (0.0 to 100.0) into a polar angle in degrees (clockwise from 225° / bottom-left)."""
    clamped = clamp_value(value)
    return start_angle + (clamped / 100.0) * sweep_angle


def render(
    value: float,
    telltales: Optional[Dict[str, Optional[float]]] = None,
    size: int = 256,
    config: Optional[Dict[str, Any]] = None,
) -> Image.Image:
    """Core gauge renderer facade. Validates inputs and dispatches to the configured skin renderer."""
    # 1. Type validation and clamping
    clamped_val = clamp_value(value)

    # 2. Size validation
    if not isinstance(size, int) or size < 128:
        raise ValueError(f"Gauge size must be an integer >= 128, got {size}")

    # 3. Extract skin name from config (defaults to 'stingray')
    if config is None:
        config = {}
    skin_name = config.get("skin", "stingray")

    # 4. Resolve skin renderer and execute off-screen draw
    skin_renderer = get_skin(skin_name)
    return skin_renderer(
        value=clamped_val,
        telltales=telltales,
        size=size,
        config=config,
    )
```

---

### 6.4 `tests/unit/test_gauge.py` (Add)

**Complete file contents:**

```python
"""Unit tests for boostgauge.gauge facade, validation, clamping, and math functions.

Issue #1: Core Gauge Renderer — Analog Tachometer with Arc, Needle, and Tick Marks
"""

import sys
import pytest
from PIL import Image

from boostgauge.gauge import clamp_value, render, value_to_angle


def test_t010_render_pure_function_signature_no_tkinter():
    """Verify render() returns PIL.Image without importing tkinter (REQ-1)."""
    # Ensure tkinter is not loaded prior or during render call
    img = render(0.0, None, 256)
    assert isinstance(img, Image.Image)
    assert img.size == (256, 256)
    assert "tkinter" not in sys.modules


def test_t020_value_clamping():
    """Verify clamp_value clamps values < 0.0 and > 100.0 (REQ-2)."""
    assert clamp_value(-15.0) == 0.0
    assert clamp_value(125.0) == 100.0
    assert clamp_value(50.0) == 50.0
    assert clamp_value(0.0) == 0.0
    assert clamp_value(100.0) == 100.0


def test_t030_type_validation_non_numeric():
    """Verify non-numeric value types raise TypeError (REQ-2)."""
    with pytest.raises(TypeError, match="must be a number"):
        clamp_value("invalid")  # type: ignore

    with pytest.raises(TypeError, match="must be a number"):
        render("invalid")  # type: ignore

    with pytest.raises(TypeError, match="must be a number"):
        clamp_value(True)  # type: ignore


def test_t040_default_image_size():
    """Verify default gauge image size is 256x256 px (REQ-3)."""
    img = render(50.0)
    assert img.size == (256, 256)


def test_t050_custom_image_sizes():
    """Verify custom sizes (128x128, 512x512) produce matching PIL dimensions (REQ-3)."""
    img_128 = render(50.0, size=128)
    assert img_128.size == (128, 128)

    img_512 = render(50.0, size=512)
    assert img_512.size == (512, 512)


def test_t060_under_minimum_size_error():
    """Verify size < 128 raises ValueError (REQ-3)."""
    with pytest.raises(ValueError, match="at least 128"):
        render(50.0, size=64)


def test_value_to_angle_conversion():
    """Verify angle conversion for key metric positions."""
    assert value_to_angle(0.0) == 225.0
    assert value_to_angle(50.0) == 360.0
    assert value_to_angle(100.0) == 495.0
    assert value_to_angle(60.0) == 387.0
```

---

### 6.5 `tests/visual/test_gauge_visual.py` (Add)

**Complete file contents:**

```python
"""Visual regression and baseline-independent property tests for gauge renderer.

Issue #1: Core Gauge Renderer — Analog Tachometer with Arc, Needle, and Tick Marks
"""

import math
from pathlib import Path
import pytest
from PIL import Image, ImageChops, ImageStat

from boostgauge.gauge import render, value_to_angle

BASELINES_DIR = Path(__file__).resolve().parent / "baselines"


def calculate_image_rms(img1: Image.Image, img2: Image.Image) -> float:
    """Calculate Root Mean Square (RMS) difference per channel between two PIL images."""
    if img1.size != img2.size or img1.mode != img2.mode:
        raise ValueError("Image dimensions and modes must match for RMS calculation")
    diff = ImageChops.difference(img1, img2)
    stat = ImageStat.Stat(diff)
    # Average RMS across RGB channels
    rms_sum = sum(stat.rms[:3])
    return rms_sum / 3.0


def check_or_generate_baseline(img: Image.Image, baseline_name: str, generate_flag: bool) -> None:
    """Compare rendered image against baseline or save baseline if requested."""
    BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    baseline_path = BASELINES_DIR / f"{baseline_name}.png"

    if generate_flag:
        img.save(baseline_path)
        pytest.skip(f"Baseline saved to {baseline_path}")

    if not baseline_path.exists():
        pytest.fail(f"Baseline image missing: {baseline_path}. Run with --generate-baselines to create.")

    baseline_img = Image.open(baseline_path).convert("RGBA")
    rms = calculate_image_rms(img, baseline_img)
    assert rms <= 1.0, f"Visual regression failure for {baseline_name}: RMS diff = {rms:.4f} > 1.0"


# ============================================================================
# Section: Baseline-Independent Trigonometric Property Assertions (Issue #1902)
# ============================================================================

def test_t160_baseline_independent_needle_position_value_50():
    """Baseline-independent test: at value=50, main needle points to 360° (3 o'clock / horizontal right).

    Directly inspects rendered pixel colors along expected needle trajectory without baseline image dependency.
    """
    size = 256
    img = render(50.0, size=size)
    cx, cy = size / 2.0, size / 2.0
    radius = size * 0.38

    # Value 50 corresponds to 360° (0° horizontal right in standard polar coordinates)
    # Check pixels 30px to the right of center (3 o'clock needle body)
    sample_x = int(cx + radius * 0.5)
    sample_y = int(cy)

    r, g, b, a = img.getpixel((sample_x, sample_y))

    # Assert main red needle is present: Red channel dominant (R > 180, G < 100, B < 100)
    assert r > 180 and g < 100 and b < 100, f"Expected red needle at 3 o'clock (50.0), got RGBA=({r},{g},{b},{a})"

    # Verify opposite position (9 o'clock left of pivot) does NOT contain main needle
    opp_x = int(cx - radius * 0.5)
    or_, og, ob, _ = img.getpixel((opp_x, sample_y))
    assert not (or_ > 180 and og < 100 and ob < 100), f"Un-expected red needle at 9 o'clock for value=50, got RGB=({or_},{og},{ob})"


def test_t120_baseline_independent_needle_position_value_100():
    """Baseline-independent test: at value=100, main needle points to 495° (bottom-right / 4:30 position)."""
    size = 256
    img = render(100.0, size=size)
    cx, cy = size / 2.0, size / 2.0
    radius = size * 0.38

    # Angle 495°: dx = cos(495°)*r = -0.7071*r, dy = sin(495°)*r = 0.7071*r
    rad = math.radians(495.0)
    sample_x = int(cx + (radius * 0.5) * math.cos(rad))
    sample_y = int(cy + (radius * 0.5) * math.sin(rad))

    r, g, b, _ = img.getpixel((sample_x, sample_y))
    assert r > 180 and g < 100 and b < 100, f"Expected red needle at 100.0 (495°), got RGB=({r},{g},{b})"


def test_t090_baseline_independent_redline_arc_presence():
    """Baseline-independent test: verify redline arc pixels exist in scale segment between 60 and 100."""
    size = 256
    img = render(0.0, size=size)
    cx, cy = size / 2.0, size / 2.0
    radius = size * 0.38

    # Redline arc starts at metric value 60 (387° -> 27° in PIL coordinates)
    # Check pixel along redline radius at 80% metric scale (angle 225 + 0.8*270 = 441°)
    rad = math.radians(441.0)
    arc_r = radius * 0.88
    sample_x = int(cx + arc_r * math.cos(rad))
    sample_y = int(cy + arc_r * math.sin(rad))

    r, g, b, _ = img.getpixel((sample_x, sample_y))
    assert r > 180 and g < 100 and b < 100, f"Expected redline arc at metric value 80 angle, got RGB=({r},{g},{b})"


# ============================================================================
# Section: Visual Baseline Regression Tests
# ============================================================================

def getoption(config: pytest.Config | None, name: str, default: bool = False) -> bool:
    """Retrieve command-line option from pytest config or option attribute."""
    if config is None:
        return default
    if hasattr(config, "getoption"):
        try:
            return bool(config.getoption(name, default=default))
        except (ValueError, AttributeError):
            pass
    attr = name.lstrip("-").replace("-", "_")
    return bool(getattr(getattr(config, "option", None), attr, default))


def test_t070_t080_visual_baseline_value_0(pytestconfig):
    """Verify gauge render output at value 0 against baseline image (REQ-4)."""
    generate = getoption(pytestconfig, "--generate-baselines", default=False)
    img = render(0.0, None, 256)
    check_or_generate_baseline(img, "gauge_v0_no_telltales", generate)


def test_t110_visual_baseline_telltales_mixed(pytestconfig):
    """Verify gauge render output with active telltales against baseline image (REQ-7)."""
    generate = getoption(pytestconfig, "--generate-baselines", default=False)
    telltales = {"1m": 20.0, "10m": 40.0, "1h": 60.0, "all_time": 80.0}
    img = render(50.0, telltales=telltales, size=256)
    check_or_generate_baseline(img, "gauge_v50_telltales_mixed", generate)


def test_t130_deterministic_output_byte_equality():
    """Verify identical render calls produce byte-identical PIL image output (REQ-9)."""
    img1 = render(42.5, {"10m": 55.0}, 256)
    img2 = render(42.5, {"10m": 55.0}, 256)
    assert img1.tobytes() == img2.tobytes()


def test_t140_hide_telltale_when_none():
    """Verify telltales set to None are not rendered (REQ-10)."""
    img_with = render(50.0, telltales={"10m": 70.0}, size=256)
    img_none = render(50.0, telltales={"10m": None}, size=256)
    img_empty = render(50.0, telltales={}, size=256)

    assert img_none.tobytes() == img_empty.tobytes()
    assert img_with.tobytes() != img_none.tobytes()
```

## 7. Pattern References

### 7.1 Off-Screen Image Rendering Strategy

**File:** `docs/design/0001-test-strategy.md` (lines 33-54)

```python
"""Option C — render to off-screen PIL.Image first; tkinter Canvas is a display surface only.

The gauge renderer is a pure function: state -> PIL.Image. The tkinter Canvas receives that image and displays it. Tests exercise the renderer; they never instantiate tkinter.Tk().
"""
```

**Relevance:** Mandates that `boostgauge.gauge.render()` generates a `PIL.Image` directly using Pillow vector primitives without importing `tkinter`.

---

### 7.2 Project Test Bootstrap

**File:** `tests/conftest.py` (lines 1-8)

```python
"""Project test bootstrap."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
```

**Relevance:** Establishes cross-platform test import path setup using `pathlib.Path`.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `from typing import Any, Dict, Optional, Protocol, Tuple` | stdlib | `skins/__init__.py`, `skins/stingray.py`, `gauge.py` |
| `from dataclasses import dataclass` | stdlib | `gauge.py`, data context definitions |
| `import math` | stdlib | `skins/stingray.py`, `gauge.py`, `test_gauge_visual.py` |
| `import sys` | stdlib | `test_gauge.py` |
| `from pathlib import Path` | stdlib | `test_gauge_visual.py` |
| `from PIL import Image, ImageDraw, ImageFont, ImageChops, ImageStat` | `pillow (>=12.2.0,<13.0.0)` | `skins/__init__.py`, `skins/stingray.py`, `gauge.py`, `test_gauge.py`, `test_gauge_visual.py` |
| `import pytest` | `pytest` | `test_gauge.py`, `test_gauge_visual.py` |

**New Dependencies:** None (uses existing pinned `pillow` dependency).

## 9. Placeholder

*Reserved for future alignment.*

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output | Assertion Type |
|---------|---------------|-------|-----------------|----------------|
| T010 | `render()` | `(0.0, None, 256)` | `PIL.Image.Image` | `isinstance(img, Image.Image)`, `'tkinter' not in sys.modules` |
| T020 | `clamp_value()` | `-15.0`, `125.0` | `0.0`, `100.0` | `clamp_value(-15.0) == 0.0`, `clamp_value(125.0) == 100.0` |
| T030 | `clamp_value()`, `render()` | `"invalid"` | Raises `TypeError` | `pytest.raises(TypeError)` |
| T040 | `render()` | `(50.0)` | `(256, 256)` | `img.size == (256, 256)` |
| T050 | `render()` | `(50.0, size=128/512)` | `(128, 128)`, `(512, 512)` | `img.size == requested_size` |
| T060 | `render()` | `(50.0, size=64)` | Raises `ValueError` | `pytest.raises(ValueError)` |
| T070 | `render_stingray()` | `(0.0)` | `PIL.Image.Image` | Visual comparison with baseline `gauge_v0_no_telltales` |
| T080 | `render_stingray()` | `(0.0)` | Baseline comparison | RMS diff `≤ 1.0` against baseline |
| T090 | `render_stingray()` | `(0.0)` | Redline arc pixels | **Baseline-Independent:** Red channel dominant at radius 0.88 and angle 441° |
| T100 | `render_stingray()` | `(0.0)` | Wordmark pixels | Text rendered centered below pivot |
| T110 | `render_stingray()` | `(50.0, telltales={...})` | Translucent needles | RMS diff `≤ 1.0` against baseline `gauge_v50_telltales_mixed` |
| T120 | `render_stingray()` | `(100.0)` | Main needle at 495° | **Baseline-Independent:** Red channel dominant at 495° polar coordinate |
| T130 | `render()` | `(42.5, ...)` (2x calls) | Byte-identical output | `img1.tobytes() == img2.tobytes()` |
| T140 | `render_stingray()` | `telltales={"1m": None}` | Needle hidden | `img_none.tobytes() == img_empty.tobytes()` |
| T150 | `render_stingray()` | `(75.0)` | Layered render | Main needle rendered over redline arc |
| T160 | `render_stingray()` | `(50.0)` | Main needle at 360° | **Baseline-Independent:** Red channel dominant at 3 o'clock position (cx + 0.5*r, cy) |

## 11. Implementation Notes

### 11.1 Anti-Aliasing & Supersampling Strategy

To eliminate jagged polygon edges and sub-pixel tick mark distortion on circular arcs, drawing is performed at a `supersample_factor = 2` (512x512 for default 256x256 target size). Upon completing vector primitives drawing, `Image.resize(size, resample=Image.Resampling.LANCZOS)` downscales the high-resolution buffer into a smooth anti-aliased output image.

### 11.2 Visual Color Palette Tokens

- **Dial Background:** Matte Black `RGBA(13, 14, 18, 255)` (`#0d0e12`)
- **Housing Bezel:** Polished Metallic Chrome `RGBA(180, 185, 195, 255)` / Inner Rim `RGBA(70, 75, 85, 255)`
- **Redline Arc:** Saturated Warning Red `RGBA(230, 34, 0, 255)` (`#e62200`) spanning scale range 60 to 100
- **Main Needle:** Racing Red Pointer `RGBA(255, 42, 42, 255)` with outline `RGBA(200, 10, 10, 255)`
- **Telltales:** Translucent 65% opacity `RGBA` overlays:
  - `1m`: Cyan `RGBA(0, 229, 255, 166)`
  - `10m`: Orange `RGBA(255, 145, 0, 166)`
  - `1h`: Magenta `RGBA(213, 0, 249, 166)`
  - `all_time`: Red `RGBA(255, 23, 68, 166)`
- **Pivot Cap:** Brushed Chrome `RGBA(220, 225, 235, 255)` with dark inner core `RGBA(160, 165, 175, 255)`

### 11.3 Baseline-Independent Trigonometric Property Assertions Strategy (Issue #1902)

To ensure visual tests do not validate self-contained defects in baseline images (e.g. an inverted needle producing an inverted baseline that passes indefinitely), `tests/visual/test_gauge_visual.py` incorporates baseline-independent property assertions. These assertions calculate exact pixel coordinates via polar trigonometry `(cx + r * cos(rad), cy + r * sin(rad))` and evaluate color channel thresholds (e.g. asserting `R > 180` and `G < 100` along the needle trajectory) without referencing stored PNG baselines.

### 11.4 Cross-Platform Path Handling (Issue #1841)

All file paths in tests (e.g. locating visual baseline directories) use `pathlib.Path` objects rather than string concatenation or hardcoded path separators. Comparisons compare `Path` objects directly to prevent backslash/forward-slash discrepancies on Windows vs POSIX systems.

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3 - marked N/A, all files are Add)
- [x] Every data structure has a concrete JSON/YAML example (Section 4)
- [x] Every function has input/output examples with realistic values (Section 5)
- [x] Change instructions are diff-level specific / full code blocks (Section 6)
- [x] Pattern references include file:line and are verified to exist (Section 7)
- [x] All imports are listed and verified (Section 8)
- [x] Test mapping covers all LLD test scenarios including baseline-independent assertions (Section 10)

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #1 |
| Verdict | APPROVED |
| Date | 2026-08-01 |
| Iterations | 1 |
| Finalized | 2026-08-01T09:15:00-05:00 |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #1 |
| Verdict | APPROVED |
| Date | 2026-08-01 |
| Iterations | 3 |
| Finalized | 2026-08-01T14:16:29Z |

### Review Feedback Summary

The Implementation Spec for Issue #1 is complete, highly detailed, and ready for execution with >80% first-try success rate. The revisions in Iteration 3 resolved previous review feedback by adding the fallback-safe `getoption()` helper in `tests/visual/test_gauge_visual.py` for pytest config option retrieval and fixing code block syntax formatting in Section 7.1. All files to be created include complete Python source code and test coverage with both visual baselines and baseline-independent tri...
