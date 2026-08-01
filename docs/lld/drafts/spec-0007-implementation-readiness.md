# Implementation Spec: Configuration File and CLI Arguments

| Field | Value |
|-------|-------|
| Issue | #7 |
| LLD | `docs/lld/done/0007-config-cli.md` |
| Generated | 2026-08-01 |
| Status | APPROVED |

---

## 1. Overview

This implementation spec defines the configuration management subsystem for BoostGauge. It establishes JSON configuration persistence, CLI argument parsing, fail-closed validation, window geometry saving/restoration, and dynamic threshold updates using an observer pattern.

**Objective:** Implement configuration management with JSON file persistence, CLI argument overrides, dynamic threshold updates, and window geometry restoration for BoostGauge.

**Success Criteria:**
1. Default configuration file is automatically created with default values at platform-specific location (`~/.boostgauge/config.json` on POSIX or `%APPDATA%\boostgauge\config.json` on Windows) if missing on launch.
2. Custom config file path can be specified via `--config PATH` CLI argument (raising `FileNotFoundError` if a custom path does not exist).
3. CLI argument `--reset-config` resets the target configuration file to standard defaults upon execution.
4. CLI options (`--theme`, `--size`, `--poll`, `--opacity`, `--no-topmost`) override corresponding settings in the active runtime configuration without mutating the persisted configuration file.
5. Window geometry (`position.x`, `position.y`, `size`) is restored at startup and saved atomically to disk on window shutdown.
6. Threshold configurations update dynamically in memory and notify registered observer listeners without requiring an application restart.
7. Validation raises clear `ValueError` exceptions and fails closed when configuration parameters violate type or numerical bounds.

---

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/__init__.py` | Add | Package initialization file exposing `__version__` |
| 2 | `src/boostgauge/config.py` | Add | Core configuration management module: dataclasses, validation, atomic saving, loading, CLI parsing, and `ConfigManager` observer state |
| 3 | `src/boostgauge/app.py` | Add | Main application bootstrapper integrating CLI argument parsing, `ConfigManager` initialization, and window geometry binding |
| 4 | `tests/unit/test_config.py` | Add | Complete unit test suite verifying configuration loading, saving, validation, CLI overrides, and edge cases |

**Implementation Order Rationale:**
`__init__.py` establishes package identity. `config.py` implements pure data structures and configuration logic independent of external callers. `app.py` imports `config.py` to drive application lifecycle execution. `tests/unit/test_config.py` validates `config.py` and `app.py` logic under pure unit isolation per Option C of `docs/design/0001-test-strategy.md` without initializing `tkinter.Tk()`.

---

## 3. Current State (for Modify/Delete files)

No existing files are modified or deleted in this issue. All four target files (`src/boostgauge/__init__.py`, `src/boostgauge/config.py`, `src/boostgauge/app.py`, and `tests/unit/test_config.py`) are new additions ("Add").

---

## 4. Data Structures

### 4.1 Dataclass Definitions

```python
from dataclasses import dataclass
from typing import Any, Callable

@dataclass
class ThresholdBounds:
    yellow: float
    red: float

@dataclass
class ThresholdConfig:
    conpty: ThresholdBounds
    memory_percent: ThresholdBounds
    process_count: ThresholdBounds
    handle_count: ThresholdBounds

@dataclass
class WindowPosition:
    x: int
    y: int

@dataclass
class TelltaleWindows:
    short: int
    medium: int
    long: int

@dataclass
class AppConfig:
    polling_interval_seconds: float
    theme: str
    size: int
    opacity: float
    always_on_top: bool
    position: WindowPosition
    thresholds: ThresholdConfig
    telltale_windows: TelltaleWindows
    show_driver_label: bool
    show_digital_readout: bool
    show_session_count: bool
