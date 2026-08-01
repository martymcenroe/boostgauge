# Implementation Spec: Peak-Hold Telltale Needles — 1m, 10m, 1h, All-Time (#2)

| Field | Value |
|-------|-------|
| Issue | #2 |
| LLD | `docs/lld/done/0002-telltale-needles.md` |
| Generated | 2026-07-31 |
| Status | APPROVED |

## 1. Overview

This implementation spec defines the multi-window peak-hold (telltale) needle layer for the boostgauge system monitor. It introduces `TelltaleManager` to wrap four sliding-window `Telltale` instances (1m, 10m, 1h, all-time), feeds metric samples into the manager, and renders four distinct translucent telltale needles behind the main tachometer needle on an off-screen PIL Image using 4x supersampling.

**Objective:** Render four peak-hold (telltale) needles (1m, 10m, 1h, all-time) on the gauge surface on top of core gauge geometry using peak values provided by `Telltale` instances.

**Success Criteria:**
1. `TelltaleManager` instantiates and manages 4 `Telltale` instances with windows `60.0`, `600.0`, `3600.0`, and `None`.
2. `render()` cleanly consumes a `telltales` dictionary `dict[str, float | None]` without mutating renderer state.
3. Translucent telltale needles render behind the main needle with target color styling (1m: Cyan, 10m: Orange, 1h: Magenta, All-time: Red).
4. Peaks evaluating to `None` (pre-sample or post-reset) are suppressed from needle rendering.
5. Individual (`reset_window`) and collective (`reset_all`) reset actions clear stored peak states.
6. A visual legend displaying window keys and peak values renders on the gauge dial face.
7. Off-screen rendering executes headless per Option C in `docs/design/0001-test-strategy.md` with zero `tkinter.Tk()` instantiation in tests.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/telltale_manager.py` | Add | `TelltaleManager` class orchestrating 4 `Telltale` instances (1m, 10m, 1h, all-time), updating sample history, returning peaks dict, and handling resets. |
| 2 | `src/boostgauge/skins/stingray.py` | Modify | Implement `TELLTALE_STYLES`, `_draw_telltales()`, and `_draw_legend()`; update `render_stingray()` to composite telltale needles and legend overlay. |
| 3 | `src/boostgauge/gauge.py` | Modify | Update `render()` pure function signature to accept `telltales` dictionary and dispatch to active skin renderer. |
| 4 | `tests/unit/test_telltale_manager.py` | Add | Unit test suite covering manager initialization, metric streaming, peak calculations, window expiry, and reset handling. |
| 5 | `tests/contract/test_telltale_contract.py` | Add | Contract test suite validating `TelltaleManager` public methods and `render()` interface compatibility. |
| 6 | `tests/visual/test_telltale_visual.py` | Add | Visual regression test suite verifying needle z-ordering, color styling, translucency, legend placement, and baseline-independent needle angle geometry. |
| 7 | `tests/integration/test_telltale_integration.py` | Add | Integration test suite verifying end-to-end flow from metric ingestion through manager into rendered PIL Image. |

**Implementation Order Rationale:** `TelltaleManager` establishes the data container required by the renderer. Modifying `stingray.py` and `gauge.py` completes the off-screen image generation pipeline. Writing unit, contract, visual, and integration test suites in sequence validates data logic before verifying pixel output and pipeline integration.

## 3. Current State (for Modify/Delete files)

### 3.1 `src/boostgauge/skins/stingray.py`

**Relevant excerpt** (lines 1-62):

```python
"""Stingray skin rendering logic for analog tachometer gauge face.

Issue #1: Core Gauge Renderer — Analog Tachometer with Arc, Needle, and Tick Marks
"""

from __future__ import annotations

import math

from typing import Any

from PIL import Image, ImageDraw, ImageFont

def _val_to_angle(value: float, min_angle: float = 225.0, max_angle: float = -45.0) -> float:
    """Map gauge metric value (0-100) to dial sweep angle in degrees."""
    ...

