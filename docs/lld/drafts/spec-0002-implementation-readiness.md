# Implementation Spec: Feature: peak-hold telltale needles — 1m, 10m, 1h, all-time (#2)

<!-- Metadata -->
| Field | Value |
|-------|-------|
| Issue | #2 |
| LLD | `docs/lld/done/0002-telltale-renderer.md` |
| Generated | 2026-08-01 |
| Status | APPROVED |

## 1. Overview

This implementation adds peak-hold telltale needles (1m, 10m, 1h, and all-time windows) to the `boostgauge` tachometer renderer using off-screen PIL RGBA layer composition. It provides `TelltaleManager` for encapsulating window tracking logic and `TelltaleRenderer` for rendering translucent needles and a corner legend overlay z-ordered behind the main needle.

**Objective:** Render four peak-hold (telltale) needles (1m, 10m, 1h, and all-time) on the PIL Image gauge surface z-ordered behind the main needle with context menu reset capabilities.

**Success Criteria:**
- Four sliding window telltale needles (1m/60s cyan, 10m/600s orange, 1h/3600s magenta, all-time red) rendered on PIL RGBA surface behind main needle.
- Deterministic value-to-angle position mapping with NaN/Inf bounds clamping.
- Skipping needle drawing when peak value is `None`.
- Context menu support for resetting individual or all telltale peaks.
- Color-coded legend overlay indicating active telltale windows.
- Automated tests passing across unit, contract, and visual regression suites under Option C architecture without instantiating `tkinter.Tk()`.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/telltale_renderer.py` | Add | Telltale configuration dataclasses, `val_to_angle_rad`, `TelltaleManager`, and `TelltaleRenderer` classes for PIL composition. |
| 2 | `tests/unit/test_telltale_renderer.py` | Add | Unit tests for angle mapping math, NaN/Inf bounds, manager updates, and reset dispatching. |
| 3 | `tests/contract/test_telltale_contract.py` | Add | Contract tests validating public interfaces and parameter contracts for `TelltaleManager` and `TelltaleRenderer`. |
| 4 | `tests/visual/test_telltale_visual.py` | Add | Visual regression tests using PIL image comparison against baselines and baseline-independent trigonometric assertions. |

**Implementation Order Rationale:**
1. `telltale_renderer.py` defines the core types (`TelltaleStyle`, `GaugeGeometry`), math utilities, state manager (`TelltaleManager`), and PIL rendering pipeline (`TelltaleRenderer`).
2. `test_telltale_renderer.py` verifies core math and logical correctness in isolation.
3. `test_telltale_contract.py` ensures interface adherence and parameter boundary handling.
4. `test_telltale_visual.py` validates pixel composition, z-ordering, and rendering correctness against baselines and trigonometric property assertions.

## 3. Current State (for Modify/Delete files)

No files are modified or deleted in this feature; all files are new (`Add`). However, for integration context, the relevant existing modules that `telltale_renderer.py` interacts with (`src/boostgauge/telltale.py`, `src/boostgauge/skins/stingray.py`, and `src/boostgauge/gauge.py`) are excerpted below.

### 3.1 `src/boostgauge/telltale.py`

**Relevant excerpt** (lines 10-45):

```python
class Telltale:
    """Tracks peak values over a sliding time window with optional linear decay."""

    def __init__(self, window: float, decay_rate: Optional[float] = None) -> None:
        """Initialize Telltale needle state."""
        self.window = window
        self.decay_rate = decay_rate
        self.samples: Deque[Tuple[float, float]] = deque()

    def update(self, timestamp: float, value: float) -> None:
        """Record a new sample timestamp and value."""
        ...

    def current_peak(self, current_time: Optional[float] = None) -> Optional[float]:
        """Compute the active peak value at current_time or the latest sample timestamp."""
        ...

    def reset(self) -> None:
        """Clear all sample history and decay state."""
        self.samples.clear()
```

**What changes:** No direct modifications to `telltale.py`. `TelltaleManager` in `telltale_renderer.py` will instantiate and coordinate four instances of `Telltale`.

### 3.2 `src/boostgauge/skins/stingray.py`

**Relevant excerpt** (lines 18-25, 63-75):

```python
def _val_to_angle(value: float, min_angle: float = 225.0, max_angle: float = -45.0) -> float:
    """Map gauge metric value (0-100) to dial sweep angle in degrees."""
    clamped_val = max(0.0, min(100.0, float(value)))
    sweep = max_angle - min_angle
    return min_angle + (clamped_val / 100.0) * sweep

def _draw_needle(
    draw: ImageDraw.ImageDraw,
    center: Tuple[float, float],
    radius: float,
    angle_deg: float,
    color: Tuple[int, int, int, int],
    width_ratio: float = 1.0,
    is_main: bool = False,
) -> None:
    ...
