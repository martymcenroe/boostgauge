"""Base data collector abstractions."""

import abc
from dataclasses import dataclass


@dataclass
class SystemSnapshot:
    """Snapshot of system resource metrics at a point in time."""
    timestamp: float
    conpty_count: int
    process_count: int
    memory_percent: float
    handle_count: int
    unleashed_sessions: int
    driver: str
    composite_value: float


class DataCollector(abc.ABC):
    """Abstract base class for system metric collectors."""

    @abc.abstractmethod
    def start(self) -> None:
        """Start the background polling thread."""
        pass  # pragma: no cover

    @abc.abstractmethod
    def stop(self) -> None:
        """Signal the background thread to stop and wait for it to exit."""
        pass  # pragma: no cover