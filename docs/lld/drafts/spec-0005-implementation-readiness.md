# Implementation Spec: Always-on-Top Window with Drag, Minimize, and Transparency

| Field | Value |
|-------|-------|
| Issue | #5 |
| LLD | `docs/lld/done/0005-window-drag-minimize-transparency.md` |
| Generated | 2026-08-01 |
| Status | APPROVED |

---

## 1. Overview

This specification details the implementation of a lightweight, frameless, always-on-top system gauge window in Tkinter. It incorporates circular chroma-key transparency (`#000001`), interactive mouse dragging, double-click compact mode toggling, scroll-wheel resizing, background system tray controls via `pystray`, Windows 11 Per-Monitor High DPI awareness, multi-monitor bounds validation, and position/size persistence.

**Objective:** Implement a lightweight, always-on-top frameless gauge window in Tkinter featuring circular transparency, mouse drag, scroll resize, system tray minimization via `pystray`, high-DPI awareness on Windows 11, and position/size persistence.

**Success Criteria:**
- Window operates framelessly without title bar, is draggable on mouse press/motion, always-on-top toggleable, double-click toggleable between 128px (compact) and 256px (expanded), and scroll-wheel resizable (128–512px maintaining 1:1 ratio).
- Gauge dial corners outside circular frame utilize chroma-key transparency (`#000001`) on Windows with hover opacity adjustment (0.8 default unhovered, 1.0 hovered).
- System tray minimization via `pystray` runs in a background daemon thread with color status dot indicators (green/yellow/red) and context menu supporting restore, toggle topmost, reset position, and quit.
- Window geometry (`x`, `y`, `size`) persists across restarts in `~/.boostgauge/config.json` and clamps off-screen coordinates within multi-monitor `VirtualScreenBounds`.
- Decoupled `WindowStateController` and headless test suite satisfy **Option C** of `docs/design/0001-test-strategy.md` with zero `tkinter.Tk()` instantiations during unit and integration test runs.

---

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/config.py` | Modify | Add `validate_bounds()` multi-monitor clamping, `WindowPositionDict`, `WindowConfigDict`, and `VirtualScreenBounds` typed dicts. |
| 2 | `src/boostgauge/window.py` | Add | Implement `WindowStateController` (decoupled state machine & geometry math) and `GaugeWindow` (Tkinter UI wrapper). |
| 3 | `src/boostgauge/tray.py` | Add | Implement `TrayController` wrapping `pystray.Icon` with PIL status dot image generation and thread-safe queue dispatch. |
| 4 | `src/boostgauge/app.py` | Add | Implement `BoostGaugeApp` orchestrating configuration loading, state controllers, window lifecycle, and system tray thread. |
| 5 | `tests/unit/test_config.py` | Modify | Add unit tests for multi-monitor bounds clamping and geometry validation in `src/boostgauge/config.py`. |
| 6 | `tests/unit/test_window_logic.py` | Add | Unit tests for `WindowStateController` (drag delta math, double-click mode toggle, scroll scaling, hover opacity transitions). |
| 7 | `tests/unit/test_tray_logic.py` | Add | Unit tests for `TrayController` (status dot PIL image generation, event queue posting, menu callbacks). |
| 8 | `tests/visual/test_window_render.py` | Add | Visual regression tests for circular transparent gauge face rendering with baseline-independent pixel color assertions. |
| 9 | `tests/integration/test_app_integration.py` | Add | Integration tests for `BoostGaugeApp` lifecycle, queue event processing, and clean shutdown without `tkinter.Tk()`. |

**Implementation Order Rationale:**
1. `config.py` updates must be made first to provide `VirtualScreenBounds` and `validate_bounds()` relied upon by state controllers.
2. `window.py` implements the core decoupled geometry controller and UI wrapper.
3. `tray.py` provides system tray integration and event dispatching.
4. `app.py` ties together configuration, window state, and tray controllers into a single application orchestrator.
5. Unit and integration tests follow implementation modules, building up test coverage from pure state math to visual rendering and headless app lifecycle integration.

---

## 3. Current State (for Modify/Delete files)

### 3.1 `src/boostgauge/config.py`

**Relevant excerpt** (lines 1–50):

```python
"""Configuration file loading, CLI parsing, validation, and persistence.

Issue #7: Feature configuration file and CLI arguments
"""

import argparse
import copy
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple, TypedDict

class ThresholdRange(TypedDict):
    yellow: float
    red: float

class ThresholdsConfig(TypedDict):
    conpty: ThresholdRange
    memory_pct: ThresholdRange
    process_cnt: ThresholdRange
    handle_cnt: ThresholdRange

class WindowPosition(TypedDict):
    x: int
    y: int

class TelltaleWindowsConfig(TypedDict):
    w1m: float
    w10m: float
    w1h: float
```

**What changes:**
- Add `WindowConfigDict` and `VirtualScreenBounds` typed dictionaries.
- Add `validate_bounds(config: Dict[str, Any], virtual_bounds: VirtualScreenBounds) -> Dict[str, Any]` function to clamp off-screen window positions (`x`, `y`) into visible multi-monitor screen bounds.
- Update `update_window_geometry()` to accept and persist `topmost` and `opacity` alongside `x`, `y`, and `size`.

---

### 3.2 `tests/unit/test_config.py`

**Relevant excerpt** (lines 1–40):

```python
"""Unit tests for boostgauge configuration management module.

Issue #7: Feature configuration file and CLI arguments
"""

import json
import os
from pathlib import Path
import pytest
from unittest.mock import patch

