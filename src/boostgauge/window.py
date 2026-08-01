"""Window geometry controller and Tkinter surface implementation.

Issue #5: Feature: always-on-top window with drag, minimize, and transparency
"""

import logging
from typing import Any, Callable, Optional, Tuple

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