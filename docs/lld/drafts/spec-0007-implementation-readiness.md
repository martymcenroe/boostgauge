# Implementation Spec: Configuration File and CLI Arguments

| Field | Value |
|-------|-------|
| Issue | #7 |
| LLD | `docs/lld/done/0007-config-cli.md` |
| Generated | 2026-08-01 |
| Status | APPROVED |

---

## 1. Overview

**Objective:** Implement configuration management with JSON file persistence, CLI argument overrides, dynamic threshold updates, and window geometry restoration for BoostGauge.

**Success Criteria:**
1. Default configuration file is automatically created with default values at platform-specific location (`~/.boostgauge/config.json` on Unix/Linux/macOS or `%APPDATA%\boostgauge\config.json` on Windows) if missing on launch.
2. Custom config file path can be specified via `--config PATH` CLI argument, overriding the default configuration file location.
3. `--reset-config` CLI argument resets the target configuration file to default values.
4. CLI options (`--theme`, `--size`, `--poll`, `--opacity`, `--no-topmost`) override values loaded from the configuration file for the current process run.
5. Window position (`position.x`, `position.y`) and size (`size`) geometry are restored on startup and written atomically to disk on exit.
6. Threshold configurations update dynamically in memory and notify registered observers without requiring application restart.
7. Strict validation raises `ValueError` with descriptive messages and fails closed when invalid parameters are detected.

---

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/__init__.py` | Add | Package initialization file defining version string (`__version__ = "0.1.0"`) and public module exports |
| 2 | `src/boostgauge/config.py` | Add | Configuration management module: dataclasses, default path resolution, atomic persistence, schema validation, CLI parsing, merging, and `ConfigManager` container |
| 3 | `src/boostgauge/app.py` | Add | Main application entry point integrating configuration management, CLI argument processing, window geometry setup, and lifecycle handling |
| 4 | `tests/unit/test_config.py` | Add | Complete unit test suite verifying config creation, loading, saving, validation, CLI overrides, observer callbacks, and edge cases |

**Implementation Order Rationale:**
- `__init__.py` establishes package namespace and version attributes.
- `config.py` defines core data structures, validation rules, serialization logic, CLI argument parsing, and stateful observer container (`ConfigManager`).
- `app.py` imports `config.py` to orchestrate application startup, configuration loading, CLI argument application, and shutdown persistence.
- `tests/unit/test_config.py` validates `config.py` functions in isolation per Option C of `docs/design/0001-test-strategy.md` without requiring `tkinter` bindings.

---

## 3. Current State (for Modify/Delete files)

N/A - All files in this specification are new additions (`Add`). No pre-existing files are modified or deleted.

---

## 4. Data Structures

### 4.1 Dataclass Schemas

```python
from dataclasses import dataclass, field
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

### 4.2 Concrete Config Serialization Format (`config.json`)

**Concrete JSON Example:**

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
      "yellow": 32.0,
      "red": 64.0
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
    """Return default config file path based on platform (%APPDATA%/boostgauge/config.json or ~/.boostgauge/config.json)."""
    ...
```

**Input Example:**
```python
# No arguments
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
- `APPDATA` environment variable missing or empty on Windows -> falls back to `Path.home() / ".boostgauge" / "config.json"`.

---

### 5.2 `get_default_config()`

**File:** `src/boostgauge/config.py`

**Signature:**
```python
def get_default_config() -> dict[str, Any]:
    """Return dictionary containing standard default configuration settings."""
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
    "size": 256,
    "opacity": 1.0,
    "always_on_top": True,
    "position": {"x": 100, "y": 100},
    "thresholds": {
        "conpty": {"yellow": 32.0, "red": 64.0},
        "memory_percent": {"yellow": 75.0, "red": 90.0},
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
- Always returns a new dictionary instance so callers cannot mutate standard defaults globally.

---

### 5.3 `validate_config()`

**File:** `src/boostgauge/config.py`

**Signature:**
```python
def validate_config(config_dict: dict[str, Any]) -> dict[str, Any]:
    """Validate configuration dictionary fields against allowed types and value ranges, raising ValueError on failure."""
    ...