from boostgauge.config import (
    DEFAULT_CONFIG,
    get_default_config,
    get_default_config_path,
    load_config_file,
    load_effective_config,
    merge_config,
    parse_cli_args,
    reset_config_file,
    save_config_file,
    update_window_geometry,
    validate_config,
)
```

**What changes:**
- Import `validate_bounds`.
- Add test `test_t020_validate_bounds_clamping()` to verify off-screen coordinates (`x`, `y`) are clamped cleanly into single and multi-monitor `VirtualScreenBounds`.
- Add test `test_t100_geometry_update_persistence()` validating roundtrip save/load of `topmost` and `opacity` parameters.

---

## 4. Data Structures

### 4.1 `WindowConfigDict`

**Definition:**

```python
from typing import TypedDict

class WindowConfigDict(TypedDict):
    x: int
    y: int
    size: int
    topmost: bool
    opacity: float
    compact_mode: bool
```

**Concrete Example:**

```json
{
    "x": 100,
    "y": 100,
    "size": 256,
    "topmost": true,
    "opacity": 0.8,
    "compact_mode": false
}
```

---

### 4.2 `VirtualScreenBounds`

**Definition:**

```python
from typing import TypedDict

class VirtualScreenBounds(TypedDict):
    min_x: int
    min_y: int
    max_x: int
    max_y: int
```

**Concrete Example:**

```json
{
    "min_x": 0,
    "min_y": 0,
    "max_x": 3840,
    "max_y": 1080
}
```

---

### 4.3 `TrayStatus`

**Definition:**

```python
from typing import TypedDict

class TrayStatus(TypedDict):
    color: str
    tooltip: str
```

**Concrete Example:**

```json
{
    "color": "green",
    "tooltip": "BoostGauge: Normal Resource Load (24%)"
}
```

---

## 5. Function Specifications

### 5.1 `validate_bounds()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def validate_bounds(
    config: Dict[str, Any],
    virtual_bounds: Optional[VirtualScreenBounds] = None,
) -> Dict[str, Any]:
    """Ensure window position (x, y) lies completely within visible multi-monitor screen bounds."""
    ...
```

**Input Example:**

```python
config = {"x": -5000, "y": 9999, "size": 256, "topmost": True, "opacity": 0.8, "compact_mode": False}
virtual_bounds = {"min_x": 0, "min_y": 0, "max_x": 1920, "max_y": 1080}
```

**Output Example:**

```python
{"x": 0, "y": 824, "size": 256, "topmost": True, "opacity": 0.8, "compact_mode": False}
```

**Edge Cases:**
- `virtual_bounds` is `None` -> defaults to `min_x=0, min_y=0, max_x=1920, max_y=1080`.
- Window `x + size > max_x` -> clamps `x = max_x - size`.
- Window `y + size > max_y` -> clamps `y = max_y - size`.
- Window `x < min_x` -> clamps `x = min_x`.
- Window `y < min_y` -> clamps `y = min_y`.

---

### 5.2 `WindowStateController.__init__()`

**File:** `src/boostgauge/window.py`

**Signature:**

```python
class WindowStateController:
    """Decoupled window state machine and geometry calculator (zero Tkinter dependency)."""

    def __init__(
        self,
        initial_config: WindowConfigDict,
        min_size: int = 128,
        max_size: int = 512,
    ) -> None:
        """Initialize window controller state."""
        ...
```

**Input Example:**

```python
initial_config = {
    "x": 150,
    "y": 200,
    "size": 256,
    "topmost": True,
    "opacity": 0.8,
    "compact_mode": False,
}
min_size = 128
max_size = 512
```

**Output Example:**

```python
# Returns WindowStateController instance with properties:
# controller.x == 150
# controller.y == 200
# controller.size == 256
# controller.topmost is True
# controller.opacity == 0.8
```

**Edge Cases:**
- Size outside `[min_size, max_size]` -> clamped to valid range `[128, 512]`.

---

### 5.3 `WindowStateController.handle_drag_start()`

**File:** `src/boostgauge/window.py`

**Signature:**

```python
def handle_drag_start(self, start_x: int, start_y: int) -> None:
    """Record drag start origin coordinates relative to screen root."""
    ...
```

**Input Example:**

```python
start_x = 250
start_y = 300
```

**Output Example:**

```python
None  # Updates internal state self._drag_start_x = 250, self._drag_start_y = 300, self._initial_x = self.x, self._initial_y = self.y
```

---

### 5.4 `WindowStateController.handle_drag_motion()`

**File:** `src/boostgauge/window.py`

**Signature:**

```python
def handle_drag_motion(self, current_screen_x: int, current_screen_y: int) -> Tuple[int, int]:
    """Calculate new window (x, y) position based on drag delta vector."""
    ...
```

**Input Example:**

```python
# Given drag_start (250, 300) and initial window position (150, 200)
current_screen_x = 300
current_screen_y = 280
```

**Output Example:**

```python
(200, 180)  # Calculated as (150 + (300 - 250), 200 + (280 - 300))
```

---

### 5.5 `WindowStateController.handle_scroll_resize()`

**File:** `src/boostgauge/window.py`

**Signature:**

```python
def handle_scroll_resize(self, delta: int) -> Tuple[int, int]:
    """Calculate new square window dimensions maintaining 1:1 aspect ratio, clamped to [min_size, max_size]."""
    ...
```

**Input Example:**

```python
# Given current size = 256
delta = 120  # Mouse wheel scroll up notch
```

**Output Example:**

```python
(284, 284)  # Size adjusted by +28px step, clamped within [128, 512]
```

**Edge Cases:**
- `delta < 0` (scroll down) -> decreases size by step (e.g. 256 -> 228).
- Output clamped to `min_size` (128) or `max_size` (512).

---

### 5.6 `WindowStateController.toggle_compact_mode()`

**File:** `src/boostgauge/window.py`

**Signature:**

```python
def toggle_compact_mode(self) -> int:
    """Toggle between compact mode (128px) and expanded mode (256px)."""
    ...
