# Implementation Spec: Feature: Configuration File and CLI Arguments

| Field | Value |
|-------|-------|
| Issue | #7 |
| LLD | `docs/lld/active/7-configuration-file-and-cli-arguments.md` |
| Generated | 2026-07-28 |
| Status | APPROVED |

## 1. Overview

This implementation spec defines the configuration system for BoostGauge, including JSON settings file persistence, platform-specific config paths, command-line argument overrides via `argparse`, dynamic threshold updates, and window position/size state saving.

**Objective:** Implement a configuration system for BoostGauge that handles settings file persistence, CLI argument overrides, dynamic threshold updates, and window position/size state saving.

**Success Criteria:**
- Automatic creation of default JSON config file at `%APPDATA%/boostgauge/config.json` (Windows) or `~/.boostgauge/config.json` (POSIX) on first launch when no config file exists.
- Command-line flags (`--theme`, `--size`, `--poll`, `--opacity`, `--no-topmost`, `--config`, `--reset-config`) overriding loaded disk settings.
- Custom config file loading via `--config PATH`.
- Configuration reset via `--reset-config` resetting target file on disk to defaults.
- Persistence of window position (`x`, `y`) and size on application exit.
- In-memory dynamic update and re-validation of metric thresholds without application restart.
- controlled `ConfigError` exceptions and clear stderr messaging for invalid JSON formats or out-of-bounds parameter values.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `pyproject.toml` | Modify | Add `boostgauge` script entry points for CLI execution |
| 2 | `src/boostgauge/__init__.py` | Add | Package initialization defining version and export symbols |
| 3 | `src/boostgauge/config.py` | Add | Core configuration module (TypedDict models, path resolution, defaults, validation, JSON I/O, CLI parsing, overrides, geometry updates) |
| 4 | `src/boostgauge/__main__.py` | Add | Package main execution entry point calling `app.main()` |
| 5 | `src/boostgauge/app.py` | Add | Application lifecycle and CLI execution controller integrating configuration loading, overrides, and runtime startup |
| 6 | `tests/unit/test_config.py` | Add | Comprehensive unit test suite for configuration logic, path resolution, validation, CLI overrides, atomic I/O, and error handling |

**Implementation Order Rationale:**
1. `pyproject.toml` defines script entry points for Poetry/pip.
2. `src/boostgauge/__init__.py` establishes the package namespace.
3. `src/boostgauge/config.py` contains all zero-dependency data structures and logic functions required by application execution and tests.
4. `src/boostgauge/app.py` and `src/boostgauge/__main__.py` depend directly on `config.py`.
5. `tests/unit/test_config.py` validates `config.py` in isolation per Option C of the project GUI test strategy.

## 3. Current State (for Modify/Delete files)

### 3.1 `pyproject.toml`

**Relevant excerpt** (lines 1-28):

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
dependencies = [
    "psutil (>=7.2.2,<8.0.0)",
    "pillow (>=12.2.0,<13.0.0)",
    "pystray (>=0.19.5,<0.20.0)"
]

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

**What changes:** Add script entry points `[project.scripts]` and `[tool.poetry.scripts]` pointing `boostgauge` to `boostgauge.__main__:main`.

## 4. Data Structures

### 4.1 `Threshold`

**Definition:**

```python
class Threshold(TypedDict):
    yellow: float
    red: float
```

**Concrete Example:**

