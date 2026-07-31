"""Configuration management module for BoostGauge.

Issue #7: Configuration file and CLI arguments.
Handles loading, validating, saving JSON configuration settings, and parsing CLI arguments.
"""

from __future__ import annotations

import argparse
import copy
import json
import logging
import os
import platform
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict

logger = logging.getLogger(__name__)


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
        "conpty": {"yellow": 10.0, "red": 20.0},
        "memory_percent": {"yellow": 75.0, "red": 90.0},
        "process_count": {"yellow": 150.0, "red": 300.0},
        "handle_count": {"yellow": 10000.0, "red": 20000.0},
    },
    "telltale_windows": {
        "short": 60,
        "medium": 600,
        "long": 3600,
    },
    "show_driver_label": True,
    "show_digital_readout": True,
    "show_session_count": True,
}


def get_default_config_path() -> Path:
    """Return platform-specific default configuration path (%APPDATA%/boostgauge/config.json or ~/.boostgauge/config.json)."""
    if platform.system() == "Windows":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "boostgauge" / "config.json"
    return Path.home() / ".boostgauge" / "config.json"


def get_default_config() -> ConfigData:
    """Return a dictionary containing factory default configuration settings."""
    return copy.deepcopy(DEFAULT_CONFIG)


def validate_config(data: Dict[str, Any]) -> ConfigData:
    """Validate raw configuration dictionary against expected types/bounds and inject missing fields from defaults."""
    defaults = get_default_config()

    if not isinstance(data, dict):
        logger.warning("Configuration payload is not a valid JSON object. Using defaults.")
        return defaults

    result: ConfigData = copy.deepcopy(defaults)

    if "polling_interval_seconds" in data:
        val = data["polling_interval_seconds"]
        if isinstance(val, (int, float)) and val > 0:
            result["polling_interval_seconds"] = float(val)
        else:
            logger.warning("Invalid polling_interval_seconds: %r. Reverting to default.", val)

    if "theme" in data:
        val = data["theme"]
        if isinstance(val, str) and val.strip():
            result["theme"] = val
        else:
            logger.warning("Invalid theme: %r. Reverting to default.", val)

    if "size" in data:
        val = data["size"]
        if isinstance(val, int) and val > 0:
            result["size"] = val
        else:
            logger.warning("Invalid size: %r. Reverting to default.", val)

    if "opacity" in data:
        val = data["opacity"]
        if isinstance(val, (int, float)) and 0.0 <= float(val) <= 1.0:
            result["opacity"] = float(val)
        else:
            logger.warning("Invalid opacity: %r. Reverting to default.", val)

    if "always_on_top" in data:
        val = data["always_on_top"]
        if isinstance(val, bool):
            result["always_on_top"] = val
        else:
            logger.warning("Invalid always_on_top: %r. Reverting to default.", val)

    if "show_driver_label" in data and isinstance(data["show_driver_label"], bool):
        result["show_driver_label"] = data["show_driver_label"]
    if "show_digital_readout" in data and isinstance(data["show_digital_readout"], bool):
        result["show_digital_readout"] = data["show_digital_readout"]
    if "show_session_count" in data and isinstance(data["show_session_count"], bool):
        result["show_session_count"] = data["show_session_count"]

    if "position" in data and isinstance(data["position"], dict):
        pos = data["position"]
        if "x" in pos and isinstance(pos["x"], int):
            result["position"]["x"] = pos["x"]
        if "y" in pos and isinstance(pos["y"], int):
            result["position"]["y"] = pos["y"]

    if "telltale_windows" in data and isinstance(data["telltale_windows"], dict):
        tw = data["telltale_windows"]
        for k in ("short", "medium", "long"):
            if k in tw and isinstance(tw[k], int) and tw[k] > 0:
                result["telltale_windows"][k] = tw[k]  # type: ignore[literal-required]

    if "thresholds" in data and isinstance(data["thresholds"], dict):
        thresh = data["thresholds"]
        for cat in ("conpty", "memory_percent", "process_count", "handle_count"):
            if cat in thresh and isinstance(thresh[cat], dict):
                cat_dict = thresh[cat]
                for level in ("yellow", "red"):
                    if level in cat_dict and isinstance(cat_dict[level], (int, float)):
                        result["thresholds"][cat][level] = float(cat_dict[level])  # type: ignore[literal-required]

    return result


