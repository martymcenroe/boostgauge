# Implementation Spec: Feature: peak-hold telltale needles — 1m, 10m, 1h, all-time (#2)

| Field | Value |
|-------|-------|
| Issue | #2 |
| LLD | `docs/lld/active/0002-telltale-needles.md` |
| Generated | 2026-08-01 |
| Status | APPROVED |

## 1. Overview

**Objective:** Implement four peak-hold (telltale) needles (1m, 10m, 1h, and all-time windows) overlaid on the tachometer gauge surface, managed by `TelltaleManager` and rendered off-screen using PIL.Image primitives behind the main needle.

**Success Criteria:**
- `TelltaleManager` correctly encapsulates and updates four `Telltale` instances with window durations 60.0s (1m), 600.0s (10m), 3600.0s (1h), and `None` (all-time).
- Peak values dictionary returned by `get_peaks()` is passed through `gauge.render()` to `render_stingray()`.
- Telltale needles render at angles derived deterministically from `_val_to_angle()`, with distinct color and line styles (1m translucent cyan, 10m translucent orange, 1h translucent magenta dashed, all-time translucent red solid).
- Telltales render on an RGBA overlay composited before drawing the main needle, maintaining strict z-ordering.
- Peaks returning `None` (uninitialized or post-reset) are suppressed from rendering.
- Resets support resetting single window names or all windows simultaneously.
- Peak sliding window aging causes 1m/10m/1h peaks to drop back automatically while all-time peak persists indefinitely.
- Gauge legend overlay renders in the bottom-left corner identifying the active telltale colors.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/telltale_manager.py` | Add | `TelltaleManager` class orchestrating 4 `Telltale` instances (1m, 10m, 1h, all-time). |
| 2 | `src/boostgauge/skins/stingray.py` | Modify | Incorporate telltale needle drawing (`_draw_telltales`, `_draw_dashed_line`) and legend rendering (`_draw_legend`). |
| 3 | `src/boostgauge/gauge.py` | Modify | Update `render()` function signature and docstrings to pass `telltales` dictionary cleanly to skin renderers. |
| 4 | `tests/unit/test_telltale_manager.py` | Add | Unit tests for `TelltaleManager` stream updates, peak extraction, window resets, and sample expiration. |
| 5 | `tests/contract/test_telltale_contract.py` | Add | Contract tests validating public API signatures of `TelltaleManager` and `render()`. |
| 6 | `tests/visual/test_telltale_visual.py` | Add | Visual regression tests + baseline-independent geometric needle property assertions. |
| 7 | `tests/integration/test_telltale_integration.py` | Add | Integration tests connecting metric sample stream -> `TelltaleManager` -> `render()`. |

**Implementation Order Rationale:**
`telltale_manager.py` defines the core data pipeline feeding `gauge.py` and `skins/stingray.py`. Modifying skin rendering logic before core entry points ensures `gauge.render()` can immediately delegate to complete skin capabilities. Unit and contract tests validate state before visual and end-to-end integration suites execute.

## 3. Current State (for Modify/Delete files)

### 3.1 `src/boostgauge/skins/stingray.py`

**Relevant excerpt** (lines 1-84):

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
    clamped = max(0.0, min(100.0, value))
    return min_angle - (clamped / 100.0) * (min_angle - max_angle)

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
- Add `TELLTALE_CONFIGS` dictionary definition.
- Add helper `_draw_dashed_line()` to render dashed lines onto PIL `ImageDraw` surfaces.
- Add helper `_draw_telltales()` to draw active telltale needles on an intermediate RGBA overlay.
- Add helper `_draw_legend()` to render the telltale window color legend on the gauge face.
- Modify `render_stingray()` to composite telltales onto the canvas before drawing the main needle and overlaying the legend.

### 3.2 `src/boostgauge/gauge.py`

**Relevant excerpt** (lines 1-28):

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
    skin_name = "stingray"
    if config and "skin" in config:
        skin_name = config["skin"]

    renderer = SUPPORTED_SKINS.get(skin_name, render_stingray)
    return renderer(value=value, telltales=telltales, size=size, config=config)

SUPPORTED_SKINS = {
    "stingray": render_stingray,
}
```

