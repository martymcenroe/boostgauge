# Implementation Spec: #7 - Feature: Configuration File and CLI Arguments

<!-- Metadata -->
| Field | Value |
|-------|-------|
| Issue | #7 |
| LLD | `docs/lld/done/0007-config-cli.md` |
| Generated | 2026-07-31 |
| Status | APPROVED |

## 1. Overview

This implementation specification defines the configuration file persistence, platform-specific path resolution, CLI argument parsing, schema validation, dynamic threshold updating, and window geometry preservation for BoostGauge. It establishes a zero-runtime-dependency configuration management system using standard library `json` and `argparse` modules.

**Objective:** Implement a configuration system for BoostGauge that handles settings file persistence, CLI argument overrides, dynamic threshold updates, and window position/size state saving.

**Success Criteria:**
- Default configuration auto-created at `%APPDATA%/boostgauge/config.json` on Windows or `~/.boostgauge/config.json` on POSIX systems when missing.
- CLI flags (`--theme`, `--size`, `--poll`, `--opacity`, `--no-topmost`, `--config`, `--reset-config`) correctly override config values or alter target path / default state.
- Window position (`x`, `y`) and `size` parameters saved atomically to JSON on exit and loaded on startup.
- Dynamic threshold modifications validate immediately in memory without application restart.
- Invalid JSON contents or out-of-range CLI values raise a clean `ConfigError`.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/__init__.py` | Add | Package initialization defining package version and public exports |
| 2 | `src/boostgauge/config.py` | Add | Core configuration module: path resolution, defaults, validation, I/O, CLI parsing, overrides |
| 3 | `src/boostgauge/app.py` | Add | Application runtime entry point shell integrating config lifecycle |
| 4 | `src/boostgauge/__main__.py` | Add | Executable CLI entry point executing main application flow |
| 5 | `pyproject.toml` | Modify | Register `boostgauge` CLI script entry point |
| 6 | `tests/unit/test_config.py` | Add | Unit test suite for configuration logic, path resolution, CLI overrides, atomic saving, and error handling |

**Implementation Order Rationale:**
1. `__init__.py` establishes the `boostgauge` namespace.
2. `config.py` contains core configuration logic and error definitions without depending on other package modules.
3. `app.py` depends on `GaugeConfigDict` and functions in `config.py`.
4. `__main__.py` depends on both `config.py` and `app.py` to drive execution.
5. `pyproject.toml` binds the `boostgauge` executable command to `boostgauge.__main__:main`.
6. `test_config.py` verifies `config.py` isolated from GUI dependencies per standard testing policy.

## 3. Current State (for Modify/Delete files)

### 3.1 `pyproject.toml`

**Relevant excerpt** (lines 17-28):

```toml
[project.urls]
Homepage = "https://boostgauge.martymcenroe.ai"
Repository = "https://github.com/martymcenroe/boostgauge"
Documentation = "https://github.com/martymcenroe/boostgauge/wiki"
Issues = "https://github.com/martymcenroe/boostgauge/issues"
"Built with AssemblyZero" = "https://github.com/martymcenroe/AssemblyZero"


[build-system]
requires = ["poetry-core>=2.0.0,<3.0.0"]
build-backend = "poetry.core.masonry.api"
```

**What changes:** Add `[project.scripts]` section defining `boostgauge = "boostgauge.__main__:main"` right after `[project.urls]`.

## 4. Data Structures

### 4.1 `Threshold`

**Definition:**

```python
from typing import TypedDict

class Threshold(TypedDict):
    yellow: float
    red: float
```

**Concrete Example:**

```json
{
  "yellow": 20.0,
  "red": 40.0
}
```

### 4.2 `MetricThresholds`

**Definition:**

```python
from typing import TypedDict

class MetricThresholds(TypedDict):
    conpty: Threshold
    memory_percent: Threshold
    process_count: Threshold
    handle_count: Threshold
```

**Concrete Example:**

```json
{
  "conpty": { "yellow": 20.0, "red": 40.0 },
  "memory_percent": { "yellow": 75.0, "red": 90.0 },
  "process_count": { "yellow": 150.0, "red": 300.0 },
  "handle_count": { "yellow": 10000.0, "red": 25000.0 }
}
```

### 4.3 `WindowPosition`

**Definition:**

```python
from typing import TypedDict

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

### 4.4 `TelltaleWindows`

**Definition:**

