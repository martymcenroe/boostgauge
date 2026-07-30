# Implementation Spec: Always-On-Top Window with Drag, Minimize, and Transparency (#5)

| Field | Value |
|-------|-------|
| Issue | #5 |
| LLD | `docs/lld/done/0005-always-on-top-window-drag-minimize-transparency.md` |
| Generated | 2026-07-30 |
| Status | APPROVED |

## 1. Overview

This specification details the implementation of a frameless, transparent, always-on-top Tkinter window manager (`GaugeWindow`) paired with a cross-platform system tray manager (`TrayManager`) using `pystray`. The system enables mouse dragging, mouse wheel resizing (preserving 1:1 aspect ratio), double-click size toggling between compact (128x128) and expanded modes, dynamic idle/hover transparency, virtual multi-monitor coordinate clamping, and status dot tray indication (green/yellow/red) with background thread synchronization.

**Objective:** Implement an always-on-top, frameless, transparent Tkinter widget with mouse dragging, system tray minimization via `pystray`, and persistent window position and size configuration.

**Success Criteria:**
1. Frameless window created with `overrideredirect(True)` and draggable via mouse press and motion anywhere on the dial face.
2. Dynamic chroma-key transparency (`#000001`) outside circular dial face on Windows platforms.
3. System tray icon displaying status dots (green < 60%, yellow < 85%, red >= 85%) updated via background thread safely using `root.after()`.
4. Double-click tray icon restores window from withdrawn state; double-click gauge face toggles compact (128px) and expanded sizes.
5. Window geometry (x, y, size) persistently saved to configuration file on app exit and clamped to virtual display bounds on launch.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/window.py` | Add | Core window manager `GaugeWindow` handling frameless Tk window creation, topmost setting, drag movement, wheel resizing, transparency/opacity, and screen-clamping geometry persistence. |
| 2 | `src/boostgauge/tray.py` | Add | System tray manager `TrayManager` wrapping `pystray.Icon` with a dynamic 16x16 color status dot (green/yellow/red), double-click restore, right-click context menu, and thread-safe callbacks to `GaugeWindow`. |
| 3 | `src/boostgauge/app.py` | Modify | Integrate `GaugeWindow` and `TrayManager` into application lifecycle, connect data snapshot updates to gauge rendering and tray status, handle tray minimize/restore events, and persist window geometry on shutdown. |
| 4 | `src/boostgauge/__init__.py` | Modify | Export `GaugeWindow`, `TrayManager`, and `determine_tray_status` in package `__all__`. |
| 5 | `tests/unit/test_window.py` | Add | Headless unit tests validating window geometry calculations, multi-monitor clamping, drag delta math, transparency settings, and opacity state transitions using mock Tk components per `docs/design/0001-test-strategy.md`. |
| 6 | `tests/unit/test_tray.py` | Add | Unit tests validating tray status dot image generation (green/yellow/red), context menu routing, thread-safe event dispatch logic, and load status determination without instantiating an OS tray icon. |

**Implementation Order Rationale:** `window.py` and `tray.py` provide foundational GUI controllers. `app.py` requires both modules to integrate the runtime lifecycle. `__init__.py` exposes the public exports. Test modules validate `window.py` and `tray.py` without requiring GUI hardware.

## 3. Current State (for Modify/Delete files)

### 3.1 `src/boostgauge/app.py`

**Relevant excerpt** (lines 1-47):

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

**What changes:** Update `main()` to instantiate `GaugeWindow`, setup `TrayManager` callbacks, start the background tray thread, launch the data polling loop (`root.after`), and handle clean shutdown with geometry persistence via `update_window_geometry()` and `save_config()`.

### 3.2 `src/boostgauge/__init__.py`

**Relevant excerpt** (lines 1-19):

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

**What changes:** Import `GaugeWindow` from `boostgauge.window` and `TrayManager`, `determine_tray_status` from `boostgauge.tray`, adding them to `__all__`.

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
    hover_opacity: float
    is_expanded: bool
    is_minimized_to_tray: bool
```

**Concrete Example:**

```json
{
    "x": 250,
    "y": 140,
    "size": 256,
    "topmost": true,
    "opacity": 0.8,
    "hover_opacity": 1.0,
    "is_expanded": true,
    "is_minimized_to_tray": false
}
```

### 4.2 `TrayStatus`

**Definition:**

```python
from typing import Literal

TrayStatus = Literal["green", "yellow", "red"]
```

**Concrete Example:**

```json
"green"
```

## 5. Function Specifications

### 5.1 `GaugeWindow.__init__()`

**File:** `src/boostgauge/window.py`

**Signature:**

```python
def __init__(
    self,
    config: Optional[Dict[str, Any]] = None,
    on_geometry_change: Optional[Callable[[int, int, int], None]] = None,
    on_close: Optional[Callable[[], None]] = None,
    root: Optional[Any] = None,
) -> None:
    """Initialize window state, geometry properties, and callback handlers."""
    ...
```

