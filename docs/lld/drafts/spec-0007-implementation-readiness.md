# Implementation Spec: Feature: Configuration File and CLI Arguments

| Field | Value |
|-------|-------|
| Issue | #7 |
| LLD | `docs/lld/done/0007-config-cli.md` |
| Generated | 2026-07-31 |
| Status | APPROVED |

---

## 1. Overview

This implementation specification defines the design and code changes required to implement a robust, cross-platform configuration and CLI argument management system for BoostGauge. It establishes persistent user preferences via standard OS paths, dynamic CLI flag overrides, schema validation, and atomic window geometry updates on application exit.

**Objective:** Implement a robust configuration management system for BoostGauge that provides persistent settings storage in standard OS user paths, CLI argument parsing with config file override semantics, dynamic threshold updates, and window position/size state persistence on exit.

**Success Criteria:**
- Configuration file is automatically initialized with defaults in `%APPDATA%/boostgauge/config.json` (Windows) or `~/.boostgauge/config.json` (POSIX) if missing.
- CLI flags (`--theme`, `--size`, `--poll`, `--opacity`, `--no-topmost`, `--config`, `--reset-config`) override loaded configuration file settings cleanly without persisting CLI overrides back to disk.
- Window geometry updates `(x, y, size)` are saved atomically to disk on shutdown.
- Invalid configuration structures, types, missing fields, or out-of-bound numerical values raise descriptive `ConfigError` exceptions.
- Test suite achieves ≥95% branch coverage following Option C (off-screen rendering, zero `tkinter.Tk()` instantiation).

---

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `pyproject.toml` | Modify | Define `boostgauge` CLI script entry point under `[tool.poetry.scripts]` |
| 2 | `src/boostgauge/__init__.py` | Add | Package initialization file defining package version (`__version__ = "0.1.0"`) and public exports |
| 3 | `src/boostgauge/config.py` | Add | Configuration manager implementing schema validation, path resolution, atomic file persistence, CLI parsing, and override logic |
| 4 | `src/boostgauge/app.py` | Add | Application runtime controller stub managing lifecycle and geometry persistence |
| 5 | `src/boostgauge/__main__.py` | Add | Main executable entry point handling CLI argument parsing and application bootstrap |
| 6 | `tests/unit/test_config.py` | Add | Comprehensive unit test suite for configuration resolution, validation, CLI overrides, atomic saving, and reset logic |

**Implementation Order Rationale:**
1. Update `pyproject.toml` to register the package entry point.
2. Initialize `__init__.py` to establish package metadata.
3. Build core logic in `config.py` as it has zero internal dependencies.
4. Implement `app.py` runtime controller consuming `config.py`.
5. Implement `__main__.py` entry point calling `config.py` and `app.py`.
6. Add unit tests in `tests/unit/test_config.py` to validate all configuration and CLI scenarios.

---

## 3. Current State (for Modify/Delete files)

### 3.1 `pyproject.toml`

**Relevant excerpt** (lines 19-33):

```toml
[build-system]
requires = ["poetry-core>=2.0.0,<3.0.0"]
build-backend = "poetry.core.masonry.api"

[dependency-groups]
dev = [
    "pytest (>=9.0.3,<10.0.0)",
    "pytest-cov (>=7.1.0,<8.0.0)"
]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
# importlib mode: the tiered test tree (unit/visual/integration) may reuse
# basenames like test_gauge.py; default prepend mode dies at collection on
# the first duplicate (#129 — killed pipeline phase 3 three times).
addopts = "-ra --strict-markers --import-mode=importlib"
```

**What changes:**
Add `[tool.poetry.scripts]` table defining `boostgauge = "boostgauge.__main__:main"`.

---

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
    "yellow": 70.0,
    "red": 90.0
}
```

---

### 4.2 `MetricThresholds`

**Definition:**

```python
class MetricThresholds(TypedDict):
    conpty: Threshold
    memory_percent: Threshold
    process_count: Threshold
    handle_count: Threshold
```

**Concrete Example:**

```json
{
    "conpty": {"yellow": 10.0, "red": 20.0},
    "memory_percent": {"yellow": 75.0, "red": 90.0},
    "process_count": {"yellow": 50.0, "red": 100.0},
    "handle_count": {"yellow": 1000.0, "red": 5000.0}
}
```

---

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

---

### 4.4 `TelltaleWindows`

**Definition:**

```python
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

---

### 4.5 `GaugeConfigDict`

**Definition:**

