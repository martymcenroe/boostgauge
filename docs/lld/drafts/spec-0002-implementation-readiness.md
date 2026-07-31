# Implementation Spec: peak-hold telltale needles — 1m, 10m, 1h, all-time (#2)

| Field | Value |
|-------|-------|
| Issue | #2 |
| LLD | `docs/lld/active/LLD-002.md` |
| Generated | 2026-07-31 |
| Status | APPROVED |

## 1. Overview

This implementation spec defines the exact code changes required to render four peak-hold (telltale) needles (1m, 10m, 1h, all-time) behind the main gauge needle on an off-screen PIL surface, adhering to Option C of `docs/design/0001-test-strategy.md`.

**Objective:** Render four peak-hold needles (1m, 10m, 1h, all-time) on top of the PIL gauge face behind the main needle, consuming `Telltale` instances from #41.

**Success Criteria:**
- `TelltaleManager` encapsulates 4 `Telltale` sliding-window instances (60s, 600s, 3600s, None).
- Live metric samples are piped simultaneously to all 4 telltales on every update.
- Off-screen PIL gauge renderer (Stingray skin) renders 4 distinct telltale needles (1m cyan translucent, 10m orange translucent, 1h magenta translucent dashed, all-time solid red) behind the main needle layer.
- Needles with `None` peak state (post-reset or uninitialized) are omitted from the render.
- Individual window resets ("m1", "m10", "h1", "all") and `reset_all()` clear peak state.
- 100% test coverage with unit tests in `tests/unit/test_telltale.py` and visual regression tests (with baseline-independent assertions) in `tests/visual/test_gauge.py`.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `tests/visual/baselines` | Add (Directory) | Baseline directory for visual regression test image blobs. |
| 2 | `src/boostgauge/telltale.py` | Add | Class `Telltale` (sliding-window peak hold) and `TelltaleManager` encapsulating 4 telltale windows, sample routing, and reset dispatching. |
| 3 | `src/boostgauge/skins/stingray.py` | Add | Stingray skin renderer implementing dial face, tick marks, 4 telltale needles layer, and main dynamic needle layer. |
| 4 | `src/boostgauge/gauge.py` | Add | Main gauge rendering entry point handling skin dispatch, telltales layer composition, and main needle rendering. |
| 5 | `tests/unit/test_telltale.py` | Add | Unit tests for `Telltale` and `TelltaleManager` sample routing, peak state retrieval, sliding window eviction, and reset dispatches. |
| 6 | `tests/visual/test_gauge.py` | Add | Render-pixel visual regression tests for telltale rendering, post-reset needle suppression, main needle z-order, and baseline-independent geometry assertions. |

**Implementation Order Rationale:**
1. `telltale.py` provides the core data structures and sliding-window logic consumed by all subsequent modules.
2. `skins/stingray.py` provides the visual rendering functions for dial geometry, telltales layer, and main needle.
3. `gauge.py` provides the composite rendering facade consuming `telltale.py` and `skins/stingray.py`.
4. `test_telltale.py` validates the pure state logic of `Telltale` and `TelltaleManager`.
5. `test_gauge.py` validates the off-screen PIL image rendering, z-ordering, and visual output against baselines.

## 3. Current State (for Modify/Delete files)

This feature is a greenfield implementation for Issue #2. All files listed in Section 2 are new additions (`Add` or `Add (Directory)`). No pre-existing source files are modified or deleted.

## 4. Data Structures

### 4.1 `WindowKey`

**Definition:**

```python
from typing import Literal

WindowKey = Literal["m1", "m10", "h1", "all"]
```

**Concrete Example:**

```json
"m1"
```

### 4.2 `TelltalePeakDict`

**Definition:**

```python
from typing import Optional, TypedDict

class TelltalePeakDict(TypedDict):
    """Dictionary containing current peak values for each telltale window."""
    m1: Optional[float]
    m10: Optional[float]
    h1: Optional[float]
    all: Optional[float]
```

**Concrete Example:**

```json
{
    "m1": 45.2,
    "m10": 68.7,
    "h1": 84.0,
    "all": 95.5
}
```

### 4.3 `TelltaleStyle`

**Definition:**

```python
from typing import TypedDict

class TelltaleStyle(TypedDict):
    """Visual style metadata for rendering a telltale needle."""
    color: tuple[int, int, int, int]  # RGBA color with alpha translucency
    width: float                      # Needle stroke width in pixels
    dashed: bool                      # True if style is dashed/dotted
```