```json
{
    "yellow": 20.0,
    "red": 30.0
}
```

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
    "conpty": {
        "yellow": 20.0,
        "red": 30.0
    },
    "memory_percent": {
        "yellow": 70.0,
        "red": 85.0
    },
    "process_count": {
        "yellow": 150.0,
        "red": 300.0
    },
    "handle_count": {
        "yellow": 10000.0,
        "red": 20000.0
    }
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
        "y": 150
    },
    "thresholds": {
        "conpty": {
            "yellow": 20.0,
            "red": 30.0
        },
        "memory_percent": {
            "yellow": 70.0,
            "red": 85.0
        },
        "process_count": {
            "yellow": 150.0,
            "red": 300.0
        },
        "handle_count": {
            "yellow": 10000.0,
            "red": 20000.0
        }
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

```python
# No arguments required
```

**Output Example (Windows):**

```python
Path("C:/Users/mcwiz/AppData/Roaming/boostgauge/config.json")
```

**Output Example (POSIX):**

```python
Path("/home/user/.boostgauge/config.json")
```

**Edge Cases:**
- Windows environment variable `%APPDATA%` missing -> falls back to `Path.home() / "AppData" / "Roaming" / "boostgauge" / "config.json"`.

---

### 5.2 `get_default_config()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def get_default_config() -> GaugeConfigDict:
    """Return deep copy of default configuration dictionary."""
    ...
```

**Input Example:**

```python
# No arguments required
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
    "thresholds": {
        "conpty": {"yellow": 20.0, "red": 30.0},
        "memory_percent": {"yellow": 70.0, "red": 85.0},
        "process_count": {"yellow": 150.0, "red": 300.0},
        "handle_count": {"yellow": 10000.0, "red": 20000.0},
    },
    "telltale_windows": {"short": 60, "medium": 600, "long": 3600},
    "show_driver_label": True,
    "show_digital_readout": True,
    "show_session_count": True,
}
```

**Edge Cases:**
- Direct mutations to returned dictionary must not pollute subsequent calls (returns standard `copy.deepcopy()`).

---

### 5.3 `validate_config()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def validate_config(config: Dict[str, Any]) -> GaugeConfigDict:
    """Validate structure and value bounds of a configuration dictionary, returning typed GaugeConfigDict or raising ConfigError."""
    ...
```

**Input Example (Valid):**

```python
config_data = {
    "polling_interval_seconds": 1.5,
    "theme": "amber",
    "size": 350,
    "opacity": 0.85,
    "always_on_top": True,
    "position": {"x": 200, "y": 200},
    "thresholds": {
        "conpty": {"yellow": 15.0, "red": 25.0},
        "memory_percent": {"yellow": 60.0, "red": 80.0},
        "process_count": {"yellow": 100.0, "red": 200.0},
        "handle_count": {"yellow": 5000.0, "red": 15000.0},
    },
    "telltale_windows": {"short": 30, "medium": 300, "long": 1800},
    "show_driver_label": True,
    "show_digital_readout": False,
    "show_session_count": True,
}
```

**Output Example:**

```python
# Returns typed GaugeConfigDict matching input
```

**Edge Cases:**
- `opacity` out of range (e.g. `1.5` or `-0.1`) -> raises `ConfigError("opacity must be between 0.0 and 1.0")`
- `polling_interval_seconds <= 0` -> raises `ConfigError("polling_interval_seconds must be positive")`
- Unsupported `theme` (e.g. `"neon"`) -> raises `ConfigError("Invalid theme 'neon'. Supported themes: dark, light, amber, carbon")`
- `yellow >= red` threshold -> raises `ConfigError("Threshold yellow must be strictly less than red for conpty")`

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
config_path = Path("/tmp/test_config.json")
```

**Output Example:**

```python
# Returns GaugeConfigDict dictionary loaded from disk or created defaults
```

**Edge Cases:**
- File does not exist -> creates parent directories, writes `get_default_config()` as JSON, and returns defaults.
- File contains invalid JSON -> raises `ConfigError("Failed to parse config JSON: ...")`.
- File content fails validation -> raises `ConfigError`.

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
config_path = Path("/tmp/test_config.json")
```

**Output Example:**

```python
None
```

**Edge Cases:**
- Target parent directory does not exist -> creates directory via `mkdir(parents=True, exist_ok=True)`.
- Crash mid-write protection -> writes to temporary `.tmp` file in target directory before performing atomic `os.replace`.

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
args = ["--theme", "amber", "--size", "400", "--poll", "2.0", "--no-topmost"]
```

**Output Example:**

```python
Namespace(
    theme="amber",
    size=400,
    poll=2.0,
    opacity=None,
    no_topmost=True,
    config=None,
    reset_config=False
)
```

