# Implementation Spec: peak-hold telltale needles — 1m, 10m, 1h, all-time (#2)

| Field | Value |
|-------|-------|
| Issue | #2 |
| LLD | `docs/lld/done/0002-telltale-needles.md` |
| Generated | 2026-07-30 |
| Status | APPROVED |

---

## 1. Overview

**Objective:** Instantiate four sliding-window peak-hold `Telltale` instances (1m, 10m, 1h, all-time), pipe live metric updates, manage resets, and render their peak values on top of the gauge surface behind the main needle.

**Success Criteria:**
- Encapsulate sliding window peak hold instances inside `TelltaleManager` supporting 60s (`m1`), 600s (`m10`), 3600s (`h1`), and infinite (`all`) windows.
- Provide `update()`, `get_peaks()`, `reset()`, and `reset_all()` methods.
- Export `TelltaleManager` from `boostgauge.__init__`.
- Achieve ≥89% test coverage across unit tests (`test_telltale.py`) and visual regression tests (`test_gauge.py`).
- Validate visual telltale rendering using baseline-independent property assertions alongside off-screen image comparison under Option C GUI testing rules.

---

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/telltale.py` | Modify | Add `TelltaleManager` class to orchestrate 4 `Telltale` windows (60s, 600s, 3600s, `float('inf')`), stream routing, state extraction, and resets. |
| 2 | `src/boostgauge/__init__.py` | Modify | Export `TelltaleManager` in package `__all__` list. |
| 3 | `tests/unit/test_telltale.py` | Modify | Add unit tests for `TelltaleManager` initialization, multi-window metric distribution, peak dictionary extraction, individual window resets, and `reset_all()`. |
| 4 | `tests/visual/test_gauge.py` | Modify | Add visual regression test cases for distinct four-needle rendering, post-reset missing needle suppression, main needle z-order overlay, and baseline-independent pixel/geometry assertions. |

**Implementation Order Rationale:**
`src/boostgauge/telltale.py` defines `TelltaleManager` which is the core business logic facade. Next, `src/boostgauge/__init__.py` exposes `TelltaleManager` at package top-level. `tests/unit/test_telltale.py` verifies unit behavior before visual integration, and `tests/visual/test_gauge.py` tests off-screen PIL rendering of the gauge surface with active telltales.

---

## 3. Current State (for Modify/Delete files)

### 3.1 `src/boostgauge/telltale.py`

**Relevant excerpt** (lines 1-48):

```python
"""Pure sliding-window peak-hold needle logic with optional linear decay.

Issue #41: Telltale peak-hold needle logic (pure, no GUI)
"""

from __future__ import annotations

from collections import deque

from typing import Optional, Tuple

class Telltale:

    """Pure sliding-window peak-hold needle logic with optional linear decay."""

    def __init__(self, window: float, decay_rate: Optional[float] = None) -> None:
    """Initialize Telltale with window duration in seconds and optional decay rate (units/sec).

Args:"""
    ...

    def update(self, timestamp: float, value: float) -> None:
    """Feed a new sample (timestamp, value) into the telltale state.

Args:"""
    ...

    def _prune_expired(self, evaluation_time: float) -> None:
    """Prune samples older than (evaluation_time - window) from active window queues.

Args:"""
    ...

    def current_peak(self, timestamp: Optional[float] = None) -> Optional[float]:
    """Compute the effective peak value at the specified timestamp (or latest sample timestamp).

Args:"""
    ...

    def reset(self) -> None:
    """Clear all historical state; subsequent current_peak() calls return None until updated."""
    ...
```

**What changes:** Append `WindowKey`, `TelltaleDict`, `WindowConfig`, and `TelltaleManager` class implementation after the `Telltale` class.

---

### 3.2 `src/boostgauge/__init__.py`

**Relevant excerpt** (lines 1-20):

```python
"""BoostGauge package initialization.

Issue #7: Configuration File and CLI Arguments
"""

from boostgauge.collector import DataCollector, SystemSnapshot

from boostgauge.collectors import WindowsCollector, create_collector

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "DataCollector",
    "SystemSnapshot",
    "WindowsCollector",
    "create_collector",
]
```

**What changes:** Import `TelltaleManager` from `boostgauge.telltale` and add `"TelltaleManager"` to `__all__`.

---

### 3.3 `tests/unit/test_telltale.py`

**Relevant excerpt** (lines 1-52):

```python
"""Unit test suite for pure Telltale peak-hold needle logic.

Issue #41: Telltale peak-hold needle logic (pure, no GUI)
Ref: docs/design/0001-test-strategy (Option C unit tier compliance)
"""

