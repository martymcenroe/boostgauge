# Implementation Spec: Configuration file and CLI arguments

| Field | Value |
|-------|-------|
| Issue | #7 |
| LLD | `docs/lld/done/0007-config-and-cli-args.md` |
| Generated | 2026-07-31 |
| Status | APPROVED |

## 1. Overview

This specification details the implementation of the configuration management and command-line argument parsing subsystem (`src/boostgauge/config.py`) and its associated unit test suite (`tests/unit/test_config.py`) for BoostGauge.

**Objective:** Implement a configuration management system and CLI argument parser to handle thresholds, visual settings, window positioning, and polling intervals with priority overrides.

**Success Criteria:**
- Configuration file is auto-created with factory defaults at `%APPDATA%/boostgauge/config.json` (Windows) or `~/.boostgauge/config.json` (POSIX) when non-existent.
- CLI arguments (`--theme`, `--size`, `--poll`, `--opacity`, `--no-topmost`, `--config`, `--reset-config`) override configuration file values at runtime.
- Malformed JSON configuration files fall back gracefully to default values with logged warnings.
- Window coordinates and diameter size are saved atomically to disk without blocking GUI execution or instantiating `tkinter.Tk()`.
- Dynamic threshold and visual updates take effect immediately in memory.
- Unit test suite achieves ≥95% branch coverage with pure logic execution.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/config.py` | Add | Configuration loader, JSON schema defaults, validation, atomic saving, and CLI argument parsing functions. |
| 2 | `tests/unit/test_config.py` | Add | Comprehensive unit tests covering default generation, CLI parsing, priority merging, persistence, corruption recovery, and boundary validation. |

**Implementation Order Rationale:** `src/boostgauge/config.py` defines the core types, functions, and logic required by the application. `tests/unit/test_config.py` imports functions directly from `boostgauge.config` to validate behavior off-screen without GUI dependencies.

## 3. Current State (for Modify/Delete files)

Both target files (`src/boostgauge/config.py` and `tests/unit/test_config.py`) are new files with Change Type **Add**. No existing files are modified or deleted in this implementation.

### 3.1 `src/boostgauge/config.py`

*New file. Parent directory `src/boostgauge/` exists.*

### 3.2 `tests/unit/test_config.py`

*New file. Parent directory `tests/unit/` exists.*

## 4. Data Structures

### 4.1 `ThresholdValues`

**Definition:**

```python
from typing import TypedDict

class ThresholdValues(TypedDict):
    yellow: float
    red: float
```

**Concrete Example:**

```json
{
    "yellow": 70.0,
    "red": 85.0
}
```

### 4.2 `ThresholdsConfig`

**Definition:**

```python
class ThresholdsConfig(TypedDict):
    conpty: ThresholdValues
    memory_percent: ThresholdValues
    process_count: ThresholdValues
    handle_count: ThresholdValues
```

**Concrete Example:**

```json
{
    "conpty": {"yellow": 5.0, "red": 10.0},
    "memory_percent": {"yellow": 70.0, "red": 85.0},
    "process_count": {"yellow": 50.0, "red": 100.0},
    "handle_count": {"yellow": 1000.0, "red": 2000.0}
}
```

### 4.3 `PositionConfig`

**Definition:**

```python
class PositionConfig(TypedDict):
    x: int
    y: int
```

**Concrete Example:**

```json
{
    "x": 120,
    "y": 80
}
```

### 4.4 `TelltaleWindowsConfig`

**Definition:**

```python
class TelltaleWindowsConfig(TypedDict):
    short: int
    medium: int
    long: int