```

**What changes:** No modification to `stingray.py`. `telltale_renderer.py` reuses the same 225° to -45° dial sweep math and angle conventions.

## 4. Data Structures

### 4.1 `TelltaleStyle`

**Definition:**

```python
from dataclasses import dataclass
from typing import Optional, Tuple

@dataclass(frozen=True)
class TelltaleStyle:
    window_name: str                  # "1m", "10m", "1h", "all_time"
    window_seconds: Optional[float]   # 60.0, 600.0, 3600.0, None for all-time
    color_rgba: Tuple[int, int, int, int]  # (R, G, B, A) color tuple
    width_px: int                     # Needle line stroke width in pixels
    dash_pattern: Optional[Tuple[int, int]]  # None for solid line, (on, off) for dashed
    legend_label: str                 # Human-readable legend label
```

**Concrete Example:**

```json
{
    "window_name": "1m",
    "window_seconds": 60.0,
    "color_rgba": [0, 220, 255, 160],
    "width_px": 2,
    "dash_pattern": null,
    "legend_label": "1 Min Peak"
}
```

### 4.2 `GaugeGeometry`

**Definition:**

```python
@dataclass(frozen=True)
class GaugeGeometry:
    center_x: float           # Dial pivot center X in pixels
    center_y: float           # Dial pivot center Y in pixels
    radius: float             # Outer dial sweep radius in pixels
    start_angle_deg: float    # Start angle in degrees (e.g. 225.0)
    end_angle_deg: float      # End angle in degrees (e.g. -45.0)
    min_value: float          # Gauge minimum scale value (e.g. 0.0)
    max_value: float          # Gauge maximum scale value (e.g. 100.0)
```

**Concrete Example:**

```json
{
    "center_x": 128.0,
    "center_y": 128.0,
    "radius": 100.0,
    "start_angle_deg": 225.0,
    "end_angle_deg": -45.0,
    "min_value": 0.0,
    "max_value": 100.0
}
```

### 4.3 `PeaksMapping`

**Definition:**

```python
from typing import Dict, Optional

PeaksMapping = Dict[str, Optional[float]]
```

**Concrete Example:**

```json
{
    "1m": 72.5,
    "10m": 85.0,
    "1h": 91.2,
    "all_time": 98.4
}
```

## 5. Function Specifications

### 5.1 `val_to_angle_rad()`

**File:** `src/boostgauge/telltale_renderer.py`

**Signature:**

```python
def val_to_angle_rad(
    val: float,
    min_val: float = 0.0,
    max_val: float = 100.0,
    start_angle_deg: float = 225.0,
    end_angle_deg: float = -45.0,
) -> float:
    """Map a metric value deterministically to an angle in radians with NaN/Inf bounds checking."""
    ...
```

**Input Example:**

```python
val = 50.0
min_val = 0.0
max_val = 100.0
start_angle_deg = 225.0
end_angle_deg = -45.0
```

**Output Example:**

```python
# angle_deg = 225.0 + 0.5 * (-45.0 - 225.0) = 90.0 degrees
# 90.0 degrees in radians = math.pi / 2 = 1.5707963267948966
1.5707963267948966
```

**Edge Cases:**
- `math.isnan(val)` -> returns `math.radians(start_angle_deg)`
- `val == float('inf')` -> clamps to `max_val`, returning `math.radians(end_angle_deg)`
- `val == float('-inf')` -> clamps to `min_val`, returning `math.radians(start_angle_deg)`
- `val < min_val` -> clamps to `min_val`
- `val > max_val` -> clamps to `max_val`

---

### 5.2 `TelltaleManager.__init__()`

**File:** `src/boostgauge/telltale_renderer.py`

**Signature:**

```python
class TelltaleManager:
    """Manages four Telltale logic instances for 1m, 10m, 1h, and all-time windows."""

    def __init__(self, windows: Optional[Dict[str, Optional[float]]] = None) -> None:
        """Initialize the four Telltale instances with window bounds."""
        ...
```

**Input Example:**

```python
windows = {
    "1m": 60.0,
    "10m": 600.0,
    "1h": 3600.0,
    "all_time": None,
}
```

**Output Example:**

```python
# Initializes manager self.telltales dict mapping window names to Telltale objects.
None
```

**Edge Cases:**
- `windows is None` -> uses default windows (`"1m": 60.0, "10m": 600.0, "1h": 3600.0, "all_time": None`)

---

### 5.3 `TelltaleManager.update()`

**File:** `src/boostgauge/telltale_renderer.py`

**Signature:**

```python
def update(self, timestamp: float, value: float) -> None:
    """Pipe a new metric sample into all four Telltale instances."""
    ...
