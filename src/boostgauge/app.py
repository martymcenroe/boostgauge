"""Application runtime controller integration for BoostGauge.

Issue #7: Configuration File and CLI Arguments
Integrates configuration lifecycle with window manager and metric polling.
"""

from pathlib import Path
from typing import Optional

from boostgauge.config import GaugeConfigDict, update_window_geometry


class BoostGaugeApp:
    """Application lifecycle controller."""

    def __init__(self, config: GaugeConfigDict, config_path: Path) -> None:
        self.config = config
        self.config_path = config_path
        self._is_running = False

    def run(self) -> int:
        """Start the application event loop (stub for CLI main entry)."""
        self._is_running = True
        return 0

    def shutdown(
        self,
        current_x: Optional[int] = None,
        current_y: Optional[int] = None,
        current_size: Optional[int] = None,
    ) -> None:
        """Persist final window position and size on application exit."""
        x = current_x if current_x is not None else self.config["position"]["x"]
        y = current_y if current_y is not None else self.config["position"]["y"]
        size = current_size if current_size is not None else self.config["size"]

        self.config = update_window_geometry(self.config, self.config_path, x, y, size)
        self._is_running = False