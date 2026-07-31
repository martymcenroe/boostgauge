"""Configuration management system for BoostGauge.

Issue #7: Configuration File and CLI Arguments
Provides path resolution, schema validation, atomic JSON persistence,
CLI argument parsing, and override semantics.
"""

import argparse
import copy
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, TypedDict


class ConfigError(Exception):
    """Raised when configuration parsing, validation, or path resolution fails."""
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


VALID_THEMES = {"dark", "light", "neon", "classic"}


def get_default_config_path() -> Path:
    """Return platform-specific default config path.

    %APPDATA%/boostgauge/config.json on Windows, ~/.boostgauge/config.json on POSIX.
    """
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
    """Return a deep copy of default GaugeConfigDict."""
    return {
        "polling_interval_seconds": 1.0,
        "theme": "dark",
        "size": 300,
        "opacity": 0.9,
        "always_on_top": True,
        "position": {"x": 100, "y": 100},
        "thresholds": {
            "conpty": {"yellow": 8.0, "red": 16.0},
            "memory_percent": {"yellow": 75.0, "red": 90.0},
            "process_count": {"yellow": 50.0, "red": 100.0},
            "handle_count": {"yellow": 1000.0, "red": 5000.0},
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


def validate_config(config: Dict[str, Any]) -> GaugeConfigDict:
    """Validate keys, types, and numerical bounds of a configuration dictionary."""
    if not isinstance(config, dict):
        raise ConfigError("Configuration root must be a JSON object.")

    defaults = get_default_config()
    required_keys = set(defaults.keys())
    missing_keys = required_keys - set(config.keys())
    if missing_keys:
        raise ConfigError(f"Missing required config key: '{sorted(list(missing_keys))[0]}'.")

    poll = config.get("polling_interval_seconds")
    if not isinstance(poll, (int, float)) or isinstance(poll, bool) or poll < 0.1:
        raise ConfigError(f"Invalid 'polling_interval_seconds': {poll}. Must be a float >= 0.1.")

    theme = config.get("theme")
    if not isinstance(theme, str) or theme not in VALID_THEMES:
        raise ConfigError(f"Invalid 'theme': {theme}. Must be one of {sorted(list(VALID_THEMES))}.")

    size = config.get("size")
    if not isinstance(size, int) or isinstance(size, bool) or not (100 <= size <= 2000):
        raise ConfigError(f"Invalid 'size': {size}. Must be an integer between 100 and 2000.")

    opacity = config.get("opacity")
    if not isinstance(opacity, (int, float)) or isinstance(opacity, bool) or not (0.1 <= opacity <= 1.0):
        raise ConfigError(f"Invalid 'opacity': {opacity}. Must be between 0.1 and 1.0.")

    for bool_key in ("always_on_top", "show_driver_label", "show_digital_readout", "show_session_count"):
        val = config.get(bool_key)
        if not isinstance(val, bool):
            raise ConfigError(f"Invalid '{bool_key}': {val}. Must be a boolean.")

    pos = config.get("position")
    if not isinstance(pos, dict) or "x" not in pos or "y" not in pos:
        raise ConfigError("Invalid 'position': must be an object with integer 'x' and 'y' properties.")
    if not isinstance(pos["x"], int) or isinstance(pos["x"], bool) or not isinstance(pos["y"], int) or isinstance(pos["y"], bool):
        raise ConfigError("Invalid 'position': 'x' and 'y' must be integers.")

    thresholds = config.get("thresholds")
    if not isinstance(thresholds, dict):
        raise ConfigError("Invalid 'thresholds': must be a JSON object.")

    for m_key in ("conpty", "memory_percent", "process_count", "handle_count"):
        if m_key not in thresholds or not isinstance(thresholds[m_key], dict):
            raise ConfigError(f"Invalid threshold metric configuration for '{m_key}'.")
        t_dict = thresholds[m_key]
        if "yellow" not in t_dict or "red" not in t_dict:
            raise ConfigError(f"Threshold for '{m_key}' must specify 'yellow' and 'red' values.")
        y_val, r_val = t_dict["yellow"], t_dict["red"]
        if not isinstance(y_val, (int, float)) or isinstance(y_val, bool) or not isinstance(r_val, (int, float)) or isinstance(r_val, bool):
            raise ConfigError(f"Threshold values for '{m_key}' must be numeric.")
        if y_val >= r_val:
            raise ConfigError(f"Threshold 'yellow' ({y_val}) must be strictly less than 'red' ({r_val}) for '{m_key}'.")

    tt_windows = config.get("telltale_windows")
    if not isinstance(tt_windows, dict):
        raise ConfigError("Invalid 'telltale_windows': must be a JSON object.")
    for w_key in ("short", "medium", "long"):
        val = tt_windows.get(w_key)
        if not isinstance(val, int) or isinstance(val, bool) or val <= 0:
            raise ConfigError(f"Invalid telltale window for '{w_key}': must be a positive integer.")

    return config  # type: ignore[return-value]


def load_config_file(path: Path) -> GaugeConfigDict:
    """Load configuration from specified JSON file path; creates defaults if missing."""
    if not path.exists():
        default_cfg = get_default_config()
        save_config_file(default_cfg, path)
        return default_cfg

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Malformed JSON in config file '{path}': {exc}") from exc
    except PermissionError as exc:
        raise ConfigError(f"Permission denied accessing config file '{path}': {exc}") from exc
    except Exception as exc:
        raise ConfigError(f"Failed to read config file '{path}': {exc}") from exc

    return validate_config(data)


def save_config_file(config: GaugeConfigDict, path: Path) -> None:
    """Atomically write configuration dictionary as formatted JSON to path."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", dir=str(path.parent), delete=False, encoding="utf-8") as tf:
            json.dump(config, tf, indent=4)
            temp_name = tf.name

        os.replace(temp_name, str(path))
    except Exception as exc:
        if 'temp_name' in locals() and os.path.exists(temp_name):
            try:
                os.remove(temp_name)
            except OSError:
                pass
        raise ConfigError(f"Failed to save configuration to '{path}': {exc}") from exc


def create_cli_parser() -> argparse.ArgumentParser:
    """Construct ArgumentParser for BoostGauge CLI flags."""
    parser = argparse.ArgumentParser(
        prog="boostgauge",
        description="Lightweight system tachometer with peak-hold needles for monitoring AI agent resource pressure.",
    )
    parser.add_argument("--theme", choices=sorted(list(VALID_THEMES)), help="Set UI color theme.")
    parser.add_argument("--size", type=int, help="Gauge window size in pixels (100-2000).")
    parser.add_argument("--poll", type=float, help="Polling interval in seconds (>= 0.1).")
    parser.add_argument("--opacity", type=float, help="Window opacity (0.1-1.0).")
    parser.add_argument("--no-topmost", action="store_true", help="Disable always-on-top window behavior.")
    parser.add_argument("--config", type=str, help="Path to custom JSON configuration file.")
    parser.add_argument("--reset-config", action="store_true", help="Reset configuration file to default settings.")
    return parser


def parse_cli_args(args: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments from given list or sys.argv."""
    parser = create_cli_parser()
    return parser.parse_args(args)


def merge_cli_overrides(config: GaugeConfigDict, cli_args: argparse.Namespace) -> GaugeConfigDict:
    """Apply non-None CLI options onto configuration dictionary."""
    merged = copy.deepcopy(config)

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

    return validate_config(merged)


def load_effective_config(args: Optional[list[str]] = None) -> Tuple[GaugeConfigDict, Path]:
    """Execute complete configuration loading pipeline."""
    cli_args = parse_cli_args(args)

    if cli_args.config:
        config_path = Path(cli_args.config).resolve()
    else:
        config_path = get_default_config_path()

    if cli_args.reset_config:
        default_cfg = get_default_config()
        save_config_file(default_cfg, config_path)
        effective = merge_cli_overrides(default_cfg, cli_args)
        return effective, config_path

    file_config = load_config_file(config_path)
    effective_config = merge_cli_overrides(file_config, cli_args)
    return effective_config, config_path


def update_window_geometry(
    config: GaugeConfigDict,
    path: Path,
    x: int,
    y: int,
    size: int,
) -> GaugeConfigDict:
    """Update window position and size in config dict and save atomically to disk."""
    updated = copy.deepcopy(config)
    updated["position"] = {"x": x, "y": y}
    updated["size"] = size
    validated = validate_config(updated)
    save_config_file(validated, path)
    return validated