def load_config(config_path: Optional[Path] = None) -> ConfigData:
    """Load configuration from disk. Auto-create with defaults if file missing; recover gracefully on corrupt JSON."""
    target_path = config_path if config_path is not None else get_default_config_path()

    if not target_path.exists():
        logger.info("Config file missing at %s. Creating with defaults.", target_path)
        defaults = get_default_config()
        save_config(defaults, target_path)
        return defaults

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
        return validate_config(raw_data)
    except (json.JSONDecodeError, OSError) as err:
        logger.warning("Error reading config file %s: %s. Using default configuration.", target_path, err)
        return get_default_config()


def save_config(config: ConfigData, config_path: Optional[Path] = None) -> None:
    """Write configuration dictionary atomically to disk using a temporary file and os.replace."""
    target_path = config_path if config_path is not None else get_default_config_path()

    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = target_path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
        os.replace(tmp_path, target_path)
    except OSError as err:
        logger.warning("Failed to save configuration to %s: %s", target_path, err)


def reset_config(config_path: Optional[Path] = None) -> ConfigData:
    """Overwrite target configuration file with default settings and return default ConfigData."""
    defaults = get_default_config()
    target_path = config_path if config_path is not None else get_default_config_path()
    save_config(defaults, target_path)
    return defaults


def parse_cli_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse CLI options for theme, size, poll interval, opacity, no-topmost, config path, and reset-config."""
    parser = argparse.ArgumentParser(description="BoostGauge System Tachometer")

    parser.add_argument("--theme", type=str, default=None, help="Visual theme name")
    parser.add_argument("--size", type=int, default=None, help="Gauge pixel diameter (> 0)")
    parser.add_argument("--poll", type=float, default=None, help="Polling interval in seconds (> 0)")
    parser.add_argument("--opacity", type=float, default=None, help="Window opacity (0.0 to 1.0)")
    parser.add_argument(
        "--no-topmost",
        action="store_true",
        default=False,
        help="Disable always-on-top window behavior",
    )
    parser.add_argument("--config", type=str, default=None, help="Path to custom JSON config file")
    parser.add_argument(
        "--reset-config",
        action="store_true",
        default=False,
        help="Reset configuration file to factory defaults",
    )

    parsed = parser.parse_args(args if args is not None else sys.argv[1:])

    if parsed.size is not None and parsed.size <= 0:
        parser.error("--size must be a positive integer")
    if parsed.poll is not None and parsed.poll <= 0:
        parser.error("--poll must be a positive number")
    if parsed.opacity is not None and not (0.0 <= parsed.opacity <= 1.0):
        parser.error("--opacity must be between 0.0 and 1.0")

    return parsed


def merge_config_and_cli(config: ConfigData, cli_args: argparse.Namespace) -> ConfigData:
    """Return a new ConfigData object where non-None CLI options override configuration settings."""
    merged = copy.deepcopy(config)

    if cli_args.theme is not None:
        merged["theme"] = cli_args.theme

    if cli_args.size is not None:
        merged["size"] = cli_args.size

    if cli_args.poll is not None:
        merged["polling_interval_seconds"] = cli_args.poll

    if cli_args.opacity is not None:
        merged["opacity"] = cli_args.opacity

    if getattr(cli_args, "no_topmost", False):
        merged["always_on_top"] = False

    return merged


def update_window_state(
    config: ConfigData,
    x: int,
    y: int,
    size: int,
    config_path: Optional[Path] = None,
) -> ConfigData:
    """Update window position (x, y) and size parameters in configuration and persist to disk."""
    updated = copy.deepcopy(config)
    updated["position"]["x"] = int(x)
    updated["position"]["y"] = int(y)
    updated["size"] = int(size)

    save_config(updated, config_path)
    return updated