from __future__ import annotations

import pytest

from boostgauge.telltale import Telltale

def test_t010_initialization_and_module_exposure() -> None:
    """T010: Test Telltale initialization and parameter storage."""
    ...

def test_t020_pre_update_peak_return() -> None:
    """T020: Verify current_peak() returns None before any update calls."""
    ...

def test_t030_single_sample_update() -> None:
    """T030: Verify single sample update returns the exact sample value."""
    ...

def test_t040_rising_series_tracking() -> None:
    """T040: Verify peak updates immediately when new maximum sample arrives."""
    ...

def test_t050_window_drop_without_decay() -> None:
    """T050: Verify instant drop to active window max when high ages out without decay."""
    ...

def test_t060_monotonic_decay_from_expired_high() -> None:
    """T060: Verify linear decay at decay_rate units/sec from departed peak."""
    ...

def test_t070_active_window_decay_floor() -> None:
    """T070: Verify active window max acts as floor for linear decay."""
    ...

def test_t080_reset_behavior() -> None:
    """T080: Verify reset clears all historical state and sample queues."""
    ...

def test_t090_invalid_window_duration_parameter() -> None:
    """T090: Verify ValueError raised when window duration <= 0."""
    ...

def test_t100_invalid_decay_rate_parameter() -> None:
    """T100: Verify ValueError raised when decay_rate < 0."""
    ...
```

**What changes:** Append unit tests targeting `TelltaleManager` behavior (scenarios T010_mgr through T080_mgr for manager initialization, window updates, peak dictionary extraction, window resets, 1m drop-back, and all-time window persistence).

---

### 3.4 `tests/visual/test_gauge.py`

**Relevant excerpt** (lines 1-38):

```python
"""Visual regression test suite for boostgauge off-screen rendering (Option C).

Issue #1: Core Gauge Renderer
"""

from __future__ import annotations

from pathlib import Path

import pytest

from PIL import Image

from boostgauge.gauge import render

def calculate_rms_diff(img1: Image.Image, img2: Image.Image) -> float:
    """Calculate normalized Root-Mean-Square pixel difference between two images."""
    ...

def get_baseline_path(filename: str) -> Path:
    """Resolve cross-platform path to visual baseline PNG file."""
    ...

def test_t040_rest_state_visual_regression(pytestconfig):
    """Assert rest state (value=0, telltales=None) against canonical baseline PNG."""
    ...

def test_t050_telltale_needle_rendering():
    """Verify telltales rendering produces a visually distinct image from rest state."""
    ...

def test_t060_telltales_none_removal():
    """Verify passing telltales with all None produces byte-identical output to telltales=None."""
    ...

def test_t070_redline_arc_visual_distinction():
    """Verify value=75 renders main needle cleanly within redline arc zone."""
    ...
```

**What changes:** Add tests `test_t080_four_distinct_telltale_needles_rendering()` and `test_t090_telltale_baseline_independent_needle_positions()` verifying needle presence, color distinction, and geometric angle assertions without baseline dependencies.

---

## 4. Data Structures

### 4.1 `WindowKey` & `WindowConfig`

**Definition:**

```python
from typing import Dict, Literal, Optional, TypedDict

WindowKey = Literal["m1", "m10", "h1", "all"]

class WindowConfig(TypedDict):
    """Configuration mapping window key to duration in seconds."""
    key: WindowKey
    duration: float  # float('inf') for all-time
```

**Concrete Example (JSON):**

```json
{
    "key": "m1",
    "duration": 60.0
}
```

---

### 4.2 `TelltaleDict`

**Definition:**

```python
class TelltaleDict(TypedDict, total=False):
    """Dictionary mapping telltale window keys to current peak values (0.0 to 100.0 or None)."""
    m1: Optional[float]    # 1 minute sliding window peak (60s)
    m10: Optional[float]   # 10 minute sliding window peak (600s)
    h1: Optional[float]    # 1 hour sliding window peak (3600s)
    all: Optional[float]   # All-time peak (infinite window)
