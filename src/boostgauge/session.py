"""Telltale wiring, calibration, and the running session (issues #2 and #416).

Pure and testable: no tkinter, no clock reads. The app layer (#5) binds the
context menu, hover and the refresh loop to what lives here.

- ``TelltaleSet`` — the four ``Telltale`` instances (short, medium, long from
  ``telltale_windows``; all-time with window None), sample fan-out, the
  four-slot ``peaks()`` list passed to the renderer unfiltered (a None peak
  reaches the renderer as None — deciding not to draw is #332's T1), reset
  dispatch, and the one label formatter shared by menu entries and tooltip
  lines.
- ``bands_for`` — #416: what 100 means. Memory keeps its absolute band. The
  three counts calibrate: in ``auto`` mode red is this machine's stored
  all-time high and yellow is 0.6 of it; a metric with no high yet seeds
  from the first reading with headroom (red 2.5 r, yellow 1.5 r), so a fresh
  install's needle starts at exactly 40.0. ``manual`` mode uses
  ``thresholds`` — typed, or written by *Mark this as redline*.
- ``Session`` — the model behind the window: ingests collector snapshots and
  recomputes the composite against the session's bands, renders a frame
  through #332's ``render``, learns the session's highs, hot-reloads
  thresholds (#7, thresholds only), tracks hand-made position/size changes,
  and performs the exit write.
"""

from __future__ import annotations

import queue
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Optional

from boostgauge.collector import Band, DataCollector, SystemSnapshot, Thresholds, composite
from boostgauge.config import (COUNT_METRICS, apply_threshold_updates, save_session_changes,
                               thresholds_from_config)
from boostgauge.skins import stingray
from boostgauge.telltale import Telltale

SLOT_KEYS = ("short", "medium", "long")
# Name column of the aesthetic doc's palette rows, bound pairwise to stingray.TELLTALE_COLORS
# (cyan #3BD7F0, orange #FF9A2E, magenta #D45BE8, coral red #FF6E7A — ruling #267).
COLOR_NAMES = ("cyan", "orange", "magenta", "coral red")
ALL_TIME_LABEL = "All-time"
RESET_ALL_LABEL = "Reset All"

# ---- calibration constants (#416) ------------------------------------------------
SEED_RED = 2.5          # first run: red = 2.5 x the first reading ...
SEED_YELLOW = 1.5       # ... yellow = 1.5 x, so normalize(r) = 60 x r / 1.5 r = 40.0 exactly
YELLOW_OF_RED = 0.6     # auto mode and Mark: yellow = 0.6 x red
# A zero or near-zero first reading must not make red zero: seed from at least this much.
SEED_FLOORS = {"conpty": 4.0, "process_count": 50.0, "handle_count": 5000.0}


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


# ---- calibration (#416) --------------------------------------------------------------


def raw_counts(snapshot: SystemSnapshot) -> dict[str, float]:
    """The three calibrated metrics' raw readings from a snapshot."""
    return {"conpty": float(snapshot.conpty_count),
            "process_count": float(snapshot.process_count),
            "handle_count": float(snapshot.handle_count)}


def _floored(metric: str, reading: float) -> float:
    return max(float(reading), SEED_FLOORS[metric])


def seeded_highs(first_reading: Mapping[str, float]) -> dict[str, float]:
    """The highs a first run records: red = 2.5 x the (floored) first reading, per metric."""
    return {m: SEED_RED * _floored(m, first_reading[m]) for m in COUNT_METRICS}


