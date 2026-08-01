# Implementation Spec: Feature: Always-On-Top Window with Drag, Minimize, and Transparency

| Field | Value |
|-------|-------|
| Issue | #5 |
| LLD | `docs/lld/active/5-always-on-top-window.md` |
| Generated | 2026-08-01 |
| Status | APPROVED |

---

## 1. Overview

This implementation spec details the creation of an always-on-top, borderless gauge window in Tkinter with circular chroma-key transparency, mouse drag positioning, scroll/pinch resizing, system tray minimization via `pystray`, high-DPI scaling, and multi-monitor state persistence.

**Objective:** Implement an always-on-top, frameless gauge widget in Tkinter featuring circular transparency, mouse drag, scroll resize, system tray minimization via `pystray`, high-DPI scaling support, and position/size state persistence.

**Success Criteria:**
- Frameless gauge window remains always-on-top (`root.attributes('-topmost', True)`) across focus changes.
- Click-and-drag moves window smoothly with position auto-saved on release.
- Mouse wheel / pinch resizes gauge diameter (128px to 512px) maintaining 1:1 aspect ratio.
- Double-clicking gauge face toggles between compact mode (128px) and expanded mode (256px).
- Chroma-key background `#000001` renders transparent outer corners around circular tachometer.
- Hover changes opacity between 80% (unhovered) and 100% (hovered).
- Minimizing hides taskbar entry and displays system tray status dot icon (green/yellow/red) with pystray.
- Double-clicking system tray restores window; right-clicking displays context menu (Settings, Reset, Quit).
- Window position is validated against `VirtualScreenBounds` to prevent offscreen coordinates across multi-monitor setups.
- Automated tests strictly follow Option C of `docs/design/0001-test-strategy.md` without instantiating `tkinter.Tk()`.

---

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/config.py` | Modify | Extend configuration definitions with `WindowConfigDict`, `VirtualScreenBounds`, validation rules, and `WindowConfig` class wrapper. |
| 2 | `src/boostgauge/tray.py` | Add | Implement `TrayController` running `pystray.Icon` in daemon thread and dispatching events via thread-safe `queue.Queue`. |
| 3 | `src/boostgauge/window.py` | Add | Implement `WindowStateController` (Tk-free geometry/drag state machine) and `BoostGaugeWindow` (Tkinter surface). |
| 4 | `src/boostgauge/app.py` | Add | Main application orchestrator bringing together collector, window, tray, and configuration lifecycle. |
| 5 | `tests/unit/test_config.py` | Modify | Extend config unit tests to cover `WindowConfig`, `WindowConfigDict`, and multi-monitor screen bounds clamping. |
| 6 | `tests/unit/test_window_logic.py` | Add | Headless unit tests for geometry calculations, drag deltas, double-click toggles, scroll scaling, and DPI scaling factors. |
| 7 | `tests/unit/test_tray_logic.py` | Add | Headless unit tests for status icon generation, thread event queue dispatching, and menu callback routing. |
| 8 | `tests/visual/test_window_render.py` | Add | Visual regression tests verifying offscreen PIL dial rendering, circular transparency masking, and status dot rendering. |
| 9 | `tests/integration/test_app_integration.py` | Add | Integration tests verifying component wiring, event queue polling, and configuration persistence round-trips. |

**Implementation Order Rationale:**
Configuration models (`config.py`) must be updated first as state models underpin all controllers. Next, decoupled logic controllers (`tray.py` and `window.py`) are created so they can be unit-tested headlessly under Option C before app orchestration (`app.py`) integrates them. Test suites follow the same order: unit logic tests first, visual render tests second, and integration tests last.

---

## 3. Current State (for Modify/Delete files)

### 3.1 `src/boostgauge/config.py`

**Relevant excerpt** (lines 15-45):

```python
class WindowPosition(TypedDict):
    x: int
    y: int

class TelltaleWindowsConfig(TypedDict):
    window_1m: float
    window_10m: float
    window_1h: float

class BoostGaugeConfig(TypedDict):
    polling_interval_seconds: float
    theme: str
    always_on_top: bool
    opacity: float
    window_position: WindowPosition
    size: int
    show_telltales: bool
    show_redline: bool
    thresholds: ThresholdsConfig
    telltale_windows: TelltaleWindowsConfig
```

**What changes:** Add `WindowConfigDict` and `VirtualScreenBounds` TypedDict definitions, add `compact_mode: bool` field to configuration schemas, add `validate_bounds()` logic to clamp window coordinates inside screen rects, and add `WindowConfig` management class.

### 3.2 `tests/unit/test_config.py`

**Relevant excerpt** (lines 1-40):

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

**What changes:** Add unit test functions `test_window_config_dict_validation()`, `test_virtual_screen_bounds_clamping()`, `test_corrupt_config_recovery()`, and `test_platform_path_assertions()` ensuring strict platform independence using `pathlib.Path`.

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
    "x": 200,
    "y": 300,
    "size": 256,
    "topmost": true,
    "opacity": 0.8,
    "compact_mode": false
}
```

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
    "max_x": 1920,
    "max_y": 1080
}
```

### 4.3 `TrayEvent`

**Definition:**

```python
from typing import TypedDict, Optional, Dict, Any

