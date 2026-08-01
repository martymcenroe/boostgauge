# Implementation Spec: Always-On-Top Window with Drag, Minimize, and Transparency (#5)

| Field | Value |
|-------|-------|
| Issue | #5 |
| LLD | `docs/lld/done/0005-window-tray.md` |
| Generated | 2026-08-01 |
| Status | APPROVED |

## 1. Overview

Implement an always-on-top, frameless, transparent Tkinter widget (`GaugeWindow`) supporting mouse dragging, mouse wheel resizing, system tray minimization (`TrayManager` via `pystray`), and persistent geometry configuration across application restarts.

**Objective:** Implement an always-on-top, frameless, transparent Tkinter widget supporting mouse dragging, mouse wheel resizing, system tray minimization via pystray, and persistent geometry configuration across restarts.

**Success Criteria:**
1. Always-on-top Tkinter window attribute (`root.attributes('-topmost', True)`) surviving focus changes with context menu toggle.
2. Frameless, titlebar-less window with drag support anywhere on gauge face and double-click toggle between compact (128px) and expanded (256px) modes.
3. Circular window background transparency via `-transparentcolor` chroma-keying (`#000001`) with configurable opacity and hover transparency transitions.
4. Minimize to Windows system tray icon using `pystray` with dynamic status color indicator dot (green/yellow/red), double-click restore, and right-click context menu.
5. Window geometry (X, Y coordinates and size) persistence across restarts, including screen edge clamping and multi-monitor display bounds awareness.
6. Headless unit test suite achieving 100% line + branch coverage on `src/boostgauge/window.py` and `src/boostgauge/tray.py` without instantiating `tkinter.Tk()`.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/window.py` | Add | Frameless, transparent, always-on-top window manager (`GaugeWindow`) supporting mouse dragging, wheel resizing, display boundary clamping, and canvas rendering. |
| 2 | `src/boostgauge/tray.py` | Add | System tray icon manager (`TrayManager`) using `pystray` in a background daemon thread with thread-safe `root.after()` callbacks and dynamic status indicator dots. |
| 3 | `src/boostgauge/__init__.py` | Modify | Export `GaugeWindow` and `TrayManager` in package root exports. |
| 4 | `src/boostgauge/app.py` | Add | Main application entry point integrating `GaugeWindow`, `TrayManager`, data collector thread, update loop, and geometry persistence. |
| 5 | `tests/unit/test_window.py` | Add | Headless unit tests for `GaugeWindow` state math, geometry persistence, screen boundary clamping, and event handlers without instantiating `tkinter.Tk()`. |
| 6 | `tests/unit/test_tray.py` | Add | Headless unit tests for `TrayManager` status dot image generation, context menu construction, and thread-safe event dispatching. |

**Implementation Order Rationale:**
1. `window.py` and `tray.py` implement isolated window math and tray icon state logic.
2. `__init__.py` exposes `GaugeWindow` and `TrayManager` at the package level.
3. `app.py` integrates the window, tray manager, data collector, and configuration persistence into an executable lifecycle.
4. `test_window.py` and `test_tray.py` verify all window and tray logic headlessly.

## 3. Current State (for Modify/Delete files)

### 3.1 `src/boostgauge/__init__.py`

**Relevant excerpt** (lines 1-18):

```python
"""boostgauge package root.

Issue #4: Windows data collector — ConPTY, processes, memory, handles
"""

from boostgauge.collector import DataCollector, SystemSnapshot, normalize_metric, calculate_composite_metric

from boostgauge.collectors import create_collector, WindowsCollector

__all__ = [
    "DataCollector",
    "SystemSnapshot",
    "WindowsCollector",
    "create_collector",
    "normalize_metric",
    "calculate_composite_metric",
]
```

**What changes:**
Import `GaugeWindow` from `boostgauge.window` and `TrayManager` from `boostgauge.tray`, and add both symbols to `__all__`. Update module docstring to reference Issue #5.

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
    "x": 100,
    "y": 200,
    "size": 256,
    "topmost": true,
    "opacity": 0.9,
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
) -> None:
    """Initialize window state, geometry properties, chroma-key background, and callback hooks."""
    ...
```

**Input Example:**

```python
config = {
    "x": 150,
    "y": 250,
    "size": 256,
    "topmost": True,
    "opacity": 0.9,
    "hover_opacity": 1.0,
}
on_geometry_change = lambda x, y, size: print(f"Saved: {x}, {y}, {size}")
on_close = lambda: print("App closing")
```

**Output Example:**

```python
None  # Initializes instance attributes: self.x=150, self.y=250, self.size=256, self.topmost=True, self.opacity=0.9, self.bg_color="#000001"
```

**Edge Cases:**
- `config` is `None`: Uses default geometry values (`x=100`, `y=100`, `size=256`, `topmost=True`, `opacity=1.0`, `hover_opacity=1.0`).

