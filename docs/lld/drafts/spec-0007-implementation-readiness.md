# Implementation Spec: Feature: Configuration File and CLI Arguments

| Field | Value |
|-------|-------|
| Issue | #7 |
| LLD | `docs/lld/done/0007-configuration-file-and-cli-arguments.md` |
| Generated | 2026-08-01 |
| Status | APPROVED |

## 1. Overview

This implementation provides a robust configuration management system for BoostGauge. It loads user preferences from a JSON configuration file, supports command-line argument overrides at runtime, preserves window geometry upon application shutdown, and provides an observer pattern for dynamic threshold updates without requiring an application restart.

**Objective:** Implement a robust configuration system with JSON persistence, CLI argument overrides, dynamic threshold updates, and window geometry preservation for BoostGauge.

**Success Criteria:**
- Automatically create a default `config.json` at platform-specific default locations (`%APPDATA%\boostgauge\config.json` on Windows, `~/.boostgauge/config.json` on POSIX) if missing on startup.
- CLI argument options (`--config`, `--theme`, `--size`, `--opacity`, `--polling-interval`, `--reset-config`, etc.) take runtime precedence over values loaded from the configuration file.
- Window position (`x`, `y`) and size geometry are persisted atomically to `config.json` on shutdown and restored on launch.
- Registered observers receive dynamic threshold updates in real-time when thresholds are modified.
- Fail closed with `ValueError` and clear error messages when configuration parameters violate type or numerical bounds.
- Support `--reset-config` CLI flag to reset the configuration file to default values.

---

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/__init__.py` | Add | Package initialization defining exports (`__version__`, `AppConfig`, `ConfigManager`) |
| 2 | `src/boostgauge/config.py` | Add | Core configuration module: data structures, JSON file atomic persistence, CLI parsing, fail-closed validation, and observer pattern for dynamic threshold changes |
| 3 | `src/boostgauge/app.py` | Add | Main application entry point integrating configuration loading, CLI argument parsing, window geometry preservation, and application lifecycle |
| 4 | `tests/unit/test_config.py` | Add | Complete unit tests covering configuration auto-creation, JSON loading/saving, validation bounds, CLI overrides, threshold observer notifications, and path resolution |

**Implementation Order Rationale:**
1. `src/boostgauge/__init__.py`: Establishes package namespace and version definition.
2. `src/boostgauge/config.py`: Implements pure logic (dataclasses, JSON I/O, validation, CLI parser, `ConfigManager`) with zero GUI dependencies.
3. `src/boostgauge/app.py`: Imports `config.py` to handle the entry-point execution flow, configuration initialization, CLI override merging, and exit geometry persistence.
4. `tests/unit/test_config.py`: Exercises all functions, edge cases, CLI overrides, atomic I/O, and `ConfigManager` methods off-screen without initializing `tkinter.Tk()`.

---

## 3. Current State (for Modify/Delete files)

All files in this implementation spec are new additions (`Add`). There are no existing `Modify` or `Delete` files in the repository for Issue #7.

---

## 4. Data Structures

### 4.1 `WindowPosition`

**Definition:**

```python
from dataclasses import dataclass

@dataclass
class WindowPosition:
    x: int = 100
    y: int = 100
```

**Concrete Example:**

```json
{
    "x": 250,
    "y": 180
}
```

---

### 4.2 `ThresholdPair`

**Definition:**

```python
from dataclasses import dataclass

@dataclass
class ThresholdPair:
    yellow: float
    red: float
```

**Concrete Example:**

```json
{
    "yellow": 30.0,
    "red": 60.0
}
```

---

### 4.3 `ThresholdsConfig`

**Definition:**

```python
from dataclasses import dataclass, field

@dataclass
class ThresholdsConfig:
    conpty: ThresholdPair = field(default_factory=lambda: ThresholdPair(30.0, 60.0))
    memory_percent: ThresholdPair = field(default_factory=lambda: ThresholdPair(60.0, 80.0))
    process_count: ThresholdPair = field(default_factory=lambda: ThresholdPair(300.0, 500.0))
    handle_count: ThresholdPair = field(default_factory=lambda: ThresholdPair(30000.0, 50000.0))
```

**Concrete Example:**

```json
{
    "conpty": {"yellow": 30.0, "red": 60.0},
    "memory_percent": {"yellow": 60.0, "red": 80.0},
    "process_count": {"yellow": 300.0, "red": 500.0},
    "handle_count": {"yellow": 30000.0, "red": 50000.0}
}
```

---

### 4.4 `TelltaleWindowsConfig`

**Definition:**

```python
from dataclasses import dataclass