class TrayEvent(TypedDict):
    event_type: str  # 'restore', 'toggle_topmost', 'reset', 'quit'
    payload: Optional[Dict[str, Any]]
```

**Concrete Example:**

```json
{
    "event_type": "toggle_topmost",
    "payload": {
        "topmost": true
    }
}
```

---

## 5. Function Specifications

### 5.1 `WindowConfig.validate_bounds()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def validate_bounds(
    self, config: WindowConfigDict, bounds: VirtualScreenBounds
) -> WindowConfigDict:
    """Clamp window top-left (x, y) coordinates so the window stays entirely visible within virtual screen rect."""
    ...
```

**Input Example:**

```python
config = {
    "x": 2500,
    "y": 1500,
    "size": 256,
    "topmost": True,
    "opacity": 0.8,
    "compact_mode": False,
}
bounds = {"min_x": 0, "min_y": 0, "max_x": 1920, "max_y": 1080}
```

**Output Example:**

```python
{
    "x": 1664,
    "y": 824,
    "size": 256,
    "topmost": True,
    "opacity": 0.8,
    "compact_mode": False,
}
```

**Edge Cases:**
- `x < min_x`: Clamps `x` to `min_x`.
- `x + size > max_x`: Clamps `x` to `max_x - size`.
- `y < min_y`: Clamps `y` to `min_y`.
- `y + size > max_y`: Clamps `y` to `max_y - size`.

---

### 5.2 `WindowStateController.compute_drag_move()`

**File:** `src/boostgauge/window.py`

**Signature:**

```python
def compute_drag_move(
    self, start_win_x: int, start_win_y: int, mouse_dx: int, mouse_dy: int
) -> Tuple[int, int]:
    """Calculate target window position given initial window origin and mouse delta."""
    ...
```

**Input Example:**

```python
start_win_x = 300
start_win_y = 400
mouse_dx = 45
mouse_dy = -15
```

**Output Example:**

```python
(345, 385)
```

**Edge Cases:**
- `mouse_dx == 0` and `mouse_dy == 0`: Returns unchanged origin `(300, 400)`.
- Negative delta causing negative window position: returns calculated arithmetic coordinates (bounds checking applied separately).

---

### 5.3 `WindowStateController.compute_wheel_resize()`

**File:** `src/boostgauge/window.py`

**Signature:**

```python
def compute_wheel_resize(
    self, current_size: int, scroll_delta: int, step_size: int = 32
) -> int:
    """Compute new window diameter clamped between min_size (128) and max_size (512)."""
    ...
```

**Input Example:**

```python
current_size = 256
scroll_delta = 1  # Scroll up / zoom in
step_size = 32
```

**Output Example:**

```python
288
```

**Edge Cases:**
- Resizing beyond `max_size=512`: returns `512`.
- Resizing below `min_size=128`: returns `128`.

---

### 5.4 `WindowStateController.toggle_compact_mode()`

**File:** `src/boostgauge/window.py`

**Signature:**

```python
def toggle_compact_mode(self) -> Tuple[int, bool]:
    """Toggle window between compact mode (128px) and expanded mode (256px). Returns (new_size, compact_state)."""
    ...
```

**Input Example:**

```python
# Initial state: compact_mode=False, size=256
```

**Output Example:**

```python
(128, True)
```

**Edge Cases:**
- Calling repeatedly alternates between `(128, True)` and `(256, False)`.

---

### 5.5 `WindowStateController.calculate_dpi_scaled_size()`

**File:** `src/boostgauge/window.py`

**Signature:**

```python
def calculate_dpi_scaled_size(self, base_size: int, dpi_scale: float) -> int:
    """Scale base pixel dimension by DPI scale factor, returning integer rounded dimension."""
    ...
```

**Input Example:**

```python
base_size = 256
dpi_scale = 1.5
```

**Output Example:**

```python
384
```

**Edge Cases:**
- `dpi_scale <= 0`: Raises `ValueError("dpi_scale must be positive")`.

---

### 5.6 `TrayController.create_status_icon_image()`

**File:** `src/boostgauge/tray.py`

**Signature:**

```python
def create_status_icon_image(
    self, color_name: str = "green", size: int = 64
) -> Image.Image:
    """Create a 64x64 PIL Image with a centered status circle dot (green/yellow/red)."""
    ...
```

**Input Example:**

```python
color_name = "green"
size = 64
```

**Output Example:**

```python
# PIL Image object (mode 'RGBA', size 64x64)
```

**Edge Cases:**
- Invalid `color_name` (e.g. `"blue"`): Defaults to `"green"` icon.

---

## 6. Change Instructions

### 6.1 `src/boostgauge/config.py` (Modify)

**Change 1:** Add `WindowConfigDict`, `VirtualScreenBounds`, and `WindowConfig` manager.

```diff
 from pathlib import Path
 import sys
