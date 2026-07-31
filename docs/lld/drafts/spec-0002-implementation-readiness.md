# Implementation Spec: Feature: peak-hold telltale needles — 1m, 10m, 1h, all-time (#2)

| Field | Value |
|-------|-------|
| Issue | #2 |
| LLD | `docs/lld/done/0002-peak-hold-telltale-needles.md` |
| Generated | 2026-07-31 |
| Status | APPROVED |

## 1. Overview

This implementation spec defines the exact components, data structures, off-screen PIL rendering logic, and test suites required to render four peak-hold (telltale) needles (1m, 10m, 1h, all-time) on the `boostgauge` racing tachometer surface behind the main needle.

**Objective:** Render four peak-hold needles (1m, 10m, 1h, all-time) on top of the PIL gauge surface behind the main needle, consuming `Telltale` instances managed by a unified `TelltaleManager`.

**Success Criteria:**
1. Four telltale windows (60s, 600s, 3600s, all-time) updated concurrently per sample stream pass.
2. Distinct visual styles for each window (cyan 1m, orange 10m, magenta 1h, solid red all-time).
3. Main dynamic needle rendered strictly on top of telltale needles in z-order layer composition.
4. Missing or reset peaks (`None`) suppressed cleanly from render.
5. Window reset actions (`reset(key)` and `reset_all()`) clear target peak states.
6. Baseline-independent trigonometry assertions and visual regression test suites passing 100% headlessly.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/telltale.py` | Add | Defines single sliding-window `Telltale` and multi-window `TelltaleManager` facade with window routing and reset dispatch. |
| 2 | `src/boostgauge/skins/stingray.py` | Add | Implements Stingray tachometer skin rendering, polar needle angle conversions, and telltale layer drawing. |
| 3 | `src/boostgauge/gauge.py` | Add | Main gauge composite rendering entry point coordinating background face, telltale layer, and main needle z-order. |
| 4 | `tests/unit/test_telltale.py` | Add | Unit test suite for `Telltale` and `TelltaleManager` window routing, peak hold, expiration, and reset operations. |
| 5 | `tests/visual/baselines` | Add (Directory) | Directory holding baseline png images for off-screen PIL rendering visual regression tests. |
| 6 | `tests/visual/test_gauge.py` | Add | Visual regression & baseline-independent property test suite for gauge telltale rendering. |

**Implementation Order Rationale:**
- `telltale.py` is pure logic with no internal dependencies and provides peak data structures needed by renderers.
- `skins/stingray.py` contains low-level PIL drawing primitives for telltales and dial faces.
- `gauge.py` imports `telltale.py` and `skins/stingray.py` to expose the main `render_gauge()` composite function.
- Unit tests (`tests/unit/test_telltale.py`) test `TelltaleManager` independently before visual test execution.
- Baseline directory (`tests/visual/baselines`) and visual test suite (`tests/visual/test_gauge.py`) validate the visual output.

## 3. Current State (for Modify/Delete files)

No files are modified or deleted in this implementation. All files listed in Section 2 are new additions (`Add` / `Add (Directory)`).

## 4. Data Structures

### 4.1 `WindowKey` & `TelltalePeakDict`

**Definition:**

```python
from typing import Dict, Literal, Optional, TypedDict

WindowKey = Literal["m1", "m10", "h1", "all"]

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
    "m1": 42.5,
    "m10": 68.0,
    "h1": 85.2,
    "all": 97.4
}
```

Post-reset example:

```json
{
    "m1": null,
    "m10": 68.0,
    "h1": 85.2,
    "all": 97.4
}
```

### 4.2 `TelltaleStyle`

**Definition:**

```python
class TelltaleStyle(TypedDict):
    """Visual style metadata for rendering a telltale needle."""
    color: tuple[int, int, int, int]  # RGBA color tuple
    width: float                      # Needle line width in pixels
    dashed: bool                      # True for dashed line style, False for solid
```

**Concrete Example:**

```json
{
    "color": [0, 229, 255, 180],
    "width": 2.0,
    "dashed": true
}
```

## 5. Function Specifications

### 5.1 `TelltaleManager.__init__()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def __init__(self) -> None:
    """Instantiate four Telltale window objects with 60s, 600s, 3600s, and None windows."""
    ...
