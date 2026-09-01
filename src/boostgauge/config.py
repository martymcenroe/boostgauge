"""Configuration file and CLI (issue #7).

The file lives at ``%APPDATA%/boostgauge/config.json`` on Windows and
``~/.boostgauge/config.json`` elsewhere. Its eleven keys and their defaults
are ``DEFAULT_CONFIG``, verbatim from the issue.

Writes happen at exactly three moments and at no other time (#7 §Config
persistence): first-run auto-create, the launch reset (``--reset-config``),
and the exit write of the keys the user changed by hand — ``position`` and
``size`` — patched into whatever the file then holds, so direct edits made
while the app ran survive (rulings #249, #290). CLI value overrides govern the
session and are never written (rulings #235, #240).

Reads are unrestricted. Of a mid-session re-read only the keys under
``thresholds`` are applied to the running session (rulings #291, #292);
every other key waits for the next launch (#294).

Invalid VALUES raise ``ConfigError`` with a message that names the key, what
was expected and what was found (V1). A file that is not JSON at all is moved
aside to ``config.json.corrupt``, logged, and recreated with defaults.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Optional, TypedDict

logger = logging.getLogger(__name__)


class PositionConfig(TypedDict):
    x: int
    y: int


class BandConfig(TypedDict):
    yellow: float
    red: float


class ThresholdsConfig(TypedDict):
    conpty: BandConfig
    memory_percent: BandConfig
    process_count: BandConfig
    handle_count: BandConfig


class TelltaleWindows(TypedDict):
    short: float
    medium: float
    long: float


class AppConfig(TypedDict):
    polling_interval_seconds: float
    theme: str
    size: int
    opacity: float
    always_on_top: bool
    position: PositionConfig
    thresholds: ThresholdsConfig
    telltale_windows: TelltaleWindows
    show_driver_label: bool
    show_digital_readout: bool
    show_session_count: bool


THEMES = ("dark", "light", "neon", "classic")
METRICS = ("conpty", "memory_percent", "process_count", "handle_count")
WINDOWS = ("short", "medium", "long")

DEFAULT_CONFIG: AppConfig = {
    "polling_interval_seconds": 2,
    "theme": "dark",
    "size": 300,
    "opacity": 0.9,
    "always_on_top": True,
    "position": {"x": 100, "y": 100},
    "thresholds": {
        "conpty": {"yellow": 30, "red": 60},
        "memory_percent": {"yellow": 60, "red": 80},
        "process_count": {"yellow": 300, "red": 500},
        "handle_count": {"yellow": 30000, "red": 50000},
    },
    "telltale_windows": {"short": 60, "medium": 600, "long": 3600},
    "show_driver_label": True,
    "show_digital_readout": True,
    "show_session_count": True,
}


class ConfigError(ValueError):
    """A config value that cannot be used. The message names the key, the expectation, the value."""


def default_config_path() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home())
        return Path(base) / "boostgauge" / "config.json"
    return Path.home() / ".boostgauge" / "config.json"


# ---- validation (V1) ---------------------------------------------------------


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _expect(condition: bool, key: str, expected: str, got: Any) -> None:
    if not condition:
        raise ConfigError(f"config key {key!r}: expected {expected}, got {got!r}")


def validate(config: dict) -> None:
    """Raise ``ConfigError`` naming the first key whose value cannot be used."""
    v = config.get("polling_interval_seconds")
    _expect(_is_number(v) and v > 0, "polling_interval_seconds", "a number of seconds > 0", v)
    v = config.get("theme")
    _expect(v in THEMES, "theme", "one of " + ", ".join(THEMES), v)
    v = config.get("size")
    _expect(_is_int(v) and v >= 64, "size", "an integer number of pixels >= 64", v)
    v = config.get("opacity")
    _expect(_is_number(v) and 0.0 <= v <= 1.0, "opacity", "a number between 0.0 and 1.0", v)
    v = config.get("always_on_top")
    _expect(isinstance(v, bool), "always_on_top", "true or false", v)
    pos = config.get("position")
    _expect(isinstance(pos, dict) and _is_int(pos.get("x")) and _is_int(pos.get("y")),
            "position", "an object with integer x and y", pos)
    th = config.get("thresholds")
    _expect(isinstance(th, dict), "thresholds", "an object with one band per metric", th)
    for metric in METRICS:
        band = th.get(metric)
        ok = (isinstance(band, dict) and _is_number(band.get("yellow")) and _is_number(band.get("red"))
              and 0 <= band["yellow"] < band["red"])
        _expect(ok, f"thresholds.{metric}", "an object with numbers 0 <= yellow < red", band)
    tw = config.get("telltale_windows")
    _expect(isinstance(tw, dict), "telltale_windows", "an object with short, medium, long", tw)
    for window in WINDOWS:
        v = tw.get(window)
        _expect(_is_number(v) and v > 0, f"telltale_windows.{window}", "a number of seconds > 0", v)
    for key in ("show_driver_label", "show_digital_readout", "show_session_count"):
        v = config.get(key)
        _expect(isinstance(v, bool), key, "true or false", v)


# ---- file I/O --------------------------------------------------------------------


def _atomic_write(path: Path, data: dict) -> None:
    """Write ``data`` as JSON via a temp file in the same directory, then replace."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _deep_merge(base: dict, override: dict) -> None:
    for key, value in override.items():
        if isinstance(base.get(key), dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def _read_json(path: Path) -> Optional[dict]:
    """The file's JSON object, or None when the file is not valid JSON."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _recover_corrupt(path: Path) -> None:
    corrupt = path.with_name(path.name + ".corrupt")
    try:
        if corrupt.exists():
            corrupt.unlink()
    except OSError as exc:
        logger.error("could not remove the previous corrupt backup %s: %s", corrupt, exc)
    os.replace(path, corrupt)
    logger.error("config at %s is not valid JSON; moved it to %s and recreated the file with defaults",
                 path, corrupt)
    _atomic_write(path, deepcopy(DEFAULT_CONFIG))


# ---- the three write moments + the launch read --------------------------------------


def load_config(path, reset_flag: bool = False, cli_overrides: Optional[dict] = None) -> AppConfig:
    """Launch order (#7): reset if flagged, read (auto-create if missing), CLI overrides in memory.

    Raises ``ConfigError`` for an unusable value, from the file or the CLI.
    """
    path = Path(path)
    if reset_flag:
        _atomic_write(path, deepcopy(DEFAULT_CONFIG))
        logger.info("config reset to defaults at %s", path)
    if not path.exists():
        _atomic_write(path, deepcopy(DEFAULT_CONFIG))
        logger.info("config created with defaults at %s", path)

    disk = _read_json(path)
    if disk is None:
        _recover_corrupt(path)
        disk = {}

    config: dict = deepcopy(DEFAULT_CONFIG)
    _deep_merge(config, disk)
    if cli_overrides:
        config.update(cli_overrides)
    validate(config)
    logger.info("config loaded from %s", path)
    return config  # type: ignore[return-value]


def apply_threshold_updates(path, current: AppConfig) -> AppConfig:
    """Re-read the file; apply ONLY the keys under ``thresholds`` (rulings #291, #292).

    Returns ``current`` itself when nothing usable changed. Never writes.
    """
    path = Path(path)
    try:
        disk = _read_json(path)
    except OSError as exc:
        logger.error("could not re-read config %s: %s", path, exc)
        return current
    if disk is None:
        logger.error("config at %s is not valid JSON; keeping the running thresholds", path)
        return current
    disk_thresholds = disk.get("thresholds")
    if not isinstance(disk_thresholds, dict):
        return current
    merged = deepcopy(current["thresholds"])
    _deep_merge(merged, disk_thresholds)
    if merged == current["thresholds"]:
        return current
    candidate = deepcopy(current)
    candidate["thresholds"] = merged
    try:
        validate(candidate)
    except ConfigError as exc:
        logger.error("ignoring threshold edit in %s: %s", path, exc)
        return current
    logger.info("thresholds reloaded from %s", path)
    return candidate


def save_session_changes(path, hand_changed_position: Optional[PositionConfig] = None,
                         hand_changed_size: Optional[int] = None) -> bool:
    """The exit write: patch exactly the hand-changed keys into the file as it is now.

    Returns True when a write happened. With nothing hand-changed there is no
    write at all (B1), so the file's bytes are untouched.
    """
    if hand_changed_position is None and hand_changed_size is None:
        return False
    path = Path(path)
    try:
        disk = _read_json(path)
    except OSError as exc:
        logger.error("could not read config %s for the exit write: %s", path, exc)
        return False
    if disk is None:
        logger.error("config at %s is not valid JSON; exit write skipped", path)
        return False
    if hand_changed_position is not None:
        disk["position"] = dict(hand_changed_position)
    if hand_changed_size is not None:
        disk["size"] = hand_changed_size
    _atomic_write(path, disk)
    logger.info("exit write saved hand-made changes to %s", path)
    return True


# ---- bridge to the collector (#4 left this for #7) ------------------------------------


def thresholds_from_config(config: dict):
    """The collector's ``Thresholds`` built from the config's ``thresholds`` object."""
    from boostgauge.collector import Band, Thresholds

    th = config["thresholds"]

    def band(metric: str) -> Band:
        return Band(th[metric]["yellow"], th[metric]["red"])

    return Thresholds(conpty=band("conpty"), memory_percent=band("memory_percent"),
                      process_count=band("process_count"), handle_count=band("handle_count"))


# ---- CLI ------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="boostgauge",
        description="Real-time system monitor styled like a racing tachometer.")
    parser.add_argument("--theme", choices=THEMES, help="visual theme")
    parser.add_argument("--size", type=int, metavar="PIXELS", help="gauge diameter in pixels (default 300)")
    parser.add_argument("--poll", type=float, metavar="SECONDS", help="polling interval (default 2)")
    parser.add_argument("--opacity", type=float, metavar="FLOAT", help="window opacity 0.0-1.0 (default 0.9)")
    parser.add_argument("--no-topmost", action="store_true", help="don't keep the window on top")
    parser.add_argument("--config", type=Path, metavar="PATH", help="path to the config file")
    parser.add_argument("--reset-config", action="store_true", help="reset the config file to defaults")
    return parser


def parse_cli(argv: Optional[list[str]] = None) -> tuple[Path, bool, dict]:
    """(config path, reset flag, session overrides) from the command line.

    Overrides carry only the flags actually given, keyed by config name.
    """
    args = build_parser().parse_args(argv)
    overrides: dict = {}
    if args.theme is not None:
        overrides["theme"] = args.theme
    if args.size is not None:
        overrides["size"] = args.size
    if args.poll is not None:
        overrides["polling_interval_seconds"] = args.poll
    if args.opacity is not None:
        overrides["opacity"] = args.opacity
    if args.no_topmost:
        overrides["always_on_top"] = False
    return (args.config or default_config_path()), bool(args.reset_config), overrides