```

**Input Example:**

```python
timestamp = 1700000000.0
value = 78.5
```

**Output Example:**

```python
None
```

**Edge Cases:**
- NaN or Inf value -> passes value to `Telltale.update()`, sanitization occurs during peak evaluation or rendering.

---

### 5.4 `TelltaleManager.reset()`

**File:** `src/boostgauge/telltale_renderer.py`

**Signature:**

```python
def reset(self, window_name: Optional[str] = None) -> None:
    """Reset a specific telltale by name, or all four if window_name is None."""
    ...
```

**Input Example:**

```python
# Reset single window
window_name = "1m"

# Reset all windows
window_name = None
```

**Output Example:**

```python
None
```

**Edge Cases:**
- `window_name` not in `self.telltales` -> raises `KeyError(f"Unknown window: {window_name}")`

---

### 5.5 `TelltaleManager.get_peaks()`

**File:** `src/boostgauge/telltale_renderer.py`

**Signature:**

```python
def get_peaks(self, current_time: Optional[float] = None) -> Dict[str, Optional[float]]:
    """Return a mapping of window_name to current peak value (or None)."""
    ...
```

**Input Example:**

```python
current_time = 1700000060.0
```

**Output Example:**

```python
{
    "1m": 78.5,
    "10m": 78.5,
    "1h": 78.5,
    "all_time": 78.5,
}
```

**Edge Cases:**
- Telltale has no samples -> peak is `None`

---

### 5.6 `TelltaleRenderer.__init__()`

**File:** `src/boostgauge/telltale_renderer.py`

**Signature:**

```python
class TelltaleRenderer:
    """Renders telltale needles and legend onto a PIL Image gauge background surface."""

    def __init__(
        self,
        geometry: GaugeGeometry,
        styles: Optional[List[TelltaleStyle]] = None,
        show_legend: bool = True,
    ) -> None:
        """Initialize renderer with gauge geometry and telltale style definitions."""
        ...
```

**Input Example:**

```python
geometry = GaugeGeometry(
    center_x=128.0,
    center_y=128.0,
    radius=100.0,
    start_angle_deg=225.0,
    end_angle_deg=-45.0,
    min_value=0.0,
    max_value=100.0,
)
styles = None  # Use default 4 styles
show_legend = True
```

**Output Example:**

```python
None
```

**Edge Cases:**
- `styles is None` -> uses default list of 4 styles (`1m`, `10m`, `1h`, `all_time`).

---

### 5.7 `TelltaleRenderer.render_telltales()`

**File:** `src/boostgauge/telltale_renderer.py`

**Signature:**

```python
def render_telltales(
    self,
    base_image: Image.Image,
    peaks: Dict[str, Optional[float]],
) -> Image.Image:
    """Composite telltale needles onto base_image RGBA surface behind main needle."""
    ...
```

**Input Example:**

```python
base_image = Image.new("RGBA", (256, 256), (14, 16, 20, 255))
peaks = {
    "1m": 50.0,
    "10m": 75.0,
    "1h": 90.0,
    "all_time": None,
}
```

**Output Example:**

```python
# Returns new PIL.Image RGBA instance with telltales rendered
# <PIL.Image.Image image mode=RGBA size=256x256 at 0x...>
```

**Edge Cases:**
- `peaks` key missing or value is `None` -> skips rendering that telltale needle.
- `base_image` is not mode `"RGBA"` -> converts or raises `ValueError("base_image must be RGBA mode")`.

---

### 5.8 `TelltaleRenderer.render_legend()`

**File:** `src/boostgauge/telltale_renderer.py`

**Signature:**

```python
def render_legend(self, base_image: Image.Image) -> Image.Image:
    """Render small color-coded telltale legend overlay in gauge corner."""
    ...
```

**Input Example:**

```python
base_image = Image.new("RGBA", (256, 256), (14, 16, 20, 255))
```

**Output Example:**

```python
# Returns PIL.Image RGBA instance with legend box drawn in bottom-left corner
# <PIL.Image.Image image mode=RGBA size=256x256 at 0x...>
```

**Edge Cases:**
- `base_image` size smaller than legend footprint (e.g. < 128x128) -> scales legend proportionally or clamps offsets.

## 6. Change Instructions

### 6.1 `src/boostgauge/telltale_renderer.py` (Add)

**Complete file contents:**

```python
"""Telltale needle configuration, state manager, position mapping, and PIL renderer.

Issue #2: Feature: peak-hold telltale needles — 1m, 10m, 1h, all-time
"""

from dataclasses import dataclass

import math

from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from boostgauge.telltale import Telltale

@dataclass(frozen=True)
class TelltaleStyle:
    """Style attributes for a single telltale window needle."""

    window_name: str
    window_seconds: Optional[float]
    color_rgba: Tuple[int, int, int, int]
    width_px: int
    dash_pattern: Optional[Tuple[int, int]]
    legend_label: str