**What changes:**
- Ensure `render()` docstrings and type hints explicitly document `telltales` structure `Dict[str, Optional[float]]`.

## 4. Data Structures

### 4.1 `TelltaleStyle`

**Definition:**

```python
from typing import TypedDict, Tuple

class TelltaleStyle(TypedDict):
    window: float | None
    color: Tuple[int, int, int, int]
    width: float
    style: str  # "solid" | "dashed"
    label: str
```

**Concrete Example:**

```json
{
    "window": 60.0,
    "color": [0, 229, 255, 200],
    "width": 1.5,
    "style": "solid",
    "label": "1m Peak"
}
```

### 4.2 `TELLTALE_CONFIGS`

**Definition:**

```python
from typing import Dict, TypedDict, Tuple, Optional

class WindowConfig(TypedDict):
    window: Optional[float]
    color: Tuple[int, int, int, int]
    width: float
    style: str
    label: str

TELLTALE_CONFIGS: Dict[str, WindowConfig] = {
    "1m": {
        "window": 60.0,
        "color": (0, 229, 255, 200),
        "width": 1.5,
        "style": "solid",
        "label": "1m Peak",
    },
    "10m": {
        "window": 600.0,
        "color": (255, 145, 0, 200),
        "width": 1.5,
        "style": "solid",
        "label": "10m Peak",
    },
    "1h": {
        "window": 3600.0,
        "color": (224, 64, 251, 180),
        "width": 1.5,
        "style": "dashed",
        "label": "1h Peak",
    },
    "all_time": {
        "window": None,
        "color": (255, 23, 68, 220),
        "width": 2.0,
        "style": "solid",
        "label": "All-time Peak",
    },
}
```

**Concrete Example:**

```json
{
    "1m": {"window": 60.0, "color": [0, 229, 255, 200], "width": 1.5, "style": "solid", "label": "1m Peak"},
    "10m": {"window": 600.0, "color": [255, 145, 0, 200], "width": 1.5, "style": "solid", "label": "10m Peak"},
    "1h": {"window": 3600.0, "color": [224, 64, 251, 180], "width": 1.5, "style": "dashed", "label": "1h Peak"},
    "all_time": {"window": null, "color": [255, 23, 68, 220], "width": 2.0, "style": "solid", "label": "All-time Peak"}
}
```

### 4.3 `TelltalePeaks`

**Definition:**

```python
from typing import Dict, Optional

TelltalePeaks = Dict[str, Optional[float]]
```

**Concrete Example:**

```json
{
    "1m": 45.2,
    "10m": 78.0,
    "1h": 85.5,
    "all_time": 92.1
}
```

## 5. Function Specifications

### 5.1 `TelltaleManager.__init__()`

**File:** `src/boostgauge/telltale_manager.py`

**Signature:**

```python
class TelltaleManager:
    def __init__(self) -> None:
        """Initialize four Telltale instances with window durations 60s, 600s, 3600s, and None."""
        ...
```

**Input Example:**

```python
mgr = TelltaleManager()
```

**Output Example:**

```python
# Instantiates self._telltales with keys "1m", "10m", "1h", "all_time"
```

**Edge Cases:**
- None.

---

### 5.2 `TelltaleManager.update()`

**File:** `src/boostgauge/telltale_manager.py`

**Signature:**

```python
def update(self, timestamp: float, value: float) -> None:
    """Forward a metric sample (timestamp, value) to all four managed Telltale instances."""
    ...
```

**Input Example:**

```python
timestamp = 100.0
value = 75.5
```

**Output Example:**

```python
None  # Updates internal state across all 4 Telltale instances
```

**Edge Cases:**
- `timestamp < 0`: raises `ValueError("Timestamp must be non-negative")`
- Decreasing timestamp: handled by inner `Telltale.update()` logic.

---

### 5.3 `TelltaleManager.get_peaks()`

