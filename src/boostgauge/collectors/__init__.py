"""Collectors package initialization and factory.

Issue #4: Feature: Windows Data Collector — ConPTY, Processes, Memory, Handles
"""

from __future__ import annotations

import sys
from typing import Any, Dict, Optional

from boostgauge.collector import DataCollector, SystemSnapshot
from boostgauge.collectors.windows import WindowsCollector


def get_collector(
    platform_name: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> DataCollector:
    """Factory function returning platform-specific DataCollector.

    Args:
        platform_name: Platform identifier (e.g. 'win32', 'linux'). Defaults to sys.platform.
        config: Optional collector configuration dict.

    Returns:
        Instantiated DataCollector implementation.
    """
    plat = platform_name if platform_name is not None else sys.platform
    if plat.startswith("win"):
        return WindowsCollector(config=config)
    return DataCollector(config=config)


__all__ = ["DataCollector", "SystemSnapshot", "WindowsCollector", "get_collector"]