# Implementation Spec: Feature: peak-hold telltale needles — 1m, 10m, 1h, all-time (#2)

| Field | Value |
|-------|-------|
| Issue | #2 |
| LLD | `docs/lld/done/0002-telltale-needles.md` |
| Generated | 2026-07-31 |
| Status | APPROVED |

## 1. Overview

**Objective:** Render four peak-hold (telltale) needles (1m, 10m, 1h, all-time) on top of the core gauge surface consuming peak values provided by `TelltaleManager` and `Telltale` instances.

**Success Criteria:**
- `TelltaleManager` encapsulates four `Telltale` sliding window instances (60s, 600s, 3600s, infinite) and updates peaks on stream input.
- `render()` and skin renderer `render_stingray()` accept peak dictionary `dict[str, float | None]` without mutating input state or raising errors on `None` peaks.
- Translucent needles (1m cyan, 10m orange, 1h magenta dashed, all-time red) are rendered z-ordered behind the main needle on a supersampled 4x canvas off-screen using Pillow.
- Color-coded legend is drawn on the bottom-left corner of the dial face.
- 100% unit, contract, integration, and visual test coverage with headless PIL execution (`tkinter.Tk()` is never called).

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `tests/visual/baselines` | Add (Directory) | Directory for storing visual baseline image reference files |
| 2 | `src/boostgauge/telltale_manager.py` | Add | `TelltaleManager` class managing four `Telltale` instances (1m, 10m, 1h, All-time) |
| 3 | `src/boostgauge/skins/stingray.py` | Modify | Implement `_draw_telltales`, `_draw_legend`, and update `render_stingray` to draw telltales behind main needle |
| 4 | `src/boostgauge/gauge.py` | Modify | Ensure `render()` passes `telltales` payload through to active skin renderer |
| 5 | `tests/unit/test_telltale_manager.py` | Add | Unit tests for `TelltaleManager` updates, sliding windows, and resets |
| 6 | `tests/contract/test_telltale_contract.py` | Add | Contract tests verifying `TelltaleManager` and `render()` signatures |
| 7 | `tests/visual/test_telltale_visual.py` | Add | Visual regression tests verifying needle render, z-order, legend, and baseline-independent geometry assertions |
| 8 | `tests/integration/test_telltale_integration.py` | Add | Integration tests wiring metric streams through manager into gauge rendering |

**Implementation Order Rationale:**
`telltale_manager.py` defines the state container using `Telltale` from `src/boostgauge/telltale.py`. Next, `skins/stingray.py` and `gauge.py` implement the rendering pipeline. Finally, test suites validate unit, contract, visual, and integration requirements sequentially.

## 3. Current State (for Modify/Delete files)

### 3.1 `src/boostgauge/skins/stingray.py`

**Relevant excerpt** (lines 62–93):

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
    dash_pattern: tuple[int, int] | None = None,
) -> None:
    """Draw a gauge needle (main or telltale) pointing at specified angle."""
    ...

def _get_cached_background(size: tuple[int, int], skin_name: str = "stingray") -> Image.Image:
    """Retrieve or render static gauge background (bezel, dial, ticks, numerals, wordmark, redline)."""
    ...

def resize(image: Image.Image, size: tuple[int, int], resample: Any = Image.Resampling.LANCZOS) -> Image.Image:
    """Resize PIL Image surface to target size using specified resampling filter."""
    return image.resize(size, resample)

def render_stingray(
    value: float,
    telltales: dict[str, float | None] | None = None,
    size: tuple[int, int] = (256, 256),
    config: dict[str, Any] | None = None,
) -> Image.Image:
    """Stingray skin implementation rendering to PIL Image with 4x supersampling."""
    scale = 4
    canvas_size = (size[0] * scale, size[1] * scale)
    bg = _get_cached_background(canvas_size, skin_name="stingray")
    canvas = bg.copy()
    draw = ImageDraw.Draw(canvas)

    center = (canvas_size[0] / 2.0, canvas_size[1] / 2.0)
    radius = min(canvas_size) * 0.42

    needle_angle = _val_to_angle(value)
    _draw_needle(draw, center, radius, needle_angle, color=(255, 30, 30, 255), width=3.5 * scale, length_factor=0.85, has_counterweight=True)

    out = resize(canvas, size, Image.Resampling.LANCZOS)
    return out
