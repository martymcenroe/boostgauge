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
        if self.icon is not None:
            self.icon.run()

    def _handle_restore(self, icon: Any, item: Any) -> None:
        self.on_restore()

    def _handle_toggle_topmost(self, icon: Any, item: Any) -> None:
        self.on_toggle_topmost()

    def _handle_quit(self, icon: Any, item: Any) -> None:
        self.stop()
        self.on_quit()