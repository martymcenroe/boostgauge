# Implementation Spec: Feature: configuration file and CLI arguments

<!-- Metadata -->
| Field | Value |
|-------|-------|
| Issue | #7 |
| LLD | `docs/lld/active/LLD-007.md` |
| Generated | 2026-07-15 |
| Status | APPROVED |

## 1. Overview

This implementation spec establishes a robust, zero-dependency configuration system for BoostGauge. It loads user preferences, coordinates, sizes, thresholds, and telltale parameters from a JSON configuration file, overrides them with command-line arguments when provided, validates the merged configuration, and dynamically reloads modified thresholds at runtime using a lightweight file modification time poll.

**Objective:** Implement a local JSON configuration file and command-line argument overrides with robust validations, atomic saving, and runtime reloading without external configuration parsing or file-watching dependencies.

**Success Criteria:**
- Detect and load configurations from `~/.boostgauge/config.json` (Unix) or `%APPDATA%/boostgauge/config.json` (Windows).
- Override file configurations with CLI arguments `--theme`, `--size`, `--poll`, `--opacity`, `--no-topmost`, `--config`, and `--reset-config` correctly.
- Ensure that window position coordinates (x, y) and gauge size are saved atomically to the active configuration file upon window closure.
- Support dynamic reloading of config parameters (e.g. thresholds) when the file is modified at runtime, failing safe to last-known-good configurations if syntax or validation errors are found.
- Implement comprehensive unit and integration test coverage (≥95%) without instantiating `tkinter.Tk()` during testing.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `pyproject.toml` | Modify | Add script entrypoint mapping `boostgauge` command to `boostgauge.app:main`. |
| 2 | `src/boostgauge/config.py` | Add | Configuration management module implementing loading, saving, validation, CLI parsing, and dynamic reloading. |
| 3 | `src/boostgauge/app.py` | Add | Main application entry point initializing configuration and setting up event loops. |
| 4 | `tests/unit/test_config.py` | Add | Unit tests for configuration logic, validations, CLI parsing, and overrides. |
| 5 | `tests/integration/test_config_flow.py` | Add | Integration tests verifying config creation, persistence, and dynamic reloading. |

**Implementation Order Rationale:**
- `pyproject.toml` is modified first to define the CLI entry point.
- `config.py` implements the core configuration loading, overriding, and validation logic, which `app.py` depends on.
- `app.py` is implemented after `config.py` to bootstrap the application, wire up the tkinter event loop, coordinate dynamic config checks, and handle shutdown saves.
- Tests (`tests/unit/test_config.py` and `tests/integration/test_config_flow.py`) are implemented last to verify unit behavior and full end-to-end integration flows.

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

**What changes:** Adds a `[project.scripts]` section immediately following `[project.urls]` to map the CLI command `boostgauge` to the main function in `src/boostgauge/app.py`.

## 4. Data Structures

### 4.1 `AppConfig` and Nested Configurations

**Definition:**

```python
from typing import TypedDict, Dict

class Position(TypedDict):
    x: int
    y: int

class Threshold(TypedDict):
    yellow: float
    red: float

class Thresholds(TypedDict):
    conpty: Threshold
    memory_percent: Threshold
    process_count: Threshold
    handle_count: Threshold

class TelltaleWindows(TypedDict):
    short: int
    medium: int
    long: int

class AppConfig(TypedDict):
    polling_interval_seconds: float
    theme: str
    size: int
    opacity: float
    always_on_top: bool
    position: Position
    thresholds: Thresholds
    telltale_windows: TelltaleWindows
    show_driver_label: bool
    show_digital_readout: bool
    show_session_count: bool
```

**Concrete Example:**

```json
{
  "polling_interval_seconds": 2.0,
  "theme": "dark",
  "size": 256,
  "opacity": 0.85,
  "always_on_top": true,
  "position": {
    "x": 150,
    "y": 200
  },
  "thresholds": {
    "conpty": {
      "yellow": 4.0,
      "red": 8.0
    },
    "memory_percent": {
      "yellow": 80.0,
      "red": 90.0
    },
    "process_count": {
      "yellow": 10.0,
      "red": 20.0
    },
    "handle_count": {
      "yellow": 500.0,
      "red": 1000.0
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
    """Returns the default platform-specific path (~/.boostgauge/config.json or %APPDATA%/boostgauge/config.json)."""
    ...
```

**Input Example:**
```python
# None
```

**Output Example:**
```python
# On Windows:
Path("C:/Users/mcwiz/AppData/Roaming/boostgauge/config.json")
# On Unix:
Path("/home/user/.boostgauge/config.json")
```

**Edge Cases:**
- Missing environment variables like `APPDATA` on Windows -> falls back to user home directory configuration path `~/.boostgauge/config.json`.

---

### 5.2 `get_default_config()`

**File:** `src/boostgauge/config.py`

**Signature:**
```python
def get_default_config() -> Dict[str, Any]:
    """Returns a dict containing standard configuration default values."""
    ...
```