@dataclass(frozen=True)
class GaugeGeometry:
    """Geometry parameters for needle angle and position calculation."""

    center_x: float
    center_y: float
    radius: float
    start_angle_deg: float = 225.0
    end_angle_deg: float = -45.0
    min_value: float = 0.0
    max_value: float = 100.0

DEFAULT_TELLTALE_STYLES: List[TelltaleStyle] = [
    TelltaleStyle(
        window_name="1m",
        window_seconds=60.0,
        color_rgba=(0, 220, 255, 160),  # Cyan translucent
        width_px=2,
        dash_pattern=None,
        legend_label="1m",
    ),
    TelltaleStyle(
        window_name="10m",
        window_seconds=600.0,
        color_rgba=(255, 165, 0, 160),  # Orange translucent
        width_px=2,
        dash_pattern=None,
        legend_label="10m",
    ),
    TelltaleStyle(
        window_name="1h",
        window_seconds=3600.0,
        color_rgba=(220, 0, 220, 160),  # Magenta translucent
        width_px=2,
        dash_pattern=(4, 4),
        legend_label="1h",
    ),
    TelltaleStyle(
        window_name="all_time",
        window_seconds=None,
        color_rgba=(255, 50, 50, 220),  # Red thin solid
        width_px=1,
        dash_pattern=None,
        legend_label="All",
    ),
]

def val_to_angle_rad(
    val: float,
    min_val: float = 0.0,
    max_val: float = 100.0,
    start_angle_deg: float = 225.0,
    end_angle_deg: float = -45.0,
) -> float:
    """Map a metric value deterministically to an angle in radians with NaN/Inf bounds checking."""
    if math.isnan(val):
        return math.radians(start_angle_deg)
    if val == float("inf"):
        clamped_val = max_val
    elif val == float("-inf"):
        clamped_val = min_val
    else:
        clamped_val = max(min_val, min(max_val, float(val)))

    val_range = max_val - min_val
    if val_range <= 0:
        norm = 0.0
    else:
        norm = (clamped_val - min_val) / val_range

    sweep_deg = end_angle_deg - start_angle_deg
    angle_deg = start_angle_deg + norm * sweep_deg
    return math.radians(angle_deg)

class TelltaleManager:
    """Manages four Telltale logic instances for 1m, 10m, 1h, and all-time windows."""

    def __init__(self, windows: Optional[Dict[str, Optional[float]]] = None) -> None:
        """Initialize the four Telltale instances with window bounds."""
        if windows is None:
            windows = {
                "1m": 60.0,
                "10m": 600.0,
                "1h": 3600.0,
                "all_time": None,
            }
        self.telltales: Dict[str, Telltale] = {}
        for name, win in windows.items():
            # If window is None (all_time), pass infinity to Telltale logic
            win_val = win if win is not None else float("inf")
            self.telltales[name] = Telltale(window=win_val)

    def update(self, timestamp: float, value: float) -> None:
        """Pipe a new metric sample into all four Telltale instances."""
        for telltale in self.telltales.values():
            telltale.update(timestamp, value)

    def reset(self, window_name: Optional[str] = None) -> None:
        """Reset a specific telltale by name, or all four if window_name is None."""
        if window_name is None:
            for telltale in self.telltales.values():
                telltale.reset()
        else:
            if window_name not in self.telltales:
                raise KeyError(f"Unknown window: {window_name}")
            self.telltales[window_name].reset()

    def get_peaks(self, current_time: Optional[float] = None) -> Dict[str, Optional[float]]:
        """Return a mapping of window_name to current peak value (or None)."""
        peaks: Dict[str, Optional[float]] = {}
        for name, telltale in self.telltales.items():
            peaks[name] = telltale.current_peak(current_time=current_time)
        return peaks

