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
        """Poll and execute all pending events from the system tray thread."""
        try:
            while True:
                event = self.event_queue.get_nowait()
                try:
                    self._handle_tray_event(event)
                except Exception as e:
                    logger.error(f"Error handling tray event {event}: {e}")
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