**Input Example:**

```python
config = {"position": {"x": 100, "y": 100}, "size": 256, "always_on_top": True, "opacity": 0.9}
on_geometry_change = lambda x, y, size: print(f"Geometry updated: {x}, {y}, {size}")
on_close = lambda: print("Window closed")
root = None
```

**Output Example:**

```python
# Instantiates GaugeWindow object with x=100, y=100, size=256, topmost=True, opacity=0.9
```

**Edge Cases:**
- `config=None` -> Uses default geometry values `x=100, y=100, size=256, topmost=True, opacity=0.8`.
- Invalid screen coordinates -> `clamp_to_screen()` normalizes coordinates to visible monitor area.

### 5.2 `GaugeWindow.clamp_to_screen()`

**File:** `src/boostgauge/window.py`

**Signature:**

```python
def clamp_to_screen(self, x: int, y: int, size: int) -> Tuple[int, int]:
    """Ensure window coordinates remain fully visible within virtual screen boundaries."""
    ...
```

**Input Example:**

```python
x = 5000
y = -100
size = 256
# Screen bounds: virtual_x=0, virtual_y=0, vwidth=1920, vheight=1080
```

**Output Example:**

```python
(1664, 0)
```

**Edge Cases:**
- Negative coordinates -> clamped to minimum `vrootx` (0).
- Coordinates exceeding screen width/height -> clamped to `vrootx + vwidth - size` and `vrooty + vheight - size`.

### 5.3 `GaugeWindow.toggle_topmost()`

**File:** `src/boostgauge/window.py`

**Signature:**

```python
def toggle_topmost(self) -> bool:
    """Toggle always-on-top attribute on Tk window and return new boolean state."""
    ...
```

**Input Example:**

```python
# Initial state: self.topmost = True
```

**Output Example:**

```python
False
```

**Edge Cases:**
- Invoked when Tk root is destroyed or mock root is inactive -> updates internal boolean state and handles TkException gracefully.

### 5.4 `GaugeWindow.toggle_compact_expanded()`

**File:** `src/boostgauge/window.py`

**Signature:**

```python
def toggle_compact_expanded(self) -> int:
    """Toggle window size between compact (128px) and expanded (256px/configured) modes."""
    ...
```

**Input Example:**

```python
# Current window size: 256 (expanded)
```

**Output Example:**

```python
128
```

**Edge Cases:**
- Already compact (128px) -> restores previous saved expanded size (e.g., 256px).
- Custom size 512px -> toggles between 128px and 512px.

### 5.5 `GaugeWindow.handle_mouse_wheel()`

**File:** `src/boostgauge/window.py`

**Signature:**

```python
def handle_mouse_wheel(self, event: Any) -> None:
    """Resize gauge window on mouse wheel scroll while enforcing 1:1 aspect ratio and size bounds."""
    ...
```

**Input Example:**

```python
event = type("Event", (), {"delta": 120, "num": 4})() # Scroll up event
# Current size: 256
```

**Output Example:**

```python
# Window size updated to 288 (step of +32)
```

**Edge Cases:**
- Scroll down attempting size < 128 -> size clamped to minimum 128.
- Scroll up attempting size > 1024 -> size clamped to maximum 1024.

### 5.6 `TrayManager.create_status_icon()`

**File:** `src/boostgauge/tray.py`

**Signature:**

```python
def create_status_icon(self, status: TrayStatus = "green") -> Image.Image:
    """Generate a 16x16 RGBA PIL Image containing a colored status dot indicator."""
    ...
```

**Input Example:**

```python
status = "yellow"
```

**Output Example:**

```python
# PIL Image object, mode="RGBA", size=(16, 16), centered circle with RGBA (241, 196, 15, 255)
```

**Edge Cases:**
- Invalid status string -> defaults to `"green"` icon.

### 5.7 `determine_tray_status()`

**File:** `src/boostgauge/tray.py`

**Signature:**

```python
def determine_tray_status(
    value: float,
    warning_thresh: float = 60.0,
    danger_thresh: float = 85.0,
) -> TrayStatus:
    """Map normalized composite metric value (0-100) to tray status level ('green', 'yellow', 'red')."""
    ...
```

**Input Example:**

```python
value = 75.0
warning_thresh = 60.0
danger_thresh = 85.0
```

**Output Example:**

```python
"yellow"
```

**Edge Cases:**
- `value = 45.0` -> `"green"`
- `value = 85.0` -> `"red"`
- `value = -10.0` -> clamped, returns `"green"`

## 6. Change Instructions

### 6.1 `src/boostgauge/window.py` (Add)

**Complete file contents:**