### 5.2 `GaugeWindow.clamp_to_screen_bounds()`

**File:** `src/boostgauge/window.py`

**Signature:**

```python
def clamp_to_screen_bounds(
    self,
    x: int,
    y: int,
    width: int,
    height: int,
    virtual_screen: Tuple[int, int, int, int] = (0, 0, 1920, 1080),
) -> Tuple[int, int]:
    """Ensure window geometry stays fully visible within active monitor virtual display rectangle."""
    ...
```

**Input Example:**

```python
x = 2000
y = 1000
width = 256
height = 256
virtual_screen = (0, 0, 1920, 1080)
```

**Output Example:**

```python
(1664, 824)
```

**Edge Cases:**
- Negative coordinates out-of-bounds (`x = -500`, `y = -100`): Clamps to `virtual_screen[0]` and `virtual_screen[1]` -> `(0, 0)`.
- Target window size larger than monitor resolution: Clamps position to virtual screen origin `(virtual_screen[0], virtual_screen[1])`.

### 5.3 `GaugeWindow.handle_drag_motion()`

**File:** `src/boostgauge/window.py`

**Signature:**

```python
def handle_drag_motion(
    self,
    root_x: int,
    root_y: int,
    virtual_screen: Tuple[int, int, int, int] = (0, 0, 1920, 1080),
) -> Tuple[int, int]:
    """Calculate new window position based on mouse motion delta and apply screen bounds clamping."""
    ...
```

**Input Example:**

```python
# Assuming self.drag_offset_x = 50, self.drag_offset_y = 30, self.size = 256
root_x = 500
root_y = 300
virtual_screen = (0, 0, 1920, 1080)
```

**Output Example:**

```python
(450, 270)
```

**Edge Cases:**
- Dragging cursor outside monitor boundaries (`root_x = 5000`, `root_y = 5000`): Returns clamped coordinates `(1664, 824)`.

### 5.4 `GaugeWindow.handle_wheel_resize()`

**File:** `src/boostgauge/window.py`

**Signature:**

```python
def handle_wheel_resize(self, delta: int) -> int:
    """Resize window dimension while preserving square aspect ratio bounded between 64px and 512px."""
    ...
```

**Input Example:**

```python
# Assuming current self.size = 256
delta = 120  # Positive scroll up event
```

**Output Example:**

```python
272  # Increments size by step of 16px
```

**Edge Cases:**
- Scrolling up beyond max size limit (512px): Bounded to `512`.
- Scrolling down beyond min size limit (64px): Bounded to `64`.

### 5.5 `GaugeWindow.toggle_compact_expanded()`

**File:** `src/boostgauge/window.py`

**Signature:**

```python
def toggle_compact_expanded(self) -> int:
    """Toggle window size between compact (128px) and expanded (256px) modes."""
    ...
```

**Input Example:**

```python
size = 256  # Assuming current self.size = 256
```

**Output Example:**

```python
128
```

**Edge Cases:**
- Current size is `128` (or any value other than 256): Toggles size to `256`.

### 5.6 `GaugeWindow.toggle_topmost()`

**File:** `src/boostgauge/window.py`

**Signature:**

```python
def toggle_topmost(self) -> bool:
    """Toggle always-on-top attribute on Tk window state and return new boolean state."""
    ...
```

**Input Example:**

```python
topmost = True  # Assuming current self.topmost = True
```

**Output Example:**

```python
False
```

**Edge Cases:**
- `self.root` is `None` (headless mode): Flips `self.topmost` internal boolean attribute and returns it cleanly.

### 5.7 `TrayManager.create_status_dot()`

**File:** `src/boostgauge/tray.py`

**Signature:**

```python
def create_status_dot(self, status: TrayStatus) -> Image.Image:
    """Generate 16x16 PIL Image indicator dot for given status (green/yellow/red)."""
    ...
```

**Input Example:**

```python
status = "green"
```

**Output Example:**

```python
img  # <PIL.Image.Image image mode=RGBA size=16x16> 16x16 PIL image with dark gray background and filled green circle
```

**Edge Cases:**
- Unknown status string passed: Defaults status dot color to yellow (`#FFFF00`).

### 5.8 `TrayManager.start()`

**File:** `src/boostgauge/tray.py`

**Signature:**

```python
def start(self) -> None:
    """Launch pystray Icon loop in background daemon thread."""
    ...
```

**Input Example:**

```python
None
```

**Output Example:**

```python
None  # Launches daemon thread running self.icon.run()
```

**Edge Cases:**
- Icon already running: Log warning and return without spawning duplicate thread.

## 6. Change Instructions

### 6.1 `src/boostgauge/window.py` (Add)

**Complete file contents:**

