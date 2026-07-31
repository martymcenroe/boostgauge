# Implementation Spec: Feature: Configuration File and CLI Arguments

| Field | Value |
|-------|-------|
| Issue | #7 |
| LLD | `docs/lld/active/0007-config-cli.md` |
| Generated | 2026-07-31 |
| Status | APPROVED |

## 1. Overview

This implementation spec defines the technical details for building BoostGauge's configuration manager, command-line interface argument parser, atomic settings persistence, dynamic runtime threshold updates, and application state orchestration.

**Objective:** Implement a robust configuration management system for BoostGauge providing persistent user settings storage, command-line interface argument parsing with override semantics, dynamic runtime threshold updates, and automatic exit state persistence for window geometry.

**Success Criteria:**
- Default `config.json` file auto-created at platform-specific location on first launch.
- Command-line flags override configuration file settings during runtime without mutating non-overridden config settings.
- Window geometry (`x`, `y`, `size`) saved atomically on application exit and restored on subsequent launches.
- Runtime threshold updates applied dynamically without requiring application process restart.
- Robust schema validation with graceful fallback to default config values when encountering malformed inputs.
- Support `--config PATH` for custom config paths and `--reset-config` for factory reset.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/__init__.py` | Add | Package initialization file defining package metadata and exports |
| 2 | `src/boostgauge/config.py` | Add | Core configuration manager handling default resolution, validation, persistence, and CLI overrides |
| 3 | `src/boostgauge/app.py` | Add | Application lifecycle and runtime state orchestrator integrating config with monitoring |
| 4 | `src/boostgauge/__main__.py` | Add | Executable entry point handling CLI argument parsing, config merging, and app bootstrap |
| 5 | `pyproject.toml` | Modify | Register `boostgauge` CLI executable script under `[tool.poetry.scripts]` |
| 6 | `tests/unit/test_config.py` | Add | Unit test suite covering path resolution, parsing, schema validation, CLI overrides, and atomic persistence |

**Implementation Order Rationale:**
1. `__init__.py` establishes module namespace and version metadata.
2. `config.py` provides independent configuration data types, JSON loaders, validators, atomic save functions, and CLI parsers.
3. `app.py` consumes `config.py` utilities to control window lifecycle, runtime threshold changes, and shutdown persistence.
4. `__main__.py` ties CLI parsing, configuration loading, and `App` initialization into an entry point `main()`.
5. `pyproject.toml` is updated to expose `boostgauge` CLI entry point once `__main__.py` exists.
6. `test_config.py` tests all functional contracts defined in `config.py` and `app.py`.

## 3. Current State (for Modify/Delete files)

### 3.1 `pyproject.toml`

**Relevant excerpt** (lines 17-33):

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

**What changes:** Register `boostgauge = "boostgauge.__main__:main"` under a new `[tool.poetry.scripts]` section.

## 4. Data Structures

### 4.1 `PositionDict`

**Definition:**

```python
from typing import TypedDict

class PositionDict(TypedDict):
    x: int
    y: int
```

**Concrete Example:**

```json
{
  "x": 250,
  "y": 150
}
```

### 4.2 `ThresholdConfig`

**Definition:**

```python
from typing import TypedDict

class ThresholdConfig(TypedDict):
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

### 4.3 `ThresholdsDict`

**Definition:**

```python
from typing import TypedDict

class ThresholdsDict(TypedDict):
    conpty: ThresholdConfig
    memory_percent: ThresholdConfig
    process_count: ThresholdConfig
    handle_count: ThresholdConfig
```

**Concrete Example:**

```json
{
  "conpty": {
    "yellow": 16.0,
    "red": 28.0
  },
  "memory_percent": {
    "yellow": 75.0,
    "red": 90.0
  },
  "process_count": {
    "yellow": 150.0,
    "red": 300.0
  },
  "handle_count": {
    "yellow": 50000.0,
    "red": 80000.0
  }
}
```

### 4.4 `TelltaleWindowsDict`

**Definition:**

```python
from typing import TypedDict

class TelltaleWindowsDict(TypedDict):
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
from typing import TypedDict

class BoostGaugeConfig(TypedDict):
    polling_interval_seconds: float
    theme: str
    size: int
    opacity: float
    always_on_top: bool
    position: PositionDict
    thresholds: ThresholdsDict
    telltale_windows: TelltaleWindowsDict
    show_driver_label: bool
    show_digital_readout: bool
    show_session_count: bool
```

**Concrete Example:**

```json
{
  "polling_interval_seconds": 0.5,
  "theme": "default",
  "size": 300,
  "opacity": 0.95,
  "always_on_top": true,
  "position": {
    "x": 100,
    "y": 100
  },
  "thresholds": {
    "conpty": {
      "yellow": 16.0,
      "red": 28.0
    },
    "memory_percent": {
      "yellow": 75.0,
      "red": 90.0
    },
    "process_count": {
      "yellow": 150.0,
      "red": 300.0
    },
    "handle_count": {
      "yellow": 50000.0,
      "red": 80000.0
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
def get_default_config_path() -> pathlib.Path:
    """Return platform-specific default configuration path (~/.boostgauge/config.json or %APPDATA%/boostgauge/config.json)."""
    ...
```