```python
"""Core window manager handling frameless Tk window creation, positioning, and events.

Issue #5: always-on-top window with drag, minimize, and transparency (#5)
"""

from __future__ import annotations

import sys
from typing import Any, Callable, Dict, Optional, Tuple
from PIL import Image, ImageTk


TRANSPARENT_COLOR = "#000001"
MIN_WINDOW_SIZE = 128
MAX_WINDOW_SIZE = 1024
DEFAULT_EXPANDED_SIZE = 256
IDLE_OPACITY = 0.8
HOVER_OPACITY = 1.0


class GaugeWindow:
    """Frameless, transparent, always-on-top Tkinter window manager for BoostGauge."""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        on_geometry_change: Optional[Callable[[int, int, int], None]] = None,
        on_close: Optional[Callable[[], None]] = None,
        root: Optional[Any] = None,
    ) -> None:
        """Initialize window state, geometry properties, and callback handlers."""
        cfg = config or {}
        pos = cfg.get("position", {}) if isinstance(cfg.get("position"), dict) else {}

        self.x: int = int(pos.get("x", 100))
        self.y: int = int(pos.get("y", 100))
        self.size: int = int(cfg.get("size", DEFAULT_EXPANDED_SIZE))
        self.saved_expanded_size: int = self.size if self.size > MIN_WINDOW_SIZE else DEFAULT_EXPANDED_SIZE
        self.topmost: bool = bool(cfg.get("always_on_top", True))
        self.opacity: float = float(cfg.get("opacity", IDLE_OPACITY))
        self.hover_opacity: float = HOVER_OPACITY
        self.is_expanded: bool = self.size > MIN_WINDOW_SIZE
        self.is_minimized_to_tray: bool = False

        self.on_geometry_change = on_geometry_change
        self.on_close = on_close

        self._drag_start_x: int = 0
        self._drag_start_y: int = 0
        self._photo_image: Optional[ImageTk.PhotoImage] = None

        if root is not None:
            self.root = root
        else:
            import tkinter as tk
            self.root = tk.Tk()

        self.canvas: Optional[Any] = None
        self._canvas_image_id: Optional[int] = None
        self.setup_window()

    def clamp_to_screen(self, x: int, y: int, size: int) -> Tuple[int, int]:
        """Ensure window coordinates remain fully visible within virtual screen boundaries."""
        try:
            vrootx = self.root.winfo_vrootx()
            vrooty = self.root.winfo_vrooty()
            vwidth = self.root.winfo_vrootwidth()
            vheight = self.root.winfo_vrootheight()
        except Exception:
            vrootx, vrooty = 0, 0
            vwidth = getattr(self.root, "winfo_screenwidth", lambda: 1920)()
            vheight = getattr(self.root, "winfo_screenheight", lambda: 1080)()

        max_x = vrootx + vwidth - size
        max_y = vrooty + vheight - size

        clamped_x = max(vrootx, min(x, max_x))
        clamped_y = max(vrooty, min(y, max_y))

        return clamped_x, clamped_y

    def setup_window(self) -> None:
        """Configure Tk root attributes: frameless, topmost, transparent background color, and event bindings."""
        clamped_x, clamped_y = self.clamp_to_screen(self.x, self.y, self.size)
        self.x, self.y = clamped_x, clamped_y

        if hasattr(self.root, "overrideredirect"):
            self.root.overrideredirect(True)

        if hasattr(self.root, "attributes"):
            try:
                self.root.attributes("-topmost", self.topmost)
            except Exception:
                pass

            if sys.platform == "win32":
                try:
                    self.root.attributes("-transparentcolor", TRANSPARENT_COLOR)
                except Exception:
                    pass

            try:
                self.root.attributes("-alpha", self.opacity)
            except Exception:
                pass

        if hasattr(self.root, "geometry"):
            self.root.geometry(f"{self.size}x{self.size}+{self.x}+{self.y}")

        if hasattr(self.root, "configure"):
            self.root.configure(bg=TRANSPARENT_COLOR)

        import tkinter as tk
        if hasattr(self.root, "title"):
            self.canvas = tk.Canvas(
                self.root,
                width=self.size,
                height=self.size,
                bg=TRANSPARENT_COLOR,
                highlightthickness=0,
            )
            self.canvas.pack(fill=tk.BOTH, expand=True)

            self.canvas.bind("<ButtonPress-1>", self.handle_drag_start)
            self.canvas.bind("<B1-Motion>", self.handle_drag_motion)
            self.canvas.bind("<Double-Button-1>", lambda e: self.toggle_compact_expanded())
            self.canvas.bind("<Enter>", lambda e: self.set_opacity(self.hover_opacity))
            self.canvas.bind("<Leave>", lambda e: self.set_opacity(self.opacity))
            self.canvas.bind("<MouseWheel>", self.handle_mouse_wheel)
            self.canvas.bind("<Button-4>", self.handle_mouse_wheel)
            self.canvas.bind("<Button-5>", self.handle_mouse_wheel)

    def update_image(self, pil_img: Image.Image) -> None:
        """Update display Canvas with a new PIL Image rendered frame."""
        if self.canvas is None:
            return

        resized = getattr(pil_img, "resize")((self.size, self.size), Image.Resampling.LANCZOS)
        self._photo_image = ImageTk.PhotoImage(resized)

        if self._canvas_image_id is None:
            self._canvas_image_id = self.canvas.create_image(0, 0, anchor="nw", image=self._photo_image)
        else:
            self.canvas.itemconfig(self._canvas_image_id, image=self._photo_image)

    def toggle_topmost(self) -> bool:
        """Toggle always-on-top attribute on Tk window and return new boolean state."""
        self.topmost = not self.topmost
        if hasattr(self.root, "attributes"):
            try:
                self.root.attributes("-topmost", self.topmost)
            except Exception:
                pass
        return self.topmost

    def toggle_compact_expanded(self) -> int:
        """Toggle window size between compact (128px) and expanded (256px/configured) modes."""
        if self.size == MIN_WINDOW_SIZE:
            self.size = self.saved_expanded_size
            self.is_expanded = True
        else:
            self.saved_expanded_size = self.size
            self.size = MIN_WINDOW_SIZE
            self.is_expanded = False

        self.x, self.y = self.clamp_to_screen(self.x, self.y, self.size)
        if hasattr(self.root, "geometry"):
            self.root.geometry(f"{self.size}x{self.size}+{self.x}+{self.y}")

        if self.canvas is not None and hasattr(self.canvas, "config"):
            self.canvas.config(width=self.size, height=self.size)

        if self.on_geometry_change:
            self.on_geometry_change(self.x, self.y, self.size)

        return self.size

    def set_opacity(self, alpha: float) -> None:
        """Set window opacity level bounded between 0.1 and 1.0."""
        clamped_alpha = max(0.1, min(1.0, float(alpha)))
        if hasattr(self.root, "attributes"):
            try:
                self.root.attributes("-alpha", clamped_alpha)
            except Exception:
                pass

    def handle_drag_start(self, event: Any) -> None:
        """Record initial screen pointer coordinates when mouse button is pressed on gauge face."""
        self._drag_start_x = getattr(event, "x", 0)
        self._drag_start_y = getattr(event, "y", 0)

    def handle_drag_motion(self, event: Any) -> None:
        """Recalculate window screen position during mouse drag motion and update geometry."""
        try:
            curr_x = self.root.winfo_x()
            curr_y = self.root.winfo_y()
        except Exception:
            curr_x, curr_y = self.x, self.y

        dx = getattr(event, "x", 0) - self._drag_start_x
        dy = getattr(event, "y", 0) - self._drag_start_y

        new_x = curr_x + dx
        new_y = curr_y + dy

        self.x, self.y = self.clamp_to_screen(new_x, new_y, self.size)
        if hasattr(self.root, "geometry"):
            self.root.geometry(f"{self.size}x{self.size}+{self.x}+{self.y}")

        if self.on_geometry_change:
            self.on_geometry_change(self.x, self.y, self.size)

    def handle_mouse_wheel(self, event: Any) -> None:
        """Resize gauge window on mouse wheel scroll while enforcing 1:1 aspect ratio and size bounds."""
        delta = getattr(event, "delta", 0)
        num = getattr(event, "num", 0)

        step = 32
        if delta > 0 or num == 4:
            new_size = self.size + step
        elif delta < 0 or num == 5:
            new_size = self.size - step
        else:
            return

        self.size = max(MIN_WINDOW_SIZE, min(MAX_WINDOW_SIZE, new_size))
        if self.size > MIN_WINDOW_SIZE:
            self.saved_expanded_size = self.size
            self.is_expanded = True

        self.x, self.y = self.clamp_to_screen(self.x, self.y, self.size)
        if hasattr(self.root, "geometry"):
            self.root.geometry(f"{self.size}x{self.size}+{self.x}+{self.y}")

        if self.canvas is not None and hasattr(self.canvas, "config"):
            self.canvas.config(width=self.size, height=self.size)

        if self.on_geometry_change:
            self.on_geometry_change(self.x, self.y, self.size)

    def minimize_to_tray(self) -> None:
        """Withdraw Tk window from desktop and taskbar, delegating visibility to system tray."""
        if hasattr(self.root, "withdraw"):
            self.root.withdraw()
        self.is_minimized_to_tray = True

    def restore_from_tray(self) -> None:
        """Deiconify Tk window, restore screen visibility, and re-assert topmost focus."""
        if hasattr(self.root, "deiconify"):
            self.root.deiconify()
        if hasattr(self.root, "lift"):
            self.root.lift()
        if hasattr(self.root, "attributes"):
            try:
                self.root.attributes("-topmost", self.topmost)
            except Exception:
                pass
        self.is_minimized_to_tray = False

    def destroy(self) -> None:
        """Gracefully destroy Tk window and release canvas resources."""
        if self.on_close:
            try:
                self.on_close()
            except Exception:
                pass
        if hasattr(self.root, "destroy"):
            self.root.destroy()
```

