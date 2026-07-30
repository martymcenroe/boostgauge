"""Collectors package initialization and factory function.

Issue #4: Windows data collector — ConPTY, processes, memory, handles
"""

import queue
import sys
from typing import Any, Dict, Optional

from boostgauge.collector import DataCollector, SystemSnapshot
from boostgauge.collectors.windows import WindowsCollector


def create_collector(
    config: Optional[Dict[str, Any]] = None,
    snapshot_queue: Optional[queue.Queue] = None,
) -> DataCollector:
    """Factory function instantiating platform-appropriate DataCollector.

    Args:
        config: Configuration dictionary with poll intervals and thresholds.
        snapshot_queue: Target queue for pushed SystemSnapshots.

    Returns:
        Platform-specific DataCollector instance (WindowsCollector on Windows).
    """
    if sys.platform == "win32":
        return WindowsCollector(config=config, snapshot_queue=snapshot_queue)
    return WindowsCollector(config=config, snapshot_queue=snapshot_queue)


__all__ = ["DataCollector", "SystemSnapshot", "WindowsCollector", "create_collector"]