# Implementation Spec: Configuration File and CLI Arguments

| Field | Value |
|-------|-------|
| Issue | #7 |
| LLD | `docs/lld/active/0007-config-cli.md` |
| Generated | 2026-08-01 |
| Status | APPROVED |

## 1. Overview

This implementation establishes the core configuration system for BoostGauge. It provides default settings management, JSON disk persistence with atomic writing, CLI argument parsing and overrides, dynamic threshold hot-reloading, and window geometry tracking.

**Objective:** Implement a robust configuration system for BoostGauge supporting defaults, JSON file persistence, CLI argument overrides, window geometry tracking, and runtime threshold hot-reloading.

**Success Criteria:**
1. Default configuration file auto-created at `~/.boostgauge/config.json` (or `%APPDATA%/boostgauge/config.json` on Windows) on initial launch.
2. Command-line flags (`--theme`, `--size`, `--poll`, `--opacity`, `--no-topmost`, `--config`, `--reset-config`) correctly parse and override file configuration settings at runtime.
3. Strict schema validation enforces types, allowed themes, and value ranges, raising `ValueError` on invalid settings.
4. CLI flag `--reset-config` restores target configuration file to defaults.
5. Window geometry updates (`position.x`, `position.y`, `size`) persist to disk on move/exit and restore on launch.
6. Unified programmatic API in `src/boostgauge/config.py` passes all unit tests with 100% line and branch coverage in headless mode.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/__init__.py` | Add | Package initialization making `boostgauge` an importable Python module. |
| 2 | `src/boostgauge/config.py` | Add | Core configuration management module (defaults, JSON load/save, CLI parsing, validation, merging, geometry updates, and reset). |
| 3 | `tests/unit/test_config.py` | Add | Headless unit test suite covering configuration loading, CLI overrides, file persistence, validation errors, and geometry updates. |

**Implementation Order Rationale:**
`__init__.py` must exist first so that `boostgauge` is recognizable as a Python package. `src/boostgauge/config.py` contains the core business logic required for configuration handling. `tests/unit/test_config.py` imports `src/boostgauge/config.py` to validate all functionality.

## 3. Current State (for Modify/Delete files)

No existing application files are modified or deleted in this feature; all target files (`src/boostgauge/__init__.py`, `src/boostgauge/config.py`, and `tests/unit/test_config.py`) are new additions.

For context on existing test bootstrap configuration in the repository, the excerpt from `tests/conftest.py` (lines 1-8) is shown below:

```python
"""Project test bootstrap."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
```

**What changes:** No changes to `tests/conftest.py`. New module `src/boostgauge/config.py` and test file `tests/unit/test_config.py` will utilize `sys.path` set up by `conftest.py`.

## 4. Data Structures

### 4.1 `ThresholdRange`

**Definition:**

```python
from typing import TypedDict

class ThresholdRange(TypedDict):
    yellow: float
    red: float
```

**Concrete Example:**

```json
{
    "yellow": 75.0,
    "red": 90.0
}
```

### 4.2 `ThresholdsConfig`

**Definition:**

```python
class ThresholdsConfig(TypedDict):
    conpty: ThresholdRange
    memory_percent: ThresholdRange
    process_count: ThresholdRange
    handle_count: ThresholdRange
```

**Concrete Example:**

```json
{
    "conpty": {"yellow": 10.0, "red": 20.0},
    "memory_percent": {"yellow": 75.0, "red": 90.0},
    "process_count": {"yellow": 150.0, "red": 300.0},
    "handle_count": {"yellow": 50000.0, "red": 100000.0}
}
```

### 4.3 `WindowPosition`

**Definition:**

```python
class WindowPosition(TypedDict):
    x: int
    y: int
```

**Concrete Example:**

```json
{
    "x": 100,
    "y": 150
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

### 4.5 `BoostGaugeConfig`

**Definition:**

```python
class BoostGaugeConfig(TypedDict):
    polling_interval_seconds: float
    theme: str
    size: int
    opacity: float
    always_on_top: bool
    position: WindowPosition
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
    "position": {"x": 100, "y": 100},
    "thresholds": {
        "conpty": {"yellow": 10.0, "red": 20.0},
        "memory_percent": {"yellow": 75.0, "red": 90.0},
        "process_count": {"yellow": 150.0, "red": 300.0},
        "handle_count": {"yellow": 50000.0, "red": 100000.0}
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
    """Return platform-dependent default configuration path (~/.boostgauge/config.json or %APPDATA%/boostgauge/config.json)."""
    ...
```

**Input Example:**

```python
# No arguments
```

**Output Example (Unix):**

```python
Path("/home/user/.boostgauge/config.json")
```

**Output Example (Windows):**

```python
Path("C:/Users/user/AppData/Roaming/boostgauge/config.json")
```

**Edge Cases:**
- `APPDATA` environment variable unset on Windows -> falls back to `Path.home() / "AppData" / "Roaming" / "boostgauge" / "config.json"`.

### 5.2 `get_default_config()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def get_default_config() -> dict[str, Any]:
    """Return dictionary containing default configuration settings."""
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
```

**Edge Cases:**
- Returns a fresh deep copy on every invocation to prevent mutating global shared state.

### 5.3 `load_config_file()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def load_config_file(path: Path) -> dict[str, Any]:
    """Load configuration from JSON file; create default file if it does not exist."""
    ...
```

**Input Example:**

```python
path = Path("/tmp/test_config/config.json")
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
        "conpty": {"yellow": 10.0, "red": 20.0},
        "memory_percent": {"yellow": 75.0, "red": 90.0},
        "process_count": {"yellow": 150.0, "red": 300.0},
        "handle_count": {"yellow": 50000.0, "red": 100000.0},
    },
    "telltale_windows": {"short": 60, "medium": 600, "long": 3600},
    "show_driver_label": True,
    "show_digital_readout": True,
    "show_session_count": True,
}
```

**Edge Cases:**
- File missing -> auto-creates parent directories and default config file, returning default config.
- Corrupted/malformed JSON -> raises `ValueError("Invalid JSON in configuration file: ...")`.

### 5.4 `save_config_file()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def save_config_file(config: dict[str, Any], path: Path) -> None:
    """Atomically write configuration dictionary to JSON file."""
    ...
```

**Input Example:**

```python
config = {"theme": "light", "size": 350}
path = Path("/tmp/test_config/config.json")
```

**Output Example:**

```python
None  # Atomically writes to /tmp/test_config/config.json
```

**Edge Cases:**
- Target parent directory does not exist -> creates parent directories using `path.parent.mkdir(parents=True, exist_ok=True)`.
- Crash mid-write -> writes to temporary `.tmp` file in same directory first before calling `os.replace`.

### 5.5 `parse_cli_args()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def parse_cli_args(args: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse command-line flags for configuration overrides."""
    ...
