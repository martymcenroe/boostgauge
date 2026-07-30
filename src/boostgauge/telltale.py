"""Pure sliding-window peak-hold needle logic with optional linear decay.

Issue #41: Telltale peak-hold needle logic (pure, no GUI)
"""

from __future__ import annotations

from collections import deque
from typing import Dict, Literal, Optional, Tuple, TypedDict


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


WindowKey = Literal["m1", "m10", "h1", "all"]


class TelltaleDict(TypedDict, total=False):
    """Dictionary mapping telltale window keys to current peak values (0.0 to 100.0 or None)."""
    m1: Optional[float]
    m10: Optional[float]
    h1: Optional[float]
    all: Optional[float]


class WindowConfig(TypedDict):
    """Configuration mapping window key to duration in seconds."""
    key: WindowKey
    duration: float


class TelltaleManager:
    """Manages lifecycle, metric routing, state extraction, and resets for 4 telltale windows."""

    def __init__(self) -> None:
        """Initialize 4 Telltale instances with 60s, 600s, 3600s, and inf windows."""
        self.telltales: Dict[WindowKey, Telltale] = {
            "m1": Telltale(window=60.0),
            "m10": Telltale(window=600.0),
            "h1": Telltale(window=3600.0),
            "all": Telltale(window=float("inf")),
        }
        self._last_timestamp: Optional[float] = None

    def update(self, timestamp: float, value: float) -> None:
        """Pipe incoming sample timestamp and metric value to all four Telltale instances."""
        if timestamp < 0:
            raise ValueError("Timestamp must be non-negative")
        if self._last_timestamp is not None and timestamp < self._last_timestamp:
            raise ValueError("Timestamp must be monotonically non-decreasing")
        self._last_timestamp = timestamp
        for telltale in self.telltales.values():
            telltale.update(timestamp, value)

    def get_peaks(self, timestamp: Optional[float] = None) -> TelltaleDict:
        """Extract current peak values for all windows formatted as a TelltaleDict."""
        eval_ts = timestamp if timestamp is not None else self._last_timestamp
        return {
            "m1": self.telltales["m1"].current_peak(eval_ts),
            "m10": self.telltales["m10"].current_peak(eval_ts),
            "h1": self.telltales["h1"].current_peak(eval_ts),
            "all": self.telltales["all"].current_peak(eval_ts),
        }

    def reset(self, window_key: Optional[str] = None) -> None:
        """Reset specified telltale window ('m1', 'm10', 'h1', 'all'), or reset all if window_key is None or 'all_windows'."""
        if window_key is None or window_key == "all_windows":
            self.reset_all()
        elif window_key in self.telltales:
            self.telltales[window_key].reset()  # type: ignore[index]
        else:
            raise ValueError(f"Unknown window key: {window_key}")

    def reset_all(self) -> None:
        """Reset all four telltale instances to cleared state."""
        for telltale in self.telltales.values():
            telltale.reset()
        self._last_timestamp = None