**Input Example:**
```python
# None
```

**Output Example:**
```python
{
    "polling_interval_seconds": 2.0,
    "theme": "dark",
    "size": 256,
    "opacity": 0.85,
    "always_on_top": True,
    "position": {"x": 100, "y": 100},
    "thresholds": {
        "conpty": {"yellow": 4.0, "red": 8.0},
        "memory_percent": {"yellow": 80.0, "red": 90.0},
        "process_count": {"yellow": 10.0, "red": 20.0},
        "handle_count": {"yellow": 500.0, "red": 1000.0}
    },
    "telltale_windows": {"short": 60, "medium": 600, "long": 3600},
    "show_driver_label": True,
    "show_digital_readout": True,
    "show_session_count": True
}
```

**Edge Cases:**
- Returns a fresh dictionary reference on every call to avoid mutable defaults corruption.

---

### 5.3 `validate_config()`

**File:** `src/boostgauge/config.py`

**Signature:**
```python
def validate_config(config_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Validates types and value bounds of configuration fields. Raises ValueError or TypeError."""
    ...
```

**Input Example:**
```python
config_dict = {
    "polling_interval_seconds": 2.0,
    "theme": "dark",
    "size": 256,
    "opacity": 1.5,  # Invalid value (should be between 0.1 and 1.0)
    "always_on_top": True
}
```

**Output Example:**
```python
# Raises ValueError: "opacity must be between 0.1 and 1.0"
```

**Edge Cases:**
- `polling_interval_seconds <= 0` -> raises `ValueError`.
- `size` is not an `int` or out of range `[128, 1024]` -> raises `ValueError`/`TypeError`.
- `opacity` is not a `float` or out of range `[0.1, 1.0]` -> raises `ValueError`/`TypeError`.
- Thresholds are negative, or `yellow >= red` -> raises `ValueError`.
- `telltale_windows` intervals are negative, or `short >= medium` or `medium >= long` -> raises `ValueError`.

---

### 5.4 `load_config()`

**File:** `src/boostgauge/config.py`

**Signature:**
```python
def load_config(path: Path) -> Dict[str, Any]:
    """Reads configuration file. Creates file with defaults if not exists."""
    ...
```

**Input Example:**
```python
path = Path("/home/user/.boostgauge/config.json")
```

**Output Example:**
```python
{
    "polling_interval_seconds": 2.0,
    "theme": "dark",
    ...
}
```

**Edge Cases:**
- File does not exist -> creates parent directories, saves default configuration to path, and returns defaults.
- JSON structure is corrupted (invalid syntax) -> raises `ValueError` with clear syntax details.
- Path permission error -> propagates filesystem exceptions.

---

### 5.5 `save_config()`

**File:** `src/boostgauge/config.py`

**Signature:**
```python
def save_config(config: Dict[str, Any], path: Path) -> None:
    """Saves the config state atomically using a temporary file and atomic replace."""
    ...
```

**Input Example:**
```python
config = {"polling_interval_seconds": 2.0, "theme": "dark", "size": 300}
path = Path("/home/user/.boostgauge/config.json")
```

**Output Example:**
```python
# None (writes config json atomically to disk)
```

**Edge Cases:**
- Disk is full -> fails to replace, cleans up temp file, and raises `OSError` without truncating original file.
- Permission issues on write -> propagates error safely without corrupting original file.

---

### 5.6 `parse_cli_args()`

**File:** `src/boostgauge/config.py`

**Signature:**
```python
def parse_cli_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parses command-line arguments using argparse."""
    ...
```

**Input Example:**
```python
args = ["--theme", "light", "--size", "300", "--no-topmost"]
```

**Output Example:**
```python
Namespace(theme='light', size=300, poll=None, opacity=None, no_topmost=True, config=None, reset_config=False)
```

**Edge Cases:**
- Missing options -> defaults to `None` for override parameters and `False` for flags.
- Invalid options (e.g. `--size abc`) -> prints usage information to stderr and exits with code 2.

---

### 5.7 `override_config_with_cli()`

**File:** `src/boostgauge/config.py`

**Signature:**
```python
def override_config_with_cli(config: Dict[str, Any], cli_args: argparse.Namespace) -> Dict[str, Any]:
    """Merges loaded configuration dictionary with non-None CLI argument overrides."""
    ...
```

**Input Example:**
```python
config = {"theme": "dark", "size": 256, "always_on_top": True, "polling_interval_seconds": 2.0}
cli_args = argparse.Namespace(theme="light", size=None, poll=1.5, opacity=None, no_topmost=True)
```

**Output Example:**
```python
{"theme": "light", "size": 256, "always_on_top": False, "polling_interval_seconds": 1.5}
```

**Edge Cases:**
- `cli_args` attributes are `None` -> corresponding keys in `config` are left unmodified.
- `cli_args.no_topmost` is `True` -> forces `always_on_top` to `False`.

---