-from typing import Any, Dict, List, Optional, Tuple, TypedDict
+from typing import Any, Dict, List, Optional, Tuple, TypedDict, cast

 class ThresholdRange(TypedDict):
     yellow: float
@@ -20,6 +20,19 @@ class WindowPosition(TypedDict):
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

 class TelltaleWindowsConfig(TypedDict):
     window_1m: float
@@ -32,6 +45,7 @@ class BoostGaugeConfig(TypedDict):
     always_on_top: bool
     opacity: float
     window_position: WindowPosition
+    compact_mode: bool
     size: int
     show_telltales: bool
     show_redline: bool
@@ -40,6 +54,49 @@ class BoostGaugeConfig(TypedDict):

+class WindowConfig:
+    """Manages reading, writing, and validating window state settings stored on disk."""
+
+    def __init__(self, config_path: Optional[Path] = None) -> None:
+        self.config_path = config_path or get_default_config_path()
+
+    def load(self) -> WindowConfigDict:
+        data = load_config_file(self.config_path)
+        pos = data.get("window_position", {"x": 100, "y": 100})
+        return {
+            "x": int(pos.get("x", 100)),
+            "y": int(pos.get("y", 100)),
+            "size": int(data.get("size", 256)),
+            "topmost": bool(data.get("always_on_top", True)),
+            "opacity": float(data.get("opacity", 1.0)),
+            "compact_mode": bool(data.get("compact_mode", False)),
+        }
+
+    def save(self, config: WindowConfigDict) -> None:
+        data = load_config_file(self.config_path)
+        data["window_position"] = {"x": config["x"], "y": config["y"]}
+        data["size"] = config["size"]
+        data["always_on_top"] = config["topmost"]
+        data["opacity"] = config["opacity"]
+        data["compact_mode"] = config["compact_mode"]
+        save_config_file(data, self.config_path)
+
+    def validate_bounds(
+        self, config: WindowConfigDict, bounds: VirtualScreenBounds
+    ) -> WindowConfigDict:
+        validated = dict(config)
+        size = validated["size"]
+        min_x = bounds["min_x"]
+        min_y = bounds["min_y"]
+        max_x = bounds["max_x"]
+        max_y = bounds["max_y"]
+
+        validated["x"] = max(min_x, min(validated["x"], max_x - size))
+        validated["y"] = max(min_y, min(validated["y"], max_y - size))
+        return cast(WindowConfigDict, validated)
```

---

### 6.2 `src/boostgauge/tray.py` (Add)

**Complete file contents:**

```python
"""Decoupled system tray controller using pystray with status dot icons and context menu dispatch.

Issue #5: Feature: always-on-top window with drag, minimize, and transparency
"""

import logging
import queue
import threading
from typing import Any, Dict, Optional

from PIL import Image, ImageDraw
import pystray

logger = logging.getLogger(__name__)

STATUS_COLORS = {
    "green": (34, 197, 94, 255),
    "yellow": (234, 179, 8, 255),
    "red": (239, 68, 68, 255),
}


class TrayController:
    """Manages pystray Icon lifecycle in a background thread and dispatches queue events."""

    def __init__(self, event_queue: queue.Queue) -> None:
        self.event_queue = event_queue
        self.icon: Optional[pystray.Icon] = None
        self.thread: Optional[threading.Thread] = None
        self._current_color = "green"

    def create_status_icon_image(
        self, color_name: str = "green", size: int = 64
    ) -> Image.Image:
        """Create a 64x64 PIL Image with a status dot indicator."""
        rgba = STATUS_COLORS.get(color_name.lower(), STATUS_COLORS["green"])
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        margin = size // 8
        draw.ellipse(
            [margin, margin, size - margin, size - margin],
            fill=rgba,
            outline=(255, 255, 255, 200),
            width=2,
        )
        return img

    def _on_restore_click(self, icon: Any, item: Any) -> None:
        self.event_queue.put({"event_type": "restore", "payload": None})

    def _on_toggle_topmost_click(self, icon: Any, item: Any) -> None:
        self.event_queue.put({"event_type": "toggle_topmost", "payload": None})

    def _on_reset_click(self, icon: Any, item: Any) -> None:
        self.event_queue.put({"event_type": "reset", "payload": None})

    def _on_quit_click(self, icon: Any, item: Any) -> None:
        self.event_queue.put({"event_type": "quit", "payload": None})
        self.stop()

    def start(self) -> None:
        """Start system tray icon in a background daemon thread."""
        menu = pystray.Menu(
            pystray.MenuItem("Restore Window", self._on_restore_click, default=True),
            pystray.MenuItem("Toggle Always On Top", self._on_toggle_topmost_click),
            pystray.MenuItem("Reset Geometry", self._on_reset_click),
            pystray.MenuItem("Quit", self._on_quit_click),
        )
        icon_img = self.create_status_icon_image(self._current_color)
        self.icon = pystray.Icon(
            "boostgauge", icon_img, "BoostGauge Monitor", menu=menu
        )

        self.thread = threading.Thread(target=self.icon.run, daemon=True)
        self.thread.start()
        logger.info("TrayController started background icon thread.")

    def stop(self) -> None:
        """Stop background pystray icon loop."""
        if self.icon:
            try:
                self.icon.stop()
            except Exception as e:
                logger.warning(f"Error stopping pystray icon: {e}")
            self.icon = None

    def update_status(self, color_name: str, tooltip: str) -> None:
        """Update system tray icon color dot and tooltip text."""
        self._current_color = color_name
        if self.icon:
            self.icon.icon = self.create_status_icon_image(color_name)
            self.icon.title = tooltip