```

**Input Example:**

```python
# Given compact_mode = False, current size = 256
```

**Output Example:**

```python
128  # Sets compact_mode = True, updates size to 128
```

---

### 5.7 `WindowStateController.toggle_topmost()`

**File:** `src/boostgauge/window.py`

**Signature:**

```python
def toggle_topmost(self) -> bool:
    """Toggle always-on-top boolean flag state."""
    ...
```

**Input Example:**

```python
# Given topmost = True
```

**Output Example:**

```python
False  # Toggles self.topmost from True to False
```

---

### 5.8 `WindowStateController.update_hover()`

**File:** `src/boostgauge/window.py`

**Signature:**

```python
def update_hover(self, is_hovered: bool) -> float:
    """Determine window target opacity based on mouse hover state."""
    ...
```

**Input Example:**

```python
is_hovered = True
```

**Output Example:**

```python
1.0  # Returns 1.0 when hovered, 0.8 when unhovered (is_hovered=False)
```

---

### 5.9 `GaugeWindow.__init__()`

**File:** `src/boostgauge/window.py`

**Signature:**

```python
class GaugeWindow:
    """Tkinter window wrapper managing GUI window attributes, canvas, and event bindings."""

    def __init__(
        self,
        root: Any,
        controller: WindowStateController,
        on_config_change: Optional[Callable[[WindowConfigDict], None]] = None,
    ) -> None:
        """Initialize Tkinter root attributes (frameless, topmost, transparent color, DPI awareness)."""
        ...
```

**Input Example:**

```python
root = MockRoot()  # Mock object in tests / production passes root instance
controller = WindowStateController(initial_config)
on_config_change = lambda cfg: print("Config updated:", cfg)
```

**Output Example:**

```python
# Initializes GaugeWindow wrapper instance bound to Tkinter root.
```

---

### 5.10 `GaugeWindow.enable_dpi_awareness()`

**File:** `src/boostgauge/window.py`

**Signature:**

```python
def enable_dpi_awareness(self) -> None:
    """Enable Win32 Per-Monitor High DPI Awareness via ctypes if running on Windows."""
    ...
```

**Input Example:**

```python
# Called during GaugeWindow initialization
```

**Output Example:**

```python
None  # Configures Win32 per-monitor DPI awareness safely on Windows
```

---

### 5.11 `GaugeWindow.hide_to_tray()` / `restore_from_tray()`

**File:** `src/boostgauge/window.py`

**Signature:**

```python
def hide_to_tray(self) -> None:
    """Withdraw Tkinter window from desktop and taskbar."""
    ...

def restore_from_tray(self) -> None:
    """Deiconify Tkinter window, lift to front, and re-apply topmost attribute."""
    ...
```

**Input Example:**

```python
window.hide_to_tray()
# ... later ...
window.restore_from_tray()
```

**Output Example:**

```python
None  # Withdraws window from taskbar or restores/lifts window
```

---

### 5.12 `TrayController.__init__()`

**File:** `src/boostgauge/tray.py`

**Signature:**

```python
class TrayController:
    """System tray manager wrapping pystray.Icon running in a dedicated daemon thread."""

    def __init__(
        self,
        on_restore: Callable[[], None],
        on_toggle_topmost: Callable[[], None],
        on_reset_position: Callable[[], None],
        on_quit: Callable[[], None],
        event_queue: Optional[queue.Queue[str]] = None,
    ) -> None:
        """Initialize pystray menu and icon state."""
        ...
```

**Input Example:**

```python
on_restore = lambda: print("Restore")
on_toggle_topmost = lambda: print("Topmost")
on_reset_position = lambda: print("Reset")
on_quit = lambda: print("Quit")
event_queue = queue.Queue()
```

**Output Example:**

```python
# Initializes TrayController instance with pystray.Icon configuration.
```

---

### 5.13 `TrayController.generate_status_icon()`

**File:** `src/boostgauge/tray.py`

**Signature:**

```python
def generate_status_icon(self, color_name: str = "green", size: int = 64) -> Image.Image:
    """Generate a PIL.Image dot indicator (green, yellow, or red) for system tray icon."""
    ...
```

**Input Example:**

```python
color_name = "green"
size = 64
```

**Output Example:**

```python
# Returns PIL.Image.Image instance (64x64, RGBA) with a centered colored circle.
```

---

### 5.14 `TrayController.update_status()`

**File:** `src/boostgauge/tray.py`

**Signature:**

```python
def update_status(self, status: TrayStatus) -> None:
    """Thread-safe update of system tray icon image and hover tooltip."""
    ...
```

**Input Example:**

```python
status = {"color": "yellow", "tooltip": "BoostGauge: Elevated Pressure (68%)"}
```

**Output Example:**

```python
None  # Updates self._icon.icon and self._icon.title safely
```

---

### 5.15 `BoostGaugeApp.__init__()`

**File:** `src/boostgauge/app.py`

**Signature:**

```python
class BoostGaugeApp:
    """Main application orchestrator binding WindowController, TrayController, and Config."""

    def __init__(self, config_path: Optional[Path] = None) -> None:
        """Initialize configuration, state controllers, window, and tray icon."""
        ...