```

**Input Example:**
```python
config_dict = {
    "polling_interval_seconds": 1.0,
    "theme": "dark",
    "size": 256,
    "opacity": 1.0,
    "always_on_top": True,
    "position": {"x": 100, "y": 100},
    "thresholds": {
        "conpty": {"yellow": 32.0, "red": 64.0},
        "memory_percent": {"yellow": 75.0, "red": 90.0},
        "process_count": {"yellow": 150.0, "red": 300.0},
        "handle_count": {"yellow": 10000.0, "red": 20000.0},
    },
    "telltale_windows": {"short": 60, "medium": 600, "long": 3600},
    "show_driver_label": True,
    "show_digital_readout": True,
    "show_session_count": True,
}
```

**Output Example:**
```python
# Returns verified dictionary unchanged
{ ... }
```

**Edge Cases:**
- `opacity = 1.5` -> raises `ValueError("opacity must be a float between 0.0 and 1.0, got 1.5")`
- `size = -50` -> raises `ValueError("size must be a positive integer, got -50")`
- `theme = "cyber"` -> raises `ValueError("Invalid theme 'cyber'. Allowed themes: ['classic', 'dark', 'light', 'neon']")`
- `polling_interval_seconds = 0` -> raises `ValueError("polling_interval_seconds must be > 0, got 0")`
- Missing required key `"thresholds"` -> raises `ValueError("Missing required config key: 'thresholds'")`
- `yellow >= red` in threshold -> raises `ValueError("Threshold 'conpty' yellow (64.0) must be strictly less than red (32.0)")`

---

### 5.4 `load_config()`

**File:** `src/boostgauge/config.py`

**Signature:**
```python
def load_config(config_path: Path | None = None) -> AppConfig:
    """Load configuration from JSON file at path (creating defaults if missing), validate fields, and return AppConfig object."""
    ...
```

**Input Example 1 (Default path creation):**
```python
config_path = None
```

**Output Example:**
```python
AppConfig(
    polling_interval_seconds=1.0,
    theme="dark",
    size=256,
    opacity=1.0,
    always_on_top=True,
    position=WindowPosition(x=100, y=100),
    thresholds=ThresholdConfig(
        conpty=ThresholdBounds(yellow=32.0, red=64.0),
        memory_percent=ThresholdBounds(yellow=75.0, red=90.0),
        process_count=ThresholdBounds(yellow=150.0, red=300.0),
        handle_count=ThresholdBounds(yellow=10000.0, red=20000.0),
    ),
    telltale_windows=TelltaleWindows(short=60, medium=600, long=3600),
    show_driver_label=True,
    show_digital_readout=True,
    show_session_count=True,
)
```

**Edge Cases:**
- Custom `config_path` is passed and does NOT exist -> raises `FileNotFoundError(f"Config file not found at {config_path}")`.
- Default `config_path` (`None`) does NOT exist -> creates parent directories if missing and writes default configuration file before returning.

---

### 5.5 `save_config_atomic()`

**File:** `src/boostgauge/config.py`

**Signature:**
```python
def save_config_atomic(config: AppConfig, path: Path) -> None:
    """Atomically write AppConfig object to JSON file at path using a temporary file in the destination directory and os.replace."""
    ...
