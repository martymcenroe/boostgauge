"""BoostGauge package initialization.

Issue #7: Configuration File and CLI Arguments
"""

from boostgauge.collector import DataCollector, SystemSnapshot
from boostgauge.collectors import WindowsCollector, create_collector
from boostgauge.telltale import TelltaleManager
from boostgauge.window import GaugeWindow
from boostgauge.tray import TrayManager, determine_tray_status

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "DataCollector",
    "GaugeWindow",
    "SystemSnapshot",
    "TelltaleManager",
    "TrayManager",
    "WindowsCollector",
    "create_collector",
    "determine_tray_status",
]