**Edge Cases:**
- `args=None` -> parses `sys.argv[1:]`.
- Invalid flag type (e.g. `--size abc`) -> `argparse` outputs error to stderr and calls `sys.exit(2)`.

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
    size=450,
    poll=0.5,
    opacity=0.7,
    no_topmost=True,
    config=None,
    reset_config=False
)
```

**Output Example:**

```python
{
    "polling_interval_seconds": 0.5,
    "theme": "light",
    "size": 450,
    "opacity": 0.7,
    "always_on_top": False,
    # ... other default fields preserved
}
```

**Edge Cases:**
- CLI arguments with `None` values are ignored, preserving disk/default settings.
- `--no-topmost=True` explicitly sets `always_on_top = False`.

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
x = 350
y = 420
size = 280
```

**Output Example:**

```python
# Returns copy of config with config["position"]["x"] == 350, config["position"]["y"] == 420, config["size"] == 280
```

**Edge Cases:**
- Negative coordinates or size -> validated when `validate_config()` is subsequently invoked.

---

### 5.9 `main()`

**File:** `src/boostgauge/app.py`

**Signature:**

```python
def main(args: Optional[list[str]] = None) -> int:
    """CLI application entry point managing configuration workflow and app startup."""
    ...
```

**Input Example:**

```python
args = ["--theme", "dark"]
```

**Output Example:**

```python
0  # Success return code
```

**Edge Cases:**
- Invalid config or CLI options -> catches `ConfigError`, prints error message to `sys.stderr`, and returns exit code `1`.

---

### 5.10 `test_get_default_config_path_posix()`

**File:** `tests/unit/test_config.py`

**Signature:**

```python
def test_get_default_config_path_posix(monkeypatch: pytest.MonkeyPatch) -> None:
    """T020: Test path resolution on POSIX systems."""
    ...
```

**Input Example:**

```python
monkeypatch.setattr(sys, "platform", "linux")
monkeypatch.setattr(Path, "home", lambda: Path("/home/testuser"))
```

**Output Example:**

```python
# Assertion passes: path == Path("/home/testuser/.boostgauge/config.json")
```

**Edge Cases:**
- Platform is non-Windows -> resolves to `Path.home() / ".boostgauge" / "config.json"`.

---

### 5.11 `test_get_default_config_path_windows()`

**File:** `tests/unit/test_config.py`

**Signature:**

```python
def test_get_default_config_path_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    """T020: Test path resolution on Windows systems with APPDATA environment variable."""
    ...
```

**Input Example:**

```python
monkeypatch.setattr(sys, "platform", "win32")
monkeypatch.setenv("APPDATA", r"C:\Users\testuser\AppData\Roaming")
```

**Output Example:**

```python
# Assertion passes: path == Path(r"C:\Users\testuser\AppData\Roaming\boostgauge\config.json")
```

**Edge Cases:**
- Platform is Windows with APPDATA set -> resolves to `%APPDATA%/boostgauge/config.json`.

---

### 5.12 `test_config_auto_creation_on_first_run()`

**File:** `tests/unit/test_config.py`

**Signature:**

```python
def test_config_auto_creation_on_first_run(tmp_path: Path) -> None:
    """T010: Test config file auto-creation when file is missing."""
    ...
```

**Input Example:**

```python
tmp_path = Path("/tmp/pytest-of-user/pytest-0/test_config_auto_creation_on_f0")
```

**Output Example:**

```python
# Creates config.json containing default configuration dictionary and returns defaults
```

**Edge Cases:**
- Target parent directory does not exist -> creates parent directories automatically.

---

### 5.13 `test_cli_options_override_config_file()`

**File:** `tests/unit/test_config.py`

**Signature:**

```python
def test_cli_options_override_config_file(tmp_path: Path) -> None:
    """T030: Test CLI options overriding loaded configuration values."""
    ...
```

**Input Example:**

```python
tmp_path = Path("/tmp/pytest-of-user/pytest-0/test_cli_options_override_conf0")
```

**Output Example:**

```python
# Overridden configuration dictionary has theme="light", size=400, polling_interval_seconds=5.0
```

**Edge Cases:**
- Unspecified CLI options leave existing config file settings unchanged.

## 6. Change Instructions

### 6.1 `pyproject.toml` (Modify)

**Change 1:** Add script entry point definitions after dependencies section.