```

**Input Example:**
```python
config = AppConfig(...)
path = Path("/home/user/.boostgauge/config.json")
```

**Output Example:**
```python
None  # File written safely via atomic temporary swap
```

**Edge Cases:**
- Target directory does not exist -> creates parent directories (`path.parent.mkdir(parents=True, exist_ok=True)`).
- Permission error during `.tmp` write or `os.replace` -> bubbles OS exception cleanly.

---

### 5.6 `parse_cli_args()`

**File:** `src/boostgauge/config.py`

**Signature:**
```python
def parse_cli_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for boostgauge options including theme, size, poll, opacity, no-topmost, config path, and reset-config."""
    ...
```

**Input Example:**
```python
args = ["--theme", "light", "--size", "300", "--no-topmost"]
```

**Output Example:**
```python
argparse.Namespace(
    config=None,
    reset_config=False,
    theme="light",
    size=300,
    poll=None,
    opacity=None,
    no_topmost=True,
)
```

**Edge Cases:**
- Invalid flag argument (e.g. `--size abc`) -> `argparse.ArgumentParser` exits with usage error.

---

### 5.7 `merge_cli_overrides()`

**File:** `src/boostgauge/config.py`

**Signature:**
```python
def merge_cli_overrides(config: AppConfig, cli_args: argparse.Namespace) -> AppConfig:
    """Apply non-None CLI argument values over configuration object."""
    ...
```

**Input Example:**
```python
config = AppConfig(theme="dark", size=256, always_on_top=True, ...)
cli_args = argparse.Namespace(
    theme="neon", size=320, poll=0.5, opacity=0.8, no_topmost=True
)
```

**Output Example:**
```python
AppConfig(
    theme="neon",
    size=320,
    polling_interval_seconds=0.5,
    opacity=0.8,
    always_on_top=False,
    ...
)
```

**Edge Cases:**
- `cli_args` attributes are all `None` or `False` (defaults) -> returns `config` with unchanged settings.

---

### 5.8 `ConfigManager` Class

**File:** `src/boostgauge/config.py`

**Signature:**
```python
class ConfigManager:
    """Stateful configuration container providing dynamic threshold updates and observer notifications."""
    def __init__(self, config: AppConfig, config_path: Path):
        self.config = config
        self.config_path = config_path
        self._threshold_listeners: list[Callable[[ThresholdConfig], None]] = []

    def update_geometry(self, x: int, y: int, size: int) -> None:
        """Update window position and size in state."""
        ...

    def save(self) -> None:
        """Persist current configuration to disk atomically."""
        ...

    def update_thresholds(self, new_thresholds: dict[str, Any]) -> None:
        """Update thresholds in memory and notify registered listeners without requiring a restart."""
        ...

    def add_threshold_listener(self, callback: Callable[[ThresholdConfig], None]) -> None:
        """Register observer callback triggered when threshold configurations change."""
        ...
```

---

### 5.9 `main()`

**File:** `src/boostgauge/app.py`

**Signature:**
```python
def main(args: list[str] | None = None) -> int:
    """Main application entry point handling configuration setup, argument processing, and lifecycle execution."""
    ...
```

**Input Example:**
```python
args = ["--theme", "dark"]
```

**Output Example:**
```python
0  # Return code on clean execution
```

---

## 6. Change Instructions

### 6.1 `src/boostgauge/__init__.py` (Add)

**Complete file contents:**

```python
"""BoostGauge - Lightweight system monitor styled like a racing tachometer.

Issue #7: Configuration File and CLI Arguments
"""

__version__ = "0.1.0"
__all__ = ["__version__"]
```

---

### 6.2 `src/boostgauge/config.py` (Add)

**Complete file contents:**

```python
"""Configuration management module for BoostGauge.

Issue #7: Configuration File and CLI Arguments
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

VALID_THEMES = {"dark", "light", "neon", "classic"}


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
    """Return default config file path based on platform (%APPDATA%/boostgauge/config.json or ~/.boostgauge/config.json)."""
    if os.name == "nt":
        app_data = os.environ.get("APPDATA")
        if app_data:
            return Path(app_data) / "boostgauge" / "config.json"
        return Path.home() / ".boostgauge" / "config.json"
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
            "conpty": {"yellow": 32.0, "red": 64.0},
            "memory_percent": {"yellow": 75.0, "red": 90.0},
            "process_count": {"yellow": 150.0, "red": 300.0},
            "handle_count": {"yellow": 10000.0, "red": 20000.0},
        },
        "telltale_windows": {"short": 60, "medium": 600, "long": 3600},
        "show_driver_label": True,
        "show_digital_readout": True,
        "show_session_count": True,
    }


