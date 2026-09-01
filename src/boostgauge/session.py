"""Telltale wiring and the running session (issue #2).

Pure and testable: no tkinter, no clock reads. The app layer (#5) binds the
context menu, hover and the refresh loop to what lives here.

- ``TelltaleSet`` — the four ``Telltale`` instances (short, medium, long from
  ``telltale_windows``; all-time with window None), sample fan-out, the
  four-slot ``peaks()`` list passed to the renderer unfiltered (a None peak
  reaches the renderer as None — deciding not to draw is #332's T1), reset
  dispatch, and the one label formatter shared by menu entries and tooltip
  lines.
- ``Session`` — the model behind the window: ingests collector snapshots,
  renders a frame through #332's ``render``, hot-reloads thresholds from the
  config file (#7, thresholds only), tracks hand-made position/size changes,
  and performs the exit write.
"""

from __future__ import annotations

import queue
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Optional

from boostgauge.collector import DataCollector, SystemSnapshot
from boostgauge.config import apply_threshold_updates, save_session_changes, thresholds_from_config
from boostgauge.skins import stingray
from boostgauge.telltale import Telltale

SLOT_KEYS = ("short", "medium", "long")
# Name column of the aesthetic doc's palette rows, bound pairwise to stingray.TELLTALE_COLORS
# (cyan #3BD7F0, orange #FF9A2E, magenta #D45BE8, coral red #FF6E7A — ruling #267).
COLOR_NAMES = ("cyan", "orange", "magenta", "coral red")
ALL_TIME_LABEL = "All-time"
RESET_ALL_LABEL = "Reset All"


def window_label(seconds: Optional[float]) -> str:
    """'All-time' for None; a whole number of hours 'Nh'; else whole minutes 'Nm'; else 'Ns'."""
    if seconds is None:
        return ALL_TIME_LABEL
    s = float(seconds)
    if s > 0 and s % 3600 == 0:
        return f"{int(s // 3600)}h"
    if s > 0 and s % 60 == 0:
        return f"{int(s // 60)}m"
    return f"{int(s)}s" if s == int(s) else f"{s:g}s"


class TelltaleSet:
    """The four peak-hold instances, in renderer slot order: short, medium, long, all-time."""

    def __init__(self, windows: Mapping[str, float]) -> None:
        self.windows: tuple[Optional[float], ...] = (
            float(windows["short"]), float(windows["medium"]), float(windows["long"]), None)
        self.telltales: tuple[Telltale, ...] = tuple(Telltale(w) for w in self.windows)

    @classmethod
    def from_config(cls, config: Mapping) -> "TelltaleSet":
        return cls(config["telltale_windows"])

    # ---- W2: fan-out --------------------------------------------------------------
    def feed(self, timestamp: float, value: float) -> None:
        for t in self.telltales:
            t.update(timestamp, value)

    # ---- W3: the four-slot argument, None passed through --------------------------
    def peaks(self) -> list[Optional[float]]:
        return [t.current_peak() for t in self.telltales]

    # ---- RS: reset dispatch ----------------------------------------------------------
    def reset(self, slot: int) -> None:
        self.telltales[slot].reset()

    def reset_all(self) -> None:
        for t in self.telltales:
            t.reset()

    # ---- labels: one formatter for menu entries and tooltip lines ----------------
    def labels(self) -> list[str]:
        return [window_label(w) for w in self.windows]

    def menu_entries(self) -> list[tuple[str, Callable[[], None]]]:
        """('Reset <label>', handler) for each slot, then ('Reset All', reset_all)."""
        entries: list[tuple[str, Callable[[], None]]] = [
            (f"Reset {label}", (lambda i=i: self.reset(i))) for i, label in enumerate(self.labels())]
        entries.append((RESET_ALL_LABEL, self.reset_all))
        return entries

    def tooltip_lines(self) -> list[str]:
        return [f"{label} — {name}" for label, name in zip(self.labels(), COLOR_NAMES)]

    def tooltip_text(self) -> str:
        return "\n".join(self.tooltip_lines())


class Session:
    """What the window shows and what it saves — with the window itself left to the app layer."""

    def __init__(self, config: dict, config_path, *, collector: Optional[DataCollector] = None,
                 telltales: Optional[TelltaleSet] = None,
                 renderer: Callable = stingray.render) -> None:
        self.config = config
        self.config_path = Path(config_path)
        self.collector = collector
        self.telltales = telltales or TelltaleSet.from_config(config)
        self.renderer = renderer
        self.latest: Optional[SystemSnapshot] = None
        self.hand_changed_position: Optional[dict] = None
        self.hand_changed_size: Optional[int] = None

    # ---- samples in ------------------------------------------------------------------
    def ingest(self, snapshot: SystemSnapshot) -> None:
        """One collector sample: remember it, fan it out to all four telltales (W2)."""
        self.latest = snapshot
        self.telltales.feed(snapshot.timestamp, snapshot.composite_value)

    def drain(self, snapshots: queue.Queue) -> int:
        """Ingest every queued snapshot; returns how many."""
        n = 0
        while True:
            try:
                snap = snapshots.get_nowait()
            except queue.Empty:
                return n
            self.ingest(snap)
            n += 1

    @property
    def value(self) -> float:
        return self.latest.composite_value if self.latest is not None else 0.0

    # ---- frames out (W3) -------------------------------------------------------------
    def frame(self, size: Optional[int] = None):
        """One refresh: the renderer gets the value and all four peaks, None included."""
        return self.renderer(self.value, self.telltales.peaks(), size or self.config["size"])

    # ---- config: thresholds hot-reload (#7 H1), hand changes, exit write --------------
    def reread_thresholds(self) -> bool:
        """Re-read the file; apply threshold edits to the running collector. True if changed."""
        updated = apply_threshold_updates(self.config_path, self.config)
        if updated is self.config:
            return False
        self.config = updated
        if self.collector is not None:
            self.collector.thresholds = thresholds_from_config(updated)
        return True

    def moved(self, x: int, y: int) -> None:
        self.hand_changed_position = {"x": int(x), "y": int(y)}

    def resized(self, size: int) -> None:
        self.hand_changed_size = int(size)
        self.config["size"] = int(size)

    def exit_write(self) -> bool:
        return save_session_changes(self.config_path, self.hand_changed_position, self.hand_changed_size)
