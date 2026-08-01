"""Main application entry point for BoostGauge.

Issue #5: Always-on-top window with drag, minimize, transparency, and tray icon.
"""

from __future__ import annotations

import atexit

import logging

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