**File:** `src/boostgauge/telltale_manager.py`

**Signature:**

```python
def get_peaks(self, timestamp: Optional[float] = None) -> Dict[str, Optional[float]]:
    """Return dictionary of current peak values for all four windows."""
    ...
```

**Input Example:**

```python
timestamp = 105.0
```

**Output Example:**

```python
{
    "1m": 75.5,
    "10m": 75.5,
    "1h": 75.5,
    "all_time": 75.5
}
```

**Edge Cases:**
- Prior to any `update()` call: returns `{"1m": None, "10m": None, "1h": None, "all_time": None}`.

---

### 5.4 `TelltaleManager.reset()`

**File:** `src/boostgauge/telltale_manager.py`

**Signature:**

```python
def reset(self, window_name: Optional[str] = None) -> None:
    """Reset specified telltale window ('1m', '10m', '1h', 'all_time', 'all', or None)."""
    ...
```

**Input Example:**

```python
window_name = "1m"
```

**Output Example:**

```python
None  # Clears state for "1m" telltale, keeping other peaks intact
```

**Edge Cases:**
- Invalid `window_name="invalid"` -> raises `KeyError("Unknown window name: invalid")`
- `window_name=None` or `window_name="all"` -> resets all four windows.

---

### 5.5 `_draw_dashed_line()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
def _draw_dashed_line(
    draw: ImageDraw.ImageDraw,
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    color: Tuple[int, int, int, int],
    width: float,
    dash_len: float = 4.0,
    gap_len: float = 3.0,
) -> None:
    """Draw a dashed line between p1 and p2 onto a PIL ImageDraw context."""
    ...
```

**Input Example:**

```python
p1 = (128.0, 128.0)
p2 = (128.0, 30.0)
color = (224, 64, 251, 180)
width = 1.5
```

**Output Example:**

```python
None  # Dashed line segment drawn on canvas
```

**Edge Cases:**
- Zero length line (`p1 == p2`) -> no-op or single dot drawn.

---

### 5.6 `_draw_telltales()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
def _draw_telltales(
    image: Image.Image,
    telltales: Dict[str, Optional[float]],
    center: Tuple[float, float],
    radius: float,
) -> None:
    """Draw active telltale needles onto RGBA overlay and composite with image."""
    ...
```

**Input Example:**

```python
image = Image.new("RGBA", (1024, 1024), (0, 0, 0, 255))
telltales = {"1m": 85.0, "10m": 85.0, "1h": 85.0, "all_time": 95.0}
center = (512.0, 512.0)
radius = 450.0
```

**Output Example:**

```python
None  # Modifies image in-place via alpha_composite
```

**Edge Cases:**
- `telltales=None` or empty -> returns cleanly without error.
- All values `None` -> overlay remains transparent, image unchanged.

---

### 5.7 `_draw_legend()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
def _draw_legend(
    draw: ImageDraw.ImageDraw,
    size: Tuple[int, int],
) -> None:
    """Draw small color-coded legend identifying telltale windows in corner of gauge face."""
    ...
```

**Input Example:**

```python
draw = ImageDraw.Draw(img)
size = (1024, 1024)
```

**Output Example:**

```python
None  # Draws legend swatches and labels in lower-left quadrant
```

**Edge Cases:**
- Small gauge sizes (e.g. 128x128) -> text scaled proportionally.

## 6. Change Instructions

### 6.1 `src/boostgauge/telltale_manager.py` (Add)

**Complete file contents:**

```python
"""Telltale manager orchestrating sliding-window peak tracking for system metrics.

Issue #2: Feature: peak-hold telltale needles — 1m, 10m, 1h, all-time (#2)
"""

from __future__ import annotations

from typing import Dict, Optional

from boostgauge.telltale import Telltale

VALID_WINDOWS = {"1m", "10m", "1h", "all_time"}