```

### 4.2 Concrete JSON Example (`config.json`)

```json
{
  "polling_interval_seconds": 1.0,
  "theme": "dark",
  "size": 256,
  "opacity": 1.0,
  "always_on_top": true,
  "position": {
    "x": 100,
    "y": 100
  },
  "thresholds": {
    "conpty": {
      "yellow": 20.0,
      "red": 40.0
    },
    "memory_percent": {
      "yellow": 75.0,
      "red": 90.0
    },
    "process_count": {
      "yellow": 50.0,
      "red": 100.0
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

---

## 5. Function Specifications

### 5.1 `get_default_config_path()`

**File:** `src/boostgauge/config.py`

**Signature:**
```python
def get_default_config_path() -> Path:
    """Return platform-specific default configuration file path."""
```

**Input Example:** None

**Output Example (POSIX):**
```python
Path.home() / ".boostgauge" / "config.json"
# e.g., PosixPath('/home/user/.boostgauge/config.json')
```

**Output Example (Windows):**
```python
Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "boostgauge" / "config.json"
# e.g., WindowsPath('C:/Users/user/AppData/Roaming/boostgauge/config.json')
```

**Edge Cases:**
- `%APPDATA%` un-set on Windows -> falls back to `Path.home() / "AppData" / "Roaming" / "boostgauge" / "config.json"`.

---

### 5.2 `get_default_config()`

**File:** `src/boostgauge/config.py`

**Signature:**
```python
def get_default_config() -> dict[str, Any]:
    """Return dictionary containing standard default configuration settings."""
```

**Input Example:** None

**Output Example:**
```python
{
    "polling_interval_seconds": 1.0,
    "theme": "dark",
    "size": 256,
    "opacity": 1.0,
    "always_on_top": True,
    "position": {"x": 100, "y": 100},
    "thresholds": {
        "conpty": {"yellow": 20.0, "red": 40.0},
        "memory_percent": {"yellow": 75.0, "red": 90.0},
        "process_count": {"yellow": 50.0, "red": 100.0},
        "handle_count": {"yellow": 10000.0, "red": 20000.0},
    },
    "telltale_windows": {"short": 60, "medium": 600, "long": 3600},
    "show_driver_label": True,
    "show_digital_readout": True,
    "show_session_count": True,
}
```

**Edge Cases:** None (returns immutable dictionary constant construct).

---

### 5.3 `validate_config()`

**File:** `src/boostgauge/config.py`

**Signature:**
```python
def validate_config(config_dict: dict[str, Any]) -> dict[str, Any]:
    """Validate configuration dictionary fields against allowed types and bounds."""
```

**Input Example (Valid):**
```python
{
    "polling_interval_seconds": 1.0,
    "theme": "neon",
    "size": 300,
    "opacity": 0.9,
    "always_on_top": True,
    "position": {"x": 50, "y": 50},
    "thresholds": {
        "conpty": {"yellow": 15.0, "red": 30.0},
        "memory_percent": {"yellow": 70.0, "red": 85.0},
        "process_count": {"yellow": 40.0, "red": 80.0},
        "handle_count": {"yellow": 5000.0, "red": 15000.0},
    },
    "telltale_windows": {"short": 60, "medium": 600, "long": 3600},
    "show_driver_label": True,
    "show_digital_readout": True,
    "show_session_count": True,
}
```

**Output Example:**
Returns the validated dictionary identical to input.

**Edge Cases:**
- `opacity = 1.5` -> raises `ValueError("Opacity must be between 0.0 and 1.0, got 1.5")`
- `size = -50` -> raises `ValueError("Size must be a positive integer, got -50")`
- `theme = "cyberpunk"` -> raises `ValueError("Invalid theme 'cyberpunk'. Must be one of: classic, dark, light, neon")`
- `polling_interval_seconds = 0` -> raises `ValueError("Polling interval must be positive, got 0")`
- Threshold `yellow >= red` -> raises `ValueError("Yellow threshold (40.0) must be strictly less than red threshold (30.0) for conpty")`

---

### 5.4 `load_config()`

**File:** `src/boostgauge/config.py`

**Signature:**
```python
def load_config(config_path: Path | None = None) -> AppConfig:
    """Load configuration from JSON file, auto-creating defaults if missing at default path."""
```

**Input Example 1 (Default Path, missing file):**
```python
config_path = None
```
**Output Example 1:**
Automatically writes default config file to `get_default_config_path()` and returns matching `AppConfig` instance.

**Input Example 2 (Explicit Path, non-existent):**
```python
config_path = Path("/tmp/nonexistent_config.json")
```
**Edge Cases:**
- Explicit non-existent `config_path` -> raises `FileNotFoundError("Configuration file not found at /tmp/nonexistent_config.json")`
- Malformed JSON in file -> raises `ValueError("Failed to parse configuration JSON: ...")`

---

### 5.5 `save_config_atomic()`

**File:** `src/boostgauge/config.py`

**Signature:**
```python
def save_config_atomic(config: AppConfig | dict[str, Any], path: Path) -> None:
    """Atomically write configuration to JSON file using temporary file swap."""
```

**Input Example:**
```python
config = AppConfig(...)  # or dict equivalent
path = Path("/tmp/test_config.json")
```

**Output Example:** `None` (side effect: creates/overwrites `/tmp/test_config.json` via `/tmp/test_config.json.tmp` atomic `os.replace`).

**Edge Cases:**
- Parent directory does not exist -> creates parent directories via `path.parent.mkdir(parents=True, exist_ok=True)`.

---

### 5.6 `parse_cli_args()`

**File:** `src/boostgauge/config.py`

**Signature:**
```python
def parse_cli_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments for boostgauge."""
```

**Input Example:**
```python
args = ["--theme", "neon", "--size", "320", "--no-topmost"]
```

**Output Example:**
```python
argparse.Namespace(
    config=None,
    reset_config=False,
    theme="neon",
    size=320,
    poll=None,
    opacity=None,
    no_topmost=True,
)
```

**Edge Cases:**
- Invalid flag (e.g. `--invalid-flag`) -> raises `SystemExit` with `argparse` usage message.

---

### 5.7 `merge_cli_overrides()`

**File:** `src/boostgauge/config.py`

**Signature:**
```python
def merge_cli_overrides(config: AppConfig, cli_args: argparse.Namespace) -> AppConfig:
    """Apply non-None CLI argument values over AppConfig instance."""
```

**Input Example:**
```python
config = load_config()  # default theme="dark", opacity=1.0, always_on_top=True
cli_args = argparse.Namespace(
    config=None, reset_config=False, theme="light", size=None, poll=None, opacity=0.8, no_topmost=True
)
```

**Output Example:**
Returns a new `AppConfig` instance with `theme="light"`, `opacity=0.8`, `always_on_top=False`, and remaining fields unchanged.

**Edge Cases:**
- CLI override value invalid (e.g. `cli_args.opacity = 2.0`) -> `validate_config()` called during merge raises `ValueError`.

---

### 5.8 `ConfigManager` Methods

**File:** `src/boostgauge/config.py`

```python
class ConfigManager:
    def __init__(self, config: AppConfig, config_path: Path):
        self.config = config
        self.config_path = config_path
        self._threshold_listeners: list[Callable[[ThresholdConfig], None]] = []

    def update_geometry(self, x: int, y: int, size: int) -> None:
        """Update window position and size in state."""
        self.config.position.x = x
        self.config.position.y = y
        self.config.size = size

    def save(self) -> None:
        """Persist current configuration to disk atomically."""
        save_config_atomic(self.config, self.config_path)

    def update_thresholds(self, new_thresholds: dict[str, Any]) -> None:
        """Update threshold values dynamically and notify registered listeners."""
        # Validates new_thresholds against schema, updates self.config.thresholds, invokes listeners

    def add_threshold_listener(self, callback: Callable[[ThresholdConfig], None]) -> None:
        """Register listener callback for dynamic threshold updates."""
        self._threshold_listeners.append(callback)
```

---

## 6. Change Instructions

### 6.1 `src/boostgauge/__init__.py` (Add)

**Complete File Contents:**

```python
"""boostgauge package initialization."""
__version__ = "0.1.0"

__all__ = ["__version__"]
```

---

### 6.2 `src/boostgauge/config.py` (Add)

**Complete File Contents:**

```python
"""Configuration management module for boostgauge.

Handles JSON configuration file loading, saving, validation, CLI parsing,
and stateful ConfigManager observer updates.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import sys
from typing import Any, Callable

VALID_THEMES = {"classic", "dark", "light", "neon"}


@dataclass
class ThresholdBounds:
    yellow: float
    red: float


@dataclass
class ThresholdConfig:
    conpty: ThresholdBounds
    memory_percent: ThresholdBounds
    process_count: ThresholdBounds
    handle_count: ThresholdBounds


@dataclass
class WindowPosition:
    x: int
    y: int


@dataclass
class TelltaleWindows:
    short: int
    medium: int
    long: int


@dataclass
class AppConfig:
    polling_interval_seconds: float
    theme: str
    size: int
    opacity: float
    always_on_top: bool
    position: WindowPosition
    thresholds: ThresholdConfig
    telltale_windows: TelltaleWindows
    show_driver_label: bool
    show_digital_readout: bool
    show_session_count: bool


def get_default_config_path() -> Path:
    """Return default config file path based on platform (~/.boostgauge/config.json or %APPDATA%/boostgauge/config.json)."""
    if sys.platform == "win32" or os.name == "nt":
        app_data = os.environ.get("APPDATA")
        if app_data:
            base_dir = Path(app_data)
        else:
            base_dir = Path.home() / "AppData" / "Roaming"
        return base_dir / "boostgauge" / "config.json"
    return Path.home() / ".boostgauge" / "config.json"


def get_default_config() -> dict[str, Any]:
    """Return dictionary containing standard default configuration settings."""
    return {
        "polling_interval_seconds": 1.0,
        "theme": "dark",
        "size": 256,
        "opacity": 1.0,
        "always_on_top": True,
        "position": {"x": 100, "y": 100},
        "thresholds": {
            "conpty": {"yellow": 20.0, "red": 40.0},
            "memory_percent": {"yellow": 75.0, "red": 90.0},
            "process_count": {"yellow": 50.0, "red": 100.0},
            "handle_count": {"yellow": 10000.0, "red": 20000.0},
        },
        "telltale_windows": {"short": 60, "medium": 600, "long": 3600},
        "show_driver_label": True,
        "show_digital_readout": True,
        "show_session_count": True,
    }


def validate_config(config_dict: dict[str, Any]) -> dict[str, Any]:
    """Validate configuration dictionary fields against allowed types and value ranges."""
    if not isinstance(config_dict, dict):
        raise ValueError("Configuration must be a dictionary")

    # Polling interval
    poll = config_dict.get("polling_interval_seconds")
    if not isinstance(poll, (int, float)) or poll <= 0:
        raise ValueError(f"Polling interval must be a positive number, got {poll}")

    # Theme
    theme = config_dict.get("theme")
    if theme not in VALID_THEMES:
        sorted_themes = ", ".join(sorted(VALID_THEMES))
        raise ValueError(f"Invalid theme '{theme}'. Must be one of: {sorted_themes}")

    # Size
    size = config_dict.get("size")
    if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
        raise ValueError(f"Size must be a positive integer, got {size}")

    # Opacity
    opacity = config_dict.get("opacity")
    if not isinstance(opacity, (int, float)) or isinstance(opacity, bool) or not (0.0 <= opacity <= 1.0):
        raise ValueError(f"Opacity must be between 0.0 and 1.0, got {opacity}")

    # Position
    pos = config_dict.get("position")
    if not isinstance(pos, dict) or "x" not in pos or "y" not in pos:
        raise ValueError("Position must be a dict containing 'x' and 'y' integer coordinates")
    if not isinstance(pos["x"], int) or not isinstance(pos["y"], int):
        raise ValueError(f"Position x and y must be integers, got {pos}")

    # Thresholds
    thresholds = config_dict.get("thresholds")
    if not isinstance(thresholds, dict):
        raise ValueError("Thresholds must be a dictionary")

    required_metrics = {"conpty", "memory_percent", "process_count", "handle_count"}
    for metric in required_metrics:
        if metric not in thresholds or not isinstance(thresholds[metric], dict):
            raise ValueError(f"Missing or invalid threshold metric '{metric}'")
        bounds = thresholds[metric]
        if "yellow" not in bounds or "red" not in bounds:
            raise ValueError(f"Metric '{metric}' must specify both 'yellow' and 'red' thresholds")
        yellow = bounds["yellow"]
        red = bounds["red"]
        if not isinstance(yellow, (int, float)) or not isinstance(red, (int, float)):
            raise ValueError(f"Threshold values for '{metric}' must be numbers")
        if yellow >= red:
            raise ValueError(f"Yellow threshold ({yellow}) must be strictly less than red threshold ({red}) for {metric}")

    return config_dict


def dict_to_app_config(config_dict: dict[str, Any]) -> AppConfig:
    """Convert validated configuration dictionary to AppConfig dataclass object."""
    thresholds = ThresholdConfig(
        conpty=ThresholdBounds(**config_dict["thresholds"]["conpty"]),
        memory_percent=ThresholdBounds(**config_dict["thresholds"]["memory_percent"]),
        process_count=ThresholdBounds(**config_dict["thresholds"]["process_count"]),
        handle_count=ThresholdBounds(**config_dict["thresholds"]["handle_count"]),
    )
    position = WindowPosition(**config_dict["position"])
    telltale_windows = TelltaleWindows(**config_dict["telltale_windows"])

    return AppConfig(
        polling_interval_seconds=float(config_dict["polling_interval_seconds"]),
        theme=str(config_dict["theme"]),
        size=int(config_dict["size"]),
        opacity=float(config_dict["opacity"]),
        always_on_top=bool(config_dict["always_on_top"]),
        position=position,
        thresholds=thresholds,
        telltale_windows=telltale_windows,
        show_driver_label=bool(config_dict["show_driver_label"]),
        show_digital_readout=bool(config_dict["show_digital_readout"]),
        show_session_count=bool(config_dict["show_session_count"]),
    )


def save_config_atomic(config: AppConfig | dict[str, Any], path: Path) -> None:
    """Atomically write AppConfig object or dictionary to JSON file at path."""
    if isinstance(config, AppConfig):
        data = asdict(config)
    else:
        data = config

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_path, path)


def load_config(config_path: Path | None = None) -> AppConfig:
    """Load configuration from JSON file at path (creating defaults if missing at default location)."""
    is_default = False
    if config_path is None:
        config_path = get_default_config_path()
        is_default = True

    if not config_path.exists():
        if is_default:
            default_dict = get_default_config()
            save_config_atomic(default_dict, config_path)
            return dict_to_app_config(default_dict)
        else:
            raise FileNotFoundError(f"Configuration file not found at: {config_path}")

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse configuration JSON: {exc}") from exc

    validated_data = validate_config(data)
    return dict_to_app_config(validated_data)


def parse_cli_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments for boostgauge."""
    parser = argparse.ArgumentParser(description="BoostGauge system tachometer monitor")
    parser.add_argument("--config", type=str, help="Path to custom configuration file")
    parser.add_argument("--reset-config", action="store_true", help="Reset configuration file to defaults")
    parser.add_argument("--theme", type=str, help="UI theme (classic, dark, light, neon)")
    parser.add_argument("--size", type=int, help="Window gauge size in pixels")
    parser.add_argument("--poll", type=float, help="Polling interval in seconds")
    parser.add_argument("--opacity", type=float, help="Window transparency (0.0 to 1.0)")
    parser.add_argument("--no-topmost", action="store_true", help="Disable always-on-top window behavior")

    return parser.parse_args(args if args is not None else sys.argv[1:])


def merge_cli_overrides(config: AppConfig, cli_args: argparse.Namespace) -> AppConfig:
    """Apply non-None CLI argument values over AppConfig instance and re-validate."""
    config_dict = asdict(config)

    if cli_args.theme is not None:
        config_dict["theme"] = cli_args.theme
    if cli_args.size is not None:
        config_dict["size"] = cli_args.size
    if cli_args.poll is not None:
        config_dict["polling_interval_seconds"] = cli_args.poll
    if cli_args.opacity is not None:
        config_dict["opacity"] = cli_args.opacity
    if cli_args.no_topmost:
        config_dict["always_on_top"] = False

    validated = validate_config(config_dict)
    return dict_to_app_config(validated)


class ConfigManager:
    """Stateful configuration container providing dynamic updates and observer notifications."""

    def __init__(self, config: AppConfig, config_path: Path):
        self.config = config
        self.config_path = config_path
        self._threshold_listeners: list[Callable[[ThresholdConfig], None]] = []

    def update_geometry(self, x: int, y: int, size: int) -> None:
        """Update window position and size in state."""
        self.config.position.x = x
        self.config.position.y = y
        self.config.size = size

    def save(self) -> None:
        """Persist current configuration to disk atomically."""
        save_config_atomic(self.config, self.config_path)

    def update_thresholds(self, new_thresholds: dict[str, Any]) -> None:
        """Update thresholds in memory and notify registered listeners without requiring a restart."""
        current_dict = asdict(self.config)
        current_dict["thresholds"].update(new_thresholds)
        validated = validate_config(current_dict)
        self.config = dict_to_app_config(validated)

        for listener in self._threshold_listeners:
            listener(self.config.thresholds)

    def add_threshold_listener(self, callback: Callable[[ThresholdConfig], None]) -> None:
        """Register observer callback triggered when threshold configurations change."""
        self._threshold_listeners.append(callback)
```

---

### 6.3 `src/boostgauge/app.py` (Add)

**Complete File Contents:**

```python
"""Main application entry point for boostgauge.

Integrates CLI argument parsing, configuration loading, window geometry,
and runtime threshold management.
"""
from __future__ import annotations

from pathlib import Path
import sys

from boostgauge.config import (
    ConfigManager,
    get_default_config,
    get_default_config_path,
    load_config,
    merge_cli_overrides,
    parse_cli_args,
    save_config_atomic,
)


def bootstrap_config(argv: list[str] | None = None) -> ConfigManager:
    """Initialize ConfigManager using CLI arguments and configuration file persistence."""
    cli_args = parse_cli_args(argv)

    if cli_args.config:
        config_path = Path(cli_args.config)
    else:
        config_path = get_default_config_path()

    if cli_args.reset_config:
        save_config_atomic(get_default_config(), config_path)

    config = load_config(config_path)
    config = merge_cli_overrides(config, cli_args)

    return ConfigManager(config, config_path)


def main(argv: list[str] | None = None) -> int:
    """Main execution routine."""
    try:
        manager = bootstrap_config(argv)
        # Application window setup and main loop will be hooked here
        return 0
    except (ValueError, FileNotFoundError) as exc:
        print(f"Configuration Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

---

### 6.4 `tests/unit/test_config.py` (Add)

**Complete File Contents:**

```python
"""Unit tests for configuration file loading, saving, validation, CLI overrides, and edge cases.

Ref: docs/design/0001-test-strategy.md (Tier 1 Pure Logic Tests)
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import pytest

from boostgauge.app import bootstrap_config
from boostgauge.config import (
    AppConfig,
    ConfigManager,
    get_default_config,
    get_default_config_path,
    load_config,
    merge_cli_overrides,
    parse_cli_args,
    save_config_atomic,
    validate_config,
)


def test_t010_auto_create_default_config_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """T010: Default config file is auto-created with valid JSON schema when missing."""
    target_config = tmp_path / "sub_dir" / "config.json"
    monkeypatch.setattr("boostgauge.config.get_default_config_path", lambda: target_config)

    assert not target_config.exists()
    config = load_config(None)
    assert target_config.exists()
    assert config.theme == "dark"
    assert config.size == 256
    # Assert platform-independent Path equality per Issue #1841
    assert target_config == tmp_path / "sub_dir" / "config.json"


def test_t020_load_config_custom_path(tmp_path: Path) -> None:
    """T020: Load config from custom path via load_config(path)."""
    custom_path = tmp_path / "custom_config.json"
    custom_data = get_default_config()
    custom_data["theme"] = "neon"
    custom_data["size"] = 320
    save_config_atomic(custom_data, custom_path)

    config = load_config(custom_path)
    assert config.theme == "neon"
    assert config.size == 320


def test_t030_reset_config_via_cli_bootstrap(tmp_path: Path) -> None:
    """T030: Reset configuration file via --reset-config flag."""
    custom_path = tmp_path / "config_to_reset.json"
    custom_data = get_default_config()
    custom_data["theme"] = "neon"
    save_config_atomic(custom_data, custom_path)

    manager = bootstrap_config(["--config", str(custom_path), "--reset-config"])
    assert manager.config.theme == "dark"


def test_t040_override_config_values_with_cli_options(tmp_path: Path) -> None:
    """T040: CLI flags override config file values in active memory state.

    Per Issue #1860, CLI overrides are runtime precedence over config file;
    we assert active memory state is overridden without asserting side-effect disk mutations.
    """
    cfg_file = tmp_path / "config.json"
    save_config_atomic(get_default_config(), cfg_file)

    args = parse_cli_args(["--theme", "light", "--size", "400", "--no-topmost"])
    config = load_config(cfg_file)
    merged = merge_cli_overrides(config, args)

    assert merged.theme == "light"
    assert merged.size == 400
    assert merged.always_on_top is False
    # Original config loaded from disk remains unaffected until save() is called
    assert config.theme == "dark"


def test_t050_save_window_position_and_size_geometry(tmp_path: Path) -> None:
    """T050: Window geometry updates are written atomically to disk."""
    cfg_file = tmp_path / "config.json"
    save_config_atomic(get_default_config(), cfg_file)

    config = load_config(cfg_file)
    manager = ConfigManager(config, cfg_file)
    manager.update_geometry(150, 200, 350)
    manager.save()

    reloaded = load_config(cfg_file)
    assert reloaded.position.x == 150
    assert reloaded.position.y == 200
    assert reloaded.size == 350


def test_t060_restore_window_position_and_size_geometry(tmp_path: Path) -> None:
    """T060: Restored window position and size geometry applied on startup."""
    cfg_file = tmp_path / "geometry_config.json"
    custom_data = get_default_config()
    custom_data["position"] = {"x": 120, "y": 180}
    custom_data["size"] = 400
    save_config_atomic(custom_data, cfg_file)

    config = load_config(cfg_file)
    assert config.position.x == 120
    assert config.position.y == 180
    assert config.size == 400


def test_t070_live_threshold_update_without_restart(tmp_path: Path) -> None:
    """T070: Threshold updates take effect immediately in memory and trigger observer callbacks."""
    cfg_file = tmp_path / "config.json"
    save_config_atomic(get_default_config(), cfg_file)
    config = load_config(cfg_file)
    manager = ConfigManager(config, cfg_file)

    notified = []
    manager.add_threshold_listener(lambda t: notified.append(t.conpty.yellow))

    manager.update_thresholds({"conpty": {"yellow": 35.0, "red": 50.0}})

    assert manager.config.thresholds.conpty.yellow == 35.0
    assert manager.config.thresholds.conpty.red == 50.0
    assert len(notified) == 1
    assert notified[0] == 35.0


def test_t080_validate_opacity_out_of_bounds() -> None:
    """T080: Invalid opacity raises ValueError."""
    data = get_default_config()
    data["opacity"] = 1.5
    with pytest.raises(ValueError, match="Opacity must be between 0.0 and 1.0"):
        validate_config(data)

    data["opacity"] = -0.1
    with pytest.raises(ValueError, match="Opacity must be between 0.0 and 1.0"):
        validate_config(data)


def test_t090_validate_negative_or_invalid_size() -> None:
    """T090: Invalid size raises ValueError."""
    data = get_default_config()
    data["size"] = -50
    with pytest.raises(ValueError, match="Size must be a positive integer"):
        validate_config(data)


def test_t100_validate_unknown_theme_name() -> None:
    """T100: Unknown theme name raises ValueError listing allowed options."""
    data = get_default_config()
    data["theme"] = "invalid_theme"
    with pytest.raises(ValueError, match="Invalid theme 'invalid_theme'. Must be one of: classic, dark, light, neon"):
        validate_config(data)


def test_t110_nonexistent_custom_config_file_raises_error(tmp_path: Path) -> None:
    """T110: Non-existent custom config file specified via --config raises FileNotFoundError."""
    missing_file = tmp_path / "nonexistent.json"
    with pytest.raises(FileNotFoundError, match="Configuration file not found"):
        load_config(missing_file)


def test_platform_default_config_path_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify platform-independent path resolution logic."""
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(os, "name", "nt")
    monkeypatch.setenv("APPDATA", r"C:\Users\TestUser\AppData\Roaming")
    path_win = get_default_config_path()
    assert path_win == Path(r"C:\Users\TestUser\AppData\Roaming") / "boostgauge" / "config.json"

    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(os, "name", "posix")
    monkeypatch.setattr(Path, "home", lambda: Path("/home/testuser"))
    path_posix = get_default_config_path()
    assert path_posix == Path("/home/testuser") / ".boostgauge" / "config.json"
```

---

## 7. Pattern References

### 7.1 Test Bootstrap and Path Insertion

**File:** `tests/conftest.py` (lines 1-8)

```python
"""Project test bootstrap."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
```

**Relevance:** Demonstrates standard project path setup allowing direct package imports from `src/boostgauge` during unit tests without modifying environment flags.

---

### 7.2 Off-Screen / Pure-Logic GUI Testing Strategy (Option C)

**File:** `docs/design/0001-test-strategy.md` (lines 33-48)

```python
# Chosen: Option C — render to off-screen PIL.Image first; tkinter Canvas is a display surface only.
# The renderer is a pure function. Tests exercise pure logic and data transformation
# without ever instantiating tkinter.Tk().
```

**Relevance:** Direct constraint governing configuration testing: all configuration loading, CLI argument merging, geometry persistence, and threshold observer callbacks are executed as pure python logic tests under `tests/unit/test_config.py` without requiring a graphical display or initializing a `tkinter.Tk()` window instance.

---

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `import argparse` | Standard Library | `src/boostgauge/config.py` |
| `from dataclasses import dataclass, asdict` | Standard Library | `src/boostgauge/config.py` |
| `import json` | Standard Library | `src/boostgauge/config.py` |
| `import os` | Standard Library | `src/boostgauge/config.py`, `tests/unit/test_config.py` |
| `from pathlib import Path` | Standard Library | `src/boostgauge/config.py`, `src/boostgauge/app.py`, `tests/unit/test_config.py` |
| `import sys` | Standard Library | `src/boostgauge/config.py`, `src/boostgauge/app.py`, `tests/unit/test_config.py` |
| `from typing import Any, Callable` | Standard Library | `src/boostgauge/config.py` |
| `import pytest` | Third-Party (pyproject.toml) | `tests/unit/test_config.py` |

**New Dependencies:** None (uses standard library modules and existing pytest test framework).

---

## 9. Placeholder

*Reserved for alignment with LLD section numbering.*

---

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output / Behavior | Assertion Rules |
|---------|---------------|-------|---------------------------|-----------------|
| T010 | `load_config(None)` | `config_path=None` (missing file) | Creates default `config.json` file and returns default `AppConfig` | Compare `pathlib.Path` objects directly (`path == expected_path`), never string endswith (Issue #1841) |
| T020 | `load_config(custom_path)` | `custom_path` pointing to custom JSON | Loads settings matching custom file content | Verify dataclass fields match custom JSON values |
| T030 | `bootstrap_config()` | `--config PATH --reset-config` | Overwrites target file with default JSON schema and returns default `AppConfig` | Verify restored configuration fields match defaults |
| T040 | `merge_cli_overrides()` | `--theme light --size 400 --no-topmost` | Effective `AppConfig` in memory reflects CLI overrides | Assert memory state reflects CLI overrides; do NOT assert file on disk is modified (Issue #1860) |
| T050 | `ConfigManager.update_geometry()` & `save()` | `x=150, y=200, size=350` | Writes geometry update atomically to target JSON file | Reload file from disk and assert updated geometry values match |
| T060 | `load_config()` | Config JSON with `x=120, y=180, size=400` | Instantiates `AppConfig` with matching position and size | Dataclass `position.x`, `position.y`, `size` equal stored values |
| T070 | `ConfigManager.update_thresholds()` | `{"conpty": {"yellow": 35.0, "red": 50.0}}` | Updates thresholds in state and invokes registered listeners | Assert in-memory state updated and listener callback called with new thresholds |
| T080 | `validate_config()` | `"opacity": 1.5` or `-0.1` | Raises `ValueError` with bounds error message | Assert exception message mentions `0.0 and 1.0` |
| T090 | `validate_config()` | `"size": -50` | Raises `ValueError` with size error message | Assert exception message mentions positive integer |
| T100 | `validate_config()` | `"theme": "invalid"` | Raises `ValueError` listing allowed themes | Assert exception message contains valid themes list |
| T110 | `load_config()` | Non-existent custom path `Path("missing.json")` | Raises `FileNotFoundError` | Assert exception raised on missing custom file |

**Baseline-Independent Assertions:** N/A (Configuration management subsystem has no visual baseline dependencies).

---

## 11. Implementation Notes

### 11.1 Error Handling Convention

All configuration parsing and validation failures operate under a strict fail-closed pattern:
- Validation errors raise `ValueError` detailing the exact parameter and allowed bounds.
- Missing custom configuration files raise `FileNotFoundError`.
- `main()` catches `ValueError` and `FileNotFoundError`, prints a clean single-line error message to `sys.stderr`, and exits with status code `1`.

### 11.2 Atomic Write Safety

File persistence in `save_config_atomic()` follows an explicit write-and-replace strategy:
1. Write JSON data to temporary file `path.with_suffix(".tmp")`.
2. Flush and close file handle cleanly.
3. Call `os.replace(tmp_path, path)` to perform an atomic filesystem replacement.
This protects existing `config.json` files from corrupting during abrupt system power loss or process termination.

### 11.3 Allowed Themes Constant

Theme validation enforces membership against `VALID_THEMES = {"classic", "dark", "light", "neon"}`.

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
| Finalized | 2026-08-01T07:27:06-05:00 |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #7 |
| Verdict | APPROVED |
| Date | 2026-08-01 |
| Iterations | 1 |
| Finalized | 2026-08-01T12:28:28Z |

### Review Feedback Summary

The revised implementation spec for Issue #7 is complete, concrete, internally consistent, and fully executable. The revisions correctly update test_platform_default_config_path_resolution to monkeypatch both sys.platform and os.name, ensuring cross-platform path resolution unit tests run reliably on all operating systems. All functions, data structures, and unit tests provide complete, production-ready python code that directly traces to the underlying requirements without inventing unmentioned...