### 5.8 `ConfigManager` Methods

**File:** `src/boostgauge/config.py`

**Signatures:**
```python
class ConfigManager:
    def __init__(self, config_path: Optional[Path] = None, cli_args: Optional[argparse.Namespace] = None) -> None:
        """Initializes configuration settings and tracks file modification times."""
        ...

    def load(self) -> Dict[str, Any]:
        """Loads file configuration, merges CLI arguments, validates the result, and stores state."""
        ...

    def save(self) -> None:
        """Saves current state to the configured configuration file."""
        ...

    def check_and_reload(self) -> bool:
        """Checks configuration file modification time. Reloads if changed. Returns True if reloaded."""
        ...

    def get(self, key: str) -> Any:
        """Retrieves a configuration value by key."""
        ...

    def update_position_and_size(self, x: int, y: int, size: int) -> None:
        """Updates window coordinates and size in memory."""
        ...
```

**Input/Output Examples:**
```python
mgr = ConfigManager(config_path=Path("custom.json"), cli_args=cli_args)
mgr.load()  # -> returns merged configuration dictionary
mgr.get("theme")  # -> "light"
mgr.update_position_and_size(150, 200, 350)
mgr.save()  # -> updates custom.json atomically
mgr.check_and_reload()  # -> True if custom.json was modified on disk and successfully reloaded, else False
```

**Edge Cases:**
- If dynamic reloading in `check_and_reload` fails validation or throws `JSONDecodeError`, the error is intercepted, a warning is printed to stderr, and the last-known-good in-memory configuration is preserved.

## 6. Change Instructions

### 6.1 `src/boostgauge/config.py` (Add)

**Complete file contents:**

