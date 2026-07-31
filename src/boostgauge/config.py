"""Configuration loader, schema validation, persistence, and CLI argument parsing.

Issue #7: Configuration file and CLI arguments
"""

from __future__ import annotations

import argparse
import copy
import json
import logging
import os
import platform
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict

logger = logging.getLogger("boostgauge.config")


class ThresholdValues(TypedDict):
    yellow: float
    red: float


class ThresholdsConfig(TypedDict):
    conpty: ThresholdValues
    memory_percent: ThresholdValues
    process_count: ThresholdValues
    handle_count: ThresholdValues


class PositionConfig(TypedDict):
    x: int
    y: int


class TelltaleWindowsConfig(TypedDict):
    short: int
    medium: int
    long: int


class ConfigData(TypedDict):
    polling_interval_seconds: float
    theme: str
    size: int
    opacity: float
    always_on_top: bool
    position: PositionConfig
    thresholds: ThresholdsConfig
    telltale_windows: TelltaleWindowsConfig
    show_driver_label: bool
    show_digital_readout: bool
    show_session_count: bool


DEFAULT_CONFIG: ConfigData = {
    "polling_interval_seconds": 1.0,
    "theme": "dark",
    "size": 300,
    "opacity": 1.0,
    "always_on_top": True,
    "position": {"x": 100, "y": 100},
    "thresholds": {
        "conpty": {"yellow": 5.0, "red": 10.0},
        "memory_percent": {"yellow": 70.0, "red": 85.0},
        "process_count": {"yellow": 50.0, "red": 100.0},
        "handle_count": {"yellow": 1000.0, "red": 2000.0},
    },
    "telltale_windows": {"short": 60, "medium": 600, "long": 3600},
    "show_driver_label": True,
    "show_digital_readout": True,
    "show_session_count": True,
}


def get_default_config_path() -> Path:
    """Return platform-specific default config path (%APPDATA%/boostgauge/config.json or ~/.boostgauge/config.json)."""
    if platform.system() == "Windows":
        appdata = os.environ.get("APPDATA")
        if appdata:
            base_dir = Path(appdata)
        else:
            base_dir = Path.home() / "AppData" / "Roaming"
        return base_dir / "boostgauge" / "config.json"
    else:
        return Path.home() / ".boostgauge" / "config.json"


def get_default_config() -> ConfigData:
    """Return dictionary containing factory default configuration settings."""
    return copy.deepcopy(DEFAULT_CONFIG)


def validate_config(data: Dict[str, Any]) -> ConfigData:
    """Validate raw dictionary against expected types and ranges; fill missing or invalid keys with defaults."""
    defaults = get_default_config()
    if not isinstance(data, dict):
        logger.warning("Configuration data is not a dictionary. Falling back to default configuration.")
        return defaults

    result: Dict[str, Any] = copy.deepcopy(defaults)

    if "polling_interval_seconds" in data:
        val = data["polling_interval_seconds"]
        if isinstance(val, (int, float)) and val > 0:
            result["polling_interval_seconds"] = float(val)
        else:
            logger.warning("Invalid polling_interval_seconds '%s'. Expected positive float.", val)

    if "theme" in data:
        val = data["theme"]
        if isinstance(val, str) and val.strip():
            result["theme"] = val.strip()
        else:
            logger.warning("Invalid theme '%s'. Expected non-empty string.", val)

    if "size" in data:
        val = data["size"]
        if isinstance(val, int) and val >= 50:
            result["size"] = val
        else:
            logger.warning("Invalid size '%s'. Expected integer >= 50.", val)

    if "opacity" in data:
        val = data["opacity"]
        if isinstance(val, (int, float)) and 0.1 <= float(val) <= 1.0:
            result["opacity"] = float(val)
        else:
            logger.warning("Invalid opacity '%s'. Expected float between 0.1 and 1.0.", val)

    if "always_on_top" in data:
        val = data["always_on_top"]
        if isinstance(val, bool):
            result["always_on_top"] = val
        else:
            logger.warning("Invalid always_on_top '%s'. Expected boolean.", val)

    if "show_driver_label" in data:
        val = data["show_driver_label"]
        if isinstance(val, bool):
            result["show_driver_label"] = val

    if "show_digital_readout" in data:
        val = data["show_digital_readout"]
        if isinstance(val, bool):
            result["show_digital_readout"] = val

    if "show_session_count" in data:
        val = data["show_session_count"]
        if isinstance(val, bool):
            result["show_session_count"] = val

    if "position" in data and isinstance(data["position"], dict):
        pos = data["position"]
        if "x" in pos and isinstance(pos["x"], int):
            result["position"]["x"] = pos["x"]
        if "y" in pos and isinstance(pos["y"], int):
            result["position"]["y"] = pos["y"]

    if "thresholds" in data and isinstance(data["thresholds"], dict):
        thresholds_in = data["thresholds"]
        for key in ("conpty", "memory_percent", "process_count", "handle_count"):
            if key in thresholds_in and isinstance(thresholds_in[key], dict):
                t_val = thresholds_in[key]
                if "yellow" in t_val and isinstance(t_val["yellow"], (int, float)):
                    result["thresholds"][key]["yellow"] = float(t_val["yellow"])
                if "red" in t_val and isinstance(t_val["red"], (int, float)):
                    result["thresholds"][key]["red"] = float(t_val["red"])

    if "telltale_windows" in data and isinstance(data["telltale_windows"], dict):
        tw_in = data["telltale_windows"]
        for key in ("short", "medium", "long"):
            if key in tw_in and isinstance(tw_in[key], int) and tw_in[key] > 0:
                result["telltale_windows"][key] = tw_in[key]

    return result  # type: ignore[return-value]