**Concrete Example:**

```json
{
    "color": [0, 225, 255, 180],
    "width": 2.0,
    "dashed": false
}
```

## 5. Function Specifications

### 5.1 `Telltale.__init__()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def __init__(self, window: Optional[float] = None) -> None:
    """Initialize sliding-window peak-hold telltale."""
    ...
```

**Input Example:**

```python
window = 60.0
```

**Output Example:**

```python
# Returns initialized Telltale instance with self.window = 60.0
```

**Edge Cases:**
- `window = None`: Represents an all-time peak hold with no time expiration.

---

### 5.2 `Telltale.update()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def update(self, timestamp: float, value: float) -> None:
    """Pipe live metric sample (timestamp, value) into the telltale window."""
    ...
```

**Input Example:**

```python
timestamp = 1774972800.0
value = 75.5
```

**Output Example:**

```python
None
```

**Edge Cases:**
- Input `value` < 0.0 or > 100.0 is clamped to range [0.0, 100.0].

---

### 5.3 `Telltale.current_peak()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def current_peak(self, timestamp: Optional[float] = None) -> Optional[float]:
    """Return the peak value within the sliding window relative to timestamp."""
    ...
```

**Input Example:**

```python
timestamp = 1774972865.0
```

**Output Example:**

```python
75.5
```

**Edge Cases:**
- No samples recorded or all samples pruned -> returns `None`.

---

### 5.4 `Telltale.reset()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def reset(self) -> None:
    """Clear all sample history for this telltale."""
    ...
```

**Input Example:**

```python
# No arguments
```

**Output Example:**

```python
None
```

---

### 5.5 `TelltaleManager.__init__()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def __init__(self) -> None:
    """Instantiate four Telltale instances with 60s, 600s, 3600s, and None windows."""
    ...
```

**Input Example:**

```python
# No arguments
```

**Output Example:**

```python
# Returns TelltaleManager with initialized windows: m1(60s), m10(600s), h1(3600s), all(None)
```

---

### 5.6 `TelltaleManager.update()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def update(self, timestamp: float, value: float) -> None:
    """Pipe live metric sample (timestamp, value) into all four Telltale instances."""
    ...
```

**Input Example:**

```python
timestamp = 100.0
value = 85.0
```

**Output Example:**

```python
None
```

---

### 5.7 `TelltaleManager.get_peaks()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def get_peaks(self, timestamp: Optional[float] = None) -> TelltalePeakDict:
    """Return current peak values dict mapping window keys to peak values or None."""
    ...
```

**Input Example:**

```python
timestamp = 100.0
```

**Output Example:**

```python
{
    "m1": 85.0,
    "m10": 85.0,
    "h1": 85.0,
    "all": 85.0
}
```

---

### 5.8 `TelltaleManager.reset()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def reset(self, key: str) -> None:
    """Reset a specific window ('m1', 'm10', 'h1', 'all') or all if key='all_windows'."""
    ...
```

**Input Example:**

```python
key = "m1"
```

**Output Example:**

```python
None
```

**Edge Cases:**
- Invalid window key (e.g. `"invalid"`) -> raises `KeyError("Invalid telltale window key: invalid")`.
- Key `"all_windows"` -> resets all four windows.

---

### 5.9 `TelltaleManager.reset_all()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def reset_all(self) -> None:
    """Reset all four Telltale instances simultaneously."""
    ...
```

**Input Example:**

```python
# No arguments
```

**Output Example:**

```python
None
```

---

### 5.10 `render_telltale_needles()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
def render_telltale_needles(
    image: Image.Image,
    telltales: TelltalePeakDict,
    center: tuple[float, float],
    radius: float,
    val_to_angle_fn: Any
) -> Image.Image:
    """Render up to four telltale needles onto the PIL image surface behind main needle."""
    ...
```

**Input Example:**

```python
image = Image.new("RGBA", (256, 256), (15, 17, 23, 255))
telltales = {"m1": 40.0, "m10": 60.0, "h1": 80.0, "all": 95.0}
center = (128.0, 128.0)
radius = 90.0
val_to_angle_fn = lambda v: 225.0 - (v / 100.0) * 270.0
```

**Output Example:**

```python
# Returns updated PIL.Image.Image instance (256x256 RGBA) with translucent needles rendered
```

---

### 5.11 `render_gauge()`

**File:** `src/boostgauge/gauge.py`

**Signature:**

```python
def render_gauge(
    value: float,
    telltales: Optional[TelltalePeakDict] = None,
    size: tuple[int, int] = (256, 256),
    skin: str = "stingray"
) -> Image.Image:
    """Gauge rendering entry point handling skin dispatch, telltales layer, and main needle layer."""
    ...
