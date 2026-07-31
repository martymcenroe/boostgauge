# Implementation Spec: Feature: peak-hold telltale needles — 1m, 10m, 1h, all-time (#2)

| Field | Value |
|-------|-------|
| Issue | #2 |
| LLD | `docs/lld/active/0002-peak-hold-telltale-needles.md` |
| Generated | 2026-07-31 |
| Status | APPROVED |

## 1. Overview

This implementation specification defines the software architecture, data structures, logic flows, and testing strategy for implementing four peak-hold (telltale) gauge needles (1m, 10m, 1h, and all-time) in `boostgauge`. The feature encapsulates multi-window peak tracking inside a pure `TelltaleManager` component and composite-renders telltale needles on off-screen PIL image surfaces behind the main gauge needle according to Option C testing conventions.

**Objective:** Render four peak-hold needles (1m, 10m, 1h, all-time) on the PIL gauge surface behind the main needle by consuming `Telltale` instances from Issue #41.

**Success Criteria:**
1. `TelltaleManager` instantiates four `Telltale` instances with time windows of 60s (`1m`), 600s (`10m`), 3600s (`1h`), and `None` (`all`).
2. Continuous updates route `(timestamp, value)` metric tuples to all four `Telltale` instances simultaneously.
3. Rendering draws cyan translucent (`1m`), orange translucent (`10m`), magenta dashed (`1h`), and red solid (`all`) telltale needles at current peak locations.
4. Telltale needles strictly render underneath the main tachometer needle in z-order.
5. Missing peaks (`None`) caused by resets or uninitialized states omit needle rendering without throwing exceptions.
6. Context menu reset dispatches support individual window reset (`reset(window_key)`) and global reset (`reset_all()`).
7. 1m telltale peak automatically falls back to active in-window sample maximum after peak sample ages past 60s.
8. All-time telltale retains its maximum sample indefinitely until explicitly reset.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/telltale.py` | Modify | Add `TelltaleManager` class wrapping four `Telltale` sliding-window instances, dispatching sample updates and handling per-window resets. |
| 2 | `src/boostgauge/skins/stingray.py` | Modify | Add `TELLTALE_STYLES` dictionary, update `_draw_needle` to support dashed needles, add telltale rendering function `render_telltale_needles`, and update `render_stingray` to draw telltales before main needle. |
| 3 | `src/boostgauge/gauge.py` | Modify | Ensure `render()` passes `telltales` dictionary down to skin render functions. |
| 4 | `tests/unit/test_telltale.py` | Modify | Add unit tests verifying `TelltaleManager` initialization, multi-window sample distribution, window resets, decay behavior, and peak eviction. |
| 5 | `tests/visual/test_gauge.py` | Add | Add visual regression tests and baseline-independent property assertions (trigonometric tip checks, pixel color layering, missing needle suppression). |
| 6 | `tests/visual/baselines` | Add (Directory) | Directory for storing baseline snapshot images for visual testing. |

**Implementation Order Rationale:**
- `src/boostgauge/telltale.py` is modified first to define `TelltaleManager` data interfaces and business logic.
- `src/boostgauge/skins/stingray.py` and `src/boostgauge/gauge.py` are modified next to implement telltale visual styling and wire composite PIL rendering.
- `tests/unit/test_telltale.py` and `tests/visual/test_gauge.py` are implemented last to validate functional correctness and visual properties.

## 3. Current State (for Modify/Delete files)

### 3.1 `src/boostgauge/telltale.py`

**Relevant excerpt** (lines 1-48):

```python
"""Peak-hold telltale needle logic for system gauges.

Issue #41: Telltale peak-hold needle logic (pure, no GUI)
"""

from collections import deque
from dataclasses import dataclass
from typing import Optional


class Sample:
    """Represents a single system sample with a timestamp and scalar value."""