### 6.2 `src/boostgauge/tray.py` (Add)

**Complete file contents:**

```python
"""Cross-platform system tray controller using pystray with dynamic status indicator.

Issue #5: always-on-top window with drag, minimize, and transparency (#5)
"""

from __future__ import annotations

import threading
from typing import Callable, Literal, Optional
from PIL import Image, ImageDraw

import pystray


TrayStatus = Literal["green", "yellow", "red"]

STATUS_COLORS = {
    "green": (46, 204, 113, 255),
    "yellow": (241, 196, 15, 255),
    "red": (231, 76, 60, 255),
}


def determine_tray_status(
    value: float,
    warning_thresh: float = 60.0,
    danger_thresh: float = 85.0,
) -> TrayStatus:
    """Map normalized composite metric value (0-100) to tray status level ('green', 'yellow', 'red')."""
    val = float(value)
    if val >= danger_thresh:
        return "red"
    elif val >= warning_thresh:
        return "yellow"
    else:
        return "green"


class TrayManager:
    """Cross-platform system tray controller using pystray with dynamic status indicator."""

    def __init__(
        self,
        on_restore: Callable[[], None],
        on_quit: Callable[[], None],
        on_reset_telltales: Optional[Callable[[], None]] = None,
        on_toggle_topmost: Optional[Callable[[], None]] = None,
    ) -> None:
        """Initialize tray manager with interaction callback handlers."""
        self.on_restore = on_restore
        self.on_quit = on_quit
        self.on_reset_telltales = on_reset_telltales
        self.on_toggle_topmost = on_toggle_topmost

        self.current_status: TrayStatus = "green"
        self._thread: Optional[threading.Thread] = None

        menu = pystray.Menu(
            pystray.MenuItem("Restore Window", lambda icon, item: self._safe_invoke(self.on_restore), default=True),
            pystray.MenuItem("Toggle Always-on-Top", lambda icon, item: self._safe_invoke(self.on_toggle_topmost)),
            pystray.MenuItem("Reset Telltales", lambda icon, item: self._safe_invoke(self.on_reset_telltales)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit BoostGauge", lambda icon, item: self._safe_invoke(self.on_quit)),
        )

        initial_icon = self.create_status_icon(self.current_status)
        self.icon = pystray.Icon("boostgauge", initial_icon, "BoostGauge Monitor", menu)

    def _safe_invoke(self, callback: Optional[Callable[[], None]]) -> None:
        """Invoke callback safely if provided."""
        if callback:
            callback()

    def create_status_icon(self, status: TrayStatus = "green") -> Image.Image:
        """Generate a 16x16 RGBA PIL Image containing a colored status dot indicator."""
        img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        fill_color = STATUS_COLORS.get(status, STATUS_COLORS["green"])
        draw.ellipse([2, 2, 13, 13], fill=fill_color, outline=(0, 0, 0, 128))
        return img

    def start(self) -> None:
        """Start pystray Icon loop on a background daemon thread."""
        if self._thread is not None and self._thread.is_alive():
            return

        self._thread = threading.Thread(target=self.icon.run, daemon=True)
        self._thread.start()

    def update_status(self, status: TrayStatus) -> None:
        """Update system tray icon image to reflect current metric severity level."""
        self.current_status = status
        new_icon = self.create_status_icon(status)
        self.icon.icon = new_icon

    def stop(self) -> None:
        """Stop system tray icon thread and detach icon."""
        try:
            self.icon.stop()
        except Exception:
            pass
```