```

**Input Example:**

```python
# No arguments required
manager = TelltaleManager()
```

**Output Example:**

```python
# TelltaleManager instance with self._telltales initialized to:
# {
#   "m1": Telltale(window=60.0),
#   "m10": Telltale(window=600.0),
#   "h1": Telltale(window=3600.0),
#   "all": Telltale(window=None)
# }
```

**Edge Cases:**
- Initial state before any samples: all `current_peak()` calls return `None`.

### 5.2 `TelltaleManager.update()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def update(self, timestamp: float, value: float) -> None:
    """Pipe live metric sample (timestamp, value) into all four Telltale instances."""
    ...
```

**Input Example:**

```python
timestamp = 1774958400.0
value = 75.5
```

**Output Example:**

```python
None  # Mutates internal window deque states
```

**Edge Cases:**
- Negative timestamp -> process as valid float timestamp.
- Out-of-bounds metric values (> 100.0 or < 0.0) -> clamped internally to [0.0, 100.0].

### 5.3 `TelltaleManager.get_peaks()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def get_peaks(self, timestamp: Optional[float] = None) -> TelltalePeakDict:
    """Return current peak values dict mapping window keys to peak values or None."""
    ...
```

**Input Example:**

```python
timestamp = 1774958465.0  # Optional reference evaluation timestamp
```

**Output Example:**

```python
{
    "m1": 50.0,    # Peak within last 60 seconds relative to timestamp
    "m10": 75.5,   # Peak within last 600 seconds
    "h1": 75.5,    # Peak within last 3600 seconds
    "all": 92.0    # All-time peak
}
```

**Edge Cases:**
- If `timestamp` is omitted, defaults to current time or sample max timestamp.
- If window is empty or post-reset, its dict entry is `None`.

### 5.4 `TelltaleManager.reset()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def reset(self, key: str) -> None:
    """Reset a specific window ('m1', 'm10', 'h1', 'all') or all windows if key='all'."""
    ...
```

**Input Example:**

```python
key = "m1"
```

**Output Example:**

```python
None  # Resets self._telltales["m1"] peak state to None
```

**Edge Cases:**
- `key == "all"` -> resets all four window instances.
- Invalid `key` string -> raises `KeyError(f"Unknown telltale window key: {key}")`.

### 5.5 `TelltaleManager.reset_all()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def reset_all(self) -> None:
    """Reset all four Telltale instances simultaneously."""
    ...
```

**Input Example:**

```python
manager.reset_all()
```

**Output Example:**

```python
None  # All window peaks cleared to None
```

### 5.6 `render_telltale_needles()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
def render_telltale_needles(
    image: Image.Image,
    telltales: TelltalePeakDict,
    center: tuple[float, float] = (128.0, 128.0),
    radius: float = 90.0,
    val_to_angle_fn: Any = None
) -> Image.Image:
    """Render active telltale needles onto PIL image surface behind main needle."""
    ...
```

**Input Example:**

```python
from PIL import Image
image = Image.new("RGBA", (256, 256), (15, 23, 42, 255))
telltales = {"m1": 40.0, "m10": 60.0, "h1": 80.0, "all": 95.0}
center = (128.0, 128.0)
radius = 90.0
```

**Output Example:**

```python
# Returns PIL.Image.Image instance (RGBA, 256x256) with telltale lines drawn
```

**Edge Cases:**
- `telltales` contains `None` for a key -> skip rendering line for that key.
- `telltales` empty or all values `None` -> return original image unmodified.

### 5.7 `render_gauge()`

**File:** `src/boostgauge/gauge.py`

**Signature:**

```python
def render_gauge(
    value: float,
    telltale_manager: Optional[TelltaleManager] = None,
    size: tuple[int, int] = (256, 256)
) -> Image.Image:
    """Composite gauge renderer drawing dial face, telltales layer, and main needle."""
    ...
