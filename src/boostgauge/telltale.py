"""Peak-hold telltale needle logic for boostgauge.

Issue #41: Telltale peak-hold needle logic (pure, no GUI)
"""

from dataclasses import dataclass


@dataclass
class Sample:
    timestamp: float
    value: float


class Telltale:
    """Tracks the peak value of a time series over a sliding window with optional decay."""

    def __init__(self, window: float | None, decay_rate: float | None = None) -> None:
        if window is not None and window <= 0:
            raise ValueError("window must be None or greater than zero")
        if decay_rate is not None and decay_rate <= 0:
            raise ValueError("decay_rate must be None or greater than zero")

        self._window = window
        self._decay_rate = decay_rate
        self._history: list[Sample] = []
        self._max_timestamp: float = float('-inf')

    def update(self, timestamp: float, value: float) -> None:
        if self._max_timestamp != float('-inf') and timestamp < self._max_timestamp:
            raise ValueError("timestamp must be >= any previously fed timestamp")

        self._history.append(Sample(timestamp, value))
        self._max_timestamp = timestamp

    def current_peak(self) -> float | None:
        if not self._history:
            return None

        max_contribution = float('-inf')

        for sample in self._history:
            age = self._max_timestamp - sample.timestamp

            if self._window is None or age <= self._window:
                contribution = sample.value
            elif self._decay_rate is None:
                continue
            else:
                departure_time = sample.timestamp + self._window
                elapsed = self._max_timestamp - departure_time
                contribution = sample.value - (self._decay_rate * elapsed)

            if contribution > max_contribution:
                max_contribution = contribution

        return max_contribution if max_contribution != float('-inf') else None

    def reset(self) -> None:
        self._history.clear()
        self._max_timestamp = float('-inf')