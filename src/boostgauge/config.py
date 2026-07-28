"""Configuration management system for BoostGauge.

Issue #7: Feature: Configuration File and CLI Arguments
"""

import argparse
from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
import sys
from typing import Any, Callable, Dict, List, Optional


class ConfigError(Exception):
    """Base exception for configuration errors."""
    pass


class ConfigValidationError(ConfigError):
    """Raised when configuration parameters fail validation constraints."""
    pass


@dataclass
class ThresholdRange:
    yellow: float
    red: float


@dataclass
class ThresholdsConfig:
    conpty: ThresholdRange = field(default_factory=lambda: ThresholdRange(30.0, 60.0))
    memory_percent: ThresholdRange = field(default_factory=lambda: ThresholdRange(60.0, 80.0))
    process_count: ThresholdRange = field(default_factory=lambda: ThresholdRange(300.0, 500.0))
    handle_count: ThresholdRange = field(default_factory=lambda: ThresholdRange(30000.0, 50000.0))


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
class BoostGaugeConfig:
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
    theme: Optional[str] = None
    size: Optional[int] = None
    poll: Optional[float] = None
    opacity: Optional[float] = None
    no_topmost: Optional[bool] = None
    config: Optional[Path] = None
    reset_config: bool = False


_CONFIG_LISTENERS: List[Callable[[BoostGaugeConfig], None]] = []


def get_default_config_path() -> Path:
    """Returns OS-specific config path (%APPDATA%/boostgauge/config.json on Windows, ~/.boostgauge/config.json on POSIX)."""
    if sys.platform == "win32":
        app_data = os.environ.get("APPDATA")
        if app_data:
            base_dir = Path(app_data)
        else:
            base_dir = Path.home() / "AppData" / "Roaming"
        return base_dir / "boostgauge" / "config.json"
    else:
        return Path.home() / ".boostgauge" / "config.json"


def parse_cli_args(args: Optional[list] = None) -> CLIArgs:
    """Parses command-line arguments using argparse and returns a CLIArgs object."""
    parser = argparse.ArgumentParser(
        description="BoostGauge system monitor styled like a racing tachometer."
    )
    parser.add_argument("--theme", choices=["dark", "light"], help="Gauge visual theme")
    parser.add_argument("--size", type=int, help="Gauge window diameter in pixels")
    parser.add_argument("--poll", type=float, help="Polling interval in seconds")
    parser.add_argument("--opacity", type=float, help="Window opacity (0.0 to 1.0)")
    parser.add_argument("--no-topmost", action="store_true", default=None, help="Disable always-on-top window placement")
    parser.add_argument("--config", type=Path, help="Path to custom configuration file")
    parser.add_argument("--reset-config", action="store_true", default=False, help="Reset configuration file to factory defaults")

    parsed = parser.parse_args(args)

    return CLIArgs(
        theme=parsed.theme,
        size=parsed.size,
        poll=parsed.poll,
        opacity=parsed.opacity,
        no_topmost=True if parsed.no_topmost else None,
        config=parsed.config,
        reset_config=parsed.reset_config,
    )


def _validate_threshold_range(name: str, tr: ThresholdRange) -> None:
    if tr.yellow < 0.0 or tr.red < 0.0:
        raise ConfigValidationError(f"Thresholds for '{name}' must be non-negative values.")
    if tr.yellow > tr.red:
        raise ConfigValidationError(
            f"Yellow threshold ({tr.yellow}) for '{name}' must be <= red threshold ({tr.red})."
        )