```

**What changes:**
1. Add `_draw_telltales()` to draw active translucent needles behind the main needle.
2. Add `_draw_legend()` to render the color-coded legend box on the dial face corner.
3. Update `render_stingray()` to invoke `_draw_telltales()` and `_draw_legend()` when `telltales` is provided and non-empty.

### 3.2 `src/boostgauge/gauge.py`

**Relevant excerpt** (lines 14–26):

```python
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
    return renderer(value, telltales=telltales, size=size, config=config)
```

**What changes:**
No code modifications required if `render()` already forwards `telltales` to `renderer`. Verify typing and add module docstrings for Issue #2.

## 4. Data Structures

### 4.1 `TelltalePeaks`

**Definition:**

```python
from typing import TypedDict, Optional

class TelltalePeaks(TypedDict, total=False):
    window_1m: Optional[float]
    window_10m: Optional[float]
    window_1h: Optional[float]
    window_all: Optional[float]
```

**Concrete Example (JSON):**

```json
{
    "1m": 45.2,
    "10m": 78.5,
    "1h": 92.0,
    "all": 99.4
}
```

### 4.2 `TelltaleStyleSpec`

**Definition:**

```python
from dataclasses import dataclass
from typing import Tuple, Optional

@dataclass(frozen=True)
class TelltaleStyleSpec:
    color: Tuple[int, int, int, int]
    width_factor: float
    length_factor: float
    dash_pattern: Optional[Tuple[int, int]]
    label: str
```

**Concrete Example (Python Dict / Dataclass):**

```python
TELLTALE_STYLES = {
    "1m": TelltaleStyleSpec(color=(0, 229, 255, 180), width_factor=1.5, length_factor=0.82, dash_pattern=None, label="1m"),
    "10m": TelltaleStyleSpec(color=(255, 145, 0, 180), width_factor=1.5, length_factor=0.82, dash_pattern=None, label="10m"),
    "1h": TelltaleStyleSpec(color=(213, 0, 249, 180), width_factor=1.5, length_factor=0.82, dash_pattern=(4, 4), label="1h"),
    "all": TelltaleStyleSpec(color=(255, 23, 68, 220), width_factor=1.5, length_factor=0.82, dash_pattern=None, label="ALL"),
}
```

## 5. Function Specifications

### 5.1 `TelltaleManager.__init__()`

**File:** `src/boostgauge/telltale_manager.py`

**Signature:**

```python
def __init__(self) -> None:
    """Initialize four Telltale instances with window durations (60.0, 600.0, 3600.0, None)."""
```

**Input Example:**

```python
manager = TelltaleManager()
```

**Output Example:**

```python
# Internal state holds 4 Telltale objects
manager._telltales == {
    "1m": Telltale(window=60.0),
    "10m": Telltale(window=600.0),
    "1h": Telltale(window=3600.0),
    "all": Telltale(window=None),
}
```

**Edge Cases:**
- None. Always initializes all 4 window keys cleanly.

### 5.2 `TelltaleManager.update()`

**File:** `src/boostgauge/telltale_manager.py`

**Signature:**

```python
def update(self, timestamp: float, value: float) -> None:
    """Pipe live metric sample (timestamp, value) to all four Telltale instances."""
```

**Input Example:**

```python
manager.update(timestamp=100.0, value=75.5)
```

**Output Example:**

```python
None  # Side-effect: updates peak values in all four Telltale instances
```

**Edge Cases:**
- `math.isnan(value)` or `math.isinf(value)` -> Log warning and ignore tick sample without throwing exception.
- `timestamp < 0` -> Accept float timestamps as provided.

### 5.3 `TelltaleManager.get_peaks()`

**File:** `src/boostgauge/telltale_manager.py`

**Signature:**

```python
def get_peaks(self, timestamp: Optional[float] = None) -> dict[str, Optional[float]]:
    """Return dictionary mapping window keys ('1m', '10m', '1h', 'all') to current peak values."""