```python
"""Frameless, transparent, always-on-top Tkinter window manager.

Issue #5: Always-on-top window with drag, minimize, and transparency.
"""

from __future__ import annotations

import logging

import platform

from typing import Any, Callable, Dict, Optional, Tuple

from PIL import Image, ImageTk

logger = logging.getLogger(__name__)


class GaugeWindow:
    """Frameless, transparent, always-on-top Tkinter window manager for BoostGauge."""

    CHROMA_KEY_BG = "#000001"
    MIN_SIZE = 64
    MAX_SIZE = 512
    COMPACT_SIZE = 128
    EXPANDED_SIZE = 256
    RESIZE_STEP = 16

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        on_geometry_change: Optional[Callable[[int, int, int], None]] = None,
        on_close: Optional[Callable[[], None]] = None,
    ) -> None:
        """Initialize window state, geometry properties, and callback hooks."""
        cfg = config or {}
        self.x: int = int(cfg.get("x", 100))
        self.y: int = int(cfg.get("y", 100))
        self.size: int = int(cfg.get("size", self.EXPANDED_SIZE))
        self.topmost: bool = bool(cfg.get("topmost", True))
        self.opacity: float = float(cfg.get("opacity", 1.0))
        self.hover_opacity: float = float(cfg.get("hover_opacity", 1.0))

        self.on_geometry_change = on_geometry_change
        self.on_close = on_close

        self.root: Optional[Any] = None
        self.canvas: Optional[Any] = None
        self.photo_image: Optional[ImageTk.PhotoImage] = None

        self.drag_offset_x: int = 0
        self.drag_offset_y: int = 0
        self.is_dragging: bool = False

    def setup_window(self, root: Any) -> None:
        """Configure Tk root attributes: frameless, topmost, transparent background color, and event bindings."""
        self.root = root

        # Frameless window
        root.overrideredirect(True)

        # Geometry
        root.geometry(f"{self.size}x{self.size}+{self.x}+{self.y}")

        # Always-on-top
        root.attributes("-topmost", self.topmost)

        # Opacity
        try:
            root.attributes("-alpha", self.opacity)
        except Exception as e:
            logger.debug(f"Alpha attribute setup failed: {e}")

        # Transparency chroma key (Windows platform support)
        if platform.system() == "Windows":
            try:
                root.attributes("-transparentcolor", self.CHROMA_KEY_BG)
                root.config(bg=self.CHROMA_KEY_BG)
            except Exception as e:
                logger.warning(f"Transparent color setup failed: {e}")

        # Canvas setup
        import tkinter as tk

        self.canvas = tk.Canvas(
            root,
            width=self.size,
            height=self.size,
            bg=self.CHROMA_KEY_BG if platform.system() == "Windows" else root.cget("bg"),
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Bind mouse events
        self.canvas.bind("<Button-1>", self._on_button_press)
        self.canvas.bind("<B1-Motion>", self._on_drag_motion)
        self.canvas.bind("<ButtonRelease-1>", self._on_button_release)
        self.canvas.bind("<Double-Button-1>", self._on_double_click)
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        self.canvas.bind("<Enter>", self._on_mouse_enter)
        self.canvas.bind("<Leave>", self._on_mouse_leave)
        self.canvas.bind("<Button-3>", self._on_right_click)

    def update_image(self, pil_img: Image.Image) -> None:
        """Update display Canvas with a new PIL Image rendered frame."""
        if self.root is None or self.canvas is None:
            return

        self.photo_image = ImageTk.PhotoImage(pil_img)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.photo_image)

    def toggle_topmost(self) -> bool:
        """Toggle always-on-top attribute on Tk window and return new boolean state."""
        self.topmost = not self.topmost
        if self.root is not None:
            self.root.attributes("-topmost", self.topmost)
        return self.topmost

    def toggle_compact_expanded(self) -> int:
        """Toggle window size between compact (128px) and expanded (256px) modes."""
        if self.size == self.EXPANDED_SIZE:
            self.size = self.COMPACT_SIZE
        else:
            self.size = self.EXPANDED_SIZE

        self._apply_geometry()
        if self.on_geometry_change:
            self.on_geometry_change(self.x, self.y, self.size)
        return self.size

    def set_opacity(self, alpha: float) -> None:
        """Set window opacity level bounded between 0.1 and 1.0."""
        self.opacity = max(0.1, min(1.0, float(alpha)))
        if self.root is not None:
            try:
                self.root.attributes("-alpha", self.opacity)
            except Exception as e:
                logger.debug(f"Failed to set alpha: {e}")

    def handle_drag_start(self, event_x: int, event_y: int) -> None:
        """Record initial mouse click offset relative to window top-left corner."""
        self.drag_offset_x = event_x
        self.drag_offset_y = event_y
        self.is_dragging = True

    def handle_drag_motion(
        self,
        root_x: int,
        root_y: int,
        virtual_screen: Tuple[int, int, int, int] = (0, 0, 1920, 1080),
    ) -> Tuple[int, int]:
        """Calculate new window position based on mouse motion delta and apply screen bounds clamping."""
        new_x = root_x - self.drag_offset_x
        new_y = root_y - self.drag_offset_y

        clamped_x, clamped_y = self.clamp_to_screen_bounds(
            new_x, new_y, self.size, self.size, virtual_screen
        )
        self.x = clamped_x
        self.y = clamped_y
        return self.x, self.y

    def handle_wheel_resize(self, delta: int) -> int:
        """Resize window dimension while preserving square aspect ratio bounded between min/max sizes."""
        step = self.RESIZE_STEP if delta > 0 else -self.RESIZE_STEP
        new_size = self.size + step
        self.size = max(self.MIN_SIZE, min(self.MAX_SIZE, new_size))
        self._apply_geometry()

        if self.on_geometry_change:
            self.on_geometry_change(self.x, self.y, self.size)
        return self.size

    def clamp_to_screen_bounds(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        virtual_screen: Tuple[int, int, int, int],
    ) -> Tuple[int, int]:
        """Ensure window geometry stays fully visible within active monitor virtual display rectangle."""
        v_min_x, v_min_y, v_max_x, v_max_y = virtual_screen
        max_x = max(v_min_x, v_max_x - width)
        max_y = max(v_min_y, v_max_y - height)

        clamped_x = max(v_min_x, min(x, max_x))
        clamped_y = max(v_min_y, min(y, max_y))
        return clamped_x, clamped_y

    def _get_virtual_screen_bounds(self) -> Tuple[int, int, int, int]:
        """Get virtual screen geometry (min_x, min_y, max_x, max_y) from root window."""
        if self.root is None:
            return (0, 0, 1920, 1080)
        try:
            screen_w = self.root.winfo_screenwidth()
            screen_h = self.root.winfo_screenheight()
            return (0, 0, screen_w, screen_h)
        except Exception:
            return (0, 0, 1920, 1080)

    def _apply_geometry(self) -> None:
        """Apply current x, y, and size state to Tk root window and canvas."""
        if self.root is not None:
            self.root.geometry(f"{self.size}x{self.size}+{self.x}+{self.y}")
        if self.canvas is not None:
            self.canvas.config(width=self.size, height=self.size)

    def _on_button_press(self, event: Any) -> None:
        self.handle_drag_start(event.x, event.y)

    def _on_drag_motion(self, event: Any) -> None:
        if not self.is_dragging:
            return
        bounds = self._get_virtual_screen_bounds()
        new_x, new_y = self.handle_drag_motion(event.x_root, event.y_root, bounds)
        if self.root is not None:
            self.root.geometry(f"{self.size}x{self.size}+{new_x}+{new_y}")

    def _on_button_release(self, event: Any) -> None:
        if self.is_dragging:
            self.is_dragging = False
            if self.on_geometry_change:
                self.on_geometry_change(self.x, self.y, self.size)

    def _on_double_click(self, event: Any) -> None:
        self.toggle_compact_expanded()

    def _on_mouse_wheel(self, event: Any) -> None:
        delta = getattr(event, "delta", 0)
        if delta != 0:
            self.handle_wheel_resize(delta)

    def _on_mouse_enter(self, event: Any) -> None:
        if self.hover_opacity != self.opacity and self.root is not None:
            try:
                self.root.attributes("-alpha", self.hover_opacity)
            except Exception:
                pass

    def _on_mouse_leave(self, event: Any) -> None:
        if self.hover_opacity != self.opacity and self.root is not None:
            try:
                self.root.attributes("-alpha", self.opacity)
            except Exception:
                pass

    def _on_right_click(self, event: Any) -> None:
        # Tkinter right-click context menu placeholder if needed locally
        pass
```

