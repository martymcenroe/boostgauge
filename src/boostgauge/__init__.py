"""boostgauge package root.

Issue #4: Windows data collector — ConPTY, processes, memory, handles
"""

from boostgauge.collector import DataCollector, SystemSnapshot, normalize_metric, calculate_composite_metric
from boostgauge.collectors import create_collector, WindowsCollector

__all__ = [
    "DataCollector",
    "SystemSnapshot",
    "WindowsCollector",
    "create_collector",
    "normalize_metric",
    "calculate_composite_metric",
]