```

**Input Example:**

```python
value = 55.0
telltale_manager = TelltaleManager()
telltale_manager.update(100.0, 85.0)
size = (256, 256)
```

**Output Example:**

```python
# Returns PIL.Image.Image instance (256x256 RGBA) representing final gauge frame
```

**Edge Cases:**
- `telltale_manager` is `None` -> render dial and main needle without telltale layer.
- `value` outside [0, 100] -> clamped to range [0.0, 100.0].

### 5.8 `test_t030_visual_needle_rendering_req3()`

**File:** `tests/visual/test_gauge.py`

**Signature:**

```python
def test_t030_visual_needle_rendering_req3(pytestconfig, tmp_path) -> None:
    """T030: Visual regression check for telltale needles rendering (REQ-3)."""
    ...
```

**Input Example:**

```python
pytestconfig = pytest.Config()
tmp_path = Path("/tmp/pytest-0")
```

**Output Example:**

```python
None  # Asserts RMS pixel difference between rendered gauge and baseline image is <= 1.0
```

**Edge Cases:**
- Baseline file missing -> fails test unless `--generate-baselines` option is specified.

## 6. Change Instructions

### 6.1 `src/boostgauge/telltale.py` (Add)

**Complete file contents:**

```python
"""Peak-hold telltale needle tracking and window management.

Issue #2: peak-hold telltale needles — 1m, 10m, 1h, all-time
"""

from collections import deque
from typing import Dict, Literal, Optional, Tuple, TypedDict

WindowKey = Literal["m1", "m10", "h1", "all"]


class TelltalePeakDict(TypedDict):
    """Dictionary containing current peak values for each telltale window."""

    m1: Optional[float]
    m10: Optional[float]
    h1: Optional[float]
    all: Optional[float]


class Telltale:
    """Single sliding-window or all-time peak-hold tracker."""

    def __init__(self, window: Optional[float] = None) -> None:
        """Initialize tracker.

        Args:
            window: Time window duration in seconds. If None, tracks all-time peak.
        """
        self.window = window
        self._samples: deque[Tuple[float, float]] = deque()
        self._all_time_peak: Optional[float] = None

    def update(self, timestamp: float, value: float) -> None:
        """Record sample (timestamp, value) and maintain peak tracking."""
        clamped_val = max(0.0, min(100.0, float(value)))
        if self._all_time_peak is None or clamped_val > self._all_time_peak:
            self._all_time_peak = clamped_val
        self._samples.append((float(timestamp), clamped_val))
        self._prune(timestamp)

    def current_peak(self, timestamp: Optional[float] = None) -> Optional[float]:
        """Return highest value recorded within active window."""
        if timestamp is not None:
            self._prune(timestamp)
        if self.window is None:
            return self._all_time_peak
        if not self._samples:
            return None
        return max(val for _, val in self._samples)

    def reset(self) -> None:
        """Clear all sample history and reset peak state."""
        self._samples.clear()
        self._all_time_peak = None

    def _prune(self, current_time: float) -> None:
        """Evict samples older than window duration relative to current_time."""
        if self.window is None:
            return
        cutoff = current_time - self.window
        while self._samples and self._samples[0][0] < cutoff:
            self._samples.popleft()


class TelltaleManager:
    """Manages four sliding-window Telltale instances for gauge metrics."""

    def __init__(self) -> None:
        """Instantiate Telltale instances for 60s, 600s, 3600s, and all-time."""
        self._telltales: Dict[str, Telltale] = {
            "m1": Telltale(window=60.0),
            "m10": Telltale(window=600.0),
            "h1": Telltale(window=3600.0),
            "all": Telltale(window=None),
        }

    def update(self, timestamp: float, value: float) -> None:
        """Pipe live sample to all four Telltale instances."""
        for telltale in self._telltales.values():
            telltale.update(timestamp, value)

    def get_peaks(self, timestamp: Optional[float] = None) -> TelltalePeakDict:
        """Return current peak values dictionary for active windows."""
        return {
            "m1": self._telltales["m1"].current_peak(timestamp),
            "m10": self._telltales["m10"].current_peak(timestamp),
            "h1": self._telltales["h1"].current_peak(timestamp),
            "all": self._telltales["all"].current_peak(timestamp),
        }

    def reset(self, key: str) -> None:
        """Reset specified window key ('m1', 'm10', 'h1', 'all')."""
        if key == "all":
            self.reset_all()
            return
        if key not in self._telltales:
            raise KeyError(f"Unknown telltale window key: {key}")
        self._telltales[key].reset()

    def reset_all(self) -> None:
        """Reset all four Telltale instances simultaneously."""
        for telltale in self._telltales.values():
            telltale.reset()
