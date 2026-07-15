"""Configuration management module.

Issue #7: Feature: configuration file and CLI arguments
"""

import argparse
import json
import logging
import os
from pathlib import Path
import shutil
import sys
from typing import Any, Dict, List, Optional

logger = logging.getLogger("boostgauge.config")


def get_default_config_path() -> Path:
    """Returns the default platform-specific path (~/.boostgauge/config.json or %APPDATA%/boostgauge/config.json)."""
    if os.name == "nt":
        app_data = os.environ.get("APPDATA")
        if app_data:
            return Path(app_data).resolve() / "boostgauge" / "config.json"
    return Path("~/.boostgauge/config.json").expanduser().resolve()


def get_default_config() -> Dict[str, Any]:
    """Returns a dict containing standard configuration default values."""
    return {
        "polling_interval_seconds": 2.0,
        "theme": "dark",
        "size": 256,
        "opacity": 0.85,
        "always_on_top": True,
        "position": {"x": 100, "y": 100},
        "thresholds": {
            "conpty": {"yellow": 4.0, "red": 8.0},
            "memory_percent": {"yellow": 80.0, "red": 90.0},
            "process_count": {"yellow": 10.0, "red": 20.0},
            "handle_count": {"yellow": 500.0, "red": 1000.0},
        },
        "telltale_windows": {"short": 60, "medium": 600, "long": 3600},
        "show_driver_label": True,
        "show_digital_readout": True,
        "show_session_count": True,
    }


