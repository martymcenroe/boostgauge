"""BoostGauge package initialization.

Issue #7: Configuration File and CLI Arguments
Issue #4: Feature: Windows Data Collector — ConPTY, Processes, Memory, Handles
"""

from boostgauge.collector import DataCollector, SystemSnapshot
from boostgauge.collectors import WindowsCollector, get_collector

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "SystemSnapshot",
    "DataCollector",
    "WindowsCollector",
    "get_collector",
]