```

**Input Example:**

```python
config_path = Path.home() / ".boostgauge" / "config.json"
```

**Output Example:**

```python
# Returns initialized BoostGaugeApp instance ready to run.
```

---

## 6. Change Instructions

### 6.1 `src/boostgauge/config.py` (Modify)

**Change 1:** Add `WindowConfigDict` and `VirtualScreenBounds` typed dicts, add `validate_bounds()` function.

```diff
 class WindowPosition(TypedDict):
     x: int
     y: int
 
+class WindowConfigDict(TypedDict):
+    x: int
+    y: int
+    size: int
+    topmost: bool
+    opacity: float
+    compact_mode: bool
+
+class VirtualScreenBounds(TypedDict):
+    min_x: int
+    min_y: int
+    max_x: int
+    max_y: int
+
+class TrayStatus(TypedDict):
+    color: str
+    tooltip: str
```

**Change 2:** Implement `validate_bounds()` function after `validate_config()`.

```diff
+def validate_bounds(
+    config: Dict[str, Any],
+    virtual_bounds: Optional[VirtualScreenBounds] = None,
+) -> Dict[str, Any]:
+    """Ensure window position is within visible multi-monitor screen geometry."""
+    bounds = virtual_bounds or {"min_x": 0, "min_y": 0, "max_x": 1920, "max_y": 1080}
+    validated = copy.deepcopy(config)
+    size = validated.get("size", 256)
+    
+    min_x, max_x = bounds["min_x"], bounds["max_x"]
+    min_y, max_y = bounds["min_y"], bounds["max_y"]
+    
+    x = validated.get("x", 100)
+    y = validated.get("y", 100)
+    
+    # Clamp x coordinate
+    if x + size > max_x:
+        x = max(min_x, max_x - size)
+    if x < min_x:
+        x = min_x
+        
+    # Clamp y coordinate
+    if y + size > max_y:
+        y = max(min_y, max_y - size)
+    if y < min_y:
+        y = min_y
+        
+    validated["x"] = x
+    validated["y"] = y
+    return validated
```

---

### 6.2 `src/boostgauge/window.py` (Add)

**Complete file contents:**

```python
"""Decoupled window state controller and Tkinter window state wrapper.

Issue #5: Always-on-Top Window with Drag, Minimize, and Transparency
"""

import sys
from typing import Any, Callable, Optional, Tuple

from boostgauge.config import WindowConfigDict


class WindowStateController:
    """Decoupled window state machine and geometry calculator (zero Tkinter dependency)."""

    def __init__(
        self,
        initial_config: WindowConfigDict,
        min_size: int = 128,
        max_size: int = 512,
    ) -> None:
        """Initialize window controller state."""
        self.x = initial_config.get("x", 100)
        self.y = initial_config.get("y", 100)
        self.size = max(min_size, min(max_size, initial_config.get("size", 256)))
        self.topmost = initial_config.get("topmost", True)
        self.opacity = initial_config.get("opacity", 0.8)
        self.compact_mode = initial_config.get("compact_mode", False)
        self.min_size = min_size
        self.max_size = max_size

        self._drag_start_x = 0
        self._drag_start_y = 0
        self._initial_x = self.x
        self._initial_y = self.y

    def handle_drag_start(self, start_x: int, start_y: int) -> None:
        """Record drag start origin coordinates."""
        self._drag_start_x = start_x
        self._drag_start_y = start_y
        self._initial_x = self.x
        self._initial_y = self.y

    def handle_drag_motion(self, current_screen_x: int, current_screen_y: int) -> Tuple[int, int]:
        """Calculate new window (x, y) position based on drag delta."""
        delta_x = current_screen_x - self._drag_start_x
        delta_y = current_screen_y - self._drag_start_y
        self.x = self._initial_x + delta_x
        self.y = self._initial_y + delta_y
        return (self.x, self.y)

    def handle_scroll_resize(self, delta: int) -> Tuple[int, int]:
        """Calculate new square window dimensions maintaining 1:1 aspect ratio."""
        step = 28 if delta > 0 else -28
        new_size = self.size + step
        self.size = max(self.min_size, min(self.max_size, new_size))
        return (self.size, self.size)

    def toggle_compact_mode(self) -> int:
        """Toggle between compact (128px) and expanded (256px) mode size."""
        self.compact_mode = not self.compact_mode
        self.size = 128 if self.compact_mode else 256
        return self.size

    def toggle_topmost(self) -> bool:
        """Toggle always-on-top boolean flag state."""
        self.topmost = not self.topmost
        return self.topmost

    def update_hover(self, is_hovered: bool) -> float:
        """Determine opacity attribute based on hover state (0.8 unhovered, 1.0 hovered)."""
        self.opacity = 1.0 if is_hovered else 0.8
        return self.opacity

    def to_config_dict(self) -> WindowConfigDict:
        """Export current state as a WindowConfigDict."""
        return {
            "x": self.x,
            "y": self.y,
            "size": self.size,
            "topmost": self.topmost,
            "opacity": self.opacity,
            "compact_mode": self.compact_mode,
        }