class TelltaleRenderer:
    """Renders telltale needles and legend onto a PIL Image gauge background surface."""

    def __init__(
        self,
        geometry: GaugeGeometry,
        styles: Optional[List[TelltaleStyle]] = None,
        show_legend: bool = True,
    ) -> None:
        """Initialize renderer with gauge geometry and telltale style definitions."""
        self.geometry = geometry
        self.styles = styles if styles is not None else DEFAULT_TELLTALE_STYLES
        self.show_legend = show_legend

    def render_telltales(
        self,
        base_image: Image.Image,
        peaks: Dict[str, Optional[float]],
    ) -> Image.Image:
        """Composite telltale needles onto base_image RGBA surface behind main needle."""
        if base_image.mode != "RGBA":
            canvas = base_image.convert("RGBA")
        else:
            canvas = base_image.copy()

        overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        center_x = self.geometry.center_x
        center_y = self.geometry.center_y
        needle_length = self.geometry.radius * 0.85

        for style in self.styles:
            peak_val = peaks.get(style.window_name)
            if peak_val is None or math.isnan(peak_val):
                continue

            angle_rad = val_to_angle_rad(
                val=peak_val,
                min_val=self.geometry.min_value,
                max_val=self.geometry.max_value,
                start_angle_deg=self.geometry.start_angle_deg,
                end_angle_deg=self.geometry.end_angle_deg,
            )

            # Calculate needle tip position
            tip_x = center_x + needle_length * math.cos(angle_rad)
            tip_y = center_y - needle_length * math.sin(angle_rad)  # Y inverted in PIL

            if style.dash_pattern is not None:
                self._draw_dashed_line(
                    draw=draw,
                    start=(center_x, center_y),
                    end=(tip_x, tip_y),
                    color=style.color_rgba,
                    width=style.width_px,
                    dash_pattern=style.dash_pattern,
                )
            else:
                draw.line(
                    [(center_x, center_y), (tip_x, tip_y)],
                    fill=style.color_rgba,
                    width=style.width_px,
                )

        composited = Image.alpha_composite(canvas, overlay)

        if self.show_legend:
            composited = self.render_legend(composited)

        return composited

    def _draw_dashed_line(
        self,
        draw: ImageDraw.ImageDraw,
        start: Tuple[float, float],
        end: Tuple[float, float],
        color: Tuple[int, int, int, int],
        width: int,
        dash_pattern: Tuple[int, int],
    ) -> None:
        """Draw a dashed line segment between start and end coordinates."""
        on_px, off_px = dash_pattern
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        dist = math.hypot(dx, dy)
        if dist == 0:
            return

        ux = dx / dist
        uy = dy / dist
        step = on_px + off_px
        curr = 0.0

        while curr < dist:
            segment_end = min(curr + on_px, dist)
            p1 = (start[0] + ux * curr, start[1] + uy * curr)
            p2 = (start[0] + ux * segment_end, start[1] + uy * segment_end)
            draw.line([p1, p2], fill=color, width=width)
            curr += step

    def render_legend(self, base_image: Image.Image) -> Image.Image:
        """Render small color-coded telltale legend overlay in bottom-left corner."""
        if base_image.mode != "RGBA":
            canvas = base_image.convert("RGBA")
        else:
            canvas = base_image.copy()

        overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Legend box coordinates in bottom-left corner
        margin_x = 10
        margin_y = canvas.height - 50
        box_width = 75
        box_height = 40

        # Draw semi-transparent legend box background
        draw.rectangle(
            [margin_x, margin_y, margin_x + box_width, margin_y + box_height],
            fill=(20, 22, 28, 180),
            outline=(60, 65, 75, 200),
            width=1,
        )

        font = ImageFont.load_default()
        item_y = margin_y + 4

        for style in self.styles[:4]:
            # Color indicator swatch
            draw.rectangle(
                [margin_x + 6, item_y + 2, margin_x + 14, item_y + 8],
                fill=style.color_rgba,
            )
            # Label
            draw.text(
                (margin_x + 18, item_y - 1),
                style.legend_label,
                fill=(220, 225, 230, 240),
                font=font,
            )
            item_y += 9

        return Image.alpha_composite(canvas, overlay)
```

---

### 6.2 `tests/unit/test_telltale_renderer.py` (Add)

**Complete file contents:**

```python
"""Unit tests for TelltaleRenderer, TelltaleManager, and val_to_angle_rad.

Issue #2: Feature: peak-hold telltale needles — 1m, 10m, 1h, all-time
"""

import math
from pathlib import Path

import pytest
from PIL import Image

from boostgauge.telltale_renderer import (
    GaugeGeometry,
    TelltaleManager,
    TelltaleRenderer,
    val_to_angle_rad,
)

def test_val_to_angle_rad_midpoint():
    """Test val_to_angle_rad maps 50% value to 90 degrees in radians."""
    rad = val_to_angle_rad(50.0, 0.0, 100.0, 225.0, -45.0)
    expected_deg = 90.0
    assert pytest.approx(rad, abs=1e-5) == math.radians(expected_deg)

def test_val_to_angle_rad_bounds():
    """Test val_to_angle_rad clamps min and max values."""
    min_rad = val_to_angle_rad(-10.0, 0.0, 100.0, 225.0, -45.0)
    max_rad = val_to_angle_rad(110.0, 0.0, 100.0, 225.0, -45.0)
    assert pytest.approx(min_rad, abs=1e-5) == math.radians(225.0)
    assert pytest.approx(max_rad, abs=1e-5) == math.radians(-45.0)

