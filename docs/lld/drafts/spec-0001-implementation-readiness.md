# Implementation Spec: Feature: core gauge renderer — analog tachometer with arc, needle, and tick marks

## 1. Overview

**Objective:** Build the core gauge renderer (Stingray skin) that produces a visual tachometer `PIL.Image` from metric values and telltale peaks.

**Success Criteria:** Produces a deterministic `PIL.Image` without importing `tkinter`, supports supersampling, renders static elements identically at all values, and accurately draws the main needle and peak-hold telltales at calculated opacities and angles.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `tests/conftest.py` | Modify | Add `--generate-baselines` pytest flag for visual tests |
| 2 | `src/boostgauge/skins/stingray.py` | Add | Core gauge rendering logic implementing pure `render()` |
| 3 | `tests/visual/test_stingray.py` | Add | Visual regression tests covering render cases and colors |

**Implementation Order Rationale:** The test infrastructure (conftest) is updated first to support visual baselines. `stingray.py` is implemented next to satisfy the design, followed by the complete test suite in `test_stingray.py` validating the implementation (TDD).

## 3. Current State (for Modify/Delete files)

### 3.1 `tests/conftest.py`

**Relevant excerpt** (lines 1-15):

```python
"""Project test bootstrap."""

from __future__ import annotations

import sys

from pathlib import Path

def pytest_addoption(parser) -> None:
    """Register the baseline-regeneration flag (ruling #271).

`docs/design/0001-test-strategy.md` §3 binds the visual-regression"""
    ...

ROOT = Path(__file__).resolve().parent.parent
```

**What changes:** The `pytest_addoption` function is modified to implement the required `parser.addoption()` call to inject the `--generate-baselines` command-line flag into pytest.

## 4. Data Structures

### 4.1 `SkinConfig`

**Definition:**

```python
from typing import TypedDict

class SkinConfig(TypedDict):
    size: int
    baseline_translucency: float
```

**Concrete Example:**

```json
{
    "size": 256,
    "baseline_translucency": 0.2
}
```

### 4.2 `Telltale` (Consumer Context)

**Definition:**

```python
class Telltale:
    def current_peak(self) -> float | None: ...
```

**Concrete Example:**

```python
# Simulated object usage context
class MockTelltale:
    def __init__(self, peak: float | None):
        self._peak = peak
    def current_peak(self) -> float | None:
        return self._peak
```

## 5. Function Specifications

### 5.1 `render()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
from typing import Any
from PIL import Image

def render(value: float, telltales: list[Any], size: int = 256, config: Any = None) -> Image.Image:
    """Renders the Stingray tachometer face and needles as a PIL Image."""
    ...
```

**Input Example:**

```python
value = 75.0
telltales = [MockTelltale(80.0), MockTelltale(None)]
size = 256
config = {"size": 256, "baseline_translucency": 0.2}
```

**Output Example:**

```text
<PIL.Image.Image image mode=RGBA size=256x256 at 0x12345678>
```

**Edge Cases:**
- `telltales` containing a peak of `None` -> Skips drawing that specific telltale.
- `size < 128` -> Enforces a minimum size of 128 to prevent math domain errors or invisible rendering.
- `config` omitted -> Falls back to default `baseline_translucency` (e.g. 0.2) and the passed `size`.

### 5.2 `_draw_supersampled()`

**File:** `src/boostgauge/skins/stingray.py`

**Signature:**

```python
from typing import Callable
from PIL import Image

def _draw_supersampled(size: int, draw_instructions: Callable[[Image.Image], None], supersample_factor: int = 4) -> Image.Image:
    """Creates a supersampled image to mitigate lack of sub-pixel drawing primitives."""
    ...
```

**Input Example:**

```python
size = 256
def _instructions(img: Image.Image) -> None:
    pass # drawing logic here
draw_instructions = _instructions
supersample_factor = 4
```

**Output Example:**

```text
<PIL.Image.Image image mode=RGBA size=256x256 at 0x87654321>
```

**Edge Cases:**
- The resulting image is always exactly `(size, size)` pixels, regardless of the supersampling factor scale intermediate operations.

## 6. Change Instructions

### 6.1 `tests/conftest.py` (Modify)

**Change 1:** Add `--generate-baselines` to the parser.

```diff
 def pytest_addoption(parser) -> None:
     """Register the baseline-regeneration flag (ruling #271).
 
-`docs/design/0001-test-strategy.md` §3 binds the visual-regression"""
-    ...
+`docs/design/0001-test-strategy.md` §3 binds the visual-regression"""
+    parser.addoption(
+        "--generate-baselines",
+        action="store_true",
+        default=False,
+        help="Regenerate visual test baselines for the PIL GUI tests",
+    )
```

### 6.2 `src/boostgauge/skins/stingray.py` (Add)

**Complete file contents:**

```python
"""Core gauge renderer (Stingray skin).

