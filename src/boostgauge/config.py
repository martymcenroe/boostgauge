"""Configuration file loading, CLI parsing, validation, and persistence.

Issue #7: Feature configuration file and CLI arguments
"""

import argparse
import copy
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple, TypedDict, cast


class ThresholdRange(TypedDict):
    yellow: float
    red: float


class ThresholdsConfig(TypedDict):
    conpty: ThresholdRange
    memory_percent: ThresholdRange
    process_count: ThresholdRange
    handle_count: ThresholdRange


class WindowPosition(TypedDict):
    x: int
    y: int


class WindowConfigDict(TypedDict):
    x: int
    y: int
    size: int
    topmost: bool
    opacity: float
    compact_mode: bool


class VirtualScreenBounds(TypedDict):
    min_x: int
    min_y: int
    max_x: int
    max_y: int


class TelltaleWindowsConfig(TypedDict):
    short: int
    medium: int
    long: int


class BoostGaugeConfig(TypedDict):
    polling_interval_seconds: float
    theme: str
    size: int
    opacity: float
    always_on_top: bool
    compact_mode: bool
    position: WindowPosition
    thresholds: ThresholdsConfig
    telltale_windows: TelltaleWindowsConfig
    show_driver_label: bool
    show_digital_readout: bool
    show_session_count: bool


ALLOWED_THEMES = ["dark", "light", "stealth", "cyberpunk"]