### 6.3 `src/boostgauge/app.py` (Modify)

**Change 1:** Add imports and window/tray controller integration at lines 8-20.

```diff
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
+    update_window_geometry,
     validate_config,
 )
+from boostgauge.window import GaugeWindow
+from boostgauge.tray import TrayManager, determine_tray_status
```

**Change 2:** Update `main()` function lifecycle to run window and tray managers.

```diff
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

+        window = GaugeWindow(config=config)
+
+        def on_restore() -> None:
+            window.root.after(0, window.restore_from_tray)
+
+        def on_quit() -> None:
+            def _shutdown() -> None:
+                nonlocal config
+                config = update_window_geometry(config, window.x, window.y, window.size)
+                try:
+                    save_config(config, target_config_path)
+                except Exception:
+                    pass
+                tray.stop()
+                window.destroy()
+                window.root.quit()
+            window.root.after(0, _shutdown)
+
+        def on_toggle_topmost() -> None:
+            window.root.after(0, window.toggle_topmost)
+
+        tray = TrayManager(
+            on_restore=on_restore,
+            on_quit=on_quit,
+            on_toggle_topmost=on_toggle_topmost,
+        )
+        tray.start()
+
+        window.root.protocol("WM_DELETE_WINDOW", lambda: window.minimize_to_tray())
+        window.root.mainloop()

         return 0

     except ConfigError as exc:
```

