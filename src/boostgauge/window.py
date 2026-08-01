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

        root.overrideredirect(True)
        root.geometry(f"{self.size}x{self.size}+{self.x}+{self.y}")
        root.attributes("-topmost", self.topmost)

        try:
            root.attributes("-alpha", self.opacity)
        except Exception as e:
            logger.debug(f"Alpha attribute setup failed: {e}")

        if platform.system() == "Windows":
            try:
                root.attributes("-transparentcolor", self.CHROMA_KEY_BG)
                root.config(bg=self.CHROMA_KEY_BG)
            except Exception as e:
                logger.warning(f"Transparent color setup failed: {e}")

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
        pass