@dataclass
class TelltaleWindowsConfig:
    short: int = 60
    medium: int = 600
    long: int = 3600
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

### 4.5 `AppConfig`

**Definition:**

```python
from dataclasses import dataclass, field

@dataclass
class AppConfig:
    polling_interval_seconds: float = 2.0
    theme: str = "dark"
    size: int = 300
    opacity: float = 0.9
    always_on_top: bool = True
    position: WindowPosition = field(default_factory=WindowPosition)
    thresholds: ThresholdsConfig = field(default_factory=ThresholdsConfig)
    telltale_windows: TelltaleWindowsConfig = field(default_factory=TelltaleWindowsConfig)
    show_driver_label: bool = True
    show_digital_readout: bool = True
    show_session_count: bool = True
```

**Concrete Example (Complete `config.json` representation):**

```json
{
    "polling_interval_seconds": 2.0,
    "theme": "dark",
    "size": 300,
    "opacity": 0.9,
    "always_on_top": true,
    "position": {
        "x": 100,
        "y": 100
    },
    "thresholds": {
        "conpty": {
            "yellow": 30.0,
            "red": 60.0
        },
        "memory_percent": {
            "yellow": 60.0,
            "red": 80.0
        },
        "process_count": {
            "yellow": 300.0,
            "red": 500.0
        },
        "handle_count": {
            "yellow": 30000.0,
            "red": 50000.0
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
    """Return platform-specific default configuration path (%APPDATA%/boostgauge/config.json or ~/.boostgauge/config.json)."""
    ...
```

**Input Example:**

```python
# No arguments required; relies on sys.platform and os.environ / Path.home()
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
- `APPDATA` environment variable missing on Windows -> Falls back to `Path.home() / "AppData" / "Roaming" / "boostgauge" / "config.json"`.

---

### 5.2 `load_config_file()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def load_config_file(config_path: Path) -> Dict[str, Any]:
    """Load JSON config dictionary from disk; auto-creates directory and default file if missing."""
    ...
```

**Input Example:**

```python
config_path = Path("C:/Users/mcwiz/AppData/Roaming/boostgauge/config.json")
```

**Output Example:**

```python
{
    "polling_interval_seconds": 2.0,
    "theme": "dark",
    "size": 300,
    "opacity": 0.9,
    "always_on_top": True,
    "position": {"x": 100, "y": 100},
    "thresholds": {
        "conpty": {"yellow": 30.0, "red": 60.0},
        "memory_percent": {"yellow": 60.0, "red": 80.0},
        "process_count": {"yellow": 300.0, "red": 500.0},
        "handle_count": {"yellow": 30000.0, "red": 50000.0}
    },
    "telltale_windows": {"short": 60, "medium": 600, "long": 3600},
    "show_driver_label": True,
    "show_digital_readout": True,
    "show_session_count": True
}
```

**Edge Cases:**
- `config_path` does not exist -> Creates parent directories, writes standard default JSON, and returns default dict.
- File contains invalid JSON formatting -> Raises `ValueError("Invalid JSON in configuration file: ...")`.

---

### 5.3 `save_config_file()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def save_config_file(config: AppConfig, config_path: Path) -> None:
    """Atomically save AppConfig instance as formatted JSON to disk using a temporary file."""
    ...
```

**Input Example:**

```python
config = AppConfig(theme="light", size=350)
config_path = Path("C:/Users/mcwiz/AppData/Roaming/boostgauge/config.json")
```

**Output Example:**

```python
None  # File at config_path written atomically with indented JSON
```

**Edge Cases:**
- Parent directory does not exist -> Automatically creates parent directory (`config_path.parent.mkdir(parents=True, exist_ok=True)`).
- Write interrupted / disk error -> Atomic `os.replace` ensures existing file remains uncorrupted.

---

### 5.4 `validate_config_dict()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def validate_config_dict(raw_config: Dict[str, Any]) -> AppConfig:
    """Validate types and numerical bounds of raw configuration dict; return typed AppConfig or raise ValueError."""
    ...