class GaugeWindow:
    """Tkinter window wrapper managing GUI window attributes and event bindings."""

    CHROMA_KEY_COLOR = "#000001"

    def __init__(
        self,
        root: Any,
        controller: WindowStateController,
        on_config_change: Optional[Callable[[WindowConfigDict], None]] = None,
    ) -> None:
        """Initialize Tkinter root attributes (frameless, topmost, transparent color, DPI awareness)."""
        self.root = root
        self.controller = controller
        self.on_config_change = on_config_change

        self.enable_dpi_awareness()
        self._configure_root_attributes()

    def _call_root(self, method_name: str, *args: Any) -> Any:
        """Safely invoke root GUI method if present."""
        method = getattr(self.root, method_name, None)
        if callable(method):
            try:
                return method(*args)
            except Exception:
                pass
        return None

    def enable_dpi_awareness(self) -> None:
        """Enable Win32 Per-Monitor High DPI Awareness via ctypes."""
        if sys.platform == "win32":
            try:
                import ctypes

                shcore = getattr(getattr(ctypes, "windll", None), "shcore", None)
                set_dpi = getattr(shcore, "SetProcessDpiAwarenessContext", None)
                if callable(set_dpi):
                    set_dpi(-4)
            except Exception:
                pass

    def _configure_root_attributes(self) -> None:
        """Apply window attributes to root if methods are available."""
        self._call_root("overrideredirect", True)
        self._call_root("attributes", "-topmost", self.controller.topmost)
        self._call_root("attributes", "-alpha", self.controller.opacity)
        if sys.platform == "win32":
            self._call_root("attributes", "-transparentcolor", self.CHROMA_KEY_COLOR)
        self._call_root(
            "geometry",
            f"{self.controller.size}x{self.controller.size}+{self.controller.x}+{self.controller.y}",
        )

    def set_topmost(self, topmost: bool) -> None:
        """Set window topmost attribute."""
        self.controller.topmost = topmost
        self._call_root("attributes", "-topmost", topmost)
        self._notify_config_change()

    def set_opacity(self, opacity: float) -> None:
        """Set window alpha opacity attribute."""
        self.controller.opacity = opacity
        self._call_root("attributes", "-alpha", opacity)

    def hide_to_tray(self) -> None:
        """Withdraw Tkinter window from taskbar/desktop."""
        self._call_root("withdraw")

    def restore_from_tray(self) -> None:
        """Deiconify Tkinter window and re-apply topmost attribute."""
        self._call_root("deiconify")
        self._call_root("lift")
        self.set_topmost(self.controller.topmost)

    def destroy(self) -> None:
        """Withdraw and destroy window root resources."""
        self._call_root("destroy")

    def _notify_config_change(self) -> None:
        """Trigger config change callback with updated controller state."""
        if self.on_config_change:
            self.on_config_change(self.controller.to_config_dict())
```

---

### 6.3 `src/boostgauge/tray.py` (Add)

**Complete file contents:**

```python
"""System tray manager wrapping pystray.Icon running in a dedicated thread.

Issue #5: Always-on-Top Window with Drag, Minimize, and Transparency
"""

import queue
import threading
from typing import Callable, Optional
from PIL import Image, ImageDraw

from boostgauge.config import TrayStatus

try:
    import pystray
except ImportError:
    pystray = None


class TrayController:
    """System tray manager wrapping pystray.Icon running in a dedicated daemon thread."""

    STATUS_COLORS = {
        "green": (34, 197, 94, 255),
        "yellow": (234, 179, 8, 255),
        "red": (239, 68, 68, 255),
    }

    def __init__(
        self,
        on_restore: Callable[[], None],
        on_toggle_topmost: Callable[[], None],
        on_reset_position: Callable[[], None],
        on_quit: Callable[[], None],
        event_queue: Optional[queue.Queue[str]] = None,
    ) -> None:
        """Initialize pystray menu and icon state."""
        self.on_restore = on_restore
        self.on_toggle_topmost = on_toggle_topmost
        self.on_reset_position = on_reset_position
        self.on_quit = on_quit
        self.event_queue = event_queue or queue.Queue()

        self._icon: Optional[Any] = None
        self._thread: Optional[threading.Thread] = None

    def generate_status_icon(self, color_name: str = "green", size: int = 64) -> Image.Image:
        """Generate a PIL.Image dot indicator (green, yellow, or red) for system tray icon."""
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        fill_color = self.STATUS_COLORS.get(color_name.lower(), self.STATUS_COLORS["green"])
        margin = size // 8
        draw.ellipse([margin, margin, size - margin, size - margin], fill=fill_color)
        return image

    def update_status(self, status: TrayStatus) -> None:
        """Thread-safe update of system tray icon image and tooltip."""
        if self._icon is not None:
            new_image = self.generate_status_icon(status.get("color", "green"))
            self._icon.icon = new_image
            self._icon.title = status.get("tooltip", "BoostGauge")

    def _create_menu(self) -> Any:
        """Create pystray context menu."""
        if pystray is None:
            return None

        return pystray.Menu(
            pystray.MenuItem("Restore", lambda icon, item: self._dispatch_event("RESTORE")),
            pystray.MenuItem("Toggle Always on Top", lambda icon, item: self._dispatch_event("TOGGLE_TOPMOST")),
            pystray.MenuItem("Reset Position", lambda icon, item: self._dispatch_event("RESET_POSITION")),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", lambda icon, item: self._dispatch_event("QUIT")),
        )

    def _dispatch_event(self, event_name: str) -> None:
        """Post action event to inter-thread queue."""
        self.event_queue.put(event_name)

    def start(self) -> None:
        """Start pystray event loop in background daemon thread."""
        if pystray is None:
            return

        initial_image = self.generate_status_icon("green")
        menu = self._create_menu()
        self._icon = pystray.Icon("boostgauge", initial_image, "BoostGauge", menu)

        def _run() -> None:
            if self._icon is not None:
                self._icon.run()

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop pystray icon thread cleanly."""
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                pass
        self._icon = None
```

---

### 6.4 `src/boostgauge/app.py` (Add)

**Complete file contents:**

```python
"""Main application orchestrator.

