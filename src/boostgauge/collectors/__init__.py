"""Collectors package initialization and factory function.

Issue #4: Feature: Windows data collector — ConPTY, processes, memory, handles
"""

import queue
import sys
from typing import Any, Dict, Optional

from boostgauge.collector import DataCollector, SystemSnapshot
from boostgauge.collectors.windows import WindowsCollector


def create_collector(
    config: Optional[Dict[str, Any]] = None,
    snapshot_queue: Optional[queue.Queue[SystemSnapshot]] = None,
) -> DataCollector:
    """Factory function to instantiate the platform-appropriate DataCollector."""
    cfg = config or {}
    if sys.platform == "win32" or cfg.get("_allow_non_windows_for_testing", False):
        return WindowsCollector(config=cfg, snapshot_queue=snapshot_queue)
    raise NotImplementedError(f"Platform '{sys.platform}' is not supported yet")


__all__ = [
    "DataCollector",
    "SystemSnapshot",
    "WindowsCollector",
    "create_collector",
]