def validate_config(config_dict: dict[str, Any]) -> dict[str, Any]:
    """Validate configuration dictionary fields against allowed types and value ranges, raising ValueError on failure."""
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
        if key not in config_dict:
            raise ValueError(f"Missing required config key: '{key}'")

    poll = config_dict["polling_interval_seconds"]
    if not isinstance(poll, (int, float)) or poll <= 0:
        raise ValueError(f"polling_interval_seconds must be > 0, got {poll}")

    theme = config_dict["theme"]
    if theme not in VALID_THEMES:
        allowed = sorted(list(VALID_THEMES))
        raise ValueError(f"Invalid theme '{theme}'. Allowed themes: {allowed}")

    size = config_dict["size"]
    if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
        raise ValueError(f"size must be a positive integer, got {size}")

    opacity = config_dict["opacity"]
    if not isinstance(opacity, (int, float)) or not (0.0 <= float(opacity) <= 1.0):
        raise ValueError(f"opacity must be a float between 0.0 and 1.0, got {opacity}")

    pos = config_dict["position"]
    if not isinstance(pos, dict) or "x" not in pos or "y" not in pos:
        raise ValueError("position must be a dictionary with 'x' and 'y' integer coordinates")
    if not isinstance(pos["x"], int) or isinstance(pos["x"], bool) or not isinstance(pos["y"], int) or isinstance(pos["y"], bool):
        raise ValueError("position coordinates 'x' and 'y' must be integers")

    thresh = config_dict["thresholds"]
    if not isinstance(thresh, dict):
        raise ValueError("thresholds must be a dictionary")

    required_metrics = ["conpty", "memory_percent", "process_count", "handle_count"]
    for metric in required_metrics:
        if metric not in thresh:
            raise ValueError(f"Missing threshold metric '{metric}'")
        bounds = thresh[metric]
        if not isinstance(bounds, dict) or "yellow" not in bounds or "red" not in bounds:
            raise ValueError(f"Threshold metric '{metric}' must contain 'yellow' and 'red' numeric bounds")
        y_val = bounds["yellow"]
        r_val = bounds["red"]
        if not isinstance(y_val, (int, float)) or not isinstance(r_val, (int, float)):
            raise ValueError(f"Threshold bounds for '{metric}' must be numeric")
        if y_val >= r_val:
            raise ValueError(f"Threshold '{metric}' yellow ({y_val}) must be strictly less than red ({r_val})")

    return config_dict


def dict_to_app_config(config_dict: dict[str, Any]) -> AppConfig:
    """Convert validated dictionary structure into AppConfig dataclass hierarchy."""
    thresh_data = config_dict["thresholds"]
    thresholds = ThresholdConfig(
        conpty=ThresholdBounds(**thresh_data["conpty"]),
        memory_percent=ThresholdBounds(**thresh_data["memory_percent"]),
        process_count=ThresholdBounds(**thresh_data["process_count"]),
        handle_count=ThresholdBounds(**thresh_data["handle_count"]),
    )
    pos = WindowPosition(**config_dict["position"])
    telltale = TelltaleWindows(**config_dict["telltale_windows"])

    return AppConfig(
        polling_interval_seconds=float(config_dict["polling_interval_seconds"]),
        theme=str(config_dict["theme"]),
        size=int(config_dict["size"]),
        opacity=float(config_dict["opacity"]),
        always_on_top=bool(config_dict["always_on_top"]),
        position=pos,
        thresholds=thresholds,
        telltale_windows=telltale,
        show_driver_label=bool(config_dict["show_driver_label"]),
        show_digital_readout=bool(config_dict["show_digital_readout"]),
        show_session_count=bool(config_dict["show_session_count"]),
    )


def load_config(config_path: Path | None = None) -> AppConfig:
    """Load configuration from JSON file at path (creating defaults if missing), validate fields, and return AppConfig object."""
    if config_path is None:
        target_path = get_default_config_path()
        if not target_path.exists():
            target_path.parent.mkdir(parents=True, exist_ok=True)
            default_data = get_default_config()
            validate_config(default_data)
            default_config = dict_to_app_config(default_data)
            save_config_atomic(default_config, target_path)
            return default_config
    else:
        target_path = config_path
        if not target_path.exists():
            raise FileNotFoundError(f"Config file not found at {target_path}")

    with open(target_path, "r", encoding="utf-8") as f:
        try:
            raw_data = json.load(f)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON format in config file {target_path}: {exc}") from exc

    validated_data = validate_config(raw_data)
    return dict_to_app_config(validated_data)