def validate_config(config_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Validates types and value bounds of configuration fields. Raises ValueError or TypeError."""
    if not isinstance(config_dict, dict):
        raise TypeError("Configuration must be a dictionary")

    poll = config_dict.get("polling_interval_seconds")
    if not isinstance(poll, (int, float)) or isinstance(poll, bool):
        raise TypeError("polling_interval_seconds must be a float or integer")
    if poll <= 0:
        raise ValueError("polling_interval_seconds must be greater than zero")

    theme = config_dict.get("theme")
    if not isinstance(theme, str):
        raise TypeError("theme must be a string")
    if not theme.strip():
        raise ValueError("theme cannot be empty")

    size = config_dict.get("size")
    if not isinstance(size, int) or isinstance(size, bool):
        raise TypeError("size must be an integer")
    if not (128 <= size <= 1024):
        raise ValueError("size must be between 128 and 1024")

    opacity = config_dict.get("opacity")
    if not isinstance(opacity, (int, float)) or isinstance(opacity, bool):
        raise TypeError("opacity must be a float or integer")
    if not (0.1 <= opacity <= 1.0):
        raise ValueError("opacity must be between 0.1 and 1.0")

    always_on_top = config_dict.get("always_on_top")
    if not isinstance(always_on_top, bool):
        raise TypeError("always_on_top must be a boolean")

    position = config_dict.get("position")
    if not isinstance(position, dict):
        raise TypeError("position must be a dictionary")
    for key in ("x", "y"):
        val = position.get(key)
        if not isinstance(val, int) or isinstance(val, bool):
            raise TypeError(f"position.{key} must be an integer")

    thresholds = config_dict.get("thresholds")
    if not isinstance(thresholds, dict):
        raise TypeError("thresholds must be a dictionary")
    for key in ("conpty", "memory_percent", "process_count", "handle_count"):
        t_val = thresholds.get(key)
        if not isinstance(t_val, dict):
            raise TypeError(f"thresholds.{key} must be a dictionary")
        for subkey in ("yellow", "red"):
            val = t_val.get(subkey)
            if not isinstance(val, (int, float)) or isinstance(val, bool):
                raise TypeError(f"thresholds.{key}.{subkey} must be a float or integer")
            if val < 0:
                raise ValueError(f"thresholds.{key}.{subkey} cannot be negative")
        if t_val["yellow"] >= t_val["red"]:
            raise ValueError(
                f"thresholds.{key}.yellow must be less than thresholds.{key}.red"
            )

    telltale = config_dict.get("telltale_windows")
    if not isinstance(telltale, dict):
        raise TypeError("telltale_windows must be a dictionary")
    for key in ("short", "medium", "long"):
        val = telltale.get(key)
        if not isinstance(val, int) or isinstance(val, bool):
            raise TypeError(f"telltale_windows.{key} must be an integer")
        if val <= 0:
            raise ValueError(f"telltale_windows.{key} must be greater than zero")
    if not (telltale["short"] < telltale["medium"] < telltale["long"]):
        raise ValueError("telltale_windows intervals must satisfy short < medium < long")

    for key in ("show_driver_label", "show_digital_readout", "show_session_count"):
        val = config_dict.get(key)
        if not isinstance(val, bool):
            raise TypeError(f"{key} must be a boolean")

    return config_dict


def load_config(path: Path) -> Dict[str, Any]:
    """Reads configuration file. Creates file with defaults if not exists."""
    resolved_path = path.resolve()
    if not resolved_path.exists():
        default_config = get_default_config()
        save_config(default_config, resolved_path)
        return default_config

    try:
        with open(resolved_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format in config file: {e}")


def save_config(config: Dict[str, Any], path: Path) -> None:
    """Saves the config state atomically using a temporary file and atomic replace."""
    resolved_path = path.resolve()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = resolved_path.with_suffix(".tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        os.replace(tmp_path, resolved_path)
    except Exception as e:
        if tmp_path.exists():
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        raise e


def parse_cli_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parses command-line arguments using argparse."""
    parser = argparse.ArgumentParser(
        description="BoostGauge - racing tachometer system resource monitor"
    )
    parser.add_argument(
        "--theme",
        type=str,
        help="UI color theme (e.g. dark, light)",
    )
    parser.add_argument(
        "--size",
        type=int,
        help="Square gauge visual size in pixels [128-1024]",
    )
    parser.add_argument(
        "--poll",
        type=float,
        help="System resource polling interval in seconds",
    )
    parser.add_argument(
        "--opacity",
        type=float,
        help="Window transparent opacity [0.1-1.0]",
    )
    parser.add_argument(
        "--no-topmost",
        action="store_true",
        help="Disable always-on-top window behavior",
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to custom config.json file",
    )
    parser.add_argument(
        "--reset-config",
        action="store_true",
        help="Reset configuration file to default values",
    )
    return parser.parse_args(args)


def override_config_with_cli(
    config: Dict[str, Any], cli_args: argparse.Namespace
) -> Dict[str, Any]:
    """Merges loaded configuration dictionary with non-None CLI argument overrides."""
    overridden = json.loads(json.dumps(config))  # deep copy
    if cli_args.theme is not None:
        overridden["theme"] = cli_args.theme
    if cli_args.size is not None:
        overridden["size"] = cli_args.size
    if cli_args.poll is not None:
        overridden["polling_interval_seconds"] = cli_args.poll
    if cli_args.opacity is not None:
        overridden["opacity"] = cli_args.opacity
    if cli_args.no_topmost:
        overridden["always_on_top"] = False
    return overridden


class ConfigManager:
    """Encapsulates config loading, dynamic reloading, value retrieval, and exit saving."""

    def __init__(
        self,
        config_path: Optional[Path] = None,
        cli_args: Optional[argparse.Namespace] = None,
    ) -> None:
        """Initializes configuration settings and tracks file modification times."""
        if config_path is not None:
            self.config_path = config_path
        elif cli_args and cli_args.config:
            self.config_path = Path(cli_args.config)
        else:
            self.config_path = get_default_config_path()

        self.config_path = self.config_path.resolve()
        self.cli_args = cli_args
        self._config: Dict[str, Any] = {}
        self._last_mtime: float = 0.0

    def load(self) -> Dict[str, Any]:
        """Loads file configuration, merges CLI arguments, validates the result, and stores state."""
        raw_config = load_config(self.config_path)
        if self.cli_args:
            raw_config = override_config_with_cli(raw_config, self.cli_args)
        validate_config(raw_config)
        self._config = raw_config
        self._last_mtime = self.config_path.stat().st_mtime
        return self._config

    def save(self) -> None:
        """Saves current state to the configured configuration file."""
        save_config(self._config, self.config_path)
        self._last_mtime = self.config_path.stat().st_mtime

    def check_and_reload(self) -> bool:
        """Checks configuration file modification time. Reloads if changed. Returns True if reloaded."""
        try:
            if not self.config_path.exists():
                return False
            current_mtime = self.config_path.stat().st_mtime
            if current_mtime <= self._last_mtime:
                return False

            self._last_mtime = current_mtime
            with open(self.config_path, "r", encoding="utf-8") as f:
                new_raw = json.load(f)

            if self.cli_args:
                new_raw = override_config_with_cli(new_raw, self.cli_args)

            validate_config(new_raw)
            self._config = new_raw
            return True
        except Exception as e:
            print(
                f"Warning: Configuration reload failed, retaining previous configuration. Error: {e}",
                file=sys.stderr,
            )
            return False

    def get(self, key: str) -> Any:
        """Retrieves a configuration value by key."""
        return self._config[key]

    def update_position_and_size(self, x: int, y: int, size: int) -> None:
        """Updates window coordinates and size in memory."""
        self._config["position"]["x"] = x
        self._config["position"]["y"] = y
        self._config["size"] = size