```python
"""Configuration management module.

Issue #7: Feature: configuration file and CLI arguments
"""

import argparse
import json
import logging
import os
from pathlib import Path
import shutil
import sys
from typing import Any, Dict, List, Optional

logger = logging.getLogger("boostgauge.config")


def get_default_config_path() -> Path:
    """Returns the default platform-specific path (~/.boostgauge/config.json or %APPDATA%/boostgauge/config.json)."""
    if os.name == "nt":
        app_data = os.environ.get("APPDATA")
        if app_data:
            return Path(app_data).resolve() / "boostgauge" / "config.json"
    return Path("~/.boostgauge/config.json").expanduser().resolve()


def get_default_config() -> Dict[str, Any]:
    """Returns a dict containing standard configuration default values."""
    return {
        "polling_interval_seconds": 2.0,
        "theme": "dark",
        "size": 256,
        "opacity": 0.85,
        "always_on_top": True,
        "position": {"x": 100, "y": 100},
        "thresholds": {
            "conpty": {"yellow": 4.0, "red": 8.0},
            "memory_percent": {"yellow": 80.0, "red": 90.0},
            "process_count": {"yellow": 10.0, "red": 20.0},
            "handle_count": {"yellow": 500.0, "red": 1000.0},
        },
        "telltale_windows": {"short": 60, "medium": 600, "long": 3600},
        "show_driver_label": True,
        "show_digital_readout": True,
        "show_session_count": True,
    }


def validate_config(config_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Validates types and value bounds of configuration fields. Raises ValueError or TypeError."""
    if not isinstance(config_dict, dict):
        raise TypeError("Configuration must be a dictionary")

    # Validate polling interval
    poll = config_dict.get("polling_interval_seconds")
    if not isinstance(poll, (int, float)) or isinstance(poll, bool):
        raise TypeError("polling_interval_seconds must be a float or integer")
    if poll <= 0:
        raise ValueError("polling_interval_seconds must be greater than zero")

    # Validate theme
    theme = config_dict.get("theme")
    if not isinstance(theme, str):
        raise TypeError("theme must be a string")
    if not theme.strip():
        raise ValueError("theme cannot be empty")

    # Validate size
    size = config_dict.get("size")
    if not isinstance(size, int) or isinstance(size, bool):
        raise TypeError("size must be an integer")
    if not (128 <= size <= 1024):
        raise ValueError("size must be between 128 and 1024")

    # Validate opacity
    opacity = config_dict.get("opacity")
    if not isinstance(opacity, (int, float)) or isinstance(opacity, bool):
        raise TypeError("opacity must be a float or integer")
    if not (0.1 <= opacity <= 1.0):
        raise ValueError("opacity must be between 0.1 and 1.0")

    # Validate always_on_top
    always_on_top = config_dict.get("always_on_top")
    if not isinstance(always_on_top, bool):
        raise TypeError("always_on_top must be a boolean")

    # Validate position
    position = config_dict.get("position")
    if not isinstance(position, dict):
        raise TypeError("position must be a dictionary")
    for key in ("x", "y"):
        val = position.get(key)
        if not isinstance(val, int) or isinstance(val, bool):
            raise TypeError(f"position.{key} must be an integer")

    # Validate thresholds
    thresholds = config_dict.get("thresholds")
    if not isinstance(thresholds, dict):
        raise TypeError("thresholds must be a dictionary")
    for key in ("conpty", "memory_percent", "process_count", "handle_count"):
        t_val = thresholds.get(key)
        if not isinstance(t_val, dict):
            raise TypeError(f"thresholds.{key} must be a dictionary")
        for subkey in ("yellow", "red"):
            val = t_val.get(subkey)
            if not isinstance(val, (int, float)) or isinstance(val, bool):
                raise TypeError(f"thresholds.{key}.{subkey} must be a float or integer")
            if val < 0:
                raise ValueError(f"thresholds.{key}.{subkey} cannot be negative")
        if t_val["yellow"] >= t_val["red"]:
            raise ValueError(
                f"thresholds.{key}.yellow must be less than thresholds.{key}.red"
            )

    # Validate telltale_windows
    telltale = config_dict.get("telltale_windows")
    if not isinstance(telltale, dict):
        raise TypeError("telltale_windows must be a dictionary")
    for key in ("short", "medium", "long"):
        val = telltale.get(key)
        if not isinstance(val, int) or isinstance(val, bool):
            raise TypeError(f"telltale_windows.{key} must be an integer")
        if val <= 0:
            raise ValueError(f"telltale_windows.{key} must be greater than zero")
    if not (telltale["short"] < telltale["medium"] < telltale["long"]):
        raise ValueError("telltale_windows intervals must satisfy short < medium < long")

    # Validate show flags
    for key in ("show_driver_label", "show_digital_readout", "show_session_count"):
        val = config_dict.get(key)
        if not isinstance(val, bool):
            raise TypeError(f"{key} must be a boolean")

    return config_dict


def load_config(path: Path) -> Dict[str, Any]:
    """Reads configuration file. Creates file with defaults if not exists."""
    resolved_path = path.resolve()
    if not resolved_path.exists():
        default_config = get_default_config()
        save_config(default_config, resolved_path)
        return default_config

    try:
        with open(resolved_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format in config file: {e}")


def save_config(config: Dict[str, Any], path: Path) -> None:
    """Saves the config state atomically using a temporary file and atomic replace."""
    resolved_path = path.resolve()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = resolved_path.with_suffix(".tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        os.replace(tmp_path, resolved_path)
    except Exception as e:
        if tmp_path.exists():
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        raise e


def parse_cli_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parses command-line arguments using argparse."""
    parser = argparse.ArgumentParser(
        description="BoostGauge - racing tachometer system resource monitor"
    )
    parser.add_argument(
        "--theme",
        type=str,
        help="UI color theme (e.g. dark, light)",
    )
    parser.add_argument(
        "--size",
        type=int,
        help="Square gauge visual size in pixels [128-1024]",
    )
    parser.add_argument(
        "--poll",
        type=float,
        help="System resource polling interval in seconds",
    )
    parser.add_argument(
        "--opacity",
        type=float,
        help="Window transparent opacity [0.1-1.0]",
    )
    parser.add_argument(
        "--no-topmost",
        action="store_true",
        help="Disable always-on-top window behavior",
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to custom config.json file",
    )
    parser.add_argument(
        "--reset-config",
        action="store_true",
        help="Reset configuration file to default values",
    )
    return parser.parse_args(args)


def override_config_with_cli(
    config: Dict[str, Any], cli_args: argparse.Namespace
) -> Dict[str, Any]:
    """Merges loaded configuration dictionary with non-None CLI argument overrides."""
    overridden = json.loads(json.dumps(config))  # deep copy
    if cli_args.theme is not None:
        overridden["theme"] = cli_args.theme
    if cli_args.size is not None:
        overridden["size"] = cli_args.size
    if cli_args.poll is not None:
        overridden["polling_interval_seconds"] = cli_args.poll
    if cli_args.opacity is not None:
        overridden["opacity"] = cli_args.opacity
    if cli_args.no_topmost:
        overridden["always_on_top"] = False
    return overridden


class ConfigManager:
    """Encapsulates config loading, dynamic reloading, value retrieval, and exit saving."""

    def __init__(
        self,
        config_path: Optional[Path] = None,
        cli_args: Optional[argparse.Namespace] = None,
    ) -> None:
        """Initializes configuration settings and tracks file modification times."""
        if config_path is not None:
            self.config_path = config_path
        elif cli_args and cli_args.config:
            self.config_path = Path(cli_args.config)
        else:
            self.config_path = get_default_config_path()

        self.config_path = self.config_path.resolve()
        self.cli_args = cli_args
        self._config: Dict[str, Any] = {}
        self._last_mtime: float = 0.0

    def load(self) -> Dict[str, Any]:
        """Loads file configuration, merges CLI arguments, validates the result, and stores state."""
        raw_config = load_config(self.config_path)
        if self.cli_args:
            raw_config = override_config_with_cli(raw_config, self.cli_args)
        validate_config(raw_config)
        self._config = raw_config
        self._last_mtime = self.config_path.stat().st_mtime
        return self._config

    def save(self) -> None:
        """Saves current state to the configured configuration file."""
        save_config(self._config, self.config_path)
        self._last_mtime = self.config_path.stat().st_mtime

    def check_and_reload(self) -> bool:
        """Checks configuration file modification time. Reloads if changed. Returns True if reloaded."""
        try:
            if not self.config_path.exists():
                return False
            current_mtime = self.config_path.stat().st_mtime
            if current_mtime <= self._last_mtime:
                return False

            self._last_mtime = current_mtime
            with open(self.config_path, "r", encoding="utf-8") as f:
                new_raw = json.load(f)

            if self.cli_args:
                new_raw = override_config_with_cli(new_raw, self.cli_args)

            validate_config(new_raw)
            self._config = new_raw
            return True
        except Exception as e:
            print(
                f"Warning: Configuration reload failed, retaining previous configuration. Error: {e}",
                file=sys.stderr,
            )
            return False

    def get(self, key: str) -> Any:
        """Retrieves a configuration value by key."""
        return self._config[key]

    def update_position_and_size(self, x: int, y: int, size: int) -> None:
        """Updates window coordinates and size in memory."""
        self._config["position"]["x"] = x
        self._config["position"]["y"] = y
        self._config["size"] = size
```