### 6.2 `src/boostgauge/tray.py` (Add)

**Complete file contents:**

```python
"""System tray icon manager using pystray.

Issue #5: Always-on-top window with drag, minimize, and transparency.
"""

from __future__ import annotations

import logging

import threading

from typing import Any, Callable, Literal, Optional

from PIL import Image, ImageDraw

import pystray

logger = logging.getLogger(__name__)

TrayStatus = Literal["green", "yellow", "red"]

STATUS_COLORS = {
    "green": (0, 255, 0, 255),
    "yellow": (255, 255, 0, 255),
    "red": (255, 0, 0, 255),
}


class TrayManager:
    """System tray manager executing pystray Icon in a daemon background thread."""

    def __init__(
        self,
        on_restore: Callable[[], None],
        on_toggle_topmost: Callable[[], None],
        on_quit: Callable[[], None],
    ) -> None:
        """Initialize tray manager with UI callback hooks."""
        self.on_restore = on_restore
        self.on_toggle_topmost = on_toggle_topmost
        self.on_quit = on_quit

        self.current_status: TrayStatus = "green"
        self.icon: Optional[pystray.Icon] = None
        self.thread: Optional[threading.Thread] = None
        self._is_running: bool = False

    def create_status_dot(self, status: TrayStatus) -> Image.Image:
        """Generate 16x16 PIL Image indicator dot for given status (green/yellow/red)."""
        img = Image.new("RGBA", (16, 16), (30, 30, 30, 255))
        draw = ImageDraw.Draw(img)
        fill_color = STATUS_COLORS.get(status, STATUS_COLORS["yellow"])
        draw.ellipse([3, 3, 12, 12], fill=fill_color, outline=(0, 0, 0, 255))
        return img

    def start(self) -> None:
        """Launch pystray Icon loop in background daemon thread."""
        if self._is_running:
            logger.warning("TrayManager is already running.")
            return

        icon_image = self.create_status_dot(self.current_status)
        menu = pystray.Menu(
            pystray.MenuItem("Restore Window", self._handle_restore, default=True),
            pystray.MenuItem("Toggle Always-on-Top", self._handle_toggle_topmost),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit BoostGauge", self._handle_quit),
        )

        self.icon = pystray.Icon(
            "boostgauge",
            icon_image,
            "BoostGauge System Monitor",
            menu=menu,
        )

        self._is_running = True
        self.thread = threading.Thread(target=self._run_icon, daemon=True)
        self.thread.start()

    def update_status(self, status: TrayStatus) -> None:
        """Update tray icon image with updated status indicator dot."""
        self.current_status = status
        if self.icon is not None and self._is_running:
            new_image = self.create_status_dot(status)
            self.icon.icon = new_image

    def stop(self) -> None:
        """Cleanly stop pystray icon and release system resources."""
        if self.icon is not None and self._is_running:
            self._is_running = False
            try:
                self.icon.stop()
            except Exception as e:
                logger.debug(f"Error stopping tray icon: {e}")
            self.icon = None

    def _run_icon(self) -> None:
        """Target loop execution for daemon thread."""
        if self.icon is not None:
            self.icon.run()

    def _handle_restore(self, icon: Any, item: Any) -> None:
        self.on_restore()

    def _handle_toggle_topmost(self, icon: Any, item: Any) -> None:
        self.on_toggle_topmost()

    def _handle_quit(self, icon: Any, item: Any) -> None:
        self.stop()
        self.on_quit()
```