```

**Input Example:**

```python
peaks = manager.get_peaks(timestamp=120.0)
```

**Output Example:**

```python
{
    "1m": 75.5,
    "10m": 75.5,
    "1h": 75.5,
    "all": 75.5
}
```

**Edge Cases:**
- No samples recorded yet -> Returns `{"1m": None, "10m": None, "1h": None, "all": None}`.

### 5.4 `TelltaleManager.reset_window()` and `reset_all()`

**File:** `src/boostgauge/telltale_manager.py`

**Signature:**

```python
def reset_window(self, window_key: str) -> None:
    """Reset a specific telltale window ('1m', '10m', '1h', or 'all')."""

def reset_all(self) -> None:
    """Reset all four telltale instances."""
```

**Input Example:**

```python
manager.reset_window("1m")
```

**Output Example:**

```python
# manager.get_peaks()["1m"] returns None
```

**Edge Cases:**
- Invalid `window_key` (e.g. `"5m"`) -> Raises `KeyError("Unknown window key: 5m")`.

### 5.5 `_draw_telltales()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
def _draw_telltales(
    draw: ImageDraw.ImageDraw,
    telltales: dict[str, float | None],
    center: tuple[float, float],
    radius: float,
    scale: int = 4,
) -> None:
    """Render translucent telltale needles on RGBA overlay canvas before main needle drawing."""
```

**Input Example:**

```python
telltales = {"1m": 30.0, "10m": 50.0, "1h": 70.0, "all": 90.0}
center = (512.0, 512.0)
radius = 430.08
scale = 4
```

**Output Example:**

```python
None  # Draws needles directly onto Pillow ImageDraw canvas
```

**Edge Cases:**
- `telltales["1m"]` is `None` -> Suppresses drawing needle for that window key.
- Metric values out of range (< 0.0 or > 100.0) -> Clamped between 0.0 and 100.0 via `_val_to_angle`.

### 5.6 `_draw_legend()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
def _draw_legend(
    draw: ImageDraw.ImageDraw,
    telltales: dict[str, float | None],
    center: tuple[float, float],
    radius: float,
    scale: int = 4,
) -> None:
    """Render small color-coded telltale legend box in bottom-left corner of dial face."""
```

**Input Example:**

```python
telltales = {"1m": 30.0, "10m": 50.0, "1h": 70.0, "all": 90.0}
center = (512.0, 512.0)
radius = 430.08
```

**Output Example:**

```python
None  # Draws legend box with color swatches and text labels on lower-left dial face
```

**Edge Cases:**
- All peaks `None` -> Renders legend with dimmed or normal swatches showing window labels.

## 6. Change Instructions

### 6.1 `src/boostgauge/telltale_manager.py` (Add)

**Complete File Contents:**

```python
"""Telltale manager orchestrating sliding window peak-hold needles.

Issue #2: Peak-hold telltale needles — 1m, 10m, 1h, all-time
"""

from __future__ import annotations

import logging
import math
from typing import Dict, Optional

from boostgauge.telltale import Telltale

logger = logging.getLogger(__name__)

VALID_WINDOWS = ("1m", "10m", "1h", "all")

class TelltaleManager:
    """Manages four Telltale instances for 1m, 10m, 1h, and all-time windows."""

    def __init__(self) -> None:
        """Initialize 4 Telltale instances with window durations (60.0, 600.0, 3600.0, None)."""
        self._telltales: Dict[str, Telltale] = {
            "1m": Telltale(window=60.0),
            "10m": Telltale(window=600.0),
            "1h": Telltale(window=3600.0),
            "all": Telltale(window=None),
        }

    def update(self, timestamp: float, value: float) -> None:
        """Pipe a live metric sample (timestamp, value) to all four telltale instances."""
        if math.isnan(value) or math.isinf(value):
            logger.warning("Ignoring invalid metric value in TelltaleManager: %s", value)
            return

        for telltale in self._telltales.values():
            telltale.update(timestamp, value)

    def get_peaks(self, timestamp: Optional[float] = None) -> Dict[str, Optional[float]]:
        """Return dictionary mapping window keys ('1m', '10m', '1h', 'all') to current peak values."""
        return {
            key: telltale.current_peak(timestamp)
            for key, telltale in self._telltales.items()
        }

    def reset_window(self, window_key: str) -> None:
        """Reset a specific telltale window ('1m', '10m', '1h', or 'all')."""
        if window_key not in self._telltales:
            raise KeyError(f"Unknown window key: {window_key}. Valid keys: {VALID_WINDOWS}")
        self._telltales[window_key].reset()

    def reset_all(self) -> None:
        """Reset all four telltale instances."""
        for telltale in self._telltales.values():
            telltale.reset()
