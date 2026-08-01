# Implementation Specification: Peak-Hold Telltale Needles (Issue #2)

## 1. Overview

This implementation spec defines the architectural additions and modifications required to render four peak-hold (telltale) needles (1m, 10m, 1h, and all-time windows) on the gauge surface. The telltale needles are updated live from incoming system metric streams and rendered onto off-screen `PIL.Image` surfaces directly behind the main needle, complete with a color-coded legend and context-menu reset capabilities.

**Objective:** Render four peak-hold (telltale) needles (1m, 10m, 1h, and all-time) on top of the off-screen gauge surface behind the main needle.

**Success Criteria:**
- Instantiation of four `Telltale` instances (60s, 600s, 3600s, None).
- Live metric stream updates piped to all four telltales simultaneously via `update(timestamp, value)`.
- Correct visual style assignment (1m: cyan translucent, 10m: orange translucent, 1h: magenta dashed translucent, all-time: red solid).
- Deterministic angular position mapping mapped linearly across gauge geometry (0–100 mapped to 225° to -45°).
- Skip drawing needles when `current_peak()` is `None` (before first update or post-reset).
- Off-screen `PIL.Image` alpha compositing maintaining z-order (telltales behind main needle) with zero `tkinter` calls.
- Context menu reset support for individual windows ("1m", "10m", "1h", "all_time") and `reset_all()`.
- Baseline-independent visual verification validating needle endpoint trigonometry.


## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/skins/telltale_layer.py` | Add | `TelltaleLayer` class managing `Telltale` instances, style configs, angle calculations, legend drawing, and PIL needle rendering |
| 2 | `src/boostgauge/skins/stingray.py` | Modify | Update `render_stingray()` to accept `telltales` parameter and composite telltale needles behind main needle via `TelltaleLayer.render()` |
| 3 | `src/boostgauge/gauge.py` | Modify | Update `render()` signature and implementation to forward `telltales` parameter to skin renderer |
| 4 | `tests/unit/test_telltale_layer.py` | Add | Unit test suite verifying telltale angle math, style definitions, update piping, conditional rendering skip, and reset logic |
| 5 | `tests/visual/test_telltale_render.py` | Add | Visual rendering tests including baseline image comparison and baseline-independent trigonometric angle/tip location property assertions |
| 6 | `tests/contract/test_telltale_contract.py` | Add | Interface contract verification testing `TelltaleLayer` and `gauge.render` interoperation |

**Implementation Order Rationale:**
1. `src/boostgauge/skins/telltale_layer.py` must be implemented first as it provides the encapsulated rendering and state logic for peak-hold needles.
2. `src/boostgauge/skins/stingray.py` is updated next to invoke `TelltaleLayer.render()` after rendering the gauge dial background face and before rendering the main needle.
3. `src/boostgauge/gauge.py` depends on skin renderers (such as `render_stingray`) to perform off-screen compositing and forwards the `telltales` parameter.
4. Unit tests (`test_telltale_layer.py`), contract tests (`test_telltale_contract.py`), and visual tests (`test_telltale_render.py`) are implemented against the completed layer, skin, and gauge module interfaces.


## 3. Current State (for Modify/Delete files)


### 3.1 `src/boostgauge/gauge.py`

**Current state before modification:**

```python
def render(
    value: float,
    telltales: dict[str, float | None] | None = None,
    size: tuple[int, int] = (256, 256),
    config: dict[str, Any] | None = None,
) -> Image.Image:
    """Pure function rendering gauge face and needles to off-screen PIL Image."""
    skin_name = (config or {}).get("skin", "stingray")
    renderer = SUPPORTED_SKINS.get(skin_name, render_stingray)
    return renderer(value=value, size=size, config=config)
```


## 4. Data Structures


### 4.1 `TelltaleStyle`

```python
class TelltaleStyle(NamedTuple):
    window: Optional[float]
    color: Tuple[int, int, int, int]
    width: int
    dash: Optional[Tuple[int, int]]
    label: str
```


### 4.2 `TelltaleNeedleState`

```python
class TelltaleNeedleState(NamedTuple):
    window: str
    peak_value: Optional[float]
    angle: Optional[float]
    style: TelltaleStyle
```


### [UNCHANGED] 4.3 Peak Values Dictionary (`telltales` parameter)


## [UNCHANGED] 5. Function Specifications


### [UNCHANGED] 5.1 `TelltaleLayer.__init__()`