---

### 6.2 `pyproject.toml` (Modify)

**Change 1:** Add the `[project.scripts]` entrypoint block immediately after `[project.urls]` (line 24)

```diff
 [project.urls]
 Homepage = "https://boostgauge.martymcenroe.ai"
 Repository = "https://github.com/martymcenroe/boostgauge"
 Documentation = "https://github.com/martymcenroe/boostgauge/wiki"
 Issues = "https://github.com/martymcenroe/boostgauge/issues"
 "Built with AssemblyZero" = "https://github.com/martymcenroe/AssemblyZero"
 
+[project.scripts]
+boostgauge = "boostgauge.app:main"
+
 [build-system]
 requires = ["poetry-core>=2.0.0,<3.0.0"]
 build-backend = "poetry.core.masonry.api"
```

---

### 6.3 `src/boostgauge/app.py` (Add)

**Complete file contents:**

```python
"""Main application entry point.

Issue #7: Feature: configuration file and CLI arguments
"""

import re
import sys
import tkinter as tk
from pathlib import Path

from boostgauge.config import (
    ConfigManager,
    get_default_config,
    get_default_config_path,
    parse_cli_args,
    save_config,
)


def main() -> None:
    """Bootstrap application execution flow."""
    cli_args = parse_cli_args()

    # Determine targeted configuration path
    config_path = (
        Path(cli_args.config) if cli_args.config else get_default_config_path()
    )

    # Handle reset command-line request
    if cli_args.reset_config:
        try:
            default_conf = get_default_config()
            save_config(default_conf, config_path)
            print(f"Configuration successfully reset at: {config_path}")
            sys.exit(0)
        except Exception as e:
            print(
                f"Error resetting configuration file: {e}",
                file=sys.stderr,
            )
            sys.exit(1)

    # Initialize configuration manager
    config_mgr = ConfigManager(config_path=config_path, cli_args=cli_args)
    try:
        config_mgr.load()
    except Exception as e:
        print(f"Fatal error loading configuration: {e}", file=sys.stderr)
        sys.exit(1)

    # Initialize Tkinter GUI window shell (per test strategy, Tk is NOT inside test suites)
    root = tk.Tk()
    root.title("BoostGauge")

    # Get UI settings
    size = config_mgr.get("size")
    pos_x = config_mgr.get("position")["x"]
    pos_y = config_mgr.get("position")["y"]
    opacity = config_mgr.get("opacity")
    always_on_top = config_mgr.get("always_on_top")

    # Configure Tk window geometry
    root.geometry(f"{size}x{size}+{pos_x}+{pos_y}")
    root.resizable(False, False)
    root.attributes("-alpha", opacity)
    root.attributes("-topmost", always_on_top)

    # Simple placeholder UI label (gauge styling handled in future tickets)
    label = tk.Label(
        root,
        text=f"BoostGauge ({config_mgr.get('theme')})",
        font=("Arial", 12),
    )
    label.pack(expand=True)

    # Polling ticks to dynamically inspect configurations
    def poll_config_reload() -> None:
        if config_mgr.check_and_reload():
            # Apply dynamic updates (theme, opacity, topmost)
            root.attributes("-alpha", config_mgr.get("opacity"))
            root.attributes("-topmost", config_mgr.get("always_on_top"))
            label.config(text=f"BoostGauge ({config_mgr.get('theme')})")
        # Poll every 2000 milliseconds (2 seconds)
        root.after(2000, poll_config_reload)

    # Window closure logic: query coordinates and size then save to configuration file
    def on_window_close() -> None:
        try:
            geometry_str = root.geometry()
            # Parse size and positioning from Tk's geometry format: WxH+X+Y or WxH-X-Y
            match = re.match(r"^(\d+)x(\d+)([-+]\d+)([-+]\d+)$", geometry_str)
            if match:
                width = int(match.group(1))
                x_coord = int(match.group(3))
                y_coord = int(match.group(4))
                config_mgr.update_position_and_size(x_coord, y_coord, width)
                config_mgr.save()
        except Exception as e:
            print(
                f"Warning: Failed to save position and size metrics on close: {e}",
                file=sys.stderr,
            )
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_window_close)
    root.after(2000, poll_config_reload)
    root.mainloop()


if __name__ == "__main__":
    main()
```