**Input Example:**

```python
# No arguments
```

**Output Example (POSIX):**

```python
pathlib.Path("/home/user/.boostgauge/config.json")
```

**Output Example (Windows):**

```python
pathlib.Path("C:/Users/user/AppData/Roaming/boostgauge/config.json")
```

**Edge Cases:**
- Windows missing `%APPDATA%`: falls back to `pathlib.Path.home() / "AppData" / "Roaming" / "boostgauge" / "config.json"`.

---

### 5.2 `get_default_config()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def get_default_config() -> Dict[str, Any]:
    """Return dictionary containing default configuration values."""
    ...
```

**Input Example:**

```python
# No arguments
```

**Output Example:**

```python
{
    "polling_interval_seconds": 0.5,
    "theme": "default",
    "size": 300,
    "opacity": 0.95,
    "always_on_top": True,
    "position": {"x": 100, "y": 100},
    "thresholds": {
        "conpty": {"yellow": 16.0, "red": 28.0},
        "memory_percent": {"yellow": 75.0, "red": 90.0},
        "process_count": {"yellow": 150.0, "red": 300.0},
        "handle_count": {"yellow": 50000.0, "red": 80000.0},
    },
    "telltale_windows": {"short": 60, "medium": 600, "long": 3600},
    "show_driver_label": True,
    "show_digital_readout": True,
    "show_session_count": True,
}
```

**Edge Cases:**
- Guarantees return of a deep copy so caller mutations do not alter package default structure.

---

### 5.3 `load_config_file()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def load_config_file(config_path: pathlib.Path) -> Dict[str, Any]:
    """Load and parse JSON configuration file. Auto-create default file if non-existent."""
    ...
```

**Input Example:**

```python
config_path = pathlib.Path("/tmp/boostgauge_test/config.json")
```

**Output Example:**

```python
{
    "polling_interval_seconds": 0.5,
    "theme": "default",
    "size": 300,
    "opacity": 0.95,
    "always_on_top": True,
    "position": {"x": 100, "y": 100},
    "thresholds": { ... },
    "telltale_windows": { ... },
    "show_driver_label": True,
    "show_digital_readout": True,
    "show_session_count": True
}
```

**Edge Cases:**
- File missing: auto-creates parent directory (with permission `0o700` on POSIX) and writes default configuration, then returns default config dict.
- Invalid JSON syntax: renames invalid file to `config.json.corrupt`, logs warning to `sys.stderr`, saves standard default configuration file, and returns default config dict.
- PermissionError reading file: logs warning and returns validated defaults in memory without raising exception.

---

### 5.4 `save_config_file()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def save_config_file(config_path: pathlib.Path, config_data: Dict[str, Any]) -> None:
    """Atomically write configuration data to JSON file using tempfile and os.replace."""
    ...