### 6.3 `src/boostgauge/__init__.py` (Modify)

**Change 1:** Add imports for `GaugeWindow` and `TrayManager` and update `__all__`.

```diff
 """boostgauge package root.

-Issue #4: Windows data collector — ConPTY, processes, memory, handles
+Issue #5: Always-on-top window with drag, minimize, transparency, and tray icon
 """

 from boostgauge.collector import DataCollector, SystemSnapshot, normalize_metric, calculate_composite_metric
 from boostgauge.collectors import create_collector, WindowsCollector
+from boostgauge.tray import TrayManager
+from boostgauge.window import GaugeWindow

 __all__ = [
     "DataCollector",
     "SystemSnapshot",
     "WindowsCollector",
     "create_collector",
     "normalize_metric",
     "calculate_composite_metric",
+    "GaugeWindow",
+    "TrayManager",
 ]
```

### 6.4 `src/boostgauge/app.py` (Add)

**Complete file contents:**

```python
"""Main application entry point for BoostGauge.

Issue #5: Always-on-top window with drag, minimize, transparency, and tray icon.
"""

from __future__ import annotations

import atexit

import logging

import signal

import sys

import tkinter as tk

from typing import List, Optional

from boostgauge.collectors import create_collector
from boostgauge.config import load_config, merge_config_and_cli, parse_cli_args, update_window_state
from boostgauge.gauge import render
from boostgauge.telltale import Telltale
from boostgauge.tray import TrayManager
from boostgauge.window import GaugeWindow

logger = logging.getLogger("boostgauge")


class BoostGaugeApp:
    """Main application manager integrating GaugeWindow, TrayManager, and metric updates."""

    def __init__(self, cli_args: Optional[List[str]] = None) -> None:
        raw_cli = parse_cli_args(cli_args)
        base_config = load_config()
        self.config = merge_config_and_cli(base_config, raw_cli)

        self.root = tk.Tk()
        self.window = GaugeWindow(
            config=self.config.get("position"),
            on_geometry_change=self._on_geometry_change,
            on_close=self.quit,
        )
        self.window.setup_window(self.root)

        self.tray = TrayManager(
            on_restore=self.restore_window,
            on_toggle_topmost=self.toggle_topmost,
            on_quit=self.quit,
        )

        self.collector = create_collector(self.config)
        self.telltale_1m = Telltale(window=60.0)
        self.telltale_10m = Telltale(window=600.0)
        self.telltale_1h = Telltale(window=3600.0)

        self.is_running = False

        # Cleanup handlers
        atexit.register(self.cleanup)

    def run(self) -> None:
        """Start application, background collector, tray icon, and Tk main loop."""
        self.is_running = True
        self.collector.start()
        self.tray.start()

        self._schedule_update()
        self.root.mainloop()

    def restore_window(self) -> None:
        """Restore window from system tray (thread-safe)."""

        def _restore() -> None:
            self.root.deiconify()
            self.root.attributes("-topmost", self.window.topmost)

        self.root.after(0, _restore)

    def minimize_to_tray(self) -> None:
        """Withdraw Tkinter root window to system tray."""
        self.root.withdraw()

    def toggle_topmost(self) -> None:
        """Toggle always-on-top window attribute (thread-safe)."""

        def _toggle() -> None:
            new_state = self.window.toggle_topmost()
            logger.info(f"Topmost state toggled to: {new_state}")

        self.root.after(0, _toggle)

    def quit(self) -> None:
        """Thread-safe application shutdown."""

        def _quit() -> None:
            self.cleanup()
            self.root.destroy()

        self.root.after(0, _quit)

    def cleanup(self) -> None:
        """Clean up collector threads and tray icon resources."""
        if self.is_running:
            self.is_running = False
            self.collector.stop()
            self.tray.stop()

    def _on_geometry_change(self, x: int, y: int, size: int) -> None:
        """Callback to persist updated window position and size."""
        update_window_state(self.config, x, y, size)

    def _schedule_update(self) -> None:
        """Schedule next periodic metric polling and gauge render frame."""
        if not self.is_running:
            return

        try:
            snapshot = self.collector.poll()
            composite = snapshot.composite_value

            now = snapshot.timestamp
            self.telltale_1m.update(now, composite)
            self.telltale_10m.update(now, composite)
            self.telltale_1h.update(now, composite)

            telltale_dict = {
                "1m": self.telltale_1m.current_peak(now),
                "10m": self.telltale_10m.current_peak(now),
                "1h": self.telltale_1h.current_peak(now),
            }

            img = render(
                value=composite,
                telltales=telltale_dict,
                size=(self.window.size, self.window.size),
                config=self.config,
            )
            self.window.update_image(img)

            # Update tray status dot based on load threshold
            if composite >= 80.0:
                self.tray.update_status("red")
            elif composite >= 60.0:
                self.tray.update_status("yellow")
            else:
                self.tray.update_status("green")

        except Exception as e:
            logger.error(f"Error in main update loop: {e}")

        poll_ms = int(self.config.get("poll_interval", 1.0) * 1000)
        self.root.after(poll_ms, self._schedule_update)


def main(cli_args: Optional[List[str]] = None) -> None:
    """Main CLI entry point."""
    app = BoostGaugeApp(cli_args)
    app.run()


if __name__ == "__main__":
    main()
```