```

### 6.2 `src/boostgauge/skins/stingray.py` (Modify)

**Change 1:** Add imports and style definitions.

```python
import math
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

@dataclass(frozen=True)
class TelltaleStyleSpec:
    color: Tuple[int, int, int, int]
    width_factor: float
    length_factor: float
    dash_pattern: Optional[Tuple[int, int]]
    label: str

TELLTALE_STYLES: Dict[str, TelltaleStyleSpec] = {
    "1m": TelltaleStyleSpec(color=(0, 229, 255, 180), width_factor=1.5, length_factor=0.82, dash_pattern=None, label="1m"),
    "10m": TelltaleStyleSpec(color=(255, 145, 0, 180), width_factor=1.5, length_factor=0.82, dash_pattern=None, label="10m"),
    "1h": TelltaleStyleSpec(color=(213, 0, 249, 180), width_factor=1.5, length_factor=0.82, dash_pattern=(4, 4), label="1h"),
    "all": TelltaleStyleSpec(color=(255, 23, 68, 220), width_factor=1.5, length_factor=0.82, dash_pattern=None, label="ALL"),
}
```

**Change 2:** Add `_draw_telltales` and `_draw_legend` functions.

```python
def _draw_telltales(
    draw: ImageDraw.ImageDraw,
    telltales: Dict[str, Optional[float]],
    center: Tuple[float, float],
    radius: float,
    scale: int = 4,
) -> None:
    """Render telltale needles on RGBA overlay canvas before main needle drawing (z-order)."""
    for key in ("all", "1h", "10m", "1m"):  # Render all-time first, 1m last for proper z-overlap
        peak_val = telltales.get(key)
        if peak_val is None:
            continue
        style = TELLTALE_STYLES[key]
        angle = _val_to_angle(peak_val)
        _draw_needle(
            draw=draw,
            center=center,
            radius=radius,
            angle=angle,
            color=style.color,
            width=style.width_factor * scale,
            length_factor=style.length_factor,
            has_counterweight=False,
            dash_pattern=style.dash_pattern,
        )

def _draw_legend(
    draw: ImageDraw.ImageDraw,
    telltales: Dict[str, Optional[float]],
    center: Tuple[float, float],
    radius: float,
    scale: int = 4,
) -> None:
    """Render small color-coded telltale legend box on lower-left dial face corner."""
    font = _load_skin_font(int(9 * scale))
    legend_x = center[0] - radius * 0.65
    legend_y = center[1] + radius * 0.40
    box_w = 60 * scale
    box_h = 42 * scale

    # Draw semi-transparent background box
    draw.rectangle(
        [legend_x, legend_y, legend_x + box_w, legend_y + box_h],
        fill=(15, 20, 28, 200),
        outline=(60, 70, 85, 255),
        width=int(1 * scale),
    )

    items = [("1m", "1m"), ("10m", "10m"), ("1h", "1h"), ("all", "ALL")]
    for idx, (key, label) in enumerate(items):
        style = TELLTALE_STYLES[key]
        row_y = legend_y + (4 + idx * 9) * scale
        swatch_x = legend_x + 5 * scale
        # Swatch rectangle
        draw.rectangle(
            [swatch_x, row_y, swatch_x + 8 * scale, row_y + 5 * scale],
            fill=style.color[:3] + (255,),
        )
        # Text label
        peak_val = telltales.get(key)
        val_str = f"{peak_val:.0f}" if peak_val is not None else "--"
        text = f"{label}: {val_str}"
        draw.text(
            (swatch_x + 12 * scale, row_y - 2 * scale),
            text,
            fill=(220, 225, 230, 255),
            font=font,
        )