DEFAULT_CONFIG: Dict[str, Any] = {
    "polling_interval_seconds": 1.0,
    "theme": "dark",
    "size": 300,
    "opacity": 1.0,
    "always_on_top": True,
    "compact_mode": False,
    "position": {"x": 100, "y": 100},
    "thresholds": {
        "conpty": {"yellow": 10.0, "red": 20.0},
        "memory_percent": {"yellow": 75.0, "red": 90.0},
        "process_count": {"yellow": 150.0, "red": 300.0},
        "handle_count": {"yellow": 50000.0, "red": 100000.0},
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
    """Return platform-dependent default configuration path (~/.boostgauge/config.json or %APPDATA%/boostgauge/config.json)."""
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            base_dir = Path(appdata)
        else:
            base_dir = Path.home() / "AppData" / "Roaming"
        return base_dir / "boostgauge" / "config.json"
    return Path.home() / ".boostgauge" / "config.json"


def get_default_config() -> Dict[str, Any]:
    """Return dictionary containing default configuration settings."""
    return copy.deepcopy(DEFAULT_CONFIG)


def load_config_file(path: Path) -> Dict[str, Any]:
    """Load configuration from JSON file; create default file if it does not exist."""
    resolved_path = Path(path).expanduser().resolve()
    if not resolved_path.exists():
        default_cfg = get_default_config()
        save_config_file(default_cfg, resolved_path)
        return default_cfg

    try:
        with open(resolved_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("Configuration file content must be a JSON object")
        return data
    except json.JSONDecodeError as err:
        raise ValueError(f"Invalid JSON in configuration file: {err}") from err


def save_config_file(config: Dict[str, Any], path: Path) -> None:
    """Atomically write configuration dictionary to JSON file."""
    resolved_path = Path(path).expanduser().resolve()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = resolved_path.with_suffix(resolved_path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    os.replace(tmp_path, resolved_path)


def parse_cli_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command-line flags for configuration overrides."""
    parser = argparse.ArgumentParser(description="BoostGauge - System Tachometer Monitor")
    parser.add_argument("--theme", type=str, choices=ALLOWED_THEMES, help="UI visual theme")
    parser.add_argument("--size", type=int, help="Gauge window size in pixels")
    parser.add_argument("--poll", type=float, help="Polling interval in seconds")
    parser.add_argument("--opacity", type=float, help="Window opacity (0.0 to 1.0)")
    parser.add_argument("--no-topmost", action="store_true", help="Disable always-on-top window behavior")
    parser.add_argument("--config", type=str, help="Path to custom JSON configuration file")
    parser.add_argument("--reset-config", action="store_true", help="Reset target config file to default settings")
    return parser.parse_args(args)


def validate_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Validate configuration fields against allowed values, types, and bounds; raise ValueError on invalid data."""
    if not isinstance(config, dict):
        raise ValueError("Configuration must be a dictionary")

    poll = config.get("polling_interval_seconds")
    if not isinstance(poll, (int, float)) or poll <= 0:
        raise ValueError(f"polling_interval_seconds must be a positive number, got {poll}")

    theme = config.get("theme")
    if theme not in ALLOWED_THEMES:
        raise ValueError(f"Invalid theme '{theme}'. Must be one of: {ALLOWED_THEMES}")

    size = config.get("size")
    if not isinstance(size, int) or size < 100 or size > 2000:
        raise ValueError(f"size must be an integer between 100 and 2000, got {size}")

    opacity = config.get("opacity")
    if not isinstance(opacity, (int, float)) or opacity < 0.0 or opacity > 1.0:
        raise ValueError(f"opacity must be between 0.0 and 1.0, got {opacity}")

    always_on_top = config.get("always_on_top")
    if not isinstance(always_on_top, bool):
        raise ValueError(f"always_on_top must be a boolean, got {always_on_top}")

    pos = config.get("position")
    if not isinstance(pos, dict) or "x" not in pos or "y" not in pos or not isinstance(pos["x"], int) or not isinstance(pos["y"], int):
        raise ValueError(f"position must be a dict with integer 'x' and 'y' keys, got {pos}")

    thresholds = config.get("thresholds")
    if not isinstance(thresholds, dict):
        raise ValueError("thresholds must be a dictionary")

    required_metrics = ["conpty", "memory_percent", "process_count", "handle_count"]
    for metric in required_metrics:
        if metric not in thresholds or not isinstance(thresholds[metric], dict):
            raise ValueError(f"thresholds must contain dictionary for metric '{metric}'")
        t_range = thresholds[metric]
        if "yellow" not in t_range or "red" not in t_range:
            raise ValueError(f"thresholds metric '{metric}' must contain 'yellow' and 'red' values")
        y, r = t_range["yellow"], t_range["red"]
        if not isinstance(y, (int, float)) or not isinstance(r, (int, float)):
            raise ValueError(f"threshold values for '{metric}' must be numbers")
        if y < 0 or r < y:
            raise ValueError(f"threshold values for '{metric}' must satisfy 0 <= yellow <= red, got yellow={y}, red={r}")

    telltale = config.get("telltale_windows")
    if not isinstance(telltale, dict):
        raise ValueError("telltale_windows must be a dictionary")
    for key in ["short", "medium", "long"]:
        if key not in telltale or not isinstance(telltale[key], int) or telltale[key] <= 0:
            raise ValueError(f"telltale_windows '{key}' must be a positive integer")

    for key in ["show_driver_label", "show_digital_readout", "show_session_count"]:
        if not isinstance(config.get(key), bool):
            raise ValueError(f"{key} must be a boolean")

    return config


def merge_config(file_config: Dict[str, Any], cli_args: argparse.Namespace) -> Dict[str, Any]:
    """Merge file configuration dictionary with explicit CLI argument overrides."""
    merged = copy.deepcopy(file_config)
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


def load_effective_config(cli_args_list: Optional[List[str]] = None) -> Dict[str, Any]:
    """Orchestrate loading defaults, loading/creating file, applying CLI overrides, and validating final config."""
    cli_args = parse_cli_args(cli_args_list)
    if cli_args.config:
        config_path = Path(cli_args.config).expanduser().resolve()
    else:
        config_path = get_default_config_path()

    if cli_args.reset_config:
        file_config = reset_config_file(config_path)
    else:
        file_config = load_config_file(config_path)

    merged = merge_config(file_config, cli_args)
    return validate_config(merged)


def update_window_geometry(
    path: Path,
    position: Optional[Tuple[int, int]] = None,
    size: Optional[int] = None,
) -> None:
    """Update window position (x, y) and/or size in config file on exit or move."""
    resolved_path = Path(path).expanduser().resolve()
    if resolved_path.exists():
        try:
            config = load_config_file(resolved_path)
        except ValueError:
            config = get_default_config()
    else:
        config = get_default_config()

    if position is not None:
        config["position"] = {"x": position[0], "y": position[1]}
    if size is not None:
        config["size"] = size

    save_config_file(config, resolved_path)


def reset_config_file(path: Path) -> Dict[str, Any]:
    """Reset specified configuration file to default settings."""
    resolved_path = Path(path).expanduser().resolve()
    default_config = get_default_config()
    save_config_file(default_config, resolved_path)
    return default_config


class WindowConfig:
    """Manages reading, writing, and validating window state settings stored on disk."""

    def __init__(self, config_path: Optional[Path] = None) -> None:
        self.config_path = config_path or get_default_config_path()

    def load(self) -> WindowConfigDict:
        try:
            data = load_config_file(self.config_path)
        except ValueError:
            data = get_default_config()
        pos = data.get("position", data.get("window_position", {"x": 100, "y": 100}))
        return {
            "x": int(pos.get("x", 100)),
            "y": int(pos.get("y", 100)),
            "size": int(data.get("size", 256)),
            "topmost": bool(data.get("always_on_top", True)),
            "opacity": float(data.get("opacity", 1.0)),
            "compact_mode": bool(data.get("compact_mode", False)),
        }

    def save(self, config: WindowConfigDict) -> None:
        try:
            data = load_config_file(self.config_path)
        except ValueError:
            data = get_default_config()
        data["position"] = {"x": config["x"], "y": config["y"]}
        data["size"] = config["size"]
        data["always_on_top"] = config["topmost"]
        data["opacity"] = config["opacity"]
        data["compact_mode"] = config["compact_mode"]
        save_config_file(data, self.config_path)

    def validate_bounds(
        self, config: WindowConfigDict, bounds: VirtualScreenBounds
    ) -> WindowConfigDict:
        """Clamp window top-left (x, y) coordinates so the window stays entirely visible within virtual screen rect."""
        validated = dict(config)
        size = validated["size"]
        min_x = bounds["min_x"]
        min_y = bounds["min_y"]
        max_x = bounds["max_x"]
        max_y = bounds["max_y"]

        validated["x"] = max(min_x, min(validated["x"], max_x - size))
        validated["y"] = max(min_y, min(validated["y"], max_y - size))
        return cast(WindowConfigDict, validated)