"""Configuration file management and CLI arguments for BoostGauge.

Issue #7: Feature: Configuration File and CLI Arguments
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
import sys
from typing import Any

VALID_THEMES = ("dark", "light", "neon", "classic")


@dataclass
class ThresholdsConfig:
    conpty: dict[str, float] = field(default_factory=lambda: {"yellow": 30.0, "red": 60.0})
    memory_percent: dict[str, float] = field(default_factory=lambda: {"yellow": 60.0, "red": 80.0})
    process_count: dict[str, float] = field(default_factory=lambda: {"yellow": 300.0, "red": 500.0})
    handle_count: dict[str, float] = field(default_factory=lambda: {"yellow": 30000.0, "red": 50000.0})


@dataclass
class TelltaleWindowsConfig:
    short: int = 60
    medium: int = 600
    long: int = 3600


@dataclass
class PositionConfig:
    x: int = 100
    y: int = 100


@dataclass
class GaugeConfig:
    polling_interval_seconds: float = 2.0
    theme: str = "dark"
    size: int = 300
    opacity: float = 0.9
    always_on_top: bool = True
    position: PositionConfig = field(default_factory=PositionConfig)
    thresholds: ThresholdsConfig = field(default_factory=ThresholdsConfig)
    telltale_windows: TelltaleWindowsConfig = field(default_factory=TelltaleWindowsConfig)
    show_driver_label: bool = True
    show_digital_readout: bool = True
    show_session_count: bool = True


@dataclass
class CLIArgs:
    theme: str | None = None
    size: int | None = None
    poll: float | None = None
    opacity: float | None = None
    no_topmost: bool = False
    config: str | None = None
    reset_config: bool = False


def get_default_config_path() -> Path:
    """Return platform-specific default config path (%APPDATA%/boostgauge/config.json on Windows, ~/.boostgauge/config.json on POSIX)."""
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        base_dir = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
        return base_dir / "boostgauge" / "config.json"
    return Path.home() / ".boostgauge" / "config.json"


def get_default_config() -> GaugeConfig:
    """Return a GaugeConfig instance initialized with default values."""
    return GaugeConfig()


def _dict_to_config(data: dict[str, Any]) -> GaugeConfig:
    config = GaugeConfig()
    if "polling_interval_seconds" in data:
        config.polling_interval_seconds = float(data["polling_interval_seconds"])
    if "theme" in data:
        config.theme = str(data["theme"])
    if "size" in data:
        config.size = int(data["size"])
    if "opacity" in data:
        config.opacity = float(data["opacity"])
    if "always_on_top" in data:
        config.always_on_top = bool(data["always_on_top"])
    if "show_driver_label" in data:
        config.show_driver_label = bool(data["show_driver_label"])
    if "show_digital_readout" in data:
        config.show_digital_readout = bool(data["show_digital_readout"])
    if "show_session_count" in data:
        config.show_session_count = bool(data["show_session_count"])

    if "position" in data and isinstance(data["position"], dict):
        pos_data = data["position"]
        config.position = PositionConfig(
            x=int(pos_data.get("x", 100)),
            y=int(pos_data.get("y", 100)),
        )

    if "thresholds" in data and isinstance(data["thresholds"], dict):
        thresh_data = data["thresholds"]
        config.thresholds = ThresholdsConfig(
            conpty=thresh_data.get("conpty", {"yellow": 30.0, "red": 60.0}),
            memory_percent=thresh_data.get("memory_percent", {"yellow": 60.0, "red": 80.0}),
            process_count=thresh_data.get("process_count", {"yellow": 300.0, "red": 500.0}),
            handle_count=thresh_data.get("handle_count", {"yellow": 30000.0, "red": 50000.0}),
        )

    if "telltale_windows" in data and isinstance(data["telltale_windows"], dict):
        tw_data = data["telltale_windows"]
        config.telltale_windows = TelltaleWindowsConfig(
            short=int(tw_data.get("short", 60)),
            medium=int(tw_data.get("medium", 600)),
            long=int(tw_data.get("long", 3600)),
        )

    return config


def load_config(config_path: Path | None = None) -> GaugeConfig:
    """Load config from JSON file; auto-create with defaults if missing. Raise ValueError on malformed JSON or invalid schema."""
    target_path = config_path if config_path is not None else get_default_config_path()
    if not target_path.exists():
        default_cfg = get_default_config()
        save_config(default_cfg, target_path)
        return default_cfg

    try:
        content = target_path.read_text(encoding="utf-8")
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse configuration JSON at {target_path}: {exc}") from exc
    except Exception as exc:
        raise ValueError(f"Failed to read configuration file at {target_path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Invalid configuration schema at {target_path}: top-level element must be a JSON object")

    try:
        return _dict_to_config(data)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid configuration schema at {target_path}: {exc}") from exc


def save_config(config: GaugeConfig, config_path: Path | None = None) -> None:
    """Serialize and write GaugeConfig instance to JSON file atomically."""
    target_path = config_path if config_path is not None else get_default_config_path()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.with_name(f".{target_path.name}.tmp")
    data = asdict(config)
    temp_path.write_text(json.dumps(data, indent=4), encoding="utf-8")
    temp_path.replace(target_path)


def parse_cli_args(args: list[str] | None = None) -> CLIArgs:
    """Parse command line arguments into CLIArgs object."""
    parser = argparse.ArgumentParser(
        prog="boostgauge",
        description="Lightweight system tachometer with peak-hold needles",
    )
    parser.add_argument("--theme", choices=VALID_THEMES, help="Tachometer visual theme")
    parser.add_argument("--size", type=int, help="Gauge window size in pixels")
    parser.add_argument("--poll", type=float, help="Polling interval in seconds")
    parser.add_argument("--opacity", type=float, help="Window transparency (0.0 to 1.0)")
    parser.add_argument("--no-topmost", action="store_true", help="Disable always-on-top window setting")
    parser.add_argument("--config", type=str, help="Path to custom JSON configuration file")
    parser.add_argument("--reset-config", action="store_true", help="Reset configuration file to defaults")

    parsed = parser.parse_args(args if args is not None else sys.argv[1:])
    return CLIArgs(
        theme=parsed.theme,
        size=parsed.size,
        poll=parsed.poll,
        opacity=parsed.opacity,
        no_topmost=parsed.no_topmost,
        config=parsed.config,
        reset_config=parsed.reset_config,
    )


def merge_config_and_args(config: GaugeConfig, cli_args: CLIArgs) -> GaugeConfig:
    """Apply non-None CLI argument overrides to GaugeConfig instance."""
    if cli_args.theme is not None:
        config.theme = cli_args.theme
    if cli_args.size is not None:
        config.size = cli_args.size
    if cli_args.poll is not None:
        config.polling_interval_seconds = cli_args.poll
    if cli_args.opacity is not None:
        config.opacity = cli_args.opacity
    if cli_args.no_topmost:
        config.always_on_top = False
    return config


def validate_config(config: GaugeConfig) -> list[str]:
    """Validate configuration fields and return list of validation error strings if invalid."""
    errors: list[str] = []
    if not (0.0 <= config.opacity <= 1.0):
        errors.append(f"opacity must be between 0.0 and 1.0, got {config.opacity}")
    if config.polling_interval_seconds <= 0:
        errors.append(f"polling_interval_seconds must be > 0, got {config.polling_interval_seconds}")
    if config.size <= 0:
        errors.append(f"size must be > 0, got {config.size}")
    if config.theme not in VALID_THEMES:
        errors.append(f"theme must be one of {VALID_THEMES}, got '{config.theme}'")

    for metric_name in ("conpty", "memory_percent", "process_count", "handle_count"):
        metric_dict = getattr(config.thresholds, metric_name, None)
        if isinstance(metric_dict, dict):
            yellow = metric_dict.get("yellow", 0.0)
            red = metric_dict.get("red", 0.0)
            if yellow >= red:
                errors.append(f"threshold yellow value ({yellow}) must be less than red value ({red}) for {metric_name}")

    return errors


def reset_config_to_defaults(config_path: Path | None = None) -> GaugeConfig:
    """Overwrite config file at config_path with default configuration and return default GaugeConfig."""
    target_path = config_path if config_path is not None else get_default_config_path()
    default_config = get_default_config()
    save_config(default_config, target_path)
    return default_config


def update_window_geometry(
    config: GaugeConfig,
    position: tuple[int, int],
    size: int,
    config_path: Path | None = None,
) -> GaugeConfig:
    """Update position and size in GaugeConfig and persist to config file on exit."""
    config.position.x = position[0]
    config.position.y = position[1]
    config.size = size
    save_config(config, config_path)
    return config