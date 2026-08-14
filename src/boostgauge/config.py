import json
import logging
import os
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional, TypedDict

logger = logging.getLogger(__name__)


class PositionConfig(TypedDict):
    x: int
    y: int


class ThresholdConfig(TypedDict):
    yellow: int
    red: int


class Thresholds(TypedDict):
    conpty: ThresholdConfig
    memory_percent: ThresholdConfig
    process_count: ThresholdConfig
    handle_count: ThresholdConfig


class TelltaleWindows(TypedDict):
    short: int
    medium: int
    long: int


class AppConfig(TypedDict):
    polling_interval_seconds: int
    theme: str
    size: int
    opacity: float
    always_on_top: bool
    position: PositionConfig
    thresholds: Thresholds
    telltale_windows: TelltaleWindows
    show_driver_label: bool
    show_digital_readout: bool
    show_session_count: bool


class SessionState(TypedDict):
    config_file_path: str
    active_config: AppConfig
    hand_changed_position: Optional[PositionConfig]
    hand_changed_size: Optional[int]
    reset_config_flag: bool


DEFAULT_CONFIG: AppConfig = {
    "polling_interval_seconds": 2,
    "theme": "dark",
    "size": 300,
    "opacity": 0.9,
    "always_on_top": True,
    "position": {"x": 100, "y": 100},
    "thresholds": {
        "conpty": {"yellow": 50, "red": 80},
        "memory_percent": {"yellow": 70, "red": 90},
        "process_count": {"yellow": 200, "red": 300},
        "handle_count": {"yellow": 5000, "red": 10000},
    },
    "telltale_windows": {"short": 60, "medium": 600, "long": 3600},
    "show_driver_label": True,
    "show_digital_readout": True,
    "show_session_count": True,
}


def _atomic_write(path: str, data: dict) -> None:
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=str(dest.parent))
    try:
        with os.fdopen(tmp_fd, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def mitigate_invalid_config(path: str, raw_data: str = "") -> None:
    """Handles and isolates config load failures safely, ensuring fallback to defaults without data loss. Logs ERROR on invalid config."""
    corrupt_path = path + ".corrupt"
    if os.path.exists(corrupt_path):
        try:
            os.remove(corrupt_path)
        except OSError as e:
            logger.error("Failed to remove old corrupt backup %s: %s", corrupt_path, e)
    os.rename(path, corrupt_path)
    logger.error("Invalid config at %s, moved to %s", path, corrupt_path)
    _atomic_write(path, deepcopy(DEFAULT_CONFIG))
    raise ValueError("Invalid JSON")


def load_config(path: str, reset_flag: bool, cli_overrides: dict) -> AppConfig:
    """Loads config, handles reset and auto-creation, applies CLI overrides. Logs INFO on read/write."""
    dest = Path(path)

    if reset_flag and dest.exists():
        _atomic_write(path, deepcopy(DEFAULT_CONFIG))
        logger.info("Reset config written to %s", path)

    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(path, deepcopy(DEFAULT_CONFIG))
        logger.info("Default config created at %s", path)

    raw = dest.read_text(encoding="utf-8")
    try:
        disk_data = json.loads(raw)
    except json.JSONDecodeError:
        mitigate_invalid_config(path, raw)

    config = deepcopy(DEFAULT_CONFIG)
    _deep_merge(config, disk_data)

    if cli_overrides:
        config.update(cli_overrides)

    logger.info("Config loaded from %s", path)
    return config


def _deep_merge(base: dict, override: dict) -> None:
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def apply_threshold_updates(path: str, current_config: AppConfig) -> AppConfig:
    """Re-reads config from disk and applies ONLY threshold updates to current_config. Logs INFO on reload."""
    try:
        raw = Path(path).read_text(encoding="utf-8")
        disk_data = json.loads(raw)
    except (OSError, json.JSONDecodeError) as e:
        logger.error("Failed to reload config for threshold update: %s", e)
        return current_config

    disk_thresholds = disk_data.get("thresholds")
    if disk_thresholds == current_config.get("thresholds"):
        return current_config

    updated = deepcopy(current_config)
    updated["thresholds"] = deepcopy(disk_thresholds)
    logger.info("Threshold updates applied from %s", path)
    return updated


def save_session_changes(path: str, hand_changed_position: Optional[PositionConfig], hand_changed_size: Optional[int]) -> None:
    """Writes exactly the hand-changed keys (position/size) to the config file on exit. Logs INFO on save."""
    if hand_changed_position is None and hand_changed_size is None:
        return

    try:
        raw = Path(path).read_text(encoding="utf-8")
        disk_dict = json.loads(raw)
    except (OSError, json.JSONDecodeError) as e:
        logger.error("Failed to read config for session save: %s", e)
        return

    if hand_changed_position is not None:
        disk_dict["position"] = hand_changed_position
    if hand_changed_size is not None:
        disk_dict["size"] = hand_changed_size

    _atomic_write(path, disk_dict)
    logger.info("Session changes saved to %s", path)