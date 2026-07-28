"""Configuration data models, default generation, JSON persistence, validation, and dynamic updates.

Issue #7: Configuration File and CLI Arguments
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Tuple, Optional
from pathlib import Path
import json
import os
import sys

__all__ = [
    "GaugeConfig",
    "PositionConfig",
    "ThresholdConfig",
    "ThresholdLevel",
    "TelltaleWindows",
    "get_default_config_path",
    "get_default_config",
    "validate_config",
    "dict_to_gauge_config",
    "load_config",
    "save_config",
    "save_window_state",
    "update_thresholds",
]

ALLOWED_THEMES = {"dark", "light"}
MIN_POLLING_INTERVAL = 1
MIN_GAUGE_SIZE = 100
MAX_GAUGE_SIZE = 2000
MIN_OPACITY = 0.1
MAX_OPACITY = 1.0


@dataclass
class ThresholdLevel:
    yellow: float
    red: float


@dataclass
class ThresholdConfig:
    conpty: ThresholdLevel = field(default_factory=lambda: ThresholdLevel(yellow=30.0, red=60.0))
    memory_percent: ThresholdLevel = field(default_factory=lambda: ThresholdLevel(yellow=60.0, red=80.0))
    process_count: ThresholdLevel = field(default_factory=lambda: ThresholdLevel(yellow=300.0, red=500.0))
    handle_count: ThresholdLevel = field(default_factory=lambda: ThresholdLevel(yellow=30000.0, red=50000.0))


@dataclass
class TelltaleWindows:
    short: int = 60
    medium: int = 600
    long: int = 3600


@dataclass
class PositionConfig:
    x: int = 100
    y: int = 100


@dataclass
class GaugeConfig:
    polling_interval_seconds: int = 2
    theme: str = "dark"
    size: int = 300
    opacity: float = 0.9
    always_on_top: bool = True
    position: PositionConfig = field(default_factory=PositionConfig)
    thresholds: ThresholdConfig = field(default_factory=ThresholdConfig)
    telltale_windows: TelltaleWindows = field(default_factory=TelltaleWindows)
    show_driver_label: bool = True
    show_digital_readout: bool = True
    show_session_count: bool = True


def get_default_config_path() -> Path:
    """Return platform-specific default configuration file path."""
    if sys.platform == "win32" or os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "boostgauge" / "config.json"
    return Path.home() / ".boostgauge" / "config.json"


def get_default_config() -> GaugeConfig:
    """Instantiate and return a GaugeConfig object populated with default parameters."""
    return GaugeConfig()


def validate_config(raw_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Validate raw configuration dictionary against schema constraints."""
    if not isinstance(raw_dict, dict):
        raise ValueError(f"Configuration root must be a dictionary, got {type(raw_dict).__name__}")

    poll = raw_dict.get("polling_interval_seconds", 2)
    if not isinstance(poll, int) or poll < MIN_POLLING_INTERVAL:
        raise ValueError(f"polling_interval_seconds must be an integer >= {MIN_POLLING_INTERVAL}, got {poll}")

    theme = raw_dict.get("theme", "dark")
    if theme not in ALLOWED_THEMES:
        raise ValueError(f"theme must be one of {sorted(list(ALLOWED_THEMES))}, got '{theme}'")

    size = raw_dict.get("size", 300)
    if not isinstance(size, int) or size < MIN_GAUGE_SIZE or size > MAX_GAUGE_SIZE:
        raise ValueError(f"size must be an integer between {MIN_GAUGE_SIZE} and {MAX_GAUGE_SIZE}, got {size}")

    opacity = raw_dict.get("opacity", 0.9)
    if not isinstance(opacity, (int, float)) or opacity < MIN_OPACITY or opacity > MAX_OPACITY:
        raise ValueError(f"opacity must be between {MIN_OPACITY} and {MAX_OPACITY}, got {opacity}")

    always_on_top = raw_dict.get("always_on_top", True)
    if not isinstance(always_on_top, bool):
        raise ValueError(f"always_on_top must be a boolean, got {type(always_on_top).__name__}")

    pos = raw_dict.get("position")
    if pos is not None and not isinstance(pos, dict):
        raise ValueError(f"position must be a dictionary or omitted, got {type(pos).__name__}")
    if isinstance(pos, dict):
        if "x" in pos and not isinstance(pos["x"], int):
            raise ValueError(f"position.x must be an integer, got {pos['x']}")
        if "y" in pos and not isinstance(pos["y"], int):
            raise ValueError(f"position.y must be an integer, got {pos['y']}")

    thresholds = raw_dict.get("thresholds")
    if thresholds is not None and not isinstance(thresholds, dict):
        raise ValueError(f"thresholds must be a dictionary or omitted, got {type(thresholds).__name__}")

    telltale_windows = raw_dict.get("telltale_windows")
    if telltale_windows is not None and not isinstance(telltale_windows, dict):
        raise ValueError(f"telltale_windows must be a dictionary or omitted, got {type(telltale_windows).__name__}")

    default_threshold_defaults = {
        "conpty": (30.0, 60.0),
        "memory_percent": (60.0, 80.0),
        "process_count": (300.0, 500.0),
        "handle_count": (30000.0, 50000.0),
    }

    if isinstance(thresholds, dict):
        for metric, (def_y, def_r) in default_threshold_defaults.items():
            if metric in thresholds:
                t_val = thresholds[metric]
                if t_val is not None and not isinstance(t_val, dict):
                    raise ValueError(f"thresholds.{metric} must be a dictionary or omitted, got {type(t_val).__name__}")
                if isinstance(t_val, dict):
                    yellow = t_val.get("yellow", def_y)
                    red = t_val.get("red", def_r)
                    if yellow >= red:
                        raise ValueError(f"{metric} yellow threshold ({yellow}) must be less than red threshold ({red})")

    return raw_dict