def bands_for(config: Mapping, first_reading: Optional[Mapping[str, float]] = None) -> Optional[Thresholds]:
    """The session's bands — what 100 means (#416).

    ``manual`` mode: ``thresholds`` as typed or marked. ``auto`` mode: per count
    metric, red = the stored high and yellow = 0.6 x red; a metric with no
    stored high seeds from ``first_reading`` (red 2.5 r, yellow 1.5 r, r floored)
    and, with no reading offered, the result is None — seed on the first
    snapshot. Memory always comes from ``thresholds.memory_percent``.
    """
    cal = config.get("calibration") or {"mode": "auto", "highs": {}}
    if cal.get("mode") == "manual":
        return thresholds_from_config(config)
    memory = config["thresholds"]["memory_percent"]
    highs = cal.get("highs") or {}
    bands: dict[str, Band] = {}
    for metric in COUNT_METRICS:
        high = highs.get(metric)
        if high is None:
            if first_reading is None:
                return None
            r = _floored(metric, first_reading[metric])
            bands[metric] = Band(SEED_YELLOW * r, SEED_RED * r)
        else:
            bands[metric] = Band(YELLOW_OF_RED * float(high), float(high))
    return Thresholds(conpty=bands["conpty"],
                      memory_percent=Band(float(memory["yellow"]), float(memory["red"])),
                      process_count=bands["process_count"],
                      handle_count=bands["handle_count"])


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
        # #416
        self.config.setdefault("calibration", {"mode": "auto", "highs": {}})
        self.bands: Optional[Thresholds] = bands_for(config)   # None: seed on the first snapshot
        self.session_highs: dict[str, float] = {}               # learned this session, persisted at quit
        self.calibration_dirty = False                          # Mark / Reset clicked this session
        self._push_bands()

    # ---- calibration --------------------------------------------------------------
    @property
    def calibration_mode(self) -> str:
        return self.config["calibration"]["mode"]

    def _push_bands(self) -> None:
        if self.bands is not None and self.collector is not None:
            self.collector.thresholds = self.bands

    def _seed(self, raw: Mapping[str, float]) -> None:
        seeds = seeded_highs(raw)
        self.config["calibration"]["highs"].update(seeds)
        for metric, high in seeds.items():
            self.session_highs[metric] = max(self.session_highs.get(metric, 0.0), high)
        self.bands = bands_for(self.config)
        self._push_bands()

    def _composed(self, snapshot: SystemSnapshot) -> SystemSnapshot:
        """The snapshot with its composite recomputed against the session's bands."""
        raw = raw_counts(snapshot)
        assert self.bands is not None
        value, driver = composite(raw["conpty"], snapshot.memory_percent, raw["process_count"],
                                  raw["handle_count"], self.bands)
        return replace(snapshot, composite_value=value, driver=driver)

    def mark_redline(self) -> bool:
        """*Mark this as redline*: the current readings become red, 0.6 of them yellow; manual mode."""
        if self.latest is None:
            return False
        raw = raw_counts(self.latest)
        thresholds = deepcopy(self.config["thresholds"])
        for metric in COUNT_METRICS:
            r = _floored(metric, raw[metric])
            thresholds[metric] = {"yellow": YELLOW_OF_RED * r, "red": r}
        self.config["thresholds"] = thresholds
        self.config["calibration"]["mode"] = "manual"
        self.calibration_dirty = True
        self.bands = thresholds_from_config(self.config)
        self._push_bands()
        self._reapply_latest()
        return True

    def reset_calibration(self) -> None:
        """*Reset calibration*: back to auto, highs cleared, re-seeded from the latest reading."""
        self.config["calibration"] = {"mode": "auto", "highs": {}}
        self.session_highs = {}
        self.calibration_dirty = True
        self.bands = None
        if self.latest is not None:
            self._seed(raw_counts(self.latest))
            self._reapply_latest()

    def _reapply_latest(self) -> None:
        """Recompute the latest snapshot under the new bands and feed it as a sample of this moment."""
        assert self.latest is not None
        self.latest = self._composed(self.latest)
        self.telltales.feed(self.latest.timestamp, self.latest.composite_value)

    # ---- samples in ------------------------------------------------------------------
    def ingest(self, snapshot: SystemSnapshot) -> None:
        """One collector sample: seed bands if needed, learn highs, recompute the composite,
        remember it, fan it out to all four telltales (W2)."""
        raw = raw_counts(snapshot)
        if self.bands is None:
            self._seed(raw)
        for metric, value in raw.items():
            self.session_highs[metric] = max(self.session_highs.get(metric, 0.0), value)
        self.latest = self._composed(snapshot)
        self.telltales.feed(self.latest.timestamp, self.latest.composite_value)

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

    @property
    def driver(self) -> Optional[str]:
        return self.latest.driver if self.latest is not None else None

    # ---- frames out (W3) -------------------------------------------------------------
    def frame(self, size: Optional[int] = None):
        """One refresh: the renderer gets the value and all four peaks, None included."""
        return self.renderer(self.value, self.telltales.peaks(), size or self.config["size"])

    # ---- config: thresholds hot-reload (#7 H1), hand changes, exit write --------------
    def reread_thresholds(self) -> bool:
        """Re-read the file; apply threshold edits to the session's bands. True if the config changed.

        In auto mode only the memory band can change this way — the counts come
        from the highs (#416); in manual mode all four bands follow the file.
        """
        updated = apply_threshold_updates(self.config_path, self.config)
        if updated is self.config:
            return False
        self.config = updated
        bands = bands_for(self.config)
        if bands is not None:
            self.bands = bands
            self._push_bands()
        return True

    def moved(self, x: int, y: int) -> None:
        self.hand_changed_position = {"x": int(x), "y": int(y)}

    def resized(self, size: int) -> None:
        self.hand_changed_size = int(size)
        self.config["size"] = int(size)

    def exit_write(self) -> bool:
        """#7's exit write, plus #416's learning: highs that rose, or the whole calibration after Mark / Reset."""
        if self.calibration_dirty:
            mode = self.calibration_mode
            calibration = {"mode": mode,
                           "highs": dict(self.session_highs) if mode == "auto"
                           else deepcopy(self.config["calibration"]["highs"])}
            return save_session_changes(self.config_path, self.hand_changed_position, self.hand_changed_size,
                                        calibration=calibration,
                                        thresholds=deepcopy(self.config["thresholds"]) if mode == "manual" else None)
        return save_session_changes(self.config_path, self.hand_changed_position, self.hand_changed_size,
                                    learned_highs=dict(self.session_highs))
