"""Peak-hold telltale needle logic for system gauges.

Issue #41: Telltale peak-hold needle logic (pure, no GUI)
"""

from collections import deque
from dataclasses import dataclass
from typing import Dict, Literal, Optional


WindowKey = Literal["m1", "m10", "h1", "all"]


@dataclass(frozen=True)
class Sample:
    """Represents a single system sample with a timestamp and scalar value."""

    timestamp: float
    value: float


class Telltale:
    """Tracks peak values over a sliding time window with optional linear decay."""

    def __init__(self, window: Optional[float], decay_rate: Optional[float] = None) -> None:
        """Initialize Telltale with window duration in seconds and optional decay_rate.

        Args:
            window: Sliding time window duration in seconds (> 0), or None for all-time.
            decay_rate: Optional linear decay rate in units per second (>= 0).

        Raises:
            ValueError: If window <= 0 or decay_rate < 0.
        """
        if window is not None and window <= 0:
            raise ValueError("Window must be positive")
        if decay_rate is not None and decay_rate < 0:
            raise ValueError("Decay rate must be non-negative")

        self._window: Optional[float] = float(window) if window is not None else None
        self._decay_rate: Optional[float] = (
            float(decay_rate) if decay_rate is not None else None
        )
        self._samples: deque[Sample] = deque()
        self._max_deque: deque[Sample] = deque()
        self._decay_peak: Optional[Sample] = None
        self._last_update_time: Optional[float] = None

    def update(self, timestamp: float, value: float) -> None:
        """Feed a new sample (timestamp, value) into the telltale history.

        Args:
            timestamp: Sample timestamp in seconds.
            value: Scalar sample value.

        Raises:
            ValueError: If timestamp is earlier than the previous update timestamp.
        """
        if self._last_update_time is not None and timestamp < self._last_update_time:
            raise ValueError("Timestamps must be non-decreasing")

        ts = float(timestamp)
        val = float(value)
        self._last_update_time = ts
        new_sample = Sample(ts, val)

        while self._max_deque and self._max_deque[-1].value <= val:
            self._max_deque.pop()
        self._max_deque.append(new_sample)
        self._samples.append(new_sample)

        if self._window is not None:
            self._advance_to(ts)

    def current_peak(self, timestamp: Optional[float] = None) -> Optional[float]:
        """Return the highest value within the active window, considering decay.

        Args:
            timestamp: Optional query timestamp. Defaults to latest sample timestamp.

        Returns:
            The peak value, or None if no samples have been recorded.

        Raises:
            ValueError: If timestamp is earlier than the latest update timestamp.
        """
        if self._last_update_time is None:
            return None

        t_query = float(timestamp) if timestamp is not None else self._last_update_time
        if t_query < self._last_update_time:
            raise ValueError("Query timestamp cannot be behind latest sample update")

        if self._window is not None:
            self._advance_to(t_query)

        active_window_max: Optional[float] = (
            self._max_deque[0].value if self._max_deque else None
        )

        decayed_val: Optional[float] = None
        if (
            self._window is not None
            and self._decay_peak is not None
            and self._decay_rate is not None
            and self._decay_rate > 0
        ):
            expired_time = t_query - (self._decay_peak.timestamp + self._window)
            if expired_time >= 0:
                calc_decay = self._decay_peak.value - (self._decay_rate * expired_time)
                if calc_decay > 0:
                    decayed_val = calc_decay

        if active_window_max is None:
            return decayed_val
        if decayed_val is None:
            return active_window_max
        return max(active_window_max, decayed_val)

    def _advance_to(self, t_target: float) -> None:
        """Evict expired samples relative to t_target and update decay tracking."""
        if self._window is None:
            return
        cutoff = t_target - self._window
        while self._samples and self._samples[0].timestamp < cutoff:
            expired_sample = self._samples.popleft()

            if self._max_deque and self._max_deque[0].timestamp == expired_sample.timestamp:
                self._max_deque.popleft()

            if self._decay_rate is not None and self._decay_rate > 0:
                exp_time = t_target - (expired_sample.timestamp + self._window)
                exp_decayed = expired_sample.value - (self._decay_rate * exp_time)
                curr_decayed = (
                    0.0 if self._decay_peak is None
                    else self._decay_peak.value - self._decay_rate * (t_target - self._decay_peak.timestamp - self._window)
                )
                if exp_decayed > 0 and exp_decayed >= curr_decayed:
                    self._decay_peak = expired_sample

    def reset(self) -> None:
        """Clear all sample history and reset internal peak state."""
        self._samples.clear()
        self._max_deque.clear()
        self._decay_peak = None
        self._last_update_time = None


class TelltaleManager:
    """Manages four sliding-window Telltale instances for system metric peaks.

    Encapsulates 1m (60s), 10m (600s), 1h (3600s), and all-time (None) windows.
    Closes #2
    """

    def __init__(self) -> None:
        """Initialize four Telltale window objects."""
        self._telltales: Dict[str, Telltale] = {
            "m1": Telltale(window=60.0),
            "m10": Telltale(window=600.0),
            "h1": Telltale(window=3600.0),
            "all": Telltale(window=None),
        }

    def update(self, timestamp: float, value: float) -> None:
        """Pipe live metric sample (timestamp, value) to all four telltales."""
        clamped_val = max(0.0, min(100.0, float(value)))
        for telltale in self._telltales.values():
            telltale.update(timestamp, clamped_val)

    def get_peaks(self, timestamp: Optional[float] = None) -> Dict[str, Optional[float]]:
        """Return current peak values dict for all four windows."""
        return {
            key: telltale.current_peak(timestamp)
            for key, telltale in self._telltales.items()
        }

    def reset(self, key: str) -> None:
        """Reset a specific window or all windows if key is 'all'."""
        if key == "all":
            self.reset_all()
            return
        if key not in self._telltales:
            raise KeyError(f"Invalid telltale window key: '{key}'")
        self._telltales[key].reset()

    def reset_all(self) -> None:
        """Reset all four Telltale instances simultaneously."""
        for telltale in self._telltales.values():
            telltale.reset()