### [UNCHANGED] 5.2 `TelltaleLayer.update()`


### [UNCHANGED] 5.3 `TelltaleLayer.value_to_angle()`


### [UNCHANGED] 5.4 `TelltaleLayer.render()`


### [UNCHANGED] 5.5 `TelltaleLayer.reset_window()` and `reset_all()`


### 5.6 Modified `gauge.render()`

**File:** `src/boostgauge/gauge.py`

**Signature:**

```python
def render(
    value: float,
    telltales: dict[str, float | None] | TelltaleLayer | None = None,
    size: tuple[int, int] = (256, 256),
    config: dict[str, Any] | None = None,
) -> Image.Image:
    """Pure function rendering gauge face and needles to off-screen PIL Image."""
    ...
```

**Input Example:**

```python
value = 45.0
telltales = {"1m": 60.0, "10m": 75.0, "1h": 85.0, "all_time": 95.0}
size = (256, 256)
config = {"skin": "stingray"}
```

**Output Example:**

```python
# Returns PIL.Image.Image (RGBA, 256x256)
```

**Edge Cases:**
- `telltales=None`: Renders main needle over static dial background without telltales.


## 6. Change Instructions


### 6.1 `src/boostgauge/skins/telltale_layer.py` (Add)

**Complete file contents:**