def save_config_atomic(config: AppConfig, path: Path) -> None:
    """Atomically write AppConfig object to JSON file at path using a temporary file in the destination directory and os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    data_dict = asdict(config)

    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data_dict, f, indent=2)

    os.replace(tmp_path, path)


def parse_cli_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for boostgauge options including theme, size, poll, opacity, no-topmost, config path, and reset-config."""
    parser = argparse.ArgumentParser(
        prog="boostgauge",
        description="Lightweight system tachometer with peak-hold needles.",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to custom JSON configuration file.",
    )
    parser.add_argument(
        "--reset-config",
        action="store_true",
        help="Reset configuration file to standard default values.",
    )
    parser.add_argument(
        "--theme",
        type=str,
        default=None,
        choices=sorted(list(VALID_THEMES)),
        help="Gauge theme palette.",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=None,
        help="Square size of gauge window in pixels.",
    )
    parser.add_argument(
        "--poll",
        type=float,
        default=None,
        help="Polling interval in seconds.",
    )
    parser.add_argument(
        "--opacity",
        type=float,
        default=None,
        help="Window transparency opacity (0.0 - 1.0).",
    )
    parser.add_argument(
        "--no-topmost",
        action="store_true",
        help="Disable always-on-top window pin behavior.",
    )

    parsed = parser.parse_args(args)
    if parsed.size is not None and parsed.size <= 0:
        raise ValueError(f"size must be a positive integer, got {parsed.size}")
    if parsed.poll is not None and parsed.poll <= 0:
        raise ValueError(f"poll polling interval must be > 0, got {parsed.poll}")
    if parsed.opacity is not None and not (0.0 <= parsed.opacity <= 1.0):
        raise ValueError(f"opacity must be between 0.0 and 1.0, got {parsed.opacity}")

    return parsed


def merge_cli_overrides(config: AppConfig, cli_args: argparse.Namespace) -> AppConfig:
    """Apply non-None CLI argument values over configuration object."""
    if cli_args.theme is not None:
        config.theme = cli_args.theme
    if cli_args.size is not None:
        config.size = cli_args.size
    if cli_args.poll is not None:
        config.polling_interval_seconds = cli_args.poll
    if cli_args.opacity is not None:
        config.opacity = cli_args.opacity
    if cli_args.no_topmost:
        config.always_on_top = False
    return config


class ConfigManager:
    """Stateful configuration container providing dynamic threshold updates and observer notifications."""

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
        current_dict = asdict(self.config.thresholds)
        for metric, bounds in new_thresholds.items():
            if metric in current_dict:
                if "yellow" in bounds:
                    current_dict[metric]["yellow"] = bounds["yellow"]
                if "red" in bounds:
                    current_dict[metric]["red"] = bounds["red"]

        # Validate updated metric bounds
        for metric, bounds in current_dict.items():
            if bounds["yellow"] >= bounds["red"]:
                raise ValueError(
                    f"Threshold '{metric}' yellow ({bounds['yellow']}) must be strictly less than red ({bounds['red']})"
                )

        self.config.thresholds = ThresholdConfig(
            conpty=ThresholdBounds(**current_dict["conpty"]),
            memory_percent=ThresholdBounds(**current_dict["memory_percent"]),
            process_count=ThresholdBounds(**current_dict["process_count"]),
            handle_count=ThresholdBounds(**current_dict["handle_count"]),
        )

        for listener in self._threshold_listeners:
            listener(self.config.thresholds)

    def add_threshold_listener(self, callback: Callable[[ThresholdConfig], None]) -> None:
        """Register observer callback triggered when threshold configurations change."""
        self._threshold_listeners.append(callback)
```

---

### 6.3 `src/boostgauge/app.py` (Add)

**Complete file contents:**

```python
"""Main application module integrating configuration manager and CLI argument handling.

Issue #7: Configuration File and CLI Arguments
"""

from __future__ import annotations

import sys
from pathlib import Path

from boostgauge.config import (
    ConfigManager,
    dict_to_app_config,
    get_default_config,
    get_default_config_path,
    load_config,
    merge_cli_overrides,
    parse_cli_args,
    save_config_atomic,
)