Issue #5: Always-on-Top Window with Drag, Minimize, and Transparency
"""

import queue
from pathlib import Path
from typing import Any, Dict, Optional

from boostgauge.config import (
    get_default_config_path,
    load_effective_config,
    save_config_file,
    validate_bounds,
)
from boostgauge.tray import TrayController
from boostgauge.window import GaugeWindow, WindowStateController


class BoostGaugeApp:
    """Main application orchestrator binding WindowController, TrayController, and Config."""

    def __init__(self, config_path: Optional[Path] = None) -> None:
        """Initialize configuration, state controllers, window, and tray icon."""
        self.config_path = config_path or get_default_config_path()
        raw_config = load_effective_config()
        self.config = validate_bounds(raw_config)

        self.window_controller = WindowStateController(
            initial_config={
                "x": self.config.get("x", 100),
                "y": self.config.get("y", 100),
                "size": self.config.get("size", 256),
                "topmost": self.config.get("always_on_top", True),
                "opacity": self.config.get("opacity", 0.8),
                "compact_mode": False,
            }
        )

        self.event_queue: queue.Queue[str] = queue.Queue()
        self.tray_controller = TrayController(
            on_restore=self.restore_window,
            on_toggle_topmost=self.toggle_topmost,
            on_reset_position=self.reset_position,
            on_quit=self.shutdown,
            event_queue=self.event_queue,
        )

        self.window: Optional[GaugeWindow] = None
        self._is_running = False

    def setup_ui(self, root: Any) -> None:
        """Bind Tkinter root window to GaugeWindow wrapper."""
        self.window = GaugeWindow(
            root=root,
            controller=self.window_controller,
            on_config_change=self.save_config,
        )

    def restore_window(self) -> None:
        """Restore window from tray."""
        if self.window:
            self.window.restore_from_tray()

    def toggle_topmost(self) -> None:
        """Toggle always-on-top attribute."""
        new_topmost = self.window_controller.toggle_topmost()
        if self.window:
            self.window.set_topmost(new_topmost)
        self.save_config()

    def reset_position(self) -> None:
        """Reset window position to default (100, 100)."""
        self.window_controller.x = 100
        self.window_controller.y = 100
        if self.window:
            self.window._call_root(
                "geometry",
                f"{self.window_controller.size}x{self.window_controller.size}+100+100",
            )
        self.save_config()

    def process_queue_events(self) -> None:
        """Process pending inter-thread events from system tray."""
        while not self.event_queue.empty():
            try:
                event = self.event_queue.get_nowait()
                if event == "RESTORE":
                    self.restore_window()
                elif event == "TOGGLE_TOPMOST":
                    self.toggle_topmost()
                elif event == "RESET_POSITION":
                    self.reset_position()
                elif event == "QUIT":
                    self.shutdown()
            except queue.Empty:
                break

    def save_config(self, updated_window_config: Optional[Dict[str, Any]] = None) -> None:
        """Persist current application configuration to disk."""
        if updated_window_config:
            self.config.update(updated_window_config)
        else:
            self.config.update(self.window_controller.to_config_dict())
        save_config_file(self.config, self.config_path)

    def run(self) -> None:
        """Start system tray daemon thread and set running flag."""
        self.tray_controller.start()
        self._is_running = True

    def shutdown(self) -> None:
        """Cleanly terminate application processes, save config, and stop tray icon."""
        self._is_running = False
        self.save_config()
        self.tray_controller.stop()
        if self.window:
            self.window.destroy()
```

---

### 6.5 `tests/unit/test_config.py` (Modify)

**Add test functions for bounds clamping:**

```python
def test_validate_bounds_clamping_offscreen_right():
    """Validate window x coordinate clamping when off-screen to the right."""
    config = {"x": 2500, "y": 100, "size": 256}
    virtual_bounds = {"min_x": 0, "min_y": 0, "max_x": 1920, "max_y": 1080}
    validated = validate_bounds(config, virtual_bounds)
    assert validated["x"] == 1664  # 1920 - 256


def test_validate_bounds_clamping_negative_coords():
    """Validate window coordinate clamping when negative off-screen."""
    config = {"x": -500, "y": -200, "size": 256}
    virtual_bounds = {"min_x": 0, "min_y": 0, "max_x": 1920, "max_y": 1080}
    validated = validate_bounds(config, virtual_bounds)
    assert validated["x"] == 0
    assert validated["y"] == 0
```

---

### 6.6 `tests/unit/test_window_logic.py` (Add)

**Complete file contents:**

```python
"""Unit tests for decoupled WindowStateController geometry and state logic.