```python
from typing import TypedDict

class TelltaleWindows(TypedDict):
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

### 4.5 `GaugeConfigDict`

**Definition:**

```python
from typing import TypedDict

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
```

**Concrete Example:**

```json
{
  "polling_interval_seconds": 1.0,
  "theme": "dark",
  "size": 300,
  "opacity": 0.9,
  "always_on_top": true,
  "position": {
    "x": 100,
    "y": 100
  },
  "thresholds": {
    "conpty": { "yellow": 20.0, "red": 40.0 },
    "memory_percent": { "yellow": 75.0, "red": 90.0 },
    "process_count": { "yellow": 150.0, "red": 300.0 },
    "handle_count": { "yellow": 10000.0, "red": 25000.0 }
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
    """Return platform-specific default config path (%APPDATA%/boostgauge/config.json on Windows, ~/.boostgauge/config.json on POSIX)."""
    ...
```

**Input Example:**
None (reads `sys.platform` and `os.environ`).

**Output Example (Windows):**

```python
Path("C:/Users/mcwiz/AppData/Roaming/boostgauge/config.json")
```

**Output Example (POSIX):**

```python
Path("/home/user/.boostgauge/config.json")
```

**Edge Cases:**
- `sys.platform == "win32"` but `APPDATA` env var is missing/empty -> fall back to `Path.home() / "AppData" / "Roaming" / "boostgauge" / "config.json"`.

---

### 5.2 `get_default_config()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def get_default_config() -> GaugeConfigDict:
    """Return a deep copy of default configuration dictionary."""
    ...
```

**Input Example:**
None.

**Output Example:**

```python
{
    "polling_interval_seconds": 1.0,
    "theme": "dark",
    "size": 300,
    "opacity": 0.9,
    "always_on_top": True,
    "position": {"x": 100, "y": 100},
    "thresholds": {
        "conpty": {"yellow": 20.0, "red": 40.0},
        "memory_percent": {"yellow": 75.0, "red": 90.0},
        "process_count": {"yellow": 150.0, "red": 300.0},
        "handle_count": {"yellow": 10000.0, "red": 25000.0},
    },
    "telltale_windows": {"short": 60, "medium": 600, "long": 3600},
    "show_driver_label": True,
    "show_digital_readout": True,
    "show_session_count": True,
}
```

**Edge Cases:**
- Returns a fresh deep copy on every call so callers mutating the returned dict do not pollute module default template state.

---

### 5.3 `validate_config()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def validate_config(config: dict[str, Any]) -> GaugeConfigDict:
    """Validate structure and value bounds of a configuration dictionary, returning typed GaugeConfigDict or raising ConfigError."""
    ...
```

**Input Example:**

```python
{
    "polling_interval_seconds": 0.5,
    "theme": "light",
    "size": 250,
    "opacity": 0.8,
    "always_on_top": False,
    "position": {"x": 50, "y": 50},
    "thresholds": {
        "conpty": {"yellow": 10.0, "red": 30.0},
        "memory_percent": {"yellow": 70.0, "red": 85.0},
        "process_count": {"yellow": 100.0, "red": 200.0},
        "handle_count": {"yellow": 5000.0, "red": 15000.0},
    },
    "telltale_windows": {"short": 30, "medium": 300, "long": 1800},
    "show_driver_label": True,
    "show_digital_readout": True,
    "show_session_count": True,
}
```

**Output Example:**

```python
# Returns validated GaugeConfigDict (same dict if valid)
```

**Edge Cases:**
- `polling_interval_seconds <= 0` -> raises `ConfigError("polling_interval_seconds must be positive")`.
- `theme` not in `("dark", "light", "high_contrast")` -> raises `ConfigError("Invalid theme 'invalid'. Allowed: dark, light, high_contrast")`.
- `size < 100` or `size > 2000` -> raises `ConfigError("size must be between 100 and 2000")`.
- `opacity < 0.1` or `opacity > 1.0` -> raises `ConfigError("opacity must be between 0.1 and 1.0")`.
- `yellow >= red` in thresholds -> raises `ConfigError("Threshold yellow must be strictly less than red for conpty")`.
- Missing required keys in root dictionary -> raises `ConfigError("Missing required config key: theme")`.

---

### 5.4 `load_config()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def load_config(config_path: Optional[Path] = None) -> GaugeConfigDict:
    """Load configuration from specified path (or default path), auto-creating default config if file is missing."""
    ...
```

**Input Example:**

```python
config_path = Path("/tmp/test_config/config.json")
```

**Output Example:**

```python
{
    "polling_interval_seconds": 1.0,
    "theme": "dark",
    "size": 300,
    "opacity": 0.9,
    "always_on_top": True,
    "position": {"x": 100, "y": 100},
    "thresholds": { ... },
    "telltale_windows": { ... },
    "show_driver_label": True,
    "show_digital_readout": True,
    "show_session_count": True,
}
```

**Edge Cases:**
- File missing -> auto-creates directory structure, writes default config to disk, returns default config dict.
- File contains invalid JSON syntax -> raises `ConfigError(f"Failed to parse JSON config file: {e}")`.
- File content fails schema bounds -> raises `ConfigError` via `validate_config()`.

---

### 5.5 `save_config()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def save_config(config: GaugeConfigDict, config_path: Optional[Path] = None) -> None:
    """Atomically write configuration dictionary to JSON file at specified path (or default path)."""
    ...
```

**Input Example:**

```python
config = get_default_config()
config_path = Path("/tmp/test_config/config.json")
```

**Output Example:**

```python
None  # Side effect: /tmp/test_config/config.json written atomically with formatted JSON
```

**Edge Cases:**
- Parent directory does not exist -> auto-creates parent directory path (`parents=True, exist_ok=True`).
- Write failure (e.g. read-only filesystem) -> raises `ConfigError(f"Failed to save configuration: {e}")`.

---

### 5.6 `parse_cli_args()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def parse_cli_args(args: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse CLI options for theme, size, poll, opacity, topmost, config path, and reset flag."""
    ...
```

**Input Example:**

```python
args = ["--theme", "light", "--size", "400", "--poll", "2.0", "--no-topmost"]
```

**Output Example:**

```python
argparse.Namespace(
    theme="light",
    size=400,
    poll=2.0,
    opacity=None,
    no_topmost=True,
    config=None,
    reset_config=False,
)
```

**Edge Cases:**
- Empty `args` list -> returns `Namespace` with all CLI optional overrides set to `None` / `False`.
- Invalid flag (e.g. `--unknown`) -> `argparse` prints usage and exits or raises `SystemExit`.

---

### 5.7 `apply_cli_overrides()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def apply_cli_overrides(config: GaugeConfigDict, parsed_args: argparse.Namespace) -> GaugeConfigDict:
    """Apply parsed CLI arguments as overrides on top of loaded configuration dictionary."""
    ...
```

**Input Example:**

```python
config = get_default_config()
parsed_args = argparse.Namespace(
    theme="light",
    size=400,
    poll=2.5,
    opacity=0.7,
    no_topmost=True,
    config=None,
    reset_config=False,
)
```

**Output Example:**

```python
# Updated GaugeConfigDict where:
# config["theme"] == "light"
# config["size"] == 400
# config["polling_interval_seconds"] == 2.5
# config["opacity"] == 0.7
# config["always_on_top"] == False
```

**Edge Cases:**
- `parsed_args` attributes are `None` -> leaves corresponding `config` values unchanged.
- `parsed_args.no_topmost` is `True` -> sets `config["always_on_top"] = False`.

---

### 5.8 `update_window_geometry()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def update_window_geometry(config: GaugeConfigDict, x: int, y: int, size: int) -> GaugeConfigDict:
    """Update window position and size parameters in configuration data structure prior to exit/save."""
    ...
```

**Input Example:**

```python
config = get_default_config()
x = 250
y = 300
size = 350
```

**Output Example:**

```python
# Updated GaugeConfigDict where:
# config["position"]["x"] == 250
# config["position"]["y"] == 300
# config["size"] == 350
```

**Edge Cases:**
- `size` parameter out of bounds -> validated when `save_config()` or `validate_config()` is subsequently called.

---

### 5.9 `main()`

**File:** `src/boostgauge/__main__.py`

**Signature:**

```python
def main(args: Optional[list[str]] = None) -> int:
    """CLI main entry point for BoostGauge."""
    ...
```

**Input Example:**

```python
args = ["--theme", "dark"]
```

**Output Example:**

```python
0  # Success exit code
```

**Edge Cases:**
- Invalid config or CLI options -> catches `ConfigError`, prints error message to `sys.stderr`, returns exit code `1`.

---

### 5.10 `run_app()`

**File:** `src/boostgauge/app.py`

**Signature:**

```python
def run_app(config: GaugeConfigDict) -> None:
    """Application runtime execution shell."""
    ...
```

**Input Example:**

```python
config = get_default_config()
```

**Output Example:**

```python
None
```

**Edge Cases:**
- Non-GUI headless execution shell for runtime initialization.

---

### 5.11 `test_t020_platform_path_resolution()`

**File:** `tests/unit/test_config.py`

**Signature:**

```python
def test_t020_platform_path_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    """T020: Test platform path resolution for Windows and POSIX."""
    ...
```

**Input Example:**

```python
monkeypatch = pytest.MonkeyPatch()
```

**Output Example:**

```python
None
```

**Edge Cases:**
- Validates environment variable overrides for Windows APPDATA and POSIX home directory.

---

### 5.12 `test_t030_cli_options_override_config_file()`

**File:** `tests/unit/test_config.py`

**Signature:**

```python
def test_t030_cli_options_override_config_file() -> None:
    """T030: Test CLI options override config file values."""
    ...
```

**Input Example:**

```python
args = ["--theme", "light", "--size", "400", "--poll", "5.0"]
```

**Output Example:**

```python
None
```

**Edge Cases:**
- Unspecified configuration values retain their default configuration dictionary values.

## 6. Change Instructions

### 6.1 `src/boostgauge/__init__.py` (Add)

**Complete file contents:**

```python
"""BoostGauge system monitor package.

Issue #7: Configuration File and CLI Arguments
"""

from boostgauge.config import (
    ConfigError,
    GaugeConfigDict,
    get_default_config,
    get_default_config_path,
    load_config,
    save_config,
)

__version__ = "0.1.0"

__all__ = [
    "ConfigError",
    "GaugeConfigDict",
    "get_default_config",
    "get_default_config_path",
    "load_config",
    "save_config",
    "__version__",
]
```

---

### 6.2 `src/boostgauge/config.py` (Add)

**Complete file contents:**

```python
"""Configuration manager for BoostGauge.

Handles settings file persistence, CLI argument overrides, dynamic threshold
updates, and window position/size state saving.

Issue #7: Configuration File and CLI Arguments
"""

import argparse
import copy
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, TypedDict


class ConfigError(Exception):
    """Raised when configuration file or CLI arguments fail schema or value validation."""

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


_DEFAULT_CONFIG: GaugeConfigDict = {
    "polling_interval_seconds": 1.0,
    "theme": "dark",
    "size": 300,
    "opacity": 0.9,
    "always_on_top": True,
    "position": {"x": 100, "y": 100},
    "thresholds": {
        "conpty": {"yellow": 20.0, "red": 40.0},
        "memory_percent": {"yellow": 75.0, "red": 90.0},
        "process_count": {"yellow": 150.0, "red": 300.0},
        "handle_count": {"yellow": 10000.0, "red": 25000.0},
    },
    "telltale_windows": {"short": 60, "medium": 600, "long": 3600},
    "show_driver_label": True,
    "show_digital_readout": True,
    "show_session_count": True,
}

VALID_THEMES = {"dark", "light", "high_contrast"}


def get_default_config_path() -> Path:
    """Return platform-specific default config path.

    %APPDATA%/boostgauge/config.json on Windows, ~/.boostgauge/config.json on POSIX.
    """
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "boostgauge" / "config.json"
        return Path.home() / "AppData" / "Roaming" / "boostgauge" / "config.json"
    return Path.home() / ".boostgauge" / "config.json"


def get_default_config() -> GaugeConfigDict:
    """Return a deep copy of default configuration dictionary."""
    return copy.deepcopy(_DEFAULT_CONFIG)


def validate_config(config: Dict[str, Any]) -> GaugeConfigDict:
    """Validate structure and value bounds of a configuration dictionary."""
    if not isinstance(config, dict):
        raise ConfigError("Configuration root must be a dictionary")

    required_keys = [
        "polling_interval_seconds",
        "theme",
        "size",
        "opacity",
        "always_on_top",
        "position",
        "thresholds",
        "telltale_windows",
        "show_driver_label",
        "show_digital_readout",
        "show_session_count",
    ]
    for key in required_keys:
        if key not in config:
            raise ConfigError(f"Missing required config key: '{key}'")

    poll = config["polling_interval_seconds"]
    if not isinstance(poll, (int, float)) or poll <= 0:
        raise ConfigError(f"polling_interval_seconds must be a positive number, got {poll}")

    theme = config["theme"]
    if theme not in VALID_THEMES:
        raise ConfigError(
            f"Invalid theme '{theme}'. Must be one of: {', '.join(sorted(VALID_THEMES))}"
        )

    size = config["size"]
    if not isinstance(size, int) or size < 100 or size > 2000:
        raise ConfigError(f"size must be an integer between 100 and 2000, got {size}")

    opacity = config["opacity"]
    if not isinstance(opacity, (int, float)) or opacity < 0.1 or opacity > 1.0:
        raise ConfigError(f"opacity must be a float between 0.1 and 1.0, got {opacity}")

    if not isinstance(config["always_on_top"], bool):
        raise ConfigError("always_on_top must be a boolean")

    pos = config["position"]
    if not isinstance(pos, dict) or "x" not in pos or "y" not in pos:
        raise ConfigError("position must be a dict with 'x' and 'y' integer coordinates")
    if not isinstance(pos["x"], int) or not isinstance(pos["y"], int):
        raise ConfigError("position coordinates 'x' and 'y' must be integers")

    thresholds = config["thresholds"]
    if not isinstance(thresholds, dict):
        raise ConfigError("thresholds must be a dictionary")

    required_metrics = ["conpty", "memory_percent", "process_count", "handle_count"]
    for metric in required_metrics:
        if metric not in thresholds or not isinstance(thresholds[metric], dict):
            raise ConfigError(f"Missing or invalid threshold dict for metric '{metric}'")
        t = thresholds[metric]
        if "yellow" not in t or "red" not in t:
            raise ConfigError(f"Threshold for '{metric}' must contain 'yellow' and 'red'")
        yellow, red = t["yellow"], t["red"]
        if not isinstance(yellow, (int, float)) or yellow < 0:
            raise ConfigError(f"Yellow threshold for '{metric}' must be non-negative")
        if not isinstance(red, (int, float)) or red < 0:
            raise ConfigError(f"Red threshold for '{metric}' must be non-negative")
        if yellow >= red:
            raise ConfigError(
                f"Threshold yellow ({yellow}) must be strictly less than red ({red}) for '{metric}'"
            )

    t_windows = config["telltale_windows"]
    if not isinstance(t_windows, dict):
        raise ConfigError("telltale_windows must be a dictionary")
    for w in ["short", "medium", "long"]:
        if w not in t_windows or not isinstance(t_windows[w], int) or t_windows[w] <= 0:
            raise ConfigError(f"telltale_windows parameter '{w}' must be a positive integer")

    return config  # type: ignore[return-value]


def load_config(config_path: Optional[Path] = None) -> GaugeConfigDict:
    """Load configuration from specified path (or default path), auto-creating default config if file is missing."""
    target_path = (config_path or get_default_config_path()).resolve()

    if not target_path.exists():
        default_cfg = get_default_config()
        save_config(default_cfg, target_path)
        return default_cfg

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigError(f"Failed to parse JSON config file at {target_path}: {e}") from e
    except OSError as e:
        raise ConfigError(f"Failed to read config file at {target_path}: {e}") from e

    return validate_config(data)


def save_config(config: GaugeConfigDict, config_path: Optional[Path] = None) -> None:
    """Atomically write configuration dictionary to JSON file at specified path (or default path)."""
    target_path = (config_path or get_default_config_path()).resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)

    validated = validate_config(config)

    temp_fd, temp_path_str = tempfile.mkstemp(
        dir=str(target_path.parent), prefix="cfg_", suffix=".tmp"
    )
    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
            json.dump(validated, f, indent=2)
            f.write("\n")
        os.replace(temp_path_str, target_path)
    except Exception as e:
        if os.path.exists(temp_path_str):
            try:
                os.remove(temp_path_str)
            except OSError:
                pass
        raise ConfigError(f"Failed to save configuration to {target_path}: {e}") from e


def parse_cli_args(args: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse CLI options for theme, size, poll, opacity, topmost, config path, and reset flag."""
    parser = argparse.ArgumentParser(
        prog="boostgauge",
        description="Lightweight system tachometer with peak-hold needles",
    )
    parser.add_argument("--theme", choices=["dark", "light", "high_contrast"], help="Gauge visual theme")
    parser.add_argument("--size", type=int, help="Gauge window size in pixels (100-2000)")
    parser.add_argument("--poll", type=float, help="System monitoring polling interval in seconds")
    parser.add_argument("--opacity", type=float, help="Window opacity (0.1-1.0)")
    parser.add_argument(
        "--no-topmost",
        action="store_true",
        help="Disable always-on-top window behavior",
    )
    parser.add_argument("--config", type=str, help="Path to custom configuration JSON file")
    parser.add_argument(
        "--reset-config",
        action="store_true",
        help="Reset configuration file to default values",
    )

    return parser.parse_args(args)


def apply_cli_overrides(
    config: GaugeConfigDict, parsed_args: argparse.Namespace
) -> GaugeConfigDict:
    """Apply parsed CLI arguments as overrides on top of loaded configuration dictionary."""
    cfg = copy.deepcopy(config)

    if parsed_args.theme is not None:
        cfg["theme"] = parsed_args.theme

    if parsed_args.size is not None:
        cfg["size"] = parsed_args.size

    if parsed_args.poll is not None:
        cfg["polling_interval_seconds"] = parsed_args.poll

    if parsed_args.opacity is not None:
        cfg["opacity"] = parsed_args.opacity

    if parsed_args.no_topmost:
        cfg["always_on_top"] = False

    return validate_config(cfg)


def update_window_geometry(config: GaugeConfigDict, x: int, y: int, size: int) -> GaugeConfigDict:
    """Update window position and size parameters in configuration data structure prior to exit/save."""
    cfg = copy.deepcopy(config)
    cfg["position"]["x"] = x
    cfg["position"]["y"] = y
    cfg["size"] = size
    return validate_config(cfg)
```

---

### 6.3 `src/boostgauge/app.py` (Add)

**Complete file contents:**

```python
"""Application runtime controller for BoostGauge.

Issue #7: Configuration File and CLI Arguments
"""

from boostgauge.config import GaugeConfigDict


def run_app(config: GaugeConfigDict) -> None:
    """Run BoostGauge application runtime with the given configuration dictionary."""
    # Shell implementation for config integration phase
    _ = config
```

---

### 6.4 `src/boostgauge/__main__.py` (Add)

**Complete file contents:**

```python
"""CLI entry point for BoostGauge.

Issue #7: Configuration File and CLI Arguments
"""

import sys
from pathlib import Path
from typing import Optional

from boostgauge.app import run_app
from boostgauge.config import (
    ConfigError,
    apply_cli_overrides,
    get_default_config,
    get_default_config_path,
    load_config,
    parse_cli_args,
    save_config,
)


def main(args: Optional[list[str]] = None) -> int:
    """Execute main application setup, configuration load/overrides, and runtime startup."""
    try:
        parsed_args = parse_cli_args(args)
        target_path = (
            Path(parsed_args.config) if parsed_args.config else get_default_config_path()
        )

        if parsed_args.reset_config:
            config = get_default_config()
            save_config(config, target_path)
        else:
            config = load_config(target_path)

        config = apply_cli_overrides(config, parsed_args)
        run_app(config)
        return 0
    except ConfigError as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

---

### 6.5 `pyproject.toml` (Modify)

```diff
 [project.urls]
 Homepage = "https://boostgauge.martymcenroe.ai"
 Repository = "https://github.com/martymcenroe/boostgauge"
 Documentation = "https://github.com/martymcenroe/boostgauge/wiki"
 Issues = "https://github.com/martymcenroe/boostgauge/issues"
 "Built with AssemblyZero" = "https://github.com/martymcenroe/AssemblyZero"

+[project.scripts]
+boostgauge = "boostgauge.__main__:main"
+

 [build-system]
 requires = ["poetry-core>=2.0.0,<3.0.0"]
 build-backend = "poetry.core.masonry.api"
```

---

### 6.6 `tests/unit/test_config.py` (Add)

**Complete file contents:**

```python
"""Unit tests for configuration manager.

Issue #7: Configuration File and CLI Arguments
"""

import json
import os
import sys
from pathlib import Path

import pytest

from boostgauge.__main__ import main
from boostgauge.config import (
    ConfigError,
    apply_cli_overrides,
    get_default_config,
    get_default_config_path,
    load_config,
    parse_cli_args,
    save_config,
    update_window_geometry,
    validate_config,
)


def test_t010_config_auto_creation_on_first_run(tmp_path: Path) -> None:
    """T010: Test config auto-creation on first run when file does not exist."""
    cfg_file = tmp_path / "sub" / "config.json"
    assert not cfg_file.exists()

    config = load_config(cfg_file)

    assert cfg_file.exists()
    assert config["theme"] == "dark"
    assert config["size"] == 300
    assert config["polling_interval_seconds"] == 1.0

    # Verify saved disk content matches returned dict
    with open(cfg_file, "r", encoding="utf-8") as f:
        disk_data = json.load(f)
    assert disk_data == config


def test_t020_platform_path_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    """T020: Test platform path resolution for Windows and POSIX."""
    # Test Windows path resolution
    monkeypatch.setattr(sys, "platform", "win32")
    fake_appdata = Path("C:/Fake/AppData/Roaming")
    monkeypatch.setenv("APPDATA", str(fake_appdata))

    win_path = get_default_config_path()
    assert win_path == fake_appdata / "boostgauge" / "config.json"

    # Test POSIX path resolution
    monkeypatch.setattr(sys, "platform", "linux")
    posix_path = get_default_config_path()
    assert posix_path == Path.home() / ".boostgauge" / "config.json"


def test_t030_cli_options_override_config_file() -> None:
    """T030: Test CLI options override config file values."""
    base_config = get_default_config()
    parsed = parse_cli_args(["--theme", "light", "--size", "400", "--poll", "5.0"])

    overridden = apply_cli_overrides(base_config, parsed)

    assert overridden["theme"] == "light"
    assert overridden["size"] == 400
    assert overridden["polling_interval_seconds"] == 5.0
    assert overridden["opacity"] == 0.9  # Unchanged default


def test_t040_no_topmost_cli_flag_override() -> None:
    """T040: Test --no-topmost CLI flag overrides always_on_top to False."""
    base_config = get_default_config()
    assert base_config["always_on_top"] is True

    parsed = parse_cli_args(["--no-topmost"])
    overridden = apply_cli_overrides(base_config, parsed)

    assert overridden["always_on_top"] is False


def test_t050_custom_config_path_argument(tmp_path: Path) -> None:
    """T050: Test custom --config PATH CLI argument."""
    custom_dir = tmp_path / "custom_dir"
    custom_file = custom_dir / "custom_config.json"

    # Create custom config with specific theme
    custom_cfg = get_default_config()
    custom_cfg["theme"] = "high_contrast"
    save_config(custom_cfg, custom_file)

    parsed = parse_cli_args(["--config", str(custom_file)])
    target_path = Path(parsed.config) if parsed.config else get_default_config_path()

    loaded = load_config(target_path)
    assert target_path == custom_file.resolve()
    assert loaded["theme"] == "high_contrast"


def test_t060_reset_config_cli_option(tmp_path: Path) -> None:
    """T060: Test --reset-config CLI option overwrites target config with defaults."""
    cfg_file = tmp_path / "config.json"

    # Save modified custom config
    custom_cfg = get_default_config()
    custom_cfg["theme"] = "light"
    custom_cfg["size"] = 500
    save_config(custom_cfg, cfg_file)

    # Perform reset action via CLI entry point
    exit_code = main(["--config", str(cfg_file), "--reset-config"])
    assert exit_code == 0

    reloaded = load_config(cfg_file)
    assert reloaded["theme"] == "dark"
    assert reloaded["size"] == 300


def test_t070_window_position_and_size_update_and_save(tmp_path: Path) -> None:
    """T070: Test window position & size update and atomic save."""
    cfg_file = tmp_path / "config.json"
    initial_config = load_config(cfg_file)

    updated_config = update_window_geometry(initial_config, x=250, y=300, size=350)
    save_config(updated_config, cfg_file)

    persisted = load_config(cfg_file)
    assert persisted["position"]["x"] == 250
    assert persisted["position"]["y"] == 300
    assert persisted["size"] == 350


def test_t080_dynamic_in_memory_threshold_update() -> None:
    """T080: Test dynamic in-memory threshold update and validation."""
    config = get_default_config()
    config["thresholds"]["conpty"]["yellow"] = 30.0

    validated = validate_config(config)
    assert validated["thresholds"]["conpty"]["yellow"] == 30.0


def test_t090_invalid_json_config_file_error(tmp_path: Path) -> None:
    """T090: Test invalid JSON config file content raises ConfigError."""
    cfg_file = tmp_path / "corrupt.json"
    cfg_file.write_text("{ invalid_json: ", encoding="utf-8")

    with pytest.raises(ConfigError, match="Failed to parse JSON config file"):
        load_config(cfg_file)


def test_t100_out_of_bounds_numeric_config_parameters() -> None:
    """T100: Test out-of-bounds numeric config parameters raise ConfigError."""
    config = get_default_config()
    config["opacity"] = 1.5

    with pytest.raises(ConfigError, match="opacity must be a float between 0.1 and 1.0"):
        validate_config(config)

    config = get_default_config()
    config["polling_interval_seconds"] = -1.0
    with pytest.raises(ConfigError, match="polling_interval_seconds must be a positive number"):
        validate_config(config)


def test_t110_invalid_theme_validation_error() -> None:
    """T110: Test invalid theme name raises ConfigError."""
    config = get_default_config()
    config["theme"] = "neon_blue"

    with pytest.raises(ConfigError, match="Invalid theme 'neon_blue'"):
        validate_config(config)
```

## 7. Pattern References

### 7.1 Path & Test Setup Bootstrap Pattern

**File:** `tests/conftest.py` (lines 1-8)

```python
"""Project test bootstrap."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
```

**Relevance:** Standard project path resolution pattern using `pathlib.Path` objects to ensure platform-independent module imports and test execution.

---

### 7.2 Entry Point Packaging Specification

**File:** `pyproject.toml` (lines 1-44)

```toml
[project]
name = "boostgauge"
version = "0.1.0"
...
[build-system]
requires = ["poetry-core>=2.0.0,<3.0.0"]
build-backend = "poetry.core.masonry.api"
```

**Relevance:** PEP 621 compliant Poetry metadata standard defining project scripts and dependencies without third-party CLI runtime libraries.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `import argparse` | stdlib | `src/boostgauge/config.py` |
| `import copy` | stdlib | `src/boostgauge/config.py` |
| `import json` | stdlib | `src/boostgauge/config.py`, `tests/unit/test_config.py` |
| `import os` | stdlib | `src/boostgauge/config.py`, `tests/unit/test_config.py` |
| `import sys` | stdlib | `src/boostgauge/config.py`, `src/boostgauge/__main__.py`, `tests/unit/test_config.py` |
| `import tempfile` | stdlib | `src/boostgauge/config.py` |
| `from pathlib import Path` | stdlib | All modules |
| `from typing import Any, Dict, Optional, TypedDict` | stdlib | All modules |
| `from boostgauge.__main__ import main` | internal package | `tests/unit/test_config.py` |
| `import pytest` | dev-dependency | `tests/unit/test_config.py` |

**New Dependencies:** None (uses Python standard library).

## 9. Placeholder

*Reserved for future alignment with LLD section numbering.*

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `load_config()` | `config_path=Path("tmp/config.json")` (non-existent) | Default JSON written to disk; `GaugeConfigDict` returned matching defaults |
| T020 | `get_default_config_path()` | `sys.platform="win32"` & `APPDATA` env / POSIX platform | Windows: `Path(APPDATA)/boostgauge/config.json`; POSIX: `Path.home()/.boostgauge/config.json` |
| T030 | `apply_cli_overrides()` | `args=["--theme", "light", "--size", "400", "--poll", "5.0"]` | `GaugeConfigDict` with theme="light", size=400, polling_interval_seconds=5.0 |
| T040 | `apply_cli_overrides()` | `args=["--no-topmost"]` | `GaugeConfigDict` with always_on_top=False |
| T050 | `parse_cli_args()` / `load_config()` | `args=["--config", "/custom/path.json"]` | Target path resolved to `/custom/path.json` |
| T060 | `main()` / `parse_cli_args()` | `--reset-config` execution flow | Overwrites config file with default JSON structure |
| T070 | `update_window_geometry()` & `save_config()` | `x=250, y=300, size=350` | Saved JSON contains `"position": {"x": 250, "y": 300}` and `"size": 350` |
| T080 | `validate_config()` | `config["thresholds"]["conpty"]["yellow"] = 30.0` | Validates in memory immediately, returns updated dict |
| T090 | `load_config()` | File with invalid JSON syntax | Raises `ConfigError("Failed to parse JSON config file...")` |
| T100 | `validate_config()` | `opacity=1.5` or `polling_interval_seconds=-1.0` | Raises `ConfigError` with out-of-bounds parameter message |
| T110 | `validate_config()` | `theme="neon_blue"` | Raises `ConfigError("Invalid theme 'neon_blue'...")` |

## 11. Implementation Notes

### 11.1 Error Handling Convention
- All configuration validation errors, file I/O exceptions, and syntax failures raise `ConfigError`.
- CLI entry point `__main__.py:main` catches `ConfigError`, prints `Error: <msg>` to `sys.stderr`, and returns exit code `1`.

### 11.2 Atomic Disk Writes
- `save_config()` writes formatted JSON to a temporary file (`cfg_*.tmp`) in the destination directory using `tempfile.mkstemp` and `os.fdopen`.
- Renames temporary file to target path using `os.replace` to guarantee atomic file write on POSIX and Windows filesystem architectures.

### 11.3 Validation Bounds & Constants

| Constant / Parameter | Valid Range / Allowed Values | Default Value |
|----------------------|------------------------------|---------------|
| `polling_interval_seconds` | `float > 0.0` | `1.0` |
| `theme` | `"dark"`, `"light"`, `"high_contrast"` | `"dark"` |
| `size` | `100 <= int <= 2000` | `300` |
| `opacity` | `0.1 <= float <= 1.0` | `0.9` |
| `always_on_top` | `bool` | `True` |
| `thresholds.<metric>.yellow` | `float >= 0.0`, `yellow < red` | Variable per metric |
| `thresholds.<metric>.red` | `float >= 0.0`, `red > yellow` | Variable per metric |

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
| Date | 2026-07-31 |
| Iterations | 1 |
| Finalized | 2026-07-31T01:45:52Z |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #7 |
| Verdict | APPROVED |
| Date | 2026-07-31 |
| Iterations | 2 |
| Finalized | 2026-07-31T06:47:15Z |

### Review Feedback Summary

The revised implementation spec is complete, fully concrete, and directly executable by an AI agent. The revisions successfully address prior feedback by invoking the main() CLI entry point in test_t060 to verify --reset-config execution end-to-end. Every test assertion traces directly to specified requirements, concrete code excerpts are provided for all files, data structures have complete JSON examples, and standard library implementations follow project architecture and platform conventions.