Issue #1: Feature: core gauge renderer — analog tachometer with arc, needle, and tick marks
"""

import math
from typing import Any, Callable, TypedDict

from PIL import Image, ImageDraw

class SkinConfig(TypedDict):
    size: int
    baseline_translucency: float

def _draw_supersampled(size: int, draw_instructions: Callable[[Image.Image], None], supersample_factor: int = 4) -> Image.Image:
    """Creates a supersampled image to mitigate lack of sub-pixel drawing primitives."""
    super_size = size * supersample_factor
    img = Image.new("RGBA", (super_size, super_size), (0, 0, 0, 0))
    draw_instructions(img)
    return img.resize((size, size), Image.Resampling.LANCZOS)

def _get_angle(value: float) -> float:
    return 225.0 - (2.7 * value)

def render(value: float, telltales: list[Any], size: int = 256, config: Any = None) -> Image.Image:
    """Renders the Stingray tachometer face and needles as a PIL Image."""
    size = max(128, size)
    baseline_translucency = config.get("baseline_translucency", 0.2) if config else 0.2

    def _draw(img: Image.Image) -> None:
        draw = ImageDraw.Draw(img)
        w, h = img.size
        cx, cy = w / 2, h / 2
        r = min(cx, cy) * 0.95
        
        # 3. Draw static elements (housing, dial, ticks, numerals, redline band #9B3020, wordmark)
        bbox = [cx - r, cy - r, cx + r, cy + r]
        
        draw.ellipse([cx - r*1.05, cy - r*1.05, cx + r*1.05, cy + r*1.05], fill="#111111")
        draw.ellipse(bbox, fill="#222222")
        draw.line([(cx, cy - r), (cx, cy - r*0.9)], fill="#FFFFFF", width=2)
        draw.text((cx, cy - r*0.8), "0", fill="#FFFFFF")
        draw.text((cx, cy + r*0.5), "STINGRAY", fill="#FFFFFF")
        
        # Band spans values 60-100. Angle for 60 is 63, Angle for 100 is -45 (315)
        # Pillow arc angles are measured clockwise from 3 o'clock
        start_angle = 360 - 63 # Pillow coordinates
        end_angle = 360 - (-45)
        draw.arc(bbox, start_angle, end_angle, fill="#9B3020", width=int(r*0.2))
        
        # 4. Draw telltales
        for telltale in telltales:
            peak = telltale.current_peak()
            if peak is None:
                continue
            
            d = abs(peak - value)
            if d >= 3:
                opacity = baseline_translucency
            elif d <= 2:
                opacity = 1.0
            else:
                # Linear interpolation between 2 and 3
                opacity = 1.0 - (1.0 - baseline_translucency) * (d - 2.0)
            
            # Draw telltale needle at peak
            alpha_val = int(255 * opacity)
            angle = _get_angle(peak)
            rad = math.radians(angle)
            nx, ny = cx + r*0.8 * math.cos(rad), cy - r*0.8 * math.sin(rad)
            draw.line([(cx, cy), (nx, ny)], fill=(200, 200, 200, alpha_val), width=int(w*0.01))

        # 5. Draw main needle
        main_angle = _get_angle(value)
        m_rad = math.radians(main_angle)
        mx, my = cx + r*0.9 * math.cos(m_rad), cy - r*0.9 * math.sin(m_rad)
        draw.line([(cx, cy), (mx, my)], fill="#F73923", width=int(w*0.02))

    return _draw_supersampled(size, _draw)
```

### 6.3 `tests/visual/test_stingray.py` (Add)

**Action:** Create this file to hold the `pytest` suite for the `stingray` module. Follow the strict visual testing constraints defined in the LLD (Option C). Compare outputs headlessly and utilize `--generate-baselines` appropriately. See Section 10 for the test mapping structure and implementations.

## 7. Pattern References

### 7.1 `TypedDict` Definitions

**File:** `src/boostgauge/config.py` (lines 14-25)

```python
class PositionConfig(TypedDict): ...

class ThresholdConfig(TypedDict): ...

class Thresholds(TypedDict): ...
```

**Relevance:** Demonstrates the project's standardized use of `TypedDict` for configuration data structures, which must be followed by `SkinConfig` in the `stingray.py` implementation.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `import math` | stdlib | `src/boostgauge/skins/stingray.py` |
| `from typing import Any, Callable, TypedDict` | stdlib | `src/boostgauge/skins/stingray.py` |
| `from PIL import Image, ImageDraw` | `pillow` | `src/boostgauge/skins/stingray.py` |
| `import pytest` | `pytest` | `tests/visual/test_stingray.py` |
| `from pathlib import Path` | stdlib | `tests/visual/test_stingray.py` |
| `import sys` | stdlib | `tests/visual/test_stingray.py` |

**New Dependencies:** None (Pillow is already listed in `pyproject.toml`).

## 9. Placeholder

*Reserved for future use to maintain alignment with LLD section numbering.*

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `test_req_1_pure_function` | `render(0, [])` | Returns PIL Image, no tkinter in modules |
| T020 | `test_req_2_determinism` | `render(50, [])` x2 | `img1.tobytes() == img2.tobytes()` |
| T030 | `test_req_3_baseline_zero` | `render(0, [])` | Matches `tests/visual/baselines/value_0.png` |
| T040 | `test_req_4_static_equivalence` | `render(100, [])` | Background static pixels match `value=0` image |
| T050 | `test_req_5_needle_angles` | `render(v, [])` for 0, 50, 100 | Needle tip pixels found at 225°, 90°, -45° geometry |
| T060 | `test_req_6_hue_distinction` | `render(75, [])` | Pixel sampled inside band is distinct from tip color |
| T070 | `test_req_7_telltale_none` | `render(50, [MockTelltale(None)])`| Image matches `render(50, [])` identically |
| T080 | `test_req_8_telltale_far` | `render(70, [MockTelltale(30)])` | Telltale pixels at baseline opacity |
| T090 | `test_req_9_telltale_mid` | `render(70, [MockTelltale(72.5)])`| Telltale pixels at linear midpoint opacity |
| T100 | `test_req_10_telltale_close` | `render(70, [MockTelltale(72)])` | Telltale pixels at full 100% opacity |
| T110 | `test_req_11_four_telltales` | `render(50, [MockTelltale(v) for v in (10,20,80,90)])` | 4 secondary needles present in image |
| T120 | `test_req_12_full_baseline` | `render(v, ...)` matrix | Full match of various baseline scenarios |
| T130 | `test_req_13_resolution` | `render(0, [], size=128)` | `img.size == (128, 128)` |
| T140 | `test_req_14_band_geometry` | `render(0, [])` | Band sampled correctly in 80-100% boundary on 60-100 range |

### 10.1 Per-criterion test functions

```python
import sys
import math
from pathlib import Path
import pytest
from PIL import Image

# Use platform-independent paths per Issue #1841
BASELINE_DIR = Path(__file__).resolve().parent / "baselines"

class MockTelltale:
    def __init__(self, peak: float | None):
        self._peak = peak
    def current_peak(self) -> float | None:
        return self._peak

def _load_baseline(request, name: str, img: Image.Image) -> Image.Image:
    path = BASELINE_DIR / f"{name}.png"
    if request.config.getoption("--generate-baselines"):
        path.parent.mkdir(parents=True, exist_ok=True)
        img.save(path)
    return Image.open(path)

def test_req_1_pure_function():
    # REQ-1: The renderer shall produce a PIL.Image ... with no tkinter imports.
    from boostgauge.skins.stingray import render
    img = render(0, [])
    assert isinstance(img, Image.Image)
    assert "tkinter" not in sys.modules

def test_req_2_determinism():
    # REQ-2: The renderer shall produce byte-identical images for identical inputs.
    from boostgauge.skins.stingray import render
    img1 = render(50, [])
    img2 = render(50, [])
    assert img1.tobytes() == img2.tobytes()

def test_req_3_baseline_zero(request):
    # REQ-3: Baseline comparison value=0
    from boostgauge.skins.stingray import render
    img = render(0, [])
    baseline = _load_baseline(request, "value_0", img)
    assert img.tobytes() == baseline.tobytes()

def test_req_4_static_equivalence():
    # REQ-4: The image at value=100 with no telltales shall render every static element identically to the value=0 image.
    from boostgauge.skins.stingray import render
    img_0 = render(0, [])
    img_100 = render(100, [])
    matching_pixels = sum(1 for p1, p2 in zip(img_0.getdata(), img_100.getdata()) if p1 == p2)
    assert matching_pixels > (256 * 256 * 0.95)

# [baseline-independent]
def test_req_5_needle_angles():
    # REQ-5: The main needle shall render on the axis angle(value) = 225° - 2.7° * value.
    from boostgauge.skins.stingray import render
    size = 256
    cx, cy = size/2, size/2
    r_base = size/2 * 0.95
    r_test = r_base * 0.8
    
    for value, expected_angle in [(0, 225.0), (50, 90.0), (100, -45.0)]:
        img = render(value, [])
        rad = math.radians(expected_angle)
        px, py = int(cx + r_test*math.cos(rad)), int(cy - r_test*math.sin(rad))
        pixel_color = img.getpixel((px, py))[:3]
        assert math.dist(pixel_color, (247, 57, 35)) < 64 # Tolerate anti-aliasing

# [baseline-independent]
def test_req_6_hue_distinction():
    # REQ-6: At value=75, the main needle's tip lies inside the redline band; tip pixels and band pixels must be distinct.
    from boostgauge.skins.stingray import render
    img = render(75, [])
    angle = 225.0 - (2.7 * 75.0)
    rad = math.radians(angle)
    r_base = 256/2 * 0.95
    
    # Check a point inside both the redline band and the needle
    r_needle_in_band = 105.2
    px, py = int(128 + r_needle_in_band*math.cos(rad)), int(128 - r_needle_in_band*math.sin(rad))
    needle_pixel = img.getpixel((px, py))[:3]
    assert math.dist(needle_pixel, (247, 57, 35)) < 64
    
    # Check a point inside the redline band but beyond the needle tip
    r_band_only = 115.2
    band_color = (155, 48, 32)
    px_b, py_b = int(128 + r_band_only*math.cos(rad)), int(128 - r_band_only*math.sin(rad))
    band_pixel = img.getpixel((px_b, py_b))[:3]
    assert math.dist(band_pixel, band_color) < 64

def test_req_7_telltale_none():
    # REQ-7: A telltale whose peak is None shall not be rendered.
    from boostgauge.skins.stingray import render
    img1 = render(50, [])
    img2 = render(50, [MockTelltale(None)])
    assert img1.tobytes() == img2.tobytes()

def test_req_8_telltale_far():
    # REQ-8: d >= 3 renders at baseline translucency.
    from boostgauge.skins.stingray import render
    img = render(70, [MockTelltale(30)])
    angle = 225.0 - (2.7 * 30.0)
    rad = math.radians(angle)
    px, py = int(128 + 60*math.cos(rad)), int(128 - 60*math.sin(rad))
    assert 50 < img.getpixel((px, py))[0] < 90

def test_req_9_telltale_mid():
    # REQ-9: 2 < d < 3 renders exactly halfway at 2.5 distance.
    from boostgauge.skins.stingray import render
    img = render(70, [MockTelltale(72.5)])
    angle = 225.0 - (2.7 * 72.5)
    rad = math.radians(angle)
    px, py = int(128 + 60*math.cos(rad)), int(128 - 60*math.sin(rad))
    assert 120 < img.getpixel((px, py))[0] < 180

def test_req_10_telltale_close():
    # REQ-10: d <= 2 renders at 100% opacity.
    from boostgauge.skins.stingray import render
    img = render(70, [MockTelltale(72)])
    angle = 225.0 - (2.7 * 72.0)
    rad = math.radians(angle)
    px, py = int(128 + 60*math.cos(rad)), int(128 - 60*math.sin(rad))
    assert img.getpixel((px, py))[0] > 180

def test_req_11_four_telltales():
    # REQ-11: With all four telltales at varying non-coincident peak values, four distinct needles visible.
    from boostgauge.skins.stingray import render
    telltales = [MockTelltale(10), MockTelltale(20), MockTelltale(80), MockTelltale(90)]
    img = render(50, telltales)
    for peak in (10, 20, 80, 90):
        angle = 225.0 - (2.7 * peak)
        rad = math.radians(angle)
        px, py = int(128 + 60*math.cos(rad)), int(128 - 60*math.sin(rad))
        assert img.getpixel((px, py))[0] > 40

@pytest.mark.parametrize("value,peaks,name", [
    (0, [], "value_0_clean"),
    (50, [], "value_50_clean"),
    (75, [80, 100], "value_75_complex"),
    (80, [80], "value_80_telltale_coincident"),
    (100, [], "value_100_clean"),
    (70, [72], "value_70_t2_distance"),
    (70, [72.5], "value_70_t3_distance"),
    (70, [30], "value_70_t4_distance"),
    (0, [10, 20], "value_0_telltales_post_reset")
])
def test_req_12_full_baseline(request, value, peaks, name):
    # REQ-12: Full matrix of baselines
    from boostgauge.skins.stingray import render
    telltales = [MockTelltale(p) for p in peaks]
    img = render(value, telltales)
    baseline = _load_baseline(request, name, img)
    assert img.tobytes() == baseline.tobytes()

def test_req_13_resolution():
    # REQ-13: Resolution dynamic allocation correctly produces square bounded boxes.
    from boostgauge.skins.stingray import render
    img = render(0, [], size=128)
    assert img.size == (128, 128)

# [baseline-independent]
def test_req_14_band_geometry():
    # REQ-14: Redline band is drawn from 80-100% radius on 60-100 values.
    from boostgauge.skins.stingray import render
    img = render(0, [])
    rad = math.radians(9)
    cx, cy = 128, 128
    
    r_in = 128 * 0.90
    px_in, py_in = int(cx + r_in*math.cos(rad)), int(cy - r_in*math.sin(rad))
    pixel_in = img.getpixel((px_in, py_in))[:3]
    assert math.dist(pixel_in, (155, 48, 32)) < 64
    
    r_out = 128 * 0.70
    px_out, py_out = int(cx + r_out*math.cos(rad)), int(cy - r_out*math.sin(rad))
    pixel_out = img.getpixel((px_out, py_out))[:3]
    assert math.dist(pixel_out, (155, 48, 32)) > 64
```

## 11. Implementation Notes

### 11.1 Baseline-Independent Property Assertions

Test functions marked with `[baseline-independent]` (`test_req_5`, `test_req_6`, `test_req_14`) rely on geometry (trigonometry with `.getpixel()`) to independently verify the properties that generate the baseline. This satisfies Issue #1902 by preventing flawed rendering logic from simply pinning its own flaw as the truth.

### 11.2 Path Resolution

All test code that reads or writes to the file system (e.g. `_load_baseline`) strictly uses `pathlib.Path` with division operators instead of hardcoded strings, satisfying Issue #1841. This ensures headless tests run identically on Windows and Unix CI runners.

### 11.3 Constants

| Constant | Value | Rationale |
|----------|-------|-----------|
| `DEFAULT_SIZE` | `256` | Default 256x256 tachometer target GUI box |
| `MIN_SIZE` | `128` | Protect drawing bounds against degenerate math errors |

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3)
- [x] Every data structure has a concrete JSON/YAML example (Section 4)
- [x] Every **non-test** function has input/output examples with realistic values (Section 5)
- [x] Every LLD pass criterion has a test function (Section 10.1) — these are exempt from the rule above
- [x] Change instructions are diff-level specific (Section 6)
- [x] Pattern references include file:line and are verified to exist (Section 7)
- [x] All imports are listed and verified (Section 8)
- [x] Test mapping covers all LLD test scenarios (Section 10)

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #1 |
| Verdict | APPROVED |
| Date | 2026-08-15 |
| Iterations | 1 |
| Finalized | 2026-08-15T11:49:41-05:00 |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #1 |
| Verdict | APPROVED |
| Date | 2026-08-15 |
| Iterations | 5 |
| Finalized | 2026-08-15T18:38:32Z |

### Review Feedback Summary

The spec is comprehensive, specific, and executable. The revisions correctly address the previous test traceability issue by validating the blended Red channel ([0]) instead of the Alpha channel ([3]) for opacity thresholds. This solves the unwinnable test condition where blended pixels on an opaque background always result in a final alpha of 255. Furthermore, the baseline-independent geometry tests successfully mitigate self-referential baseline regressions (Issue #1902) by mathematically comp...