```

**Concrete Example (JSON):**

```json
{
    "m1": 45.2,
    "m10": 78.0,
    "h1": 89.5,
    "all": 95.0
}
```

---

## 5. Function Specifications

### 5.1 `TelltaleManager.__init__()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def __init__(self) -> None:
    """Initialize 4 Telltale instances with 60s, 600s, 3600s, and inf windows."""
```

**Input Example:** `mgr = TelltaleManager()`

**Output Example:** `mgr` instance with `mgr.telltales` dictionary mapping keys `"m1"`, `"m10"`, `"h1"`, `"all"` to `Telltale` instances.

**Edge Cases:** N/A (no arguments required).

---

### 5.2 `TelltaleManager.update()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def update(self, timestamp: float, value: float) -> None:
    """Pipe incoming sample timestamp and metric value to all four Telltale instances."""
```

**Input Example:**

```python
timestamp = 1700000000.0
value = 85.5
```

**Output Example:** `None` (side-effect: updates all 4 internal `Telltale` instances).

**Edge Cases:**
- `timestamp < 0`: raises `ValueError("Timestamp must be non-negative")`.
- Non-monotonic timestamp: raises `ValueError("Timestamp must be monotonically non-decreasing")`.

---

### 5.3 `TelltaleManager.get_peaks()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def get_peaks(self, timestamp: Optional[float] = None) -> TelltaleDict:
    """Extract current peak values for all windows formatted as a TelltaleDict."""
```

**Input Example:** `timestamp = 1700000065.0`

**Output Example:**

```python
{
    "m1": 30.0,
    "m10": 85.5,
    "h1": 85.5,
    "all": 85.5,
}
```

**Edge Cases:**
- Called before any samples provided: returns `{"m1": None, "m10": None, "h1": None, "all": None}`.
- `timestamp` omitted: evaluates peaks using the latest sample timestamp recorded across telltales.

---

### 5.4 `TelltaleManager.reset()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def reset(self, window_key: Optional[str] = None) -> None:
    """Reset specified telltale window ('m1', 'm10', 'h1', 'all'), or reset all if window_key is None or 'all_windows'."""
```

**Input Example:** `window_key = "m1"`

**Output Example:** `None` (side-effect: resets target window `Telltale` instance state).

**Edge Cases:**
- `window_key = None` or `window_key = "all_windows"`: calls `reset_all()`.
- `window_key = "invalid"`: raises `ValueError("Unknown window key: invalid")`.

---

### 5.5 `TelltaleManager.reset_all()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def reset_all(self) -> None:
    """Reset all four telltale instances to cleared state."""
```

**Input Example:** `mgr.reset_all()`

**Output Example:** `None` (side-effect: calls `.reset()` on all 4 `Telltale` instances).

**Edge Cases:** Safe to execute repeatedly on empty or previously reset managers.

---

## 6. Change Instructions

### 6.1 `src/boostgauge/telltale.py` (Modify)

**Change 1:** Add imports and type definitions for `TelltaleManager`.

```diff
-from typing import Optional, Tuple
+from typing import Dict, Literal, Optional, Tuple, TypedDict

+WindowKey = Literal["m1", "m10", "h1", "all"]
+
+class TelltaleDict(TypedDict, total=False):
+    """Dictionary mapping telltale window keys to current peak values (0.0 to 100.0 or None)."""
+    m1: Optional[float]
+    m10: Optional[float]
+    h1: Optional[float]
+    all: Optional[float]
+
+class WindowConfig(TypedDict):
+    """Configuration mapping window key to duration in seconds."""
+    key: WindowKey
+    duration: float
```

**Change 2:** Append `TelltaleManager` class to end of file.

```diff
     def reset(self) -> None:
         """Clear all historical state; subsequent current_peak() calls return None until updated."""
         self._samples.clear()
         self._last_timestamp = None