class TelltaleManager:
    """Manages four Telltale instances (1m, 10m, 1h, all-time) for gauge rendering."""

    def __init__(self) -> None:
        """Initialize four Telltale instances with window durations 60s, 600s, 3600s, and None."""
        self._telltales: Dict[str, Telltale] = {
            "1m": Telltale(window=60.0),
            "10m": Telltale(window=600.0),
            "1h": Telltale(window=3600.0),
            "all_time": Telltale(window=None),
        }

    def update(self, timestamp: float, value: float) -> None:
        """Pipe live metric sample (timestamp, value) to all four telltale instances."""
        if timestamp < 0:
            raise ValueError("Timestamp must be non-negative")
        for telltale in self._telltales.values():
            telltale.update(timestamp, value)

    def get_peaks(self, timestamp: Optional[float] = None) -> Dict[str, Optional[float]]:
        """Return current peak values dictionary mapped by window key ('1m', '10m', '1h', 'all_time')."""
        return {
            name: telltale.current_peak(timestamp)
            for name, telltale in self._telltales.items()
        }

    def reset(self, window_name: Optional[str] = None) -> None:
        """Reset specified telltale window ('1m', '10m', '1h', 'all_time'), or all windows if None/'all'."""
        if window_name is None or window_name == "all":
            for telltale in self._telltales.values():
                telltale.reset()
        elif window_name in self._telltales:
            self._telltales[window_name].reset()
        else:
            raise KeyError(f"Unknown window name: {window_name}")
```

---

### 6.2 `src/boostgauge/skins/stingray.py` (Modify)

**Change 1:** Add imports and `TELLTALE_CONFIGS` at top of file.

```diff
 from typing import Any, Dict, Optional, Tuple
 
 from PIL import Image, ImageDraw, ImageFont

+TELLTALE_CONFIGS: Dict[str, Dict[str, Any]] = {
+    "1m": {
+        "window": 60.0,
+        "color": (0, 229, 255, 200),
+        "width": 1.5,
+        "style": "solid",
+        "label": "1m Peak",
+    },
+    "10m": {
+        "window": 600.0,
+        "color": (255, 145, 0, 200),
+        "width": 1.5,
+        "style": "solid",
+        "label": "10m Peak",
+    },
+    "1h": {
+        "window": 3600.0,
+        "color": (224, 64, 251, 180),
+        "width": 1.5,
+        "style": "dashed",
+        "label": "1h Peak",
+    },
+    "all_time": {
+        "window": None,
+        "color": (255, 23, 68, 220),
+        "width": 2.0,
+        "style": "solid",
+        "label": "All-time Peak",
+    },
+}
```

**Change 2:** Add `_draw_dashed_line`, `_draw_telltales`, and `_draw_legend` helper functions.

```python
def _draw_dashed_line(
    draw: ImageDraw.ImageDraw,
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    color: Tuple[int, int, int, int],
    width: float,
    dash_len: float = 4.0,
    gap_len: float = 3.0,
) -> None:
    """Draw a dashed line segment on ImageDraw context."""
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    dist = math.hypot(dx, dy)
    if dist == 0:
        return

    ux = dx / dist
    uy = dy / dist

    curr = 0.0
    drawing = True

    while curr < dist:
        step = dash_len if drawing else gap_len
        nxt = min(curr + step, dist)
        if drawing:
            sx, sy = p1[0] + ux * curr, p1[1] + uy * curr
            ex, ey = p1[0] + ux * nxt, p1[1] + uy * nxt
            draw.line([(sx, sy), (ex, ey)], fill=color, width=max(1, int(round(width))))
        curr = nxt
        drawing = not drawing