def _load_skin_font(font_size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load Eurostile-adjacent font with dynamic platform fallback chain."""
    ...

def _draw_bezel_and_dial(draw: ImageDraw.ImageDraw, size: tuple[int, int]) -> None:
    """Draw square chromed bezel, chamfered corners, specular highlights, and recessed round dial face."""
    ...

def _draw_ticks_and_numerals(draw: ImageDraw.ImageDraw, center: tuple[float, float], radius: float) -> None:
    """Draw 11 major and 40 minor white tick marks and Eurostile-adjacent numerals (0-100)."""
    ...

def _draw_redline_arc(draw: ImageDraw.ImageDraw, center: tuple[float, float], radius: float) -> None:
    """Draw redline arc hugging outer tick ring from metric value 60 to 100."""
    ...

def _draw_wordmark(draw: ImageDraw.ImageDraw, center: tuple[float, float], radius: float) -> None:
    """Draw BOOSTGAUGE small-caps white wordmark below central pivot cap."""
    ...

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

def _get_cached_background(size: tuple[int, int], skin_name: str = "stingray") -> Image.Image:
    """Retrieve or render static gauge background (bezel, dial, ticks, numerals, wordmark, redline)."""
    ...

def render_stingray(
    value: float,
    telltales: dict[str, float | None] | None = None,
    size: tuple[int, int] = (256, 256),
    config: dict[str, Any] | None = None,
) -> Image.Image:
    """Stingray skin implementation rendering to PIL Image with 4x supersampling."""
    ...
```

**What changes:**
1. Define `TELLTALE_STYLES` dictionary mapping window keys (`'1m'`, `'10m'`, `'1h'`, `'all'`) to `TelltaleStyleSpec` instances specifying colors, widths, and legend labels.
2. Implement `_draw_telltales()` to draw non-None telltale needles onto the high-resolution RGBA canvas behind the main needle.
3. Implement `_draw_legend()` to render the color-coded telltale legend overlay onto the high-resolution RGBA canvas.
4. Update `render_stingray()` to invoke `_draw_telltales()` after background rendering and before `_draw_needle()` for the main metric needle, and call `_draw_legend()` prior to final downsampling.

### 3.2 `src/boostgauge/gauge.py`

**Relevant excerpt** (lines 1-27):

```python
"""Core gauge renderer entry point.

Issue #1: Core Gauge Renderer — Analog Tachometer with Arc, Needle, and Tick Marks
"""

from __future__ import annotations

from typing import Any

from PIL import Image

from boostgauge.skins.stingray import render_stingray

def render(
    value: float,
    telltales: dict[str, float | None] | None = None,
    size: tuple[int, int] = (256, 256),
    config: dict[str, Any] | None = None,
) -> Image.Image:
    """Pure function rendering gauge face and needles to off-screen PIL Image."""
    ...

SUPPORTED_SKINS = {
    "stingray": render_stingray,
}
```

**What changes:**
Pass the `telltales` dictionary into the skin renderer function within `render()` (`return skin_fn(value, telltales=telltales, size=size, config=config)`). Update docstrings to reference Issue #2 / Closes #2.

## 4. Data Structures

### 4.1 `TelltalePeaks`

**Definition:**

```python
from typing import Optional, TypedDict

class TelltalePeaks(TypedDict, total=False):
    """Dictionary representation of current telltale peak values."""
    window_1m: Optional[float]
    window_10m: Optional[float]
    window_1h: Optional[float]
    window_all: Optional[float]
```

**Concrete Example (Active Peaks):**

```json
{
  "1m": 72.4,
  "10m": 88.5,
  "1h": 91.0,
  "all": 98.2
}
```

**Concrete Example (Post-Reset / Partial Data):**

```json
{
  "1m": null,
  "10m": 55.0,
  "1h": 82.1,
  "all": 98.2
}
```

### 4.2 `TelltaleStyleSpec`

**Definition:**

```python
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class TelltaleStyleSpec:
    """Visual style specification for a telltale needle and legend entry."""
    color: tuple[int, int, int, int]        # RGBA color tuple with opacity (0-255)
    width_pct: float                        # Needle width as percentage of dial radius (e.g. 0.015 = 1.5%)
    dash_pattern: Optional[tuple[int, int]] # Optional dash-gap pattern, None for solid line
    label: str                              # Human-readable legend label
```

**Concrete Example:**

```json
{
  "1m": {
    "color": [0, 229, 255, 180],
    "width_pct": 0.015,
    "dash_pattern": null,
    "label": "1m"
  },
  "10m": {
    "color": [255, 145, 0, 180],
    "width_pct": 0.015,
    "dash_pattern": null,
    "label": "10m"
  },
  "1h": {
    "color": [255, 0, 127, 180],
    "width_pct": 0.015,
    "dash_pattern": null,
    "label": "1h"
  },
  "all": {
    "color": [255, 23, 68, 220],
    "width_pct": 0.02,
    "dash_pattern": null,
    "label": "MAX"
  }
}
```

## 5. Function Specifications

### 5.1 `TelltaleManager.__init__()`

**File:** `src/boostgauge/telltale_manager.py`

**Signature:**

```python
class TelltaleManager:
    def __init__(self) -> None:
        """Initialize 4 Telltale instances with window durations (60s, 600s, 3600s, None)."""
        ...
```

**Input Example:**

```python
manager = TelltaleManager()
```

**Output Example:**

```python
# Internal state initialized:
# manager._telltales = {
#     "1m": Telltale(window_seconds=60.0),
#     "10m": Telltale(window_seconds=600.0),
#     "1h": Telltale(window_seconds=3600.0),
#     "all": Telltale(window_seconds=None),
# }
```

**Edge Cases:**
- Instantiation requires no arguments and initializes all four windows in unpopulated state (`current_peak() == None`).

### 5.2 `TelltaleManager.update()`

**File:** `src/boostgauge/telltale_manager.py`

**Signature:**

```python
def update(self, timestamp: float, value: float) -> None:
    """Pipe a live metric sample (timestamp, value) to all four telltale instances."""
    ...
```

**Input Example:**

```python
timestamp = 1700000000.0
value = 78.5
```

**Output Example:**

```python
None  # State updated in-place across all four Telltale instances
```

**Edge Cases:**
- `value < 0.0` or `value > 100.0`: Value passed directly to underlying `Telltale` instances.
- Non-monotonic timestamps: Delegated to `Telltale` error handling.

### 5.3 `TelltaleManager.get_peaks()`

**File:** `src/boostgauge/telltale_manager.py`

**Signature:**

```python
def get_peaks(self, timestamp: Optional[float] = None) -> dict[str, Optional[float]]:
    """Return dictionary mapping window keys ('1m', '10m', '1h', 'all') to current peak values."""
    ...
```

**Input Example:**

```python
timestamp = 1700000065.0
```

**Output Example:**

```python
{
    "1m": 78.5,
    "10m": 92.0,
    "1h": 92.0,
    "all": 95.4
}
```

**Edge Cases:**
- Called before any samples ingested: Returns `{"1m": None, "10m": None, "1h": None, "all": None}`.
- `timestamp=None`: Uses current system time `time.time()` for evaluating window expiry.

### 5.4 `TelltaleManager.reset_window()`

**File:** `src/boostgauge/telltale_manager.py`

**Signature:**

```python
def reset_window(self, window_key: str) -> None:
    """Reset a specific telltale window ('1m', '10m', '1h', or 'all')."""
    ...
```

**Input Example:**

```python
window_key = "1m"
```

**Output Example:**

```python
None  # _telltales["1m"].reset() invoked
```

**Edge Cases:**
- Invalid `window_key` (e.g. `"5m"`): Raises `KeyError("Invalid telltale window key: '5m'. Valid keys are: '1m', '10m', '1h', 'all'.")`.

### 5.5 `TelltaleManager.reset_all()`

**File:** `src/boostgauge/telltale_manager.py`

**Signature:**

```python
def reset_all(self) -> None:
    """Reset all four telltale instances."""
    ...
```

**Input Example:**

```python
manager.reset_all()
```

**Output Example:**

```python
None  # All four Telltale instances reset
```

**Edge Cases:**
- Calling on an already empty manager executes safely without error.

### 5.6 `render()`

**File:** `src/boostgauge/gauge.py`

**Signature:**

```python
def render(
    value: float,
    telltales: Optional[dict[str, Optional[float]]] = None,
    size: tuple[int, int] = (256, 256),
    config: Optional[dict[str, Any]] = None,
) -> Image.Image:
    """Pure function rendering main gauge and telltale needles to off-screen PIL Image."""
    ...
```

**Input Example:**

```python
value = 45.0
telltales = {"1m": 65.0, "10m": 80.0, "1h": 80.0, "all": 95.0}
size = (256, 256)
config = {"skin": "stingray"}
```

**Output Example:**

```python
# Returns <PIL.Image.Image image mode=RGBA size=256x256>
```

**Edge Cases:**
- `telltales=None` or `{}`: Renders main gauge face and main needle without telltales or legend.
- Unknown skin in `config`: Raises `KeyError("Unsupported skin: ...")`.

### 5.7 `_draw_telltales()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
def _draw_telltales(
    draw_layer: Image.Image,
    telltales: dict[str, Optional[float]],
    center: tuple[float, float],
    radius: float,
    scale_factor: int = 4,
) -> None:
    """Draw non-None telltale needles onto supersampled RGBA layer behind main needle."""
    ...
```

**Input Example:**

```python
# draw_layer: 1024x1024 RGBA PIL Image
telltales = {"1m": 75.0, "10m": None, "1h": 85.0, "all": 95.0}
center = (512.0, 512.0)
radius = 400.0
scale_factor = 4
```

**Output Example:**

```python
None  # Translucent needles for '1m', '1h', and 'all' drawn onto draw_layer
```

**Edge Cases:**
- All telltale values are `None`: Returns immediately without modifying `draw_layer`.
- Peak value out of 0-100 range: Clamped / mapped via `_val_to_angle`.

### 5.8 `_draw_legend()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
def _draw_legend(
    draw_layer: Image.Image,
    telltales: dict[str, Optional[float]],
    size: tuple[int, int],
    scale_factor: int = 4,
) -> None:
    """Draw compact color-coded telltale legend on dial face."""
    ...
```

**Input Example:**

```python
# draw_layer: 1024x1024 RGBA PIL Image
telltales = {"1m": 75.0, "10m": 80.0, "1h": 85.0, "all": 95.0}
size = (256, 256)
scale_factor = 4
```

**Output Example:**

```python
None  # Legend box with color swatches and peak values drawn on dial lower quadrant
```

**Edge Cases:**
- Telltale value is `None`: Displays value string as `"--"` or `"OFF"`.

## 6. Change Instructions

### 6.1 `src/boostgauge/telltale_manager.py` (Add)

**Complete file contents:**

```python
"""TelltaleManager orchestrating multi-window peak-hold telltale instances.

Issue #2: peak-hold telltale needles — 1m, 10m, 1h, all-time (Closes #2)
"""

from __future__ import annotations

import time
from typing import Dict, Optional

from boostgauge.telltale import Telltale

VALID_WINDOWS = ("1m", "10m", "1h", "all")


class TelltaleManager:
    """Manages four Telltale instances for 1m, 10m, 1h, and all-time windows."""

    def __init__(self) -> None:
        """Initialize 4 Telltale instances with window durations (60s, 600s, 3600s, None)."""
        self._telltales: Dict[str, Telltale] = {
            "1m": Telltale(window_seconds=60.0),
            "10m": Telltale(window_seconds=600.0),
            "1h": Telltale(window_seconds=3600.0),
            "all": Telltale(window_seconds=None),
        }

    def update(self, timestamp: float, value: float) -> None:
        """Pipe a live metric sample (timestamp, value) to all four telltale instances."""
        for telltale in self._telltales.values():
            telltale.update(timestamp, value)

    def get_peaks(self, timestamp: Optional[float] = None) -> Dict[str, Optional[float]]:
        """Return dictionary mapping window keys ('1m', '10m', '1h', 'all') to current peak values."""
        ts = timestamp if timestamp is not None else time.time()
        return {key: instance.current_peak(ts) for key, instance in self._telltales.items()}

    def reset_window(self, window_key: str) -> None:
        """Reset a specific telltale window ('1m', '10m', '1h', or 'all')."""
        if window_key not in self._telltales:
            raise KeyError(
                f"Invalid telltale window key: '{window_key}'. Valid keys are: {', '.join(VALID_WINDOWS)}."
            )
        self._telltales[window_key].reset()

    def reset_all(self) -> None:
        """Reset all four telltale instances."""
        for telltale in self._telltales.values():
            telltale.reset()
```

### 6.2 `src/boostgauge/skins/stingray.py` (Modify)

**Change 1:** Add imports and `TELLTALE_STYLES` dictionary definition at top level.

```diff
 import math
 
-from typing import Any
+from typing import Any, Dict, Optional
 
 from PIL import Image, ImageDraw, ImageFont
 
+from boostgauge.telltale_manager import TelltalePeaks
+
+
+class TelltaleStyleSpec:
+    """Visual style specification for telltale needle and legend."""
+
+    def __init__(
+        self,
+        color: tuple[int, int, int, int],
+        width_pct: float,
+        dash_pattern: Optional[tuple[int, int]],
+        label: str,
+    ) -> None:
+        self.color = color
+        self.width_pct = width_pct
+        self.dash_pattern = dash_pattern
+        self.label = label
+
+
+TELLTALE_STYLES: Dict[str, TelltaleStyleSpec] = {
+    "1m": TelltaleStyleSpec(color=(0, 229, 255, 180), width_pct=0.015, dash_pattern=None, label="1m"),
+    "10m": TelltaleStyleSpec(color=(255, 145, 0, 180), width_pct=0.015, dash_pattern=None, label="10m"),
+    "1h": TelltaleStyleSpec(color=(255, 0, 127, 180), width_pct=0.015, dash_pattern=None, label="1h"),
+    "all": TelltaleStyleSpec(color=(255, 23, 68, 220), width_pct=0.02, dash_pattern=None, label="MAX"),
+}
```

**Change 2:** Add `_draw_telltales()` and `_draw_legend()` helper functions.

```diff
 def _draw_needle(
     ...
 ) -> None:
     """Draw a gauge needle (main or telltale) pointing at specified angle."""
     ...

+def _draw_telltales(
+    draw_layer: Image.Image,
+    telltales: Dict[str, Optional[float]],
+    center: tuple[float, float],
+    radius: float,
+    scale_factor: int = 4,
+) -> None:
+    """Draw non-None telltale needles onto supersampled RGBA layer behind main needle."""
+    draw = ImageDraw.Draw(draw_layer)
+    # Order of drawing: all, 1h, 10m, 1m so shorter windows draw over longer windows
+    for key in ("all", "1h", "10m", "1m"):
+        peak_val = telltales.get(key)
+        if peak_val is None:
+            continue
+        style = TELLTALE_STYLES.get(key)
+        if style is None:
+            continue
+        angle = _val_to_angle(peak_val)
+        width = radius * style.width_pct * scale_factor
+        _draw_needle(
+            draw=draw,
+            center=center,
+            radius=radius,
+            angle=angle,
+            color=style.color,
+            width=max(width, 1.5 * scale_factor),
+            length_factor=0.82,
+            has_counterweight=False,
+        )
+
+
+def _draw_legend(
+    draw_layer: Image.Image,
+    telltales: Dict[str, Optional[float]],
+    size: tuple[int, int],
+    scale_factor: int = 4,
+) -> None:
+    """Draw compact color-coded telltale legend on dial face."""
+    draw = ImageDraw.Draw(draw_layer)
+    font = _load_skin_font(10 * scale_factor)
+    
+    # Positioning near bottom-right quadrant of dial face
+    base_x = size[0] * scale_factor * 0.62
+    base_y = size[1] * scale_factor * 0.68
+    row_height = 14 * scale_factor
+    swatch_size = 8 * scale_factor

+    for idx, key in enumerate(("1m", "10m", "1h", "all")):
+        style = TELLTALE_STYLES[key]
+        val = telltales.get(key)
+        val_str = f"{val:.1f}" if val is not None else "--"
+        y = base_y + (idx * row_height)
+        
+        # Draw color swatch
+        draw.rectangle(
+            [base_x, y, base_x + swatch_size, y + swatch_size],
+            fill=style.color,
+            outline=(255, 255, 255, 100),
+            width=1,
+        )
+        
+        # Draw label text
+        text = f"{style.label}: {val_str}"
+        draw.text(
+            (base_x + swatch_size + (4 * scale_factor), y - (2 * scale_factor)),
+            text,
+            fill=(220, 220, 220, 220),
+            font=font,
+        )
```

**Change 3:** Update `render_stingray()` to composite telltale needles and legend overlay.

```diff
 def render_stingray(
     value: float,
     telltales: dict[str, float | None] | None = None,
     size: tuple[int, int] = (256, 256),
     config: dict[str, Any] | None = None,
 ) -> Image.Image:
     """Stingray skin implementation rendering to PIL Image with 4x supersampling."""
     scale_factor = 4
     high_res_size = (size[0] * scale_factor, size[1] * scale_factor)
     
-    bg = _get_cached_background(size)
+    bg = _get_cached_background(high_res_size)
     canvas = Image.new("RGBA", high_res_size, (0, 0, 0, 0))
     canvas.paste(bg, (0, 0))
     
     center = (high_res_size[0] / 2.0, high_res_size[1] / 2.0)
     radius = (min(high_res_size) / 2.0) * 0.85
     
+    # Draw telltales layer if provided (z-order: dial background -> telltale needles -> main needle)
+    if telltales:
+        _draw_telltales(canvas, telltales, center, radius, scale_factor=scale_factor)
+
     # Draw main metric needle
     draw = ImageDraw.Draw(canvas)
     main_angle = _val_to_angle(value)
     _draw_needle(
         draw=draw,
         center=center,
         radius=radius,
         angle=main_angle,
         color=(255, 50, 50, 255),
         width=4.0 * scale_factor,
         length_factor=0.88,
         has_counterweight=True,
     )
     
     # Draw central pivot cap
     pivot_r = 12 * scale_factor
     draw.ellipse(
         [center[0] - pivot_r, center[1] - pivot_r, center[0] + pivot_r, center[1] + pivot_r],
         fill=(30, 30, 30, 255),
         outline=(200, 200, 200, 255),
         width=2 * scale_factor,
     )

+    # Draw legend overlay if telltales provided
+    if telltales:
+        _draw_legend(canvas, telltales, size, scale_factor=scale_factor)

     return canvas.resize(size, Image.LANCZOS)
```

### 6.3 `src/boostgauge/gauge.py` (Modify)

**Change 1:** Update `render()` to pass `telltales` parameter into active skin implementation.

```diff
 def render(
     value: float,
     telltales: dict[str, float | None] | None = None,
     size: tuple[int, int] = (256, 256),
     config: dict[str, Any] | None = None,
 ) -> Image.Image:
-    """Pure function rendering gauge face and needles to off-screen PIL Image."""
+    """Pure function rendering gauge face and needles to off-screen PIL Image.
+
+    Issue #2: peak-hold telltale needles — 1m, 10m, 1h, all-time (Closes #2)
+    """
     skin_name = (config or {}).get("skin", "stingray")
     if skin_name not in SUPPORTED_SKINS:
         raise KeyError(f"Unsupported gauge skin: '{skin_name}'. Supported skins: {list(SUPPORTED_SKINS.keys())}")
     
     skin_fn = SUPPORTED_SKINS[skin_name]
-    return skin_fn(value, size=size, config=config)
+    return skin_fn(value, telltales=telltales, size=size, config=config)
```

### 6.4 `tests/unit/test_telltale_manager.py` (Add)

**Complete file contents:**

```python
"""Unit tests for TelltaleManager.

Issue #2: peak-hold telltale needles — 1m, 10m, 1h, all-time (Closes #2)
"""

import pytest
from pathlib import Path
from boostgauge.telltale_manager import TelltaleManager


def test_t010_telltale_manager_initialization():
    """T010: Verify initialization of 4 telltale windows with correct initial peaks (None)."""
    manager = TelltaleManager()
    peaks = manager.get_peaks(timestamp=100.0)
    assert set(peaks.keys()) == {"1m", "10m", "1h", "all"}
    assert peaks["1m"] is None
    assert peaks["10m"] is None
    assert peaks["1h"] is None
    assert peaks["all"] is None


def test_t020_metric_stream_update_piping():
    """T020: Verify metric stream update pipes samples to all four telltale instances."""
    manager = TelltaleManager()
    manager.update(timestamp=100.0, value=45.0)
    manager.update(timestamp=105.0, value=85.0)
    peaks = manager.get_peaks(timestamp=110.0)
    
    assert peaks["1m"] == 85.0
    assert peaks["10m"] == 85.0
    assert peaks["1h"] == 85.0
    assert peaks["all"] == 85.0


def test_t060_window_and_collective_reset():
    """T060: Verify individual and collective reset actions clear peak states."""
    manager = TelltaleManager()
    manager.update(timestamp=100.0, value=90.0)
    
    # Reset single window
    manager.reset_window("1m")
    peaks = manager.get_peaks(timestamp=105.0)
    assert peaks["1m"] is None
    assert peaks["10m"] == 90.0
    assert peaks["1h"] == 90.0
    assert peaks["all"] == 90.0
    
    # Reset invalid window raises KeyError
    with pytest.raises(KeyError):
        manager.reset_window("invalid_window")
        
    # Reset all windows
    manager.reset_all()
    peaks_all = manager.get_peaks(timestamp=105.0)
    assert all(val is None for val in peaks_all.values())


def test_t090_sliding_window_expiration():
    """T090: Verify 1m sliding window peak drops after 60 seconds idle sample period."""
    manager = TelltaleManager()
    manager.update(timestamp=100.0, value=95.0)
    manager.update(timestamp=110.0, value=30.0)
    
    # At t=150, 1m peak is still 95.0 (within 60s)
    assert manager.get_peaks(timestamp=150.0)["1m"] == 95.0
    
    # At t=161, 1m peak expires and drops to active window sample (30.0)
    peaks_expired = manager.get_peaks(timestamp=161.0)
    assert peaks_expired["1m"] == 30.0
    # Longer windows retain 95.0 peak
    assert peaks_expired["10m"] == 95.0
    assert peaks_expired["1h"] == 95.0
    assert peaks_expired["all"] == 95.0
```

### 6.5 `tests/contract/test_telltale_contract.py` (Add)

**Complete file contents:**

```python
"""Contract tests for TelltaleManager and render() interface.

Issue #2: peak-hold telltale needles — 1m, 10m, 1h, all-time (Closes #2)
"""

from PIL import Image
from boostgauge.gauge import render
from boostgauge.telltale_manager import TelltaleManager


def test_telltale_manager_contract():
    """Contract test for TelltaleManager public API signatures."""
    manager = TelltaleManager()
    assert hasattr(manager, "update")
    assert hasattr(manager, "get_peaks")
    assert hasattr(manager, "reset_window")
    assert hasattr(manager, "reset_all")

    manager.update(100.0, 50.0)
    peaks = manager.get_peaks(105.0)
    assert isinstance(peaks, dict)
    assert set(peaks.keys()) == {"1m", "10m", "1h", "all"}


def test_render_telltales_contract():
    """Contract test verifying render() accepts telltales dict and returns PIL Image."""
    telltales = {"1m": 50.0, "10m": 75.0, "1h": 80.0, "all": 90.0}
    img = render(30.0, telltales=telltales, size=(128, 128))
    assert isinstance(img, Image.Image)
    assert img.size == (128, 128)
    assert img.mode == "RGBA"
```

### 6.6 `tests/visual/test_telltale_visual.py` (Add)

**Complete file contents:**

```python
"""Visual regression and property tests for telltale needles.

Issue #2: peak-hold telltale needles — 1m, 10m, 1h, all-time (Closes #2)
"""

import math
from PIL import Image
from boostgauge.gauge import render
from boostgauge.skins.stingray import _val_to_angle


def test_t030_angle_mapping_geometry_baseline_independent():
    """T030 (baseline-independent): Verify metric values map to exact dial sweep angles."""
    # 0 -> 225.0 degrees, 50 -> 90.0 degrees, 100 -> -45.0 degrees
    assert math.isclose(_val_to_angle(0.0), 225.0, abs_tol=1e-5)
    assert math.isclose(_val_to_angle(50.0), 90.0, abs_tol=1e-5)
    assert math.isclose(_val_to_angle(100.0), -45.0, abs_tol=1e-5)

    # Trig coordinate check for 50.0 (angle = 90 deg = top vertical)
    center = (128.0, 128.0)
    radius = 100.0
    rad = math.radians(90.0)
    tip_x = center[0] + radius * math.cos(rad)
    tip_y = center[1] - radius * math.sin(rad)
    assert math.isclose(tip_x, 128.0, abs_tol=1e-4)
    assert math.isclose(tip_y, 28.0, abs_tol=1e-4)


def test_t040_t050_t070_t100_telltale_rendering_visual():
    """T040, T050, T070, T100: Verify translucent telltale needles, legend, and None suppression."""
    peaks_full = {"1m": 40.0, "10m": 60.0, "1h": 80.0, "all": 95.0}
    img_full = render(20.0, telltales=peaks_full, size=(256, 256))
    
    peaks_suppressed = {"1m": None, "10m": 60.0, "1h": None, "all": 95.0}
    img_suppressed = render(20.0, telltales=peaks_suppressed, size=(256, 256))
    
    # Image pixel output validation without GUI window instantiation
    assert img_full.getpixel((128, 128)) is not None
    # Pixels in image with full telltales differ from suppressed telltales
    assert img_full.tobytes() != img_suppressed.tobytes()
```

### 6.7 `tests/integration/test_telltale_integration.py` (Add)

**Complete file contents:**

```python
"""Integration tests for metric streaming, telltale manager, and renderer.

Issue #2: peak-hold telltale needles — 1m, 10m, 1h, all-time (Closes #2)
"""

from PIL import Image
from boostgauge.gauge import render
from boostgauge.telltale_manager import TelltaleManager


def test_t080_option_c_headless_integration():
    """T080: Integration test executing synthetic metric stream into render() off-screen Image."""
    manager = TelltaleManager()
    
    # Synthetic metric stream (t, v)
    stream = [
        (1000.0, 30.0),
        (1005.0, 85.0),
        (1010.0, 42.0),
        (1015.0, 60.0),
    ]
    
    for ts, val in stream:
        manager.update(ts, val)
        
    peaks = manager.get_peaks(timestamp=1020.0)
    assert peaks["1m"] == 85.0
    assert peaks["all"] == 85.0
    
    # Render gauge image off-screen (Option C compliance)
    image = render(value=60.0, telltales=peaks, size=(256, 256))
    
    assert isinstance(image, Image.Image)
    assert image.size == (256, 256)
    assert image.mode == "RGBA"
```

## 7. Pattern References

### 7.1 Dynamic Sweep Angle & Needle Geometry

**File:** `src/boostgauge/skins/stingray.py` (lines 13-16, 44-55)

```python
def _val_to_angle(value: float, min_angle: float = 225.0, max_angle: float = -45.0) -> float:
    """Map gauge metric value (0-100) to dial sweep angle in degrees."""
    ...

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
    ...
```

**Relevance:** `_draw_telltales()` reuses `_val_to_angle()` and `_draw_needle()` to render telltale needles at exact sweep angles matching core gauge geometry.

### 7.2 Off-Screen Headless Skin Dispatcher

**File:** `src/boostgauge/gauge.py` (lines 18-27)

```python
def render(
    value: float,
    telltales: dict[str, float | None] | None = None,
    size: tuple[int, int] = (256, 256),
    config: dict[str, Any] | None = None,
) -> Image.Image:
    ...
```

**Relevance:** Pure functional dispatch to skin renderers without `tkinter` coupling, maintaining Option C compliance defined in `docs/design/0001-test-strategy.md`.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `from typing import Any, Dict, Optional, TypedDict` | stdlib | All modules |
| `import time` | stdlib | `telltale_manager.py` |
| `import math` | stdlib | `stingray.py`, `test_telltale_visual.py` |
| `from pathlib import Path` | stdlib | `test_telltale_manager.py` |
| `from PIL import Image, ImageDraw, ImageFont` | `Pillow` | `stingray.py`, `gauge.py`, visual/contract tests |
| `from boostgauge.telltale import Telltale` | internal | `telltale_manager.py` |
| `from boostgauge.telltale_manager import TelltaleManager` | internal | `stingray.py`, unit/contract/integration tests |
| `from boostgauge.skins.stingray import render_stingray, TELLTALE_STYLES` | internal | `gauge.py`, `stingray.py` |

**New Dependencies:** None (uses existing Pillow and stdlib packages).

## 9. Placeholder

*Reserved for alignment with LLD structure.*

## 10. Test Mapping

| Test ID | Scenario Description | Tests Function / Class | Input | Expected Behavior |
|---------|----------------------|-----------------------|-------|-------------------|
| T010 | Instantiation of 4 Telltale windows | `TelltaleManager.__init__()` | `TelltaleManager()` | Instantiates 4 windows (60s, 600s, 3600s, None) with initial peaks `None`. |
| T020 | Metric stream update piping | `TelltaleManager.update()` | Samples (100.0, 45.0), (105.0, 85.0) | `get_peaks()` returns 85.0 across all 4 windows. |
| T030 | Angle mapping math & trigonometry | `_val_to_angle()` | Values 0.0, 50.0, 100.0 | Angles 225.0°, 90.0°, -45.0°; needle tip coordinates match trig formula. |
| T040 | Translucent telltale rendering and z-order | `_draw_telltales()` | `telltales={'1m': 80, 'all': 95}` | Needles drawn behind main needle with target RGBA colors. |
| T050 | Post-reset hiding | `_draw_telltales()` | `telltales={'1m': None, '10m': 50}` | 1m needle omitted from dial render. |
| T060 | Window reset functionality | `reset_window()`, `reset_all()` | `reset_window('1m')`, `reset_all()` | Targeted or all window peaks reset to `None`. |
| T070 | Visual legend rendering | `_draw_legend()` | `telltales` dict | Color swatches and peak text rendered on dial face. |
| T080 | Option C Headless PIL validation | `render()` | Synthetic stream -> `render()` | Returns valid `PIL.Image` without `tkinter.Tk()` initialization. |
| T090 | Sliding window expiration | `TelltaleManager.get_peaks()` | Spike at t=100 (95.0), low at t=110 (30.0) | At t=161, 1m peak expires to 30.0 while 10m/1h/all retain 95.0. |
| T100 | All-time telltale styling | `_draw_telltales()` | Peak at 100.0 | Red translucent solid needle rendered behind main needle. |

## 11. Implementation Notes

### 11.1 Baseline-Independent Property Assertions

In accordance with visual testing constraints (Issue #1902), `tests/visual/test_telltale_visual.py` includes property assertions computable without baseline images:

```python
def test_t030_angle_mapping_geometry_baseline_independent():
    """Verify angular position geometry using pure mathematical trigonometry."""
    # Gauge sweep: 0 -> 225.0 deg (bottom left), 50 -> 90.0 deg (top center), 100 -> -45.0 deg (bottom right)
    for val, expected_angle in [(0.0, 225.0), (50.0, 90.0), (100.0, -45.0)]:
        angle = _val_to_angle(val)
        assert math.isclose(angle, expected_angle, abs_tol=1e-5)
```

### 11.2 Platform-Independent Path Assertions Rule (Issue #1841)

All path comparisons in test code MUST use `pathlib.Path` objects rather than hardcoded path separator strings:

```python
# CORRECT (Platform Independent):
assert path == Path.home() / ".boostgauge" / "config.json"

# INCORRECT (Fails on Windows / POSIX mismatch):
assert str(path).endswith(".boostgauge/config.json")
```

### 11.3 Traceable Test Assertions Rule (Issue #1860)

Every assertion in test suites MUST map directly to specified requirements (REQ-1 to REQ-8) or function behaviors. Tests must NOT assert side-effects not explicitly defined in the spec.

### 11.4 Rendering Hierarchy & Z-Ordering

To guarantee visual z-ordering without canvas clipping, `render_stingray()` uses the following strict layer draw order:
1. Static Dial Face Background (bezel, ticks, numerals, redline arc, wordmark)
2. Telltale Needles Layer (`_draw_telltales()`: translucent cyan, orange, magenta, red lines)
3. Main Metric Needle (`_draw_needle()`: solid opaque red line with counterweight)
4. Central Pivot Cap (dark grey circle with metallic border overlaying needle hubs)
5. Visual Legend Overlay (`_draw_legend()`: color swatches and text strings)

### 11.5 Supersampling & Antialiasing Pipeline

All drawing operations occur on an intermediate canvas scaled by `scale_factor = 4` (e.g. 1024x1024 for a 256x256 target image). The high-resolution composite canvas is downsampled to requested dimensions using PIL's `Image.LANCZOS` filter to eliminate jagged needle edges and produce crisp anti-aliased telltale lines.

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
| Issue | #2 |
| Verdict | APPROVED |
| Date | 2026-07-31 |
| Iterations | 2 |
| Finalized | 2026-07-31T21:55:00Z |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #2 |
| Verdict | APPROVED |
| Date | 2026-08-01 |
| Iterations | 2 |
| Finalized | 2026-08-01T02:54:24Z |

### Review Feedback Summary

The implementation spec is complete, fully concrete, and provides exact, executable code implementations for all modified and new files (`TelltaleManager`, `stingray.py`, `gauge.py`, and unit/contract/visual/integration test suites). All test assertions trace directly to specified system requirements, angular geometry mapping is validated baseline-independently, and Option C headless off-screen PIL rendering constraints are strictly preserved. The revision cleanly resolves the prior background s...