```

**Input Example:**

```python
value = 50.0
telltales = {"m1": 60.0, "m10": 75.0, "h1": 85.0, "all": 98.0}
size = (256, 256)
skin = "stingray"
```

**Output Example:**

```python
# Returns PIL.Image.Image (256x256 RGBA) with complete gauge composite
```

## 6. Change Instructions

### 6.1 `src/boostgauge/telltale.py` (Add)

**Complete file contents:**

```python
"""Peak-hold telltale needle tracking and management.

Issue #2: peak-hold telltale needles — 1m, 10m, 1h, all-time (#2)
Issue #41: Telltale window tracker implementation
"""

from collections import deque
from typing import Dict, Literal, Optional, TypedDict

WindowKey = Literal["m1", "m10", "h1", "all"]


class TelltalePeakDict(TypedDict):
    """Dictionary containing current peak values for each telltale window."""
    m1: Optional[float]
    m10: Optional[float]
    h1: Optional[float]
    all: Optional[float]


class Telltale:
    """Sliding-window peak-hold tracker for system metrics."""

    def __init__(self, window: Optional[float] = None) -> None:
        """Initialize telltale with optional sliding window duration in seconds.

        Args:
            window: Window duration in seconds. None for all-time peak hold.
        """
        self.window = window
        self._samples: deque[tuple[float, float]] = deque()

    def update(self, timestamp: float, value: float) -> None:
        """Pipe live metric sample (timestamp, value) into the telltale window.

        Args:
            timestamp: Unix timestamp of the sample in seconds.
            value: Metric value in range [0.0, 100.0].
        """
        clamped_val = max(0.0, min(100.0, float(value)))
        self._samples.append((float(timestamp), clamped_val))
        self._prune(timestamp)

    def _prune(self, current_time: float) -> None:
        """Prune samples older than current_time - window."""
        if self.window is not None:
            cutoff = current_time - self.window
            while self._samples and self._samples[0][0] < cutoff:
                self._samples.popleft()

    def current_peak(self, timestamp: Optional[float] = None) -> Optional[float]:
        """Return highest metric value recorded within current window duration.

        Args:
            timestamp: Reference timestamp for window evaluation.

        Returns:
            Peak float value in [0.0, 100.0], or None if no valid samples exist.
        """
        if timestamp is not None:
            self._prune(timestamp)

        if not self._samples:
            return None

        return max(val for _, val in self._samples)

    def reset(self) -> None:
        """Clear all sample history for this telltale."""
        self._samples.clear()


class TelltaleManager:
    """Manages four sliding-window Telltale instances for system metric peaks."""

    WINDOWS: Dict[str, Optional[float]] = {
        "m1": 60.0,
        "m10": 600.0,
        "h1": 3600.0,
        "all": None,
    }

    def __init__(self) -> None:
        """Instantiate four Telltale objects with 60s, 600s, 3600s, and None windows."""
        self._telltales: Dict[str, Telltale] = {
            key: Telltale(window=win) for key, win in self.WINDOWS.items()
        }

    def update(self, timestamp: float, value: float) -> None:
        """Pipe live metric sample (timestamp, value) into all four Telltale instances.

        Args:
            timestamp: Unix timestamp in seconds.
            value: Metric value in range [0.0, 100.0].
        """
        for telltale in self._telltales.values():
            telltale.update(timestamp, value)

    def get_peaks(self, timestamp: Optional[float] = None) -> TelltalePeakDict:
        """Return current peak values dict mapping window keys to peak values or None.

        Args:
            timestamp: Reference timestamp for window pruning evaluation.

        Returns:
            TelltalePeakDict mapping 'm1', 'm10', 'h1', 'all' to peak values or None.
        """
        return {
            "m1": self._telltales["m1"].current_peak(timestamp),
            "m10": self._telltales["m10"].current_peak(timestamp),
            "h1": self._telltales["h1"].current_peak(timestamp),
            "all": self._telltales["all"].current_peak(timestamp),
        }

    def reset(self, key: str) -> None:
        """Reset a specific window ('m1', 'm10', 'h1', 'all') or all if key='all_windows'.

        Args:
            key: Window identifier ('m1', 'm10', 'h1', 'all', 'all_windows').
        """
        if key == "all_windows":
            self.reset_all()
        elif key in self._telltales:
            self._telltales[key].reset()
        else:
            raise KeyError(f"Invalid telltale window key: {key}")

    def reset_all(self) -> None:
        """Reset all four Telltale instances simultaneously."""
        for telltale in self._telltales.values():
            telltale.reset()
