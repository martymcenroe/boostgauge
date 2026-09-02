"""Telltale — peak-hold over a sliding time window, pure and clock-free (issue #41).

A `Telltale` remembers the highest value reached within `window` seconds, the
way a tachometer's telltale needle stays at the highest RPM it saw. Time only
advances through the timestamps fed to `update()`; the class never reads a
clock, so every read is a plain function of the samples it was given.

Peak semantics (issue #41, verbatim in substance):

- The reference time is the greatest timestamp fed since the last `reset()`.
- A sample is in-window while its age (reference time minus its timestamp)
  is at most `window` — closed boundary. `window=None` means all-time.
- An in-window sample contributes its value, undecayed.
- An aged-out sample is dropped from the read when `decay_rate` is unset —
  excluded, not counted as zero (ruling #125 via #315) — and when it is set
  contributes `value - decay_rate * (reference - departure)`, where departure
  is `timestamp + window`. Every departed sample keeps its own track.
- `current_peak()` is the maximum contribution; the window maximum is the
  only floor (ruling #125).

Design (not a criterion): `update()` and `current_peak()` are O(1) amortized.
In-window samples live in a monotonic deque — an older sample whose value is
not above a newer one can never be the peak nor out-decay it, so it is
dropped on arrival. Departed tracks all descend at the same rate, so their
order never changes and only the dominant one is kept.
"""

from __future__ import annotations

from collections import deque
from numbers import Real


def _positive_number(x) -> bool:
    return isinstance(x, Real) and not isinstance(x, bool) and x > 0


class Telltale:
    """Peak-hold over `window` seconds (or all-time when `window` is None)."""

    def __init__(self, window: float | None, decay_rate: float | None = None) -> None:
        if window is not None and not _positive_number(window):
            raise ValueError(f"window must be a number > 0 or None, got {window!r}")
        if decay_rate is not None and not _positive_number(decay_rate):
            raise ValueError(f"decay_rate must be a number > 0 when given, got {decay_rate!r}")
        self.window = window
        self.decay_rate = decay_rate
        self._samples: deque[tuple[float, float]] = deque()  # (timestamp, value), values strictly decreasing
        self._track: tuple[float, float] | None = None       # (value, departure) — dominant aged-out sample
        self._reference: float | None = None

    # ---- feeding --------------------------------------------------------------

    def update(self, timestamp: float, value: float) -> None:
        """Feed one sample. Timestamps must not decrease since the last reset."""
        if self._reference is not None and timestamp < self._reference:
            raise ValueError(
                f"timestamp {timestamp!r} is lower than the reference time {self._reference!r}; "
                "timestamps must not decrease since the most recent reset()")
        while self._samples and self._samples[-1][1] <= value:
            self._samples.pop()
        self._samples.append((timestamp, value))
        self._reference = timestamp
        self._age_out()

    def reset(self) -> None:
        """Discard history — samples, tracks, and the fed-timestamp record. Configuration survives."""
        self._samples.clear()
        self._track = None
        self._reference = None

    # ---- reading --------------------------------------------------------------

    def current_peak(self) -> float | None:
        """The maximum contribution among held samples; None while nothing is held. Pure."""
        if not self._samples:
            return None
        peak = self._samples[0][1]  # monotonic deque: the front is the window maximum
        if self._track is not None:
            peak = max(peak, self._track_contribution(self._track))
        return peak

    # ---- internals ------------------------------------------------------------

    def _age_out(self) -> None:
        """Move samples whose age now exceeds the window out of the deque.

        The newest sample has age zero and is never moved, so the deque is
        non-empty whenever a sample is held.
        """
        if self.window is None:
            return
        assert self._reference is not None
        while self._samples and self._reference - self._samples[0][0] > self.window:
            timestamp, value = self._samples.popleft()
            if self.decay_rate is None:
                continue  # dropped from the read entirely — excluded, not zero
            candidate = (value, timestamp + self.window)
            if self._track is None or (self._track_contribution(candidate)
                                       > self._track_contribution(self._track)):
                self._track = candidate

    def _track_contribution(self, track: tuple[float, float]) -> float:
        value, departure = track
        assert self.decay_rate is not None and self._reference is not None
        return value - self.decay_rate * (self._reference - departure)
