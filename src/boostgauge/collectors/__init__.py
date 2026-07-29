"""Package exports and platform factory for system metric data collectors.

Issue #4: Feature: Windows Data Collector — ConPTY, Processes, Memory, Handles
"""

from __future__ import annotations

import sys
from typing import Any, Optional

from boostgauge.collector import DataCollector, SystemSnapshot


def get_collector(config: Optional[dict[str, Any]] = None) -> DataCollector:
    """Factory function returning platform-appropriate DataCollector instance."""
    if sys.platform == "win32":
        from boostgauge.collectors.windows import WindowsCollector

        return WindowsCollector(config=config)
    return DataCollector(config=config)


__all__ = ["DataCollector", "SystemSnapshot", "get_collector"]