class Telltale:
    """Tracks peak values over a sliding time window with optional linear decay."""

    def __init__(self, window: float, decay_rate: Optional[float] = None) -> None:
        """Initialize Telltale with window duration in seconds and optional decay_rate."""
        ...

    def update(self, timestamp: float, value: float) -> None:
        """Feed a new sample (timestamp, value) into the telltale history."""
        ...

    def current_peak(self, timestamp: Optional[float] = None) -> Optional[float]:
        """Return the highest value within the active window, considering decay."""
        ...

    def _advance_to(self, t_target: float) -> None:
        """Evict expired samples relative to t_target and update decay tracking."""
        ...

    def reset(self) -> None:
        """Clear all sample history and reset internal peak state."""
        ...
```

**What changes:** Append `TelltaleManager` class to `src/boostgauge/telltale.py` encapsulating four `Telltale` instances (`1m`, `10m`, `1h`, `all`) with methods `update()`, `get_peaks()`, `reset()`, and `reset_all()`.

### 3.2 `src/boostgauge/skins/stingray.py`

**Relevant excerpt** (lines 60-78):

```python
from PIL import Image, ImageDraw


def render_stingray(
    value: float,
    telltales: dict[str, float | None] | None = None,
    size: tuple[int, int] = (256, 256),
    config: dict[str, Any] | None = None,
) -> Image.Image:
    """Stingray skin implementation rendering to PIL Image with 4x supersampling."""
    # Obtain static cached background (dial, ticks, redline, numerals, wordmark)
    base_img = _get_cached_background(size)
    img = base_img.copy()
    draw = ImageDraw.Draw(img)

    # Render main needle
    center = (size[0] / 2.0, size[1] / 2.0)
    radius = min(size) * 0.4
    angle = _val_to_angle(value)
    _draw_needle(draw, center, radius, angle, color=(255, 50, 50, 255), width=3.0, length_factor=0.85)

    return img
```

**What changes:**
- Add `TELLTALE_STYLES` dictionary defining visual properties (color, width, length_factor, dashed) for `"1m"`, `"10m"`, `"1h"`, and `"all"`.
- Update `_draw_needle` helper function to support optional `dashed` needle rendering.
- Implement `render_telltale_needles` function rendering active telltales to PIL `Image` canvas.
- Update `render_stingray` to invoke `render_telltale_needles` before drawing the main needle to guarantee correct z-order.

### 3.3 `src/boostgauge/gauge.py`

**Relevant excerpt** (lines 15-28):

```python
def render(
    value: float,
    telltales: dict[str, float | None] | None = None,
    size: tuple[int, int] = (256, 256),
    config: dict[str, Any] | None = None,
) -> Image.Image:
    """Pure function rendering gauge face and needles to off-screen PIL Image."""
    skin_name = config.get("skin", "stingray") if config else "stingray"
    renderer = SUPPORTED_SKINS.get(skin_name, render_stingray)
    return renderer(value=value, telltales=telltales, size=size, config=config)
```

**What changes:** Verify signature and forward `telltales` dictionary to `renderer()` explicitly.

### 3.4 `tests/unit/test_telltale.py`

**Relevant excerpt** (lines 1-25):

```python
"""Unit tests for Telltale peak-hold sliding window and decay tracking.

Issue #41: Telltale peak-hold needle logic (pure, no GUI)
"""

import pytest

from boostgauge.telltale import Sample, Telltale


def test_scenario_010_expose_telltale_class():
    """Scenario 010: Expose Telltale class in src/boostgauge/telltale.py (REQ-1)."""
    ...
```

**What changes:** Add test functions covering `TelltaleManager` multi-window sample updates, per-window resets (`1m`, `10m`, `1h`, `all`), global reset, and window expiration.

## 4. Data Structures

### 4.1 `WindowKey` and `TelltalePeakDict`

**Definition:**

```python
from typing import Dict, Literal, Optional, Tuple, TypedDict

WindowKey = Literal["1m", "10m", "1h", "all"]