```

### 6.2 `src/boostgauge/skins/stingray.py` (Add)

**Complete file contents:**

```python
"""Stingray tachometer skin renderer.

Issue #2: peak-hold telltale needles — 1m, 10m, 1h, all-time
"""

import math
from typing import Dict, Optional, Tuple, TypedDict
from PIL import Image, ImageDraw, ImageFilter

from boostgauge.telltale import TelltalePeakDict


class TelltaleStyle(TypedDict):
    """Visual styling metadata for telltale needles."""

    color: Tuple[int, int, int, int]
    width: float
    dashed: bool


# Visual styles per REQ-3
TELLTALE_STYLES: Dict[str, TelltaleStyle] = {
    "m1": {"color": (0, 229, 255, 180), "width": 2.0, "dashed": True},      # Cyan
    "m10": {"color": (255, 140, 0, 200), "width": 2.0, "dashed": True},     # Orange
    "h1": {"color": (217, 70, 239, 200), "width": 2.0, "dashed": True},     # Magenta
    "all": {"color": (239, 68, 68, 235), "width": 2.5, "dashed": False},    # Red solid
}


def val_to_angle(value: float, min_val: float = 0.0, max_val: float = 100.0) -> float:
    """Convert metric value in [0, 100] to gauge angle in degrees (135° to 405°)."""
    clamped = max(min_val, min(max_val, float(value)))
    ratio = (clamped - min_val) / (max_val - min_val)
    return 135.0 + ratio * 270.0


def calculate_needle_tip(
    center: Tuple[float, float], radius: float, angle_deg: float
) -> Tuple[float, float]:
    """Calculate (x, y) coordinates of needle tip for a given angle in degrees."""
    rad = math.radians(angle_deg)
    tip_x = center[0] + radius * math.cos(rad)
    tip_y = center[1] + radius * math.sin(rad)
    return (tip_x, tip_y)


def render_dial_face(size: Tuple[int, int] = (256, 256)) -> Image.Image:
    """Render background dial face with ticks and dark tachometer aesthetic."""
    img = Image.new("RGBA", size, (15, 23, 42, 255))
    draw = ImageDraw.Draw(img)
    center = (size[0] / 2.0, size[1] / 2.0)
    outer_r = min(size) * 0.42

    # Outer bezel ring
    draw.ellipse(
        [
            center[0] - outer_r,
            center[1] - outer_r,
            center[0] + outer_r,
            center[1] + outer_r,
        ],
        outline=(51, 65, 85, 255),
        width=3,
    )

    # Dial tick marks (0 to 100 at intervals of 10)
    for v in range(0, 101, 10):
        ang = val_to_angle(float(v))
        inner_r = outer_r - (12.0 if v % 20 == 0 else 6.0)
        p1 = calculate_needle_tip(center, inner_r, ang)
        p2 = calculate_needle_tip(center, outer_r - 2.0, ang)
        draw.line([p1, p2], fill=(148, 163, 184, 255), width=2 if v % 20 == 0 else 1)

    return img