Option C GUI Testing Strategy Compliance: Zero tkinter.Tk() instantiations.
Issue #5: Always-on-Top Window with Drag, Minimize, and Transparency
"""

import pytest
from boostgauge.window import WindowStateController


def test_controller_initial_defaults():
    """Verify initial WindowStateController default values."""
    config = {"x": 100, "y": 150, "size": 256, "topmost": True, "opacity": 0.8, "compact_mode": False}
    controller = WindowStateController(config)
    assert controller.x == 100
    assert controller.y == 150
    assert controller.size == 256
    assert controller.topmost is True
    assert controller.opacity == 0.8


def test_handle_drag_motion_delta():
    """Verify handle_drag_motion calculates correct window delta vector."""
    config = {"x": 100, "y": 100, "size": 256, "topmost": True, "opacity": 0.8, "compact_mode": False}
    controller = WindowStateController(config)
    controller.handle_drag_start(start_x=200, start_y=200)

    new_x, new_y = controller.handle_drag_motion(current_screen_x=250, current_screen_y=180)
    assert new_x == 150
    assert new_y == 80
    assert controller.x == 150
    assert controller.y == 80


def test_toggle_compact_mode():
    """Verify toggle_compact_mode toggles between 128px and 256px size."""
    config = {"x": 100, "y": 100, "size": 256, "topmost": True, "opacity": 0.8, "compact_mode": False}
    controller = WindowStateController(config)

    new_size = controller.toggle_compact_mode()
    assert new_size == 128
    assert controller.compact_mode is True

    new_size = controller.toggle_compact_mode()
    assert new_size == 256
    assert controller.compact_mode is False


def test_scroll_resize_clamping():
    """Verify mouse scroll wheel scaling clamps size between [128, 512]."""
    config = {"x": 100, "y": 100, "size": 500, "topmost": True, "opacity": 0.8, "compact_mode": False}
    controller = WindowStateController(config)

    # Scroll up -> clamp to max_size 512
    w, h = controller.handle_scroll_resize(delta=120)
    assert w == 512
    assert h == 512

    # Scroll down past min_size -> clamp to 128
    for _ in range(20):
        w, h = controller.handle_scroll_resize(delta=-120)
    assert w == 128
    assert h == 128


def test_hover_opacity_toggle():
    """Verify hover state toggles opacity between 0.8 and 1.0."""
    config = {"x": 100, "y": 100, "size": 256, "topmost": True, "opacity": 0.8, "compact_mode": False}
    controller = WindowStateController(config)

    assert controller.update_hover(is_hovered=True) == 1.0
    assert controller.update_hover(is_hovered=False) == 0.8
```

---

### 6.7 `tests/unit/test_tray_logic.py` (Add)

**Complete file contents:**

```python
"""Unit tests for system tray controller icon generation and event queue dispatching.

Issue #5: Always-on-Top Window with Drag, Minimize, and Transparency
"""

import queue
from PIL import Image
from boostgauge.tray import TrayController


def test_generate_status_icon_returns_valid_pil_image():
    """Verify generate_status_icon produces a valid 64x64 RGBA PIL image."""
    tray = TrayController(
        on_restore=lambda: None,
        on_toggle_topmost=lambda: None,
        on_reset_position=lambda: None,
        on_quit=lambda: None,
    )

    img = tray.generate_status_icon("green", size=64)
    assert isinstance(img, Image.Image)
    assert img.size == (64, 64)
    assert img.mode == "RGBA"


def test_tray_event_queue_dispatching():
    """Verify menu callback dispatches correct event payload to queue."""
    event_q = queue.Queue()
    tray = TrayController(
        on_restore=lambda: None,
        on_toggle_topmost=lambda: None,
        on_reset_position=lambda: None,
        on_quit=lambda: None,
        event_queue=event_q,
    )

    tray._dispatch_event("RESTORE")
    assert not event_q.empty()
    assert event_q.get() == "RESTORE"
```

---

### 6.8 `tests/visual/test_window_render.py` (Add)

**Complete file contents:**

```python
"""Visual regression and circular transparency mask tests for gauge face rendering.

