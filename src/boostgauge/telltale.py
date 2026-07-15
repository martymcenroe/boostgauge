"""Peak-hold telltale needle logic.

Issue #41: Feature: Telltale peak-hold needle logic (pure, no GUI)
"""

from collections import deque
from typing import Optional, TypedDict


class TelltaleSample(TypedDict):
    timestamp: float
    value: float
    key: float


class Telltale:
    """Tracks the peak value reached over a sliding time window with optional decay."""

    def __init__(self, window: float, decay_rate: Optional[float] = None) -> None:
        """Initialize the peak-hold telltale.

        Args:
            window: Sliding window duration in seconds (must be positive).
            decay_rate: Optional decay rate in units/second (must be non-negative).
        """
        if window <= 0:
            raise ValueError("Window must be positive.")
        if decay_rate is not None and decay_rate < 0:
            raise ValueError("decay_rate must be non-negative.")

        self.window = window
        self.decay_rate = decay_rate
        self._history: deque[TelltaleSample] = deque()
        self._peak: Optional[float] = None
        self._last_t: Optional[float] = None

    def update(self, timestamp: float, value: float) -> None:
        """Feed a new sample into the telltale.

        Args:
            timestamp: The timestamp of the sample. Must be >= the previous timestamp.
            value: The value of the sample.
        """
        if self._last_t is not None and timestamp < self._last_t:
            raise ValueError("Timestamps must be monotonically increasing.")

        self._last_t = timestamp
        cutoff = timestamp - self.window

        # 1. Expire old elements outside the window
        while self._history and self._history[0]["timestamp"] < cutoff:
            self._history.popleft()

        # 2. Compute invariant decay key
        if self.decay_rate is not None:
            key = value + self.decay_rate * timestamp
        else:
            key = value

        # 3. Maintain monotonic order (remove items with smaller/equal keys from back)
        while self._history and self._history[-1]["key"] <= key:
            self._history.pop()

        # 4. Append new sample
        self._history.append({
            "timestamp": timestamp,
            "value": value,
            "key": key
        })

        # 5. Update computed peak
        front = self._history[0]
        if self.decay_rate is not None:
            self._peak = front["key"] - self.decay_rate * timestamp
        else:
            self._peak = front["value"]

    def current_peak(self) -> Optional[float]:
        """Get the current peak-hold value.

        Returns:
            The peak value, or None if no samples have been received or after reset().
        """
        return self._peak

    def reset(self) -> None:
        """Reset the telltale's state and clear history."""
        self._history.clear()
        self._peak = None
        self._last_t = None