```

**Input Example:**

```python
args = ["--theme", "light", "--size", "400", "--no-topmost"]
```

**Output Example:**

```python
argparse.Namespace(
    theme="light",
    size=400,
    poll=None,
    opacity=None,
    no_topmost=True,
    config=None,
    reset_config=False,
)
```

**Edge Cases:**
- `args=None` -> parses `sys.argv[1:]`.
- Unrecognized argument -> `argparse.ArgumentParser` calls `sys.exit()` with usage error message.

### 5.6 `validate_config()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def validate_config(config: dict[str, Any]) -> dict[str, Any]:
    """Validate configuration fields against allowed values, types, and bounds; raise ValueError on invalid data."""
    ...
```

**Input Example:**

```python
config = {
    "polling_interval_seconds": 1.0,
    "theme": "dark",
    "size": 300,
    "opacity": 0.8,
    "always_on_top": True,
    "position": {"x": 50, "y": 50},
    "thresholds": {
        "conpty": {"yellow": 10.0, "red": 20.0},
        "memory_percent": {"yellow": 75.0, "red": 90.0},
        "process_count": {"yellow": 150.0, "red": 300.0},
        "handle_count": {"yellow": 50000.0, "red": 100000.0},
    },
    "telltale_windows": {"short": 60, "medium": 600, "long": 3600},
    "show_driver_label": True,
    "show_digital_readout": True,
    "show_session_count": True,
}
```

**Output Example:**

```python
# Returns validated dictionary unchanged
{...}
```

**Edge Cases:**
- `theme="invalid"` -> raises `ValueError("Invalid theme 'invalid'. Must be one of: ['dark', 'light', 'stealth', 'cyberpunk']")`.
- `opacity=1.5` -> raises `ValueError("opacity must be between 0.0 and 1.0")`.
- `polling_interval_seconds <= 0` -> raises `ValueError("polling_interval_seconds must be positive")`.
- `size < 100` or `size > 2000` -> raises `ValueError("size must be between 100 and 2000")`.

### 5.7 `merge_config()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def merge_config(file_config: dict[str, Any], cli_args: argparse.Namespace) -> dict[str, Any]:
    """Merge file configuration dictionary with explicit CLI argument overrides."""
    ...