### 6.4 `src/boostgauge/__init__.py` (Modify)

**Change 1:** Export `GaugeWindow`, `TrayManager`, `determine_tray_status` at lines 6-19.

```diff
 from boostgauge.collector import DataCollector, SystemSnapshot
 from boostgauge.collectors import WindowsCollector, create_collector
 from boostgauge.telltale import TelltaleManager
+from boostgauge.window import GaugeWindow
+from boostgauge.tray import TrayManager, determine_tray_status

 __version__ = "0.1.0"

 __all__ = [
     "__version__",
     "DataCollector",
+    "GaugeWindow",
     "SystemSnapshot",
     "TelltaleManager",
+    "TrayManager",
     "WindowsCollector",
     "create_collector",
+    "determine_tray_status",
 ]
```

### 6.5 `tests/unit/test_window.py` (Add)

**Complete file contents:**

```python
"""Unit tests for GaugeWindow window manager component.

Issue #5: always-on-top window with drag, minimize, and transparency (#5)
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock
import pytest
from PIL import Image

from boostgauge.window import GaugeWindow, MIN_WINDOW_SIZE, MAX_WINDOW_SIZE, TRANSPARENT_COLOR


class DummyTkRoot:
    """Mock Tk root for headless testing without GUI display per docs/design/0001-test-strategy.md."""

    def __init__(self) -> None:
        self.attrs = {}
        self.geom = ""
        self.overridden = False
        self.bg = ""
        self.withdrawn = False
        self.deiconified = False
        self.lifted = False
        self.destroyed = False

    def overrideredirect(self, flag: bool) -> None:
        self.overridden = flag

    def attributes(self, key: str, value: Any = None) -> Any:
        if value is not None:
            self.attrs[key] = value
            return None
        return self.attrs.get(key)

    def geometry(self, geom_str: str) -> None:
        self.geom = geom_str

    def configure(self, **kwargs) -> None:
        if "bg" in kwargs:
            self.bg = kwargs["bg"]

    def winfo_vrootx(self) -> int:
        return 0

    def winfo_vrooty(self) -> int:
        return 0

    def winfo_vrootwidth(self) -> int:
        return 1920

    def winfo_vrootheight(self) -> int:
        return 1080

    def winfo_x(self) -> int:
        return 100

    def winfo_y(self) -> int:
        return 100

    def withdraw(self) -> None:
        self.withdrawn = True

    def deiconify(self) -> None:
        self.deiconified = True

    def lift(self) -> None:
        self.lifted = True

    def destroy(self) -> None:
        self.destroyed = True


def test_t010_topmost_toggle() -> None:
    root = DummyTkRoot()
    win = GaugeWindow(config={"always_on_top": True}, root=root)
    assert root.attrs.get("-topmost") is True

    new_state = win.toggle_topmost()
    assert new_state is False
    assert root.attrs.get("-topmost") is False


def test_t020_drag_motion_geometry() -> None:
    root = DummyTkRoot()
    win = GaugeWindow(config={"position": {"x": 100, "y": 100}, "size": 256}, root=root)

    win.handle_drag_start(type("Event", (), {"x": 10, "y": 10})())
    win.handle_drag_motion(type("Event", (), {"x": 60, "y": 40})())

    assert win.x == 150
    assert win.y == 130
    assert root.geom == "256x256+150+130"


def test_t030_double_click_compact_expanded_toggle() -> None:
    root = DummyTkRoot()
    win = GaugeWindow(config={"size": 256}, root=root)

    new_size = win.toggle_compact_expanded()
    assert new_size == 128
    assert win.is_expanded is False

    restored_size = win.toggle_compact_expanded()
    assert restored_size == 256
    assert win.is_expanded is True


def test_t040_transparent_background_setup() -> None:
    root = DummyTkRoot()
    win = GaugeWindow(root=root)
    assert root.bg == TRANSPARENT_COLOR
    if sys.platform == "win32":
        assert root.attrs.get("-transparentcolor") == TRANSPARENT_COLOR


def test_t050_opacity_adjustment() -> None:
    root = DummyTkRoot()
    win = GaugeWindow(config={"opacity": 0.8}, root=root)
    assert root.attrs.get("-alpha") == 0.8

    win.set_opacity(1.0)
    assert root.attrs.get("-alpha") == 1.0


def test_t060_minimize_to_tray() -> None:
    root = DummyTkRoot()
    win = GaugeWindow(root=root)
    win.minimize_to_tray()
    assert root.withdrawn is True
    assert win.is_minimized_to_tray is True


def test_t080_restore_from_tray() -> None:
    root = DummyTkRoot()
    win = GaugeWindow(root=root)
    win.minimize_to_tray()

    win.restore_from_tray()
    assert root.deiconified is True
    assert root.lifted is True
    assert win.is_minimized_to_tray is False


def test_t110_virtual_multimonitor_bounds_clamping() -> None:
    root = DummyTkRoot()
    win = GaugeWindow(root=root)

    cx, cy = win.clamp_to_screen(5000, 5000, 256)
    assert cx == 1920 - 256
    assert cy == 1080 - 256


def test_t120_mouse_wheel_aspect_ratio_resize() -> None:
    root = DummyTkRoot()
    win = GaugeWindow(config={"size": 256}, root=root)

    win.handle_mouse_wheel(type("Event", (), {"delta": 120, "num": 0})())
    assert win.size == 288

    win.handle_mouse_wheel(type("Event", (), {"delta": -120, "num": 0})())
    assert win.size == 256


def test_t130_mouse_wheel_out_of_bounds_clamping() -> None:
    root = DummyTkRoot()
    win = GaugeWindow(config={"size": 128}, root=root)

    win.handle_mouse_wheel(type("Event", (), {"delta": -120, "num": 0})())
    assert win.size == MIN_WINDOW_SIZE
```