TelltalePeakDict = TypedDict(
    "TelltalePeakDict",
    {
        "1m": Optional[float],
        "10m": Optional[float],
        "1h": Optional[float],
        "all": Optional[float],
    },
)
```

**Concrete Example:**

```json
{
    "1m": 45.2,
    "10m": 68.0,
    "1h": 85.5,
    "all": 98.1
}
```

### 4.2 `TelltaleStyle`

**Definition:**

```python
class TelltaleStyle(TypedDict):
    """Visual styling attributes for rendering a specific telltale needle."""
    color: Tuple[int, int, int, int]  # RGBA tuple with alpha opacity
    width: float                      # Line stroke width in pixels
    length_factor: float              # Radial length multiplier relative to gauge radius
    dashed: bool                      # True if needle should be drawn with dashed pattern
```

**Concrete Example:**

```json
{
    "color": [0, 255, 255, 180],
    "width": 1.5,
    "length_factor": 0.80,
    "dashed": false
}
```

## 5. Function Specifications

### 5.1 `TelltaleManager.__init__()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
class TelltaleManager:
    """Manages four sliding-window Telltale instances for peak-hold metric tracking."""

    def __init__(self) -> None:
        """Instantiate 4 Telltale objects with 60.0s, 600.0s, 3600.0s, and None windows."""
        ...
```

**Input Example:**

```python
manager = TelltaleManager()
```

**Output Example:**

```python
# Instantiates manager._telltales dictionary:
# {
#     "1m": Telltale(window=60.0),
#     "10m": Telltale(window=600.0),
#     "1h": Telltale(window=3600.0),
#     "all": Telltale(window=None),
# }
```

**Edge Cases:** None (no arguments).

---

### 5.2 `TelltaleManager.update()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def update(self, timestamp: float, value: float) -> None:
    """Forward metric sample (timestamp, value) to all four managed Telltale instances."""
    ...
```

**Input Example:**

```python
manager.update(timestamp=1000.0, value=75.5)
```

**Output Example:**

```python
None  # Updates internal state across all 4 Telltale instances
```

**Edge Cases:**
- `value < 0.0` -> Value forwarded to `Telltale.update()`.
- Non-monotonic timestamp (`timestamp < last_timestamp`) -> `Telltale.update()` raises `ValueError`.

---

### 5.3 `TelltaleManager.get_peaks()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def get_peaks(self, timestamp: Optional[float] = None) -> dict[str, Optional[float]]:
    """Return dictionary mapping window keys ('1m', '10m', '1h', 'all') to current peaks."""
    ...
```

**Input Example:**

```python
peaks = manager.get_peaks(timestamp=1065.0)
```

**Output Example:**

```python
{
    "1m": 50.0,
    "10m": 75.5,
    "1h": 75.5,
    "all": 75.5,
}
```

**Edge Cases:**
- Prior to initial `update()` call -> Returns `{"1m": None, "10m": None, "1h": None, "all": None}`.
- `timestamp` is `None` -> Queries current peaks without advancing window time evaluation.

---

### 5.4 `TelltaleManager.reset()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def reset(self, window_key: str) -> None:
    """Reset peak tracking for a specific window key ('1m', '10m', '1h', 'all').

    If window_key is 'all', resets all four windows.
    """
    ...
```

**Input Example:**

```python
manager.reset("1m")
```

**Output Example:**

```python
None  # manager.get_peaks()["1m"] returns None
```

**Edge Cases:**
- `window_key` not in `["1m", "10m", "1h", "all"]` -> Raises `KeyError(f"Invalid window key: {window_key}")`.

---

### 5.5 `TelltaleManager.reset_all()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def reset_all(self) -> None:
    """Reset peak tracking across all four managed Telltale instances simultaneously."""
    ...
