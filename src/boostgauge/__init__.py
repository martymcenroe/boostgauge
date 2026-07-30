"""BoostGauge package initialization.

Issue #7: Configuration File and CLI Arguments
"""

from boostgauge.collector import DataCollector, SystemSnapshot
from boostgauge.collectors import WindowsCollector, create_collector

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "DataCollector",
    "SystemSnapshot",
    "WindowsCollector",
    "create_collector",
]