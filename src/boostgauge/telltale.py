"""Pure sliding-window peak-hold needle logic with optional linear decay.

Issue #41: Telltale peak-hold needle logic (pure, no GUI)
"""

from __future__ import annotations

from collections import deque
from typing import Optional, Tuple


class Telltale:
    """Pure sliding-window peak-hold needle logic with optional linear decay."""

    def __init__(self, window: float, decay_rate: Optional[float] = None) -> None:
        """Initialize Telltale with window duration in seconds and optional decay rate (units/sec).

        Args:
            window: Sliding window duration in seconds (> 0).
            decay_rate: Optional linear decay rate in units per second (>= 0).

        Raises:
            ValueError: If window <= 0 or decay_rate < 0.
        """
        if window <= 0:
            raise ValueError("window must be positive")
        if decay_rate is not None and decay_rate < 0:
            raise ValueError("decay_rate must be non-negative")

        self.window: float = float(window)
        self.decay_rate: Optional[float] = float(decay_rate) if decay_rate is not None else None

        self._samples: deque[Tuple[float, float]] = deque()
        self._max_deque: deque[Tuple[float, float]] = deque()
        self._best_expired_key: Optional[float] = None
        self._latest_timestamp: Optional[float] = None

    def update(self, timestamp: float, value: float) -> None:
        """Feed a new sample (timestamp, value) into the telltale state.

        Args:
            timestamp: Sample timestamp in seconds.
            value: Numerical sample value.
        """
        t = float(timestamp)
        v = float(value)

        self._latest_timestamp = t
        self._prune_expired(t)

        self._samples.append((t, v))

        while self._max_deque and self._max_deque[-1][1] <= v:
            self._max_deque.pop()
        self._max_deque.append((t, v))

    def _prune_expired(self, evaluation_time: float) -> None:
        """Prune samples older than (evaluation_time - window) from active window queues.

        Args:
            evaluation_time: Timestamp to evaluate window cutoff against.
        """
        cutoff = evaluation_time - self.window
        while self._samples and self._samples[0][0] < cutoff:
            t_old, v_old = self._samples.popleft()
            if self._max_deque and self._max_deque[0] == (t_old, v_old):
                self._max_deque.popleft()

            if self.decay_rate is not None and self.decay_rate > 0:
                expired_key = v_old + self.decay_rate * (t_old + self.window)
                if self._best_expired_key is None or expired_key > self._best_expired_key:
                    self._best_expired_key = expired_key

    def current_peak(self, timestamp: Optional[float] = None) -> Optional[float]:
        """Compute the effective peak value at the specified timestamp (or latest sample timestamp).

        Args:
            timestamp: Optional evaluation timestamp. Defaults to latest sample timestamp.

        Returns:
            The current peak value (floored by window maximum), or None if no samples exist.
        """
        eval_time = timestamp if timestamp is not None else self._latest_timestamp
        if eval_time is None:
            return None

        self._prune_expired(eval_time)

        if not self._samples and self._best_expired_key is None:
            return None

        active_max = self._max_deque[0][1] if self._max_deque else None

        if self.decay_rate is not None and self.decay_rate > 0 and self._best_expired_key is not None:
            decayed_peak = self._best_expired_key - self.decay_rate * eval_time
            if active_max is not None:
                return max(active_max, decayed_peak)
            return decayed_peak

        return active_max

    def reset(self) -> None:
        """Clear all historical state; subsequent current_peak() calls return None until updated."""
        self._samples.clear()
        self._max_deque.clear()
        self._best_expired_key = None
        self._latest_timestamp = None