```

---

### 6.2 `src/boostgauge/skins/stingray.py` (Add)

**Complete file contents:**

```python
"""Stingray tachometer skin renderer with telltale needles support.

Issue #2: peak-hold telltale needles — 1m, 10m, 1h, all-time (#2)
"""

import math
from typing import Any, Dict, Optional, Tuple, TypedDict
from PIL import Image, ImageDraw

from boostgauge.telltale import TelltalePeakDict


class TelltaleStyle(TypedDict):
    """Visual style metadata for rendering a telltale needle."""
    color: tuple[int, int, int, int]
    width: float
    dashed: bool


# Distinct visual styles for 4 telltale windows per REQ-3
TELLTALE_STYLES: Dict[str, TelltaleStyle] = {
    "m1": {"color": (0, 225, 255, 180), "width": 2.0, "dashed": False},      # Translucent cyan
    "m10": {"color": (255, 140, 0, 200), "width": 2.0, "dashed": False},    # Translucent orange
    "h1": {"color": (220, 0, 220, 200), "width": 2.0, "dashed": True},      # Translucent magenta dashed
    "all": {"color": (255, 30, 30, 230), "width": 2.5, "dashed": False},    # Solid red
}


def val_to_angle(val: float) -> float:
    """Map metric value in [0.0, 100.0] to gauge dial angle in degrees.

    0.0 maps to 225.0 degrees (bottom-left).
    100.0 maps to -45.0 degrees / 315.0 degrees (bottom-right).
    Sweep angle is 270 degrees clockwise.
    """
    clamped = max(0.0, min(100.0, float(val)))
    return 225.0 - (clamped / 100.0) * 270.0


def angle_to_vector(center: Tuple[float, float], radius: float, angle_deg: float) -> Tuple[float, float]:
    """Calculate 2D Cartesian point coordinates from center pivot, radius, and angle in degrees."""
    cx, cy = center
    rad = math.radians(angle_deg)
    x = cx + radius * math.cos(rad)
    y = cy - radius * math.sin(rad)
    return (x, y)


def render_telltale_needles(
    image: Image.Image,
    telltales: TelltalePeakDict,
    center: Tuple[float, float],
    radius: float,
    val_to_angle_fn: Any = val_to_angle,
) -> Image.Image:
    """Render up to four telltale needles onto PIL image surface behind main needle.

    Renders translucent cyan (1m), orange (10m), magenta dashed (1h), and solid red (all-time).
    Suppresses any needle whose current_peak is None.
    """
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    cx, cy = center

    # Render telltales in order: all, h1, m10, m1 (so m1 cyan renders top of telltale stack)
    window_keys = ["all", "h1", "m10", "m1"]

    for key in window_keys:
        peak_val = telltales.get(key)
        if peak_val is None:
            continue

        style = TELLTALE_STYLES[key]
        angle = val_to_angle_fn(peak_val)
        tx, ty = angle_to_vector(center, radius, angle)

        if style["dashed"]:
            # Draw dashed line using 5 segment points
            num_segments = 6
            for i in range(0, num_segments, 2):
                t0 = i / num_segments
                t1 = (i + 1) / num_segments
                x0 = cx + t0 * (tx - cx)
                y0 = cy + t0 * (ty - cy)
                x1 = cx + t1 * (tx - cx)
                y1 = cy + t1 * (ty - cy)
                draw.line([(x0, y0), (x1, y1)], fill=style["color"], width=int(style["width"]))
        else:
            draw.line([(cx, cy), (tx, ty)], fill=style["color"], width=int(style["width"]))

    return Image.alpha_composite(image, overlay)