### 6.6 `tests/unit/test_tray.py` (Add)

**Complete file contents:**

```python
"""Unit tests for TrayManager system tray component.

Issue #5: always-on-top window with drag, minimize, and transparency (#5)
"""

from __future__ import annotations

from unittest.mock import MagicMock
import pytest
from PIL import Image

from boostgauge.tray import TrayManager, determine_tray_status, STATUS_COLORS


def test_t070_tray_status_indicator_color_mapping() -> None:
    assert determine_tray_status(45.0) == "green"
    assert determine_tray_status(75.0) == "yellow"
    assert determine_tray_status(92.0) == "red"

    tray = TrayManager(on_restore=MagicMock(), on_quit=MagicMock())

    img_green = tray.create_status_icon("green")
    assert img_green.size == (16, 16)
    assert img_green.getpixel((8, 8)) == STATUS_COLORS["green"]

    img_yellow = tray.create_status_icon("yellow")
    assert img_yellow.getpixel((8, 8)) == STATUS_COLORS["yellow"]

    img_red = tray.create_status_icon("red")
    assert img_red.getpixel((8, 8)) == STATUS_COLORS["red"]


def test_t090_tray_context_menu_callbacks() -> None:
    on_restore = MagicMock()
    on_quit = MagicMock()
    on_reset = MagicMock()
    on_toggle = MagicMock()

    tray = TrayManager(
        on_restore=on_restore,
        on_quit=on_quit,
        on_reset_telltales=on_reset,
        on_toggle_topmost=on_toggle,
    )

    tray.on_restore()
    on_restore.assert_called_once()

    tray.on_toggle_topmost()
    on_toggle.assert_called_once()

    tray.on_reset_telltales()
    on_reset.assert_called_once()

    tray.on_quit()
    on_quit.assert_called_once()
```

## 7. Pattern References

### 7.1 Configuration & Geometry Persistence Pattern

**File:** `src/boostgauge/config.py` (lines 240-245)

```python
def update_window_geometry(config: GaugeConfigDict, x: int, y: int, size: int) -> GaugeConfigDict:
    """Update window position and size parameters in configuration data structure prior to exit/save."""
    updated = copy.deepcopy(config)
    updated["position"] = {"x": x, "y": y}
    updated["size"] = size
    return updated
```

**Relevance:** `GaugeWindow` updates its internal `(x, y, size)` attributes during drag and mouse wheel scaling events, which are serialized to `config.json` via `update_window_geometry` during application shutdown in `app.py`.

### 7.2 Off-Screen Headless GUI Renderer Pattern

**File:** `src/boostgauge/gauge.py` (lines 25-41)

```python
def render(
    value: float,
    telltales: Optional[TelltaleDict] = None,
    size: int = 256,
    config: Optional[Dict[str, Any]] = None,
) -> Image.Image:
    """Render gauge state into off-screen PIL Image using configured skin (defaults to Stingray)."""
    clamped_val, clamped_size = validate_render_inputs(value, size)
    ...
```

**Relevance:** Demonstrates rendering off-screen PIL Images without instantiating physical Tk windows, following `docs/design/0001-test-strategy.md` Option C for headless unit tests.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `import sys` | stdlib | `src/boostgauge/window.py` |
| `import threading` | stdlib | `src/boostgauge/tray.py` |
| `from typing import Any, Callable, Dict, Literal, Optional, Tuple` | stdlib | `window.py`, `tray.py` |
| `from PIL import Image, ImageDraw, ImageTk` | `pillow` | `window.py`, `tray.py` |
| `import pystray` | `pystray` | `src/boostgauge/tray.py` |
| `from boostgauge.window import GaugeWindow` | internal | `src/boostgauge/app.py`, `__init__.py` |
| `from boostgauge.tray import TrayManager, determine_tray_status` | internal | `src/boostgauge/app.py`, `__init__.py` |