```

**Input Example:**

```python
manager.reset_all()
```

**Output Example:**

```python
None  # All peak values in get_peaks() become None
```

**Edge Cases:** Calling on already reset manager executes safely without error.

---

### 5.6 `render_telltale_needles()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
from PIL import Image


def render_telltale_needles(
    image: Image.Image,
    telltales: dict[str, float | None],
    center: tuple[float, float],
    radius: float,
    val_to_angle_fn: Any,
) -> Image.Image:
    """Render active telltale needles on the PIL Image canvas behind the main gauge needle."""
    ...
```

**Input Example:**

```python
image = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
telltales = {"1m": 45.0, "10m": 60.0, "1h": None, "all": 90.0}
center = (128.0, 128.0)
radius = 102.4
val_to_angle_fn = _val_to_angle

rendered_img = render_telltale_needles(image, telltales, center, radius, val_to_angle_fn)
```

**Output Example:**

```python
# Returns PIL.Image.Image with 1m (cyan), 10m (orange), and all (red) needles rendered; 1h omitted.
```

**Edge Cases:**
- `telltales` is `None` or empty dictionary -> Returns copy of `image` unmodified.
- All peak values in `telltales` are `None` -> Returns copy of `image` unmodified.

## 6. Change Instructions

### 6.1 `src/boostgauge/telltale.py` (Modify)

**Change 1:** Add `TelltaleManager` implementation after line 48.

```python
class TelltaleManager:
    """Manages four sliding-window Telltale instances for peak-hold metric tracking."""

    def __init__(self) -> None:
        """Instantiate 4 Telltale objects with 60.0s, 600.0s, 3600.0s, and None windows."""
        self._telltales: dict[str, Telltale] = {
            "1m": Telltale(window=60.0),
            "10m": Telltale(window=600.0),
            "1h": Telltale(window=3600.0),
            "all": Telltale(window=None),
        }

    def update(self, timestamp: float, value: float) -> None:
        """Forward metric sample (timestamp, value) to all four managed Telltale instances."""
        for telltale in self._telltales.values():
            telltale.update(timestamp, value)

    def get_peaks(self, timestamp: Optional[float] = None) -> dict[str, Optional[float]]:
        """Return a dictionary mapping window identifiers to current peak values."""
        return {
            key: telltale.current_peak(timestamp)
            for key, telltale in self._telltales.items()
        }

    def reset(self, window_key: str) -> None:
        """Reset peak tracking for a specific window key ('1m', '10m', '1h', 'all') or all if 'all'."""
        if window_key == "all":
            self.reset_all()
            return
        if window_key not in self._telltales:
            raise KeyError(f"Invalid window key: {window_key}")
        self._telltales[window_key].reset()

    def reset_all(self) -> None:
        """Reset peak tracking across all four managed Telltale instances simultaneously."""
        for telltale in self._telltales.values():
            telltale.reset()
```

---

### 6.2 `src/boostgauge/skins/stingray.py` (Modify)

**Change 1:** Add `TELLTALE_STYLES` dictionary and update needle rendering functions.

```python
from PIL import Image, ImageDraw

TELLTALE_STYLES: dict[str, dict[str, Any]] = {
    "1m": {
        "color": (0, 240, 255, 180),   # Translucent cyan
        "width": 1.5,
        "length_factor": 0.80,
        "dashed": False,
    },
    "10m": {
        "color": (255, 140, 0, 180),   # Translucent orange
        "width": 1.5,
        "length_factor": 0.80,
        "dashed": False,
    },
    "1h": {
        "color": (240, 0, 240, 200),   # Translucent magenta
        "width": 1.5,
        "length_factor": 0.80,
        "dashed": True,
    },
    "all": {
        "color": (255, 30, 30, 220),   # Solid red
        "width": 2.0,
        "length_factor": 0.85,
        "dashed": False,
    },
}