def render_stingray_skin(
    value: float,
    telltales: Optional[TelltalePeakDict] = None,
    size: Tuple[int, int] = (256, 256),
) -> Image.Image:
    """Render complete Stingray skin gauge image (background, telltales layer, main needle layer)."""
    w, h = size
    center = (w / 2.0, h / 2.0)
    radius = min(w, h) * 0.38

    # 1. Base dial background (dark charcoal)
    image = Image.new("RGBA", size, (15, 17, 23, 255))
    draw = ImageDraw.Draw(image)

    # Dial outer ring
    draw.ellipse(
        [center[0] - radius - 8, center[1] - radius - 8, center[0] + radius + 8, center[1] + radius + 8],
        outline=(45, 52, 64, 255),
        width=3,
    )

    # Tick marks (0 to 100 in steps of 10)
    for v in range(0, 101, 10):
        ang = val_to_angle(v)
        p1 = angle_to_vector(center, radius - 4, ang)
        p2 = angle_to_vector(center, radius + 4, ang)
        color = (235, 238, 245, 255) if v % 20 == 0 else (120, 130, 145, 255)
        draw.line([p1, p2], fill=color, width=2 if v % 20 == 0 else 1)

    # 2. Telltale layer (z-order 1)
    if telltales is not None:
        image = render_telltale_needles(image, telltales, center, radius, val_to_angle)

    # 3. Main dynamic needle layer (z-order 2 - ON TOP of telltales)
    needle_overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    needle_draw = ImageDraw.Draw(needle_overlay)

    main_angle = val_to_angle(value)
    nx, ny = angle_to_vector(center, radius + 2, main_angle)
    needle_draw.line([center, (nx, ny)], fill=(255, 255, 255, 255), width=3)

    # Center pivot cap
    cp_r = 6.0
    needle_draw.ellipse(
        [center[0] - cp_r, center[1] - cp_r, center[0] + cp_r, center[1] + cp_r],
        fill=(220, 40, 40, 255),
        outline=(255, 255, 255, 255),
        width=1,
    )

    return Image.alpha_composite(image, needle_overlay)
```

---

### 6.3 `src/boostgauge/gauge.py` (Add)

**Complete file contents:**

```python
"""Tachometer gauge composite renderer entry point.

Issue #2: peak-hold telltale needles — 1m, 10m, 1h, all-time (#2)
"""

from typing import Optional, Tuple
from PIL import Image

from boostgauge.skins.stingray import render_stingray_skin
from boostgauge.telltale import TelltalePeakDict


def render_gauge(
    value: float,
    telltales: Optional[TelltalePeakDict] = None,
    size: Tuple[int, int] = (256, 256),
    skin: str = "stingray",
) -> Image.Image:
    """Composite gauge renderer handling skin dispatch, main needle drawing, and telltale needle layer.

    Args:
        value: Current dynamic metric value in [0.0, 100.0].
        telltales: Optional dict of peak values for 'm1', 'm10', 'h1', 'all'.
        size: Width and height tuple in pixels (default 256x256).
        skin: Tachometer skin name (default 'stingray').

    Returns:
        PIL.Image.Image object containing rendered gauge frame.
    """
    if skin == "stingray":
        return render_stingray_skin(value=value, telltales=telltales, size=size)
    else:
        raise ValueError(f"Unknown gauge skin: {skin}")
```

---

### 6.4 `tests/unit/test_telltale.py` (Add)

**Complete file contents:**

```python
"""Unit tests for Telltale and TelltaleManager.

Issue #2: peak-hold telltale needles — 1m, 10m, 1h, all-time (#2)
"""

import pytest
from boostgauge.telltale import Telltale, TelltaleManager


def test_t010_manager_initialization():
    """T010: Verify TelltaleManager instantiates 4 window telltales (60s, 600s, 3600s, None)."""
    mgr = TelltaleManager()
    peaks = mgr.get_peaks()
    assert peaks == {"m1": None, "m10": None, "h1": None, "all": None}
    assert mgr._telltales["m1"].window == 60.0
    assert mgr._telltales["m10"].window == 600.0
    assert mgr._telltales["h1"].window == 3600.0
    assert mgr._telltales["all"].window is None


def test_t020_metric_stream_update_distribution():
    """T020: Verify update() forwards metric sample to all 4 telltales simultaneously."""
    mgr = TelltaleManager()
    mgr.update(timestamp=100.0, value=75.0)
    peaks = mgr.get_peaks(timestamp=100.0)
    assert peaks == {"m1": 75.0, "m10": 75.0, "h1": 75.0, "all": 75.0}


def test_t060_window_reset_execution():
    """T060: Verify individual window resets and reset_all() clear peak state."""
    mgr = TelltaleManager()
    mgr.update(timestamp=100.0, value=90.0)
    
    # Reset single window 'm1'
    mgr.reset("m1")
    peaks = mgr.get_peaks(timestamp=100.0)
    assert peaks["m1"] is None
    assert peaks["m10"] == 90.0
    assert peaks["h1"] == 90.0
    assert peaks["all"] == 90.0

    # Reset all windows
    mgr.reset_all()
    peaks_after = mgr.get_peaks(timestamp=100.0)
    assert peaks_after == {"m1": None, "m10": None, "h1": None, "all": None}

    # Verify invalid key raises KeyError
    with pytest.raises(KeyError):
        mgr.reset("invalid_key")