---

### 6.4 `tests/unit/test_config.py` (Add)

**Complete file contents:**

```python
"""Unit tests for configuration manager and CLI argument mapping logic.

Ref: docs/design/0001-test-strategy.md
Constraint: No tkinter.Tk() in unit tests.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Generator
import pytest

from boostgauge.config import (
    ConfigManager,
    get_default_config,
    get_default_config_path,
    load_config,
    override_config_with_cli,
    parse_cli_args,
    save_config,
    validate_config,
)


@pytest.fixture
def temp_config_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Provides a temporary config file path."""
    yield tmp_path / "config.json"


def test_default_config_path() -> None:
    """Verifies resolved platform configuration paths."""
    path = get_default_config_path()
    assert path.name == "config.json"
    assert "boostgauge" in path.parts or ".boostgauge" in path.parts


def test_default_config_structure() -> None:
    """Verifies that the generated defaults dict matches schema properties."""
    conf = get_default_config()
    assert conf["polling_interval_seconds"] == 2.0
    assert conf["theme"] == "dark"
    assert conf["size"] == 256
    assert conf["opacity"] == 0.85
    assert conf["always_on_top"] is True
    assert conf["position"]["x"] == 100
    assert conf["position"]["y"] == 100
    assert conf["thresholds"]["conpty"]["yellow"] == 4.0
    assert conf["thresholds"]["conpty"]["red"] == 8.0


def test_validate_config_valid() -> None:
    """Ensures valid configs pass schema validation."""
    valid_conf = get_default_config()
    validated = validate_config(valid_conf)
    assert validated == valid_conf


def test_validate_config_invalid_types() -> None:
    """Ensures validation fails on invalid property values or types."""
    bad_conf = get_default_config()

    # Invalid interval
    bad_conf["polling_interval_seconds"] = -1.0
    with pytest.raises(ValueError):
        validate_config(bad_conf)
    bad_conf["polling_interval_seconds"] = "invalid"
    with pytest.raises(TypeError):
        validate_config(bad_conf)

    # Invalid size
    bad_conf = get_default_config()
    bad_conf["size"] = 100  # < 128
    with pytest.raises(ValueError):
        validate_config(bad_conf)

    # Invalid opacity
    bad_conf = get_default_config()
    bad_conf["opacity"] = 1.5  # > 1.0
    with pytest.raises(ValueError):
        validate_config(bad_conf)

    # Invalid thresholds
    bad_conf = get_default_config()
    bad_conf["thresholds"]["conpty"]["yellow"] = 10.0
    bad_conf["thresholds"]["conpty"]["red"] = 5.0  # yellow >= red
    with pytest.raises(ValueError):
        validate_config(bad_conf)


def test_load_and_save_config(temp_config_dir: Path) -> None:
    """Ensures loaded config produces default file if path doesn't exist, and loads custom keys."""
    # Creation check
    assert not temp_config_dir.exists()
    config = load_config(temp_config_dir)
    assert temp_config_dir.exists()
    assert config["theme"] == "dark"

    # Custom override write check
    config["theme"] = "light"
    save_config(config, temp_config_dir)

    reloaded = load_config(temp_config_dir)
    assert reloaded["theme"] == "light"


def test_load_config_invalid_json(temp_config_dir: Path) -> None:
    """Ensures JSON parsing issues result in ValueError."""
    temp_config_dir.write_text("{invalid json", encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(temp_config_dir)


def test_parse_cli_args() -> None:
    """Verifies that cli options map to argparse namespaces."""
    parsed = parse_cli_args(
        [
            "--theme",
            "light",
            "--size",
            "500",
            "--poll",
            "1.5",
            "--opacity",
            "0.7",
            "--no-topmost",
        ]
    )
    assert parsed.theme == "light"
    assert parsed.size == 500
    assert parsed.poll == 1.5
    assert parsed.opacity == 0.7
    assert parsed.no_topmost is True


def test_override_config_with_cli() -> None:
    """Verifies overrides blend correctly on config fields."""
    config = get_default_config()
    cli = argparse.Namespace(
        theme="light", size=500, poll=1.5, opacity=0.9, no_topmost=True
    )
    overridden = override_config_with_cli(config, cli)
    assert overridden["theme"] == "light"
    assert overridden["size"] == 500
    assert overridden["polling_interval_seconds"] == 1.5
    assert overridden["opacity"] == 0.9
    assert overridden["always_on_top"] is False


def test_config_manager_load_save(temp_config_dir: Path) -> None:
    """Ensures ConfigManager parses loaded/saved updates correctly."""
    cli = argparse.Namespace(
        theme="custom-cli",
        size=None,
        poll=None,
        opacity=None,
        no_topmost=False,
        config=str(temp_config_dir),
    )
    mgr = ConfigManager(config_path=temp_config_dir, cli_args=cli)

    loaded = mgr.load()
    assert loaded["theme"] == "custom-cli"
    assert mgr.get("theme") == "custom-cli"

    mgr.update_position_and_size(250, 350, 450)
    mgr.save()

    # Re-verify that position and size saved correctly
    plain_mgr = ConfigManager(config_path=temp_config_dir)
    fresh_load = plain_mgr.load()
    assert fresh_load["position"]["x"] == 250
    assert fresh_load["position"]["y"] == 350
    assert fresh_load["size"] == 450
```