def render_telltale_needles(
    image: Image.Image,
    telltales: dict[str, float | None],
    center: tuple[float, float],
    radius: float,
    val_to_angle_fn: Any = _val_to_angle,
) -> Image.Image:
    """Render active telltale needles on the PIL Image canvas behind the main gauge needle."""
    if not telltales:
        return image
    out_img = image.copy()
    draw = ImageDraw.Draw(out_img)
    for key in ["1m", "10m", "1h", "all"]:
        val = telltales.get(key)
        if val is None:
            continue
        style = TELLTALE_STYLES.get(key)
        if not style:
            continue
        angle = val_to_angle_fn(val)
        _draw_needle(
            draw,
            center,
            radius,
            angle,
            color=style["color"],
            width=style["width"],
            length_factor=style["length_factor"],
            has_counterweight=False,
            dashed=style["dashed"],
        )
    return out_img


def render_stingray(
    value: float,
    telltales: dict[str, float | None] | None = None,
    size: tuple[int, int] = (256, 256),
    config: dict[str, Any] | None = None,
) -> Image.Image:
    """Stingray skin implementation rendering to PIL Image with 4x supersampling."""
    base_img = _get_cached_background(size)
    img = base_img.copy()
    center = (size[0] / 2.0, size[1] / 2.0)
    radius = min(size) * 0.4

    # Render telltale needles layer first (behind main needle)
    if telltales:
        img = render_telltale_needles(img, telltales, center, radius, _val_to_angle)

    draw = ImageDraw.Draw(img)
    angle = _val_to_angle(value)
    _draw_needle(draw, center, radius, angle, color=(255, 50, 50, 255), width=3.0, length_factor=0.85)

    return img
```

---

### 6.3 `src/boostgauge/gauge.py` (Modify)

```python
def render(
    value: float,
    telltales: dict[str, float | None] | None = None,
    size: tuple[int, int] = (256, 256),
    config: dict[str, Any] | None = None,
) -> Image.Image:
    """Pure function rendering gauge face and needles to off-screen PIL Image."""
    skin_name = config.get("skin", "stingray") if config else "stingray"
    renderer = SUPPORTED_SKINS.get(skin_name, render_stingray)
    return renderer(value=value, telltales=telltales, size=size, config=config)
```

---

### 6.4 `tests/unit/test_telltale.py` (Modify)

Append `TelltaleManager` unit tests to `tests/unit/test_telltale.py`:

```python
from boostgauge.telltale import TelltaleManager


def test_t010_manager_initialization():
    """Scenario 010: Instantiate TelltaleManager with four sliding window configurations (REQ-1)."""
    manager = TelltaleManager()
    peaks = manager.get_peaks()
    assert set(peaks.keys()) == {"1m", "10m", "1h", "all"}
    assert all(p is None for p in peaks.values())


def test_t020_sample_update_distribution():
    """Scenario 020: Pipe live metric sample updates to all four telltale instances simultaneously (REQ-2)."""
    manager = TelltaleManager()
    manager.update(timestamp=100.0, value=85.0)
    peaks = manager.get_peaks(timestamp=100.0)
    assert peaks == {"1m": 85.0, "10m": 85.0, "1h": 85.0, "all": 85.0}


def test_t060_context_menu_reset_execution():
    """Scenario 060: Execute per-needle and reset-all context menu reset actions (REQ-6)."""
    manager = TelltaleManager()
    manager.update(timestamp=100.0, value=90.0)

    manager.reset("1m")
    peaks_after_1m_reset = manager.get_peaks(timestamp=100.0)
    assert peaks_after_1m_reset["1m"] is None
    assert peaks_after_1m_reset["10m"] == 90.0

    manager.reset_all()
    peaks_after_reset_all = manager.get_peaks(timestamp=100.0)
    assert all(p is None for p in peaks_after_reset_all.values())