def initialize_config_manager(args: list[str] | None = None) -> ConfigManager:
    """Parse CLI args and prepare the stateful ConfigManager container according to priority rules."""
    cli_args = parse_cli_args(args)

    if cli_args.config:
        target_path = Path(cli_args.config).resolve()
    else:
        target_path = get_default_config_path()

    if cli_args.reset_config:
        default_data = get_default_config()
        default_config = dict_to_app_config(default_data)
        save_config_atomic(default_config, target_path)

    app_config = load_config(target_path)
    merged_config = merge_cli_overrides(app_config, cli_args)

    return ConfigManager(config=merged_config, config_path=target_path)


def main(args: list[str] | None = None) -> int:
    """Main execution entry point."""
    if args is None:
        args = sys.argv[1:]

    manager = initialize_config_manager(args)
    # App GUI initialization and event loop setup will consume manager instance in future issues
    _ = manager
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

---

### 6.4 `tests/unit/test_config.py` (Add)

**Complete file contents:**

```python
"""Unit tests for configuration file loading, saving, validation, CLI overrides, and edge cases.

Issue #7: Configuration File and CLI Arguments
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from boostgauge.config import (
    AppConfig,
    ConfigManager,
    ThresholdBounds,
    ThresholdConfig,
    TelltaleWindows,
    WindowPosition,
    get_default_config,
    get_default_config_path,
    load_config,
    merge_cli_overrides,
    parse_cli_args,
    save_config_atomic,
    validate_config,
)


def test_t010_auto_create_default_config_file(tmp_path: Path):
    """T010: Missing default config file is created with standard defaults on load."""
    target_file = tmp_path / "boostgauge" / "config.json"
    with patch("boostgauge.config.get_default_config_path", return_value=target_file):
        config = load_config(None)
        assert target_file.exists()
        assert config.theme == "dark"
        assert config.size == 256
        assert config.position.x == 100
        assert config.position.y == 100


def test_t020_load_config_from_custom_path(tmp_path: Path):
    """T020: Custom config path passed explicitly loads settings correctly."""
    custom_file = tmp_path / "custom_config.json"
    data = get_default_config()
    data["theme"] = "neon"
    data["size"] = 512
    custom_file.write_text(json.dumps(data), encoding="utf-8")

    config = load_config(custom_file)
    assert config.theme == "neon"
    assert config.size == 512


def test_t030_reset_config_file_to_defaults(tmp_path: Path):
    """T030: Reset flag overwrites custom file with standard default settings."""
    from boostgauge.app import initialize_config_manager

    config_file = tmp_path / "config.json"
    custom_data = get_default_config()
    custom_data["theme"] = "light"
    config_file.write_text(json.dumps(custom_data), encoding="utf-8")

    manager = initialize_config_manager(["--config", str(config_file), "--reset-config"])
    assert manager.config.theme == "dark"

    # Verify on-disk JSON was overwritten with default config
    saved_data = json.loads(config_file.read_text(encoding="utf-8"))
    assert saved_data["theme"] == "dark"


def test_t040_override_config_values_with_cli_options(tmp_path: Path):
    """T040: CLI flags override loaded config values at runtime without mutating disk."""
    config_file = tmp_path / "config.json"
    data = get_default_config()
    data["theme"] = "dark"
    data["size"] = 256
    config_file.write_text(json.dumps(data), encoding="utf-8")

    cli_args = parse_cli_args(["--theme", "neon", "--size", "300", "--no-topmost"])
    loaded_config = load_config(config_file)
    merged = merge_cli_overrides(loaded_config, cli_args)

    assert merged.theme == "neon"
    assert merged.size == 300
    assert merged.always_on_top is False


def test_t050_save_window_position_and_size_geometry(tmp_path: Path):
    """T050: Updating geometry and calling save persists updated values atomically."""
    config_file = tmp_path / "config.json"
    config = load_config(None if not config_file.exists() else config_file)
    manager = ConfigManager(config, config_file)

    manager.update_geometry(150, 200, 350)
    manager.save()

    assert config_file.exists()
    disk_data = json.loads(config_file.read_text(encoding="utf-8"))
    assert disk_data["position"]["x"] == 150
    assert disk_data["position"]["y"] == 200
    assert disk_data["size"] == 350


def test_t060_restore_window_position_and_size_geometry(tmp_path: Path):
    """T060: Loading config restores persisted window position and size geometry."""
    config_file = tmp_path / "config.json"
    data = get_default_config()
    data["position"] = {"x": 120, "y": 180}
    data["size"] = 400
    config_file.write_text(json.dumps(data), encoding="utf-8")

    config = load_config(config_file)
    assert config.position.x == 120
    assert config.position.y == 180
    assert config.size == 400


def test_t070_live_threshold_update_without_restart():
    """T070: Updating threshold bounds invokes observer callbacks with new thresholds."""
    data = get_default_config()
    validated = validate_config(data)
    from boostgauge.config import dict_to_app_config

    config = dict_to_app_config(validated)
    manager = ConfigManager(config, Path("/fake/path.json"))

    received_thresholds: list[ThresholdConfig] = []

    def callback(updated: ThresholdConfig):
        received_thresholds.append(updated)

    manager.add_threshold_listener(callback)
    manager.update_thresholds({"conpty": {"yellow": 40.0, "red": 70.0}})

    assert len(received_thresholds) == 1
    assert received_thresholds[0].conpty.yellow == 40.0
    assert received_thresholds[0].conpty.red == 70.0


def test_t080_validate_opacity_out_of_bounds():
    """T080: Opacity outside [0.0, 1.0] raises ValueError."""
    data = get_default_config()
    data["opacity"] = 1.5
    with pytest.raises(ValueError, match="opacity must be a float between 0.0 and 1.0"):
        validate_config(data)


def test_t090_validate_negative_size():
    """T090: Negative or zero size raises ValueError."""
    data = get_default_config()
    data["size"] = -50
    with pytest.raises(ValueError, match="size must be a positive integer"):
        validate_config(data)

    with pytest.raises(ValueError, match="size must be a positive integer"):
        parse_cli_args(["--size", "-50"])


def test_t100_validate_unknown_theme_name():
    """T0100: Unsupported theme string raises ValueError."""
    data = get_default_config()
    data["theme"] = "invalid_theme"
    with pytest.raises(ValueError, match="Invalid theme 'invalid_theme'"):
        validate_config(data)


def test_t110_non_existent_custom_config_file_raises():
    """T110: Passing custom non-existent config path raises FileNotFoundError."""
    missing_file = Path("/nonexistent/path/config.json")
    with pytest.raises(FileNotFoundError, match="Config file not found"):
        load_config(missing_file)


def test_platform_default_config_path():
    """Verify get_default_config_path returns correct platform path object."""
    with patch("os.name", "nt"), patch.dict("os.environ", {"APPDATA": "C:\\Users\\Test\\AppData\\Roaming"}):
        nt_path = get_default_config_path()
        assert nt_path == Path("C:\\Users\\Test\\AppData\\Roaming") / "boostgauge" / "config.json"

    with patch("os.name", "posix"), patch("pathlib.Path.home", return_value=Path("/home/testuser")):
        posix_path = get_default_config_path()
        assert posix_path == Path("/home/testuser") / ".boostgauge" / "config.json"
```