+
+
+class TelltaleManager:
+    """Manages lifecycle, metric routing, state extraction, and resets for 4 telltale windows."""
+
+    def __init__(self) -> None:
+        """Initialize 4 Telltale instances with 60s, 600s, 3600s, and inf windows."""
+        self.telltales: Dict[WindowKey, Telltale] = {
+            "m1": Telltale(window=60.0),
+            "m10": Telltale(window=600.0),
+            "h1": Telltale(window=3600.0),
+            "all": Telltale(window=float("inf")),
+        }
+        self._last_timestamp: Optional[float] = None
+
+    def update(self, timestamp: float, value: float) -> None:
+        """Pipe incoming sample timestamp and metric value to all four Telltale instances."""
+        if timestamp < 0:
+            raise ValueError("Timestamp must be non-negative")
+        if self._last_timestamp is not None and timestamp < self._last_timestamp:
+            raise ValueError("Timestamp must be monotonically non-decreasing")
+        self._last_timestamp = timestamp
+        for telltale in self.telltales.values():
+            telltale.update(timestamp, value)
+
+    def get_peaks(self, timestamp: Optional[float] = None) -> TelltaleDict:
+        """Extract current peak values for all windows formatted as a TelltaleDict."""
+        eval_ts = timestamp if timestamp is not None else self._last_timestamp
+        return {
+            "m1": self.telltales["m1"].current_peak(eval_ts),
+            "m10": self.telltales["m10"].current_peak(eval_ts),
+            "h1": self.telltales["h1"].current_peak(eval_ts),
+            "all": self.telltales["all"].current_peak(eval_ts),
+        }
+
+    def reset(self, window_key: Optional[str] = None) -> None:
+        """Reset specified telltale window ('m1', 'm10', 'h1', 'all'), or reset all if window_key is None or 'all_windows'."""
+        if window_key is None or window_key == "all_windows":
+            self.reset_all()
+        elif window_key in self.telltales:
+            self.telltales[window_key].reset()  # type: ignore[index]
+        else:
+            raise ValueError(f"Unknown window key: {window_key}")
+
+    def reset_all(self) -> None:
+        """Reset all four telltale instances to cleared state."""
+        for telltale in self.telltales.values():
+            telltale.reset()
+        self._last_timestamp = None
```

---

### 6.2 `src/boostgauge/__init__.py` (Modify)

**Change 1:** Export `TelltaleManager` from `boostgauge.__init__`.

```diff
 from boostgauge.collector import DataCollector, SystemSnapshot
 from boostgauge.collectors import WindowsCollector, create_collector
+from boostgauge.telltale import TelltaleManager
 
 __version__ = "0.1.0"
 
 __all__ = [
     "__version__",
     "DataCollector",
     "SystemSnapshot",
+    "TelltaleManager",
     "WindowsCollector",
     "create_collector",
 ]
```

---

### 6.3 `tests/unit/test_telltale.py` (Modify)

**Change 1:** Add tests for `TelltaleManager` functionality.

```diff
-from boostgauge.telltale import Telltale
+from boostgauge.telltale import Telltale, TelltaleManager