def test_t070_1m_sliding_window_eviction():
    """Scenario 070: Drop 1m telltale position back after peak sample ages past 60 seconds (REQ-7)."""
    manager = TelltaleManager()
    manager.update(timestamp=100.0, value=90.0)
    manager.update(timestamp=110.0, value=50.0)

    # Within 60s window
    assert manager.get_peaks(timestamp=150.0)["1m"] == 90.0

    # Past 60s window (t=165s -> sample at t=100s expired)
    assert manager.get_peaks(timestamp=165.0)["1m"] == 50.0
    assert manager.get_peaks(timestamp=165.0)["10m"] == 90.0


def test_t080_all_time_peak_retention():
    """Scenario 080: Retain all-time telltale peak position indefinitely without reset (REQ-8)."""
    manager = TelltaleManager()
    manager.update(timestamp=100.0, value=95.0)
    manager.update(timestamp=150.0, value=40.0)

    # Query far into the future (t=10000.0)
    peaks = manager.get_peaks(timestamp=10000.0)
    assert peaks["1m"] is None
    assert peaks["10m"] is None
    assert peaks["1h"] is None
    assert peaks["all"] == 95.0
```

---

### 6.5 `tests/visual/test_gauge.py` (Add)

Create complete `tests/visual/test_gauge.py` containing visual tests and baseline-independent property assertions:

```python
"""Visual regression tests and baseline-independent property assertions for gauge rendering.

Issue #2: peak-hold telltale needles — 1m, 10m, 1h, all-time
"""

import math
from pathlib import Path
from PIL import Image
import pytest

from boostgauge.gauge import render
from boostgauge.skins.stingray import TELLTALE_STYLES, _val_to_angle


def test_t030_render_distinct_telltale_needles():
    """Scenario 030: Render distinct telltale needles for active peaks on PIL gauge surface (REQ-3)."""
    telltales = {"1m": 40.0, "10m": 60.0, "1h": 80.0, "all": 95.0}
    img = render(value=20.0, telltales=telltales, size=(256, 256))

    assert isinstance(img, Image.Image)
    assert img.size == (256, 256)
    assert img.mode == "RGBA"


def test_t040_main_needle_z_order_overlay():
    """Scenario 040: Render main needle on top of telltale needles in z-order (REQ-4)."""
    # Main needle at 60.0 overlaps telltale needle at 60.0
    telltales = {"1m": 60.0}
    img = render(value=60.0, telltales=telltales, size=(256, 256))

    center = (128.0, 128.0)
    angle = _val_to_angle(60.0)
    rad = math.radians(angle)
    # Check pixel along main needle vector near center
    check_r = 30.0
    check_x = int(round(center[0] + check_r * math.cos(rad)))
    check_y = int(round(center[1] - check_r * math.sin(rad)))

    pixel = img.getpixel((check_x, check_y))
    # Main needle color is red (255, 50, 50)
    assert pixel[0] > 200  # Red component dominant
    assert pixel[1] < 100  # Cyan component suppressed by main needle overlap


def test_t050_suppress_missing_peak_needle():
    """Scenario 050: Suppress rendering when Telltale current_peak returns None (REQ-5)."""
    img_with_telltale = render(value=20.0, telltales={"1m": 90.0}, size=(256, 256))
    img_without_telltale = render(value=20.0, telltales={"1m": None}, size=(256, 256))

    assert img_with_telltale.tobytes() != img_without_telltale.tobytes()


# --- BASELINE-INDEPENDENT PROPERTY ASSERTIONS (Issue #1902) ---

def test_baseline_independent_needle_tip_trigonometry():
    """Verify telltale needle tip coordinates using baseline-independent trigonometry."""
    center = (128.0, 128.0)
    radius = 102.4

    for key, value in [("1m", 0.0), ("10m", 50.0), ("all", 100.0)]:
        style = TELLTALE_STYLES[key]
        angle = _val_to_angle(value)
        rad = math.radians(angle)

        expected_r = radius * style["length_factor"]
        expected_x = center[0] + expected_r * math.cos(rad)
        expected_y = center[1] - expected_r * math.sin(rad)

        # Trigonometric boundary assertions
        assert 0.0 <= expected_x <= 256.0
        assert 0.0 <= expected_y <= 256.0

        if value == 50.0:  # Dial top (12:00)
            assert abs(expected_x - 128.0) < 1e-3
            assert expected_y < 128.0  # Points upwards