---

### 6.5 `tests/integration/test_config_flow.py` (Add)

**Complete file contents:**

```python
"""Integration tests checking multi-layer startup and reload configuration flow.

Ref: docs/design/0001-test-strategy.md
Constraint: No tkinter.Tk() in integration tests.
"""

import argparse
import json
import time
from pathlib import Path
from typing import Generator
import pytest

from boostgauge.config import ConfigManager, get_default_config, save_config


@pytest.fixture
def setup_config_file(tmp_path: Path) -> Generator[Path, None, None]:
    """Generates a reference configuration json on disk."""
    config_path = tmp_path / "config.json"
    conf = get_default_config()
    conf["theme"] = "integration-default"
    conf["opacity"] = 0.50
    save_config(conf, config_path)
    yield config_path


def test_integration_flow_startup_overrides(setup_config_file: Path) -> None:
    """Verifies startup combinations of config file and CLI argument overrides."""
    cli = argparse.Namespace(
        theme="cli-wins",
        size=512,
        poll=None,
        opacity=None,
        no_topmost=True,
        config=str(setup_config_file),
    )
    mgr = ConfigManager(config_path=setup_config_file, cli_args=cli)
    active_conf = mgr.load()

    # CLI overridden properties
    assert active_conf["theme"] == "cli-wins"
    assert active_conf["size"] == 512
    assert active_conf["always_on_top"] is False

    # Standard settings loaded from file
    assert active_conf["opacity"] == 0.50


def test_integration_flow_dynamic_reload(setup_config_file: Path) -> None:
    """Verifies check_and_reload identifies disk modifications and updates states."""
    cli = argparse.Namespace(
        theme=None,
        size=None,
        poll=None,
        opacity=None,
        no_topmost=False,
        config=str(setup_config_file),
    )
    mgr = ConfigManager(config_path=setup_config_file, cli_args=cli)
    mgr.load()

    assert mgr.get("opacity") == 0.50

    # Simulate manual configuration change in background file
    with open(setup_config_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["opacity"] = 0.95
    data["thresholds"]["conpty"]["yellow"] = 12.0
    data["thresholds"]["conpty"]["red"] = 15.0

    # Write new settings back to simulate external save
    time.sleep(0.1)
    save_config(data, setup_config_file)

    # Force check_and_reload to scan modified file
    reloaded = mgr.check_and_reload()
    assert reloaded is True
    assert mgr.get("opacity") == 0.95
    assert mgr.get("thresholds")["conpty"]["yellow"] == 12.0
    assert mgr.get("thresholds")["conpty"]["red"] == 15.0


def test_integration_flow_dynamic_reload_invalid(setup_config_file: Path) -> None:
    """Verifies that invalid configurations on disk do not crash the app and fall back."""
    mgr = ConfigManager(config_path=setup_config_file)
    mgr.load()

    original_opacity = mgr.get("opacity")

    # Rewrite invalid JSON structure to target path
    time.sleep(0.1)
    with open(setup_config_file, "w", encoding="utf-8") as f:
        f.write("{invalid config contents")

    # Reload check should catch parse issue, log warnings, and fail gracefully
    assert mgr.check_and_reload() is False
    assert mgr.get("opacity") == original_opacity

    # Rewrite invalid types
    invalid_data = get_default_config()
    invalid_data["opacity"] = "not a float"
    time.sleep(0.1)
    save_config(invalid_data, setup_config_file)

    # Reload check should reject config types and preserve original in-memory configs
    assert mgr.check_and_reload() is False
    assert mgr.get("opacity") == original_opacity
```

## 7. Pattern References

### 7.1 Dynamic relative path resolution

**File:** `tests/conftest.py` (lines 6-7)

```python
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
```

**Relevance:** Dynamic local path queries relative to files using `pathlib.Path` resolve config paths accurately across developer setups and environments.

### 7.2 Headless Testing Strategy

**File:** `docs/design/0001-test-strategy.md` (lines 48-50)

