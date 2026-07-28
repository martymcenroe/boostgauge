"""Configuration management module for BoostGauge.

Handles settings persistence, path resolution, JSON I/O, validation, and CLI overrides.
Issue #7: Configuration File and CLI Arguments
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, TypedDict


class ConfigError(Exception):
    """Raised when configuration file or CLI arguments fail schema or value validation."""

    pass


class Threshold(TypedDict):
    yellow: float
    red: float


class MetricThresholds(TypedDict):
    conpty: Threshold
    memory_percent: Threshold
    process_count: Threshold
    handle_count: Threshold


class WindowPosition(TypedDict):
    x: int
    y: int


class TelltaleWindows(TypedDict):
    short: int
    medium: int
    long: int


class GaugeConfigDict(TypedDict):
    polling_interval_seconds: float
    theme: str
    size: int
    opacity: float
    always_on_top: bool
    position: WindowPosition
    thresholds: MetricThresholds
    telltale_windows: TelltaleWindows
    show_driver_label: bool
    show_digital_readout: bool
    show_session_count: bool


VALID_THEMES = {"dark", "light", "amber", "carbon"}


def get_default_config_path() -> Path:
    """Return platform-specific default config path (%APPDATA%/boostgauge/config.json on Windows, ~/.boostgauge/config.json on POSIX)."""
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            base_dir = Path(appdata)
        else:
            base_dir = Path.home() / "AppData" / "Roaming"
        return base_dir / "boostgauge" / "config.json"
    else:
        return Path.home() / ".boostgauge" / "config.json"


def get_default_config() -> GaugeConfigDict:
    """Return deep copy of default configuration dictionary."""
    return copy.deepcopy({
        "polling_interval_seconds": 1.0,
        "theme": "dark",
        "size": 300,
        "opacity": 0.9,
        "always_on_top": True,
        "position": {"x": 100, "y": 100},
        "thresholds": {
            "conpty": {"yellow": 20.0, "red": 30.0},
            "memory_percent": {"yellow": 70.0, "red": 85.0},
            "process_count": {"yellow": 150.0, "red": 300.0},
            "handle_count": {"yellow": 10000.0, "red": 20000.0},
        },
        "telltale_windows": {"short": 60, "medium": 600, "long": 3600},
        "show_driver_label": True,
        "show_digital_readout": True,
        "show_session_count": True,
    })


def validate_config(config: Dict[str, Any]) -> GaugeConfigDict:
    """Validate structure and value bounds of a configuration dictionary, returning typed GaugeConfigDict or raising ConfigError."""
    if not isinstance(config, dict):
        raise ConfigError("Configuration root must be a JSON object")

    poll = config.get("polling_interval_seconds")
    if not isinstance(poll, (int, float)) or isinstance(poll, bool) or poll <= 0:
        raise ConfigError("polling_interval_seconds must be a positive number")

    theme = config.get("theme")
    if not isinstance(theme, str) or theme not in VALID_THEMES:
        sorted_themes = ", ".join(sorted(VALID_THEMES))
        raise ConfigError(f"Invalid theme '{theme}'. Supported themes: {sorted_themes}")

    size = config.get("size")
    if not isinstance(size, int) or isinstance(size, bool) or size < 50 or size > 2000:
        raise ConfigError("size must be an integer between 50 and 2000")

    opacity = config.get("opacity")
    if not isinstance(opacity, (int, float)) or isinstance(opacity, bool) or opacity < 0.0 or opacity > 1.0:
        raise ConfigError("opacity must be between 0.0 and 1.0")

    always_on_top = config.get("always_on_top")
    if not isinstance(always_on_top, bool):
        raise ConfigError("always_on_top must be a boolean")

    pos = config.get("position")
    if not isinstance(pos, dict) or "x" not in pos or "y" not in pos:
        raise ConfigError("position must be an object with 'x' and 'y' integer coordinates")
    if not isinstance(pos["x"], int) or isinstance(pos["x"], bool) or not isinstance(pos["y"], int) or isinstance(pos["y"], bool):
        raise ConfigError("position 'x' and 'y' must be integers")

    thresholds = config.get("thresholds")
    if not isinstance(thresholds, dict):
        raise ConfigError("thresholds must be an object")

    required_metrics = {"conpty", "memory_percent", "process_count", "handle_count"}
    for metric in required_metrics:
        m_val = thresholds.get(metric)
        if not isinstance(m_val, dict) or "yellow" not in m_val or "red" not in m_val:
            raise ConfigError(f"Threshold for '{metric}' must contain 'yellow' and 'red' values")
        y, r = m_val["yellow"], m_val["red"]
        if not isinstance(y, (int, float)) or isinstance(y, bool) or not isinstance(r, (int, float)) or isinstance(r, bool):
            raise ConfigError(f"Threshold values for '{metric}' must be numbers")
        if y < 0 or r < 0:
            raise ConfigError(f"Threshold values for '{metric}' must be non-negative")
        if y >= r:
            raise ConfigError(f"Threshold yellow must be strictly less than red for {metric}")

    tw = config.get("telltale_windows")
    if not isinstance(tw, dict) or not {"short", "medium", "long"}.issubset(tw.keys()):
        raise ConfigError("telltale_windows must contain 'short', 'medium', and 'long' integer values")
    s, m, l_win = tw["short"], tw["medium"], tw["long"]
    if not (isinstance(s, int) and not isinstance(s, bool) and isinstance(m, int) and not isinstance(m, bool) and isinstance(l_win, int) and not isinstance(l_win, bool)):
        raise ConfigError("telltale_windows values must be integers")
    if not (0 < s < m < l_win):
        raise ConfigError("telltale_windows values must satisfy 0 < short < medium < long")

    for flag in ("show_driver_label", "show_digital_readout", "show_session_count"):
        if not isinstance(config.get(flag), bool):
            raise ConfigError(f"{flag} must be a boolean")

    return copy.deepcopy(config)  # type: ignore[return-value]


def load_config(config_path: Optional[Path] = None) -> GaugeConfigDict:
    """Load configuration from specified path (or default path), auto-creating default config if file is missing."""
    target_path = config_path.resolve() if config_path else get_default_config_path()

    if not target_path.exists():
        default_cfg = get_default_config()
        save_config(default_cfg, target_path)
        return default_cfg

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Failed to parse config JSON at {target_path}: {exc}") from exc
    except OSError as exc:
        raise ConfigError(f"Failed to read config file at {target_path}: {exc}") from exc

    return validate_config(data)


def save_config(config: GaugeConfigDict, config_path: Optional[Path] = None) -> None:
    """Atomically write configuration dictionary to JSON file at specified path (or default path)."""
    target_path = config_path.resolve() if config_path else get_default_config_path()
    target_path.parent.mkdir(parents=True, exist_ok=True)

    validated = validate_config(config)

    tmp_path = target_path.with_suffix(f"{target_path.suffix}.tmp_{os.getpid()}")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(validated, f, indent=2)
        os.replace(tmp_path, target_path)
    except Exception as exc:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise ConfigError(f"Failed to save config file to {target_path}: {exc}") from exc


def parse_cli_args(args: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse CLI options for theme, size, poll, opacity, topmost, config path, and reset flag."""
    parser = argparse.ArgumentParser(
        prog="boostgauge",
        description="BoostGauge: Tachometer-styled system pressure monitor.",
    )
    parser.add_argument("--theme", choices=sorted(VALID_THEMES), help="Gauge color theme")
    parser.add_argument("--size", type=int, help="Gauge window size in pixels")
    parser.add_argument("--poll", type=float, help="Polling interval in seconds")
    parser.add_argument("--opacity", type=float, help="Window opacity (0.0 to 1.0)")
    parser.add_argument("--no-topmost", action="store_true", help="Disable always-on-top window behavior")
    parser.add_argument("--config", type=Path, help="Path to custom JSON configuration file")
    parser.add_argument("--reset-config", action="store_true", help="Reset configuration file to default settings")

    return parser.parse_args(args if args is not None else sys.argv[1:])


def apply_cli_overrides(config: GaugeConfigDict, parsed_args: argparse.Namespace) -> GaugeConfigDict:
    """Apply parsed CLI arguments as overrides on top of loaded configuration dictionary."""
    updated = copy.deepcopy(config)

    if parsed_args.theme is not None:
        updated["theme"] = parsed_args.theme
    if parsed_args.size is not None:
        updated["size"] = parsed_args.size
    if parsed_args.poll is not None:
        updated["polling_interval_seconds"] = parsed_args.poll
    if parsed_args.opacity is not None:
        updated["opacity"] = parsed_args.opacity
    if getattr(parsed_args, "no_topmost", False):
        updated["always_on_top"] = False

    return updated


def update_window_geometry(config: GaugeConfigDict, x: int, y: int, size: int) -> GaugeConfigDict:
    """Update window position and size parameters in configuration data structure prior to exit/save."""
    updated = copy.deepcopy(config)
    updated["position"] = {"x": x, "y": y}
    updated["size"] = size
    return updated