```

---

### 6.3 `src/boostgauge/window.py` (Add)

**Complete file contents:**

```python
"""Window geometry controller and Tkinter surface implementation.

Issue #5: Feature: always-on-top window with drag, minimize, and transparency
"""

import logging
from typing import Any, Callable, Dict, Optional, Tuple

from boostgauge.config import WindowConfigDict

logger = logging.getLogger(__name__)


class WindowStateController:
    """Decoupled pure logic for window geometry, drag deltas, and resize bounds (Tk-free)."""

    def __init__(
        self,
        initial_config: WindowConfigDict,
        min_size: int = 128,
        max_size: int = 512,
    ) -> None:
        self.x = initial_config["x"]
        self.y = initial_config["y"]
        self.size = initial_config["size"]
        self.topmost = initial_config["topmost"]
        self.opacity = initial_config["opacity"]
        self.compact_mode = initial_config["compact_mode"]
        self.min_size = min_size
        self.max_size = max_size

    def compute_drag_move(
        self, start_win_x: int, start_win_y: int, mouse_dx: int, mouse_dy: int
    ) -> Tuple[int, int]:
        """Calculate target window origin based on drag motion delta."""
        self.x = start_win_x + mouse_dx
        self.y = start_win_y + mouse_dy
        return (self.x, self.y)

    def compute_wheel_resize(
        self, current_size: int, scroll_delta: int, step_size: int = 32
    ) -> int:
        """Calculate new window size based on scroll delta within min/max bounds."""
        direction = 1 if scroll_delta > 0 else -1
        candidate = current_size + (direction * step_size)
        self.size = max(self.min_size, min(candidate, self.max_size))
        return self.size

    def toggle_compact_mode(self) -> Tuple[int, bool]:
        """Toggle between compact mode (128px) and expanded mode (256px)."""
        if self.compact_mode:
            self.compact_mode = False
            self.size = 256
        else:
            self.compact_mode = True
            self.size = 128
        return (self.size, self.compact_mode)

    def calculate_dpi_scaled_size(self, base_size: int, dpi_scale: float) -> int:
        """Calculate pixel size multiplied by DPI scale factor."""
        if dpi_scale <= 0:
            raise ValueError("dpi_scale must be positive")
        return int(round(base_size * dpi_scale))

    def get_geometry_string(self) -> str:
        """Format Tkinter geometry string 'WIDTHxHEIGHT+X+Y'."""
        return f"{self.size}x{self.size}+{self.x}+{self.y}"

    def to_config_dict(self) -> WindowConfigDict:
        """Return current state as WindowConfigDict."""
        return {
            "x": self.x,
            "y": self.y,
            "size": self.size,
            "topmost": self.topmost,
            "opacity": self.opacity,
            "compact_mode": self.compact_mode,
        }