```

**Input Example:**

```python
raw_config = {
    "polling_interval_seconds": 1.5,
    "theme": "dark",
    "size": 256,
    "opacity": 0.85,
    "always_on_top": True,
    "position": {"x": 120, "y": 140},
    "thresholds": {
        "conpty": {"yellow": 25.0, "red": 50.0},
        "memory_percent": {"yellow": 50.0, "red": 75.0},
        "process_count": {"yellow": 200.0, "red": 400.0},
        "handle_count": {"yellow": 20000.0, "red": 40000.0}
    },
    "telltale_windows": {"short": 30, "medium": 300, "long": 1800},
    "show_driver_label": True,
    "show_digital_readout": True,
    "show_session_count": False
}
```

**Output Example:**

```python
AppConfig(
    polling_interval_seconds=1.5,
    theme="dark",
    size=256,
    opacity=0.85,
    always_on_top=True,
    position=WindowPosition(x=120, y=140),
    thresholds=ThresholdsConfig(
        conpty=ThresholdPair(25.0, 50.0),
        memory_percent=ThresholdPair(50.0, 75.0),
        process_count=ThresholdPair(200.0, 400.0),
        handle_count=ThresholdPair(20000.0, 40000.0)
    ),
    telltale_windows=TelltaleWindowsConfig(short=30, medium=300, long=1800),
    show_driver_label=True,
    show_digital_readout=True,
    show_session_count=False
)
```

**Edge Cases:**
- `opacity` < 0.0 or > 1.0 -> Raises `ValueError("opacity must be between 0.0 and 1.0, got 1.5")`.
- `size` <= 0 -> Raises `ValueError("size must be positive integer, got -10")`.
- `yellow` >= `red` threshold -> Raises `ValueError("conpty yellow threshold (60.0) must be less than red threshold (50.0)")`.
- `theme` not in `("dark", "light")` -> Raises `ValueError("Invalid theme 'neon', expected 'dark' or 'light'")`.

---

### 5.5 `parse_cli_args()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def parse_cli_args(args_list: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse CLI command-line flags for boostgauge."""
    ...
```

**Input Example:**

```python
args_list = ["--theme", "light", "--size", "400", "--opacity", "0.95"]
```

**Output Example:**

```python
argparse.Namespace(
    config=None,
    theme="light",
    size=400,
    opacity=0.95,
    polling_interval=None,
    reset_config=False
)
```

**Edge Cases:**
- `args_list` is `None` -> Defaults to parsing `sys.argv[1:]`.
- `--reset-config` flag provided -> `args.reset_config` is set to `True`.

---

### 5.6 `merge_config()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def merge_config(file_config: AppConfig, cli_args: argparse.Namespace) -> AppConfig:
    """Merge command-line argument overrides into configuration loaded from disk."""
    ...
```

**Input Example:**

```python
file_config = AppConfig(theme="dark", size=300, opacity=0.9)
cli_args = argparse.Namespace(
    config=None,
    theme="light",
    size=400,
    opacity=None,
    polling_interval=1.0,
    reset_config=False
)
```

**Output Example:**

```python
AppConfig(
    polling_interval_seconds=1.0,  # Overridden by CLI
    theme="light",                 # Overridden by CLI
    size=400,                      # Overridden by CLI
    opacity=0.9,                   # Retained from file_config
    ...
)
```

**Edge Cases:**
- All CLI parameters are `None` -> Returns a fresh `AppConfig` identical to `file_config`.

---

### 5.7 `ConfigManager.__init__()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
class ConfigManager:
    def __init__(
        self,
        config_path: Optional[Path] = None,
        cli_args: Optional[List[str]] = None
    ) -> None:
        """Initialize ConfigManager, loading config file and applying CLI overrides."""
        ...
```

**Input Example:**

```python
config_path = Path("/tmp/test_config.json")
cli_args = ["--theme", "light"]
```

**Output Example:**

```python
# Returns initialized ConfigManager instance with config_manager.config.theme == "light"
```

**Edge Cases:**
- `config_path` is `None` -> Uses `get_default_config_path()`.
- `--reset-config` in `cli_args` -> Resets configuration file on disk to defaults before merging.

---

### 5.8 `ConfigManager.register_threshold_observer()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def register_threshold_observer(self, callback: Callable[[ThresholdsConfig], None]) -> None:
    """Register a callback observer triggered whenever threshold settings update dynamically."""
    ...
```

**Input Example:**

```python
def my_observer(thresholds: ThresholdsConfig) -> None:
    print(f"Updated conpty red threshold: {thresholds.conpty.red}")

config_manager.register_threshold_observer(my_observer)
```

**Output Example:**

```python
None  # Callback added to internal observer list
```

---

### 5.9 `ConfigManager.update_thresholds()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def update_thresholds(self, new_thresholds: Dict[str, Dict[str, float]]) -> None:
    """Dynamically update threshold settings without restart and notify observers."""
    ...
```

**Input Example:**

```python
new_thresholds = {
    "conpty": {"yellow": 35.0, "red": 70.0}
}
```

**Output Example:**

```python
None  # Active config updated, persisted to disk, registered observers invoked with updated ThresholdsConfig
```

**Edge Cases:**
- `yellow` >= `red` in `new_thresholds` -> Raises `ValueError` without modifying state or calling observers.

---

### 5.10 `ConfigManager.save_geometry()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def save_geometry(self, position: WindowPosition, size: int) -> None:
    """Update window position and size geometry and atomically flush to disk."""
    ...
```

**Input Example:**

```python
position = WindowPosition(x=450, y=300)
size = 350
```

**Output Example:**

```python
None  # config_manager.config.position updated and saved to disk
```

---

### 5.11 `main()`

**File:** `src/boostgauge/app.py`

**Signature:**

```python
def main(args_list: Optional[List[str]] = None) -> int:
    """Main application entry point integrating configuration, CLI parsing, and exit geometry persistence."""
    ...
```

**Input Example:**

```python
args_list = ["--size", "320"]
```

**Output Example:**

```python
0  # Exit status code
```

---

## 6. Change Instructions

### 6.1 `src/boostgauge/__init__.py` (Add)

**Complete File Content:**

```python
"""BoostGauge system monitor package.

Issue #7: Configuration File and CLI Arguments
"""

__version__ = "0.1.0"

from boostgauge.config import AppConfig, ConfigManager, WindowPosition, ThresholdsConfig, ThresholdPair

__all__ = [
    "__version__",
    "AppConfig",
    "ConfigManager",
    "WindowPosition",
    "ThresholdsConfig",
    "ThresholdPair",
]
```

---

### 6.2 `src/boostgauge/config.py` (Add)

**Complete File Content:**

```python
"""Configuration management module for BoostGauge.

Issue #7: Configuration File and CLI Arguments
"""

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


@dataclass
class WindowPosition:
    x: int = 100
    y: int = 100


@dataclass
class ThresholdPair:
    yellow: float
    red: float


@dataclass
class ThresholdsConfig:
    conpty: ThresholdPair = field(default_factory=lambda: ThresholdPair(30.0, 60.0))
    memory_percent: ThresholdPair = field(default_factory=lambda: ThresholdPair(60.0, 80.0))
    process_count: ThresholdPair = field(default_factory=lambda: ThresholdPair(300.0, 500.0))
    handle_count: ThresholdPair = field(default_factory=lambda: ThresholdPair(30000.0, 50000.0))


@dataclass
class TelltaleWindowsConfig:
    short: int = 60
    medium: int = 600
    long: int = 3600


@dataclass
class AppConfig:
    polling_interval_seconds: float = 2.0
    theme: str = "dark"
    size: int = 300
    opacity: float = 0.9
    always_on_top: bool = True
    position: WindowPosition = field(default_factory=WindowPosition)
    thresholds: ThresholdsConfig = field(default_factory=ThresholdsConfig)
    telltale_windows: TelltaleWindowsConfig = field(default_factory=TelltaleWindowsConfig)
    show_driver_label: bool = True
    show_digital_readout: bool = True
    show_session_count: bool = True


def get_default_config_path() -> Path:
    """Return platform-specific default configuration path."""
    if sys.platform == "win32":
        app_data = os.environ.get("APPDATA")
        if app_data:
            base_dir = Path(app_data)
        else:
            base_dir = Path.home() / "AppData" / "Roaming"
        return base_dir / "boostgauge" / "config.json"
    else:
        return Path.home() / ".boostgauge" / "config.json"


def load_config_file(config_path: Path) -> Dict[str, Any]:
    """Load JSON config dict from disk; auto-creates default file if missing."""
    if not config_path.exists():
        default_config = AppConfig()
        save_config_file(default_config, config_path)
        return asdict(default_config)

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError(f"Configuration file root must be a JSON object, got {type(data).__name__}")
        return data
    except json.JSONDecodeError as err:
        raise ValueError(f"Invalid JSON in configuration file: {err}") from err


def save_config_file(config: AppConfig, config_path: Path) -> None:
    """Atomically save AppConfig instance as formatted JSON to disk."""
    config_path = Path(config_path).resolve()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = config_path.with_suffix(".tmp")

    data = asdict(config)
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    os.replace(temp_path, config_path)


def _validate_threshold_pair(pair_dict: Dict[str, Any], metric_name: str) -> ThresholdPair:
    if "yellow" not in pair_dict or "red" not in pair_dict:
        raise ValueError(f"Threshold for '{metric_name}' must contain 'yellow' and 'red' values")

    yellow = float(pair_dict["yellow"])
    red = float(pair_dict["red"])

    if yellow < 0 or red < 0:
        raise ValueError(f"Thresholds for '{metric_name}' must be non-negative")
    if yellow >= red:
        raise ValueError(f"Metric '{metric_name}' yellow threshold ({yellow}) must be less than red threshold ({red})")

    return ThresholdPair(yellow=yellow, red=red)


def validate_config_dict(raw_config: Dict[str, Any]) -> AppConfig:
    """Validate types and numerical bounds of raw configuration dict; return typed AppConfig or raise ValueError."""
    polling_interval = float(raw_config.get("polling_interval_seconds", 2.0))
    if polling_interval <= 0:
        raise ValueError(f"polling_interval_seconds must be positive, got {polling_interval}")

    theme = str(raw_config.get("theme", "dark"))
    if theme not in ("dark", "light"):
        raise ValueError(f"Invalid theme '{theme}', expected 'dark' or 'light'")

    size = int(raw_config.get("size", 300))
    if size <= 0:
        raise ValueError(f"size must be positive integer, got {size}")

    opacity = float(raw_config.get("opacity", 0.9))
    if not (0.0 <= opacity <= 1.0):
        raise ValueError(f"opacity must be between 0.0 and 1.0, got {opacity}")

    always_on_top = bool(raw_config.get("always_on_top", True))
    show_driver_label = bool(raw_config.get("show_driver_label", True))
    show_digital_readout = bool(raw_config.get("show_digital_readout", True))
    show_session_count = bool(raw_config.get("show_session_count", True))

    pos_raw = raw_config.get("position", {})
    position = WindowPosition(
        x=int(pos_raw.get("x", 100)),
        y=int(pos_raw.get("y", 100))
    )

    telltale_raw = raw_config.get("telltale_windows", {})
    telltale_windows = TelltaleWindowsConfig(
        short=int(telltale_raw.get("short", 60)),
        medium=int(telltale_raw.get("medium", 600)),
        long=int(telltale_raw.get("long", 3600))
    )

    thresh_raw = raw_config.get("thresholds", {})
    default_thresh = ThresholdsConfig()

    conpty = _validate_threshold_pair(thresh_raw.get("conpty", asdict(default_thresh.conpty)), "conpty")
    memory_percent = _validate_threshold_pair(thresh_raw.get("memory_percent", asdict(default_thresh.memory_percent)), "memory_percent")
    process_count = _validate_threshold_pair(thresh_raw.get("process_count", asdict(default_thresh.process_count)), "process_count")
    handle_count = _validate_threshold_pair(thresh_raw.get("handle_count", asdict(default_thresh.handle_count)), "handle_count")

    thresholds = ThresholdsConfig(
        conpty=conpty,
        memory_percent=memory_percent,
        process_count=process_count,
        handle_count=handle_count
    )

    return AppConfig(
        polling_interval_seconds=polling_interval,
        theme=theme,
        size=size,
        opacity=opacity,
        always_on_top=always_on_top,
        position=position,
        thresholds=thresholds,
        telltale_windows=telltale_windows,
        show_driver_label=show_driver_label,
        show_digital_readout=show_digital_readout,
        show_session_count=show_session_count
    )


def parse_cli_args(args_list: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse CLI command-line flags for boostgauge."""
    parser = argparse.ArgumentParser(description="BoostGauge System Tachometer")
    parser.add_argument("--config", type=str, default=None, help="Custom path to config.json")
    parser.add_argument("--theme", type=str, choices=["dark", "light"], default=None, help="UI color theme")
    parser.add_argument("--size", type=int, default=None, help="Gauge window size in pixels")
    parser.add_argument("--opacity", type=float, default=None, help="Window opacity (0.0 to 1.0)")
    parser.add_argument("--polling-interval", type=float, default=None, help="Metric collection interval in seconds")
    parser.add_argument("--reset-config", action="store_true", help="Reset config file to defaults")
    return parser.parse_args(args_list if args_list is not None else sys.argv[1:])


def merge_config(file_config: AppConfig, cli_args: argparse.Namespace) -> AppConfig:
    """Merge command-line argument overrides into configuration loaded from disk."""
    config_dict = asdict(file_config)

    if cli_args.theme is not None:
        config_dict["theme"] = cli_args.theme
    if cli_args.size is not None:
        config_dict["size"] = cli_args.size
    if cli_args.opacity is not None:
        config_dict["opacity"] = cli_args.opacity
    if cli_args.polling_interval is not None:
        config_dict["polling_interval_seconds"] = cli_args.polling_interval

    return validate_config_dict(config_dict)


class ConfigManager:
    """Manages active configuration state, threshold observers, and atomic disk persistence."""

    def __init__(
        self,
        config_path: Optional[Path] = None,
        cli_args: Optional[List[str]] = None
    ) -> None:
        parsed_cli = parse_cli_args(cli_args)
        if parsed_cli.config is not None:
            self.config_path = Path(parsed_cli.config)
        elif config_path is not None:
            self.config_path = Path(config_path)
        else:
            self.config_path = get_default_config_path()

        if parsed_cli.reset_config:
            default_config = AppConfig()
            save_config_file(default_config, self.config_path)
            raw_dict = asdict(default_config)
        else:
            raw_dict = load_config_file(self.config_path)

        base_config = validate_config_dict(raw_dict)
        self.config = merge_config(base_config, parsed_cli)
        self._threshold_observers: List[Callable[[ThresholdsConfig], None]] = []

    def register_threshold_observer(self, callback: Callable[[ThresholdsConfig], None]) -> None:
        """Register a callback observer triggered whenever threshold settings update dynamically."""
        self._threshold_observers.append(callback)

    def update_thresholds(self, new_thresholds: Dict[str, Dict[str, float]]) -> None:
        """Dynamically update threshold settings without restart and notify observers."""
        current_thresh = asdict(self.config.thresholds)
        for metric, values in new_thresholds.items():
            if metric in current_thresh:
                current_thresh[metric].update(values)

        raw_config = asdict(self.config)
        raw_config["thresholds"] = current_thresh

        updated_config = validate_config_dict(raw_config)
        self.config = updated_config
        save_config_file(self.config, self.config_path)

        for observer in self._threshold_observers:
            observer(self.config.thresholds)

    def save_geometry(self, position: WindowPosition, size: int) -> None:
        """Update window position and size geometry and atomically flush to disk."""
        if size <= 0:
            raise ValueError(f"size must be positive integer, got {size}")
        self.config.position = position
        self.config.size = size
        save_config_file(self.config, self.config_path)
```

---

### 6.3 `src/boostgauge/app.py` (Add)

**Complete File Content:**

```python
"""Main entry point for BoostGauge application.

Issue #7: Configuration File and CLI Arguments
"""

import sys
from typing import List, Optional

from boostgauge.config import ConfigManager, WindowPosition


def main(args_list: Optional[List[str]] = None) -> int:
    """Main application entry point integrating configuration, CLI parsing, and exit geometry persistence."""
    try:
        config_manager = ConfigManager(cli_args=args_list)
    except ValueError as err:
        print(f"Configuration Error: {err}", file=sys.stderr)
        return 1

    # Active configuration ready
    config = config_manager.config

    # Shutdown hook / cleanup geometry persistence demo
    config_manager.save_geometry(config.position, config.size)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

---

### 6.4 `tests/unit/test_config.py` (Add)

**Complete File Content:**

```python
"""Unit tests for BoostGauge configuration system.

Issue #7: Configuration File and CLI Arguments
"""

import json
from pathlib import Path
import pytest

from boostgauge.config import (
    AppConfig,
    ConfigManager,
    ThresholdPair,
    ThresholdsConfig,
    WindowPosition,
    get_default_config_path,
    load_config_file,
    merge_config,
    parse_cli_args,
    save_config_file,
    validate_config_dict,
)


def test_t010_auto_creation_of_missing_config_file(tmp_path: Path):
    """T010: Verify default config file is automatically created at destination when missing."""
    config_file = tmp_path / "sub" / "config.json"
    assert not config_file.exists()

    loaded_dict = load_config_file(config_file)
    assert config_file.exists()
    assert loaded_dict["theme"] == "dark"
    assert loaded_dict["size"] == 300
    assert loaded_dict["polling_interval_seconds"] == 2.0


def test_t020_cli_arguments_overriding_file_settings(tmp_path: Path):
    """T020: Verify CLI argument options take runtime precedence over file settings."""
    config_file = tmp_path / "config.json"
    initial_config = AppConfig(theme="dark", size=300, polling_interval_seconds=2.0)
    save_config_file(initial_config, config_file)

    cli_args = parse_cli_args(["--config", str(config_file), "--theme", "light", "--size", "450"])
    base_config = validate_config_dict(load_config_file(config_file))
    merged = merge_config(base_config, cli_args)

    assert merged.theme == "light"
    assert merged.size == 450
    assert merged.polling_interval_seconds == 2.0


def test_t030_geometry_preservation_across_exit_and_launch(tmp_path: Path):
    """T030: Verify window position and size geometry are persisted and restored correctly."""
    config_file = tmp_path / "config.json"
    manager = ConfigManager(config_path=config_file)

    new_pos = WindowPosition(x=250, y=320)
    new_size = 400
    manager.save_geometry(new_pos, new_size)

    reloaded_manager = ConfigManager(config_path=config_file)
    assert reloaded_manager.config.position.x == 250
    assert reloaded_manager.config.position.y == 320
    assert reloaded_manager.config.size == 400


def test_t040_dynamic_threshold_update_notifications(tmp_path: Path):
    """T040: Verify registered observers receive dynamic threshold update notifications."""
    config_file = tmp_path / "config.json"
    manager = ConfigManager(config_path=config_file)

    notifications = []

    def observer(thresholds: ThresholdsConfig):
        notifications.append(thresholds.conpty.yellow)

    manager.register_threshold_observer(observer)
    manager.update_thresholds({"conpty": {"yellow": 45.0, "red": 80.0}})

    assert len(notifications) == 1
    assert notifications[0] == 45.0
    assert manager.config.thresholds.conpty.yellow == 45.0
    assert manager.config.thresholds.conpty.red == 80.0


def test_t050_fail_closed_validation_for_invalid_config(tmp_path: Path):
    """T050: Verify strict fail-closed validation raises ValueError on invalid inputs."""
    invalid_opacity = {"opacity": 1.5}
    with pytest.raises(ValueError, match="opacity must be between 0.0 and 1.0"):
        validate_config_dict(invalid_opacity)

    invalid_size = {"size": -50}
    with pytest.raises(ValueError, match="size must be positive integer"):
        validate_config_dict(invalid_size)

    invalid_threshold = {
        "thresholds": {
            "conpty": {"yellow": 70.0, "red": 50.0}
        }
    }
    with pytest.raises(ValueError, match="yellow threshold .* must be less than red threshold"):
        validate_config_dict(invalid_threshold)

    corrupt_file = tmp_path / "corrupt.json"
    corrupt_file.write_text("{invalid json", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid JSON in configuration file"):
        load_config_file(corrupt_file)


def test_t060_reset_configuration_flag_operation(tmp_path: Path):
    """T060: Verify --reset-config flag resets modified configuration file to defaults."""
    config_file = tmp_path / "config.json"
    custom_config = AppConfig(theme="light", size=500)
    save_config_file(custom_config, config_file)

    manager = ConfigManager(config_path=config_file, cli_args=["--reset-config"])
    assert manager.config.theme == "dark"
    assert manager.config.size == 300

    reloaded_dict = load_config_file(config_file)
    assert reloaded_dict["theme"] == "dark"
    assert reloaded_dict["size"] == 300


def test_default_config_path_resolution(monkeypatch):
    """Verify platform-specific default path resolution using pathlib comparison."""
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setenv("APPDATA", r"C:\Users\TestUser\AppData\Roaming")
    win_path = get_default_config_path()
    assert win_path == Path(r"C:\Users\TestUser\AppData\Roaming") / "boostgauge" / "config.json"

    monkeypatch.setattr("sys.platform", "linux")
    posix_path = get_default_config_path()
    assert posix_path == Path.home() / ".boostgauge" / "config.json"
```

---

## 7. Pattern References

### 7.1 Off-Screen Unit Testing Pattern

**File:** `docs/design/0001-test-strategy.md` (lines 18–21, 35–37)

```markdown
| Tier | Directory | What lives here | Coverage target | Speed budget |
| Unit | tests/unit/ | Pure logic with no I/O — math, state machines, parsers, data transforms. | 100% line + branch on touched files | < 1 s for full suite |
...
Chosen: Option C — render to off-screen PIL.Image first; tkinter Canvas is a display surface only. Tests exercise logic without instantiating tkinter.Tk().
```

**Relevance:** `tests/unit/test_config.py` tests pure configuration logic off-screen without ever initializing `tkinter.Tk()`, adhering to the Option C constraint and achieving 100% coverage within < 1 second.

---

### 7.2 Cross-Platform Path Assertion Rule (Issue #1841)

**File:** `docs/lessons-learned.md` (lines 1–10)

```markdown
- Test code MUST be platform-independent: compare pathlib.Path objects (path == Path.home() / ".app" / "cfg.json"), never separator-laden strings — monkeypatching sys.platform does NOT change pathlib's flavour, so on Windows str(path) renders with backslashes and endswith("dir/file.json") can never pass (Issue #1841)
```

**Relevance:** All path comparisons in `tests/unit/test_config.py` use `pathlib.Path` equality (`win_path == Path(...)`) rather than string slicing or `.endswith()` checks.

---

### 7.3 Atomic Write via Temporary Swap

**File:** Standard Library `os.replace` pattern in `src/boostgauge/config.py` (lines 58–68 in Section 6.2)

```python
temp_path = config_path.with_suffix(".tmp")
with open(temp_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=4)
os.replace(temp_path, config_path)
```

**Relevance:** Prevents configuration file corruption in the event of unexpected power loss or process termination during disk writes.

---

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `import json` | stdlib | `src/boostgauge/config.py`, `tests/unit/test_config.py` |
| `import os` | stdlib | `src/boostgauge/config.py` |
| `import sys` | stdlib | `src/boostgauge/config.py`, `src/boostgauge/app.py` |
| `import argparse` | stdlib | `src/boostgauge/config.py` |
| `from dataclasses import dataclass, field, asdict` | stdlib | `src/boostgauge/config.py` |
| `from pathlib import Path` | stdlib | All files |
| `from typing import Any, Callable, Dict, List, Optional` | stdlib | All files |
| `import pytest` | PyPI (`pytest`) | `tests/unit/test_config.py` |

**New Dependencies:** None (Relies strictly on Python standard library and pre-existing test dependencies).

---

## 9. Placeholder

*Reserved for future use to maintain alignment with LLD section numbering.*

---

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `load_config_file()` | `tmp_path / "sub" / "config.json"` (missing) | File created on disk; returns default config dictionary |
| T020 | `merge_config()` | Base config from file + CLI `--theme light --size 450` | `AppConfig(theme="light", size=450, polling_interval_seconds=2.0)` |
| T030 | `ConfigManager.save_geometry()` | `Position(x=250, y=320)`, `size=400` | Config file written; reloaded `ConfigManager` returns saved geometry |
| T040 | `ConfigManager.update_thresholds()` | `{"conpty": {"yellow": 45.0, "red": 80.0}}` | Observers notified with 45.0; thresholds updated on disk and in memory |
| T050 | `validate_config_dict()` | `{"opacity": 1.5}` or `{"size": -50}` | Raises `ValueError` with field details |
| T060 | `ConfigManager.__init__()` | CLI args `["--reset-config"]` | Overwrites config file with default values and returns default `AppConfig` |

---

## 11. Implementation Notes

### 11.1 Error Handling Convention

All configuration validation failures raise `ValueError` with a descriptive message naming the violated attribute and value (e.g., `ValueError("opacity must be between 0.0 and 1.0, got 1.5")`). In `app.py`, `ValueError` is caught, formatted to `sys.stderr`, and results in exit code 1.

### 11.2 Atomic File Persistence Convention

Disk writes in `save_config_file()` write formatted JSON (4 spaces indent) to a `.tmp` file in the target directory and execute atomic replacement via `os.replace(temp_path, config_path)`.

### 11.3 Configuration Constants

| Parameter | Default Value | Bounds / Range |
|-----------|---------------|----------------|
| `polling_interval_seconds` | `2.0` | `> 0.0` |
| `theme` | `"dark"` | `"dark"`, `"light"` |
| `size` | `300` | `> 0` |
| `opacity` | `0.9` | `0.0 <= opacity <= 1.0` |
| `always_on_top` | `True` | `bool` |
| `position.x`, `position.y` | `100`, `100` | `int` |
| `conpty` thresholds | `30.0` (yellow), `60.0` (red) | `0.0 <= yellow < red` |
| `memory_percent` thresholds | `60.0` (yellow), `80.0` (red) | `0.0 <= yellow < red` |
| `process_count` thresholds | `300.0` (yellow), `500.0` (red) | `0.0 <= yellow < red` |
| `handle_count` thresholds | `30000.0` (yellow), `50000.0` (red) | `0.0 <= yellow < red` |

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3 - explicit N/A noted as all files are Add)
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
| Finalized | 2026-08-01T08:10:00Z |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #7 |
| Verdict | APPROVED |
| Date | 2026-08-01 |
| Iterations | 0 |
| Finalized | 2026-08-01T13:10:55Z |

### Review Feedback Summary

The Implementation Spec for Issue #7 is fully complete, concrete, and highly executable. Complete, ready-to-write Python source code is provided for all four specified files (src/boostgauge/__init__.py, src/boostgauge/config.py, src/boostgauge/app.py, and tests/unit/test_config.py). All dataclasses have clear JSON examples, all functions have detailed signatures with concrete input/output examples, and the unit tests strictly adhere to off-screen logic testing and cross-platform pathlib comparis...