```python
- **Option C** is the canonical GUI testing approach: the renderer produces
  a `PIL.Image`; `tkinter.Tk()` is never instantiated in tests.
```

**Relevance:** The testing modules avoid calling `tkinter.Tk()` to guarantee compatibility with headless CI environments, checking configuration state modifications in pure isolation.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `import argparse` | stdlib | `config.py`, `app.py`, test files |
| `import json` | stdlib | `config.py`, `app.py`, test files |
| `import logging` | stdlib | `config.py` |
| `import os` | stdlib | `config.py`, `app.py`, test files |
| `import re` | stdlib | `app.py` |
| `import sys` | stdlib | `config.py`, `app.py`, test files |
| `import shutil` | stdlib | `config.py` |
| `import time` | stdlib | `test_config_flow.py` |
| `import tkinter as tk` | stdlib | `app.py` |
| `from pathlib import Path` | stdlib | All files |
| `from typing import Any, Dict, List, Optional, Generator` | stdlib | All files |
| `import pytest` | dev-dependency | `test_config.py`, `test_config_flow.py` |

**New Dependencies:** None (uses standard Python library components for JSON parsing, path operations, logging, and argument parsing).

## 9. Placeholder

*Reserved for future use to maintain alignment with LLD section numbering.*

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `get_default_config_path()` | Unix vs Windows system types | Platform-compliant `.boostgauge/config.json` or `%APPDATA%/boostgauge/config.json` |
| T020 | `load_config()` | Filepath that does not exist | Automatically creates directory and writes defaults file |
| T030 | `parse_cli_args()` | CLI args representing theme, size, poll, opacity, no-topmost, config, reset-config | Returns Namespace populated with CLI values |
| T040 | `override_config_with_cli()` | Loaded configuration + custom CLI arg overrides | Returned merged dictionary where CLI values override config file |
| T050 | `ConfigManager.update_position_and_size()` & `save()` | Shutdown coordinate save with current window geometry values | Active config file updated on disk containing coordinates |
| T060 | `ConfigManager.load()` | Application startup path with existing geometry values | GUI window elements initialized with geometry parameters |
| T070 | `ConfigManager.check_and_reload()` | Modifying config file thresholds externally | Active config thresholds updated at next check cycle |
| T080 | `load_config()` | Reading syntax-invalid JSON file | Raises `ValueError` detailing JSON decode errors |
| T090 | `validate_config()` | Config file with out-of-bounds parameter values (e.g. `opacity=1.5`) | Raises `ValueError` or `TypeError` indicating bounds failures |
| T100 | `app.py` bootstrap | CLI startup with `--reset-config` | Configuration file is overwritten with defaults and exits code 0 |
| T110 | `ConfigManager.check_and_reload()` | Modifying config file with invalid structure at runtime | System returns `False` and retains previous configuration |
| T120 | `ConfigManager.check_and_reload()` | Modifying config file with invalid values at runtime | Warning printed to stderr, system retains old config |

## 11. Implementation Notes

### 11.1 Error Handling Convention
Startup load failures (`load()` throwing `TypeError`, `ValueError`, or `JSONDecodeError`) print descriptive alerts to `sys.stderr` and call `sys.exit(1)` immediately, ensuring bad config setups fail fast. Failures during runtime checking (`check_and_reload()`) log warnings to `sys.stderr` and fail safe, letting the dashboard continue to function with the current configuration.

### 11.2 Atomic Saving Mechanics
The configuration is saved by first writing out to a temporary suffix file (`.tmp`) in the target directory and performing an `os.replace` to point to the actual configuration filepath. This guarantees structural integrity and prevents blank config outputs if power shuts down or process interruption occurs during disk write.

## Completeness Checklist

- [ ] Every "Modify" file has a current state excerpt (Section 3)
- [ ] Every data structure has a concrete JSON/YAML example (Section 4)
- [ ] Every function has input/output examples with realistic values (Section 5)
- [ ] Change instructions are diff-level specific (Section 6)
- [ ] Pattern references include file:line and are verified to exist (Section 7)
- [ ] All imports are listed and verified (Section 8)
- [ ] Test mapping covers all LLD test scenarios (Section 10)

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #7 |
| Verdict | APPROVED |
| Date | 2026-07-15 |
| Iterations | 1 |
| Finalized | 2026-07-15T05:24:24Z |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #7 |
| Verdict | APPROVED |
| Date | 2026-07-15 |
| Iterations | 1 |
| Finalized | 2026-07-15T05:26:33Z |

### Review Feedback Summary

\nThe revised implementation spec is complete, highly concrete, and fully ready for implementation. It includes complete Python source code for the new files, precise `pyproject.toml` entrypoint modifications, robust data validation (correctly supporting negative display coordinates on multi-monitor setups), and comprehensive test coverage aligned with the project's headless testing strategy.\n\n## Blocking Issues\nNo blocking issues found.\n\n## High Priority Issues\nNo high-priority issues fou...