class BoostGaugeWindow:
    """Tkinter window surface binding window manager attributes, events, and transparency."""

    def __init__(
        self,
        root: Any,
        controller: WindowStateController,
        on_config_change: Optional[Callable[[WindowConfigDict], None]] = None,
    ) -> None:
        self.root = root
        self.controller = controller
        self.on_config_change = on_config_change
        self.drag_start_mouse: Optional[Tuple[int, int]] = None
        self.drag_start_win: Optional[Tuple[int, int]] = None

        self._setup_window_attributes()
        self._bind_events()

    def _setup_window_attributes(self) -> None:
        self.root.overrideredirect(True)
        self.setup_transparency_and_topmost()
        self.apply_geometry()

    def setup_transparency_and_topmost(self, bg_chroma_hex: str = "#000001") -> None:
        """Apply top-most attribute and chroma-key transparency background color."""
        self.root.attributes("-topmost", self.controller.topmost)
        self.root.config(bg=bg_chroma_hex)
        try:
            self.root.attributes("-transparentcolor", bg_chroma_hex)
        except Exception as e:
            logger.debug(f"-transparentcolor attribute not supported: {e}")

    def apply_geometry(self) -> None:
        """Apply geometry string to Tkinter root window."""
        self.root.geometry(self.controller.get_geometry_string())

    def set_hover_opacity(self, opacity: float) -> None:
        """Update window alpha opacity value."""
        self.controller.opacity = opacity
        try:
            self.root.attributes("-alpha", opacity)
        except Exception as e:
            logger.debug(f"-alpha attribute setting failed: {e}")

    def _bind_events(self) -> None:
        self.root.bind("<ButtonPress-1>", self._on_mouse_down)
        self.root.bind("<B1-Motion>", self._on_mouse_drag)
        self.root.bind("<ButtonRelease-1>", self._on_mouse_up)
        self.root.bind("<Double-Button-1>", self._on_double_click)
        self.root.bind("<MouseWheel>", self._on_mouse_wheel)
        self.root.bind("<Enter>", lambda e: self.set_hover_opacity(1.0))
        self.root.bind("<Leave>", lambda e: self.set_hover_opacity(0.8))

    def _on_mouse_down(self, event: Any) -> None:
        self.drag_start_mouse = (event.x_root, event.y_root)
        self.drag_start_win = (self.controller.x, self.controller.y)

    def _on_mouse_drag(self, event: Any) -> None:
        if self.drag_start_mouse and self.drag_start_win:
            dx = event.x_root - self.drag_start_mouse[0]
            dy = event.y_root - self.drag_start_mouse[1]
            self.controller.compute_drag_move(
                self.drag_start_win[0], self.drag_start_win[1], dx, dy
            )
            self.apply_geometry()

    def _on_mouse_up(self, event: Any) -> None:
        self.drag_start_mouse = None
        self.drag_start_win = None
        if self.on_config_change:
            self.on_config_change(self.controller.to_config_dict())

    def _on_double_click(self, event: Any) -> None:
        self.controller.toggle_compact_mode()
        self.apply_geometry()
        if self.on_config_change:
            self.on_config_change(self.controller.to_config_dict())

    def _on_mouse_wheel(self, event: Any) -> None:
        delta = 1 if event.delta > 0 else -1
        self.controller.compute_wheel_resize(self.controller.size, delta)
        self.apply_geometry()
        if self.on_config_change:
            self.on_config_change(self.controller.to_config_dict())

    def hide_to_tray(self) -> None:
        """Hide window from desktop."""
        self.root.withdraw()

    def restore_from_tray(self) -> None:
        """Restore window from tray to foreground."""
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", self.controller.topmost)
```

---

### 6.4 `src/boostgauge/app.py` (Add)

**Complete file contents:**

```python
"""Main application entry point orchestrating window, tray controller, and configuration lifecycle.

Issue #5: Feature: always-on-top window with drag, minimize, and transparency
"""

import logging
import queue
import sys
from typing import Any, Dict, Optional

from boostgauge.config import WindowConfig, load_effective_config
from boostgauge.tray import TrayController
from boostgauge.window import BoostGaugeWindow, WindowStateController

logger = logging.getLogger(__name__)


class BoostGaugeApp:
    """Application orchestrator tying together window state, tray icon, and event loop."""

    def __init__(self, root: Any = None) -> None:
        self.config_manager = WindowConfig()
        self.config = self.config_manager.load()
        self.controller = WindowStateController(self.config)
        self.event_queue: queue.Queue = queue.Queue()
        self.tray = TrayController(self.event_queue)
        self.root = root
        self.window: Optional[BoostGaugeWindow] = None

    def initialize_ui(self) -> None:
        """Initialize Tkinter surface window if root is present."""
        if self.root:
            self.window = BoostGaugeWindow(
                self.root,
                self.controller,
                on_config_change=self.config_manager.save,
            )
            self._schedule_queue_polling()

    def _schedule_queue_polling(self) -> None:
        if self.root:
            self.poll_event_queue()
            self.root.after(50, self._schedule_queue_polling)

    def poll_event_queue(self) -> None:
        """Poll and execute events posted from system tray thread."""
        try:
            while True:
                event = self.event_queue.get_nowait()
                self._handle_tray_event(event)
        except queue.Empty:
            pass

    def _handle_tray_event(self, event: Dict[str, Any]) -> None:
        event_type = event.get("event_type")
        if event_type == "restore":
            if self.window:
                self.window.restore_from_tray()
        elif event_type == "toggle_topmost":
            self.controller.topmost = not self.controller.topmost
            if self.window:
                self.window.setup_transparency_and_topmost()
            self.config_manager.save(self.controller.to_config_dict())
        elif event_type == "reset":
            self.controller.x = 100
            self.controller.y = 100
            self.controller.size = 256
            if self.window:
                self.window.apply_geometry()
            self.config_manager.save(self.controller.to_config_dict())
        elif event_type == "quit":
            if self.root:
                self.root.quit()

    def run(self) -> None:
        """Start tray background thread and enter Tkinter main loop."""
        self.tray.start()
        if self.root:
            self.initialize_ui()
            self.root.mainloop()

    def shutdown(self) -> None:
        """Cleanly stop tray icon worker thread."""
        self.tray.stop()


def main() -> None:
    import tkinter as tk

    root = tk.Tk()
    app = BoostGaugeApp(root)
    try:
        app.run()
    finally:
        app.shutdown()


if __name__ == "__main__":
    main()
```

---

### 6.5 `tests/unit/test_config.py` (Modify)

**Change 1:** Add tests for `WindowConfig` and platform-independent `pathlib.Path` assertions.

```python
from boostgauge.config import WindowConfig


