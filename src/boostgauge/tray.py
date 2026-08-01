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
        """Create a PIL Image with a status dot indicator."""
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