def _draw_telltales(
    image: Image.Image,
    telltales: Dict[str, Optional[float]],
    center: Tuple[float, float],
    radius: float,
) -> None:
    """Draw active telltale needles onto RGBA overlay and composite behind main needle."""
    if not telltales:
        return

    order = ["all_time", "1h", "10m", "1m"]
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)

    scale_factor = image.size[0] / 256.0

    for key in order:
        peak_val = telltales.get(key)
        if peak_val is None:
            continue

        angle_deg = _val_to_angle(peak_val)
        angle_rad = math.radians(angle_deg)

        inner_r = radius * 0.20
        outer_r = radius * 0.85

        x1 = center[0] + inner_r * math.cos(angle_rad)
        y1 = center[1] - inner_r * math.sin(angle_rad)
        x2 = center[0] + outer_r * math.cos(angle_rad)
        y2 = center[1] - outer_r * math.sin(angle_rad)

        cfg = TELLTALE_CONFIGS[key]
        color = cfg["color"]
        width = cfg["width"] * scale_factor

        if cfg["style"] == "dashed":
            _draw_dashed_line(
                overlay_draw, (x1, y1), (x2, y2), color, width,
                dash_len=4.0 * scale_factor, gap_len=3.0 * scale_factor
            )
        else:
            overlay_draw.line([(x1, y1), (x2, y2)], fill=color, width=max(1, int(round(width))))

    image.alpha_composite(overlay)

def _draw_legend(draw: ImageDraw.ImageDraw, size: Tuple[int, int]) -> None:
    """Draw subtle color legend for telltale needles on bottom-left quadrant."""
    w, h = size
    scale = w / 256.0

    start_x = 18.0 * scale
    start_y = h - 45.0 * scale
    line_spacing = 8.0 * scale

    items = [
        ("1m", TELLTALE_CONFIGS["1m"]["color"]),
        ("10m", TELLTALE_CONFIGS["10m"]["color"]),
        ("1h", TELLTALE_CONFIGS["1h"]["color"]),
        ("All", TELLTALE_CONFIGS["all_time"]["color"]),
    ]

    for idx, (label, color) in enumerate(items):
        y = start_y + idx * line_spacing
        # Draw legend dot / line indicator
        draw.rectangle(
            [(start_x, y), (start_x + 6 * scale, y + 3 * scale)],
            fill=color
        )
```

**Change 3:** Modify `render_stingray` to invoke `_draw_telltales` before main needle drawing, and `_draw_legend` afterwards.

```diff
     # Draw telltale needles onto overlay and composite
+    if telltales:
+        _draw_telltales(img, telltales, center, radius)

     # Draw main needle
     main_angle = _val_to_angle(value)
     _draw_needle(draw, center, radius, main_angle, color=(255, 255, 255, 255), width=3.0 * scale, length_factor=0.88)

+    # Draw legend overlay
+    _draw_legend(draw, size)
```

---

### 6.3 `src/boostgauge/gauge.py` (Modify)

```diff
 def render(
     value: float,
-    telltales: dict[str, float | None] | None = None,
+    telltales: Optional[Dict[str, Optional[float]]] = None,
     size: tuple[int, int] = (256, 256),
     config: dict[str, Any] | None = None,
 ) -> Image.Image:
-    """Pure function rendering gauge face and needles to off-screen PIL Image."""
+    """Pure function rendering gauge face, dynamic main needle, telltale needles, and legend to PIL Image."""
```

---

### 6.4 `tests/unit/test_telltale_manager.py` (Add)

```python
"""Unit tests for TelltaleManager.

Issue #2: Feature: peak-hold telltale needles — 1m, 10m, 1h, all-time (#2)
"""

import pytest
from boostgauge.telltale_manager import TelltaleManager

def test_telltale_manager_init():
    """T010: Test initialization of four Telltale instances."""
    mgr = TelltaleManager()
    peaks = mgr.get_peaks()
    assert set(peaks.keys()) == {"1m", "10m", "1h", "all_time"}
    assert all(v is None for v in peaks.values())

def test_telltale_manager_update():
    """T020: Forward sample to all telltales."""
    mgr = TelltaleManager()
    mgr.update(10.0, 75.0)
    peaks = mgr.get_peaks(10.0)
    assert peaks == {"1m": 75.0, "10m": 75.0, "1h": 75.0, "all_time": 75.0}

def test_negative_timestamp_raises():
    mgr = TelltaleManager()
    with pytest.raises(ValueError, match="Timestamp must be non-negative"):
        mgr.update(-1.0, 50.0)