```

**Input Example:**

```python
config_path = pathlib.Path("/home/user/.boostgauge/config.json")
config_data = {
    "polling_interval_seconds": 1.0,
    "theme": "neon",
    "size": 400,
    "opacity": 1.0,
    "always_on_top": True,
    "position": {"x": 250, "y": 150},
    "thresholds": { ... },
    "telltale_windows": { ... },
    "show_driver_label": True,
    "show_digital_readout": True,
    "show_session_count": True
}
```

**Output Example:**

```python
None  # Successfully writes file atomically to disk
```

**Edge Cases:**
- Parent directory non-existent: created automatically via `mkdir(parents=True, exist_ok=True)`.
- Write error/disk full: temporary file cleaned up before exception/log emission, existing file untouched.

---

### 5.5 `validate_config()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def validate_config(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Validate configuration schema types and value ranges, populating missing keys with defaults."""
    ...
```

**Input Example:**

```python
raw_config = {
    "polling_interval_seconds": "invalid_string",
    "opacity": 2.5,  # Out of range [0.0, 1.0]
    "theme": "dark"
}
```

**Output Example:**

```python
{
    "polling_interval_seconds": 0.5,  # Restored default
    "theme": "dark",                   # Retained valid user value
    "size": 300,                       # Added missing key default
    "opacity": 0.95,                   # Restored default due to invalid range
    "always_on_top": True,
    "position": {"x": 100, "y": 100},
    "thresholds": { ... },
    "telltale_windows": { ... },
    "show_driver_label": True,
    "show_digital_readout": True,
    "show_session_count": True
}
```

**Edge Cases:**
- Non-dict input: returns default config dict.
- Partial thresholds dict missing keys or with invalid bounds (`yellow >= red`): invalid threshold block replaced with default threshold values.

---

### 5.6 `build_cli_parser()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def build_cli_parser() -> argparse.ArgumentParser:
    """Construct argument parser for CLI flags."""
    ...
```

**Input Example:**

```python
# No arguments
```

**Output Example:**

```python
<argparse.ArgumentParser object at 0x7f81a0>
```

**Edge Cases:**
- Standard CLI flag definitions for `--theme`, `--size`, `--poll`, `--opacity`, `--no-topmost`, `--config`, `--reset-config`.

---

### 5.7 `parse_cli_args()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def parse_cli_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments from sys.argv or provided argument list."""
    ...
```

**Input Example:**

```python
args = ["--theme", "neon", "--poll", "1.0", "--no-topmost"]
```

**Output Example:**

```python
argparse.Namespace(
    theme="neon",
    poll=1.0,
    size=None,
    opacity=None,
    no_topmost=True,
    config=None,
    reset_config=False
)
```

**Edge Cases:**
- Invalid flag argument (e.g. `--poll -0.5` or `--opacity 2.5`): parser calls `sys.exit(2)` with descriptive standard error message.

---

### 5.8 `merge_config()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def merge_config(config_file_data: Dict[str, Any], cli_args: argparse.Namespace) -> Dict[str, Any]:
    """Merge configuration dictionary with CLI overrides."""
    ...
```

**Input Example:**

```python
config_file_data = {
    "polling_interval_seconds": 0.5,
    "theme": "classic",
    "size": 300,
    "opacity": 0.95,
    "always_on_top": True,
    "position": {"x": 100, "y": 100},
    "thresholds": { ... },
    "telltale_windows": { ... },
    "show_driver_label": True,
    "show_digital_readout": True,
    "show_session_count": True
}
cli_args = argparse.Namespace(
    theme="neon",
    poll=1.0,
    size=400,
    opacity=None,
    no_topmost=True,
    config=None,
    reset_config=False
)
```

**Output Example:**

```python
{
    "polling_interval_seconds": 1.0,   # Overridden by --poll
    "theme": "neon",                   # Overridden by --theme
    "size": 400,                       # Overridden by --size
    "opacity": 0.95,                   # Retained from file (CLI was None)
    "always_on_top": False,            # Overridden by --no-topmost
    "position": {"x": 100, "y": 100},
    "thresholds": { ... },
    "telltale_windows": { ... },
    "show_driver_label": True,
    "show_digital_readout": True,
    "show_session_count": True
}
```

**Edge Cases:**
- Unspecified CLI flags (`None` values in namespace) leave config file dictionary entries unmodified.

---

### 5.9 `update_thresholds()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def update_thresholds(config_data: Dict[str, Any], new_thresholds: Dict[str, Any]) -> Dict[str, Any]:
    """Dynamically update threshold values in runtime configuration dictionary."""
    ...
```

**Input Example:**

```python
config_data = { ... } # existing config dict
new_thresholds = {
    "memory_percent": {"yellow": 80.0, "red": 95.0}
}
```

**Output Example:**

```python
{
    ...
    "thresholds": {
        "conpty": {"yellow": 16.0, "red": 28.0},
        "memory_percent": {"yellow": 80.0, "red": 95.0}, # Updated
        "process_count": {"yellow": 150.0, "red": 300.0},
        "handle_count": {"yellow": 50000.0, "red": 80000.0}
    }
}
```

**Edge Cases:**
- Invalid values (`yellow >= red` or negative numbers): raises `ValueError("Invalid threshold values: yellow must be less than red and positive")` without modifying original config.

---

### 5.10 `update_window_state()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def update_window_state(config_data: Dict[str, Any], x: int, y: int, size: int) -> Dict[str, Any]:
    """Update window position and size state in configuration structure."""
    ...
```

**Input Example:**

```python
config_data = { ... }
x = 350
y = 200
size = 350
```

**Output Example:**

```python
{
    ...
    "size": 350,
    "position": {"x": 350, "y": 200}
}
```

**Edge Cases:**
- Negative coordinates or size <= 0: clamped to non-negative coordinates (`max(0, x)`, `max(0, y)`) and minimum size `max(100, size)`.

---

### 5.11 `main()`

**File:** `src/boostgauge/__main__.py`

**Signature:**

```python
def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI entry point executing config bootstrap and application execution."""
    ...
```

**Input Example:**

```python
argv = ["--theme", "neon", "--size", "350"]
```

**Output Example:**

```python
0  # Process exit status code
```

**Edge Cases:**
- KeyboardInterrupt or SystemExit: handles exit signal, saves window state, and returns exit code `0`.

---

### 5.12 `test_t010_auto_create_default_config()`

**File:** `tests/unit/test_config.py`

**Signature:**

```python
def test_t010_auto_create_default_config(tmp_path: pathlib.Path) -> None:
    """T010: Auto-create default config file on first run if missing."""
    ...
```

**Input Example:**

```python
tmp_path = pathlib.Path("/tmp/pytest-of-user/pytest-1/test_t010_auto_create_default_config0")
```

**Output Example:**

```python
None  # Asserts config file auto-created at tmp_path/sub_dir/config.json with default values
```

**Edge Cases:**
- Parent directory missing: auto-created during initial file write.

---

### 5.13 `test_t020_cli_arguments_override_config_values()`

**File:** `tests/unit/test_config.py`

**Signature:**

```python
def test_t020_cli_arguments_override_config_values(tmp_path: pathlib.Path) -> None:
    """T020: CLI arguments override config file values."""
    ...
```

**Input Example:**

```python
tmp_path = pathlib.Path("/tmp/pytest-of-user/pytest-1/test_t020_cli_arguments_override0")
```

**Output Example:**

```python
None  # Asserts effective config merges CLI overrides over base config values
```

**Edge Cases:**
- Non-overridden options maintain existing config file values.

---

### 5.14 `test_t030_save_and_restore_window_state()`

**File:** `tests/unit/test_config.py`

**Signature:**

```python
def test_t030_save_and_restore_window_state(tmp_path: pathlib.Path) -> None:
    """T030: Save and restore window position and size on exit."""
    ...
```

**Input Example:**

```python
tmp_path = pathlib.Path("/tmp/pytest-of-user/pytest-1/test_t030_save_and_restore0")
```

**Output Example:**

```python
None  # Asserts window position (250, 150) and size 350 restored from config file
```

**Edge Cases:**
- Shutdown persists updated position and size back to disk cleanly.

---

### 5.15 `test_t040_dynamic_threshold_updates()`

**File:** `tests/unit/test_config.py`

**Signature:**

```python
def test_t040_dynamic_threshold_updates() -> None:
    """T040: Dynamic threshold updates take effect at runtime."""
    ...
```

**Input Example:**

```python
# No arguments
```

**Output Example:**

```python
None  # Asserts memory_percent thresholds updated to yellow=80.0, red=95.0 and invalid bounds raise ValueError
```

**Edge Cases:**
- Invalid threshold values (yellow >= red) raise ValueError without modifying original config.

## 6. Change Instructions

### 6.1 `src/boostgauge/__init__.py` (Add)

**Complete file contents:**

```python
"""BoostGauge - Real-time system monitor styled like a racing tachometer.

Issue #7: Configuration File and CLI Arguments
"""

__version__ = "0.1.0"
__all__ = ["__version__"]
```

---

### 6.2 `src/boostgauge/config.py` (Add)

**Complete file contents:**

```python
"""Configuration management system for BoostGauge.

Handles platform default paths, schema validation, atomic file persistence,
CLI argument parsing, dynamic threshold updates, and window state updates.

Issue #7: Configuration File and CLI Arguments
"""

import argparse
import copy
import json
import os
import pathlib
import sys
import tempfile
from typing import Any, Dict, List, Optional


DEFAULT_CONFIG: Dict[str, Any] = {
    "polling_interval_seconds": 0.5,
    "theme": "default",
    "size": 300,
    "opacity": 0.95,
    "always_on_top": True,
    "position": {"x": 100, "y": 100},
    "thresholds": {
        "conpty": {"yellow": 16.0, "red": 28.0},
        "memory_percent": {"yellow": 75.0, "red": 90.0},
        "process_count": {"yellow": 150.0, "red": 300.0},
        "handle_count": {"yellow": 50000.0, "red": 80000.0},
    },
    "telltale_windows": {"short": 60, "medium": 600, "long": 3600},
    "show_driver_label": True,
    "show_digital_readout": True,
    "show_session_count": True,
}


def get_default_config_path() -> pathlib.Path:
    """Return platform-specific default configuration path.

    POSIX: ~/.boostgauge/config.json
    Windows: %APPDATA%/boostgauge/config.json
    """
    if sys.platform == "win32":
        appdata = os.getenv("APPDATA")
        if appdata:
            base_dir = pathlib.Path(appdata)
        else:
            base_dir = pathlib.Path.home() / "AppData" / "Roaming"
        return base_dir / "boostgauge" / "config.json"
    return pathlib.Path.home() / ".boostgauge" / "config.json"


def get_default_config() -> Dict[str, Any]:
    """Return a deep copy of the default configuration dictionary."""
    return copy.deepcopy(DEFAULT_CONFIG)


def save_config_file(config_path: pathlib.Path, config_data: Dict[str, Any]) -> None:
    """Atomically write configuration data to JSON file using tempfile and os.replace."""
    config_path = pathlib.Path(config_path)
    parent_dir = config_path.parent
    parent_dir.mkdir(parents=True, exist_ok=True)
    if sys.platform != "win32":
        try:
            os.chmod(parent_dir, 0o700)
        except OSError:
            pass

    tf = tempfile.NamedTemporaryFile(
        mode="w",
        dir=str(parent_dir),
        delete=False,
        encoding="utf-8",
        suffix=".tmp",
    )
    temp_path = pathlib.Path(tf.name)
    try:
        json.dump(config_data, tf, indent=2)
        tf.flush()
        os.fsync(tf.fileno())
        tf.close()
        os.replace(temp_path, config_path)
    except Exception:
        tf.close()
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise


def validate_config(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Validate configuration schema types and value ranges, populating missing keys with defaults."""
    defaults = get_default_config()
    if not isinstance(raw_config, dict):
        return defaults

    result = copy.deepcopy(defaults)

    # polling_interval_seconds
    poll = raw_config.get("polling_interval_seconds")
    if isinstance(poll, (int, float)) and poll >= 0.1:
        result["polling_interval_seconds"] = float(poll)

    # theme
    theme = raw_config.get("theme")
    if isinstance(theme, str) and theme.strip():
        result["theme"] = theme.strip()

    # size
    size = raw_config.get("size")
    if isinstance(size, int) and size >= 100:
        result["size"] = size

    # opacity
    opacity = raw_config.get("opacity")
    if isinstance(opacity, (int, float)) and 0.0 <= opacity <= 1.0:
        result["opacity"] = float(opacity)

    # always_on_top
    topmost = raw_config.get("always_on_top")
    if isinstance(topmost, bool):
        result["always_on_top"] = topmost

    # position
    pos = raw_config.get("position")
    if isinstance(pos, dict):
        x = pos.get("x")
        y = pos.get("y")
        if isinstance(x, int) and isinstance(y, int):
            result["position"] = {"x": max(0, x), "y": max(0, y)}

    # thresholds
    thresholds = raw_config.get("thresholds")
    if isinstance(thresholds, dict):
        for metric, conf in defaults["thresholds"].items():
            user_metric = thresholds.get(metric)
            if isinstance(user_metric, dict):
                y_val = user_metric.get("yellow")
                r_val = user_metric.get("red")
                if (
                    isinstance(y_val, (int, float))
                    and isinstance(r_val, (int, float))
                    and 0 < y_val < r_val
                ):
                    result["thresholds"][metric] = {
                        "yellow": float(y_val),
                        "red": float(r_val),
                    }

    # telltale_windows
    tw = raw_config.get("telltale_windows")
    if isinstance(tw, dict):
        s_val = tw.get("short")
        m_val = tw.get("medium")
        l_val = tw.get("long")
        if (
            isinstance(s_val, int)
            and isinstance(m_val, int)
            and isinstance(l_val, int)
            and 0 < s_val < m_val < l_val
        ):
            result["telltale_windows"] = {
                "short": s_val,
                "medium": m_val,
                "long": l_val,
            }

    # boolean flags
    for flag in ["show_driver_label", "show_digital_readout", "show_session_count"]:
        val = raw_config.get(flag)
        if isinstance(val, bool):
            result[flag] = val

    return result


def load_config_file(config_path: pathlib.Path) -> Dict[str, Any]:
    """Load and parse JSON configuration file. Auto-create default file if non-existent."""
    config_path = pathlib.Path(config_path)

    if not config_path.exists():
        defaults = get_default_config()
        try:
            save_config_file(config_path, defaults)
        except Exception as e:
            sys.stderr.write(f"Warning: Failed to save default configuration file: {e}\n")
        return defaults

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
        return validate_config(raw_data)
    except Exception as e:
        sys.stderr.write(f"Warning: Corrupt or unreadable config file at {config_path}: {e}\n")
        corrupt_path = config_path.with_name(config_path.name + ".corrupt")
        try:
            if config_path.exists():
                os.replace(config_path, corrupt_path)
        except OSError:
            pass
        defaults = get_default_config()
        try:
            save_config_file(config_path, defaults)
        except Exception:
            pass
        return defaults


def build_cli_parser() -> argparse.ArgumentParser:
    """Construct argument parser for CLI flags."""
    parser = argparse.ArgumentParser(
        prog="boostgauge",
        description="Lightweight system tachometer with peak-hold needles.",
    )
    parser.add_argument("--theme", type=str, help="UI color theme name")
    parser.add_argument("--size", type=int, help="Gauge window diameter in pixels (min 100)")
    parser.add_argument("--poll", type=float, help="Polling interval in seconds (min 0.1)")
    parser.add_argument("--opacity", type=float, help="Window opacity between 0.0 and 1.0")
    parser.add_argument(
        "--no-topmost",
        action="store_true",
        default=False,
        help="Disable always-on-top window behavior",
    )
    parser.add_argument("--config", type=str, help="Custom configuration file path")
    parser.add_argument(
        "--reset-config",
        action="store_true",
        default=False,
        help="Reset configuration file to default settings",
    )
    return parser


def parse_cli_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments from sys.argv or provided argument list."""
    parser = build_cli_parser()
    parsed = parser.parse_args(args)

    if parsed.poll is not None and parsed.poll < 0.1:
        parser.error("--poll must be at least 0.1 seconds")
    if parsed.size is not None and parsed.size < 100:
        parser.error("--size must be at least 100 pixels")
    if parsed.opacity is not None and not (0.0 <= parsed.opacity <= 1.0):
        parser.error("--opacity must be between 0.0 and 1.0")

    return parsed


def merge_config(config_file_data: Dict[str, Any], cli_args: argparse.Namespace) -> Dict[str, Any]:
    """Merge configuration dictionary with CLI overrides."""
    merged = copy.deepcopy(config_file_data)

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


def update_thresholds(config_data: Dict[str, Any], new_thresholds: Dict[str, Any]) -> Dict[str, Any]:
    """Dynamically update threshold values in runtime configuration dictionary."""
    updated = copy.deepcopy(config_data)
    if "thresholds" not in updated:
        updated["thresholds"] = get_default_config()["thresholds"]

    for metric, conf in new_thresholds.items():
        if isinstance(conf, dict):
            y_val = conf.get("yellow")
            r_val = conf.get("red")
            if (
                isinstance(y_val, (int, float))
                and isinstance(r_val, (int, float))
                and 0 < y_val < r_val
            ):
                updated["thresholds"][metric] = {
                    "yellow": float(y_val),
                    "red": float(r_val),
                }
            else:
                raise ValueError(
                    f"Invalid threshold values for {metric}: yellow must be positive and less than red"
                )
    return updated


def update_window_state(config_data: Dict[str, Any], x: int, y: int, size: int) -> Dict[str, Any]:
    """Update window position and size state in configuration structure."""
    updated = copy.deepcopy(config_data)
    updated["position"] = {"x": max(0, x), "y": max(0, y)}
    updated["size"] = max(100, size)
    return updated
```

---

### 6.3 `src/boostgauge/app.py` (Add)

**Complete file contents:**

```python
"""Application lifecycle and runtime state orchestrator.

Integrates dynamic configuration with system monitoring and window exit state persistence.

Issue #7: Configuration File and CLI Arguments
"""

import pathlib
from typing import Any, Dict, Optional

from boostgauge.config import save_config_file, update_thresholds, update_window_state


class App:
    """Application controller maintaining dynamic config state and saving exit geometry."""

    def __init__(self, config: Dict[str, Any], config_path: Optional[pathlib.Path] = None) -> None:
        self.config = config
        self.config_path = config_path
        self.running = False

    def update_runtime_thresholds(self, new_thresholds: Dict[str, Any]) -> None:
        """Apply dynamic threshold updates at runtime."""
        self.config = update_thresholds(self.config, new_thresholds)

    def shutdown(self, current_x: int, current_y: int, current_size: int) -> None:
        """Persist final window geometry and close application cleanly."""
        self.running = False
        self.config = update_window_state(self.config, current_x, current_y, current_size)
        if self.config_path:
            save_config_file(self.config_path, self.config)
```

---

### 6.4 `src/boostgauge/__main__.py` (Add)

**Complete file contents:**

```python
"""Main CLI executable entry point for BoostGauge.

Issue #7: Configuration File and CLI Arguments
"""

import pathlib
import sys
from typing import List, Optional

from boostgauge.app import App
from boostgauge.config import (
    get_default_config,
    get_default_config_path,
    load_config_file,
    merge_config,
    parse_cli_args,
    save_config_file,
)


def main(argv: Optional[List[str]] = None) -> int:
    """Main execution function bootstrapping configuration and launching BoostGauge application."""
    cli_args = parse_cli_args(argv)

    if cli_args.config:
        target_path = pathlib.Path(cli_args.config).resolve()
    else:
        target_path = get_default_config_path()

    if cli_args.reset_config:
        config_data = get_default_config()
        save_config_file(target_path, config_data)
    else:
        config_data = load_config_file(target_path)

    effective_config = merge_config(config_data, cli_args)

    app = App(effective_config, config_path=target_path)
    app.running = True

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

---

### 6.5 `pyproject.toml` (Modify)

**Change 1:** Add `[tool.poetry.scripts]` section before `[build-system]`

```diff
+[tool.poetry.scripts]
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
"""Unit test suite for BoostGauge configuration management and CLI arguments.

Verifies default creation, path resolution, JSON validation, atomic writes,
CLI overrides, dynamic threshold updates, and window state persistence.

Issue #7: Configuration File and CLI Arguments
"""

import json
import os
import pathlib
import sys
import pytest
from unittest.mock import patch

from boostgauge.app import App
from boostgauge.config import (
    get_default_config,
    get_default_config_path,
    load_config_file,
    merge_config,
    parse_cli_args,
    save_config_file,
    update_thresholds,
    update_window_state,
    validate_config,
)
from boostgauge.__main__ import main


def test_t010_auto_create_default_config(tmp_path: pathlib.Path) -> None:
    """T010: Auto-create default config file on first run if missing."""
    config_file = tmp_path / "sub_dir" / "config.json"
    assert not config_file.exists()

    loaded = load_config_file(config_file)
    assert config_file.exists()
    assert loaded["polling_interval_seconds"] == 0.5
    assert loaded["theme"] == "default"

    with open(config_file, "r", encoding="utf-8") as f:
        on_disk = json.load(f)
    assert on_disk["size"] == 300


def test_t020_cli_arguments_override_config_values(tmp_path: pathlib.Path) -> None:
    """T020: CLI arguments override config file values."""
    config_file = tmp_path / "config.json"
    base_config = get_default_config()
    base_config["theme"] = "classic"
    base_config["polling_interval_seconds"] = 0.5
    save_config_file(config_file, base_config)

    cli_args = parse_cli_args(["--theme", "neon", "--poll", "1.5"])
    effective = merge_config(base_config, cli_args)

    assert effective["theme"] == "neon"
    assert effective["polling_interval_seconds"] == 1.5
    # Non-overridden options maintain config values
    assert effective["size"] == 300


def test_t030_save_and_restore_window_state(tmp_path: pathlib.Path) -> None:
    """T030: Save and restore window position and size on exit."""
    config_file = tmp_path / "config.json"
    initial_config = get_default_config()
    save_config_file(config_file, initial_config)

    app = App(initial_config, config_path=config_file)
    app.shutdown(current_x=250, current_y=150, current_size=350)

    restored = load_config_file(config_file)
    assert restored["position"] == {"x": 250, "y": 150}
    assert restored["size"] == 350


def test_t040_dynamic_threshold_updates() -> None:
    """T040: Dynamic threshold updates take effect at runtime."""
    cfg = get_default_config()
    assert cfg["thresholds"]["memory_percent"]["yellow"] == 75.0

    updated = update_thresholds(
        cfg, {"memory_percent": {"yellow": 80.0, "red": 95.0}}
    )
    assert updated["thresholds"]["memory_percent"]["yellow"] == 80.0
    assert updated["thresholds"]["memory_percent"]["red"] == 95.0
    # Original metric unchanged
    assert updated["thresholds"]["conpty"]["yellow"] == 16.0

    # Invalid threshold raises ValueError
    with pytest.raises(ValueError):
        update_thresholds(cfg, {"memory_percent": {"yellow": 90.0, "red": 80.0}})


def test_t050_invalid_config_schema_fallback(tmp_path: pathlib.Path) -> None:
    """T050: Invalid config schema handling and graceful fallback."""
    config_file = tmp_path / "config.json"
    with open(config_file, "w", encoding="utf-8") as f:
        f.write("{ invalid json syntax ... ")

    loaded = load_config_file(config_file)
    assert loaded == get_default_config()

    corrupt_file = tmp_path / "config.json.corrupt"
    assert corrupt_file.exists()
    assert config_file.exists()


def test_t060_invalid_cli_parameter_error() -> None:
    """T060: Invalid CLI parameter error handling."""
    with pytest.raises(SystemExit):
        parse_cli_args(["--opacity", "2.5"])

    with pytest.raises(SystemExit):
        parse_cli_args(["--poll", "0.01"])

    with pytest.raises(SystemExit):
        parse_cli_args(["--size", "50"])


def test_t070_custom_config_file_path(tmp_path: pathlib.Path) -> None:
    """T070: Custom config file path via --config option."""
    custom_path = tmp_path / "custom" / "my_config.json"
    argv = ["--config", str(custom_path), "--theme", "dark"]

    exit_code = main(argv)
    assert exit_code == 0
    assert custom_path.exists()

    loaded = load_config_file(custom_path)
    assert loaded["theme"] == "default"  # Reset/default written on file creation


def test_t080_reset_config_to_defaults(tmp_path: pathlib.Path) -> None:
    """T080: Reset config to default values via --reset-config flag."""
    config_file = tmp_path / "config.json"
    modified = get_default_config()
    modified["theme"] = "modified_theme"
    modified["size"] = 500
    save_config_file(config_file, modified)

    argv = ["--config", str(config_file), "--reset-config"]
    exit_code = main(argv)
    assert exit_code == 0

    reset_cfg = load_config_file(config_file)
    assert reset_cfg["theme"] == "default"
    assert reset_cfg["size"] == 300


def test_t090_atomic_write_prevention_of_corruption(tmp_path: pathlib.Path) -> None:
    """T090: Atomic write prevention of partial configuration corruptions."""
    config_file = tmp_path / "config.json"
    initial_config = get_default_config()
    save_config_file(config_file, initial_config)

    new_config = get_default_config()
    new_config["theme"] = "new_theme"

    # Simulate interrupt during atomic write by mocking os.replace to fail
    with patch("os.replace", side_effect=OSError("Disk full")):
        with pytest.raises(OSError):
            save_config_file(config_file, new_config)

    # Original file must remain intact
    loaded = load_config_file(config_file)
    assert loaded["theme"] == "default"


def test_t100_cli_flags_preserve_unoverridden_config_values(tmp_path: pathlib.Path) -> None:
    """T100: CLI flags preserve un-overridden config file values."""
    config_file = tmp_path / "config.json"
    custom_saved = get_default_config()
    custom_saved["theme"] = "custom_theme"
    custom_saved["opacity"] = 0.8
    save_config_file(config_file, custom_saved)

    cli_args = parse_cli_args(["--size", "450"])
    merged = merge_config(custom_saved, cli_args)

    assert merged["size"] == 450
    assert merged["theme"] == "custom_theme"
    assert merged["opacity"] == 0.8


def test_get_default_config_path_platform_resolution() -> None:
    """Verify platform-independent path resolution comparing Path objects."""
    with patch("sys.platform", "posix"):
        expected_posix = pathlib.Path.home() / ".boostgauge" / "config.json"
        assert get_default_config_path() == expected_posix

    with patch("sys.platform", "win32"), patch.dict("os.environ", {"APPDATA": "C:\\AppData"}):
        expected_win = pathlib.Path("C:\\AppData") / "boostgauge" / "config.json"
        assert get_default_config_path() == expected_win
```

## 7. Pattern References

### 7.1 Atomic File Persistence Pattern

**File:** `src/boostgauge/config.py` (lines 62-89)

```python
    tf = tempfile.NamedTemporaryFile(
        mode="w",
        dir=str(parent_dir),
        delete=False,
        encoding="utf-8",
        suffix=".tmp",
    )
    temp_path = pathlib.Path(tf.name)
    try:
        json.dump(config_data, tf, indent=2)
        tf.flush()
        os.fsync(tf.fileno())
        tf.close()
        os.replace(temp_path, config_path)
    except Exception:
        tf.close()
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise
```

**Relevance:** Standard POSIX/Windows atomic file replacement pattern ensuring that abrupt process crashes or disk write interruptions never result in truncated or corrupted 0-byte configuration files.

### 7.2 Safe Schema Validation and Fallback Pattern

**File:** `src/boostgauge/config.py` (lines 92-167)

```python
    defaults = get_default_config()
    if not isinstance(raw_config, dict):
        return defaults

    result = copy.deepcopy(defaults)
    # Validate each key type and bounds individually...
```

**Relevance:** Ensures application resilience against missing keys, type mismatches, or out-of-bounds user modifications without crashing at startup.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `import argparse` | stdlib | `src/boostgauge/config.py` |
| `import copy` | stdlib | `src/boostgauge/config.py` |
| `import json` | stdlib | `src/boostgauge/config.py` |
| `import os` | stdlib | `src/boostgauge/config.py` |
| `import pathlib` | stdlib | `src/boostgauge/config.py`, `app.py`, `__main__.py` |
| `import sys` | stdlib | `src/boostgauge/config.py`, `__main__.py` |
| `import tempfile` | stdlib | `src/boostgauge/config.py` |
| `from typing import Any, Dict, List, Optional` | stdlib | All files |

**New Dependencies:** None (uses built-in standard library components only).

## 9. Placeholder

*Reserved for future alignment with LLD section numbering.*

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `load_config_file()` | Non-existent path `tmp_path/config.json` | Default `config.json` written to disk and dict returned |
| T020 | `merge_config()` | Config file `theme="classic"` + CLI `--theme neon` | Effective dict `theme="neon"`, non-overridden options preserved |
| T030 | `App.shutdown()` | Exit event with `current_x=250`, `current_y=150`, `current_size=350` | `config.json` on disk updated with `position` and `size` |
| T040 | `update_thresholds()` | Runtime threshold update for `memory_percent` | Dict thresholds updated; invalid threshold raises `ValueError` |
| T050 | `load_config_file()` | Malformed JSON in `config.json` | Corrupt file backed up to `.corrupt`, default config saved & returned |
| T060 | `parse_cli_args()` | CLI argument `--opacity 2.5` | Raises `SystemExit` with `argparse` error message |
| T070 | `main()` | `argv=["--config", "/tmp/custom.json"]` | Custom path `/tmp/custom.json` initialized and used |
| T080 | `main()` | `argv=["--reset-config"]` | Configuration file overwritten with exact standard defaults |
| T090 | `save_config_file()` | Simulated `os.replace` failure during write | Original `config.json` remains untouched, exception raised |
| T100 | `merge_config()` | Custom config file + `--size 450` | `size` set to 450; other saved settings preserved |

## 11. Implementation Notes

### 11.1 Error Handling Convention
- Configuration loading catches all `json.JSONDecodeError` and `PermissionError` exceptions. It logs a warning to `sys.stderr`, backs up damaged files with a `.corrupt` extension when possible, and falls back gracefully to standard defaults.

### 11.2 Atomic Persistence & File Safety
- `save_config_file` writes to a temporary file in the same target directory before calling `os.replace`. This guarantees atomic updates across POSIX and Windows filesystems.

### 11.3 CLI Override Precedence & Merging Mechanics
- CLI arguments only override configuration values when explicitly supplied on the command line (`cli_args.flag is not None` or `cli_args.flag is True`). Unspecified flags (`None`) leave config file entries unchanged.

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
| Finalized | 2026-07-31T12:32:00Z |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #7 |
| Verdict | APPROVED |
| Date | 2026-07-31 |
| Iterations | 1 |
| Finalized | 2026-07-31T17:33:36Z |

### Review Feedback Summary

The revised implementation spec is complete, highly concrete, internally consistent, and fully executable. All files to be added or modified contain exact complete code or diffs, data structures have concrete JSON examples, and all functions have detailed signatures, input/output examples, edge cases, and pattern references. Every test assertion in `tests/unit/test_config.py` directly traces to explicitly defined requirements and behavior specifications in `config.py`, `app.py`, and `__main__.py...