def dict_to_gauge_config(d: Dict[str, Any]) -> GaugeConfig:
    """Convert validated configuration dictionary into a GaugeConfig dataclass."""
    pos_data = d.get("position") or {}
    position = PositionConfig(
        x=pos_data.get("x", 100),
        y=pos_data.get("y", 100),
    )

    t_data = d.get("thresholds") or {}

    def parse_level(key: str, default_y: float, default_r: float) -> ThresholdLevel:
        sub = t_data.get(key) or {}
        return ThresholdLevel(
            yellow=float(sub.get("yellow", default_y)),
            red=float(sub.get("red", default_r)),
        )

    thresholds = ThresholdConfig(
        conpty=parse_level("conpty", 30.0, 60.0),
        memory_percent=parse_level("memory_percent", 60.0, 80.0),
        process_count=parse_level("process_count", 300.0, 500.0),
        handle_count=parse_level("handle_count", 30000.0, 50000.0),
    )

    tw_data = d.get("telltale_windows") or {}
    telltale = TelltaleWindows(
        short=tw_data.get("short", 60),
        medium=tw_data.get("medium", 600),
        long=tw_data.get("long", 3600),
    )

    config = GaugeConfig(
        polling_interval_seconds=d.get("polling_interval_seconds", 2),
        theme=d.get("theme", "dark"),
        size=d.get("size", 300),
        opacity=float(d.get("opacity", 0.9)),
        always_on_top=d.get("always_on_top", True),
        position=position,
        thresholds=thresholds,
        telltale_windows=telltale,
        show_driver_label=d.get("show_driver_label", True),
        show_digital_readout=d.get("show_digital_readout", True),
        show_session_count=d.get("show_session_count", True),
    )
    validate_config(asdict(config))
    return config


def load_config(config_path: Optional[Path] = None) -> GaugeConfig:
    """Load configuration from specified path or default location, auto-creating default file if absent."""
    path = config_path if config_path is not None else get_default_config_path()
    if not path.exists():
        config = get_default_config()
        save_config(config, path)
        return config

    try:
        with open(path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
    except Exception as e:
        raise ValueError(f"Failed to decode JSON config at {path}: {e}") from e

    validated = validate_config(raw_data)
    return dict_to_gauge_config(validated)


def save_config(config: GaugeConfig, config_path: Optional[Path] = None) -> None:
    """Atomically serialize GaugeConfig dataclass instance to JSON file on disk."""
    path = config_path if config_path is not None else get_default_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")

    data = asdict(config)
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    tmp_path.replace(path)


def save_window_state(config: GaugeConfig, position: Tuple[int, int], size: int, config_path: Optional[Path] = None) -> None:
    """Update window position and size attributes in GaugeConfig and persist updated state to disk."""
    config.position.x = position[0]
    config.position.y = position[1]
    config.size = size
    save_config(config, config_path)


def update_thresholds(config: GaugeConfig, new_thresholds: Dict[str, Dict[str, float]], config_path: Optional[Path] = None) -> GaugeConfig:
    """Update active resource metric thresholds dynamically at runtime and optionally persist changes."""
    for metric, levels in new_thresholds.items():
        if hasattr(config.thresholds, metric):
            current = getattr(config.thresholds, metric)
            new_yellow = levels.get("yellow", current.yellow)
            new_red = levels.get("red", current.red)
            if new_yellow >= new_red:
                raise ValueError(f"{metric} yellow threshold ({new_yellow}) must be less than red threshold ({new_red})")
            setattr(config.thresholds, metric, ThresholdLevel(yellow=float(new_yellow), red=float(new_red)))

    validate_config(asdict(config))
    if config_path is not None:
        save_config(config, config_path)
    return config