"""BoostGauge system monitor package.

Issue #7: Configuration File and CLI Arguments
"""

from boostgauge.config import AppConfig, ConfigManager, WindowPosition, ThresholdsConfig, ThresholdPair
from boostgauge.collector import DataCollector, SystemSnapshot
from boostgauge.collectors import WindowsCollector, create_collector

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "AppConfig",
    "ConfigManager",
    "WindowPosition",
    "ThresholdsConfig",
    "ThresholdPair",
    "DataCollector",
    "SystemSnapshot",
    "WindowsCollector",
    "create_collector",
]