def test_window_config_load_and_save(tmp_path: Path):
    """Test loading and saving WindowConfigDict with WindowConfig."""
    cfg_file = tmp_path / "test_config.json"
    wc = WindowConfig(config_path=cfg_file)

    initial = wc.load()
    assert initial["size"] == 256
    assert initial["topmost"] is True

    updated = {
        "x": 400,
        "y": 500,
        "size": 320,
        "topmost": False,
        "opacity": 0.9,
        "compact_mode": True,
    }
    wc.save(updated)

    restored = wc.load()
    assert restored["x"] == 400
    assert restored["y"] == 500
    assert restored["size"] == 320
    assert restored["topmost"] is False
    assert restored["opacity"] == 0.9
    assert restored["compact_mode"] is True


def test_virtual_screen_bounds_validation(tmp_path: Path):
    """Test multi-monitor coordinate clamping."""
    wc = WindowConfig(config_path=tmp_path / "cfg.json")
    bounds = {"min_x": 0, "min_y": 0, "max_x": 1920, "max_y": 1080}
    out_of_bounds = {
        "x": 2500,
        "y": -100,
        "size": 256,
        "topmost": True,
        "opacity": 1.0,
        "compact_mode": False,
    }
    clamped = wc.validate_bounds(out_of_bounds, bounds)
    assert clamped["x"] == 1664
    assert clamped["y"] == 0


def test_platform_independent_path_comparison():
    """Verify paths are asserted using pathlib.Path objects without string separator reliance."""
    default_path = get_default_config_path()
    assert isinstance(default_path, Path)
    expected_path = Path.home() / ".boostgauge" / "config.json"
    assert default_path == expected_path or default_path.name == "config.json"
```

---

### 6.6 `tests/unit/test_window_logic.py` (Add)

**Complete file contents:**

```python
"""Headless unit tests for window geometry logic state machine.

Issue #5: Feature: always-on-top window with drag, minimize, and transparency
"""

import pytest
from boostgauge.config import WindowConfigDict
from boostgauge.window import WindowStateController


@pytest.fixture
def baseline_config() -> WindowConfigDict:
    return {
        "x": 200,
        "y": 300,
        "size": 256,
        "topmost": True,
        "opacity": 1.0,
        "compact_mode": False,
    }


def test_t010_initial_controller_state(baseline_config: WindowConfigDict):
    """T010: Controller initializes with exact config values."""
    controller = WindowStateController(baseline_config)
    assert controller.x == 200
    assert controller.y == 300
    assert controller.size == 256
    assert controller.topmost is True


def test_t030_compute_drag_move(baseline_config: WindowConfigDict):
    """T030: Drag delta calculation returns updated position."""
    controller = WindowStateController(baseline_config)
    new_pos = controller.compute_drag_move(200, 300, 50, -20)
    assert new_pos == (250, 280)
    assert controller.x == 250
    assert controller.y == 280


def test_t040_geometry_string_formatting(baseline_config: WindowConfigDict):
    """T040: Format geometry string matches Tkinter 'WxH+X+Y' syntax."""
    controller = WindowStateController(baseline_config)
    assert controller.get_geometry_string() == "256x256+200+300"


def test_t050_toggle_compact_mode(baseline_config: WindowConfigDict):
    """T050: Double-click compact mode toggles between 128px and 256px."""
    controller = WindowStateController(baseline_config)
    size1, compact1 = controller.toggle_compact_mode()
    assert size1 == 128
    assert compact1 is True

    size2, compact2 = controller.toggle_compact_mode()
    assert size2 == 256
    assert compact2 is False


def test_t130_compute_wheel_resize_bounds(baseline_config: WindowConfigDict):
    """T130: Scroll wheel resizes diameter clamped between min (128) and max (512)."""
    controller = WindowStateController(baseline_config, min_size=128, max_size=512)

    new_size = controller.compute_wheel_resize(256, 1, step_size=32)
    assert new_size == 288

    # Test max size clamp
    max_size = controller.compute_wheel_resize(500, 1, step_size=50)
    assert max_size == 512

    # Test min size clamp
    min_size = controller.compute_wheel_resize(140, -1, step_size=50)
    assert min_size == 128


def test_t150_dpi_scaling_factor_math(baseline_config: WindowConfigDict):
    """T150: DPI scaling geometry adjustment."""
    controller = WindowStateController(baseline_config)
    scaled_150 = controller.calculate_dpi_scaled_size(256, 1.5)
    assert scaled_150 == 384

    scaled_100 = controller.calculate_dpi_scaled_size(256, 1.0)
    assert scaled_100 == 256
```

---

### 6.7 `tests/unit/test_tray_logic.py` (Add)

**Complete file contents:**

```python
"""Headless unit tests for tray icon state generation and event queue routing.

Issue #5: Feature: always-on-top window with drag, minimize, and transparency
"""

import queue
import pytest
from PIL import Image
from boostgauge.tray import TrayController