```python
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
        "conpty": {"yellow": 8.0, "red": 16.0},
        "memory_percent": {"yellow": 75.0, "red": 90.0},
        "process_count": {"yellow": 50.0, "red": 100.0},
        "handle_count": {"yellow": 1000.0, "red": 5000.0}
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

---

## 5. Function Specifications

### 5.1 `get_default_config_path()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def get_default_config_path() -> Path:
    """Return platform-specific default config path.

    %APPDATA%/boostgauge/config.json on Windows, ~/.boostgauge/config.json on POSIX.
    """
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
- Windows missing `APPDATA` env var: Fall back to `Path.home() / "AppData" / "Roaming" / "boostgauge" / "config.json"`.

---

### 5.2 `get_default_config()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def get_default_config() -> GaugeConfigDict:
    """Return a deep copy of the default configuration dictionary."""
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
        "conpty": {"yellow": 8.0, "red": 16.0},
        "memory_percent": {"yellow": 75.0, "red": 90.0},
        "process_count": {"yellow": 50.0, "red": 100.0},
        "handle_count": {"yellow": 1000.0, "red": 5000.0},
    },
    "telltale_windows": {"short": 60, "medium": 600, "long": 3600},
    "show_driver_label": True,
    "show_digital_readout": True,
    "show_session_count": True,
}
```

---

### 5.3 `validate_config()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def validate_config(config: Dict[str, Any]) -> GaugeConfigDict:
    """Validate keys, types, and numerical bounds of a config dictionary.

    Returns a typed GaugeConfigDict or raises ConfigError.
    """
    ...
```

**Input Example:**

```python
config_data = {
    "polling_interval_seconds": 0.5,
    "theme": "neon",
    "size": 400,
    "opacity": 0.85,
    "always_on_top": False,
    "position": {"x": 50, "y": 50},
    "thresholds": {
        "conpty": {"yellow": 5.0, "red": 10.0},
        "memory_percent": {"yellow": 70.0, "red": 85.0},
        "process_count": {"yellow": 40.0, "red": 80.0},
        "handle_count": {"yellow": 500.0, "red": 2000.0},
    },
    "telltale_windows": {"short": 30, "medium": 300, "long": 1800},
    "show_driver_label": True,
    "show_digital_readout": True,
    "show_session_count": False,
}
```

**Output Example:**
Returns exact input dictionary typed as `GaugeConfigDict`.

**Edge Cases:**
- `config["opacity"] = 1.5` -> raises `ConfigError("Invalid 'opacity': 1.5. Must be between 0.1 and 1.0.")`
- `config["size"] = 50` -> raises `ConfigError("Invalid 'size': 50. Must be between 100 and 2000.")`
- `config["theme"] = "invalid_theme"` -> raises `ConfigError("Invalid 'theme': invalid_theme. Must be one of ['dark', 'light', 'neon', 'classic'].")`
- Missing key `"thresholds"` -> raises `ConfigError("Missing required config key: 'thresholds'.")`

---

### 5.4 `load_config_file()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def load_config_file(path: Path) -> GaugeConfigDict:
    """Load configuration from specified JSON file path.

    Creates file with defaults if missing, or raises ConfigError if invalid.
    """
    ...
