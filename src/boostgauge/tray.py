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