```diff
 [dependency-groups]
 dev = [
     "pytest (>=9.0.3,<10.0.0)",
     "pytest-cov (>=7.1.0,<8.0.0)"
 ]
+
+[project.scripts]
+boostgauge = "boostgauge.__main__:main"
+
+[tool.poetry.scripts]
+boostgauge = "boostgauge.__main__:main"
 
 [tool.pytest.ini_options]
 testpaths = ["tests"]
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
"""Configuration management module for BoostGauge.

Handles settings persistence, path resolution, JSON I/O, validation, and CLI overrides.
Issue #7: Configuration File and CLI Arguments
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
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


VALID_THEMES = {"dark", "light", "amber", "carbon"}


def get_default_config_path() -> Path:
    """Return platform-specific default config path.

    Windows: %APPDATA%/boostgauge/config.json
    POSIX: ~/.boostgauge/config.json
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
    """Return deep copy of default configuration dictionary."""
    return {
        "polling_interval_seconds": 1.0,
        "theme": "dark",
        "size": 300,
        "opacity": 0.9,
        "always_on_top": True,
        "position": {"x": 100, "y": 100},
        "thresholds": {
            "conpty": {"yellow": 20.0, "red": 30.0},
            "memory_percent": {"yellow": 70.0, "red": 85.0},
            "process_count": {"yellow": 150.0, "red": 300.0},
            "handle_count": {"yellow": 10000.0, "red": 20000.0},
        },
        "telltale_windows": {"short": 60, "medium": 600, "long": 3600},
        "show_driver_label": True,
        "show_digital_readout": True,
        "show_session_count": True,
    }


def validate_config(config: Dict[str, Any]) -> GaugeConfigDict:
    """Validate structure and value bounds of a configuration dictionary."""
    if not isinstance(config, dict):
        raise ConfigError("Configuration root must be a JSON object")

    # Polling interval
    poll = config.get("polling_interval_seconds")
    if not isinstance(poll, (int, float)) or poll <= 0:
        raise ConfigError("polling_interval_seconds must be a positive number")

    # Theme
    theme = config.get("theme")
    if not isinstance(theme, str) or theme not in VALID_THEMES:
        sorted_themes = ", ".join(sorted(VALID_THEMES))
        raise ConfigError(f"Invalid theme '{theme}'. Supported themes: {sorted_themes}")

    # Size
    size = config.get("size")
    if not isinstance(size, int) or size < 50 or size > 2000:
        raise ConfigError("size must be an integer between 50 and 2000")

    # Opacity
    opacity = config.get("opacity")
    if not isinstance(opacity, (int, float)) or opacity < 0.0 or opacity > 1.0:
        raise ConfigError("opacity must be between 0.0 and 1.0")

    # Always on top
    always_on_top = config.get("always_on_top")
    if not isinstance(always_on_top, bool):
        raise ConfigError("always_on_top must be a boolean")

    # Position
    pos = config.get("position")
    if not isinstance(pos, dict) or "x" not in pos or "y" not in pos:
        raise ConfigError("position must be an object with 'x' and 'y' integer coordinates")
    if not isinstance(pos["x"], int) or not isinstance(pos["y"], int):
        raise ConfigError("position 'x' and 'y' must be integers")

    # Thresholds
    thresholds = config.get("thresholds")
    if not isinstance(thresholds, dict):
        raise ConfigError("thresholds must be an object")

    required_metrics = {"conpty", "memory_percent", "process_count", "handle_count"}
    for metric in required_metrics:
        m_val = thresholds.get(metric)
        if not isinstance(m_val, dict) or "yellow" not in m_val or "red" not in m_val:
            raise ConfigError(f"Threshold for '{metric}' must contain 'yellow' and 'red' values")
        y, r = m_val["yellow"], m_val["red"]
        if not isinstance(y, (int, float)) or not isinstance(r, (int, float)):
            raise ConfigError(f"Threshold values for '{metric}' must be numbers")
        if y < 0 or r < 0:
            raise ConfigError(f"Threshold values for '{metric}' must be non-negative")
        if y >= r:
            raise ConfigError(f"Threshold yellow must be strictly less than red for {metric}")

    # Telltale windows
    tw = config.get("telltale_windows")
    if not isinstance(tw, dict) or not {"short", "medium", "long"}.issubset(tw.keys()):
        raise ConfigError("telltale_windows must contain 'short', 'medium', and 'long' integer values")
    s, m, l_win = tw["short"], tw["medium"], tw["long"]
    if not (isinstance(s, int) and isinstance(m, int) and isinstance(l_win, int)):
        raise ConfigError("telltale_windows values must be integers")
    if not (0 < s < m < l_win):
        raise ConfigError("telltale_windows values must satisfy 0 < short < medium < long")

    # Boolean display flags
    for flag in ("show_driver_label", "show_digital_readout", "show_session_count"):
        if not isinstance(config.get(flag), bool):
            raise ConfigError(f"{flag} must be a boolean")

    return copy.deepcopy(config)  # type: ignore[return-value]


def load_config(config_path: Optional[Path] = None) -> GaugeConfigDict:
    """Load configuration from specified path (or default path), auto-creating default config if file is missing."""
    target_path = config_path.resolve() if config_path else get_default_config_path()

    if not target_path.exists():
        default_cfg = get_default_config()
        save_config(default_cfg, target_path)
        return default_cfg

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Failed to parse config JSON at {target_path}: {exc}") from exc
    except OSError as exc:
        raise ConfigError(f"Failed to read config file at {target_path}: {exc}") from exc

    return validate_config(data)


def save_config(config: GaugeConfigDict, config_path: Optional[Path] = None) -> None:
    """Atomically write configuration dictionary to JSON file at specified path (or default path)."""
    target_path = config_path.resolve() if config_path else get_default_config_path()
    target_path.parent.mkdir(parents=True, exist_ok=True)

    validated = validate_config(config)

    tmp_path = target_path.with_suffix(f"{target_path.suffix}.tmp_{os.getpid()}")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(validated, f, indent=2)
        os.replace(tmp_path, target_path)
    except Exception as exc:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise ConfigError(f"Failed to save config file to {target_path}: {exc}") from exc


def parse_cli_args(args: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse CLI options for theme, size, poll, opacity, topmost, config path, and reset flag."""
    parser = argparse.ArgumentParser(
        prog="boostgauge",
        description="BoostGauge: Tachometer-styled system pressure monitor.",
    )
    parser.add_argument("--theme", choices=sorted(VALID_THEMES), help="Gauge color theme")
    parser.add_argument("--size", type=int, help="Gauge window size in pixels")
    parser.add_argument("--poll", type=float, help="Polling interval in seconds")
    parser.add_argument("--opacity", type=float, help="Window opacity (0.0 to 1.0)")
    parser.add_argument("--no-topmost", action="store_true", help="Disable always-on-top window behavior")
    parser.add_argument("--config", type=Path, help="Path to custom JSON configuration file")
    parser.add_argument("--reset-config", action="store_true", help="Reset configuration file to default settings")

    return parser.parse_args(args if args is not None else sys.argv[1:])


def apply_cli_overrides(config: GaugeConfigDict, parsed_args: argparse.Namespace) -> GaugeConfigDict:
    """Apply parsed CLI arguments as overrides on top of loaded configuration dictionary."""
    updated = copy.deepcopy(config)

    if parsed_args.theme is not None:
        updated["theme"] = parsed_args.theme
    if parsed_args.size is not None:
        updated["size"] = parsed_args.size
    if parsed_args.poll is not None:
        updated["polling_interval_seconds"] = parsed_args.poll
    if parsed_args.opacity is not None:
        updated["opacity"] = parsed_args.opacity
    if getattr(parsed_args, "no_topmost", False):
        updated["always_on_top"] = False

    return updated


def update_window_geometry(config: GaugeConfigDict, x: int, y: int, size: int) -> GaugeConfigDict:
    """Update window position and size parameters in configuration data structure prior to exit/save."""
    updated = copy.deepcopy(config)
    updated["position"] = {"x": x, "y": y}
    updated["size"] = size
    return updated
```