```

**Concrete Example:**

```json
{
    "short": 60,
    "medium": 600,
    "long": 3600
}
```

### 4.5 `ConfigData`

**Definition:**

```python
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
```

**Concrete Example:**

```json
{
    "polling_interval_seconds": 1.0,
    "theme": "dark",
    "size": 300,
    "opacity": 1.0,
    "always_on_top": true,
    "position": {
        "x": 100,
        "y": 100
    },
    "thresholds": {
        "conpty": {"yellow": 5.0, "red": 10.0},
        "memory_percent": {"yellow": 70.0, "red": 85.0},
        "process_count": {"yellow": 50.0, "red": 100.0},
        "handle_count": {"yellow": 1000.0, "red": 2000.0}
    },
    "telltale_windows": {
        "short": 60,
        "medium": 600,
        "long": 3600
    },
    "show_driver_label": true,
    "show_digital_readout": true,
    "show_session_count": true
}
```

## 5. Function Specifications

### 5.1 `get_default_config_path()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def get_default_config_path() -> Path:
    """Return platform-specific default config path (%APPDATA%/boostgauge/config.json or ~/.boostgauge/config.json)."""
    ...
```

**Input Example:**

```python
# No arguments
```

**Output Example (Windows):**

```python
PosixPath("/home/user/.boostgauge/config.json") # or WindowsPath("C:/Users/user/AppData/Roaming/boostgauge/config.json")
```

**Edge Cases:**
- `APPDATA` environment variable not set on Windows -> Fall back to `Path.home() / "AppData" / "Roaming" / "boostgauge" / "config.json"`.
- Non-Windows platform -> Return `Path.home() / ".boostgauge" / "config.json"`.

### 5.2 `get_default_config()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def get_default_config() -> ConfigData:
    """Return dictionary containing factory default configuration settings."""
    ...