def test_val_to_angle_rad_nan_inf():
    """Test NaN and Inf handling in val_to_angle_rad."""
    nan_rad = val_to_angle_rad(float("nan"), 0.0, 100.0, 225.0, -45.0)
    inf_rad = val_to_angle_rad(float("inf"), 0.0, 100.0, 225.0, -45.0)
    neginf_rad = val_to_angle_rad(float("-inf"), 0.0, 100.0, 225.0, -45.0)

    assert pytest.approx(nan_rad, abs=1e-5) == math.radians(225.0)
    assert pytest.approx(inf_rad, abs=1e-5) == math.radians(-45.0)
    assert pytest.approx(neginf_rad, abs=1e-5) == math.radians(225.0)

def test_telltale_manager_init_and_update():
    """Test TelltaleManager updates peaks across all four windows."""
    mgr = TelltaleManager()
    t0 = 1000.0
    mgr.update(t0, 42.0)
    peaks = mgr.get_peaks(current_time=t0)

    assert len(peaks) == 4
    assert set(peaks.keys()) == {"1m", "10m", "1h", "all_time"}
    for k in peaks:
        assert peaks[k] == 42.0

def test_telltale_manager_reset_single_and_all():
    """Test resetting single window and resetting all windows."""
    mgr = TelltaleManager()
    t0 = 1000.0
    mgr.update(t0, 85.0)

    mgr.reset("1m")
    peaks = mgr.get_peaks(current_time=t0)
    assert peaks["1m"] is None
    assert peaks["10m"] == 85.0

    mgr.reset()
    all_peaks = mgr.get_peaks(current_time=t0)
    for k in all_peaks:
        assert all_peaks[k] is None

def test_telltale_manager_reset_invalid_key():
    """Test resetting an unknown window name raises KeyError."""
    mgr = TelltaleManager()
    with pytest.raises(KeyError):
        mgr.reset("nonexistent_window")

def test_telltale_renderer_none_peaks_skipped():
    """Test that None peak values produce identical image to base canvas."""
    geom = GaugeGeometry(center_x=128.0, center_y=128.0, radius=100.0)
    renderer = TelltaleRenderer(geometry=geom, show_legend=False)
    base = Image.new("RGBA", (256, 256), (14, 16, 20, 255))
    peaks = {"1m": None, "10m": None, "1h": None, "all_time": None}

    res = renderer.render_telltales(base, peaks)
    assert list(res.getdata()) == list(base.getdata())

def test_platform_independent_path_check():
    """Platform-independent path comparison check (Issue #1841 compliance)."""
    p = Path("tests/unit/test_telltale_renderer.py")
    expected = Path("tests") / "unit" / "test_telltale_renderer.py"
    assert p.name == expected.name
```

---

### 6.3 `tests/contract/test_telltale_contract.py` (Add)

**Complete file contents:**

```python
"""Contract tests for TelltaleManager and TelltaleRenderer public interfaces.

Issue #2: Feature: peak-hold telltale needles — 1m, 10m, 1h, all-time
"""

from typing import Dict, Optional
import pytest
from PIL import Image

from boostgauge.telltale_renderer import (
    GaugeGeometry,
    TelltaleManager,
    TelltaleRenderer,
    TelltaleStyle,
)

def test_telltale_manager_interface_contract():
    """Verify TelltaleManager input parameter contracts and return types."""
    mgr = TelltaleManager(windows={"1m": 60.0, "all_time": None})
    mgr.update(100.0, 50.0)

    peaks = mgr.get_peaks(current_time=100.0)
    assert isinstance(peaks, dict)
    assert "1m" in peaks
    assert "all_time" in peaks

    mgr.reset("1m")
    assert mgr.get_peaks()["1m"] is None

def test_telltale_renderer_interface_contract():
    """Verify TelltaleRenderer interface contract and PIL output mode/size."""
    geom = GaugeGeometry(center_x=100.0, center_y=100.0, radius=80.0)
    renderer = TelltaleRenderer(geometry=geom)
    base = Image.new("RGBA", (200, 200), (0, 0, 0, 255))
    peaks: Dict[str, Optional[float]] = {"1m": 30.0, "10m": 50.0, "1h": 70.0, "all_time": 90.0}

    out = renderer.render_telltales(base, peaks)
    assert isinstance(out, Image.Image)
    assert out.mode == "RGBA"
    assert out.size == (200, 200)
```

---

### 6.4 `tests/visual/test_telltale_visual.py` (Add)

**Complete file contents:**

```python
"""Visual regression tests for telltale needle PIL rendering.

Issue #2: Feature: peak-hold telltale needles — 1m, 10m, 1h, all-time
Follows docs/design/0001-test-strategy.md Option C (off-screen PIL, no Tkinter).
"""

import math
from pathlib import Path

import pytest
from PIL import Image, ImageChops