---

### 6.4 `src/boostgauge/__main__.py` (Add)

**Complete file contents:**

```python
"""CLI entry point for BoostGauge.

Issue #7: Configuration File and CLI Arguments
"""

import sys
from boostgauge.app import main

if __name__ == "__main__":
    sys.exit(main())
```

---

### 6.5 `src/boostgauge/app.py` (Add)

**Complete file contents:**

```python
"""Application runtime controller integrating configuration lifecycle.

Issue #7: Configuration File and CLI Arguments
"""

from __future__ import annotations

import sys
from typing import Optional

from boostgauge.config import (
    ConfigError,
    apply_cli_overrides,
    get_default_config,
    get_default_config_path,
    load_config,
    parse_cli_args,
    save_config,
    validate_config,
)


def main(args: Optional[list[str]] = None) -> int:
    """Execute main application startup sequence and configuration lifecycle."""
    try:
        parsed_args = parse_cli_args(args)
        target_config_path = parsed_args.config if parsed_args.config else get_default_config_path()

        if parsed_args.reset_config:
            default_config = get_default_config()
            save_config(default_config, target_config_path)
            config = default_config
        else:
            config = load_config(target_config_path)

        config = apply_cli_overrides(config, parsed_args)
        config = validate_config(config)

        # Application runtime startup logic will attach here in subsequent issues
        return 0

    except ConfigError as exc:
        print(f"BoostGauge Configuration Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

---

### 6.6 `tests/unit/test_config.py` (Add)

**Complete file contents:**

```python
"""Unit test suite for configuration management module.

Issue #7: Configuration File and CLI Arguments
Ref: docs/design/0001-test-strategy.md (Option C compliance)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pytest

from boostgauge.config import (
    ConfigError,
    GaugeConfigDict,
    apply_cli_overrides,
    get_default_config,
    get_default_config_path,
    load_config,
    parse_cli_args,
    save_config,
    update_window_geometry,
    validate_config,
)


def test_get_default_config_path_posix(monkeypatch: pytest.MonkeyPatch) -> None:
    """T020: Test path resolution on POSIX systems."""
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(Path, "home", lambda: Path("/home/testuser"))
    path = get_default_config_path()
    assert path == Path("/home/testuser/.boostgauge/config.json")


def test_get_default_config_path_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    """T020: Test path resolution on Windows systems with APPDATA environment variable."""
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", r"C:\Users\testuser\AppData\Roaming")
    path = get_default_config_path()
    assert path == Path(r"C:\Users\testuser\AppData\Roaming\boostgauge\config.json")


def test_config_auto_creation_on_first_run(tmp_path: Path) -> None:
    """T010: Test config file auto-creation when file is missing."""
    cfg_file = tmp_path / "boostgauge" / "config.json"
    assert not cfg_file.exists()

    loaded = load_config(cfg_file)

    assert cfg_file.exists()
    assert loaded == get_default_config()


def test_cli_options_override_config_file(tmp_path: Path) -> None:
    """T030: Test CLI options overriding loaded configuration values."""
    cfg_file = tmp_path / "config.json"
    cfg = get_default_config()
    cfg["theme"] = "dark"
    cfg["size"] = 300
    save_config(cfg, cfg_file)

    parsed = parse_cli_args(["--theme", "light", "--size", "400", "--poll", "5.0"])
    overridden = apply_cli_overrides(cfg, parsed)

    assert overridden["theme"] == "light"
    assert overridden["size"] == 400
    assert overridden["polling_interval_seconds"] == 5.0


def test_cli_no_topmost_override() -> None:
    """T040: Test --no-topmost CLI flag overriding always_on_top setting."""
    cfg = get_default_config()
    assert cfg["always_on_top"] is True

    parsed = parse_cli_args(["--no-topmost"])
    overridden = apply_cli_overrides(cfg, parsed)

    assert overridden["always_on_top"] is False


def test_custom_config_path_argument(tmp_path: Path) -> None:
    """T050: Test custom --config PATH CLI argument."""
    custom_dir = tmp_path / "custom_dir"
    custom_dir.mkdir()
    custom_file = custom_dir / "my_config.json"

    custom_cfg = get_default_config()
    custom_cfg["theme"] = "amber"
    save_config(custom_cfg, custom_file)

    parsed = parse_cli_args(["--config", str(custom_file)])
    assert parsed.config == custom_file

    loaded = load_config(parsed.config)
    assert loaded["theme"] == "amber"


def test_reset_config_option(tmp_path: Path) -> None:
    """T060: Test --reset-config CLI option overwriting disk file with defaults."""
    cfg_file = tmp_path / "config.json"
    modified_cfg = get_default_config()
    modified_cfg["theme"] = "carbon"
    modified_cfg["size"] = 500
    save_config(modified_cfg, cfg_file)

    # Perform reset action as specified in app workflow
    parsed = parse_cli_args(["--reset-config"])
    assert parsed.reset_config is True

    if parsed.reset_config:
        default_cfg = get_default_config()
        save_config(default_cfg, cfg_file)

    reloaded = load_config(cfg_file)
    assert reloaded["theme"] == "dark"
    assert reloaded["size"] == 300


def test_window_position_and_size_update_and_save(tmp_path: Path) -> None:
    """T070: Test geometry update and atomic persistence on exit."""
    cfg_file = tmp_path / "config.json"
    cfg = get_default_config()
    save_config(cfg, cfg_file)

    updated_geometry = update_window_geometry(cfg, x=250, y=300, size=350)
    save_config(updated_geometry, cfg_file)

    reloaded = load_config(cfg_file)
    assert reloaded["position"] == {"x": 250, "y": 300}
    assert reloaded["size"] == 350


def test_dynamic_in_memory_threshold_update() -> None:
    """T080: Test in-memory threshold update and re-validation."""
    cfg = get_default_config()
    cfg["thresholds"]["conpty"]["yellow"] = 40.0
    cfg["thresholds"]["conpty"]["red"] = 50.0

    validated = validate_config(cfg)
    assert validated["thresholds"]["conpty"]["yellow"] == 40.0
    assert validated["thresholds"]["conpty"]["red"] == 50.0


def test_invalid_json_config_file_error(tmp_path: Path) -> None:
    """T090: Test malformed JSON file raising ConfigError."""
    cfg_file = tmp_path / "corrupt.json"
    cfg_file.write_text("{ invalid json: ", encoding="utf-8")

    with pytest.raises(ConfigError, match="Failed to parse config JSON"):
        load_config(cfg_file)


def test_out_of_bounds_numeric_config_parameters() -> None:
    """T100: Test out-of-bounds numeric validation raising ConfigError."""
    cfg = get_default_config()
    cfg["opacity"] = 1.5
    with pytest.raises(ConfigError, match="opacity must be between 0.0 and 1.0"):
        validate_config(cfg)

    cfg_poll = get_default_config()
    cfg_poll["polling_interval_seconds"] = -1.0
    with pytest.raises(ConfigError, match="polling_interval_seconds must be a positive number"):
        validate_config(cfg_poll)


def test_invalid_theme_validation_error() -> None:
    """T110: Test invalid theme name raising ConfigError."""
    cfg = get_default_config()
    cfg["theme"] = "invalid_theme"
    with pytest.raises(ConfigError, match="Invalid theme 'invalid_theme'"):
        validate_config(cfg)


def test_threshold_yellow_greater_than_red_error() -> None:
    """Test threshold yellow >= red raising ConfigError."""
    cfg = get_default_config()
    cfg["thresholds"]["conpty"]["yellow"] = 50.0
    cfg["thresholds"]["conpty"]["red"] = 40.0
    with pytest.raises(ConfigError, match="Threshold yellow must be strictly less than red"):
        validate_config(cfg)
```

## 7. Pattern References

### 7.1 Test Module Bootstrap Pattern

**File:** `tests/conftest.py` (lines 1-8)

```python
"""Project test bootstrap."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
```

**Relevance:** Demonstrates `sys.path` insertion for resolving imports from `src/boostgauge` within pytest execution without external installation step.

### 7.2 Entry Points Configuration Pattern

**File:** `pyproject.toml` (lines 20-24)

```toml
[build-system]
requires = ["poetry-core>=2.0.0,<3.0.0"]
build-backend = "poetry.core.masonry.api"
```

**Relevance:** Standard Poetry metadata declaration format used for adding `[tool.poetry.scripts]` and `[project.scripts]`.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `import argparse` | stdlib | `src/boostgauge/config.py`, `src/boostgauge/app.py` |
| `import copy` | stdlib | `src/boostgauge/config.py` |
| `import json` | stdlib | `src/boostgauge/config.py` |
| `import os` | stdlib | `src/boostgauge/config.py` |
| `import sys` | stdlib | `src/boostgauge/config.py`, `src/boostgauge/app.py`, `src/boostgauge/__main__.py`, `tests/unit/test_config.py` |
| `from pathlib import Path` | stdlib | `src/boostgauge/config.py`, `src/boostgauge/app.py`, `tests/unit/test_config.py` |
| `from typing import Any, Dict, Optional, TypedDict` | stdlib | `src/boostgauge/config.py` |
| `import pytest` | dev-dependency | `tests/unit/test_config.py` |
| `from boostgauge.config import ...` | internal | `src/boostgauge/app.py`, `tests/unit/test_config.py` |

**New Dependencies:** None (uses Python 3.10+ standard library).

## 9. Placeholder

*Reserved for future section alignment.*

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `load_config()` | Non-existent path `tmp_path/config.json` | Creates default JSON file on disk and returns `get_default_config()` |
| T020 | `get_default_config_path()` | `sys.platform == "win32"` / `"linux"` | Path matching `%APPDATA%/boostgauge/config.json` or `~/.boostgauge/config.json` |
| T030 | `apply_cli_overrides()` | `["--theme", "light", "--size", "400", "--poll", "5.0"]` | Dict with `theme="light"`, `size=400`, `polling_interval_seconds=5.0` |
| T040 | `apply_cli_overrides()` | `["--no-topmost"]` | Dict with `always_on_top=False` |
| T050 | `load_config()` | `["--config", "/custom/path.json"]` | Config loaded from specified path `/custom/path.json` |
| T060 | `load_config()` & `save_config()` | Custom config on disk + `["--reset-config"]` | File on disk overwritten with default JSON configuration |
| T070 | `update_window_geometry()` & `save_config()` | `x=250, y=300, size=350` | Saved JSON file contains `position={"x": 250, "y": 300}` and `size=350` |
| T080 | `validate_config()` | In-memory updated thresholds `yellow=40.0, red=50.0` | Validated config dictionary with updated thresholds |
| T090 | `load_config()` | File with invalid content `{ invalid json: ` | Raises `ConfigError("Failed to parse config JSON...")` |
| T100 | `validate_config()` | `opacity=1.5` or `polling_interval_seconds=-1.0` | Raises `ConfigError` with clear message |
| T110 | `validate_config()` | `theme="invalid_theme"` | Raises `ConfigError` listing supported themes |

## 11. Implementation Notes

### 11.1 Error Handling Convention

All configuration errors (missing keys, bad values, out-of-range bounds, unparseable JSON) raise `boostgauge.config.ConfigError`. `app.main()` catches `ConfigError`, outputs a formatted message to `sys.stderr`, and returns exit code `1`.

### 11.2 Atomic File Writing

To prevent corrupted JSON files during sudden system shutdown or crash, `save_config()` writes to a temporary file (`config.json.tmp_<pid>`) in the target directory before invoking atomic operation `os.replace()`.

### 11.3 Constants & Validation Bounds

| Constant | Value / Allowed Set | Rationale |
|----------|---------------------|-----------|
| `VALID_THEMES` | `{"dark", "light", "amber", "carbon"}` | Supported tachometer visual palettes |
| `MIN_SIZE` / `MAX_SIZE` | `50` / `2000` | UI bounds for tachometer widget rendering |
| `MIN_OPACITY` / `MAX_OPACITY` | `0.0` / `1.0` | OS window alpha blending limits |

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
| Date | 2026-07-28 |
| Iterations | 1 |
| Finalized | 2026-07-28T15:57:00-05:00 |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #7 |
| Verdict | APPROVED |
| Date | 2026-07-28 |
| Iterations | 1 |
| Finalized | 2026-07-28T20:57:51Z |

### Review Feedback Summary

\nThe revised implementation spec for Issue #7 (Configuration File and CLI Arguments) is exceptionally detailed, concrete, and fully executable. The spec provides 100% complete Python source code for all new files (`src/boostgauge/__init__.py`, `src/boostgauge/config.py`, `src/boostgauge/__main__.py`, `src/boostgauge/app.py`, `tests/unit/test_config.py`) and exact diffs for modified configuration files (`pyproject.toml`). The addition of unit test function specifications (5.10–5.13) resolves pri...
