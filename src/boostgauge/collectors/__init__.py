"""Collectors package initialization and factory function.

Issue #4: Windows data collector — ConPTY, processes, memory, handles
"""

import sys
from typing import Any, Dict, Optional
import queue

from boostgauge.collector import DataCollector, SystemSnapshot
from boostgauge.collectors.windows import WindowsCollector


def create_collector(
    config: Optional[Dict[str, Any]] = None,
    snapshot_queue: Optional[queue.Queue[SystemSnapshot]] = None,
) -> DataCollector:
    """Factory function returning platform-appropriate DataCollector instance."""
    if sys.platform == "win32":
        return WindowsCollector(config=config, snapshot_queue=snapshot_queue)
    # Default fallback for other platforms (e.g. mock/test)
    return WindowsCollector(config=config, snapshot_queue=snapshot_queue)


__all__ = ["create_collector", "WindowsCollector"]