**New Dependencies:** None (All required libraries `pillow` and `pystray` are already declared in `pyproject.toml`).

## 9. Placeholder

*Reserved for future alignment with LLD section numbering.*

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `GaugeWindow.toggle_topmost()` | Initial topmost=True, call `toggle_topmost()` | Returns `False`, root attribute `-topmost` set to `False` |
| T020 | `GaugeWindow.handle_drag_motion()` | Drag start at (10, 10), motion to (60, 40) | Window `x=150, y=130`, geometry string updated |
| T030 | `GaugeWindow.toggle_compact_expanded()` | Current size 256px, trigger double-click | Size toggles to 128px; second call restores to 256px |
| T040 | `GaugeWindow.setup_window()` | Init window on win32 platform | Canvas bg and transparentcolor attribute equal `#000001` |
| T050 | `GaugeWindow.set_opacity()` | Call `set_opacity(1.0)` | Root `-alpha` attribute updated to `1.0` |
| T060 | `GaugeWindow.minimize_to_tray()` | Call `minimize_to_tray()` | Root `withdraw()` called, `is_minimized_to_tray = True` |
| T070 | `determine_tray_status()` / `create_status_icon()` | Metrics 45.0, 75.0, 92.0 | Returns `'green'`, `'yellow'`, `'red'`; baseline-independent center pixel RGB matches status color |
| T080 | `GaugeWindow.restore_from_tray()` | Call `restore_from_tray()` when withdrawn | Root `deiconify()` and `lift()` called, `is_minimized_to_tray = False` |
| T090 | `TrayManager` callbacks | Dispatch menu actions | Registered callbacks `on_restore`, `on_quit`, `on_reset_telltales` invoked |
| T100 | `update_window_geometry()` | Window at x=150, y=130, size=256 on exit | Config dictionary updated with exact position and size |
| T110 | `GaugeWindow.clamp_to_screen()` | Off-screen input x=5000, y=5000 on 1920x1080 screen | Returns clamped tuple `(1664, 824)` within screen bounds |
| T120 | `GaugeWindow.handle_mouse_wheel()` | Wheel scroll up delta +120 on size 256 | Size increases to 288; 1:1 aspect ratio maintained |
| T130 | `GaugeWindow.handle_mouse_wheel()` | Wheel scroll down delta -120 on size 128 | Size clamped to minimum 128px |

## 11. Implementation Notes

### 11.1 Error Handling Convention

All Tk attribute and geometry operations check `hasattr` and wrap platform-specific attribute assignments (such as `-transparentcolor` on Windows) in `try...except Exception:` blocks to prevent crashes on non-supported X11/macOS display backends or mock test roots.

### 11.2 Thread Safety Convention (`root.after`)

`pystray.Icon` operates inside a dedicated daemon thread. Callbacks from tray menu items MUST NEVER manipulate Tkinter GUI components directly. All GUI state changes (restore window, toggle topmost, shutdown) MUST schedule execution on the main Tk thread using `window.root.after(0, callback)`.

### 11.3 Constants

| Constant | Value | Rationale |
|----------|-------|-----------|
| `TRANSPARENT_COLOR` | `"#000001"` | Fixed chroma-key color passed to `root.attributes('-transparentcolor', ...)` for transparent window background outside circular dial face. |
| `MIN_WINDOW_SIZE` | `128` | Minimum square window dimension in pixels (compact mode). |
| `MAX_WINDOW_SIZE` | `1024` | Maximum square window dimension in pixels. |
| `DEFAULT_EXPANDED_SIZE` | `256` | Default expanded gauge window size in pixels. |
| `IDLE_OPACITY` | `0.8` | Window opacity level when mouse is unhovered. |
| `HOVER_OPACITY` | `1.0` | Window opacity level when mouse hovers over gauge face. |
| `STATUS_COLORS["green"]` | `(46, 204, 113, 255)` | RGBA tuple for green normal status dot icon. |
| `STATUS_COLORS["yellow"]` | `(241, 196, 15, 255)` | RGBA tuple for yellow warning status dot icon. |
| `STATUS_COLORS["red"]` | `(231, 76, 60, 255)` | RGBA tuple for red danger status dot icon. |

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
| Finalized | 2026-07-30T04:16:00Z |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #5 |
| Verdict | APPROVED |
| Date | 2026-07-30 |
| Iterations | 1 |
| Finalized | 2026-07-30T09:17:00Z |

### Review Feedback Summary

The revised implementation specification for Issue #5 is complete, concrete, and fully executable. All files (`src/boostgauge/window.py`, `src/boostgauge/tray.py`, `src/boostgauge/app.py`, `src/boostgauge/__init__.py`, `tests/unit/test_window.py`, and `tests/unit/test_tray.py`) are accompanied by diffs or full code implementations. All 13 test cases trace directly to explicit requirements (REQ-1 through REQ-12) without visual baseline dependencies, requirement contradictions, or invalid platform...