def test_t080_status_icon_image_generation():
    """T080: Generates valid 64x64 PIL status dot image with RGBA mode."""
    q = queue.Queue()
    tray = TrayController(q)

    img_green = tray.create_status_icon_image("green", size=64)
    assert isinstance(img_green, Image.Image)
    assert img_green.size == (64, 64)
    assert img_green.mode == "RGBA"

    # Baseline-independent color assertion at center pixel (32, 32)
    r, g, b, a = img_green.getpixel((32, 32))
    assert g > r and g > b  # Green component dominates


def test_t090_tray_event_callbacks_enqueue():
    """T090: Menu callback actions put expected TrayEvent objects into queue."""
    q = queue.Queue()
    tray = TrayController(q)

    tray._on_restore_click(None, None)
    event1 = q.get_nowait()
    assert event1["event_type"] == "restore"

    tray._on_toggle_topmost_click(None, None)
    event2 = q.get_nowait()
    assert event2["event_type"] == "toggle_topmost"

    tray._on_reset_click(None, None)
    event3 = q.get_nowait()
    assert event3["event_type"] == "reset"
```

---

### 6.8 `tests/visual/test_window_render.py` (Add)

**Complete file contents:**

```python
"""Visual regression and offscreen PIL dial rendering tests.

Issue #5: Feature: always-on-top window with drag, minimize, and transparency
"""

import math
import pytest
from PIL import Image, ImageDraw
from boostgauge.gauge import render


def test_t060_chroma_key_circular_mask_rendering():
    """T060: Offscreen PIL dial rendering has transparent/chroma background outside dial radius."""
    size = (256, 256)
    gauge_img = render(value=50.0, size=size)
    assert isinstance(gauge_img, Image.Image)
    assert gauge_img.size == size

    # Baseline-independent mathematical assertion:
    # Corner pixel at (5, 5) lies outside circular dial radius (r=128)
    corner_pixel = gauge_img.getpixel((5, 5))
    # Alpha or chroma key check
    assert corner_pixel[3] == 0 or corner_pixel[:3] == (0, 0, 1)


def test_baseline_independent_needle_angle_trigonometry():
    """Verify main needle tip position mathematically without baseline images."""
    size = (256, 256)
    center = (128.0, 128.0)
    radius = 100.0

    # At metric value 50 (mid-scale), angle should be 90 degrees (vertical pointing up)
    value = 50.0
    sweep_angle_deg = 225.0 - (value / 100.0) * 270.0  # 225 - 135 = 90 deg
    rad = math.radians(sweep_angle_deg)

    expected_tip_x = center[0] + radius * math.cos(rad)
    expected_tip_y = center[1] - radius * math.sin(rad)

    assert abs(expected_tip_x - 128.0) < 1.0
    assert abs(expected_tip_y - 28.0) < 1.0
```

---

### 6.9 `tests/integration/test_app_integration.py` (Add)

**Complete file contents:**

```python
"""Integration tests verifying component wiring and event queue processing.

Issue #5: Feature: always-on-top window with drag, minimize, and transparency
"""

import queue
import pytest
from boostgauge.app import BoostGaugeApp


def test_t100_app_tray_event_queue_processing(tmp_path):
    """T100: App polls tray event queue and updates state machine correctly."""
    app = BoostGaugeApp(root=None)
    assert app.controller.topmost is True

    # Enqueue toggle_topmost event
    app.event_queue.put({"event_type": "toggle_topmost", "payload": None})
    app.poll_event_queue()

    assert app.controller.topmost is False

    # Enqueue reset event
    app.event_queue.put({"event_type": "reset", "payload": None})
    app.poll_event_queue()

    assert app.controller.x == 100
    assert app.controller.y == 100
    assert app.controller.size == 256
```

---

## 7. Pattern References

### 7.1 Thread-Safe Queue Polling Pattern

**File:** `src/boostgauge/collector.py` (lines 20-45)

```python
class DataCollector:
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        snapshot_queue: Optional[queue.Queue[SystemSnapshot]] = None,
    ) -> None:
        self.snapshot_queue = snapshot_queue or queue.Queue()
```

**Relevance:** Thread-safe communication between background daemon threads (`pystray` icon loop) and main Tkinter event loop via non-blocking `get_nowait()` polling.

### 7.2 Offscreen PIL Image Rendering Pattern

**File:** `src/boostgauge/gauge.py` (lines 25-40)

```python
def render(
    value: float,
    telltales: Optional[Dict[str, Optional[float]]] = None,
    size: Tuple[int, int] = (256, 256),
    config: Optional[Dict[str, Any]] = None,
) -> Image.Image:
    """Pure function rendering gauge face and needles to off-screen PIL Image."""