def test_t070_1m_sliding_window_eviction():
    """T070: Verify 1m peak drops back to highest remaining sample after 60s."""
    mgr = TelltaleManager()
    mgr.update(timestamp=100.0, value=95.0)
    mgr.update(timestamp=120.0, value=50.0)

    # At t=150s (within 60s of t=100s), peak remains 95.0
    assert mgr.get_peaks(timestamp=150.0)["m1"] == 95.0

    # At t=165s (sample at t=100s has aged past 60s), peak drops to 50.0
    assert mgr.get_peaks(timestamp=165.0)["m1"] == 50.0
    # 10m window still holds 95.0
    assert mgr.get_peaks(timestamp=165.0)["m10"] == 95.0


def test_t080_all_time_peak_retention():
    """T080: Verify all-time peak persists indefinitely regardless of elapsed time."""
    mgr = TelltaleManager()
    mgr.update(timestamp=100.0, value=98.0)
    mgr.update(timestamp=4000.0, value=20.0)

    peaks = mgr.get_peaks(timestamp=4000.0)
    assert peaks["m1"] == 20.0
    assert peaks["m10"] == 20.0
    assert peaks["h1"] == 20.0
    assert peaks["all"] == 98.0
```

---

### 6.5 `tests/visual/test_gauge.py` (Add)

**Complete file contents:**

```python
"""Visual regression and property tests for PIL gauge renderer.

Issue #2: peak-hold telltale needles — 1m, 10m, 1h, all-time (#2)
Follows docs/design/0001-test-strategy.md Option C (off-screen PIL image rendering).
"""

import math
from pathlib import Path
import pytest
from PIL import Image, ImageChops, ImageStat

from boostgauge.gauge import render_gauge
from boostgauge.skins.stingray import TELLTALE_STYLES, val_to_angle


# ---------------------------------------------------------------------------
# Section 6.5.1: Baseline-Independent Property Assertions (Issue #1902)
# ---------------------------------------------------------------------------

def test_t030_visual_needle_rendering_baseline_independent():
    """T030 (Baseline-Independent): Assert needle pixel tip coordinates mathematically."""
    telltales = {"m1": 50.0, "m10": None, "h1": None, "all": None}
    img = render_gauge(value=0.0, telltales=telltales, size=(256, 256))
    
    # For value 50.0, angle is 225 - (50/100)*270 = 90.0 degrees (straight up).
    # Pivot center = (128, 128), radius = 256 * 0.38 = 97.28.
    # Needle tip coordinates = (128 + 97.28 * cos(90 deg), 128 - 97.28 * sin(90 deg)) = (128, 30.72)
    # The m1 telltale cyan color is (0, 225, 255, 180).
    # Check pixel along the needle line at (128, 50) on the rendered image surface.
    r, g, b, a = img.getpixel((128, 50))
    # Assert cyan component is non-zero and dominant over red background
    assert g > 100, f"Expected cyan green channel > 100 at needle coordinate, got {g}"
    assert b > 100, f"Expected cyan blue channel > 100 at needle coordinate, got {b}"


def test_t040_main_needle_z_order_baseline_independent():
    """T040 (Baseline-Independent): Verify main dynamic needle renders ON TOP of telltale needle."""
    # Place telltale at 50.0 and main needle overlapping at 50.0
    telltales = {"m1": 50.0, "m10": None, "h1": None, "all": None}
    img = render_gauge(value=50.0, telltales=telltales, size=(256, 256))

    # Main needle color is pure white (255, 255, 255, 255).
    # Telltale m1 color is translucent cyan (0, 225, 255, 180).
    # At needle overlap coordinate (128, 50), main white needle must dominate color channels.
    r, g, b, a = img.getpixel((128, 50))
    assert r > 200, f"Expected main needle white red channel > 200 at overlap, got {r}"
    assert g > 200, f"Expected main needle white green channel > 200 at overlap, got {g}"
    assert b > 200, f"Expected main needle white blue channel > 200 at overlap, got {b}"