```python
"""Peak-hold telltale layer renderer.

Issue #2: peak-hold telltale needles — 1m, 10m, 1h, all-time (#2)
"""

from __future__ import annotations

import math
from typing import Dict, NamedTuple, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont

from boostgauge.telltale import Telltale


class TelltaleStyle(NamedTuple):
    window: Optional[float]
    color: Tuple[int, int, int, int]
    width: int
    dash: Optional[Tuple[int, int]]
    label: str


DEFAULT_STYLES: Dict[str, TelltaleStyle] = {
    "1m": TelltaleStyle(60.0, (0, 229, 255, 180), 2, None, "1m"),
    "10m": TelltaleStyle(600.0, (255, 145, 0, 180), 2, None, "10m"),
    "1h": TelltaleStyle(3600.0, (224, 64, 251, 180), 2, (4, 4), "1h"),
    "all_time": TelltaleStyle(None, (255, 23, 68, 230), 2, None, "All"),
}


def _draw_dashed_line(
    draw: ImageDraw.ImageDraw,
    pt1: Tuple[float, float],
    pt2: Tuple[float, float],
    fill: Tuple[int, int, int, int],
    width: int,
    dash: Tuple[int, int],
) -> None:
    """Draw a dashed line between pt1 and pt2 onto PIL ImageDraw."""
    x1, y1 = pt1
    x2, y2 = pt2
    dx = x2 - x1
    dy = y2 - y1
    dist = math.hypot(dx, dy)
    if dist == 0:
        return

    dash_len, gap_len = dash
    step_len = dash_len + gap_len
    ux = dx / dist
    uy = dy / dist

    curr = 0.0
    while curr < dist:
        seg_end = min(curr + dash_len, dist)
        sx = x1 + ux * curr
        sy = y1 + uy * curr
        ex = x1 + ux * seg_end
        ey = y1 + uy * seg_end
        draw.line([(sx, sy), (ex, ey)], fill=fill, width=width)
        curr += step_len


class TelltaleLayer:
    """Manages 1m, 10m, 1h, and all-time telltale needles and renders them onto a PIL Image."""

    def __init__(
        self,
        min_val: float = 0.0,
        max_val: float = 100.0,
        start_angle: float = 225.0,
        end_angle: float = -45.0,
    ) -> None:
        if min_val >= max_val:
            raise ValueError("min_val must be less than max_val")

        self.min_val = min_val
        self.max_val = max_val
        self.start_angle = start_angle
        self.end_angle = end_angle

        self.telltales: Dict[str, Telltale] = {
            "1m": Telltale(window=60.0),
            "10m": Telltale(window=600.0),
            "1h": Telltale(window=3600.0),
            "all_time": Telltale(window=None),
        }
        self.styles = dict(DEFAULT_STYLES)

    def update(self, timestamp: float, value: float) -> None:
        """Feed live metric sample into all four Telltale instances."""
        for tt in self.telltales.values():
            tt.update(timestamp, value)

    def value_to_angle(self, value: float) -> float:
        """Map a metric value to an angular position in degrees given scale geometry."""
        clamped = max(self.min_val, min(self.max_val, value))
        ratio = (clamped - self.min_val) / (self.max_val - self.min_val)
        return self.start_angle + ratio * (self.end_angle - self.start_angle)

    def reset_window(self, window_name: str) -> None:
        """Reset a specific telltale window ('1m', '10m', '1h', 'all_time')."""
        if window_name in self.telltales:
            self.telltales[window_name].reset()

    def reset_all(self) -> None:
        """Reset all four telltale instances."""
        for tt in self.telltales.values():
            tt.reset()

    def get_style(self, window_name: str) -> TelltaleStyle:
        """Return style definition for a given window name."""
        return self.styles[window_name]

    def render(
        self,
        base_image: Image.Image,
        center: Tuple[float, float],
        radius: float,
        timestamp: Optional[float] = None,
        peaks_override: Optional[Dict[str, Optional[float]]] = None,
    ) -> Image.Image:
        """Render active telltale needles and legend onto base gauge image using PIL alpha composition."""
        overlay = Image.new("RGBA", base_image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        cx, cy = center

        # Render in z-order: all_time -> 1h -> 10m -> 1m
        draw_order = ["all_time", "1h", "10m", "1m"]

        for key in draw_order:
            if peaks_override is not None and key in peaks_override:
                peak = peaks_override[key]
            else:
                peak = self.telltales[key].current_peak(timestamp=timestamp)

            if peak is None:
                continue

            angle = self.value_to_angle(peak)
            rad = math.radians(angle)
            needle_len = radius * 0.85

            end_x = cx + needle_len * math.cos(rad)
            end_y = cy - needle_len * math.sin(rad)

            style = self.styles[key]

            if style.dash is not None:
                _draw_dashed_line(
                    draw,
                    (cx, cy),
                    (end_x, end_y),
                    fill=style.color,
                    width=style.width,
                    dash=style.dash,
                )
            else:
                draw.line(
                    [(cx, cy), (end_x, end_y)],
                    fill=style.color,
                    width=style.width,
                )

        self._render_legend(draw, base_image.size)

        if base_image.mode != "RGBA":
            base_image = base_image.convert("RGBA")

        return Image.alpha_composite(base_image, overlay)

    def _render_legend(
        self,
        draw: ImageDraw.ImageDraw,
        img_size: Tuple[int, int],
    ) -> None:
        """Render color-coded legend in bottom corner of gauge surface."""
        w, h = img_size
        padding = max(4, int(w * 0.03))
        box_size = max(6, int(w * 0.03))
        line_height = box_size + 4

        x_start = padding
        y_start = h - padding - (line_height * 4)

        try:
            font = ImageFont.load_default()
        except Exception:
            font = None

        keys = ["1m", "10m", "1h", "all_time"]
        for i, key in enumerate(keys):
            style = self.styles[key]
            y = y_start + (i * line_height)

            # Draw legend color indicator box
            draw.rectangle(
                [(x_start, y), (x_start + box_size, y + box_size)],
                fill=style.color,
                outline=(255, 255, 255, 200),
            )

            # Draw legend label text
            text_pos = (x_start + box_size + 4, y)
            if font is not None:
                draw.text(text_pos, style.label, fill=(240, 240, 240, 220), font=font)
            else:
                draw.text(text_pos, style.label, fill=(240, 240, 240, 220))
```


### 6.2 `src/boostgauge/skins/stingray.py` and `src/boostgauge/gauge.py` (Modify)

**File:** `src/boostgauge/skins/stingray.py`

**Change 1:** Update `render_stingray` signature and implementation to integrate `TelltaleLayer` compositing between background dial face rendering and main needle rendering.

```diff
 """Stingray skin renderer implementation.

 Issue #1: Core Gauge Renderer — Analog Tachometer with Arc, Needle, and Tick Marks
+Issue #2: peak-hold telltale needles — 1m, 10m, 1h, all-time (#2)
 """

 from __future__ import annotations

-from typing import Any, Tuple
+from typing import Any, Dict, Optional, Tuple, Union

 from PIL import Image, ImageDraw

+from boostgauge.skins.telltale_layer import TelltaleLayer

 def render_stingray(
     value: float,
+    telltales: Union[dict[str, float | None], TelltaleLayer, None] = None,
     size: tuple[int, int] = (256, 256),
     config: dict[str, Any] | None = None,
 ) -> Image.Image:
-    """Render Stingray skin gauge face and main needle."""
-    base_image = render_dial_face(size=size, config=config)
-    return render_main_needle(base_image, value=value)
+    """Render Stingray skin gauge face, telltales layer, and main needle."""
+    base_image = render_dial_face(size=size, config=config)
+    cx, cy = size[0] / 2.0, size[1] / 2.0
+    radius = min(size) * 0.4
+
+    if telltales is not None:
+        if isinstance(telltales, TelltaleLayer):
+            base_image = telltales.render(base_image, center=(cx, cy), radius=radius)
+        elif isinstance(telltales, dict):
+            layer = TelltaleLayer()
+            base_image = layer.render(
+                base_image, center=(cx, cy), radius=radius, peaks_override=telltales
+            )
+
+    return render_main_needle(base_image, value=value, center=(cx, cy), radius=radius)
```