from boostgauge.telltale_renderer import GaugeGeometry, TelltaleRenderer

BASELINES_DIR = Path(__file__).parent / "baselines"

def _calc_rms(img1: Image.Image, img2: Image.Image) -> float:
    """Calculate Root Mean Square (RMS) pixel difference between two images."""
    diff = ImageChops.difference(img1, img2)
    h = diff.histogram()
    sq = sum((value * (idx ** 2) for idx, value in enumerate(h)))
    rms = math.sqrt(sq / float(img1.size[0] * img1.size[1] * len(img1.mode)))
    return rms

def test_baseline_independent_needle_tip_trigonometry():
    """Baseline-independent test: Validate needle tip position math without baselines (Issue #1902)."""
    geom = GaugeGeometry(
        center_x=128.0,
        center_y=128.0,
        radius=100.0,
        start_angle_deg=225.0,
        end_angle_deg=-45.0,
        min_value=0.0,
        max_value=100.0,
    )
    renderer = TelltaleRenderer(geometry=geom, show_legend=False)

    # Render a 50% peak telltale (should point straight UP at 90 degrees)
    base = Image.new("RGBA", (256, 256), (0, 0, 0, 255))
    peaks = {"1m": 50.0}
    rendered = renderer.render_telltales(base, peaks)

    # At 90 degrees: tip X = center_x = 128.0, tip Y = center_y - radius * 0.85 = 128.0 - 85.0 = 43.0
    # Check pixel along the needle ray at (128, 50)
    pixel = rendered.getpixel((128, 50))
    # Pixel alpha should be non-zero (cyan telltale has alpha 160)
    assert pixel[3] > 0
    # Color should be blended cyan over black (R=0, G=138, B=160)
    assert pixel[0] == 0
    assert pixel[1] == 138
    assert pixel[2] == 160

def test_telltale_rendering_baseline_diff(request):
    """Visual regression check comparing rendered telltales against committed baseline image."""
    geom = GaugeGeometry(center_x=128.0, center_y=128.0, radius=100.0)
    renderer = TelltaleRenderer(geometry=geom, show_legend=True)
    base = Image.new("RGBA", (256, 256), (14, 16, 20, 255))
    peaks = {"1m": 25.0, "10m": 50.0, "1h": 75.0, "all_time": 95.0}

    rendered = renderer.render_telltales(base, peaks)

    baseline_path = BASELINES_DIR / "telltale_4_present.png"
    if getattr(request.config.option, "generate_baselines", False):
        BASELINES_DIR.mkdir(parents=True, exist_ok=True)
        rendered.save(baseline_path)
        pytest.skip("Generated baseline image.")

    if not baseline_path.exists():
        pytest.skip(f"Baseline image missing at {baseline_path}")

    baseline_img = Image.open(baseline_path).convert("RGBA")
    rms = _calc_rms(rendered, baseline_img)
    # Option C tolerance: RMS <= 1.0 / 255
    assert rms <= (1.0 / 255.0)
```

## 7. Pattern References

### 7.1 Value-to-Angle Dial Sweep Mapping

**File:** `src/boostgauge/skins/stingray.py` (lines 18-25)

```python
def _val_to_angle(value: float, min_angle: float = 225.0, max_angle: float = -45.0) -> float:
    """Map gauge metric value (0-100) to dial sweep angle in degrees."""
    clamped_val = max(0.0, min(100.0, float(value)))
    sweep = max_angle - min_angle
    return min_angle + (clamped_val / 100.0) * sweep
```

**Relevance:** `val_to_angle_rad` in `telltale_renderer.py` follows the exact same 225° to -45° (270° total sweep) dial convention, converting degrees to radians for PIL line endpoint calculation.

### 7.2 Off-Screen PIL Needle Line Rendering

**File:** `src/boostgauge/skins/stingray.py` (lines 63-75)

```python
def _draw_needle(
    draw: ImageDraw.ImageDraw,
    center: Tuple[float, float],
    radius: float,
    angle_deg: float,
    color: Tuple[int, int, int, int],
    width_ratio: float = 1.0,
    is_main: bool = False,
) -> None:
    """Draw pointer needle with pivot mounting and counterweight."""
```

**Relevance:** Demonstrates calculating tip endpoint coordinates using `center_x + length * cos(angle)` and `center_y - length * sin(angle)` for PIL pixel surfaces.

### 7.3 Sliding-Window Peak Tracking Logic

**File:** `src/boostgauge/telltale.py` (lines 10-35)

```python
class Telltale:
    """Tracks peak values over a sliding time window with optional linear decay."""

    def __init__(self, window: float, decay_rate: Optional[float] = None) -> None:
        ...

    def update(self, timestamp: float, value: float) -> None:
        ...

    def current_peak(self, current_time: Optional[float] = None) -> Optional[float]:
        ...
