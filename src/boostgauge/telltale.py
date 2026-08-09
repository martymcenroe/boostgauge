"""Pure peak-hold telltale needle tracking logic over a sliding time window.

Issue #41: Feature: Telltale peak-hold needle logic (pure, no GUI)
"""

from collections import deque
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Sample:
    """Single numeric observation with timestamp."""

    timestamp: float
    value: float


class Telltale:
    """Pure peak-hold telltale needle tracker over a sliding time window."""

    def __init__(self, window: float, decay_rate: Optional[float] = None) -> None:
        """Initialize Telltale with window duration in seconds (>0) and optional decay rate (units/sec)."""
        if window <= 0:
            raise ValueError("Window duration must be positive")
        if decay_rate is not None and decay_rate < 0:
            raise ValueError("Decay rate cannot be negative")

        self.window: float = float(window)
        self.decay_rate: Optional[float] = float(decay_rate) if decay_rate is not None else None
        self.samples: deque[Sample] = deque()
        self.max_deque: deque[Sample] = deque()
        self.latest_timestamp: Optional[float] = None

    def update(self, timestamp: float, value: float) -> None:
        """Feed a new sample (timestamp, value) and update internal sliding window state."""
        timestamp_float = float(timestamp)
        value_float = float(value)

        if self.latest_timestamp is not None and timestamp_float < self.latest_timestamp:
            raise ValueError("Timestamps must be non-decreasing")

        self.latest_timestamp = timestamp_float

        cutoff = timestamp_float - self.window
        while self.samples and self.samples[0].timestamp < cutoff:
            self.samples.popleft()

        while self.max_deque and self.max_deque[0].timestamp < cutoff:
            self.max_deque.popleft()

        while self.max_deque and self.max_deque[-1].value <= value_float:
            self.max_deque.pop()

        new_sample = Sample(timestamp=timestamp_float, value=value_float)
        self.samples.append(new_sample)
        self.max_deque.append(new_sample)

    def current_peak(self, current_time: Optional[float] = None) -> Optional[float]:
        """Return highest value in window, accounting for optional decay up to current_time."""
        if not self.samples:
            return None

        eval_time = float(current_time) if current_time is not None else self.latest_timestamp
        assert self.latest_timestamp is not None

        if eval_time < self.latest_timestamp:
            raise ValueError("Evaluation time cannot precede latest timestamp")

        cutoff = eval_time - self.window
        window_max: Optional[float] = None
        for s in self.samples:
            if s.timestamp >= cutoff:
                if window_max is None or s.value > window_max:
                    window_max = s.value

        if self.decay_rate is None or self.decay_rate == 0.0:
            return window_max

        peak_cand: Optional[float] = None
        for s in self.max_deque:
            decay_elapsed = max(0.0, eval_time - (s.timestamp + self.window))
            decayed = s.value - self.decay_rate * decay_elapsed
            if peak_cand is None or decayed > peak_cand:
                peak_cand = decayed

        if peak_cand is None:
            return window_max

        if window_max is None:
            return peak_cand

        return max(peak_cand, window_max)

    def reset(self) -> None:
        """Clear all sample history and reset telltale state to initial uninitialized state."""
        self.samples.clear()
        self.max_deque.clear()
        self.latest_timestamp = None