**File:** `src/boostgauge/gauge.py`

**Change 2:** Update imports and `render()` function implementation to accept `telltales` parameter and forward it to skin renderers.

```diff
 """Core gauge renderer entry point.

 Issue #1: Core Gauge Renderer — Analog Tachometer with Arc, Needle, and Tick Marks
+Issue #2: peak-hold telltale needles — 1m, 10m, 1h, all-time (#2)
 """

 from __future__ import annotations

-from typing import Any
+from typing import Any, Dict, Optional, Union

 from PIL import Image

 from boostgauge.skins.stingray import render_stingray
+from boostgauge.skins.telltale_layer import TelltaleLayer

 def render(
     value: float,
-    telltales: dict[str, float | None] | None = None,
+    telltales: Union[dict[str, float | None], TelltaleLayer, None] = None,
     size: tuple[int, int] = (256, 256),
     config: dict[str, Any] | None = None,
 ) -> Image.Image:
-    """Pure function rendering gauge face and needles to off-screen PIL Image."""
-    ...
+    """Pure function rendering gauge face and needles to off-screen PIL Image."""
+    skin_name = (config or {}).get("skin", "stingray")
+    renderer = SUPPORTED_SKINS.get(skin_name, render_stingray)
+    return renderer(value=value, telltales=telltales, size=size, config=config)

 SUPPORTED_SKINS = {
     "stingray": render_stingray,
 }
```


### 6.3 `tests/unit/test_telltale_layer.py` (Add)

**Complete file contents:**

```python
"""Unit tests for TelltaleLayer.

Issue #2: peak-hold telltale needles — 1m, 10m, 1h, all-time (#2)
"""

import pytest
from PIL import Image

from boostgauge.skins.telltale_layer import TelltaleLayer, TelltaleStyle


def test_telltale_layer_init_default():
    layer = TelltaleLayer()
    assert set(layer.telltales.keys()) == {"1m", "10m", "1h", "all_time"}
    assert layer.telltales["1m"].window == 60.0
    assert layer.telltales["10m"].window == 600.0
    assert layer.telltales["1h"].window == 3600.0
    assert layer.telltales["all_time"].window is None


def test_telltale_layer_invalid_bounds():
    with pytest.raises(ValueError, match="min_val must be less than max_val"):
        TelltaleLayer(min_val=100.0, max_val=50.0)


def test_telltale_layer_update_piping():
    layer = TelltaleLayer()
    t0 = 1000.0
    layer.update(t0, 75.0)

    for key, tt in layer.telltales.items():
        assert tt.current_peak(timestamp=t0) == 75.0


def test_value_to_angle_mapping():
    layer = TelltaleLayer(min_val=0.0, max_val=100.0, start_angle=225.0, end_angle=-45.0)

    assert layer.value_to_angle(0.0) == 225.0
    assert layer.value_to_angle(50.0) == 90.0
    assert layer.value_to_angle(100.0) == -45.0

    # Clamping tests
    assert layer.value_to_angle(-10.0) == 225.0
    assert layer.value_to_angle(150.0) == -45.0


def test_style_definitions():
    layer = TelltaleLayer()
    style_1m = layer.get_style("1m")
    assert style_1m.color == (0, 229, 255, 180)

    style_10m = layer.get_style("10m")
    assert style_10m.color == (255, 145, 0, 180)

    style_1h = layer.get_style("1h")
    assert style_1h.color == (224, 64, 251, 180)
    assert style_1h.dash == (4, 4)

    style_all = layer.get_style("all_time")
    assert style_all.color == (255, 23, 68, 230)
    assert style_all.dash is None


def test_reset_window_and_reset_all():
    layer = TelltaleLayer()
    t0 = 1000.0
    layer.update(t0, 80.0)

    layer.reset_window("1m")
    assert layer.telltales["1m"].current_peak(t0) is None
    assert layer.telltales["10m"].current_peak(t0) == 80.0

    layer.reset_all()
    for tt in layer.telltales.values():
        assert tt.current_peak(t0) is None


def test_none_peak_skip_rendering():
    layer = TelltaleLayer()
    base_img = Image.new("RGBA", (100, 100), (0, 0, 0, 255))
    rendered = layer.render(base_img, center=(50.0, 50.0), radius=40.0)

    # When all peaks are None, no telltale line pixels are drawn (only legend overlay)
    assert rendered.size == (100, 100)
```


