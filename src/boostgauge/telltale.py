"""Peak-hold telltale needle tracking sliding-window maximums with linear decay.

Issue #41: Feature: Telltale peak-hold needle logic (pure, no GUI)
"""

from collections import deque
from typing import Deque, Optional, Tuple


Sample = Tuple[float, float]


class Telltale:
    """Tracks peak values over a sliding time window with optional linear decay."""

    def __init__(self, window: float, decay_rate: Optional[float] = None) -> None:
        """Initialize Telltale needle state.

        Args:
            window: Sliding window duration in seconds (> 0).
            decay_rate: Optional linear decay rate in value units/second (>= 0).

        Raises:
            ValueError: If window <= 0 or decay_rate < 0.
        """
        if window <= 0:
            raise ValueError("Window duration must be positive")
        if decay_rate is not None and decay_rate < 0:
            raise ValueError("Decay rate must be non-negative")

        self._window: float = float(window)
        self._decay_rate: Optional[float] = (
            float(decay_rate) if decay_rate is not None else None
        )
        self._samples: Deque[Sample] = deque()
        self._last_timestamp: Optional[float] = None

    def update(self, timestamp: float, value: float) -> None:
        """Record a new sample timestamp and value.

        Args:
            timestamp: Sample timestamp in seconds.
            value: Numerical reading value.

        Raises:
            ValueError: If timestamp is earlier than the previous sample's timestamp.
        """
        t = float(timestamp)
        v = float(value)

        if self._last_timestamp is not None and t < self._last_timestamp:
            raise ValueError(
                "Timestamp cannot be earlier than previous sample timestamp"
            )

        self._last_timestamp = t
        self._samples.append((t, v))
        self._prune_samples(t)

    def current_peak(self, current_time: Optional[float] = None) -> Optional[float]:
        """Compute the active peak value at current_time or the latest sample timestamp.

        Args:
            current_time: Optional explicit evaluation timestamp.

        Returns:
            The peak value bounded by window maximum, or None if no samples exist.

        Raises:
            ValueError: If current_time is earlier than the latest sample timestamp.
        """
        if not self._samples or self._last_timestamp is None:
            return None

        eval_time = (
            self._last_timestamp
            if current_time is None
            else float(current_time)
        )

        if current_time is not None and eval_time < self._last_timestamp:
            raise ValueError(
                "current_time cannot be earlier than latest sample timestamp"
            )

        active_vals = [
            v for (t, v) in self._samples if eval_time - t <= self._window
        ]

        window_max = max(active_vals) if active_vals else None

        if self._decay_rate is None or self._decay_rate == 0:
            return window_max

        effective_peak = window_max
        for t, v in self._samples:
            if eval_time <= t + self._window:
                eff = v
            else:
                decay_elapsed = eval_time - (t + self._window)
                eff = v - (self._decay_rate * decay_elapsed)
                if eff <= 0:
                    continue
            if effective_peak is None or eff > effective_peak:
                effective_peak = eff

        if effective_peak is None:
            return None

        if window_max is not None and effective_peak < window_max:
            return window_max

        return effective_peak

    def reset(self) -> None:
        """Clear all sample history and decay state."""
        self._samples.clear()
        self._last_timestamp = None

    def _prune_samples(self, current_time: float) -> None:
        """Evict expired samples that can no longer influence active peak or decay."""
        while self._samples:
            t, v = self._samples[0]
            if self._decay_rate is None or self._decay_rate == 0:
                if current_time - t > self._window:
                    self._samples.popleft()
                else:
                    break
            else:
                max_retention = self._window + max(0.0, v / self._decay_rate)
                if current_time - t > max_retention:
                    self._samples.popleft()
                else:
                    break