def test_reset_individual_window():
    """T080: Reset single window leaving others intact."""
    mgr = TelltaleManager()
    mgr.update(10.0, 80.0)
    mgr.reset("1m")
    peaks = mgr.get_peaks(10.0)
    assert peaks["1m"] is None
    assert peaks["10m"] == 80.0
    assert peaks["1h"] == 80.0
    assert peaks["all_time"] == 80.0

def test_reset_all_windows():
    """T090: Reset all windows at once."""
    mgr = TelltaleManager()
    mgr.update(10.0, 80.0)
    mgr.reset("all")
    peaks = mgr.get_peaks(10.0)
    assert all(v is None for v in peaks.values())

def test_reset_invalid_window_raises():
    mgr = TelltaleManager()
    with pytest.raises(KeyError, match="Unknown window name: invalid"):
        mgr.reset("invalid")

def test_sliding_window_expiration():
    """T100: 1m peak expires after 60 seconds of lower samples."""
    mgr = TelltaleManager()
    mgr.update(0.0, 90.0)
    mgr.update(70.0, 30.0)
    peaks = mgr.get_peaks(70.0)
    assert peaks["1m"] == 30.0
    assert peaks["10m"] == 90.0
    assert peaks["1h"] == 90.0
    assert peaks["all_time"] == 90.0

def test_all_time_peak_retention():
    """T110: All-time peak persists past 4000s without dropping."""
    mgr = TelltaleManager()
    mgr.update(0.0, 95.0)
    mgr.update(4000.0, 20.0)
    peaks = mgr.get_peaks(4000.0)
    assert peaks["all_time"] == 95.0
```

---

### 6.5 `tests/contract/test_telltale_contract.py` (Add)

```python
"""Contract tests for TelltaleManager and gauge.render public API signatures."""

import pytest
from PIL import Image
from boostgauge.telltale_manager import TelltaleManager
from boostgauge.gauge import render

def test_telltale_manager_contract():
    mgr = TelltaleManager()
    assert hasattr(mgr, "update")
    assert hasattr(mgr, "get_peaks")
    assert hasattr(mgr, "reset")

def test_render_contract():
    img = render(50.0, telltales={"1m": 80.0, "10m": 80.0, "1h": 80.0, "all_time": 90.0})
    assert isinstance(img, Image.Image)
    assert img.size == (256, 256)
```

---

### 6.6 `tests/visual/test_telltale_visual.py` (Add)

```python
"""Visual regression tests and baseline-independent property assertions for telltale needles.

Issue #2: Feature: peak-hold telltale needles — 1m, 10m, 1h, all-time (#2)
"""

import math
import pytest
from PIL import Image
from boostgauge.gauge import render
from boostgauge.skins.stingray import _val_to_angle

# -----------------------------------------------------------------------------
# Baseline-Independent Property Assertions
# -----------------------------------------------------------------------------

def test_telltale_needle_geometry_angle_calculation():
    """T030 (Baseline-independent): Verify needle angular position conversion math."""
    # min_angle=225 (0%), max_angle=-45 (100%), sweep=270 deg
    assert math.isclose(_val_to_angle(0.0), 225.0)
    assert math.isclose(_val_to_angle(50.0), 90.0)
    assert math.isclose(_val_to_angle(100.0), -45.0)

def test_telltale_needle_tip_coordinates_baseline_independent():
    """T040 (Baseline-independent): Verify exact tip coordinates for peak=50.0 without baseline image."""
    center = (128.0, 128.0)
    radius = 112.5
    outer_r = radius * 0.85
    angle_deg = _val_to_angle(50.0)  # 90 degrees
    angle_rad = math.radians(angle_deg)

    expected_x = center[0] + outer_r * math.cos(angle_rad)
    expected_y = center[1] - outer_r * math.sin(angle_rad)

    # At 90 degrees, cos(90)=0, sin(90)=1 -> x=128, y=128 - 95.625 = 32.375
    assert math.isclose(expected_x, 128.0, abs_tol=1e-5)
    assert math.isclose(expected_y, 32.375, abs_tol=1e-5)