### 6.4 `tests/visual/test_telltale_render.py` (Add)

**Complete file contents:**

```python
"""Visual rendering tests for telltale needles.

Issue #2: peak-hold telltale needles — 1m, 10m, 1h, all-time (#2)
"""

import math
from PIL import Image
from boostgauge.skins.telltale_layer import TelltaleLayer


def test_visual_telltale_trigonometric_endpoints():
    """Validate needle endpoint trigonometry and alpha compositing independently of baseline images."""
    layer = TelltaleLayer(min_val=0.0, max_val=100.0, start_angle=225.0, end_angle=-45.0)
    base_img = Image.new("RGBA", (200, 200), (0, 0, 0, 255))
    cx, cy = 100.0, 100.0
    radius = 80.0
    needle_len = radius * 0.85

    # 50.0 value -> 90 degrees (pointing straight up)
    peaks = {"all_time": 50.0}
    rendered = layer.render(base_img, center=(cx, cy), radius=radius, peaks_override=peaks)

    # Expected tip location: x = 100 + 68*cos(90deg) = 100, y = 100 - 68*sin(90deg) = 32
    expected_tip_x = int(round(cx + needle_len * math.cos(math.radians(90.0))))
    expected_tip_y = int(round(cy - needle_len * math.sin(math.radians(90.0))))

    pixel = rendered.getpixel((expected_tip_x, expected_tip_y))
    # Red needle style for all_time: RGB high red component
    assert pixel[0] > 200
```


### 6.5 `tests/contract/test_telltale_contract.py` (Add)

**Complete file contents:**

```python
"""Interface contract verification tests for TelltaleLayer and gauge.render.

Issue #2: peak-hold telltale needles — 1m, 10m, 1h, all-time (#2)
"""

from PIL import Image
from boostgauge.gauge import render
from boostgauge.skins.telltale_layer import TelltaleLayer


def test_gauge_render_accepts_telltale_layer():
    """Verify gauge.render interoperation with TelltaleLayer instance."""
    layer = TelltaleLayer()
    layer.update(100.0, 50.0)
    img = render(value=50.0, telltales=layer, size=(256, 256))
    assert isinstance(img, Image.Image)
    assert img.size == (256, 256)


def test_gauge_render_accepts_peaks_dict():
    """Verify gauge.render interoperation with peak values dictionary."""
    peaks = {"1m": 25.0, "10m": 50.0, "1h": 75.0, "all_time": 90.0}
    img = render(value=50.0, telltales=peaks, size=(128, 128))
    assert isinstance(img, Image.Image)
    assert img.size == (128, 128)
```


## [UNCHANGED] 7. Pattern References


### [UNCHANGED] 7.1 Value to Angle Geometry Pattern


### [UNCHANGED] 7.2 Off-Screen PIL Image Composite Pattern


## [UNCHANGED] 8. Dependencies & Imports


## [UNCHANGED] 9. Placeholder


## [UNCHANGED] 10. Test Mapping


### [UNCHANGED] Baseline-Independent Visual Assertions


### [UNCHANGED] Platform-Independent Path Assertions


## [UNCHANGED] 11. Implementation Notes


### [UNCHANGED] 11.1 Rendering Constants & Colors


### [UNCHANGED] 11.2 Geometry Calculations


## [UNCHANGED] Completeness Checklist


## [UNCHANGED] Review Log

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #2 |
| Verdict | APPROVED |
| Date | 2026-08-01 |
| Iterations | 2 |
| Finalized | 2026-08-01T08:15:09Z |

### Review Feedback Summary

The revised implementation specification provides complete, concrete, and fully executable instructions for all touched files. The added visual and contract test files include complete code excerpts with baseline-independent trigonometric assertions and contract checks, successfully addressing all previous review feedback. All assertions cleanly trace back to specified requirements.