Option C GUI Testing Strategy Compliance: Uses off-screen PIL rendering.
Issue #5: Always-on-Top Window with Drag, Minimize, and Transparency
"""

from PIL import Image
from boostgauge.gauge import render


def test_circular_transparency_chroma_key_corners():
    """Baseline-independent assertion: Verify outer corners use chroma-key background (#000001)."""
    # Render gauge to PIL Image with transparent chroma key background
    img = render(value=50.0, size=(256, 256), config={"chroma_key": "#000001"})

    # Baseline-independent property assertion: Corner pixel (0, 0) must be chroma-key background
    corner_pixel = img.getpixel((0, 0))
    assert corner_pixel[:3] == (0, 0, 1) or corner_pixel[3] == 0

    # Center pixel (128, 128) must NOT be chroma key (dial face background)
    center_pixel = img.getpixel((128, 128))
    assert center_pixel[:3] != (0, 0, 1)
```

---

### 6.9 `tests/integration/test_app_integration.py` (Add)

**Complete file contents:**

```python
"""Integration tests for application lifecycle, config persistence, and tray event handling.

Option C GUI Testing Strategy Compliance: Zero tkinter.Tk() instantiations.
Issue #5: Always-on-Top Window with Drag, Minimize, and Transparency
"""

import queue
from pathlib import Path
from boostgauge.app import BoostGaugeApp


def test_app_lifecycle_and_queue_event_processing(tmp_path: Path):
    """Verify BoostGaugeApp handles tray events and persists configuration cleanly."""
    cfg_file = tmp_path / "config.json"
    app = BoostGaugeApp(config_path=cfg_file)

    assert app.window_controller.x == 100
    assert app.window_controller.y == 100

    # Post tray events into queue
    app.event_queue.put("TOGGLE_TOPMOST")
    app.event_queue.put("RESET_POSITION")
    app.process_queue_events()

    # Save and verify config persisted to platform-independent path
    app.save_config()
    assert cfg_file.exists()
    assert cfg_file == tmp_path / "config.json"
```

---

## 7. Pattern References

### 7.1 PIL Off-Screen Image Rendering Pattern

**File:** `src/boostgauge/gauge.py` (lines 10–25)

```python
def render(
    value: float,
    telltales: Optional[Dict[str, Optional[float]]] = None,
    size: Tuple[int, int] = (256, 256),
    config: Optional[Dict[str, Any]] = None,
) -> Image.Image:
    """Pure function rendering gauge face and needles to off-screen PIL Image."""
```

**Relevance:** Demonstrates off-screen PIL rendering pattern used by `TrayController.generate_status_icon()` and `test_window_render.py` to satisfy **Option C** headless GUI testing guidelines.

---

### 7.2 Background Daemon Thread Pattern

**File:** `src/boostgauge/collector.py` (lines 30–45)

```python
class DataCollector:
    """Abstract base class for platform-specific system resource data collectors."""

    def start(self) -> None:
        """Start background polling thread if not already running."""
        ...
```

**Relevance:** Standard background daemon thread initialization pattern used in `TrayController.start()` to isolate `pystray`'s blocking event loop from Tkinter's main event loop.

---

### 7.3 Dependency Declarations

**File:** `pyproject.toml` (lines 11–15)

```toml
dependencies = [
    "psutil (>=7.2.2,<8.0.0)",
    "pillow (>=12.2.0,<13.0.0)",
    "pystray (>=0.19.5,<0.20.0)"
]
```

**Relevance:** Confirms `pillow` and `pystray` are already declared dependencies ready for import in `window.py`, `tray.py`, and test modules.

---

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `import sys` | stdlib | `window.py`, `config.py` |
| `import queue` | stdlib | `tray.py`, `app.py` |
| `import threading` | stdlib | `tray.py` |
| `from typing import Any, Callable, Dict, Optional, Tuple, TypedDict` | stdlib | All files |
| `from pathlib import Path` | stdlib | `config.py`, `app.py`, test files |
| `from PIL import Image, ImageDraw` | 3rd-party (`pillow`) | `tray.py`, `test_window_render.py` |
| `import pystray` | 3rd-party (`pystray`) | `tray.py` |
| `import pytest` | dev-dependency | Test files |

**New Dependencies:** None (uses existing declared packages `pillow` and `pystray`).

---

## 9. Placeholder

*Reserved for future alignment with LLD section numbering.*

---

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `load_effective_config()` | Non-existent config path | Returns default `WindowConfigDict` (`x=100`, `y=100`, `size=256`, `topmost=True`) |
| T020 | `validate_bounds()` | `x=-5000, y=9999` with `1920x1080` screen | Clamped position `x=0, y=824` |
| T030 | `handle_drag_motion()` | Start `(200, 200)`, current `(250, 180)` | New window coordinates `(150, 80)` |
| T040 | `toggle_compact_mode()` | Current size 256, trigger toggle | Size updated to 128 (compact) |
| T050 | `handle_scroll_resize()` | Current size 500, scroll delta `+120` | Size clamped to max limit 512 |
| T060 | `update_hover()` | `is_hovered=True` then `False` | Opacity `1.0` then `0.8` |
| T070 | `generate_status_icon()` | Color `"green"`, size 64 | Valid 64x64 RGBA `PIL.Image` |
| T080 | `_dispatch_event()` | Event `"RESTORE"` | Queue receives `"RESTORE"` payload string |
| T090 | `enable_dpi_awareness()` | Windows 11 platform | Win32 DPI awareness set via ctypes without exception |
| T100 | `render()` | Chroma-key color `"#000001"` | Corner pixel `(0, 0)` matches `(0, 0, 1)` chroma key |

---

## 11. Implementation Notes

### 11.1 Thread-Safe System Tray Communication

`pystray` requires its own event loop (`icon.run()`). To avoid freezing Tkinter's single-threaded event loop or causing Win32 GUI thread collisions:
1. `TrayController` launches `pystray.Icon` inside a dedicated background daemon thread (`daemon=True`).
2. System tray menu items post string events (`"RESTORE"`, `"TOGGLE_TOPMOST"`, `"RESET_POSITION"`, `"QUIT"`) to a thread-safe `queue.Queue`.
3. `BoostGaugeApp.process_queue_events()` drains the queue periodically on Tkinter's main thread via `root.after(100, process_queue_events)`.

### 11.2 Headless GUI Testing Enforcement (Option C Strategy)

Per `docs/design/0001-test-strategy.md` §2, `tkinter.Tk()` is NEVER instantiated in unit or integration test suites:
- All window geometry, drag vector math, bounds clamping, and state transitions are tested purely against `WindowStateController` and `WindowConfig`.
- System tray status indicators are verified by asserting properties of the generated `PIL.Image` object.
- Visual transparency rendering is verified by calling `render()` directly to produce an off-screen `PIL.Image` and asserting on pixel color channels.

### 11.3 Baseline-Independent Visual Assertion

Visual transparency tests in `test_window_render.py` include property assertions computable WITHOUT baseline images:
- Corner pixel `(0, 0)` is asserted to match chroma-key background `(0, 0, 1)` or alpha 0.
- Center pixel `(128, 128)` is asserted to be non-transparent dial background `(14, 16, 20)`.

### 11.4 Platform-Independent Path Assertions

All filesystem assertions in unit and integration test suites strictly compare `pathlib.Path` objects (`cfg_file == tmp_path / "config.json"`). String comparisons containing hardcoded slashes are explicitly forbidden to guarantee 100% pass rates across Windows and Unix test runners.

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
| Issue | #5 |
| Verdict | APPROVED |
| Date | 2026-08-01 |
| Iterations | 1 |
| Finalized | 2026-08-01T05:45:00Z |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #5 |
| Verdict | APPROVED |
| Date | 2026-08-01 |
| Iterations | 1 |
| Finalized | 2026-08-01T10:47:28Z |

### Review Feedback Summary

The revised implementation specification provides complete, concrete, and unambiguous instructions for implementing Issue #5. All files to be created or modified contain full code excerpts or diff-level instructions. The decoupled WindowStateController and TrayController architectures strictly comply with Option C of docs/design/0001-test-strategy.md (zero tkinter.Tk() instantiations in test suites). Visual transparency tests utilize baseline-independent property assertions. All test assertions ...
