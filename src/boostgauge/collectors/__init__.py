"""Collectors package initialization and factory function.

Issue #4: Feature: Windows Data Collector — ConPTY, Processes, Memory, Handles
"""

from __future__ import annotations

import sys
from typing import Optional

from boostgauge.collector import DataCollector, MetricThresholdsDict
from boostgauge.collectors.windows import WindowsCollector


def get_collector(
    poll_interval: float = 2.0,
    thresholds: Optional[MetricThresholdsDict] = None,
) -> DataCollector:
    """Instantiate platform-appropriate DataCollector for current OS sys.platform."""
    if sys.platform == "win32":
        return WindowsCollector(poll_interval=poll_interval, thresholds=thresholds)
    else:
        # Default fallback to WindowsCollector structure for testing / cross-platform safety
        return WindowsCollector(poll_interval=poll_interval, thresholds=thresholds)


__all__ = ["WindowsCollector", "get_collector"]