+def test_t010_mgr_initialization() -> None:
+    """T010_mgr: TelltaleManager creates 4 window keys (m1, m10, h1, all)."""
+    mgr = TelltaleManager()
+    assert set(mgr.telltales.keys()) == {"m1", "m10", "h1", "all"}
+    assert mgr.get_peaks() == {"m1": None, "m10": None, "h1": None, "all": None}
+
+def test_t020_mgr_update_distribution() -> None:
+    """T020_mgr: update(t, v) routes samples to all four windows."""
+    mgr = TelltaleManager()
+    mgr.update(100.0, 75.0)
+    peaks = mgr.get_peaks()
+    assert peaks == {"m1": 75.0, "m10": 75.0, "h1": 75.0, "all": 75.0}
+
+def test_t030_mgr_sliding_window_drop() -> None:
+    """T030_mgr: 1m peak drops after 60 seconds, while 10m/1h/all persist."""
+    mgr = TelltaleManager()
+    mgr.update(0.0, 90.0)
+    mgr.update(65.0, 30.0)
+    peaks = mgr.get_peaks(65.0)
+    assert peaks["m1"] == 30.0
+    assert peaks["m10"] == 90.0
+    assert peaks["h1"] == 90.0
+    assert peaks["all"] == 90.0
+
+def test_t040_mgr_all_time_persistence() -> None:
+    """T040_mgr: All-time window holds peak permanently past 3600 seconds."""
+    mgr = TelltaleManager()
+    mgr.update(0.0, 95.0)
+    mgr.update(4000.0, 10.0)
+    peaks = mgr.get_peaks(4000.0)
+    assert peaks["m1"] == 10.0
+    assert peaks["m10"] == 10.0
+    assert peaks["h1"] == 10.0
+    assert peaks["all"] == 95.0
+
+def test_t050_mgr_individual_and_global_reset() -> None:
+    """T050_mgr: Test individual window reset and reset_all()."""
+    mgr = TelltaleManager()
+    mgr.update(100.0, 80.0)
+    mgr.reset("m1")
+    assert mgr.get_peaks()["m1"] is None
+    assert mgr.get_peaks()["m10"] == 80.0
+
+    mgr.reset("all_windows")
+    assert mgr.get_peaks() == {"m1": None, "m10": None, "h1": None, "all": None}
+
+def test_t060_mgr_invalid_reset_key() -> None:
+    """T060_mgr: ValueError raised on unknown reset key."""
+    mgr = TelltaleManager()
+    with pytest.raises(ValueError, match="Unknown window key: invalid_key"):
+        mgr.reset("invalid_key")
```

---

### 6.4 `tests/visual/test_gauge.py` (Modify)

**Change 1:** Add tests for distinct telltale rendering and baseline-independent needle assertions.

```diff
+def test_t080_four_distinct_telltale_needles_rendering():
+    """Verify gauge render with 4 active telltale peaks differs from rest state."""
+    rest_img = render(0.0, telltales=None)
+    telltale_img = render(
+        0.0,
+        telltales={"m1": 25.0, "m10": 50.0, "h1": 75.0, "all": 90.0}
+    )
+    rms_diff = calculate_rms_diff(rest_img, telltale_img)
+    assert rms_diff > 0.01, f"Expected visual difference from telltales, got RMS diff {rms_diff}"
+
+def test_t090_telltale_baseline_independent_needle_positions():
+    """Baseline-independent assertion: Verify pixel changes occur along expected needle vectors."""
+    rest_img = render(0.0, telltales=None)
+    telltale_img = render(
+        0.0,
+        telltales={"m1": 50.0, "m10": None, "h1": None, "all": None}
+    )
+    # 50% mark corresponds to vertical position at gauge center
+    w, h = rest_img.size
+    cx, cy = w // 2, h // 2
+    
+    # Inspect pixels around needle tip area for 50% value (straight up from center)
+    rest_pixels = rest_img.load()
+    telltale_pixels = telltale_img.load()
+    
+    # Needle tip at 50% value lies above center (cy - offset)
+    diffs = 0
+    for y in range(cy - 60, cy - 20):
+        for x in range(cx - 5, cx + 5):
+            if rest_pixels[x, y] != telltale_pixels[x, y]:
+                diffs += 1
+    
+    assert diffs > 0, "Baseline-independent check failed: No pixel modifications detected along 50% needle vector"
```

---

## 7. Pattern References

### 7.1 `Telltale` class pattern

**File:** `src/boostgauge/telltale.py` (lines 13-48)

```python
class Telltale:
    """Pure sliding-window peak-hold needle logic with optional linear decay."""
    def __init__(self, window: float, decay_rate: Optional[float] = None) -> None: ...
    def update(self, timestamp: float, value: float) -> None: ...
    def current_peak(self, timestamp: Optional[float] = None) -> Optional[float]: ...
    def reset(self) -> None: ...
```

**Relevance:** `TelltaleManager` wraps four standard instances of `Telltale` without modifying `Telltale` internal implementation, maintaining clean delegation and facade design.

---

### 7.2 Off-screen Pillow render pattern (Option C)

**File:** `tests/visual/test_gauge.py` (lines 10-38)

```python
from boostgauge.gauge import render

def calculate_rms_diff(img1: Image.Image, img2: Image.Image) -> float: ...

def test_t040_rest_state_visual_regression(pytestconfig):
    img = render(0.0, telltales=None)
    ...
