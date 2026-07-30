# Implementation Spec: #5 - Always-on-Top Window with Drag, Minimize, and Transparency

| Field | Value |
|-------|-------|
| Issue | #5 |
| LLD | `docs/lld/active/0005-always-on-top-window-drag-minimize-transparency.md` |
| Generated | 2026-07-30 |
| Status | APPROVED |

---

## 1. Overview

This implementation provides a frameless, always-on-top, draggable, transparent Tkinter host window (`GaugeWindow`) and system tray integration (`TrayManager` via `pystray`) for BoostGauge. The window supports mouse wheel resizing, double-click compact mode toggling, opacity transitions on mouse hover, off-screen geometry clamping, and state persistence to configuration.

**Objective:** Implement an always-on-top, frameless, draggable, and transparent Tkinter window for BoostGauge with system tray minimization, opacity state transitions, mouse wheel resizing, and geometry persistence.

**Success Criteria:**
- Window geometry and topmost state initialized from `GaugeConfigDict` and persisted on drag/resize.
- Color-key background transparency (`#010101`) and idle (0.8) / hover (1.0) alpha transitions.
- Pystray system tray icon displaying dynamic 16x16 status dots (`green`, `yellow`, `red`) in a daemon thread.
- Pure mathematical and image utility functions decoupled from `tkinter.Tk()` initialization to support Option C test execution.

---

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/window.py` | Add | Core window controller (`GaugeWindow`), tray manager (`TrayManager`), and pure math/image helpers (`clamp_window_position`, `calculate_next_size`, `create_tray_indicator_image`) |
| 2 | `src/boostgauge/app.py` | Modify | Integrate `GaugeWindow` lifecycle, system tray polling/mainloop, and position/size state saving on application exit |
| 3 | `src/boostgauge/__init__.py` | Modify | Export `GaugeWindow`, `TrayManager`, and window utility functions in top-level package API exports |
| 4 | `tests/unit/test_window.py` | Add | Unit test suite for geometry clamping, resize calculation, tray dot rendering, state transition logic, and event handling |

**Implementation Order Rationale:**
1. `window.py` contains core window, tray, and pure function logic needed by `app.py` and unit tests.
2. `app.py` integrates `window.py` into application runtime.
3. `__init__.py` exposes public exports after implementation files exist.
4. `test_window.py` tests all public interfaces and pure math/PIL routines.

---

## 3. Current State (for Modify/Delete files)

### 3.1 `src/boostgauge/app.py`

**Relevant excerpt** (lines 1–47):

```python
"""Application runtime controller integrating configuration lifecycle.

Issue #7: Configuration File and CLI Arguments
"""

from __future__ import annotations

import sys

from typing import Optional

from boostgauge.config import (
    ConfigError,
    apply_cli_overrides,
    get_default_config,
    get_default_config_path,
    load_config,
    parse_cli_args,
    save_config,
    validate_config,
)