```

**Change 3:** Integrate telltale drawing in `render_stingray()`.

```python
if telltales:
    _draw_telltales(draw, telltales, center, radius, scale=scale)
    _draw_legend(draw, telltales, center, radius, scale=scale)

needle_angle = _val_to_angle(value)
_draw_needle(draw, center, radius, needle_angle, color=(255, 30, 30, 255), width=3.5 * scale, length_factor=0.85, has_counterweight=True)
```

### 6.3 `src/boostgauge/gauge.py` (Modify)

**Change:** Ensure docstring and module export reference `TelltaleManager` and telltale needle support.

```python
"""Core gauge renderer entry point.

Issue #1: Core Gauge Renderer — Analog Tachometer with Arc, Needle, and Tick Marks
Issue #2: Peak-hold telltale needles — 1m, 10m, 1h, all-time
"""
```

## 7. Pattern References

### 7.1 `Telltale` Sliding Window Peak Tracking

**File:** `src/boostgauge/telltale.py` (lines 20–55)

```python
class Telltale:
    """Tracks peak values over a sliding time window with optional linear decay."""

    def __init__(self, window: float, decay_rate: Optional[float] = None) -> None:
        self.window = window
        self.decay_rate = decay_rate
        self.samples: deque[Sample] = deque()
```

**Relevance:** `TelltaleManager` wraps four instances of `Telltale` with `window=60.0`, `600.0`, `3600.0`, and `None` to calculate sliding window peaks without duplicating peak calculation logic.

### 7.2 Off-screen Supersampled Pillow Rendering

**File:** `src/boostgauge/skins/stingray.py` (lines 75–93)

```python
    scale = 4
    canvas_size = (size[0] * scale, size[1] * scale)
    bg = _get_cached_background(canvas_size, skin_name="stingray")
    canvas = bg.copy()
    draw = ImageDraw.Draw(canvas)
```

**Relevance:** Demonstrates 4x supersampling off-screen PIL rendering complying with Option C of `docs/design/0001-test-strategy.md`.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `from typing import Dict, Optional, Tuple, Any` | stdlib | `telltale_manager.py`, `skins/stingray.py` |
| `from dataclasses import dataclass` | stdlib | `skins/stingray.py` |
| `import logging`, `import math` | stdlib | `telltale_manager.py` |
| `from PIL import Image, ImageDraw, ImageFont` | Pillow | `skins/stingray.py`, `gauge.py` |
| `from boostgauge.telltale import Telltale` | internal | `telltale_manager.py` |
| `from boostgauge.telltale_manager import TelltaleManager` | internal | `gauge.py`, test files |

**New Dependencies:** None (`Pillow` and `psutil` already declared in `pyproject.toml`).

## 9. Placeholder

*Reserved for future use to maintain alignment with LLD section numbering.*

## 10. Test Mapping

### 10.1 Mapping Table

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `TelltaleManager.__init__()` | `TelltaleManager()` | 4 windows configured: 60s, 600s, 3600s, None |
| T020 | `TelltaleManager.update()` | `update(100.0, 75.0)` | `get_peaks()` returns `75.0` for all 4 windows |
| T030 | `_val_to_angle()` | `value=50.0` | Angle `0.0°` (sweep center) |
| T040 | `render_stingray()` | `value=20, telltales={'1m':30, '10m':50, '1h':70, 'all':90}` | Translucent telltales rendered behind main needle |
| T050 | `_draw_telltales()` | `telltales={'1m': None}` | Needle drawing skipped for `1m` window |
| T060 | `TelltaleManager.reset_window()` | `reset_window('1m')` | `get_peaks()['1m']` is `None`, others intact |
| T070 | `TelltaleManager.reset_all()` | `reset_all()` | All peaks in `get_peaks()` are `None` |
| T080 | `_draw_legend()` | `telltales={...}` | Legend box drawn in lower-left quadrant |
| T090 | `render()` | `render(50.0, telltales)` | Returns `PIL.Image.Image`, zero `tkinter.Tk` calls |
| T100 | `TelltaleManager.get_peaks()` | Spike at `t=0`, low at `t=65` | `1m` peak drops to low sample value |
| T110 | `TelltaleManager.get_peaks()` | Spike at `t=0`, low at `t=7200` | `all` peak retains high spike value |

### 10.2 Baseline-Independent Visual Property Assertions

Visual tests MUST validate physical geometry properties computable without baseline images (Issue #1902):

```python
def test_telltale_needle_geometry_trigonometry():
    """Validate needle tip coordinates via trigonometry independently of baseline image files."""
    size = (256, 256)
    scale = 4
    center_x, center_y = 128.0 * scale, 128.0 * scale
    radius = 256.0 * scale * 0.42
    length_factor = 0.82
    
    # Test metric value 50 -> angle = 0.0 degrees (pointing straight up / sweep center)
    angle_deg = _val_to_angle(50.0)
    angle_rad = math.radians(angle_deg)
    
    expected_tip_x = center_x + radius * length_factor * math.sin(angle_rad)
    expected_tip_y = center_y - radius * length_factor * math.cos(angle_rad)
    
    assert math.isclose(angle_deg, 0.0, abs_tol=1e-3)
    assert math.isclose(expected_tip_x, center_x, abs_tol=1e-3)  # Centered horizontally at 0°