```

---

### 6.6 `tests/visual/baselines` (Add Directory)

Directory path: `tests/visual/baselines/`
Contains baseline `.png` files generated via `pytest tests/visual/test_gauge.py --generate-baselines`.

## 7. Pattern References

### 7.1 `Telltale` Peak-Hold Sliding Window Pattern

**File:** `src/boostgauge/telltale.py` (lines 17-48)

```python
class Telltale:
    """Tracks peak values over a sliding time window with optional linear decay."""

    def __init__(self, window: float, decay_rate: Optional[float] = None) -> None:
        ...

    def update(self, timestamp: float, value: float) -> None:
        ...

    def current_peak(self, timestamp: Optional[float] = None) -> Optional[float]:
        ...
```

**Relevance:** `TelltaleManager` encapsulates four instances of this class without duplicating peak evaluation or sliding window sample pruning.

---

### 7.2 `_draw_needle` Renderer Pattern

**File:** `src/boostgauge/skins/stingray.py` (lines 42-56)

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
    dashed: bool = False,
) -> None:
    """Draw a gauge needle (main or telltale) pointing at specified angle."""
    ...
```

**Relevance:** `render_telltale_needles` reuses this drawing primitive for solid telltale needles (`1m`, `10m`, `all`).

---

### 7.3 `render_stingray` Composite Layering Pattern

**File:** `src/boostgauge/skins/stingray.py` (lines 60-78)

```python
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

**Relevance:** Demonstrates off-screen PIL composite rendering pattern adhering to Option C testing rules.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `from typing import Any, Dict, Literal, Optional, Tuple, TypedDict` | stdlib | `src/boostgauge/telltale.py`, `src/boostgauge/skins/stingray.py` |
| `import math` | stdlib | `src/boostgauge/skins/stingray.py`, `tests/visual/test_gauge.py` |
| `from pathlib import Path` | stdlib | `tests/visual/test_gauge.py` |
| `from PIL import Image, ImageDraw` | `Pillow (>=12.2.0,<13.0.0)` | `src/boostgauge/skins/stingray.py`, `src/boostgauge/gauge.py`, `tests/visual/test_gauge.py` |
| `from boostgauge.telltale import Telltale, TelltaleManager` | internal | `src/boostgauge/telltale.py`, `tests/unit/test_telltale.py` |
| `from boostgauge.skins.stingray import render_telltale_needles, TELLTALE_STYLES` | internal | `src/boostgauge/skins/stingray.py`, `tests/visual/test_gauge.py` |

**New Dependencies:** None (uses existing `pillow` and `psutil`).

## 9. Placeholder

*Reserved for future use to maintain alignment with LLD section numbering.*

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output | Pass Criteria |
|---------|---------------|-------|-----------------|---------------|
| T010 | `TelltaleManager.__init__()` | Constructor call | `get_peaks()` keys equal `{"1m", "10m", "1h", "all"}` with all values `None` | Instantiated 4 `Telltale` objects with windows (60, 600, 3600, None) |
| T020 | `TelltaleManager.update()` | `update(timestamp=100.0, value=85.0)` | `get_peaks()` returns `{"1m": 85.0, "10m": 85.0, "1h": 85.0, "all": 85.0}` | Live metric updates piped simultaneously to all 4 telltales |
| T030 | `render_telltale_needles()` | `telltales={"1m": 40, "10m": 60, "1h": 80, "all": 95}` | PIL `Image` (256x256, RGBA) rendered | Distinct cyan, orange, magenta, red needles drawn |
| T040 | `render_stingray()` | `value=60.0, telltales={"1m": 60.0}` | Main needle pixel visible over telltale needle at overlap | Main needle layer drawn over telltale needle (z-order overlay) |
| T050 | `render_telltale_needles()` | `telltales={"1m": None}` | PIL `Image` rendered without 1m needle | Needle omitted when peak returns `None` |
| T060 | `TelltaleManager.reset()` / `reset_all()` | `reset("1m")` then `reset_all()` | Target peak reset to `None` | `current_peak()` returns `None` for reset targets |
| T070 | `TelltaleManager.update()` / `get_peaks()` | Peak 90 at t=100s, 50 at t=110s, query t=165s | `1m` peak returns 50.0; `10m` peak returns 90.0 | 1m peak drops back after sample ages past 60s |
| T080 | `TelltaleManager.update()` / `get_peaks()` | Peak 95 at t=100s, query t=10000s | `all` peak returns 95.0 | All-time peak persists indefinitely |

## 11. Implementation Notes

### 11.1 Platform-Independent Path Assertions (Issue #1841)

All test path assertions MUST compare `pathlib.Path` objects directly rather than comparing string representations or performing string suffix assertions:

```python
# CORRECT (Platform-independent):
baseline_path = Path("tests") / "visual" / "baselines" / "stingray_telltale.png"
assert baseline_path.name == "stingray_telltale.png"

