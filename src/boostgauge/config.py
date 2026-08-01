"""Configuration management module for BoostGauge.

Issue #7: Configuration File and CLI Arguments
"""

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


@dataclass
class WindowPosition:
    x: int = 100
    y: int = 100


@dataclass
class ThresholdPair:
    yellow: float
    red: float


@dataclass
class ThresholdsConfig:
    conpty: ThresholdPair = field(default_factory=lambda: ThresholdPair(30.0, 60.0))
    memory_percent: ThresholdPair = field(default_factory=lambda: ThresholdPair(60.0, 80.0))
    process_count: ThresholdPair = field(default_factory=lambda: ThresholdPair(300.0, 500.0))
    handle_count: ThresholdPair = field(default_factory=lambda: ThresholdPair(30000.0, 50000.0))


@dataclass
class TelltaleWindowsConfig:
    short: int = 60
    medium: int = 600
    long: int = 3600


@dataclass
class AppConfig:
    polling_interval_seconds: float = 2.0
    theme: str = "dark"
    size: int = 300
    opacity: float = 0.9
    always_on_top: bool = True
    position: WindowPosition = field(default_factory=WindowPosition)
    thresholds: ThresholdsConfig = field(default_factory=ThresholdsConfig)
    telltale_windows: TelltaleWindowsConfig = field(default_factory=TelltaleWindowsConfig)
    show_driver_label: bool = True
    show_digital_readout: bool = True
    show_session_count: bool = True


def get_default_config_path() -> Path:
    """Return platform-specific default configuration path (%APPDATA%/boostgauge/config.json or ~/.boostgauge/config.json)."""
    if sys.platform == "win32":
        app_data = os.environ.get("APPDATA")
        if app_data:
            base_dir = Path(app_data)
        else:
            base_dir = Path.home() / "AppData" / "Roaming"
        return base_dir / "boostgauge" / "config.json"
    else:
        return Path.home() / ".boostgauge" / "config.json"


def load_config_file(config_path: Path) -> Dict[str, Any]:
    """Load JSON config dictionary from disk; auto-creates directory and default file if missing."""
    if not config_path.exists():
        default_config = AppConfig()
        save_config_file(default_config, config_path)
        return asdict(default_config)

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError(f"Configuration file root must be a JSON object, got {type(data).__name__}")
        return data
    except json.JSONDecodeError as err:
        raise ValueError(f"Invalid JSON in configuration file: {err}") from err


def save_config_file(config: AppConfig, config_path: Path) -> None:
    """Atomically save AppConfig instance as formatted JSON to disk using a temporary file."""
    config_path = Path(config_path).resolve()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = config_path.with_suffix(".tmp")

    data = asdict(config)
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    os.replace(temp_path, config_path)


def _validate_threshold_pair(pair_dict: Dict[str, Any], metric_name: str) -> ThresholdPair:
    if "yellow" not in pair_dict or "red" not in pair_dict:
        raise ValueError(f"Threshold for '{metric_name}' must contain 'yellow' and 'red' values")

    yellow = float(pair_dict["yellow"])
    red = float(pair_dict["red"])

    if yellow < 0 or red < 0:
        raise ValueError(f"Thresholds for '{metric_name}' must be non-negative")
    if yellow >= red:
        raise ValueError(f"Metric '{metric_name}' yellow threshold ({yellow}) must be less than red threshold ({red})")

    return ThresholdPair(yellow=yellow, red=red)