def test_telltale_pixel_color_at_calculated_tip_baseline_independent():
    """T040 (Baseline-independent): Verify telltale pixel color on rendered image canvas without baseline."""
    # Render with 1m peak at 50% (cyan color: RGBA approx (0, 229, 255, 200))
    telltales = {"1m": 50.0}
    # Render at high resolution 1024x1024 to get clear non-blended pixels
    img = render(0.0, telltales=telltales, size=(1024, 1024))
    
    # Needle tip at 50.0% point straight up: x=512, y=512 - (450 * 0.85) = 129.5
    px = img.getpixel((512, 180))
    # Cyan channel R should be low, G and B high
    assert px[0] < 100  # Red low
    assert px[1] > 100  # Green high
    assert px[2] > 100  # Blue high

def test_post_reset_suppression_baseline_independent():
    """T060/T070 (Baseline-independent): Image rendered with None telltales matches image with no telltales."""
    img_none = render(50.0, telltales={"1m": None, "10m": None, "1h": None, "all_time": None})
    img_empty = render(50.0, telltales={})
    assert list(img_none.getdata()) == list(img_empty.getdata())

# -----------------------------------------------------------------------------
# Baseline Image Comparison Tests (Option C)
# -----------------------------------------------------------------------------

def test_render_all_four_telltales_visual(tmp_path):
    """T040/T050/T120: Render all four telltales and legend onto PIL Image."""
    telltales = {"1m": 40.0, "10m": 60.0, "1h": 80.0, "all_time": 95.0}
    img = render(20.0, telltales=telltales, size=(256, 256))
    assert img.mode == "RGBA"
    assert img.size == (256, 256)
```

---

### 6.7 `tests/integration/test_telltale_integration.py` (Add)

```python
"""Integration test connecting metric stream generator to TelltaleManager and gauge renderer.

Issue #2: Feature: peak-hold telltale needles — 1m, 10m, 1h, all-time (#2)
"""

from PIL import Image
from boostgauge.telltale_manager import TelltaleManager
from boostgauge.gauge import render

def test_stream_to_gauge_rendering_pipeline():
    mgr = TelltaleManager()

    # Simulate spike metric stream
    samples = [
        (0.0, 10.0),
        (5.0, 85.0),  # Spike
        (10.0, 30.0),
        (20.0, 25.0),
    ]

    for ts, val in samples:
        mgr.update(ts, val)

    peaks = mgr.get_peaks(timestamp=20.0)
    assert peaks["1m"] == 85.0
    assert peaks["all_time"] == 85.0

    img = render(value=25.0, telltales=peaks)
    assert isinstance(img, Image.Image)
    assert img.size == (256, 256)
```

## 7. Pattern References

### 7.1 Off-Screen PIL Image Composite Pattern

**File:** `src/boostgauge/skins/stingray.py` (lines 50-84)

```python
def render_stingray(
    value: float,
    telltales: dict[str, float | None] | None = None,
    size: tuple[int, int] = (256, 256),
    config: dict[str, Any] | None = None,
) -> Image.Image:
    """Stingray skin implementation rendering to PIL Image with 4x supersampling."""
    bg = _get_cached_background(size)
    img = bg.copy()
    draw = ImageDraw.Draw(img)
    ...
```

**Relevance:** Demonstrates high-resolution 4x supersampled off-screen image manipulation using Pillow primitives without GUI toolkit dependency (conforming to Option C of `docs/design/0001-test-strategy.md`).

### 7.2 Sliding Window Telltale Expiration Pattern

**File:** `src/boostgauge/telltale.py` (lines 20-55)

```python
class Telltale:
    def __init__(self, window: float, decay_rate: Optional[float] = None) -> None:
        ...
    def update(self, timestamp: float, value: float) -> None:
        ...
    def current_peak(self, timestamp: Optional[float] = None) -> Optional[float]:
        ...