def test_t050_missing_peak_needle_suppression_baseline_independent():
    """T050 (Baseline-Independent): Verify omitted/reset telltales render background pixel."""
    # Telltales dict with all None (post-reset state)
    telltales_none = {"m1": None, "m10": None, "h1": None, "all": None}
    img = render_gauge(value=0.0, telltales=telltales_none, size=(256, 256))

    # At (128, 50), only dial background (dark charcoal ~15, 17, 23) should be present
    r, g, b, a = img.getpixel((128, 50))
    assert r < 40 and g < 40 and b < 40, f"Expected dark background at (128, 50), got ({r}, {g}, {b})"


# ---------------------------------------------------------------------------
# Section 6.5.2: Image Baseline Visual Regression Assertions
# ---------------------------------------------------------------------------

def _compare_or_generate_baseline(img: Image.Image, test_id: str, request: pytest.FixtureRequest) -> None:
    """Helper to compare rendered PIL Image with baseline PNG file or generate it."""
    baseline_dir = Path("tests/visual/baselines")
    baseline_dir.mkdir(parents=True, exist_ok=True)
    baseline_file = baseline_dir / f"{test_id}.png"

    if request.config.getoption("--generate-baselines", default=False):
        img.save(baseline_file)
        return

    if not baseline_file.exists():
        pytest.fail(
            f"Baseline file {baseline_file} does not exist. "
            f"Run pytest with --generate-baselines to create visual baseline images."
        )

    expected = Image.open(baseline_file).convert("RGBA")
    assert img.size == expected.size, f"Image dimensions mismatch: {img.size} != {expected.size}"

    diff = ImageChops.difference(img, expected)
    stat = ImageStat.Stat(diff)
    rms = math.sqrt(sum(stat.sum2) / (img.size[0] * img.size[1] * 4))

    # Tolerance: RMS <= 1.0 / 255 per docs/design/0001-test-strategy.md
    assert rms <= (1.0 / 255.0), f"Visual regression failure for {test_id}: RMS diff {rms:.6f} > 1.0/255"


def test_t030_visual_needle_rendering_baseline(request):
    """T030: Visual regression test for 4 distinct telltale needle rendering."""
    telltales = {"m1": 30.0, "m10": 55.0, "h1": 75.0, "all": 90.0}
    img = render_gauge(value=20.0, telltales=telltales, size=(256, 256))
    _compare_or_generate_baseline(img, "test_t030_visual_needle_rendering", request)


def test_t040_main_needle_z_order_baseline(request):
    """T040: Visual regression test for main needle z-order overlay."""
    telltales = {"m1": 50.0, "m10": 50.0, "h1": 50.0, "all": 50.0}
    img = render_gauge(value=50.0, telltales=telltales, size=(256, 256))
    _compare_or_generate_baseline(img, "test_t040_main_needle_z_order", request)


def test_t050_missing_peak_needle_suppression_baseline(request):
    """T050: Visual regression test for post-reset needle suppression."""
    telltales = {"m1": None, "m10": 60.0, "h1": None, "all": 90.0}
    img = render_gauge(value=30.0, telltales=telltales, size=(256, 256))
    _compare_or_generate_baseline(img, "test_t050_missing_peak_needle_suppression", request)