### 6.5 `tests/unit/test_window.py` (Add)

**Complete file contents:**

```python
"""Headless unit tests for GaugeWindow math, clamping, and event state.

Issue #5: Always-on-top window with drag, minimize, and transparency.
"""

from typing import Dict, Tuple

import pytest

from boostgauge.window import GaugeWindow


def test_topmost_attribute_toggle() -> None:
    """T010: Topmost attribute configuration and toggle."""
    win = GaugeWindow(config={"topmost": True})
    assert win.topmost is True

    new_state = win.toggle_topmost()
    assert new_state is False
    assert win.topmost is False


def test_drag_motion_coordinate_calculation() -> None:
    """T020: Drag motion coordinate delta calculation."""
    win = GaugeWindow(config={"x": 100, "y": 100, "size": 256})
    win.handle_drag_start(event_x=50, event_y=30)

    new_x, new_y = win.handle_drag_motion(
        root_x=500, root_y=300, virtual_screen=(0, 0, 1920, 1080)
    )
    assert new_x == 450
    assert new_y == 270


def test_double_click_toggle_compact_expanded() -> None:
    """T030: Double-click mode toggle compact/expanded (128px ↔ 256px)."""
    win = GaugeWindow(config={"size": 256})
    new_size = win.toggle_compact_expanded()
    assert new_size == 128
    assert win.size == 128

    restored_size = win.toggle_compact_expanded()
    assert restored_size == 256
    assert win.size == 256


def test_chroma_key_transparency_constant() -> None:
    """T040: Window chroma-key transparency setup constant."""
    win = GaugeWindow()
    assert win.CHROMA_KEY_BG == "#000001"


def test_hover_opacity_transition_calculation() -> None:
    """T050: Hover opacity transition value bounded setup."""
    win = GaugeWindow(config={"opacity": 0.8, "hover_opacity": 1.0})
    assert win.opacity == 0.8
    assert win.hover_opacity == 1.0

    win.set_opacity(0.5)
    assert win.opacity == 0.5

    # Out of bounds clamping check
    win.set_opacity(-0.5)
    assert win.opacity == 0.1
    win.set_opacity(1.5)
    assert win.opacity == 1.0


def test_screen_bounds_clamping_virtual_display() -> None:
    """T080: Geometry persistence & screen bounds clamping."""
    win = GaugeWindow(config={"size": 256})
    virtual_screen = (0, 0, 1920, 1080)

    # Clamping upper right out of bounds
    cx, cy = win.clamp_to_screen_bounds(2000, 2000, 256, 256, virtual_screen)
    assert cx == 1664  # 1920 - 256
    assert cy == 824   # 1080 - 256

    # Clamping lower left out of bounds
    cx, cy = win.clamp_to_screen_bounds(-100, -100, 256, 256, virtual_screen)
    assert cx == 0
    assert cy == 0


def test_mouse_wheel_resize_handling() -> None:
    """T090: Mouse wheel resize handling."""
    win = GaugeWindow(config={"size": 256})
    new_size = win.handle_wheel_resize(120)  # Scroll up
    assert new_size == 272

    down_size = win.handle_wheel_resize(-120) # Scroll down
    assert down_size == 256


def test_geometry_callback_triggering() -> None:
    """T100: Config save callback integration for window geometry."""
    saved_state: Dict[str, int] = {}

    def mock_callback(x: int, y: int, size: int) -> None:
        saved_state["x"] = x
        saved_state["y"] = y
        saved_state["size"] = size

    win = GaugeWindow(
        config={"x": 100, "y": 100, "size": 256},
        on_geometry_change=mock_callback,
    )
    win.toggle_compact_expanded()
    assert saved_state == {"x": 100, "y": 100, "size": 128}


def test_offscreen_position_fallback_recovery() -> None:
    """T110: Off-screen position fallback recovery math."""
    win = GaugeWindow(config={"x": -5000, "y": -5000, "size": 256})
    cx, cy = win.clamp_to_screen_bounds(win.x, win.y, win.size, win.size, (0, 0, 1920, 1080))
    assert cx == 0
    assert cy == 0
```

