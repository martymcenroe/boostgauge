"""boostgauge package root.

Issue #5: Always-on-top window with drag, minimize, transparency, and tray icon
"""

from boostgauge.collector import DataCollector, SystemSnapshot, normalize_metric, calculate_composite_metric

from boostgauge.collectors import create_collector, WindowsCollector

from boostgauge.tray import TrayManager

from boostgauge.window import GaugeWindow

__all__ = [
    "DataCollector",
    "SystemSnapshot",
    "WindowsCollector",
    "create_collector",
    "normalize_metric",
    "calculate_composite_metric",
    "GaugeWindow",
    "TrayManager",
]