```

**Input Example:**

```python
path = Path("/tmp/test_config/config.json")
```

**Output Example:**
Returns validated `GaugeConfigDict`.

**Edge Cases:**
- File does not exist -> creates parent directories, writes `get_default_config()`, returns default config.
- File contains invalid JSON (`{ invalid json `) -> raises `ConfigError("Malformed JSON in configuration file: ...")`.
- Permission denied writing/reading -> raises `ConfigError("Permission denied accessing config file: ...")`.

---

### 5.5 `save_config_file()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def save_config_file(config: GaugeConfigDict, path: Path) -> None:
    """Atomically write configuration dictionary as formatted JSON to path."""
    ...
```

**Input Example:**

```python
config = get_default_config()
path = Path("/tmp/test_config/config.json")
```

**Output Example:**
Returns `None`. File created on disk containing formatted JSON.

**Edge Cases:**
- Target parent directory does not exist -> automatically creates parent directories (`path.parent.mkdir(parents=True, exist_ok=True)`).
- Crash during save -> Uses atomic write (`NamedTemporaryFile` + `os.replace`) to ensure no corrupted partial writes occur.

---

### 5.6 `create_cli_parser()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def create_cli_parser() -> argparse.ArgumentParser:
    """Construct and return the ArgumentParser configured for BoostGauge CLI flags."""
    ...
```

**Input Example:**
None.

**Output Example:**
Returns `argparse.ArgumentParser` instance configured with `--theme`, `--size`, `--poll`, `--opacity`, `--no-topmost`, `--config`, and `--reset-config`.

---

### 5.7 `parse_cli_args()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def parse_cli_args(args: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments from given list or sys.argv."""
    ...
```

**Input Example:**

```python
args = ["--theme", "neon", "--poll", "2.0"]
```

**Output Example:**

```python
argparse.Namespace(
    theme="neon",
    size=None,
    poll=2.0,
    opacity=None,
    no_topmost=False,
    config=None,
    reset_config=False,
)
```

---

### 5.8 `merge_cli_overrides()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def merge_cli_overrides(config: GaugeConfigDict, cli_args: argparse.Namespace) -> GaugeConfigDict:
    """Apply non-None CLI options onto configuration dictionary, overriding file settings."""
    ...
```

**Input Example:**

```python
config = get_default_config()
cli_args = argparse.Namespace(
    theme="light",
    size=500,
    poll=0.5,
    opacity=0.8,
    no_topmost=True,
    config=None,
    reset_config=False,
)
```

**Output Example:**

```python
# Modified deep copy of config:
# config["theme"] == "light"
# config["size"] == 500
# config["polling_interval_seconds"] == 0.5
# config["opacity"] == 0.8
# config["always_on_top"] == False
```

**Edge Cases:**
- `cli_args.theme` invalid string -> raises `ConfigError` via `validate_config()`.

---

### 5.9 `load_effective_config()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def load_effective_config(args: Optional[list[str]] = None) -> Tuple[GaugeConfigDict, Path]:
    """Execute complete configuration pipeline: parse CLI args, load/create config file, apply CLI overrides."""
    ...
```

**Input Example:**

```python
args = ["--config", "/tmp/my_config.json", "--theme", "neon"]
```

**Output Example:**

```python
(
    effective_config,  # GaugeConfigDict with theme="neon"
    Path("/tmp/my_config.json")
)
```

**Edge Cases:**
- `--reset-config` present -> Overwrites target config path with `get_default_config()` on disk, returns default config and target path.

---

### 5.10 `update_window_geometry()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def update_window_geometry(
    config: GaugeConfigDict,
    path: Path,
    x: int,
    y: int,
    size: int,
) -> GaugeConfigDict:
    """Update position and size in configuration dictionary and atomically save to file on disk."""
    ...
```

**Input Example:**

```python
config = get_default_config()
path = Path("/tmp/config.json")
x = 250
y = 300
size = 400
```

**Output Example:**
Returns updated `GaugeConfigDict` where `config["position"] == {"x": 250, "y": 300}` and `config["size"] == 400`. Saves updated configuration to `path` atomically.

---

## 6. Change Instructions

### 6.1 `pyproject.toml` (Modify)

**Change:** Add `[tool.poetry.scripts]` entry point.

```diff
 [dependency-groups]
 dev = [
     "pytest (>=9.0.3,<10.0.0)",
     "pytest-cov (>=7.1.0,<8.0.0)"
 ]
 
+[tool.poetry.scripts]
+boostgauge = "boostgauge.__main__:main"
+
 [tool.pytest.ini_options]
 testpaths = ["tests"]
 python_files = ["test_*.py"]
```

---

### 6.2 `src/boostgauge/__init__.py` (Add)

**Complete file contents:**

```python
"""BoostGauge package initialization.

Issue #7: Configuration File and CLI Arguments
"""

__version__ = "0.1.0"
__all__ = ["__version__"]
```

---

### 6.3 `src/boostgauge/config.py` (Add)

**Complete file contents:**

```python
"""Configuration management system for BoostGauge.

Issue #7: Configuration File and CLI Arguments
Provides path resolution, schema validation, atomic JSON persistence,
CLI argument parsing, and override semantics.
"""

import argparse
import copy
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, TypedDict


class ConfigError(Exception):
    """Raised when configuration parsing, validation, or path resolution fails."""
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


VALID_THEMES = {"dark", "light", "neon", "classic"}


def get_default_config_path() -> Path:
    """Return platform-specific default config path.

    %APPDATA%/boostgauge/config.json on Windows, ~/.boostgauge/config.json on POSIX.
    """
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            base_dir = Path(appdata)
        else:
            base_dir = Path.home() / "AppData" / "Roaming"
        return base_dir / "boostgauge" / "config.json"
    else:
        return Path.home() / ".boostgauge" / "config.json"


def get_default_config() -> GaugeConfigDict:
    """Return a deep copy of default GaugeConfigDict."""
    return {
        "polling_interval_seconds": 1.0,
        "theme": "dark",
        "size": 300,
        "opacity": 0.9,
        "always_on_top": True,
        "position": {"x": 100, "y": 100},
        "thresholds": {
            "conpty": {"yellow": 8.0, "red": 16.0},
            "memory_percent": {"yellow": 75.0, "red": 90.0},
            "process_count": {"yellow": 50.0, "red": 100.0},
            "handle_count": {"yellow": 1000.0, "red": 5000.0},
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


def validate_config(config: Dict[str, Any]) -> GaugeConfigDict:
    """Validate keys, types, and numerical bounds of a configuration dictionary."""
    if not isinstance(config, dict):
        raise ConfigError("Configuration root must be a JSON object.")

    defaults = get_default_config()
    required_keys = set(defaults.keys())
    missing_keys = required_keys - set(config.keys())
    if missing_keys:
        raise ConfigError(f"Missing required config key: '{sorted(list(missing_keys))[0]}'.")

    # Validate poll interval
    poll = config.get("polling_interval_seconds")
    if not isinstance(poll, (int, float)) or isinstance(poll, bool) or poll < 0.1:
        raise ConfigError(f"Invalid 'polling_interval_seconds': {poll}. Must be a float >= 0.1.")

    # Validate theme
    theme = config.get("theme")
    if not isinstance(theme, str) or theme not in VALID_THEMES:
        raise ConfigError(f"Invalid 'theme': {theme}. Must be one of {sorted(list(VALID_THEMES))}.")

    # Validate size
    size = config.get("size")
    if not isinstance(size, int) or isinstance(size, bool) or not (100 <= size <= 2000):
        raise ConfigError(f"Invalid 'size': {size}. Must be an integer between 100 and 2000.")

    # Validate opacity
    opacity = config.get("opacity")
    if not isinstance(opacity, (int, float)) or isinstance(opacity, bool) or not (0.1 <= opacity <= 1.0):
        raise ConfigError(f"Invalid 'opacity': {opacity}. Must be between 0.1 and 1.0.")

    # Validate boolean flags
    for bool_key in ("always_on_top", "show_driver_label", "show_digital_readout", "show_session_count"):
        val = config.get(bool_key)
        if not isinstance(val, bool):
            raise ConfigError(f"Invalid '{bool_key}': {val}. Must be a boolean.")

    # Validate position
    pos = config.get("position")
    if not isinstance(pos, dict) or "x" not in pos or "y" not in pos:
        raise ConfigError("Invalid 'position': must be an object with integer 'x' and 'y' properties.")
    if not isinstance(pos["x"], int) or isinstance(pos["x"], bool) or not isinstance(pos["y"], int) or isinstance(pos["y"], bool):
        raise ConfigError("Invalid 'position': 'x' and 'y' must be integers.")

    # Validate thresholds
    thresholds = config.get("thresholds")
    if not isinstance(thresholds, dict):
        raise ConfigError("Invalid 'thresholds': must be a JSON object.")

    for m_key in ("conpty", "memory_percent", "process_count", "handle_count"):
        if m_key not in thresholds or not isinstance(thresholds[m_key], dict):
            raise ConfigError(f"Invalid threshold metric configuration for '{m_key}'.")
        t_dict = thresholds[m_key]
        if "yellow" not in t_dict or "red" not in t_dict:
            raise ConfigError(f"Threshold for '{m_key}' must specify 'yellow' and 'red' values.")
        y_val, r_val = t_dict["yellow"], t_dict["red"]
        if not isinstance(y_val, (int, float)) or isinstance(y_val, bool) or not isinstance(r_val, (int, float)) or isinstance(r_val, bool):
            raise ConfigError(f"Threshold values for '{m_key}' must be numeric.")
        if y_val >= r_val:
            raise ConfigError(f"Threshold 'yellow' ({y_val}) must be strictly less than 'red' ({r_val}) for '{m_key}'.")

    # Validate telltale windows
    tt_windows = config.get("telltale_windows")
    if not isinstance(tt_windows, dict):
        raise ConfigError("Invalid 'telltale_windows': must be a JSON object.")
    for w_key in ("short", "medium", "long"):
        val = tt_windows.get(w_key)
        if not isinstance(val, int) or isinstance(val, bool) or val <= 0:
            raise ConfigError(f"Invalid telltale window for '{w_key}': must be a positive integer.")

    return config  # type: ignore[return-value]


def load_config_file(path: Path) -> GaugeConfigDict:
    """Load configuration from specified JSON file path; creates defaults if missing."""
    if not path.exists():
        default_cfg = get_default_config()
        save_config_file(default_cfg, path)
        return default_cfg

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Malformed JSON in config file '{path}': {exc}") from exc
    except PermissionError as exc:
        raise ConfigError(f"Permission denied accessing config file '{path}': {exc}") from exc
    except Exception as exc:
        raise ConfigError(f"Failed to read config file '{path}': {exc}") from exc

    return validate_config(data)


def save_config_file(config: GaugeConfigDict, path: Path) -> None:
    """Atomically write configuration dictionary as formatted JSON to path."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Create temp file in same directory for atomic replace across filesystems
        with tempfile.NamedTemporaryFile("w", dir=str(path.parent), delete=False, encoding="utf-8") as tf:
            json.dump(config, tf, indent=4)
            temp_name = tf.name

        os.replace(temp_name, str(path))
    except Exception as exc:
        if 'temp_name' in locals() and os.path.exists(temp_name):
            try:
                os.remove(temp_name)
            except OSError:
                pass
        raise ConfigError(f"Failed to save configuration to '{path}': {exc}") from exc


def create_cli_parser() -> argparse.ArgumentParser:
    """Construct ArgumentParser for BoostGauge CLI flags."""
    parser = argparse.ArgumentParser(
        prog="boostgauge",
        description="Lightweight system tachometer with peak-hold needles for monitoring AI agent resource pressure.",
    )
    parser.add_argument("--theme", choices=sorted(list(VALID_THEMES)), help="Set UI color theme.")
    parser.add_argument("--size", type=int, help="Gauge window size in pixels (100-2000).")
    parser.add_argument("--poll", type=float, help="Polling interval in seconds (>= 0.1).")
    parser.add_argument("--opacity", type=float, help="Window opacity (0.1-1.0).")
    parser.add_argument("--no-topmost", action="store_true", help="Disable always-on-top window behavior.")
    parser.add_argument("--config", type=str, help="Path to custom JSON configuration file.")
    parser.add_argument("--reset-config", action="store_true", help="Reset configuration file to default settings.")
    return parser


def parse_cli_args(args: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments from given list or sys.argv."""
    parser = create_cli_parser()
    return parser.parse_args(args)


def merge_cli_overrides(config: GaugeConfigDict, cli_args: argparse.Namespace) -> GaugeConfigDict:
    """Apply non-None CLI options onto configuration dictionary."""
    merged = copy.deepcopy(config)

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

    return validate_config(merged)


def load_effective_config(args: Optional[list[str]] = None) -> Tuple[GaugeConfigDict, Path]:
    """Execute complete configuration loading pipeline."""
    cli_args = parse_cli_args(args)

    if cli_args.config:
        config_path = Path(cli_args.config).resolve()
    else:
        config_path = get_default_config_path()

    if cli_args.reset_config:
        default_cfg = get_default_config()
        save_config_file(default_cfg, config_path)
        effective = merge_cli_overrides(default_cfg, cli_args)
        return effective, config_path

    file_config = load_config_file(config_path)
    effective_config = merge_cli_overrides(file_config, cli_args)
    return effective_config, config_path


def update_window_geometry(
    config: GaugeConfigDict,
    path: Path,
    x: int,
    y: int,
    size: int,
) -> GaugeConfigDict:
    """Update window position and size in config dict and save atomically to disk."""
    updated = copy.deepcopy(config)
    updated["position"] = {"x": x, "y": y}
    updated["size"] = size
    validated = validate_config(updated)
    save_config_file(validated, path)
    return validated
```

---

### 6.4 `src/boostgauge/app.py` (Add)

**Complete file contents:**

```python
"""Application runtime controller integration for BoostGauge.

Issue #7: Configuration File and CLI Arguments
Integrates configuration lifecycle with window manager and metric polling.
"""

from pathlib import Path
from typing import Optional

from boostgauge.config import GaugeConfigDict, update_window_geometry


class BoostGaugeApp:
    """Application lifecycle controller."""

    def __init__(self, config: GaugeConfigDict, config_path: Path) -> None:
        self.config = config
        self.config_path = config_path
        self._is_running = False

    def run(self) -> int:
        """Start the application event loop (stub for CLI main entry)."""
        self._is_running = True
        return 0

    def shutdown(self, current_x: Optional[int] = None, current_y: Optional[int] = None, current_size: Optional[int] = None) -> None:
        """Persist final window position and size on application exit."""
        x = current_x if current_x is not None else self.config["position"]["x"]
        y = current_y if current_y is not None else self.config["position"]["y"]
        size = current_size if current_size is not None else self.config["size"]

        self.config = update_window_geometry(self.config, self.config_path, x, y, size)
        self._is_running = False
```

---

### 6.5 `src/boostgauge/__main__.py` (Add)

**Complete file contents:**

```python
"""Main entry point execution for boostgauge CLI script.

Issue #7: Configuration File and CLI Arguments
"""

import sys
from typing import Optional

from boostgauge.app import BoostGaugeApp
from boostgauge.config import ConfigError, load_effective_config


def main(args: Optional[list[str]] = None) -> int:
    """Bootstrap BoostGauge application from CLI arguments."""
    try:
        config, config_path = load_effective_config(args)
    except ConfigError as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1
    except Exception as err:
        print(f"Unexpected error initializing configuration: {err}", file=sys.stderr)
        return 1

    app = BoostGaugeApp(config, config_path)
    return app.run()


if __name__ == "__main__":
    sys.exit(main())
```

---

### 6.6 `tests/unit/test_config.py` (Add)

**Complete file contents:**

```python
"""Unit test suite for configuration file resolution, validation, CLI overrides, and geometry persistence.

Issue #7: Configuration File and CLI Arguments
Option C compliant: No GUI/tkinter initialization.
"""

import json
from pathlib import Path
import pytest

from boostgauge.config import (
    ConfigError,
    get_default_config,
    get_default_config_path,
    load_config_file,
    load_effective_config,
    merge_cli_overrides,
    parse_cli_args,
    save_config_file,
    update_window_geometry,
    validate_config,
)
from boostgauge.app import BoostGaugeApp
from boostgauge.__main__ import main


def test_default_config_path_resolution(monkeypatch):
    """T020: Resolution returns valid platform-specific path structure."""
    # Test Windows mock
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setenv("APPDATA", r"C:\Users\test\AppData\Roaming")
    win_path = get_default_config_path()
    assert win_path == Path(r"C:\Users\test\AppData\Roaming") / "boostgauge" / "config.json"

    # Test POSIX mock
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr(Path, "home", lambda: Path("/home/test"))
    posix_path = get_default_config_path()
    assert posix_path == Path("/home/test") / ".boostgauge" / "config.json"


def test_default_config_creation_on_missing_file(tmp_path):
    """T010: Missing file is created automatically with default schema."""
    config_file = tmp_path / "sub" / "config.json"
    assert not config_file.exists()

    cfg = load_config_file(config_file)
    assert config_file.exists()
    assert cfg == get_default_config()

    with open(config_file, "r", encoding="utf-8") as f:
        on_disk = json.load(f)
    assert on_disk["theme"] == "dark"
    assert on_disk["size"] == 300


def test_cli_options_override_file(tmp_path):
    """T030: CLI flags override configuration file settings in effective config."""
    config_file = tmp_path / "config.json"
    default_cfg = get_default_config()
    default_cfg["theme"] = "dark"
    default_cfg["size"] = 300
    save_config_file(default_cfg, config_file)

    cli_input = ["--config", str(config_file), "--theme", "neon", "--poll", "0.5", "--no-topmost"]
    effective_cfg, path = load_effective_config(cli_input)

    assert path == config_file
    assert effective_cfg["theme"] == "neon"
    assert effective_cfg["polling_interval_seconds"] == 0.5
    assert effective_cfg["always_on_top"] is False
    # Verify file on disk was NOT mutated by runtime CLI overrides
    on_disk_cfg = load_config_file(config_file)
    assert on_disk_cfg["theme"] == "dark"


def test_custom_config_path_via_cli(tmp_path):
    """T040: Specifies custom config path via --config flag."""
    custom_dir = tmp_path / "custom_dir"
    custom_file = custom_dir / "custom_config.json"
    cli_input = ["--config", str(custom_file)]

    effective_cfg, path = load_effective_config(cli_input)
    assert path.resolve() == custom_file.resolve()
    assert custom_file.exists()
    assert effective_cfg == get_default_config()


def test_save_and_restore_geometry(tmp_path):
    """T050, T060: Geometry persistence on update and restoration on startup."""
    config_file = tmp_path / "config.json"
    cfg = get_default_config()
    save_config_file(cfg, config_file)

    # Save new geometry (T050)
    updated_cfg = update_window_geometry(cfg, config_file, x=250, y=350, size=500)
    assert updated_cfg["position"]["x"] == 250
    assert updated_cfg["position"]["y"] == 350
    assert updated_cfg["size"] == 500

    # Restore geometry on load (T060)
    restored_cfg, _ = load_effective_config(["--config", str(config_file)])
    assert restored_cfg["position"] == {"x": 250, "y": 350}
    assert restored_cfg["size"] == 500


def test_dynamic_threshold_updates(tmp_path):
    """T070: Threshold updates take effect dynamically in memory and validate correctly."""
    cfg = get_default_config()
    cfg["thresholds"]["conpty"]["yellow"] = 12.0
    cfg["thresholds"]["conpty"]["red"] = 25.0

    validated = validate_config(cfg)
    assert validated["thresholds"]["conpty"]["yellow"] == 12.0
    assert validated["thresholds"]["conpty"]["red"] == 25.0


def test_validation_invalid_bounds():
    """T080: Out of bounds numerical values raise ConfigError."""
    cfg = get_default_config()
    cfg["opacity"] = 1.5
    with pytest.raises(ConfigError, match="Invalid 'opacity'"):
        validate_config(cfg)

    cfg = get_default_config()
    cfg["size"] = 50
    with pytest.raises(ConfigError, match="Invalid 'size'"):
        validate_config(cfg)

    cfg = get_default_config()
    cfg["polling_interval_seconds"] = 0.05
    with pytest.raises(ConfigError, match="Invalid 'polling_interval_seconds'"):
        validate_config(cfg)

    cfg = get_default_config()
    cfg["theme"] = "unknown_theme"
    with pytest.raises(ConfigError, match="Invalid 'theme'"):
        validate_config(cfg)

    cfg = get_default_config()
    cfg["thresholds"]["memory_percent"]["yellow"] = 95.0
    cfg["thresholds"]["memory_percent"]["red"] = 80.0
    with pytest.raises(ConfigError, match="must be strictly less than"):
        validate_config(cfg)


def test_malformed_json_error(tmp_path):
    """T090: Malformed JSON triggers descriptive ConfigError."""
    config_file = tmp_path / "malformed.json"
    config_file.write_text("{ invalid json: ", encoding="utf-8")

    with pytest.raises(ConfigError, match="Malformed JSON"):
        load_config_file(config_file)


def test_reset_config_cli_option(tmp_path):
    """T100: --reset-config flag resets configuration file to defaults."""
    config_file = tmp_path / "config.json"
    custom_cfg = get_default_config()
    custom_cfg["theme"] = "neon"
    custom_cfg["size"] = 800
    save_config_file(custom_cfg, config_file)

    assert load_config_file(config_file)["theme"] == "neon"

    effective_cfg, path = load_effective_config(["--config", str(config_file), "--reset-config"])
    assert path == config_file
    assert effective_cfg["theme"] == "dark"
    assert effective_cfg["size"] == 300

    on_disk = load_config_file(config_file)
    assert on_disk["theme"] == "dark"
    assert on_disk["size"] == 300


def test_main_entry_point_error_exit(tmp_path, capsys):
    """Test main entry point returns 1 on ConfigError."""
    config_file = tmp_path / "corrupt.json"
    config_file.write_text("{ corrupt ", encoding="utf-8")

    exit_code = main(["--config", str(config_file)])
    assert exit_code == 1

    captured = capsys.readouterr()
    assert "Error: Malformed JSON" in captured.err


def test_app_shutdown_persists_geometry(tmp_path):
    """Test BoostGaugeApp shutdown persists window geometry."""
    config_file = tmp_path / "config.json"
    cfg, path = load_effective_config(["--config", str(config_file)])
    app = BoostGaugeApp(cfg, path)
    app.run()
    assert app._is_running is True

    app.shutdown(current_x=300, current_y=400, current_size=600)
    assert app._is_running is False

    disk_cfg = load_config_file(config_file)
    assert disk_cfg["position"] == {"x": 300, "y": 400}
    assert disk_cfg["size"] == 600
```

---

## 7. Pattern References

### 7.1 Standard Library Atomic File Replace

**File:** Standard Python library `tempfile` and `os.replace`

```python
with tempfile.NamedTemporaryFile("w", dir=str(path.parent), delete=False, encoding="utf-8") as tf:
    json.dump(config, tf, indent=4)
    temp_name = tf.name
os.replace(temp_name, str(path))
```

**Relevance:** Prevents configuration file corruption during crash or unexpected process exit while updating window geometry on shutdown.

---

### 7.2 Strategy & Layered Override Pattern

**File:** `src/boostgauge/config.py` (lines 200-245)

```python
def load_effective_config(args: Optional[list[str]] = None) -> Tuple[GaugeConfigDict, Path]:
    file_config = load_config_file(config_path)
    effective_config = merge_cli_overrides(file_config, cli_args)
    return effective_config, config_path
```

**Relevance:** Ensures precedence order: Default Values -> Disk Config File -> CLI Arguments Override.

---

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `import argparse` | stdlib | `src/boostgauge/config.py` |
| `import copy` | stdlib | `src/boostgauge/config.py` |
| `import json` | stdlib | `src/boostgauge/config.py`, `tests/unit/test_config.py` |
| `import os` | stdlib | `src/boostgauge/config.py` |
| `import sys` | stdlib | `src/boostgauge/config.py`, `src/boostgauge/__main__.py` |
| `import tempfile` | stdlib | `src/boostgauge/config.py` |
| `from pathlib import Path` | stdlib | `src/boostgauge/config.py`, `src/boostgauge/app.py`, `tests/unit/test_config.py` |
| `from typing import Any, Dict, Optional, Tuple, TypedDict` | stdlib | `src/boostgauge/config.py`, `src/boostgauge/app.py`, `src/boostgauge/__main__.py` |
| `import pytest` | dev-dependency | `tests/unit/test_config.py` |

**New Dependencies:** None (uses standard library modules exclusively).

---

## 9. Placeholder

*Reserved for alignment with LLD section numbering.*

---

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `load_config_file()` | Non-existent path | File created with default JSON schema, returns `get_default_config()` |
| T020 | `get_default_config_path()` | `sys.platform == 'win32'` vs `'linux'` | Returns Path matching `APPDATA/boostgauge/config.json` or `~/.boostgauge/config.json` |
| T030 | `load_effective_config()` | `--theme neon --poll 0.5 --no-topmost` | Effective config updated; disk file unchanged |
| T040 | `load_effective_config()` | `--config custom.json` | Path resolved to `custom.json`; config loaded/created there |
| T050 | `update_window_geometry()` | `x=250, y=350, size=500` | Config updated in memory & saved atomically to JSON file on disk |
| T060 | `load_effective_config()` | Path with saved geometry | Returns config containing restored `x=250, y=350, size=500` |
| T070 | `validate_config()` | Updated `thresholds` dict | Returns validated config dict containing updated thresholds |
| T080 | `validate_config()` | Invalid bounds (`opacity=1.5`, `size=50`) | Raises `ConfigError` detailing validation failure |
| T090 | `load_config_file()` | Path containing `{ corrupt json ` | Raises `ConfigError` with `Malformed JSON` error message |
| T100 | `load_effective_config()` | `--reset-config` flag | Overwrites target file on disk with default JSON schema and returns default config |

---

## 11. Implementation Notes

### 11.1 Platform-Independent Path Testing (Issue #1841)
In all test cases, path comparisons MUST use `pathlib.Path` objects (e.g., `path == Path.home() / ".boostgauge" / "config.json"`) or `path.resolve()`. String comparisons (such as `str(path).endswith("boostgauge/config.json")`) are strictly forbidden because Windows path separators (`\`) will cause string assertions containing `/` to fail on Windows environments even when path logic is correct.

### 11.2 Asserting Only Specified Behaviors (Issue #1860)
CLI flag overrides (`--theme`, `--poll`, `--opacity`, `--no-topmost`) take precedence at runtime for the active session, but MUST NOT be persisted back to disk on startup unless `--reset-config` is explicitly specified. Unit tests (e.g. T030) must verify that disk contents remain unchanged when runtime CLI overrides are applied.

### 11.3 GUI Test Strategy Option C Compliance
All tests in `tests/unit/test_config.py` run without initializing `tkinter.Tk()`. `BoostGaugeApp` in unit tests is tested headlessly using pure data structures.

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
| Finalized | 2026-07-31T10:25:00Z |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #7 |
| Verdict | APPROVED |
| Date | 2026-07-31 |
| Iterations | 1 |
| Finalized | 2026-07-31T15:25:42Z |

### Review Feedback Summary

The revised implementation specification for Issue #7 provides complete, concrete, and fully executable code for all required files (pyproject.toml, src/boostgauge/__init__.py, src/boostgauge/config.py, src/boostgauge/app.py, src/boostgauge/__main__.py, and tests/unit/test_config.py). The revision cleanly addresses prior feedback regarding platform-independent path assertions using Path composition. All assertions in the test suite trace directly to specified behaviors and requirements.