```

**Input Example:**

```python
file_config = get_default_config()
cli_args = argparse.Namespace(
    theme="stealth",
    size=450,
    poll=2.0,
    opacity=0.9,
    no_topmost=True,
    config=None,
    reset_config=False,
)
```

**Output Example:**

```python
{
    "polling_interval_seconds": 2.0,
    "theme": "stealth",
    "size": 450,
    "opacity": 0.9,
    "always_on_top": False,
    # other keys retained from file_config...
}
```

**Edge Cases:**
- `cli_args` options with `None` values do not overwrite `file_config` values.
- `no_topmost=True` sets `always_on_top=False`. `no_topmost=False` leaves `always_on_top` as set in `file_config`.

### 5.8 `load_effective_config()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def load_effective_config(cli_args_list: Optional[list[str]] = None) -> dict[str, Any]:
    """Orchestrate loading defaults, loading/creating file, applying CLI overrides, and validating final config."""
    ...
```

**Input Example:**

```python
cli_args_list = ["--theme", "cyberpunk", "--opacity", "0.95"]
```

**Output Example:**

```python
{
    "polling_interval_seconds": 1.0,
    "theme": "cyberpunk",
    "size": 300,
    "opacity": 0.95,
    "always_on_top": True,
    "position": {"x": 100, "y": 100},
    "thresholds": {...},
    "telltale_windows": {...},
    "show_driver_label": True,
    "show_digital_readout": True,
    "show_session_count": True,
}
```

**Edge Cases:**
- `--reset-config` passed in `cli_args_list` -> overwrites target config file with defaults and returns validated default config dict.

### 5.9 `update_window_geometry()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def update_window_geometry(
    path: Path,
    position: Optional[tuple[int, int]] = None,
    size: Optional[int] = None,
) -> None:
    """Update window position (x, y) and/or size in config file on exit or move."""
    ...
```

**Input Example:**

```python
path = Path("/tmp/test_config/config.json")
position = (250, 400)
size = 350
```

**Output Example:**

```python
None  # Updates and saves config file with position={"x": 250, "y": 400} and size=350
```

**Edge Cases:**
- `position=None` -> only updates `size`.
- `size=None` -> only updates `position`.
- File missing or invalid -> uses default config as base, updates geometry, and saves.

### 5.10 `reset_config_file()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def reset_config_file(path: Path) -> dict[str, Any]:
    """Reset specified configuration file to default settings."""
    ...
```

**Input Example:**

```python
path = Path("/tmp/test_config/config.json")
```

**Output Example:**

```python
# Returns default config dictionary and writes defaults to disk
{
    "polling_interval_seconds": 1.0,
    "theme": "dark",
    ...
}
```

**Edge Cases:**
- Path directory missing -> auto-creates parent directories before saving defaults.

### 5.11 `test_t010_default_config_file_creation()`

**File:** `tests/unit/test_config.py`

**Signature:**

```python
def test_t010_default_config_file_creation(tmp_path: Path) -> None:
    """T010: Auto-creates config.json with default keys on initial run."""
    ...