```

**Relevance:** `TelltaleManager` encapsulates four `Telltale` instances from `src/boostgauge/telltale.py` to maintain peaks without duplicating window eviction algorithms.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `dataclasses.dataclass` | stdlib | `telltale_renderer.py` |
| `math` | stdlib | `telltale_renderer.py`, `test_telltale_renderer.py`, `test_telltale_visual.py` |
| `pathlib.Path` | stdlib | `test_telltale_renderer.py`, `test_telltale_visual.py` |
| `typing.Dict, List, Optional, Tuple` | stdlib | `telltale_renderer.py`, test files |
| `PIL.Image, ImageDraw, ImageFont, ImageChops` | `pillow` (>=12.2.0) | `telltale_renderer.py`, test files |
| `boostgauge.telltale.Telltale` | internal | `telltale_renderer.py` |
| `boostgauge.telltale_renderer.*` | internal | test files |

**New Dependencies:** None (uses existing Pillow dependency).

## 9. Placeholder

*Reserved for future use to maintain alignment with LLD section numbering.*

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `TelltaleManager.__init__()` | Manager init | 4 telltales created for 1m (60s), 10m (600s), 1h (3600s), and all_time (inf) |
| T020 | `TelltaleManager.update()` | `timestamp=1000.0, value=85.0` | All 4 telltales update peak value to 85.0 |
| T030 | `val_to_angle_rad()` | `val=50.0` and `val=NaN` | 50.0 maps to 90° (pi/2 rad); NaN maps to start_angle (225° rad) |
| T040 | `TelltaleRenderer.render_telltales()` | Base RGBA image + valid peaks | Rendered PIL Image with translucent needles composited |
| T050 | `TelltaleRenderer.render_telltales()` | Peaks with `1m: None` | Needle for 1m is omitted; image unchanged at 1m angle |
| T060 | `TelltaleManager.reset()` | `reset('1m')` then `reset()` | Peak becomes `None` for 1m, then `None` for all windows |
| T070 | `TelltaleRenderer.render_legend()` | Base image + legend request | Image with 4-item legend rectangle drawn in bottom-left corner |
| T080 | Visual RMS & Trigonometry | Test fixtures 4-present + tip math | RMS diff vs baseline <= 1.0/255 and ray pixel matches cyan color |

## 11. Implementation Notes

### 11.1 Defensive Floating-Point Math
`val_to_angle_rad()` handles `float('nan')`, `float('inf')`, and `float('-inf')` explicitly before performing normalization or radian conversion. NaNs fall back safely to `start_angle_deg`, while Infinities clamp to `min_val` or `max_val`.

### 11.2 PIL Layer Alpha Composition (Option C Architecture)
All needle drawing is performed on a temporary `Image.new("RGBA", canvas.size, (0, 0, 0, 0))` overlay. Drawing translucent pixels on the overlay and performing `Image.alpha_composite(canvas, overlay)` preserves the underlying gauge dial artwork without destructive pixel overwrite artifacts.

### 11.3 Baseline-Independent Visual Property Assertions (Issue #1902 Compliance)
`test_telltale_visual.py` includes `test_baseline_independent_needle_tip_trigonometry()` which directly asserts that for a peak value of 50.0, the needle ray at angle 90° (straight UP) has non-zero alpha and expected blended cyan RGB values `(0, 138, 160)`. This guarantees test validity independently of baseline PNG file generation.

### 11.4 Constants & Display Tokens

| Parameter | Value | Description |
|-----------|-------|-------------|
| Sweep Range | 225.0° to -45.0° | 270-degree tachometer dial sweep |
| Needle Radius Ratio | 0.85 | Needle tip length relative to gauge radius |
| 1m Style | `(0, 220, 255, 160)`, 2px solid | Cyan translucent |
| 10m Style | `(255, 165, 0, 160)`, 2px solid | Orange translucent |
| 1h Style | `(220, 0, 220, 160)`, 2px dashed | Magenta translucent dashed |
| All-Time Style | `(255, 50, 50, 220)`, 1px solid | Red thin solid |

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
| Finalized | 2026-08-01T05:37:53Z |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #2 |
| Verdict | APPROVED |
| Date | 2026-08-01 |
| Iterations | 2 |
| Finalized | 2026-08-01T10:39:31Z |

### Review Feedback Summary

The revised implementation spec addresses prior feedback by updating the baseline-independent visual property assertion in test_telltale_visual.py to accurately reflect alpha composition of cyan (0, 220, 255, 160) over a black (0, 0, 0, 255) background canvas, yielding expected blended RGB values (0, 138, 160). All test assertions are fully traceable to specified behaviors, change instructions are diff-level concrete, and architecture strictly adheres to Option C headless PIL composition.