---

## 7. Pattern References

### 7.1 Option C Pure Logic GUI Testing Pattern

**File:** `docs/design/0001-test-strategy.md` (lines 33-49)

```markdown
Chosen: Option C — render to off-screen PIL.Image first; tkinter Canvas is a display surface only.
The renderer produces a PIL.Image; tests never instantiate tkinter.Tk().
```

**Relevance:** `test_config.py` tests pure configuration loading, CLI parsing, dictionary validation, and observer registration without initializing `tkinter.Tk()`.

### 7.2 Test Suite Python Path Setup

**File:** `tests/conftest.py` (lines 1-8)

```python
"""Project test bootstrap."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
```

**Relevance:** `conftest.py` ensures `src/` is in `sys.path`, allowing `boostgauge.config` and `boostgauge.app` imports to resolve across pytest runners.

---

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `import json` | stdlib | `src/boostgauge/config.py`, `tests/unit/test_config.py` |
| `import argparse` | stdlib | `src/boostgauge/config.py` |
| `import os` | stdlib | `src/boostgauge/config.py` |
| `import sys` | stdlib | `src/boostgauge/app.py` |
| `from pathlib import Path` | stdlib | `src/boostgauge/config.py`, `src/boostgauge/app.py`, `tests/unit/test_config.py` |
| `from dataclasses import dataclass, asdict` | stdlib | `src/boostgauge/config.py` |
| `from typing import Any, Callable` | stdlib | `src/boostgauge/config.py` |
| `import pytest` | external | `tests/unit/test_config.py` |
| `from unittest.mock import patch` | stdlib | `tests/unit/test_config.py` |