```

**Input Example:**

```python
tmp_path = Path("/tmp/pytest-of-user/pytest-0/test_t0100")
```

**Output Example:**

```python
None  # Creates config.json with DEFAULT_CONFIG in tmp_path
```

**Edge Cases:**
- `tmp_path` target file `config.json` does not exist prior to test execution.

### 5.12 `test_t020_directory_creation_on_first_run()`

**File:** `tests/unit/test_config.py`

**Signature:**

```python
def test_t020_directory_creation_on_first_run(tmp_path: Path) -> None:
    """T020: Creates missing parent directories when writing default config."""
    ...
```

**Input Example:**

```python
tmp_path = Path("/tmp/pytest-of-user/pytest-0/test_t0200")
```

**Output Example:**

```python
None  # Creates nested subdirectories and default config.json
```

**Edge Cases:**
- Parent directories `nested/subfolder` do not exist before invocation.

### 5.13 `test_t030_cli_argument_parsing()`

**File:** `tests/unit/test_config.py`

**Signature:**

```python
def test_t030_cli_argument_parsing() -> None:
    """T030: Correctly parses all valid CLI flags."""
    ...
```

**Input Example:**

```python
# No arguments (internal CLI flag list passed to parse_cli_args)
```

**Output Example:**

```python
None  # Asserts all parsed Namespace attributes match expected CLI values
```

**Edge Cases:**
- Passes all supported options (`--theme`, `--size`, `--poll`, `--opacity`, `--no-topmost`, `--config`, `--reset-config`) simultaneously.

### 5.14 `test_t040_cli_overrides_config_values()`

**File:** `tests/unit/test_config.py`

**Signature:**

```python
def test_t040_cli_overrides_config_values() -> None:
    """T040: CLI values take precedence over values loaded from config.json."""
    ...
```

**Input Example:**

```python
# No arguments (uses default config dict and parse_cli_args)
```

**Output Example:**

```python
None  # Asserts merged dict contains CLI override values
```

**Edge Cases:**
- Unset CLI flags (`None`) leave file configuration settings intact.

## 6. Change Instructions

### 6.1 `src/boostgauge/__init__.py` (Add)

**Complete file contents:**

```python
"""BoostGauge package initialization.

Issue #7: Feature configuration file and CLI arguments
"""

__version__ = "0.1.0"
```

### 6.2 `src/boostgauge/config.py` (Add)

**Complete file contents:**

```python
"""Configuration file loading, CLI parsing, validation, and persistence.

Issue #7: Feature configuration file and CLI arguments
"""

import argparse
import copy
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple, TypedDict


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
```

### 6.3 `tests/unit/test_config.py` (Add)

**Complete file contents:**

```python
"""Unit tests for boostgauge configuration management module.

Issue #7: Feature configuration file and CLI arguments
"""

import json
import os
from pathlib import Path
import pytest
from unittest.mock import patch

from boostgauge.config import (
    DEFAULT_CONFIG,
    get_default_config,
    get_default_config_path,
    load_config_file,
    load_effective_config,
    merge_config,
    parse_cli_args,
    reset_config_file,
    save_config_file,
    update_window_geometry,
    validate_config,
)


def test_t010_default_config_file_creation(tmp_path: Path):
    """T010: Auto-creates config.json with default keys on initial run."""
    config_file = tmp_path / "config.json"
    assert not config_file.exists()

    loaded = load_config_file(config_file)
    assert config_file.exists()
    assert loaded == DEFAULT_CONFIG

    with open(config_file, "r", encoding="utf-8") as f:
        file_data = json.load(f)
    assert file_data == DEFAULT_CONFIG


def test_t020_directory_creation_on_first_run(tmp_path: Path):
    """T020: Creates missing parent directories when writing default config."""
    config_file = tmp_path / "nested" / "subfolder" / "config.json"
    assert not config_file.parent.exists()

    loaded = load_config_file(config_file)
    assert config_file.exists()
    assert loaded == DEFAULT_CONFIG