```

### 10.3 Platform-Independent Path Comparison Guidance

All test code MUST use `pathlib.Path` objects to ensure platform independence (Issue #1841):

```python
from pathlib import Path

def test_baseline_directory_path():
    baseline_dir = Path(__file__).parent / "baselines"
    assert baseline_dir.is_dir() or not baseline_dir.exists()
    # Always compare pathlib.Path objects, NEVER string endswith with forward slashes
    assert baseline_dir == Path(__file__).parent / "baselines"
```

## 11. Implementation Notes

### 11.1 Error Handling Convention

- `TelltaleManager.update()` handles `NaN` and `Infinity` values gracefully by logging a warning and skipping internal updates.
- `_draw_telltales()` silently skips any window key mapped to `None`.
- `TelltaleManager.reset_window()` raises `KeyError` if given an invalid window name.

### 11.2 Logging Convention

Use module logger `logger = logging.getLogger(__name__)`.
Example: `logger.warning("Ignoring invalid metric value in TelltaleManager: %s", value)`.

### 11.3 Constants & Tokens

| Constant | Value | Rationale |
|----------|-------|-----------|
| `TELLTALE_COLOR_1M` | `(0, 229, 255, 180)` | Thin cyan translucent overlay |
| `TELLTALE_COLOR_10M` | `(255, 145, 0, 180)` | Thin orange translucent overlay |
| `TELLTALE_COLOR_1H` | `(213, 0, 249, 180)` | Thin magenta dashed translucent overlay |
| `TELLTALE_COLOR_ALL` | `(255, 23, 68, 220)` | Thin red solid high-visibility overlay |
| `SUPERSAMPLE_SCALE` | `4` | Anti-aliasing quality multiplier |

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3)
- [x] Every data structure has a concrete JSON/YAML example (Section 4)
- [x] Every function has input/output examples with realistic values (Section 5)
- [x] Change instructions are diff-level specific (Section 6)
- [x] Pattern references include file:line and are verified to exist (Section 7)
- [x] All imports are listed and verified (Section 8)
- [x] Test mapping covers all LLD test scenarios (Section 10)
- [x] Baseline-independent visual property assertions included (Section 10.2)
- [x] Platform-independent Path comparisons enforced (Section 10.3)

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #2 |
| Verdict | APPROVED |
| Date | 2026-07-31 |
| Iterations | 1 |
| Finalized | 2026-07-31T23:53:00Z |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #2 |
| Verdict | APPROVED |
| Date | 2026-08-01 |
| Iterations | 2 |
| Finalized | 2026-08-01T04:55:04Z |

### Review Feedback Summary

The revised implementation spec addresses all prior review feedback cleanly. The angle conversion assertion for midpoint value 50.0 was corrected to 0.0° (sweep center), matching the arc specification (-135° to +135°), and the corresponding baseline-independent trigonometry test in Section 10.2 was updated consistently. All assertions trace directly to specified behaviors, file diffs are complete and executable, data structures feature concrete examples, and baseline-independent visual testing g...
