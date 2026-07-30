"""BoostGauge package initialization.

Issue #7: Configuration File and CLI Arguments
"""

from boostgauge.collector import DataCollector, SystemSnapshot
from boostgauge.collectors import WindowsCollector, create_collector
from boostgauge.telltale import TelltaleManager

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "DataCollector",
    "SystemSnapshot",
    "TelltaleManager",
    "WindowsCollector",
    "create_collector",
]