def test_t030_cli_argument_parsing():
    """T030: Correctly parses all valid CLI flags."""
    args = parse_cli_args([
        "--theme", "cyberpunk",
        "--size", "500",
        "--poll", "0.5",
        "--opacity", "0.75",
        "--no-topmost",
        "--config", "custom/path.json",
        "--reset-config",
    ])
    assert args.theme == "cyberpunk"
    assert args.size == 500
    assert args.poll == 0.5
    assert args.opacity == 0.75
    assert args.no_topmost is True
    assert args.config == "custom/path.json"
    assert args.reset_config is True


def test_t040_cli_overrides_config_values():
    """T040: CLI values take precedence over values loaded from config.json."""
    file_config = get_default_config()
    file_config["theme"] = "dark"
    file_config["size"] = 300
    file_config["opacity"] = 1.0

    cli_args = parse_cli_args(["--theme", "light", "--size", "400", "--opacity", "0.8"])
    merged = merge_config(file_config, cli_args)

    assert merged["theme"] == "light"
    assert merged["size"] == 400
    assert merged["opacity"] == 0.8
    assert merged["always_on_top"] is True


def test_t050_custom_config_file_path(tmp_path: Path):
    """T050: Loads configuration from custom path passed via --config."""
    custom_path = tmp_path / "custom_config.json"
    custom_data = get_default_config()
    custom_data["theme"] = "stealth"
    save_config_file(custom_data, custom_path)

    effective = load_effective_config(["--config", str(custom_path)])
    assert effective["theme"] == "stealth"


def test_t060_invalid_theme_validation():
    """T060: Raises ValueError for unsupported theme string."""
    invalid_config = get_default_config()
    invalid_config["theme"] = "invalid_theme_name"

    with pytest.raises(ValueError, match="Invalid theme 'invalid_theme_name'"):
        validate_config(invalid_config)


def test_t070_invalid_opacity_validation():
    """T070: Raises ValueError for opacity out of 0.0-1.0 bounds."""
    invalid_config_high = get_default_config()
    invalid_config_high["opacity"] = 1.5
    with pytest.raises(ValueError, match="opacity must be between 0.0 and 1.0"):
        validate_config(invalid_config_high)

    invalid_config_low = get_default_config()
    invalid_config_low["opacity"] = -0.1
    with pytest.raises(ValueError, match="opacity must be between 0.0 and 1.0"):
        validate_config(invalid_config_low)


