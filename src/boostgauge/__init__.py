"""BoostGauge package initialization.

Issue #7: Feature configuration file and CLI arguments
Issue #4: Feature: Windows data collector — ConPTY, processes, memory, handles
"""

from boostgauge.collector import DataCollector, SystemSnapshot
from boostgauge.collectors import WindowsCollector, create_collector

__version__ = "0.1.0"

__all__ = [
    "DataCollector",
    "SystemSnapshot",
    "WindowsCollector",
    "create_collector",
    "__version__",
]