def main(args: Optional[list[str]] = None) -> int:
    """Execute main application startup sequence and configuration lifecycle."""
    try:
        parsed_args = parse_cli_args(args)
        target_config_path = parsed_args.config if parsed_args.config else get_default_config_path()

        if parsed_args.reset_config:
            default_config = get_default_config()
            save_config(default_config, target_config_path)
            config = default_config
        else:
            config = load_config(target_config_path)

        config = apply_cli_overrides(config, parsed_args)
        config = validate_config(config)

        return 0

    except ConfigError as exc:
        print(f"BoostGauge Configuration Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

**What changes:** Instantiate `GaugeWindow(config)` after configuration loading/validation, attach tray icon and metric loop callbacks, start Tkinter main loop (`window.run()`), and persist updated position/size via `save_config` upon closing.

### 3.2 `src/boostgauge/__init__.py`

**Relevant excerpt** (lines 1–19):

```python
"""BoostGauge package initialization.

Issue #7: Configuration File and CLI Arguments
"""

from boostgauge.collector import DataCollector, SystemSnapshot
from boostgauge.collectors import WindowsCollector, create_collector
from boostgauge.telltale import TelltaleManager

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "DataCollector",
    "SystemSnapshot",
    "TelltaleManager",
    "WindowsCollector",
    "create_collector",
]
```

**What changes:** Import `GaugeWindow`, `TrayManager`, `clamp_window_position`, `calculate_next_size`, and `create_tray_indicator_image` from `boostgauge.window` and add them to `__all__`.

---

## 4. Data Structures

### 4.1 `WindowStateDict`

**Definition:**

```python
from typing import TypedDict

class WindowStateDict(TypedDict):
    x: int
    y: int
    size: int
    topmost: bool
    opacity: float
    is_compact: bool
    is_minimized: bool
```

**Concrete Example:**

```json
{
    "x": 350,
    "y": 120,
    "size": 256,
    "topmost": true,
    "opacity": 0.8,
    "is_compact": false,
    "is_minimized": false
}
```

### 4.2 `TrayMenuCallbacks`

**Definition:**

```python
from typing import Callable, TypedDict

class TrayMenuCallbacks(TypedDict):
    on_toggle_topmost: Callable[[], None]
    on_reset_telltales: Callable[[], None]
    on_restore: Callable[[], None]
    on_quit: Callable[[], None]
```

**Concrete Example:**

```python
callbacks = {
    "on_toggle_topmost": lambda: print("Toggle topmost"),
    "on_reset_telltales": lambda: print("Reset telltales"),
    "on_restore": lambda: print("Restore window"),
    "on_quit": lambda: print("Quit app"),
}
```

---

## 5. Function Specifications

### 5.1 `clamp_window_position()`

**File:** `src/boostgauge/window.py`

**Signature:**

```python
def clamp_window_position(
    x: int,
    y: int,
    size: int,
    virtual_screen_bounds: tuple[int, int, int, int] = (0, 0, 1920, 1080),
) -> tuple[int, int]:
    """Clamp window top-left coordinates to keep gauge visible within target screen work area bounds."""
    ...
```

**Input Example:**

```python
x = -150
y = 1000
size = 256
virtual_screen_bounds = (0, 0, 1920, 1080)
```

**Output Example:**

```python
(0, 824)
```

**Edge Cases:**
- Candidate coordinates negative: clamped to `virtual_screen_bounds[0]` / `virtual_screen_bounds[1]`.
- Candidate coordinates exceed screen width/height minus `size`: clamped to `max_x = bounds[2] - size`, `max_y = bounds[3] - size`.
- Gauge `size` exceeds screen bounds: clamped to min bounds `(bounds[0], bounds[1])`.

### 5.2 `calculate_next_size()`

**File:** `src/boostgauge/window.py`

**Signature:**

```python
def calculate_next_size(
    current_size: int,
    delta: int,
    min_size: int = 128,
    max_size: int = 512,
    step: int = 16,
) -> int:
    """Compute updated canvas square dimension from mouse wheel delta, clamped within min and max bounds."""
    ...
```

**Input Example:**

```python
current_size = 256
delta = 1  # Scroll up
min_size = 128
max_size = 512
step = 16
```

**Output Example:**

```python
272
```

**Edge Cases:**
- `delta = -1` at `current_size = 128` (min_size): returns `128`.
- `delta = 1` at `current_size = 512` (max_size): returns `512`.
- `delta = 0`: returns `256`.

### 5.3 `create_tray_indicator_image()`

**File:** `src/boostgauge/window.py`

**Signature:**

```python
def create_tray_indicator_image(status: str = "green", size: int = 16) -> Image.Image:
    """Generate square pixel RGBA image containing circular status color dot (green/yellow/red) for system tray icon."""
    ...
```

**Input Example:**

```python
status = "yellow"
size = 16
```

**Output Example:**

```python
# Returns PIL.Image.Image object of mode "RGBA", dimensions 16x16, yellow circle (255, 191, 0, 255) on transparent background
```

**Edge Cases:**
- Invalid status string (e.g. `"blue"`): defaults to `"green"` color tuple `(40, 200, 80, 255)`.
- `size <= 0`: raises `ValueError("size must be positive")`.

### 5.4 `TrayManager.update_status()`

**File:** `src/boostgauge/window.py`

**Signature:**

```python
class TrayManager:
    def update_status(self, status: str) -> None:
        """Update system tray icon image to reflect status level ('green', 'yellow', 'red')."""
        ...
```

**Input Example:**

```python
status = "red"
```

**Output Example:**

```python
None
```

**Edge Cases:**
- Icon not initialized or already stopped: method safely updates internal state without crashing.

### 5.5 `GaugeWindow.set_topmost()`

**File:** `src/boostgauge/window.py`

**Signature:**

```python
class GaugeWindow:
    def set_topmost(self, topmost: bool) -> None:
        """Toggle root topmost attribute and update state dictionary."""
        ...
```

**Input Example:**

```python
topmost = False
```

**Output Example:**

```python
None
```

**Edge Cases:**
- Tk root headlessly mocked (Option C mode): state dictionary updated to `topmost=False` without calling Tk attributes.

---

## 6. Change Instructions

### 6.1 `src/boostgauge/window.py` (Add)

**Complete file contents:**

```python
"""Window controller and system tray integration for BoostGauge.

Issue #5: Always-on-Top Window with Drag, Minimize, and Transparency
"""

from __future__ import annotations

import sys
import threading
from typing import Any, Callable, Optional, Tuple

from PIL import Image, ImageDraw, ImageTk
import pystray

from boostgauge.config import GaugeConfigDict, update_window_geometry

STATUS_COLORS = {
    "green": (40, 200, 80, 255),
    "yellow": (255, 191, 0, 255),
    "red": (235, 50, 50, 255),
}


def clamp_window_position(
    x: int,
    y: int,
    size: int,
    virtual_screen_bounds: Tuple[int, int, int, int] = (0, 0, 1920, 1080),
) -> Tuple[int, int]:
    """Clamp window top-left coordinates to keep gauge visible within target screen work area bounds."""
    min_x, min_y, max_w, max_h = virtual_screen_bounds
    max_x = max(min_x, max_w - size)
    max_y = max(min_y, max_h - size)

    clamped_x = max(min_x, min(x, max_x))
    clamped_y = max(min_y, min(y, max_y))
    return clamped_x, clamped_y


def calculate_next_size(
    current_size: int,
    delta: int,
    min_size: int = 128,
    max_size: int = 512,
    step: int = 16,
) -> int:
    """Compute updated canvas square dimension from mouse wheel delta, clamped within min and max bounds."""
    if delta > 0:
        new_size = current_size + step
    elif delta < 0:
        new_size = current_size - step
    else:
        new_size = current_size

    return max(min_size, min(new_size, max_size))


def create_tray_indicator_image(status: str = "green", size: int = 16) -> Image.Image:
    """Generate 16x16 pixel RGBA image containing circular status color dot for system tray icon."""
    if size <= 0:
        raise ValueError("size must be positive")

    color = STATUS_COLORS.get(status, STATUS_COLORS["green"])
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    margin = max(1, size // 8)
    getattr(draw, "ellipse")((margin, margin, size - margin - 1, size - margin - 1), fill=color)
    return img


class TrayManager:
    """Manages cross-platform system tray icon lifecycle via pystray in background thread."""

    def __init__(self, callbacks: dict[str, Callable[[], None]], initial_status: str = "green") -> None:
        """Initialize pystray icon with popup menu and callbacks."""
        self.callbacks = callbacks
        self.current_status = initial_status
        self._thread: Optional[threading.Thread] = None
        self._icon: Optional[pystray.Icon] = None

        menu = pystray.Menu(
            pystray.MenuItem("Restore", lambda icon, item: self._safe_callback("on_restore"), default=True),
            pystray.MenuItem("Toggle Topmost", lambda icon, item: self._safe_callback("on_toggle_topmost")),
            pystray.MenuItem("Reset Peak Peaks", lambda icon, item: self._safe_callback("on_reset_telltales")),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", lambda icon, item: self._safe_callback("on_quit")),
        )

        img = create_tray_indicator_image(self.current_status)
        self._icon = pystray.Icon("boostgauge", img, "BoostGauge", menu=menu)

    def _safe_callback(self, key: str) -> None:
        cb = self.callbacks.get(key)
        if cb:
            cb()

    def update_status(self, status: str) -> None:
        """Update system tray icon image to reflect status level ('green', 'yellow', 'red')."""
        self.current_status = status
        if self._icon is not None:
            self._icon.icon = create_tray_indicator_image(self.current_status)

    def start(self) -> None:
        """Start pystray event loop in background daemon thread."""
        if self._icon is not None and self._thread is None:
            self._thread = threading.Thread(target=self._icon.run, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        """Stop system tray icon and detach menu background thread."""
        if self._icon is not None:
            try:
                getattr(self._icon, "stop")()
            except Exception:
                pass
            self._icon = None
        self._thread = None


class GaugeWindow:
    """Encapsulates frameless, topmost, transparent Tkinter root window and interaction handlers."""

    def __init__(
        self,
        config: GaugeConfigDict,
        on_config_change: Optional[Callable[[GaugeConfigDict], None]] = None,
        tk_root: Optional[Any] = None,
    ) -> None:
        """Initialize window state, options, and event bindings."""
        self.config = config
        self.on_config_change = on_config_change

        self.size = config["size"]
        self.x = config["position"]["x"]
        self.y = config["position"]["y"]
        self.topmost = config["always_on_top"]
        self.opacity = config["opacity"]
        self.is_compact = False
        self.is_minimized = False

        self._start_drag_x = 0
        self._start_drag_y = 0
        self._start_win_x = 0
        self._start_win_y = 0

        self.root = tk_root
        self.canvas = None
        self._photo_image = None

        if self.root is not None:
            self._init_tk_window()

    def _init_tk_window(self) -> None:
        """Configure native Tkinter root attributes and mouse bindings."""
        import tkinter as tk

        getattr(self.root, "overrideredirect")(True)
        self.set_topmost(self.topmost)
        self.apply_transparency()

        getattr(self.root, "geometry")(f"{self.size}x{self.size}+{self.x}+{self.y}")

        self.canvas = tk.Canvas(
            self.root,
            width=self.size,
            height=self.size,
            bg="#010101",
            highlightthickness=0,
            bd=0,
        )
        getattr(self.canvas, "pack")(fill=tk.BOTH, expand=True)

        getattr(self.canvas, "bind")("<ButtonPress-1>", self._on_drag_start)
        getattr(self.canvas, "bind")("<B1-Motion>", self._on_drag_motion)
        getattr(self.canvas, "bind")("<ButtonRelease-1>", self._on_drag_end)
        getattr(self.canvas, "bind")("<Double-Button-1>", lambda e: self.toggle_compact_mode())
        getattr(self.canvas, "bind")("<Enter>", lambda e: self._set_opacity(1.0))
        getattr(self.canvas, "bind")("<Leave>", lambda e: self._set_opacity(self.opacity))

        getattr(self.canvas, "bind")("<MouseWheel>", self._on_mouse_wheel)
        getattr(self.canvas, "bind")("<Button-4>", lambda e: self._on_mouse_wheel_delta(1))
        getattr(self.canvas, "bind")("<Button-5>", lambda e: self._on_mouse_wheel_delta(-1))

    def apply_transparency(self, bg_color: str = "#010101") -> None:
        """Apply Windows transparent color key and root alpha attributes."""
        if self.root is None:
            return
        if sys.platform == "win32":
            try:
                getattr(self.root, "attributes")("-transparentcolor", bg_color)
            except Exception:
                pass
        self._set_opacity(self.opacity)

    def _set_opacity(self, alpha: float) -> None:
        if self.root is not None:
            try:
                getattr(self.root, "attributes")("-alpha", alpha)
            except Exception:
                pass

    def set_topmost(self, topmost: bool) -> None:
        """Toggle root topmost attribute and update persistent configuration."""
        self.topmost = topmost
        self.config["always_on_top"] = topmost
        if self.root is not None:
            try:
                getattr(self.root, "attributes")("-topmost", topmost)
            except Exception:
                pass
        if self.on_config_change:
            self.on_config_change(self.config)

    def toggle_compact_mode(self) -> None:
        """Toggle between compact (192px) and normal/expanded size mode."""
        if self.is_compact:
            self.size = self.config["size"]
            self.is_compact = False
        else:
            self.size = 192
            self.is_compact = True
        self._update_geometry_str()

    def minimize_to_tray(self) -> None:
        """Hide Tkinter root window and ensure system tray icon is active."""
        self.is_minimized = True
        if self.root is not None:
            getattr(self.root, "withdraw")()

    def restore_from_tray(self) -> None:
        """Un-hide Tkinter root window and lift to active focus."""
        self.is_minimized = False
        if self.root is not None:
            getattr(self.root, "deiconify")()
            getattr(self.root, "lift")()
            getattr(self.root, "focus_force")()

    def update_gauge_image(self, img: Image.Image) -> None:
        """Convert PIL Image to PhotoImage and update canvas display widget."""
        if self.root is None or self.canvas is None:
            return
        resized = getattr(img, "resize")((self.size, self.size), Image.Resampling.LANCZOS)
        self._photo_image = ImageTk.PhotoImage(resized)
        getattr(self.canvas, "delete")("all")
        getattr(self.canvas, "create_image")(0, 0, anchor="nw", image=self._photo_image)

    def _on_drag_start(self, event: Any) -> None:
        self._start_drag_x = event.x_root
        self._start_drag_y = event.y_root
        self._start_win_x = self.x
        self._start_win_y = self.y

    def _on_drag_motion(self, event: Any) -> None:
        delta_x = event.x_root - self._start_drag_x
        delta_y = event.y_root - self._start_drag_y
        cand_x = self._start_win_x + delta_x
        cand_y = self._start_win_y + delta_y

        self.x, self.y = clamp_window_position(cand_x, cand_y, self.size)
        self._update_geometry_str()

    def _on_drag_end(self, event: Any) -> None:
        self.config = update_window_geometry(self.config, self.x, self.y, self.size)
        if self.on_config_change:
            self.on_config_change(self.config)

    def _on_mouse_wheel(self, event: Any) -> None:
        delta = 1 if event.delta > 0 else -1
        self._on_mouse_wheel_delta(delta)

    def _on_mouse_wheel_delta(self, delta: int) -> None:
        new_size = calculate_next_size(self.size, delta)
        if new_size != self.size:
            self.size = new_size
            if not self.is_compact:
                self.config["size"] = new_size
            self._update_geometry_str()
            self.config = update_window_geometry(self.config, self.x, self.y, self.size)
            if self.on_config_change:
                self.on_config_change(self.config)

    def _update_geometry_str(self) -> None:
        if self.root is not None:
            getattr(self.root, "geometry")(f"{self.size}x{self.size}+{self.x}+{self.y}")
            if self.canvas is not None:
                getattr(self.canvas, "config")(width=self.size, height=self.size)

    def run(self) -> None:
        """Start Tkinter event loop."""
        if self.root is not None:
            getattr(self.root, "mainloop")()
```

### 6.2 `src/boostgauge/app.py` (Modify)

**Change 1:** Add imports and update `main()` function at lines 6–45.

```diff
 from __future__ import annotations

 import sys
-
 from typing import Optional

 from boostgauge.config import (
     ConfigError,
     apply_cli_overrides,
     get_default_config,
     get_default_config_path,
     load_config,
     parse_cli_args,
     save_config,
     validate_config,
 )
+from boostgauge.window import GaugeWindow, TrayManager
```

**Change 2:** Instantiate window and handle lifecycle in `main()`:

```diff
         config = apply_cli_overrides(config, parsed_args)
         config = validate_config(config)

+        import tkinter as tk

+        root = tk.Tk()
+        window = GaugeWindow(config, on_config_change=lambda cfg: save_config(cfg, target_config_path), tk_root=root)
+
+        tray_callbacks = {
+            "on_toggle_topmost": lambda: window.set_topmost(not window.topmost),
+            "on_reset_telltales": lambda: None,
+            "on_restore": window.restore_from_tray,
+            "on_quit": getattr(root, "quit"),
+        }
+        tray = TrayManager(tray_callbacks)
+        tray.start()
+
+        try:
+            window.run()
+        finally:
+            tray.stop()
+            save_config(window.config, target_config_path)

         return 0

     except ConfigError as exc:
```

### 6.3 `src/boostgauge/__init__.py` (Modify)

**Change 1:** Export window symbols at lines 6–19.

```diff
 from boostgauge.collector import DataCollector, SystemSnapshot
 from boostgauge.collectors import WindowsCollector, create_collector
 from boostgauge.telltale import TelltaleManager
+from boostgauge.window import (
+    GaugeWindow,
+    TrayManager,
+    calculate_next_size,
+    clamp_window_position,
+    create_tray_indicator_image,
+)

 __version__ = "0.1.0"

 __all__ = [
     "__version__",
     "DataCollector",
+    "GaugeWindow",
     "SystemSnapshot",
     "TelltaleManager",
+    "TrayManager",
     "WindowsCollector",
+    "calculate_next_size",
+    "clamp_window_position",
+    "create_tray_indicator_image",
     "create_collector",
 ]
```

---

## 7. Pattern References

### 7.1 Configuration State Helper Pattern

**File:** `src/boostgauge/config.py` (lines 240–245)

```python
def update_window_geometry(config: GaugeConfigDict, x: int, y: int, size: int) -> GaugeConfigDict:
    """Update window position and size parameters in configuration data structure prior to exit/save."""
    updated = getattr(copy, "deepcopy")(config)
    updated["position"] = {"x": x, "y": y}
    updated["size"] = size
    return updated
```

**Relevance:** `GaugeWindow` calls `update_window_geometry` on drag-end and mouse wheel resize to produce a clean, updated configuration dictionary before invoking `on_config_change`.

### 7.2 Safe JSON Persistence Pattern

**File:** `src/boostgauge/config.py` (lines 184–203)

```python
def save_config(config: GaugeConfigDict, config_path: Optional[Path] = None) -> None:
    """Atomically write configuration dictionary to JSON file at specified path (or default path)."""
    target_path = config_path.resolve() if config_path else get_default_config_path()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    ...
```

**Relevance:** `app.py` passes `save_config` as the `on_config_change` callback for `GaugeWindow` so position and size changes persist atomically.

---

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `import sys` | stdlib | `window.py`, `app.py` |
| `import threading` | stdlib | `window.py` |
| `from typing import Any, Callable, Optional, Tuple` | stdlib | `window.py` |
| `from PIL import Image, ImageDraw, ImageTk` | external (`Pillow`) | `window.py` |
| `import pystray` | external (`pystray`) | `window.py` |
| `from boostgauge.config import GaugeConfigDict, update_window_geometry` | internal | `window.py` |
| `from boostgauge.window import GaugeWindow, TrayManager` | internal | `app.py`, `__init__.py` |

**New Dependencies:** None (pystray and pillow are already declared in `pyproject.toml`).

---

## 9. Placeholder

*Reserved for alignment with LLD section numbering.*

---

## 10. Test Mapping

### 10.1 Mapping Table

| Test ID | Tests Function / Scenario | Input | Expected Output / Behavior |
|---------|---------------------------|-------|----------------------------|
| T010 | `clamp_window_position()` (REQ-13) | `x=-50, y=1000, size=256, bounds=(0,0,1920,1080)` | `(0, 824)` |
| T020 | `calculate_next_size()` (REQ-14) | `current_size=256, delta=1, step=16` | `272` |
| T021 | `calculate_next_size()` boundary clamp | `current_size=512, delta=1, max_size=512` | `512` |
| T030 | `create_tray_indicator_image()` (REQ-9) | `status="green", size=16` | PIL RGBA Image, 16x16, non-zero alpha channel, green center pixel |
| T040 | `GaugeWindow.set_topmost()` state (REQ-1, REQ-2) | `GaugeWindow(cfg)`, `set_topmost(False)` | `window.topmost == False`, `window.config["always_on_top"] == False` |
| T050 | `GaugeWindow.toggle_compact_mode()` (REQ-5) | Initial size 256, call `toggle_compact_mode()` twice | 1st call: `size == 192, is_compact == True`; 2nd call: `size == 256, is_compact == False` |
| T060 | `GaugeWindow` opacity hover logic (REQ-7) | Initial opacity 0.8, enter hover | Idle alpha state 0.8, hover state 1.0 |
| T070 | `GaugeWindow.minimize_to_tray()` / `restore_from_tray()` (REQ-8, REQ-10) | `minimize_to_tray()`, then `restore_from_tray()` | `is_minimized` toggles True then False |
| T080 | Geometry update serialization (REQ-12) | Drag motion delta `(+50, +20)` from `(100, 100)` | `window.x == 150`, `window.y == 120`, `config["position"] == {"x": 150, "y": 120}` |

### 10.2 Platform-Independent & Baseline-Independent Test Assertions

All unit tests in `tests/unit/test_window.py` run without initializing `tkinter.Tk()` in accordance with Option C testing rules (`docs/design/0001-test-strategy.md`). Path assertions use `pathlib.Path` objects.

**Baseline-Independent Status Indicator Verification:**
```python
def test_tray_indicator_image_colors():
    img = create_tray_indicator_image("green", size=16)
    assert img.size == (16, 16)
    assert img.mode == "RGBA"
    # Center pixel should match green color tuple
    center_pixel = img.getpixel((8, 8))
    assert center_pixel == (40, 200, 80, 255)
    # Corner pixel outside ellipse should be transparent
    corner_pixel = img.getpixel((0, 0))
    assert corner_pixel[3] == 0
```

---

## 11. Implementation Notes

### 11.1 Option C Testing Compliance

Tkinter windows cannot be created headlessly on CI test runners without active display servers. `GaugeWindow` allows `tk_root` to be `None` during unit tests. Pure calculations (`clamp_window_position`, `calculate_next_size`, `create_tray_indicator_image`, state flags) are validated in unit tests without invoking Tkinter GUI operations.

### 11.2 Pystray Threading & Callbacks

`pystray` icon loop blocks its thread. `TrayManager` starts `pystray.Icon.run` inside a background daemon thread (`threading.Thread(daemon=True)`). Callbacks to UI state update instance flags safely across threads.

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
| Date | 2026-07-30 |
| Iterations | 1 |
| Finalized | 2026-07-30T03:53:22-05:00 |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #5 |
| Verdict | APPROVED |
| Date | 2026-07-30 |
| Iterations | 1 |
| Finalized | 2026-07-30T08:54:36Z |

### Review Feedback Summary

The implementation spec for Issue #5 is complete, concrete, internally consistent, and fully executable. All code changes and file diffs are provided with line-level detail. Function signatures include realistic input/output examples and edge cases, data structures include concrete JSON/Python examples, and pattern references match existing codebase lines. Every test assertion traces directly to specified requirements, and baseline-independent test verification is properly included in accordance...