```

**Relevance:** Dictates Option C compliance — off-screen Pillow image generation without instantiating `tkinter.Tk()`.

---

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `from typing import Dict, Literal, Optional, Tuple, TypedDict` | stdlib | `src/boostgauge/telltale.py` |
| `from boostgauge.telltale import Telltale, TelltaleManager` | internal | `src/boostgauge/__init__.py`, `tests/unit/test_telltale.py` |
| `from pathlib import Path` | stdlib | `tests/visual/test_gauge.py` |
| `from PIL import Image` | pillow | `tests/visual/test_gauge.py` |
| `import pytest` | pytest | `tests/unit/test_telltale.py`, `tests/visual/test_gauge.py` |

**New Dependencies:** None (uses existing `pillow`, `pytest`, `pytest-cov` dependencies).

---

## 9. Placeholder

*Reserved for future alignment with LLD section numbering.*

---

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `TelltaleManager.__init__()` | `mgr = TelltaleManager()` | `mgr.telltales.keys() == {"m1", "m10", "h1", "all"}` |
| T020 | `TelltaleManager.update()` | `mgr.update(100.0, 75.0)` | All 4 window peaks equal 75.0 |
| T030 | `TelltaleManager.get_peaks()` | `mgr.update(0.0, 90.0)`, `mgr.update(65.0, 30.0)` | `m1=30.0`, `m10=90.0`, `h1=90.0`, `all=90.0` |
| T040 | `render()` | `render(0.0, telltales={"m1":25, ...})` | Pillow `Image` with 4 distinct needles rendered |
| T050 | `render()` | `render(0.0, telltales={"m1":50, "m10":None, ...})` | Pillow `Image` matching single needle baseline |
| T060 | `TelltaleManager.reset()` | `mgr.reset("m1")` / `mgr.reset_all()` | `m1` peak becomes `None`, then all peaks become `None` |
| T070 | `TelltaleManager.get_peaks()` | Sample 90.0 at t=0, sample 30.0 at t=65 | `m1` drops to 30.0 after 60s window elapses |
| T080 | `TelltaleManager.get_peaks()` | Sample 95.0 at t=0, sample 10.0 at t=4000 | `all` peak remains 95.0 past 3600s |
| T090 | `render()` | `render(0.0, telltales=...)` | Needle tip pixel delta along 50% vector > 0 |

---

### 10.1 Baseline-Independent Property Assertions (Issue #1902)

Visual regression tests must complement image comparison with baseline-independent mathematical assertions:

1. **Needle Tip Geometry Assertion:**
   - Calculate needle tip position $(x_{tip}, y_{tip})$ for metric value $V \in [0, 100]$:
     $$\theta = \theta_{start} + \frac{V}{100} \cdot (\theta_{end} - \theta_{start})$$
     $$x_{tip} = c_x + r \cdot \cos(\theta), \quad y_{tip} = c_y + r \cdot \sin(\theta)$$
   - Assert pixel value difference between rest image `render(0.0, telltales=None)` and telltale image `render(0.0, telltales={"m1": V, ...})` in a bounding box surrounding $(x_{tip}, y_{tip})$.

2. **Cross-Platform Path Assertions (Issue #1841):**
   - In test files, compare `pathlib.Path` objects directly:
     ```python
     expected_path = Path("tests") / "visual" / "baselines" / "rest_state.png"
     assert resolved_path == expected_path
     ```
   - Never assert using string operations like `str(path).endswith("tests/visual/baselines/rest_state.png")`.

---

## 11. Implementation Notes

### 11.1 Error Handling & Key Validation

- `TelltaleManager.update()` enforces non-negative timestamps and monotonic progression.
- `TelltaleManager.reset()` validates input strings against allowed keys `{"m1", "m10", "h1", "all", "all_windows"}` and raises a `ValueError` for unknown keys.

### 11.2 Infinite Window Decay Behavior

- The `all` window initializes `Telltale(window=float('inf'))`.
- `Telltale._prune_expired()` computes `expiration_limit = evaluation_time - float('inf')` which yields `-inf`.
- All timestamps $t \ge 0$ satisfy $t > -inf$, ensuring samples in the `all` window are never pruned automatically and hold until an explicit `.reset()` call.

### 11.3 Constants & Window Configuration

| Window Key | Window Duration (sec) | Label | Default Color / Style |
|------------|-----------------------|-------|------------------------|
| `"m1"` | `60.0` | 1 Minute | Cyan / Solid |
| `"m10"` | `600.0` | 10 Minutes | Orange / Solid |
| `"h1"` | `3600.0` | 1 Hour | Purple / Dashed |
| `"all"` | `float('inf')` | All-Time | Red / Solid |

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
| Date | 2026-07-30 |
| Iterations | 1 |
| Finalized | 2026-07-30T03:38:22Z |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #2 |
| Verdict | APPROVED |
| Date | 2026-07-30 |
| Iterations | 1 |
| Finalized | 2026-07-30T08:39:00Z |

### Review Feedback Summary

The implementation spec for Issue #2 is complete, highly concrete, and fully actionable for an autonomous AI agent to implement with a high first-try success rate. All four affected files receive line-level diff instructions, data structures have concrete JSON examples, and function specifications detail inputs, outputs, and edge cases. Assertion traceability checks (Issue #1866) confirm that every assertion in the unit and visual test suites maps directly to explicit behaviors defined in the sp...