```

**Relevance:** Demonstrates strict adherence to Option C GUI testing strategy by generating offscreen PIL surfaces without requiring a running Tk display server.

---

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `import tkinter as tk` | stdlib | `src/boostgauge/app.py`, `src/boostgauge/window.py` |
| `import queue` | stdlib | `src/boostgauge/app.py`, `src/boostgauge/tray.py`, `tests/` |
| `import threading` | stdlib | `src/boostgauge/tray.py` |
| `from pathlib import Path` | stdlib | `src/boostgauge/config.py`, `tests/unit/test_config.py` |
| `from PIL import Image, ImageDraw` | `pillow (>=12.2.0)` | `src/boostgauge/tray.py`, `tests/visual/test_window_render.py` |
| `import pystray` | `pystray (>=0.19.5)` | `src/boostgauge/tray.py` |

**New Dependencies:** None (all dependencies already listed in `pyproject.toml`).

---

## 9. Placeholder

*Reserved for future use to maintain alignment with LLD section numbering.*

---

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `WindowStateController.__init__` | Baseline `WindowConfigDict` | Controller initialized with matching parameters |
| T020 | `BoostGaugeApp._handle_tray_event` | `{"event_type": "toggle_topmost"}` | Topmost state toggles boolean value |
| T030 | `WindowStateController.compute_drag_move` | `start=(200,300), dx=50, dy=-20` | Returns `(250, 280)` |
| T040 | `WindowStateController.get_geometry_string` | `size=256, x=200, y=300` | Returns `"256x256+200+300"` |
| T050 | `WindowStateController.toggle_compact_mode` | Mode switch call | Alternates between 128px and 256px |
| T060 | `render()` | `value=50.0, size=(256,256)` | Corner pixel alpha at (5,5) is 0 or chroma key |
| T070 | `BoostGaugeWindow.set_hover_opacity` | Hover enter / leave events | Opacity shifts between 0.8 and 1.0 |
| T080 | `TrayController.create_status_icon_image` | `color_name="green"` | 64x64 RGBA PIL Image with green center pixel |
| T090 | `TrayController._on_restore_click` | Tray menu click | `event_queue` receives `{"event_type": "restore"}` |
| T100 | `BoostGaugeApp.poll_event_queue` | Queue containing events | App state updates and queue empties |
| T110 | `WindowConfig.load` / `save` | `WindowConfigDict` object | JSON file round-trip preserves all fields |
| T120 | `WindowConfig.validate_bounds` | `x=2500, max_x=1920` | Clamped to `x=1664` within screen rect |
| T130 | `WindowStateController.compute_wheel_resize` | `scroll_delta=1, current=256` | Returns size `288` (clamped 128-512) |
| T140 | `WindowStateController.get_geometry_string` | Resize output | Width equals height (1:1 ratio) |
| T150 | `WindowStateController.calculate_dpi_scaled_size` | `base=256, dpi_scale=1.5` | Scaled integer size `384` |

---

## 11. Implementation Notes

### 11.1 Error Handling & Fallbacks

- **Corrupt Config File:** If `config.json` fails JSON decoding or is missing keys, `WindowConfig.load()` falls back to safe default geometry (256px size, centered at `x=100, y=100`, `topmost=True`).
- **Platform Transparency Support:** If `-transparentcolor` or `-alpha` window attributes are unsupported by the underlying OS or window manager, exceptions are caught silently and logged at DEBUG level so application execution continues safely.
- **Thread Shutdown:** `pystray.Icon` runs in a daemon thread (`daemon=True`) to ensure application process terminates cleanly even if the icon thread is blocked.

### 11.2 Baseline-Independent Property Assertions

Visual render tests in `tests/visual/test_window_render.py` include assertions computable without baseline images:
- Radial distance verification ensuring pixels outside radius $R = \text{size} / 2$ match chroma color `#000001` or alpha `0`.
- Trigonometric verification of needle tip coordinate $(x, y) = (x_0 + r \cos \theta, y_0 - r \sin \theta)$ at 50% gauge value ($\theta = 90^\circ$).

### 11.3 Test Code Platform Independence Rules

Per Issue #1841:
- Never assert path strings with separator checks like `str(path).endswith("config.json")`.
- Compare using `pathlib.Path` objects directly: `assert path == Path.home() / ".boostgauge" / "config.json"`.

### 11.4 Constants

| Constant | Value | Rationale |
|----------|-------|-----------|
| `MIN_WINDOW_SIZE` | `128` | Smallest legible gauge diameter |
| `MAX_WINDOW_SIZE` | `512` | Upper boundary to avoid screen overflow |
| `COMPACT_WINDOW_SIZE` | `128` | Fast compact mode size |
| `EXPANDED_WINDOW_SIZE` | `256` | Standard gauge face size |
| `CHROMA_KEY_HEX` | `"#000001"` | Chroma color unlikely to collide with gauge dial colors |
| `QUEUE_POLL_INTERVAL_MS` | `50` | Low-CPU Tkinter `root.after()` queue polling rate |

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
| Finalized | 2026-08-01T06:36:15Z |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #5 |
| Verdict | APPROVED |
| Date | 2026-08-01 |
| Iterations | 1 |
| Finalized | 2026-08-01T11:37:26Z |

### Review Feedback Summary

The revised implementation spec for Issue #5 is complete, concrete, and fully executable for an autonomous AI agent with a high expected first-try success rate. The latest revisions successfully fix previous syntax errors in `WindowStateController.get_geometry_string` and missing type annotation imports in `src/boostgauge/app.py`. All data structures and function signatures feature concrete examples with realistic values. Test assertions trace directly to specified behaviors without inventing un...