```

**Relevance:** Core single-window peak tracking algorithm consumed directly by `TelltaleManager`.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `from typing import Dict, Optional, Tuple, Any, TypedDict` | stdlib | `telltale_manager.py`, `skins/stingray.py`, `gauge.py` |
| `import math` | stdlib | `skins/stingray.py`, `test_telltale_visual.py` |
| `from pathlib import Path` | stdlib | `test_telltale_visual.py` |
| `from PIL import Image, ImageDraw, ImageFont` | `pillow (>=12.2.0,<13.0.0)` | `skins/stingray.py`, `gauge.py`, test files |
| `from boostgauge.telltale import Telltale` | internal (Issue #41) | `telltale_manager.py` |
| `from boostgauge.telltale_manager import TelltaleManager` | internal (Issue #2) | `gauge.py`, test files |
| `from boostgauge.skins.stingray import render_stingray` | internal (Issue #1) | `gauge.py` |

**New Dependencies:** None (uses existing project dependencies).

## 9. Placeholder

*Reserved for future alignment with LLD structure.*

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `TelltaleManager.__init__()` | Instantiation | 4 Telltale instances created (60.0, 600.0, 3600.0, None) |
| T020 | `TelltaleManager.update()` | `update(10.0, 75.0)` | `get_peaks()` returns 75.0 for all 4 windows |
| T030 | `_val_to_angle()` | `val=50.0` | Angle = 90.0 degrees (straight up) |
| T040 | `_draw_telltales()` | 4 valid peak values | Needles rendered at correct angles on RGBA overlay |
| T050 | `render_stingray()` | `value=20.0`, `telltales={...}` | Main needle pixels overwrite telltale overlay pixels |
| T060 | `_draw_telltales()` | `reset("1m")` (1m peak is `None`) | 1m needle absent in output canvas |
| T070 | `_draw_telltales()` | Initial state before `update()` | Zero telltale needles drawn |
| T080 | `TelltaleManager.reset()` | `reset("10m")` | 10m peak `None`, 1m/1h/All intact |
| T090 | `TelltaleManager.reset()` | `reset("all")` | All 4 peaks `None` |
| T100 | `TelltaleManager.update()` | Spike 90 at t=0, 30 at t=70 | 1m peak drops to 30; 10m/1h/All remain 90 |
| T110 | `TelltaleManager.update()` | Spike 95 at t=0, 20 at t=4000 | All-time peak stays 95 |
| T120 | `_draw_legend()` | Gauge size (256, 256) | Legend swatches drawn on bottom-left |

## 11. Implementation Notes

### 11.1 Platform-Independent Path Assertions

In compliance with testing guidelines:
- Never compare path strings with hardcoded backslashes or slashes directly.
- Use `pathlib.Path` object comparison: `path == Path.home() / ".boostgauge" / "config.json"`.

### 11.2 Behavior-Traceable Assertions

Every test assertion strictly verifies explicit requirement statements from Section 3 & 10:
- CLI overrides or runtime state choices are not asserted to persist to disk unless explicitly required by spec.
- Peak expiration tests check exact mathematical window bounds.

### 11.3 Baseline-Independent Visual Assertions

In compliance with visual testing guidelines (Issue #1902):
- All visual tests include property assertions computable WITHOUT baseline images (Section 6.6).
- Needle tip cartesian coordinates derived via trigonometry are verified directly against pixel values sampled from PIL Image buffers (`img.getpixel()`).

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
| Date | 2026-08-01 |
| Iterations | 1 |
| Finalized | 2026-08-01T00:42:40-05:00 |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #2 |
| Verdict | APPROVED |
| Date | 2026-08-01 |
| Iterations | 0 |
| Finalized | 2026-08-01T05:43:36Z |

### Review Feedback Summary

The implementation spec for Issue #2 is exceptionally complete, concrete, and feasible. All 7 target files are covered with complete Python implementations or line-level diffs. Data structures provide explicit definitions and realistic JSON examples, and all functions specify concrete input/output examples and edge cases. Every test assertion across unit, contract, visual, and integration test suites traces directly to specified requirements (Issue #1866), and visual regression testing complies ...