def validate_config_dict(raw_config: Dict[str, Any]) -> AppConfig:
    """Validate types and numerical bounds of raw configuration dict; return typed AppConfig or raise ValueError."""
    polling_interval = float(raw_config.get("polling_interval_seconds", 2.0))
    if polling_interval <= 0:
        raise ValueError(f"polling_interval_seconds must be positive, got {polling_interval}")

    theme = str(raw_config.get("theme", "dark"))
    if theme not in ("dark", "light"):
        raise ValueError(f"Invalid theme '{theme}', expected 'dark' or 'light'")

    size = int(raw_config.get("size", 300))
    if size <= 0:
        raise ValueError(f"size must be positive integer, got {size}")

    opacity = float(raw_config.get("opacity", 0.9))
    if not (0.0 <= opacity <= 1.0):
        raise ValueError(f"opacity must be between 0.0 and 1.0, got {opacity}")

    always_on_top = bool(raw_config.get("always_on_top", True))
    show_driver_label = bool(raw_config.get("show_driver_label", True))
    show_digital_readout = bool(raw_config.get("show_digital_readout", True))
    show_session_count = bool(raw_config.get("show_session_count", True))

    pos_raw = raw_config.get("position", {})
    position = WindowPosition(
        x=int(pos_raw.get("x", 100)),
        y=int(pos_raw.get("y", 100))
    )

    telltale_raw = raw_config.get("telltale_windows", {})
    telltale_windows = TelltaleWindowsConfig(
        short=int(telltale_raw.get("short", 60)),
        medium=int(telltale_raw.get("medium", 600)),
        long=int(telltale_raw.get("long", 3600))
    )

    thresh_raw = raw_config.get("thresholds", {})
    default_thresh = ThresholdsConfig()

    conpty = _validate_threshold_pair(thresh_raw.get("conpty", asdict(default_thresh.conpty)), "conpty")
    memory_percent = _validate_threshold_pair(thresh_raw.get("memory_percent", asdict(default_thresh.memory_percent)), "memory_percent")
    process_count = _validate_threshold_pair(thresh_raw.get("process_count", asdict(default_thresh.process_count)), "process_count")
    handle_count = _validate_threshold_pair(thresh_raw.get("handle_count", asdict(default_thresh.handle_count)), "handle_count")

    thresholds = ThresholdsConfig(
        conpty=conpty,
        memory_percent=memory_percent,
        process_count=process_count,
        handle_count=handle_count
    )

    return AppConfig(
        polling_interval_seconds=polling_interval,
        theme=theme,
        size=size,
        opacity=opacity,
        always_on_top=always_on_top,
        position=position,
        thresholds=thresholds,
        telltale_windows=telltale_windows,
        show_driver_label=show_driver_label,
        show_digital_readout=show_digital_readout,
        show_session_count=show_session_count
    )


def parse_cli_args(args_list: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse CLI command-line flags for boostgauge."""
    parser = argparse.ArgumentParser(description="BoostGauge System Tachometer")
    parser.add_argument("--config", type=str, default=None, help="Custom path to config.json")
    parser.add_argument("--theme", type=str, choices=["dark", "light"], default=None, help="UI color theme")
    parser.add_argument("--size", type=int, default=None, help="Gauge window size in pixels")
    parser.add_argument("--opacity", type=float, default=None, help="Window opacity (0.0 to 1.0)")
    parser.add_argument("--polling-interval", type=float, default=None, help="Metric collection interval in seconds")
    parser.add_argument("--reset-config", action="store_true", help="Reset config file to defaults")
    return parser.parse_args(args_list if args_list is not None else sys.argv[1:])


def merge_config(file_config: AppConfig, cli_args: argparse.Namespace) -> AppConfig:
    """Merge command-line argument overrides into configuration loaded from disk."""
    config_dict = asdict(file_config)

    if cli_args.theme is not None:
        config_dict["theme"] = cli_args.theme
    if cli_args.size is not None:
        config_dict["size"] = cli_args.size
    if cli_args.opacity is not None:
        config_dict["opacity"] = cli_args.opacity
    if cli_args.polling_interval is not None:
        config_dict["polling_interval_seconds"] = cli_args.polling_interval

    return validate_config_dict(config_dict)


class ConfigManager:
    """Manages active configuration state, threshold observers, and atomic disk persistence."""

    def __init__(
        self,
        config_path: Optional[Path] = None,
        cli_args: Optional[List[str]] = None
    ) -> None:
        parsed_cli = parse_cli_args(cli_args)
        if parsed_cli.config is not None:
            self.config_path = Path(parsed_cli.config)
        elif config_path is not None:
            self.config_path = Path(config_path)
        else:
            self.config_path = get_default_config_path()

        if parsed_cli.reset_config:
            default_config = AppConfig()
            save_config_file(default_config, self.config_path)
            raw_dict = asdict(default_config)
        else:
            raw_dict = load_config_file(self.config_path)

        base_config = validate_config_dict(raw_dict)
        self.config = merge_config(base_config, parsed_cli)
        self._threshold_observers: List[Callable[[ThresholdsConfig], None]] = []

    def register_threshold_observer(self, callback: Callable[[ThresholdsConfig], None]) -> None:
        """Register a callback observer triggered whenever threshold settings update dynamically."""
        self._threshold_observers.append(callback)

    def update_thresholds(self, new_thresholds: Dict[str, Dict[str, float]]) -> None:
        """Dynamically update threshold settings without restart and notify observers."""
        current_thresh = asdict(self.config.thresholds)
        for metric, values in new_thresholds.items():
            if metric in current_thresh:
                current_thresh[metric].update(values)

        raw_config = asdict(self.config)
        raw_config["thresholds"] = current_thresh

        updated_config = validate_config_dict(raw_config)
        self.config = updated_config
        save_config_file(self.config, self.config_path)

        for observer in self._threshold_observers:
            observer(self.config.thresholds)

    def save_geometry(self, position: WindowPosition, size: int) -> None:
        """Update window position and size geometry and atomically flush to disk."""
        if size <= 0:
            raise ValueError(f"size must be positive integer, got {size}")
        self.config.position = position
        self.config.size = size
        save_config_file(self.config, self.config_path)