def load_config(config_path: Optional[Path] = None) -> ConfigData:
    """Load configuration from file. Create with defaults if missing. Fallback to defaults on corrupt JSON."""
    target_path = config_path if config_path is not None else get_default_config_path()

    if not target_path.exists():
        logger.info("Config file missing at %s. Creating default config.", target_path)
        defaults = get_default_config()
        save_config(defaults, target_path)
        return defaults

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
        return validate_config(raw_data)
    except Exception as exc:
        logger.warning("Failed to parse config file at %s (%s). Falling back to default configuration.", target_path, exc)
        return get_default_config()


def save_config(config: ConfigData, config_path: Optional[Path] = None) -> None:
    """Write configuration dictionary to specified path atomically with pretty formatting."""
    target_path = config_path if config_path is not None else get_default_config_path()

    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = target_path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
        tmp_path.replace(target_path)
    except OSError as exc:
        logger.error("Failed to save config file atomically to %s: %s", target_path, exc)


def reset_config(config_path: Optional[Path] = None) -> ConfigData:
    """Overwrite configuration file with default settings and return default ConfigData."""
    defaults = get_default_config()
    save_config(defaults, config_path)
    return defaults


def _bounded_float(min_val: float, max_val: float):
    def type_checker(arg_str: str) -> float:
        try:
            val = float(arg_str)
        except ValueError:
            raise argparse.ArgumentTypeError(f"Must be a floating point number (got '{arg_str}')")
        if not (min_val <= val <= max_val):
            raise argparse.ArgumentTypeError(f"Must be between {min_val} and {max_val} (got {val})")
        return val

    return type_checker


def _positive_int(arg_str: str) -> int:
    try:
        val = int(arg_str)
    except ValueError:
        raise argparse.ArgumentTypeError(f"Must be an integer (got '{arg_str}')")
    if val < 50:
        raise argparse.ArgumentTypeError(f"Size must be >= 50 (got {val})")
    return val


def parse_cli_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments supporting theme, size, poll, opacity, no-topmost, config path, and reset-config."""
    parser = argparse.ArgumentParser(description="BoostGauge system monitor tachometer")
    parser.add_argument("--theme", type=str, default=None, help="Visual theme name")
    parser.add_argument("--size", type=_positive_int, default=None, help="Gauge window size in pixels (>= 50)")
    parser.add_argument("--poll", type=float, default=None, help="Polling interval in seconds")
    parser.add_argument("--opacity", type=_bounded_float(0.1, 1.0), default=None, help="Window opacity (0.1 to 1.0)")
    parser.add_argument("--no-topmost", action="store_true", default=False, help="Disable always-on-top window behavior")
    parser.add_argument("--config", type=str, default=None, help="Path to custom JSON configuration file")
    parser.add_argument("--reset-config", action="store_true", default=False, help="Reset configuration file to factory defaults")

    return parser.parse_args(args)


def merge_config_and_cli(config: ConfigData, cli_args: argparse.Namespace) -> ConfigData:
    """Return a new ConfigData dictionary where non-None CLI options override config file settings."""
    merged: ConfigData = copy.deepcopy(config)

    if cli_args.theme is not None:
        merged["theme"] = cli_args.theme

    if cli_args.size is not None:
        merged["size"] = cli_args.size

    if cli_args.poll is not None:
        merged["polling_interval_seconds"] = cli_args.poll

    if cli_args.opacity is not None:
        merged["opacity"] = cli_args.opacity

    if cli_args.no_topmost:
        merged["always_on_top"] = False

    return merged


def update_window_state(
    config: ConfigData, x: int, y: int, size: int, config_path: Optional[Path] = None
) -> ConfigData:
    """Update position and size in config state and persist to disk."""
    updated: ConfigData = copy.deepcopy(config)
    updated["position"]["x"] = x
    updated["position"]["y"] = y
    updated["size"] = size
    save_config(updated, config_path)
    return updated