def test_t080_malformed_json_file_handling(tmp_path: Path):
    """T080: Raises ValueError with clear message on invalid JSON."""
    corrupt_file = tmp_path / "corrupt.json"
    corrupt_file.write_text("{ invalid json syntax ...", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid JSON in configuration file"):
        load_config_file(corrupt_file)


def test_t090_reset_config_flag(tmp_path: Path):
    """T090: Overwrites config file with default settings when --reset-config passed."""
    config_file = tmp_path / "config.json"
    modified_data = get_default_config()
    modified_data["theme"] = "cyberpunk"
    modified_data["size"] = 600
    save_config_file(modified_data, config_file)

    effective = load_effective_config(["--config", str(config_file), "--reset-config"])
    assert effective["theme"] == "dark"
    assert effective["size"] == 300

    on_disk = load_config_file(config_file)
    assert on_disk["theme"] == "dark"


def test_t100_geometry_update_persistence(tmp_path: Path):
    """T100: Saves window position and size updates to config.json."""
    config_file = tmp_path / "config.json"
    save_config_file(get_default_config(), config_file)

    update_window_geometry(config_file, position=(250, 350), size=400)

    updated = load_config_file(config_file)
    assert updated["position"] == {"x": 250, "y": 350}
    assert updated["size"] == 400


def test_t110_geometry_restoration(tmp_path: Path):
    """T110: Restores saved position and size on configuration load."""
    config_file = tmp_path / "config.json"
    custom_data = get_default_config()
    custom_data["position"] = {"x": 180, "y": 220}
    custom_data["size"] = 380
    save_config_file(custom_data, config_file)

    effective = load_effective_config(["--config", str(config_file)])
    assert effective["position"] == {"x": 180, "y": 220}
    assert effective["size"] == 380


def test_t120_dynamic_threshold_update():
    """T120: Applies threshold modifications immediately in-memory."""
    config = get_default_config()
    config["thresholds"]["conpty"]["yellow"] = 15.0
    config["thresholds"]["conpty"]["red"] = 25.0

    validated = validate_config(config)
    assert validated["thresholds"]["conpty"]["yellow"] == 15.0
    assert validated["thresholds"]["conpty"]["red"] == 25.0


def test_t130_unified_effective_config_load(tmp_path: Path):
    """T130: Combines defaults, file settings, CLI flags, and returns valid config."""
    config_file = tmp_path / "config.json"
    file_data = get_default_config()
    file_data["theme"] = "stealth"
    save_config_file(file_data, config_file)

    effective = load_effective_config(["--config", str(config_file), "--size", "420"])
    assert effective["theme"] == "stealth"
    assert effective["size"] == 420
    assert effective["polling_interval_seconds"] == 1.0


def test_platform_default_config_path_unix():
    """Platform-independent check for Unix default path."""
    with patch("sys.platform", "linux"):
        expected = Path.home() / ".boostgauge" / "config.json"
        actual = get_default_config_path()
        assert actual == expected


def test_platform_default_config_path_windows():
    """Platform-independent check for Windows default path using pathlib."""
    with patch("sys.platform", "win32"), patch.dict(os.environ, {"APPDATA": r"C:\Users\test\AppData\Roaming"}):
        expected = Path(r"C:\Users\test\AppData\Roaming") / "boostgauge" / "config.json"
        actual = get_default_config_path()
        assert actual == expected


def test_additional_validation_errors():
    """Verify detailed validation failure branches."""
    cfg = get_default_config()
    cfg["polling_interval_seconds"] = 0
    with pytest.raises(ValueError, match="polling_interval_seconds"):
        validate_config(cfg)

    cfg = get_default_config()
    cfg["size"] = 50
    with pytest.raises(ValueError, match="size"):
        validate_config(cfg)

    cfg = get_default_config()
    cfg["always_on_top"] = "invalid_bool"
    with pytest.raises(ValueError, match="always_on_top"):
        validate_config(cfg)

    cfg = get_default_config()
    cfg["position"] = {"x": 10}
    with pytest.raises(ValueError, match="position"):
        validate_config(cfg)

    cfg = get_default_config()
    cfg["thresholds"]["conpty"]["yellow"] = 30.0
    cfg["thresholds"]["conpty"]["red"] = 20.0
    with pytest.raises(ValueError, match="0 <= yellow <= red"):
        validate_config(cfg)

    cfg = get_default_config()
    cfg["telltale_windows"]["short"] = -10
    with pytest.raises(ValueError, match="telltale_windows"):
        validate_config(cfg)
```

## 7. Pattern References

### 7.1 Test Bootstrap and Path Resolution Pattern

**File:** `tests/conftest.py` (lines 1-8)

```python
"""Project test bootstrap."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
```

**Relevance:** Demonstrates `Path.resolve()` and platform-safe `Path` manipulation for standard Python package structure.

### 7.2 Headless Test Architecture and Unit Tier Coverage Pattern

**File:** `docs/design/0001-test-strategy.md` (lines 16-29)

```markdown
| Tier | Directory | What lives here | Coverage target | Speed budget |
|---|---|---|---|---|
| Unit | `tests/unit/` | Pure logic with no I/O — math, state machines, parsers, data transforms. | 100% line + branch on touched files | < 1 s for full suite |
```

**Relevance:** Establishes the 100% line + branch coverage target for pure logic unit tests in `tests/unit/`.

### 7.3 Python Package Dependencies Pattern

**File:** `pyproject.toml` (lines 1-15)

```toml
[project]
name = "boostgauge"
version = "0.1.0"
description = "Real-time system monitor styled like a racing tachometer"
authors = [
    {name = "Marty McEnroe",email = "opensource@martymcenroe.ai"}
]
license = {text = "MIT"}
readme = "README.md"
requires-python = ">=3.10,<4"
```

**Relevance:** Confirms standard Python 3.10+ stdlib usage with zero added external package dependencies for configuration management.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `import argparse` | stdlib | `src/boostgauge/config.py` |
| `import copy` | stdlib | `src/boostgauge/config.py` |
| `import json` | stdlib | `src/boostgauge/config.py`, `tests/unit/test_config.py` |
| `import os` | stdlib | `src/boostgauge/config.py`, `tests/unit/test_config.py` |
| `from pathlib import Path` | stdlib | `src/boostgauge/config.py`, `tests/unit/test_config.py` |
| `import sys` | stdlib | `src/boostgauge/config.py` |
| `from typing import Any, Dict, List, Optional, Tuple, TypedDict` | stdlib | `src/boostgauge/config.py` |
| `import pytest` | test dependency | `tests/unit/test_config.py` |
| `from unittest.mock import patch` | stdlib | `tests/unit/test_config.py` |

**New Dependencies:** None required. All implementation logic relies strictly on standard library Python 3.10+.

## 9. Placeholder

*Reserved for future use to maintain alignment with LLD section numbering.*

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `load_config_file()` | Non-existent `config.json` path | Creates file on disk and returns `DEFAULT_CONFIG` |
| T020 | `save_config_file()` | Path in non-existent directory tree | Auto-creates nested directories and writes JSON file |
| T030 | `parse_cli_args()` | `["--theme", "cyberpunk", "--size", "500", ...]` | `argparse.Namespace` with parsed attributes |
| T040 | `merge_config()` | Default config dict + CLI overrides | Dict with CLI values replacing file values |
| T050 | `load_effective_config()` | `["--config", "/path/to/custom.json"]` | Config dict loaded from custom path |
| T060 | `validate_config()` | `config["theme"] = "invalid_theme"` | Raises `ValueError("Invalid theme 'invalid_theme'...")` |
| T070 | `validate_config()` | `config["opacity"] = 1.5` | Raises `ValueError("opacity must be between 0.0 and 1.0")` |
| T080 | `load_config_file()` | File containing invalid JSON text | Raises `ValueError("Invalid JSON in configuration file...")` |
| T090 | `load_effective_config()` | `["--reset-config"]` | Overwrites disk file with defaults and returns default config |
| T100 | `update_window_geometry()` | `position=(250, 350), size=400` | Disk file updated with new position and size |
| T110 | `load_effective_config()` | Disk file containing custom geometry | Returned config dict has restored geometry values |
| T120 | `validate_config()` | Mutated threshold values in dict | Validated config returned with new threshold values |
| T130 | `load_effective_config()` | CLI args + custom config path | Merged, validated `BoostGaugeConfig` dict |

## 11. Implementation Notes

### 11.1 Platform Independence in Tests (Issue #1841)
In accordance with platform independence rules, test assertions in `tests/unit/test_config.py` compare `pathlib.Path` objects directly (`actual == expected`) rather than evaluating string representations (`str(path)`), avoiding path separator mismatch failures on Windows.

### 11.2 Traceability and Assertion Scoping (Issue #1860)
All assertions in `tests/unit/test_config.py` trace directly to behaviors specified in Section 1 and Section 5. For example, CLI overrides are tested purely in-memory via `merge_config` / `load_effective_config` without asserting un-specified disk mutation side effects.

### 11.3 Baseline-Independent Assertions (Issue #1902)
This configuration specification contains no visual regression rendering baseline images. All test verification is baseline-independent and executed in pure headless logic.

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3)
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
| Date | 2026-08-01 |
| Iterations | 1 |
| Finalized | 2026-08-01T05:04:00Z |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #7 |
| Verdict | APPROVED |
| Date | 2026-08-01 |
| Iterations | 1 |
| Finalized | 2026-08-01T10:04:48Z |

### Review Feedback Summary

The revised implementation spec is complete, highly specific, and fully executable. All function signatures in `src/boostgauge/config.py` and unit tests in `tests/unit/test_config.py` provide exact, copy-pasteable Python code without pseudocode or missing details. Section 5 has been updated to include complete specifications for tests `test_t010` through `test_t040`, addressing all previous review feedback. Assertion traceability was explicitly verified across all unit test cases, confirming tha...