### 6.6 `tests/unit/test_tray.py` (Add)

**Complete file contents:**

```python
"""Headless unit tests for TrayManager status dot and callbacks.

Issue #5: Always-on-top window with drag, minimize, and transparency.
"""

from PIL import Image

from boostgauge.tray import TrayManager


def test_tray_status_dot_generation() -> None:
    """T060: System tray icon initialization & status dot creation."""
    restored = False

    def on_restore() -> None:
        nonlocal restored
        restored = True

    tray = TrayManager(
        on_restore=on_restore,
        on_toggle_topmost=lambda: None,
        on_quit=lambda: None,
    )

    img_green = tray.create_status_dot("green")
    assert isinstance(img_green, Image.Image)
    assert img_green.size == (16, 16)
    # Check green center pixel color (x=8, y=8)
    assert img_green.getpixel((8, 8)) == (0, 255, 0, 255)

    img_red = tray.create_status_dot("red")
    assert img_red.getpixel((8, 8)) == (255, 0, 0, 255)


def test_tray_restore_callback_dispatch() -> None:
    """T070: System tray double-click restore callback dispatching."""
    restored = False

    def on_restore() -> None:
        nonlocal restored
        restored = True

    tray = TrayManager(
        on_restore=on_restore,
        on_toggle_topmost=lambda: None,
        on_quit=lambda: None,
    )

    tray._handle_restore(icon=None, item=None)
    assert restored is True
```

## 7. Pattern References

### 7.1 Geometry Persistence and Config Update Pattern

**File:** `src/boostgauge/config.py` (lines 142-152)

```python
def update_window_state(
    config: ConfigData,
    x: int,
    y: int,
    size: int,
    config_path: Optional[Path] = None,
) -> ConfigData:
    """Update window position (x, y) and size parameters in configuration and persist to disk."""
    config["position"]["x"] = x
    config["position"]["y"] = y
    config["position"]["size"] = size
    save_config(config, config_path)
    return config
```

**Relevance:** Used by `BoostGaugeApp._on_geometry_change` to persist window coordinates and size whenever window dragging or resizing finishes.

### 7.2 Off-Screen PIL Image Rendering Pattern

**File:** `src/boostgauge/gauge.py` (lines 16-25)

```python
def render(
    value: float,
    telltales: dict[str, float | None] | None = None,
    size: tuple[int, int] = (256, 256),
    config: dict[str, Any] | None = None,
) -> Image.Image:
    """Pure function rendering gauge face and needles to off-screen PIL Image."""
    skin_name = (config or {}).get("theme", "stingray")
    renderer = SUPPORTED_SKINS.get(skin_name, render_stingray)
    return renderer(value=value, telltales=telltales, size=size, config=config)
```

