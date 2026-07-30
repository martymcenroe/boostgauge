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
        self._photo_image: Optional[Any] = None

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

        if hasattr(self.root, "title"):
            try:
                import tkinter as tk
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
            except Exception:
                self.canvas = None

    def update_image(self, pil_img: Image.Image) -> None:
        """Update display Canvas with a new PIL Image rendered frame."""
        if self.canvas is None:
            return

        resized = pil_img.resize((self.size, self.size), Image.Resampling.LANCZOS)
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