**New Dependencies:** None (All components use Python standard library and standard test harness).

---

## 9. Placeholder

*Reserved for alignment with LLD section numbering.*

---

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `load_config(None)` | `config_path=None` (missing file) | Writes default JSON to `get_default_config_path()`, returns `AppConfig` matching defaults |
| T020 | `load_config(Path)` | Custom valid `config.json` path | Returns `AppConfig` with custom file values |
| T030 | `initialize_config_manager()` | `--reset-config --config path` | Overwrites `path` with default settings and returns default `AppConfig` |
| T040 | `merge_cli_overrides()` | `AppConfig(theme="dark")` + `--theme neon` | Returns `AppConfig` with `theme="neon"` |
| T050 | `ConfigManager.save()` | `update_geometry(150, 200, 350)` + `save()` | Target `config.json` on disk updated with `x=150, y=200, size=350` |
| T060 | `load_config(Path)` | `config.json` containing `x=120, y=180, size=400` | Returns `AppConfig` matching persisted geometry |
| T070 | `ConfigManager.update_thresholds()` | `{"conpty": {"yellow": 40, "red": 70}}` | Invokes registered listeners with updated `ThresholdConfig` |
| T080 | `validate_config()` | Dict with `opacity=1.5` | Raises `ValueError("opacity must be a float between 0.0 and 1.0...")` |
| T090 | `validate_config()` / `parse_cli_args()` | Dict with `size=-50` or CLI `--size -50` | Raises `ValueError("size must be a positive integer...")` |
| T100 | `validate_config()` | Dict with `theme="invalid_theme"` | Raises `ValueError("Invalid theme 'invalid_theme'...")` |
| T110 | `load_config(Path)` | Non-existent custom path | Raises `FileNotFoundError("Config file not found...")` |

---

## 11. Implementation Notes

### 11.1 Atomic Persistence Mechanism

To prevent corruption of `config.json` during unexpected app termination or power loss:
1. `save_config_atomic` serializes `AppConfig` to a temporary file (`config.tmp`) in `config.json`'s parent directory.
2. `os.replace(tmp_path, target_path)` performs an atomic filesystem operation replacing the existing configuration file cleanly.

### 11.2 Error Handling and Fail-Closed Policy

- Missing required keys, out-of-range numerical bounds, invalid enum choices, or malformed JSON trigger fail-closed validation (`ValueError`), terminating startup immediately with explicit diagnostics.
- Recovery is supported via `boostgauge --reset-config`, which overwrites corrupted files with standard default settings.

### 11.3 Observer Notification Logic

`ConfigManager` stores registered callbacks (`_threshold_listeners`). When `update_thresholds()` is called:
1. In-memory `ThresholdConfig` is re-validated and replaced.
2. Each registered listener callback is invoked synchronously with the updated `ThresholdConfig`.

### 11.4 Platform-Independent Path Assertions

In accordance with platform-independence rules (Issue #1841):
- Unit tests compare `pathlib.Path` objects directly (`path == Path.home() / ".boostgauge" / "config.json"`) instead of performing hardcoded separator string matches (`str(path).endswith("dir/file.json")`).

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3 - N/A noted for all-new files)
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
| Finalized | 2026-08-01T07:30:00Z |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #7 |
| Verdict | APPROVED |
| Date | 2026-08-01 |
| Iterations | 0 |
| Finalized | 2026-08-01T12:31:15Z |

### Review Feedback Summary

The implementation spec for Issue #7 is comprehensive, concrete, and fully executable. It covers all required files with complete, ready-to-implement Python source code, precise dataclass schemas, realistic serialization samples, and exhaustive function specifications with input/output examples. All unit test assertions in tests/unit/test_config.py strictly trace to specified behaviors and LLD requirements without contradicting specified logic, inventing unexpected side effects, or failing on sp...