def validate_config_dict(raw: Dict[str, Any]) -> BoostGaugeConfig:
    """Validates raw dictionary inputs against data constraints and returns a structured BoostGaugeConfig."""
    if not isinstance(raw, dict):
        raise ConfigValidationError("Configuration root must be a JSON object/dictionary.")

    defaults = BoostGaugeConfig()

    theme = raw.get("theme", defaults.theme)
    if theme not in ("dark", "light"):
        raise ConfigValidationError(f"Invalid theme '{theme}'. Must be 'dark' or 'light'.")

    size = raw.get("size", defaults.size)
    if not isinstance(size, int) or size < 100 or size > 2000:
        raise ConfigValidationError(f"Invalid size '{size}'. Size must be an integer between 100 and 2000 pixels.")

    opacity = raw.get("opacity", defaults.opacity)
    if not isinstance(opacity, (int, float)) or opacity < 0.0 or opacity > 1.0:
        raise ConfigValidationError(f"Invalid opacity '{opacity}'. Opacity must be a float between 0.0 and 1.0.")

    polling_interval_seconds = raw.get("polling_interval_seconds", defaults.polling_interval_seconds)
    if not isinstance(polling_interval_seconds, (int, float)) or polling_interval_seconds <= 0.0:
        raise ConfigValidationError(f"Invalid polling_interval_seconds '{polling_interval_seconds}'. Must be > 0.0.")

    always_on_top = raw.get("always_on_top", defaults.always_on_top)
    if not isinstance(always_on_top, bool):
        raise ConfigValidationError("Field 'always_on_top' must be a boolean.")

    pos_raw = raw.get("position", {})
    if not isinstance(pos_raw, dict):
        raise ConfigValidationError("Field 'position' must be a dictionary.")
    x = pos_raw.get("x", defaults.position.x)
    y = pos_raw.get("y", defaults.position.y)
    if not isinstance(x, int) or not isinstance(y, int):
        raise ConfigValidationError("Position 'x' and 'y' must be integers.")
    position = PositionConfig(x=x, y=y)

    t_raw = raw.get("thresholds", {})
    if not isinstance(t_raw, dict):
        raise ConfigValidationError("Field 'thresholds' must be a dictionary.")

    def parse_tr(key: str, default_tr: ThresholdRange) -> ThresholdRange:
        sub = t_raw.get(key, {})
        if not isinstance(sub, dict):
            raise ConfigValidationError(f"Threshold group '{key}' must be a dictionary.")
        y_val = sub.get("yellow", default_tr.yellow)
        r_val = sub.get("red", default_tr.red)
        if not isinstance(y_val, (int, float)) or not isinstance(r_val, (int, float)):
            raise ConfigValidationError(f"Threshold values for '{key}' must be numeric.")
        tr = ThresholdRange(yellow=float(y_val), red=float(r_val))
        _validate_threshold_range(key, tr)
        return tr

    thresholds = ThresholdsConfig(
        conpty=parse_tr("conpty", defaults.thresholds.conpty),
        memory_percent=parse_tr("memory_percent", defaults.thresholds.memory_percent),
        process_count=parse_tr("process_count", defaults.thresholds.process_count),
        handle_count=parse_tr("handle_count", defaults.thresholds.handle_count),
    )

    tw_raw = raw.get("telltale_windows", {})
    if not isinstance(tw_raw, dict):
        raise ConfigValidationError("Field 'telltale_windows' must be a dictionary.")
    s_win = tw_raw.get("short", defaults.telltale_windows.short)
    m_win = tw_raw.get("medium", defaults.telltale_windows.medium)
    l_win = tw_raw.get("long", defaults.telltale_windows.long)
    if not all(isinstance(v, int) and v > 0 for v in (s_win, m_win, l_win)):
        raise ConfigValidationError("Telltale window durations must be positive integers.")
    telltale_windows = TelltaleWindowsConfig(short=s_win, medium=m_win, long=l_win)

    show_driver_label = raw.get("show_driver_label", defaults.show_driver_label)
    show_digital_readout = raw.get("show_digital_readout", defaults.show_digital_readout)
    show_session_count = raw.get("show_session_count", defaults.show_session_count)

    return BoostGaugeConfig(
        polling_interval_seconds=float(polling_interval_seconds),
        theme=str(theme),
        size=int(size),
        opacity=float(opacity),
        always_on_top=bool(always_on_top),
        position=position,
        thresholds=thresholds,
        telltale_windows=telltale_windows,
        show_driver_label=bool(show_driver_label),
        show_digital_readout=bool(show_digital_readout),
        show_session_count=bool(show_session_count),
    )


def save_config(config: BoostGaugeConfig, config_path: Optional[Path] = None) -> None:
    """Serializes and writes BoostGaugeConfig instance to JSON file atomically."""
    target_path = config_path if config_path is not None else get_default_config_path()
    target_path = target_path.resolve()

    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = target_path.with_suffix(".tmp")
        data = asdict(config)
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        tmp_path.replace(target_path)
    except OSError as e:
        raise ConfigError(f"Failed to save configuration to '{target_path}': {e}") from e


def load_config(config_path: Optional[Path] = None) -> BoostGaugeConfig:
    """Loads configuration from file. If file does not exist, creates it with defaults."""
    target_path = config_path if config_path is not None else get_default_config_path()
    target_path = target_path.resolve()

    if not target_path.exists():
        default_cfg = BoostGaugeConfig()
        save_config(default_cfg, target_path)
        return default_cfg

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigValidationError(f"Failed to parse JSON configuration file at '{target_path}': {e}") from e
    except OSError as e:
        raise ConfigError(f"Failed to read configuration file at '{target_path}': {e}") from e

    return validate_config_dict(raw_data)


def merge_config_and_cli(config: BoostGaugeConfig, cli_args: CLIArgs) -> BoostGaugeConfig:
    """Merges loaded configuration with explicit CLI argument overrides."""
    merged_data = asdict(config)

    if cli_args.theme is not None:
        merged_data["theme"] = cli_args.theme
    if cli_args.size is not None:
        merged_data["size"] = cli_args.size
    if cli_args.poll is not None:
        merged_data["polling_interval_seconds"] = cli_args.poll
    if cli_args.opacity is not None:
        merged_data["opacity"] = cli_args.opacity
    if cli_args.no_topmost is not None:
        merged_data["always_on_top"] = False

    return validate_config_dict(merged_data)


def update_window_state(config: BoostGaugeConfig, x: int, y: int, size: int, config_path: Optional[Path] = None) -> BoostGaugeConfig:
    """Updates position (x, y) and size in config and saves updated state to disk."""
    config.position.x = x
    config.position.y = y
    config.size = size
    save_config(config, config_path)
    return config


def register_config_listener(callback: Callable[[BoostGaugeConfig], None]) -> None:
    """Registers a listener callback for dynamic configuration changes."""
    if callback not in _CONFIG_LISTENERS:
        _CONFIG_LISTENERS.append(callback)


def notify_config_listeners(config: BoostGaugeConfig) -> None:
    """Invokes all registered callbacks with updated configuration."""
    for listener in list(_CONFIG_LISTENERS):
        listener(config)


def reset_config_to_defaults(config_path: Optional[Path] = None) -> BoostGaugeConfig:
    """Overwrites target config file with default settings and returns standard defaults."""
    target_path = config_path if config_path is not None else get_default_config_path()
    default_cfg = BoostGaugeConfig()
    save_config(default_cfg, target_path)
    return default_cfg