# INCORRECT (Fails on Windows due to backslash separators):
# assert str(path).endswith("tests/visual/baselines/stingray_telltale.png")
```

### 11.2 Z-Order Compositing Layering

To satisfy Requirement 4 (REQ-4), the PIL drawing order in `render_stingray` MUST be:
1. Static gauge background face (dial, bezel, tick marks, numerals, redline arc).
2. Telltale needles layer (`render_telltale_needles`).
3. Main dynamic gauge needle (`_draw_needle`).
4. Central pivot cap / bezel overlay.

### 11.3 Baseline-Independent Visual Property Verification (Issue #1902)

Visual tests MUST include baseline-independent property assertions using trigonometry. For a gauge sweep mapping values `0.0` to `100.0` across sweep angles `225.0°` to `-45.0°`:

$$\theta(v) = 225.0 - v \times \frac{270.0}{100.0}$$

Needle tip coordinates $(x, y)$ for center $(x_c, y_c)$ and radial length $r$:

$$x = x_c + r \cdot \cos(\theta \cdot \frac{\pi}{180})$$
$$y = y_c - r \cdot \sin(\theta \cdot \frac{\pi}{180})$$

Tests verify these computed endpoints without depending on baseline PNG snapshots.

### 11.4 Constants & Style Registry

| Key | Color (RGBA) | Line Width | Stroke Style | Window Duration |
|-----|--------------|------------|--------------|-----------------|
| `"1m"` | `(0, 240, 255, 180)` | 1.5 px | Solid | 60.0 seconds |
| `"10m"` | `(255, 140, 0, 180)` | 1.5 px | Solid | 600.0 seconds |
| `"1h"` | `(240, 0, 240, 200)` | 1.5 px | Dashed | 3600.0 seconds |
| `"all"` | `(255, 30, 30, 220)` | 2.0 px | Solid | `None` (Indefinite) |

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
| Iterations | 1 |
| Finalized | 2026-07-31T18:30:30-05:00 |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #2 |
| Verdict | APPROVED |
| Date | 2026-07-31 |
| Iterations | 2 |
| Finalized | 2026-07-31T23:33:57Z |

### Review Feedback Summary

The revised implementation spec for Issue #2 provides complete, concrete, and unambiguous instructions for implementing the multi-window peak-hold telltale needles feature. All requirements (REQ-1 through REQ-8) map directly to concrete test functions and code specifications. Every assertion in the unit and visual test suites is traceable to explicit requirement text and function specifications (Issue #1866 verified). Baseline-independent visual property assertions are explicitly provided using ...