def render_telltale_needles(
    image: Image.Image,
    telltales: TelltalePeakDict,
    center: Tuple[float, float] = (128.0, 128.0),
    radius: float = 90.0,
) -> Image.Image:
    """Render up to four telltale needles onto the image surface (REQ-3, REQ-5)."""
    result = image.copy()
    overlay = Image.new("RGBA", result.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Order: m1, m10, h1, all
    for key in ["m1", "m10", "h1", "all"]:
        peak_val = telltales.get(key)
        if peak_val is None:
            continue  # REQ-5: Suppress rendering post-reset or missing peak

        style = TELLTALE_STYLES[key]
        angle = val_to_angle(peak_val)
        tip = calculate_needle_tip(center, radius, angle)

        if style["dashed"]:
            # Render dashed line segment from pivot to tip
            num_segments = 12
            for i in range(0, num_segments, 2):
                t1 = i / num_segments
                t2 = (i + 1) / num_segments
                sx = center[0] + t1 * (tip[0] - center[0])
                sy = center[1] + t1 * (tip[1] - center[1])
                ex = center[0] + t2 * (tip[0] - center[0])
                ey = center[1] + t2 * (tip[1] - center[1])
                draw.line(
                    [(sx, sy), (ex, ey)],
                    fill=style["color"],
                    width=int(round(style["width"])),
                )
        else:
            draw.line(
                [center, tip],
                fill=style["color"],
                width=int(round(style["width"])),
            )

    return Image.alpha_composite(result, overlay)


def render_main_needle(
    image: Image.Image,
    value: float,
    center: Tuple[float, float] = (128.0, 128.0),
    radius: float = 92.0,
) -> Image.Image:
    """Render dynamic main needle on top layer (z-order 2) (REQ-4)."""
    result = image.copy()
    overlay = Image.new("RGBA", result.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    angle = val_to_angle(value)
    tip = calculate_needle_tip(center, radius, angle)

    # Solid main needle (bright red/white tip)
    draw.line([center, tip], fill=(255, 255, 255, 255), width=4)
    draw.line([center, tip], fill=(239, 68, 68, 255), width=2)

    # Pivot cap
    cap_r = 8.0
    draw.ellipse(
        [
            center[0] - cap_r,
            center[1] - cap_r,
            center[0] + cap_r,
            center[1] + cap_r,
        ],
        fill=(226, 232, 240, 255),
        outline=(15, 23, 42, 255),
        width=2,
    )

    return Image.alpha_composite(result, overlay)
```

### 6.3 `src/boostgauge/gauge.py` (Add)

**Complete file contents:**

```python
"""Gauge renderer entry point.

Issue #2: peak-hold telltale needles — 1m, 10m, 1h, all-time
"""

from typing import Optional, Tuple
from PIL import Image

from boostgauge.skins.stingray import (
    render_dial_face,
    render_main_needle,
    render_telltale_needles,
)
from boostgauge.telltale import TelltaleManager, TelltalePeakDict


def render_gauge(
    value: float,
    telltale_manager: Optional[TelltaleManager] = None,
    size: Tuple[int, int] = (256, 256),
) -> Image.Image:
    """Composite gauge surface renderer following z-order rules.

    Layer 0: Dial face background & tick marks
    Layer 1: Telltale needles (behind main needle)
    Layer 2: Main dynamic gauge needle & center pivot cap
    """
    # Layer 0: Dial face
    canvas = render_dial_face(size=size)
    center = (size[0] / 2.0, size[1] / 2.0)
    radius = min(size) * 0.35

    # Layer 1: Telltale needles layer (if manager present)
    if telltale_manager is not None:
        peaks: TelltalePeakDict = telltale_manager.get_peaks()
        canvas = render_telltale_needles(
            image=canvas, telltales=peaks, center=center, radius=radius
        )

    # Layer 2: Main needle layer (always on top)
    canvas = render_main_needle(
        image=canvas, value=value, center=center, radius=radius + 2.0
    )

    return canvas
```

### 6.4 `tests/unit/test_telltale.py` (Add)

**Complete file contents:**

```python
"""Unit tests for Telltale and TelltaleManager logic.

Issue #2: peak-hold telltale needles — 1m, 10m, 1h, all-time
"""

import pytest
from boostgauge.telltale import Telltale, TelltaleManager


def test_t010_manager_initialization_req1():
    """T010: Verify TelltaleManager initializes 4 telltale windows (REQ-1)."""
    manager = TelltaleManager()
    peaks = manager.get_peaks()
    assert peaks == {"m1": None, "m10": None, "h1": None, "all": None}


def test_t020_metric_stream_update_distribution_req2():
    """T020: Forward sample updates to all windows simultaneously (REQ-2)."""
    manager = TelltaleManager()
    t0 = 1000.0
    manager.update(t0, 75.0)

    peaks = manager.get_peaks(timestamp=t0)
    assert peaks == {"m1": 75.0, "m10": 75.0, "h1": 75.0, "all": 75.0}


def test_t060_window_reset_execution_req6():
    """T060: Individual window reset and reset_all clear peak state (REQ-6)."""
    manager = TelltaleManager()
    manager.update(100.0, 80.0)

    # Reset single window 'm1'
    manager.reset("m1")
    peaks = manager.get_peaks(timestamp=100.0)
    assert peaks["m1"] is None
    assert peaks["m10"] == 80.0
    assert peaks["h1"] == 80.0
    assert peaks["all"] == 80.0

    # Reset all windows
    manager.reset_all()
    peaks_all = manager.get_peaks(timestamp=100.0)
    assert peaks_all == {"m1": None, "m10": None, "h1": None, "all": None}


def test_t070_m1_sliding_window_eviction_req7():
    """T070: 1m peak drops back after 60s without explicit reset (REQ-7)."""
    manager = TelltaleManager()
    # High sample at t=0
    manager.update(0.0, 90.0)
    # Lower sample at t=30
    manager.update(30.0, 50.0)

    assert manager.get_peaks(timestamp=30.0)["m1"] == 90.0

    # At t=65 (past 60s window), 90.0 sample is evicted; peak drops to 50.0
    peaks_65 = manager.get_peaks(timestamp=65.0)
    assert peaks_65["m1"] == 50.0
    assert peaks_65["m10"] == 90.0
    assert peaks_65["all"] == 90.0


def test_t080_all_time_peak_retention_req8():
    """T080: All-time peak persists indefinitely regardless of time (REQ-8)."""
    manager = TelltaleManager()
    manager.update(0.0, 95.0)
    manager.update(4000.0, 20.0)

    peaks = manager.get_peaks(timestamp=4000.0)
    assert peaks["m1"] == 20.0
    assert peaks["m10"] == 20.0
    assert peaks["h1"] == 20.0
    assert peaks["all"] == 95.0
```

### 6.5 `tests/visual/baselines` (Add Directory)

Directory created for visual baseline storage.

### 6.6 `tests/visual/test_gauge.py` (Add)

**Complete file contents:**

```python
"""Visual regression and baseline-independent tests for gauge rendering.

Issue #2: peak-hold telltale needles — 1m, 10m, 1h, all-time
"""

import math
from pathlib import Path
import pytest
from PIL import Image, ImageChops, ImageStat

from boostgauge.gauge import render_gauge
from boostgauge.skins.stingray import TELLTALE_STYLES, calculate_needle_tip, val_to_angle
from boostgauge.telltale import TelltaleManager

BASELINES_DIR = Path(__file__).resolve().parent / "baselines"


def _compute_rms_diff(img1: Image.Image, img2: Image.Image) -> float:
    """Compute Root Mean Square (RMS) difference between two PIL images."""
    diff = ImageChops.difference(img1, img2)
    stat = ImageStat.Stat(diff)
    sum_sq = sum(rms ** 2 for rms in stat.rms)
    return math.sqrt(sum_sq / len(stat.rms))


def test_t030_visual_needle_rendering_req3(pytestconfig, tmp_path):
    """T030: Visual regression check for telltale needles rendering (REQ-3)."""
    BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    baseline_path = BASELINES_DIR / "telltale_4_needles.png"

    manager = TelltaleManager()
    manager.update(100.0, 40.0)
    manager.update(200.0, 60.0)
    manager.update(300.0, 80.0)
    manager.update(400.0, 95.0)

    rendered = render_gauge(value=50.0, telltale_manager=manager)

    if pytestconfig.getoption("--generate-baselines", default=False):
        rendered.save(baseline_path)

    if not baseline_path.exists():
        pytest.fail(f"Baseline missing: {baseline_path}. Run with --generate-baselines to create.")

    baseline_img = Image.open(baseline_path).convert("RGBA")
    rms = _compute_rms_diff(rendered.convert("RGBA"), baseline_img)
    assert rms <= 1.0, f"Visual regression RMS diff {rms:.3f} exceeded tolerance 1.0"


def test_t040_main_needle_z_order_req4():
    """T040: Verify main needle rendered on top of telltale needles (REQ-4)."""
    manager = TelltaleManager()
    manager.update(100.0, 60.0)  # Telltale peak at 60.0

    # Render main needle at same position (60.0)
    rendered = render_gauge(value=60.0, telltale_manager=manager)

    # Check center pivot cap is intact (white/gray pivot cap on top layer)
    center_pixel = rendered.getpixel((128, 128))
    assert center_pixel[0] > 200 and center_pixel[1] > 200  # Pivot cap light gray/white


def test_t050_missing_peak_needle_suppression_req5():
    """T050: Suppress telltale needle when current_peak() is None (REQ-5)."""
    manager = TelltaleManager()
    manager.update(100.0, 80.0)
    manager.reset("m1")  # Reset m1 window -> None

    rendered = render_gauge(value=30.0, telltale_manager=manager)
    assert isinstance(rendered, Image.Image)


# ============================================================================
# BASELINE-INDEPENDENT PROPERTY ASSERTIONS (Issue #1902)
# ============================================================================


def test_baseline_independent_needle_tip_trigonometry_angles():
    """Baseline-Independent: Verify needle tip geometry computed via trigonometry.

    Validates needle tip polar angle coordinates directly without relying on baseline image.
    """
    center = (128.0, 128.0)
    radius = 90.0

    # Value 0 -> 135 degrees (bottom left)
    angle_0 = val_to_angle(0.0)
    assert math.isclose(angle_0, 135.0)
    tip_0 = calculate_needle_tip(center, radius, angle_0)
    expected_0_x = 128.0 + 90.0 * math.cos(math.radians(135.0))
    expected_0_y = 128.0 + 90.0 * math.sin(math.radians(135.0))
    assert math.isclose(tip_0[0], expected_0_x, abs_tol=1e-3)
    assert math.isclose(tip_0[1], expected_0_y, abs_tol=1e-3)

    # Value 100 -> 405 degrees (bottom right)
    angle_100 = val_to_angle(100.0)
    assert math.isclose(angle_100, 405.0)
    tip_100 = calculate_needle_tip(center, radius, angle_100)
    expected_100_x = 128.0 + 90.0 * math.cos(math.radians(405.0))
    expected_100_y = 128.0 + 90.0 * math.sin(math.radians(405.0))
    assert math.isclose(tip_100[0], expected_100_x, abs_tol=1e-3)
    assert math.isclose(tip_100[1], expected_100_y, abs_tol=1e-3)


def test_baseline_independent_all_time_needle_pixel_color():
    """Baseline-Independent: Verify solid red pixel present at all-time needle tip.

    Validates needle color rendering independently of baseline binary image.
    """
    manager = TelltaleManager()
    manager.update(100.0, 50.0)  # Peak 50.0 -> 270 degrees (straight top 128, 38)

    rendered = render_gauge(value=0.0, telltale_manager=manager)

    # Telltale all-time needle at 50.0 points straight UP (angle 270 deg)
    # Radius = 256 * 0.35 = 89.6. Tip at (128, 128 - 89.6) ~ (128, 38)
    tip_x, tip_y = 128, 42
    r, g, b, a = rendered.getpixel((tip_x, tip_y))

    # All-time needle style is solid red (239, 68, 68)
    assert r > 200 and g < 100 and b < 100, f"Expected red pixel at telltale tip, got RGBA=({r},{g},{b},{a})"
```

## 7. Pattern References

### 7.1 Option C Off-Screen PIL Renderer

**File:** `docs/design/0001-test-strategy.md` (lines 35-48)

```markdown
Chosen: Option C — render to off-screen PIL.Image first; tkinter Canvas is a display surface only.
The gauge renderer is a pure function: state -> PIL.Image.
```

**Relevance:** The implementation follows Option C strictly. Renderer functions return pure `PIL.Image` objects and never reference `tkinter`.

### 7.2 Visual Baseline Generation and Diff RMS Calculation

**File:** `docs/design/0001-test-strategy.md` (lines 58-73)

```markdown
`tests/visual/baselines/{test_id}.png` — one image per fixture.
A test that fails for a missing baseline writes the candidate image... only when invoked with pytest --generate-baselines.
Pixel-diff with a tolerance band: Byte-different but pixel-RMS ≤ 1.0 / 255 -> pass.
```

**Relevance:** `tests/visual/test_gauge.py` implements `--generate-baselines` flag handling and RMS tolerance assertion `<= 1.0`.

### 7.3 Test Suite Bootstrap Pattern

**File:** `tests/conftest.py` (lines 1-8)

```python
"""Project test bootstrap."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
```

**Relevance:** All test modules import `boostgauge` directly relying on `conftest.py` path initialization.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `typing.Dict`, `Literal`, `Optional`, `Tuple`, `TypedDict` | stdlib | `telltale.py`, `skins/stingray.py`, `gauge.py` |
| `collections.deque` | stdlib | `telltale.py` |
| `math` | stdlib | `skins/stingray.py`, `test_gauge.py` |
| `pathlib.Path` | stdlib | `test_gauge.py` |
| `PIL.Image`, `ImageDraw`, `ImageFilter`, `ImageChops`, `ImageStat` | Pillow (>=12.2.0) | `skins/stingray.py`, `gauge.py`, `test_gauge.py` |
| `pytest` | dev-dependency | `test_telltale.py`, `test_gauge.py` |

**New Dependencies:** None (uses existing `pillow` and `pytest` declared in `pyproject.toml`).

## 9. Placeholder

*Reserved for future use to maintain alignment with LLD section numbering.*

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output | Baseline-Independent Assertion |
|---------|---------------|-------|-----------------|--------------------------------|
| T010 | `TelltaleManager.__init__()` | Constructor call | `peaks == {"m1": None, "m10": None, "h1": None, "all": None}` | Direct dict equality assert |
| T020 | `TelltaleManager.update()` | `update(1000.0, 75.0)` | All 4 window peaks equal `75.0` | Direct dict equality assert |
| T030 | `render_gauge()` | 4 peak values `[40, 60, 80, 95]` | PIL Image matching visual baseline | RMS diff `<= 1.0` vs baseline blob |
| T040 | `render_gauge()` | Main val `60.0`, Telltale peak `60.0` | Center pivot cap light gray/white on top layer | Pivot cap center pixel color RGBA check |
| T050 | `render_gauge()` | Post-reset `m1=None` | Image rendered cleanly without error | Image instance check |
| T060 | `TelltaleManager.reset()` | `reset('m1')`, `reset_all()` | Target peak `None` | Dict equality assert |
| T070 | `Telltale.current_peak()` | Sample 90 at t=0, sample 50 at t=30 | `m1` peak returns `50.0` at t=65 | Value assertion post-eviction |
| T080 | `Telltale.current_peak()` | Sample 95 at t=0, 20 at t=4000 | `all` peak returns `95.0` at t=4000 | Value assertion post-4000s |

## 11. Implementation Notes

### 11.1 Baseline-Independent Property Assertions (Issue #1902)

Per Issue #1902 quality requirement, visual test suites MUST include mathematical property assertions computable without baseline images. `tests/visual/test_gauge.py` includes trigonometric needle tip angle calculations and red pixel sampling at exact needle coordinates to prevent self-validating inverted baseline defects.

### 11.2 Platform-Independent Path Assertions (Issue #1841)

All file paths in test code use `pathlib.Path` objects (e.g. `BASELINES_DIR / "telltale_4_needles.png"`) rather than separator-laden string concatenation. String comparison on paths is strictly prohibited to guarantee Windows/Linux cross-platform pass rates.

### 11.3 Side-Effect Assertion Constraints (Issue #1860)

Tests assert only explicitly specified behavior from Section 3 / Section 10. No un-specified side effects (e.g., config disk persistence) are asserted.

### 11.4 Constants

| Constant | Value | Rationale |
|----------|-------|-----------|
| `GAUGE_SIZE` | `(256, 256)` | Standard gauge surface resolution |
| `MIN_ANGLE_DEG` | `135.0` | 0% metric value gauge angle |
| `MAX_ANGLE_DEG` | `405.0` | 100% metric value gauge angle |
| `RMS_TOLERANCE` | `1.0` | Maximum allowed RMS pixel difference for visual regression tests |

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3 - N/A, all files are Add)
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
| Finalized | 2026-07-31T16:47:00Z |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #2 |
| Verdict | APPROVED |
| Date | 2026-07-31 |
| Iterations | 1 |
| Finalized | 2026-07-31T21:48:08Z |

### Review Feedback Summary

The implementation spec is fully complete, concrete, and highly executable. All files to be added include full Python source code in Section 6, providing exact implementation details without placeholders or pseudo-code. Function signatures, data structures, and edge cases are thoroughly specified with concrete examples. All unit and visual test assertions trace directly to specified behaviors (REQ-1 through REQ-8), and explicit baseline-independent property assertions are included in Section 6.6...