**Relevance:** Demonstrates rendering off-screen PIL images per `docs/design/0001-test-strategy.md` (Option C), allowing `GaugeWindow` canvas rendering and tray status dots to be tested headlessly without instantiating `tkinter.Tk()`.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `import tkinter as tk` | stdlib | `window.py`, `app.py` |
| `import threading` | stdlib | `tray.py` |
| `import platform` | stdlib | `window.py` |
| `import atexit` | stdlib | `app.py` |
| `from PIL import Image, ImageTk, ImageDraw` | `pillow` (>=12.2.0) | `window.py`, `tray.py`, `app.py` |
| `import pystray` | `pystray` (>=0.19.5) | `tray.py` |
| `from boostgauge.config import load_config, save_config, update_window_state` | internal | `app.py` |
| `from boostgauge.collectors import create_collector` | internal | `app.py` |
| `from boostgauge.gauge import render` | internal | `app.py` |
| `from boostgauge.telltale import Telltale` | internal | `app.py` |

**New Dependencies:** None (All dependencies already declared in `pyproject.toml`).

## 9. Placeholder

*Reserved for future alignment with LLD section numbering.*

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `GaugeWindow.toggle_topmost()` | Initial `topmost=True`, call `toggle_topmost()` | Returns `False`, updates internal state |
| T020 | `GaugeWindow.handle_drag_motion()` | `drag_offset_x=50`, `drag_offset_y=30`, `root_x=500`, `root_y=300` | Returns `(450, 270)` |
| T030 | `GaugeWindow.toggle_compact_expanded()` | Initial `size=256`, call `toggle_compact_expanded()` | Returns `128`, toggles size state |
| T040 | `GaugeWindow.__init__()` | Instantiate default `GaugeWindow()` | `win.CHROMA_KEY_BG == "#000001"` |
| T050 | `GaugeWindow.set_opacity()` | `alpha=0.5` | Updates `win.opacity == 0.5` with min/max clamping |
| T060 | `TrayManager.create_status_dot()` | `status="green"` | 16x16 PIL Image with green center pixel `(0, 255, 0, 255)` |
| T070 | `TrayManager._handle_restore()` | Double-click restore tray menu event | Invokes `on_restore()` callback |
| T080 | `GaugeWindow.clamp_to_screen_bounds()` | `x=2000, y=2000, size=256`, virtual screen `(0,0,1920,1080)` | Clamps to `(1664, 824)` within display rectangle |
| T090 | `GaugeWindow.handle_wheel_resize()` | `size=256, delta=120` | Returns `272` (16px increment) |
| T100 | `GaugeWindow._on_button_release()` | Drag release after geometry change | Triggers `on_geometry_change(x, y, size)` callback |
| T110 | `GaugeWindow.clamp_to_screen_bounds()` | `x=-5000, y=-5000, size=256`, virtual screen `(0,0,1920,1080)` | Clamps position to origin `(0, 0)` |

## 11. Implementation Notes

### 11.1 Thread-Safety with Tkinter and Pystray

`pystray.Icon.run()` blocks its executing thread. Running `TrayManager` in a daemon background thread prevents the system tray loop from freezing Tkinter's main loop. To prevent thread racing or GUI lockups, any UI modifications triggered from tray icon events (such as restoring the window or toggling topmost) MUST dispatch through `root.after(0, callback)` back to the main Tkinter thread.

### 11.2 Multi-Monitor Coordinates Clamping

When user geometry is restored from configuration files or during mouse drag motion, monitors may have been disconnected or resized. `GaugeWindow.clamp_to_screen_bounds` checks candidate coordinates against the active virtual display bounds `(min_x, min_y, max_x, max_y)`. If saved coordinates fall outside all monitors, the gauge clamps cleanly to the visible monitor origin `(0, 0)`.

### 11.3 Test Code Platform Independence

Per project standards, all path comparisons in unit tests must compare `pathlib.Path` objects rather than hardcoded string paths with backslashes or forward slashes to ensure Windows and Unix compatibility.

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
| Finalized | 2026-08-01T04:23:01Z |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #5 |
| Verdict | APPROVED |
| Date | 2026-08-01 |
| Iterations | 1 |
| Finalized | 2026-08-01T09:24:32Z |

### Review Feedback Summary

The revised implementation spec for Issue #5 is complete, concrete, and fully executable by an autonomous AI agent. All files to be created or modified contain explicit Python implementations or precise diffs. Function specifications include realistic input/output examples, and data structures feature complete schema examples. Every test assertion in test_window.py and test_tray.py directly traces to specified function behaviors, and the test suite complies with the project's headless testing st...