```

## 7. Pattern References

### 7.1 Off-Screen PIL Renderer Architecture

**File:** `docs/design/0001-test-strategy.md` (lines 35-50)

```markdown
Chosen: Option C — render to off-screen PIL.Image first; tkinter Canvas is a display surface only.
The gauge renderer is a pure function: state -> PIL.Image.
The tkinter Canvas receives that image and displays it. Tests exercise the renderer; they never instantiate tkinter.Tk().
```

**Relevance:** Establishes Option C requirement: `render_gauge()` returns `PIL.Image.Image` directly without referencing `tkinter`, permitting 100% headless CI visual regression testing.

---

### 7.2 Visual Baseline Comparison Protocol

**File:** `docs/design/0001-test-strategy.md` (lines 66-73)

```markdown
- Byte-different but pixel-RMS <= 1.0 / 255 -> pass with a warning (anti-aliasing noise; harmless).
- Pixel-RMS > 1.0 / 255 -> fail. Diff image written to tests/visual/diffs/{test_id}.png for triage.
Implementation: PIL.ImageChops.difference() + ImageStat.Stat(diff).rms.
```

**Relevance:** Enforces exact RMS tolerance calculation (`RMS <= 1.0 / 255`) and `--generate-baselines` workflow flag for visual regression testing.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `from typing import Dict, Literal, Optional, Tuple, TypedDict, Any` | stdlib | `telltale.py`, `skins/stingray.py`, `gauge.py` |
| `from collections import deque` | stdlib | `telltale.py` |
| `import math` | stdlib | `skins/stingray.py`, `test_gauge.py` |
| `from pathlib import Path` | stdlib | `test_gauge.py` |
| `from PIL import Image, ImageDraw, ImageChops, ImageStat` | pillow (>=12.2.0) | `skins/stingray.py`, `gauge.py`, `test_gauge.py` |
| `import pytest` | pytest | `test_telltale.py`, `test_gauge.py` |

**New Dependencies:** None (uses existing Pillow and stdlib dependencies declared in `pyproject.toml`).

## 9. Placeholder

*Reserved for future use to maintain alignment with LLD section numbering.*

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `TelltaleManager.__init__()` | Constructor call | 4 telltales created with windows (60s, 600s, 3600s, None) returning `None` peak |
| T020 | `TelltaleManager.update()` | `timestamp=100.0, value=75.0` | `get_peaks()` returns `{"m1": 75.0, "m10": 75.0, "h1": 75.0, "all": 75.0}` |
| T030 | `render_telltale_needles()` & `render_gauge()` | `telltales={"m1": 30.0, "m10": 55.0, "h1": 75.0, "all": 90.0}` | Baseline-independent pixel check passes and visual baseline RMS <= 1.0/255 |
| T040 | `render_gauge()` | `value=50.0`, telltale at `50.0` | White main needle pixel color dominates over translucent cyan at overlap point |
| T050 | `render_gauge()` | `telltales={"m1": None, ...}` | Needles with `None` peak omitted; background pixel rendered at coordinates |
| T060 | `TelltaleManager.reset()` & `reset_all()` | `reset("m1")` then `reset_all()` | Target peak reset to `None`, invalid key raises `KeyError` |
| T070 | `Telltale.current_peak()` | Sample 95 at t=100s, sample 50 at t=120s | `m1` peak returns 50.0 after 60s (t=165s), `m10` still holds 95.0 |
| T080 | `Telltale.current_peak()` | Sample 98 at t=100s, sample 20 at t=4000s | `all` peak remains 98.0 after 3900s |

## 11. Implementation Notes

### 11.1 Error Handling Convention

- Input metric values passed to `Telltale.update()` are clamped to `[0.0, 100.0]` range to prevent geometry overflow or invalid angle calculations.
- Passing an unrecognized window key to `TelltaleManager.reset(key)` raises `KeyError(f"Invalid telltale window key: {key}")`.
- Passing an unrecognized skin name to `render_gauge()` raises `ValueError(f"Unknown gauge skin: {skin}")`.

### 11.2 Platform Independence Rule (Issue #1841)

All test paths in `tests/visual/test_gauge.py` use `pathlib.Path` objects (`Path("tests/visual/baselines") / f"{test_id}.png"`) rather than separator-laden string concatenations to ensure platform-independent execution on Windows and POSIX systems.

### 11.3 Baseline-Independent Visual Assertions (Issue #1902)

`tests/visual/test_gauge.py` includes baseline-independent property assertions in Section 6.5.1 that compute needle tip coordinate geometry trigonometrically and check raw RGB/RGBA pixel channel values without reading baseline PNG files.

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3 - greenfield status noted)
- [x] Every data structure has a concrete JSON/YAML example (Section 4)
- [x] Every function has input/output examples with realistic values (Section 5)
- [x] Change instructions are diff-level specific with complete file listings (Section 6)
- [x] Pattern references include file:line locations and are verified to exist (Section 7)
- [x] All imports are listed and verified (Section 8)
- [x] Test mapping covers all LLD test scenarios T010-T080 (Section 10)

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #2 |
| Verdict | APPROVED |
| Date | 2026-07-31 |
| Iterations | 1 |
| Finalized | 2026-07-31T16:28:00Z |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #2 |
| Verdict | APPROVED |
| Date | 2026-07-31 |
| Iterations | 1 |
| Finalized | 2026-07-31T21:29:16Z |

### Review Feedback Summary

The Implementation Spec is approved. The revision correctly disambiguates the window key 'all' (for resetting the all-time peak window) from 'all_windows' (for resetting all 4 windows via reset_all()). All 8 requirements in Section 3 map cleanly to explicit unit tests in Section 6.4 and visual regression/baseline-independent property tests in Section 6.5. Every assertion in the test code is traceable to specified requirements and behavior, and the spec includes baseline-independent visual proper...