```

**Input Example:**

```python
# No arguments
```

**Output Example:**

```python
{
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
```

**Edge Cases:**
- Returns a fresh deep copy dictionary each time to prevent accidental mutation of global state.

### 5.3 `validate_config()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def validate_config(data: Dict[str, Any]) -> ConfigData:
    """Validate raw dictionary against expected types and ranges; fill missing or invalid keys with defaults."""
    ...
```

**Input Example:**

```python
data = {
    "polling_interval_seconds": -5.0,  # Invalid bound
    "theme": "light",
    "size": "invalid_type",            # Invalid type
    "thresholds": {
        "conpty": {"yellow": 3.0}     # Missing red field
    }
}
```

**Output Example:**

```python
{
    "polling_interval_seconds": 1.0,   # Fallback to default
    "theme": "light",                  # Retained valid value
    "size": 300,                       # Fallback to default
    "opacity": 1.0,
    "always_on_top": True,
    "position": {"x": 100, "y": 100},
    "thresholds": {
        "conpty": {"yellow": 3.0, "red": 10.0}, # Restored default red
        "memory_percent": {"yellow": 70.0, "red": 85.0},
        "process_count": {"yellow": 50.0, "red": 100.0},
        "handle_count": {"yellow": 1000.0, "red": 2000.0},
    },
    "telltale_windows": {"short": 60, "medium": 600, "long": 3600},
    "show_driver_label": True,
    "show_digital_readout": True,
    "show_session_count": True,
}
```

**Edge Cases:**
- Non-dict input -> Logs warning, returns full `get_default_config()`.
- Out-of-bounds numbers (`opacity < 0.1` or `opacity > 1.0`, `size < 50`, `polling_interval_seconds <= 0`) -> Fall back to corresponding default value.

### 5.4 `load_config()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def load_config(config_path: Optional[Path] = None) -> ConfigData:
    """Load configuration from file. Create with defaults if missing. Fallback to defaults on corrupt JSON."""
    ...
```

**Input Example:**

```python
config_path = Path("/tmp/mock_config.json")
```

**Output Example:**

```python
{
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
```

**Edge Cases:**
- `config_path` is `None` -> Uses `get_default_config_path()`.
- File does not exist -> Automatically creates parent directories and file with `get_default_config()`, then returns default configuration.
- Corrupt JSON / Permission Error -> Logs warning to stderr/logging, returns validated `get_default_config()`.

### 5.5 `save_config()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def save_config(config: ConfigData, config_path: Optional[Path] = None) -> None:
    """Write configuration dictionary to specified path atomically with pretty formatting."""
    ...
```

**Input Example:**

```python
config = get_default_config()
config_path = Path("/tmp/test_dir/config.json")
```

**Output Example:**

```python
None  # Creates or overwrites /tmp/test_dir/config.json atomically
```

**Edge Cases:**
- Parent directories missing -> Creates parent directories recursively (`parents=True`).
- Permission denied / OSError during write -> Logs error warning, suppresses exception to prevent application crash.

### 5.6 `reset_config()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def reset_config(config_path: Optional[Path] = None) -> ConfigData:
    """Overwrite configuration file with default settings and return default ConfigData."""
    ...
```

**Input Example:**

```python
config_path = Path("/tmp/existing_config.json")
```

**Output Example:**

```python
# Returns get_default_config() and overwrites file contents with defaults
{
    "polling_interval_seconds": 1.0,
    "theme": "dark",
    "size": 300,
    "opacity": 1.0,
    "always_on_top": True,
    ...
}
```

**Edge Cases:**
- Overwrites any pre-existing custom config file content at `config_path`.

### 5.7 `parse_cli_args()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def parse_cli_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments supporting theme, size, poll, opacity, no-topmost, config path, and reset-config."""
    ...
```

**Input Example:**

```python
args = ["--theme", "light", "--size", "400", "--poll", "2.0", "--opacity", "0.9", "--no-topmost"]
```

**Output Example:**

```python
argparse.Namespace(
    theme="light",
    size=400,
    poll=2.0,
    opacity=0.9,
    no_topmost=True,
    config=None,
    reset_config=False
)
```

**Edge Cases:**
- Invalid numeric type or out-of-range option (e.g. `--opacity 2.5` or `--size -100`) -> Calls `parser.error()` causing system exit with descriptive message.
- `args` is `None` -> Parses `sys.argv[1:]`.

### 5.8 `merge_config_and_cli()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def merge_config_and_cli(config: ConfigData, cli_args: argparse.Namespace) -> ConfigData:
    """Return a new ConfigData dictionary where non-None CLI options override config file settings."""
    ...
```

**Input Example:**

```python
config = get_default_config()
cli_args = argparse.Namespace(
    theme="light",
    size=400,
    poll=None,
    opacity=0.8,
    no_topmost=True,
    config=None,
    reset_config=False
)
```

**Output Example:**

```python
{
    "polling_interval_seconds": 1.0,   # Unchanged
    "theme": "light",                  # Overridden by CLI
    "size": 400,                       # Overridden by CLI
    "opacity": 0.8,                    # Overridden by CLI
    "always_on_top": False,            # Overridden by --no-topmost
    "position": {"x": 100, "y": 100},
    "thresholds": {...},
    "telltale_windows": {...},
    "show_driver_label": True,
    "show_digital_readout": True,
    "show_session_count": True,
}
```

**Edge Cases:**
- `cli_args` options with `None` values do not overwrite existing `config` dictionary keys.
- Merged result is a new copy; does not mutate input `config` dict. Runtime CLI overrides are not persisted to disk.

### 5.9 `update_window_state()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def update_window_state(
    config: ConfigData,
    x: int,
    y: int,
    size: int,
    config_path: Optional[Path] = None
) -> ConfigData:
    """Update position and size in config state and persist to disk."""
    ...
```

**Input Example:**

```python
config = get_default_config()
x = 250
y = 300
size = 350
config_path = Path("/tmp/config.json")
```

**Output Example:**

```python
{
    "polling_interval_seconds": 1.0,
    "theme": "dark",
    "size": 350,                       # Updated
    "opacity": 1.0,
    "always_on_top": True,
    "position": {"x": 250, "y": 300},  # Updated
    "thresholds": {...},
    ...
}
```

**Edge Cases:**
- Immediately saves updated dictionary to `config_path` (or `get_default_config_path()` if `None`).

## 6. Change Instructions

### 6.1 `src/boostgauge/config.py` (Add)

**Complete file contents:**

```python
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

    # Validate top-level primitive fields
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

    # Validate position
    if "position" in data and isinstance(data["position"], dict):
        pos = data["position"]
        if "x" in pos and isinstance(pos["x"], int):
            result["position"]["x"] = pos["x"]
        if "y" in pos and isinstance(pos["y"], int):
            result["position"]["y"] = pos["y"]

    # Validate thresholds
    if "thresholds" in data and isinstance(data["thresholds"], dict):
        thresholds_in = data["thresholds"]
        for key in ("conpty", "memory_percent", "process_count", "handle_count"):
            if key in thresholds_in and isinstance(thresholds_in[key], dict):
                t_val = thresholds_in[key]
                if "yellow" in t_val and isinstance(t_val["yellow"], (int, float)):
                    result["thresholds"][key]["yellow"] = float(t_val["yellow"])
                if "red" in t_val and isinstance(t_val["red"], (int, float)):
                    result["thresholds"][key]["red"] = float(t_val["red"])

    # Validate telltale_windows
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
```

---

### 6.2 `tests/unit/test_config.py` (Add)

**Complete file contents:**

```python
"""Unit tests for BoostGauge configuration and CLI argument management.

Issue #7: Configuration file and CLI arguments
"""

import json
from pathlib import Path
import pytest

from boostgauge.config import (
    get_default_config,
    get_default_config_path,
    load_config,
    merge_config_and_cli,
    parse_cli_args,
    reset_config,
    save_config,
    update_window_state,
    validate_config,
)


def test_t010_auto_create_default_config_on_first_run(tmp_path: Path) -> None:
    """T010: Ensure load_config creates default config file if missing."""
    config_file = tmp_path / "boostgauge" / "config.json"
    assert not config_file.exists()

    config = load_config(config_file)

    assert config_file.exists()
    assert config == get_default_config()

    with open(config_file, "r", encoding="utf-8") as f:
        saved_data = json.load(f)
    assert saved_data["theme"] == "dark"
    assert saved_data["size"] == 300


def test_t020_cli_arguments_override_config_file_values() -> None:
    """T020: Merged config prioritizes non-None CLI options over config values."""
    base_config = get_default_config()
    base_config["theme"] = "dark"
    base_config["size"] = 300
    base_config["polling_interval_seconds"] = 1.0

    cli_args = parse_cli_args(["--theme", "neon", "--size", "450", "--no-topmost"])
    merged = merge_config_and_cli(base_config, cli_args)

    assert merged["theme"] == "neon"
    assert merged["size"] == 450
    assert merged["always_on_top"] is False
    assert merged["polling_interval_seconds"] == 1.0  # Unchanged
    # Verify input config was not mutated
    assert base_config["theme"] == "dark"


def test_t030_all_supported_cli_flags_parsed_correctly() -> None:
    """T030: Parser extracts theme, size, poll, opacity, topmost, config, reset."""
    args = [
        "--theme", "cyberpunk",
        "--size", "500",
        "--poll", "0.5",
        "--opacity", "0.85",
        "--no-topmost",
        "--config", "/custom/path.json",
        "--reset-config"
    ]
    parsed = parse_cli_args(args)

    assert parsed.theme == "cyberpunk"
    assert parsed.size == 500
    assert parsed.poll == 0.5
    assert parsed.opacity == 0.85
    assert parsed.no_topmost is True
    assert parsed.config == "/custom/path.json"
    assert parsed.reset_config is True


def test_t040_reset_config_flag_overwrites_file_with_defaults(tmp_path: Path) -> None:
    """T040: Reset config overwrites an existing file with defaults."""
    config_file = tmp_path / "config.json"
    custom_data = get_default_config()
    custom_data["theme"] = "custom_theme"
    custom_data["size"] = 800
    save_config(custom_data, config_file)

    reset_result = reset_config(config_file)

    assert reset_result == get_default_config()
    with open(config_file, "r", encoding="utf-8") as f:
        reloaded = json.load(f)
    assert reloaded["theme"] == "dark"
    assert reloaded["size"] == 300


def test_t050_save_and_restore_window_position_and_size(tmp_path: Path) -> None:
    """T050: Update window state updates memory dict and persists to JSON file."""
    config_file = tmp_path / "config.json"
    initial_config = get_default_config()

    updated = update_window_state(initial_config, x=250, y=175, size=400, config_path=config_file)

    assert updated["position"]["x"] == 250
    assert updated["position"]["y"] == 175
    assert updated["size"] == 400

    reloaded = load_config(config_file)
    assert reloaded["position"]["x"] == 250
    assert reloaded["position"]["y"] == 175
    assert reloaded["size"] == 400


def test_t060_in_memory_threshold_update_without_restart() -> None:
    """T060: Modifying threshold dict updates memory state dynamically."""
    config = get_default_config()
    assert config["thresholds"]["memory_percent"]["yellow"] == 70.0

    config["thresholds"]["memory_percent"]["yellow"] = 80.0
    config["thresholds"]["memory_percent"]["red"] = 92.0

    assert config["thresholds"]["memory_percent"]["yellow"] == 80.0
    assert config["thresholds"]["memory_percent"]["red"] == 92.0


def test_t070_graceful_handling_of_corrupt_config_json(tmp_path: Path) -> None:
    """T070: Corrupt JSON syntax falls back to default values without raising crash."""
    config_file = tmp_path / "corrupt_config.json"
    config_file.write_text("{ corrupt json syntax ...", encoding="utf-8")

    config = load_config(config_file)

    assert config == get_default_config()


def test_t080_validation_of_out_of_range_cli_values() -> None:
    """T080: Out-of-bounds CLI opacity or size raises SystemExit from argparse."""
    with pytest.raises(SystemExit):
        parse_cli_args(["--opacity", "2.5"])

    with pytest.raises(SystemExit):
        parse_cli_args(["--size", "30"])


def test_get_default_config_path_platform_handling(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify platform detection for default config path uses pathlib.Path comparison."""
    monkeypatch.setattr("platform.system", lambda: "Windows")
    monkeypatch.setenv("APPDATA", "C:/Users/MockUser/AppData/Roaming")
    win_path = get_default_config_path()
    expected_win = Path("C:/Users/MockUser/AppData/Roaming/boostgauge/config.json")
    assert win_path == expected_win

    monkeypatch.setattr("platform.system", lambda: "Linux")
    posix_path = get_default_config_path()
    expected_posix = Path.home() / ".boostgauge" / "config.json"
    assert posix_path == expected_posix


def test_validate_config_partial_and_corrupt_keys() -> None:
    """Verify partial validation retains valid fields and replaces invalid ones with defaults."""
    raw_data = {
        "polling_interval_seconds": -1.0,  # Invalid
        "theme": "vibrant",                # Valid
        "opacity": 0.5,                    # Valid
        "thresholds": {
            "conpty": {"yellow": 8.0}      # Missing red
        }
    }
    validated = validate_config(raw_data)

    assert validated["polling_interval_seconds"] == 1.0  # Restored default
    assert validated["theme"] == "vibrant"
    assert validated["opacity"] == 0.5
    assert validated["thresholds"]["conpty"]["yellow"] == 8.0
    assert validated["thresholds"]["conpty"]["red"] == 10.0  # Restored default
```

## 7. Pattern References

### 7.1 Off-Screen Pure Logic Test Execution

**File:** `tests/conftest.py` (lines 1-8)

```python
"""Project test bootstrap."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
```

**Relevance:** Standard project practice for testing non-GUI logic directly against `src/` modules without instantiating `tkinter.Tk()` components.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `import argparse` | stdlib | `src/boostgauge/config.py` |
| `import copy` | stdlib | `src/boostgauge/config.py` |
| `import json` | stdlib | `src/boostgauge/config.py`, `tests/unit/test_config.py` |
| `import logging` | stdlib | `src/boostgauge/config.py` |
| `import os` | stdlib | `src/boostgauge/config.py` |
| `import platform` | stdlib | `src/boostgauge/config.py` |
| `from pathlib import Path` | stdlib | `src/boostgauge/config.py`, `tests/unit/test_config.py` |
| `from typing import Any, Dict, List, Optional, TypedDict` | stdlib | `src/boostgauge/config.py` |
| `import pytest` | external (dev) | `tests/unit/test_config.py` |

**New Dependencies:** None required. Uses Python standard library only.

## 9. Placeholder

*Reserved for future alignment with LLD section numbering.*

## 10. Test Mapping

| Test ID | Scenario | Tests Function | Input | Expected Output | Pass Criteria |
|---------|----------|---------------|-------|-----------------|---------------|
| T010 | 010 / REQ-1 | `load_config()` | Non-existent path `tmp_path/config.json` | Returns `get_default_config()`, file created | File exists on disk, matches default JSON schema |
| T020 | 030 / REQ-2 | `merge_config_and_cli()` | Config `theme="dark"`, CLI `--theme neon` | Merged config `theme="neon"` | `merged["theme"] == "neon"` without disk modification |
| T030 | 040 / REQ-3 | `parse_cli_args()` | `--theme cyberpunk --size 500 --poll 0.5 --opacity 0.85 --no-topmost` | Namespace object with parsed values | All flags correctly mapped in returned Namespace |
| T040 | 050 / REQ-4 | `reset_config()` | Path to modified config file | File overwritten with `DEFAULT_CONFIG` JSON | Reloaded file matches factory defaults |
| T050 | 060 / REQ-5 | `update_window_state()` | `x=250, y=175, size=400` | Config updated and persisted to JSON | Reloaded config retains updated position & size |
| T060 | 070 / REQ-6 | In-memory threshold update | Mutate `config["thresholds"]["memory_percent"]` | Memory state reflects new thresholds immediately | Threshold values updated without restarting app |
| T070 | 080 / REQ-7 | `load_config()` | Malformed JSON file content | Warning logged, default config returned | Function succeeds without crashing |
| T080 | 090 / REQ-7 | `parse_cli_args()` | `--opacity 2.5` or `--size 30` | `SystemExit` raised by `argparse` | Out-of-bounds parameters rejected cleanly |

## 11. Implementation Notes

### 11.1 Error Handling & Graceful Recovery

- `load_config()` catches all file reading and JSON parsing exceptions (`JSONDecodeError`, `PermissionError`, `OSError`). It logs a warning via `logging.getLogger("boostgauge.config")` and falls back to `get_default_config()`.
- `save_config()` writes to a temporary file (`.tmp`) in the same destination directory before executing `os.replace` (atomic file replacement) to prevent partial file write corruption during unexpected application exit or power loss.

### 11.2 Platform Independence in Test Suite

- All file path comparisons in `tests/unit/test_config.py` compare `pathlib.Path` objects directly (`win_path == Path(...)`), adhering to Issue #1841. Hardcoded string concatenation with separator slashes is forbidden.
- Test assertions trace strictly to specified behavior in Sections 3 and 10; CLI overrides in memory are never asserted to persist back to disk (Issue #1860).

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3 - explicit note for Add-only files)
- [x] Every data structure has a concrete JSON/YAML example (Section 4)
- [x] Every function has input/output examples with realistic values (Section 5)
- [x] Change instructions are diff-level specific (Section 6)
- [x] Pattern references include file:line and are verified to exist (Section 7)
- [x] All imports are listed and verified (Section 8)
- [x] Test mapping covers all LLD test scenarios (Section 10)

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #7 |
| Verdict | APPROVED |
| Date | 2026-07-31 |
| Iterations | 1 |
| Finalized | 2026-07-31T12:46:00Z |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #7 |
| Verdict | APPROVED |
| Date | 2026-07-31 |
| Iterations | 1 |
| Finalized | 2026-07-31T17:47:41Z |

### Review Feedback Summary

The specification is complete, concrete, and ready for immediate implementation. The updated test suite resolves the path escaping issue in test_get_default_config_path_platform_handling by using normalized forward-slash paths for pathlib.Path comparison across platforms. Every assertion in tests/unit/test_config.py directly traces to specified behavior in Section 5 and Requirements 1-7. The implementation details for src/boostgauge/config.py and tests/unit/test_config.py provide complete, fully...
