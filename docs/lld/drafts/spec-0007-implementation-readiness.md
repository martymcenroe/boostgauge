# Implementation Spec: Feature: Configuration File and CLI Arguments

<!-- Metadata -->
| Field | Value |
|-------|-------|
| Issue | #7 |
| LLD | `docs/lld/done/0007-configuration-file-and-cli-arguments.md` |
| Generated | 2026-08-01 |
| Status | APPROVED |

## 1. Overview

This implementation spec defines the configuration system for BoostGauge. It establishes strongly-typed JSON configuration persistence, CLI argument overrides, dynamic threshold observer updates, strict parameter validation, and atomic file saving for window geometry preservation.

**Objective:** Implement a robust configuration system with JSON persistence, CLI argument overrides, dynamic threshold updates, and window geometry preservation for BoostGauge.

**Success Criteria:**
- Default configuration file is automatically created at platform-specific paths (`%APPDATA%\boostgauge\config.json` on Windows, `~/.boostgauge/config.json` on POSIX) on first launch if absent.
- CLI flags override loaded configuration settings in memory during runtime without modifying un-saved disk values.
- `--reset-config` flag overwrites target configuration file with default JSON settings.
- Window geometry (x, y position and size) is updated in state and saved atomically to disk using `.tmp` write and `os.replace`.
- Observers receive immediate notifications when threshold values update dynamically at runtime.
- Invalid configuration parameters (out-of-bound ranges, unknown themes, invalid thresholds) raise explicit `ValueError` exceptions failing closed.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/__init__.py` | Add | Package initialization file exposing package version `__version__` |
| 2 | `src/boostgauge/config.py` | Add | Core configuration dataclasses, path resolution, JSON serialization, CLI parser, merge logic, validation guards, dynamic threshold observer pattern, and atomic disk persistence |
| 3 | `src/boostgauge/app.py` | Add | Application entry point integrating `ConfigManager` lifecycle, CLI parsing, geometry update helpers, and metric loop bootstrapping |
| 4 | `tests/unit/test_config.py` | Add | Unit test suite validating config file auto-creation, platform path resolution, CLI overrides, atomic save integrity, threshold observers, and strict validation |

**Implementation Order Rationale:**
1. `src/boostgauge/__init__.py` establishes module package metadata.
2. `src/boostgauge/config.py` contains all dataclasses and configuration logic, operating cleanly without GUI dependencies.
3. `src/boostgauge/app.py` imports `src/boostgauge/config.py` to bootstrap CLI parsing and application lifecycle.
4. `tests/unit/test_config.py` verifies all `config.py` functions in isolation per Option C of `docs/design/0001-test-strategy.md` (no `tkinter` GUI context needed).

## 3. Current State (for Modify/Delete files)

*No files are being modified or deleted; all files listed in Section 2 are new ('Add').*

## 4. Data Structures

### 4.1 Dataclass Definitions

```python
from dataclasses import dataclass, field
from typing import Dict, Any, Tuple, Optional, Callable
from pathlib import Path

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
```

### 4.2 Concrete Serialized Configuration JSON Example

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

## 5. Function Specifications

### 5.1 `get_default_config_path()`

**File:** `src/boostgauge/config.py`

**Signature:**
```python
def get_default_config_path() -> Path:
    """Return the platform-specific default path for the configuration file."""
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
- `%APPDATA%` environment variable missing or empty on Windows -> Fall back to `Path.home() / "AppData" / "Roaming" / "boostgauge" / "config.json"`.

---

### 5.2 `load_config_file()`

**File:** `src/boostgauge/config.py`

**Signature:**
```python
def load_config_file(config_path: Path) -> dict[str, Any]:
    """Load and parse JSON configuration file. Create file with defaults if missing."""
    ...
```

**Input Example:**
```python
config_path = Path("/tmp/test_config/config.json")
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
- `config_path` does not exist -> creates parent directories, writes standard default JSON, and returns default config dictionary.
- File contains invalid/corrupted JSON -> raises `ValueError("Invalid JSON in configuration file: ...")`.

---

### 5.3 `parse_cli_args()`

**File:** `src/boostgauge/config.py`

**Signature:**
```python
def parse_cli_args(args_list: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments provided to boostgauge executable."""
    ...
```

**Input Example:**
```python
args_list = ["--theme", "neon", "--poll", "5.0", "--no-topmost"]
```

**Output Example:**
```python
argparse.Namespace(
    config=None,
    reset_config=False,
    theme="neon",
    size=None,
    poll=5.0,
    opacity=None,
    topmost=False
)
```

**Edge Cases:**
- `args_list=None` -> parses `sys.argv[1:]`.
- Invalid flag name passed -> `argparse` prints error and raises `SystemExit`.

---

### 5.4 `merge_cli_overrides()`

**File:** `src/boostgauge/config.py`

**Signature:**
```python
def merge_cli_overrides(config_dict: dict[str, Any], cli_args: argparse.Namespace) -> dict[str, Any]:
    """Override configuration dictionary values with non-None CLI argument options."""
    ...
```

**Input Example:**
```python
config_dict = {
    "polling_interval_seconds": 2.0,
    "theme": "dark",
    "size": 300,
    "always_on_top": True
}
cli_args = argparse.Namespace(
    theme="neon",
    poll=5.0,
    size=None,
    topmost=False,
    opacity=None
)
```

**Output Example:**
```python
{
    "polling_interval_seconds": 5.0,
    "theme": "neon",
    "size": 300,
    "always_on_top": False
}
```

**Edge Cases:**
- Field in `cli_args` is `None` -> dictionary entry in `config_dict` remains unchanged.
- `topmost` in `cli_args` is `False` (from `--no-topmost`) -> sets `config_dict["always_on_top"] = False`.

---

### 5.5 `validate_config()`

**File:** `src/boostgauge/config.py`

**Signature:**
```python
def validate_config(config_dict: dict[str, Any]) -> AppConfig:
    """Validate structure, types, and value bounds of configuration dictionary, returning validated AppConfig."""
    ...
```

**Input Example:**
```python
config_dict = {
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

**Output Example:**
```python
AppConfig(
    polling_interval_seconds=2.0,
    theme="dark",
    size=300,
    opacity=0.9,
    always_on_top=True,
    position=WindowPosition(x=100, y=100),
    thresholds=ThresholdsConfig(
        conpty=ThresholdPair(yellow=30.0, red=60.0),
        memory_percent=ThresholdPair(yellow=60.0, red=80.0),
        process_count=ThresholdPair(yellow=300.0, red=500.0),
        handle_count=ThresholdPair(yellow=30000.0, red=50000.0)
    ),
    telltale_windows=TelltaleWindowsConfig(short=60, medium=600, long=3600),
    show_driver_label=True,
    show_digital_readout=True,
    show_session_count=True
)
```

**Edge Cases:**
- `theme` equal to `"cyberpunk"` -> raises `ValueError("Invalid theme: cyberpunk. Must be one of dark, light, neon, classic.")`.
- `opacity` equal to `1.5` -> raises `ValueError("Opacity must be between 0.1 and 1.0, got 1.5")`.
- `polling_interval_seconds` equal to `0.0` or `-1.0` -> raises `ValueError("polling_interval_seconds must be positive, got 0.0")`.
- `thresholds["conpty"]["yellow"] >= thresholds["conpty"]["red"]` -> raises `ValueError("Yellow threshold (60.0) must be less than red threshold (30.0) for conpty")`.

---

### 5.6 `ConfigManager.__init__()`

**File:** `src/boostgauge/config.py`

**Signature:**
```python
def __init__(self, config_path: Optional[Path] = None, cli_args: Optional[argparse.Namespace] = None) -> None:
    """Initialize ConfigManager, resolving target path, handling CLI reset, loading/validating config state."""
    ...
```

**Input Example:**
```python
config_path = Path("/tmp/custom_config.json")
cli_args = argparse.Namespace(reset_config=False, theme="neon", poll=None, opacity=None, size=None, topmost=None, config=None)
```

**Output Example:**
```python
None  # Initializes instance attributes self.config_path, self.config, self._observers
```

**Edge Cases:**
- `config_path` is `None` -> defaults to `get_default_config_path()`.
- `cli_args.reset_config=True` -> overwrites target config file with default JSON values before reading and loading.

---

### 5.7 `ConfigManager.register_observer()`

**File:** `src/boostgauge/config.py`

**Signature:**
```python
def register_observer(self, callback: Callable[[AppConfig], None]) -> None:
    """Register observer callback to receive dynamic configuration update notifications."""
    ...
```

**Input Example:**
```python
callback = lambda cfg: print(f"New threshold config: {cfg.thresholds}")
```

**Output Example:**
```python
None
```

**Edge Cases:**
- `callback` is already registered -> append to internal list (or preserve set semantics).

---

### 5.8 `ConfigManager.update_thresholds()`

**File:** `src/boostgauge/config.py`

**Signature:**
```python
def update_thresholds(self, new_thresholds: dict[str, dict[str, float]]) -> None:
    """Update threshold configurations dynamically and notify registered observers without restart."""
    ...
```

**Input Example:**
```python
new_thresholds = {
    "conpty": {"yellow": 25.0, "red": 50.0}
}
```

**Output Example:**
```python
None
```

**Edge Cases:**
- `yellow >= red` in `new_thresholds` -> raises `ValueError`, state remains unmodified, observers are not notified.

---

### 5.9 `ConfigManager.update_geometry()`

**File:** `src/boostgauge/config.py`

**Signature:**
```python
def update_geometry(self, x: int, y: int, size: int) -> None:
    """Update window position and size in state and persist atomically to disk."""
    ...
```

**Input Example:**
```python
x = 150
y = 200
size = 350
```

**Output Example:**
```python
None
```

**Edge Cases:**
- `size < 100` or `size > 2000` -> raises `ValueError("size must be between 100 and 2000, got 50")`, geometry is not updated, disk write is skipped.

---

### 5.10 `ConfigManager.save()`

**File:** `src/boostgauge/config.py`

**Signature:**
```python
def save(self) -> None:
    """Save current configuration atomically to disk using temp file write and atomic replace."""
    ...
```

**Input Example:**
```python
# No parameters
```

**Output Example:**
```python
None
```

**Edge Cases:**
- Target parent directory deleted at runtime -> `save()` creates parent directory (`self.config_path.parent.mkdir(parents=True, exist_ok=True)`), writes to `config_path.with_suffix(".json.tmp")`, and invokes `os.replace`.

---

### 5.11 `main()`

**File:** `src/boostgauge/app.py`

**Signature:**
```python
def main(args_list: Optional[list[str]] = None) -> int:
    """Main application entry point integrating configuration, CLI parsing, and app bootstrap."""
    ...
```

**Input Example:**
```python
args_list = ["--theme", "dark"]
```

**Output Example:**
```python
0
```

**Edge Cases:**
- `ValueError` encountered during configuration parsing/validation -> prints error message to `sys.stderr` and returns exit code `1`.

## 6. Change Instructions

### 6.1 `src/boostgauge/__init__.py` (Add)

**Complete file contents:**

```python
"""BoostGauge - Real-time system tachometer package initialization."""

__version__ = "0.1.0"

__all__ = ["__version__"]
```

---

### 6.2 `src/boostgauge/config.py` (Add)

**Complete file contents:**

```python
"""Configuration management module for BoostGauge.

Handles JSON file persistence, CLI argument parsing, strict validation,
dynamic threshold observer notifications, and atomic disk persistence.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Optional

ALLOWED_THEMES = {"dark", "light", "neon", "classic"}


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
    """Return platform-specific default configuration path (~/.boostgauge/config.json or %APPDATA%/boostgauge/config.json)."""
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            base_dir = Path(appdata)
        else:
            base_dir = Path.home() / "AppData" / "Roaming"
        return base_dir / "boostgauge" / "config.json"
    return Path.home() / ".boostgauge" / "config.json"


def get_default_config_dict() -> Dict[str, Any]:
    """Return dictionary representation of default AppConfig state."""
    return asdict(AppConfig())


def load_config_file(config_path: Path) -> Dict[str, Any]:
    """Load and parse JSON configuration file. Auto-create file with defaults if missing."""
    if not config_path.exists():
        config_path.parent.mkdir(parents=True, exist_ok=True)
        default_dict = get_default_config_dict()
        tmp_path = config_path.with_suffix(".json.tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(default_dict, f, indent=2)
        os.replace(tmp_path, config_path)
        return default_dict

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("JSON configuration root must be a dictionary object.")
            return data
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in configuration file {config_path}: {exc}") from exc


def parse_cli_args(args_list: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments provided to boostgauge executable."""
    parser = argparse.ArgumentParser(
        prog="boostgauge",
        description="Lightweight system tachometer with peak-hold needles",
    )
    parser.add_argument("--config", type=str, default=None, help="Path to custom JSON configuration file")
    parser.add_argument("--reset-config", action="store_true", help="Reset configuration file to default settings")
    parser.add_argument("--theme", type=str, default=None, choices=["dark", "light", "neon", "classic"], help="Gauge visual color theme")
    parser.add_argument("--size", type=int, default=None, help="Square gauge window dimension in pixels [100..2000]")
    parser.add_argument("--poll", type=float, default=None, help="Polling interval in seconds")
    parser.add_argument("--opacity", type=float, default=None, help="Window transparency opacity [0.1..1.0]")

    topmost_group = parser.add_mutually_exclusive_group()
    topmost_group.add_argument("--topmost", action="store_true", default=None, help="Keep window always-on-top")
    topmost_group.add_argument("--no-topmost", action="store_false", dest="topmost", help="Disable always-on-top window behavior")

    return parser.parse_parse_args(args_list) if hasattr(parser, "parse_parse_args") else parser.parse_args(args_list)


def merge_cli_overrides(config_dict: Dict[str, Any], cli_args: argparse.Namespace) -> Dict[str, Any]:
    """Override configuration dictionary entries with non-None CLI options in memory."""
    merged = dict(config_dict)
    if cli_args.theme is not None:
        merged["theme"] = cli_args.theme
    if cli_args.size is not None:
        merged["size"] = cli_args.size
    if cli_args.poll is not None:
        merged["polling_interval_seconds"] = cli_args.poll
    if cli_args.opacity is not None:
        merged["opacity"] = cli_args.opacity
    if cli_args.topmost is not None:
        merged["always_on_top"] = cli_args.topmost
    return merged


def validate_config(config_dict: Dict[str, Any]) -> AppConfig:
    """Validate parameter boundaries, enum choices, and inner threshold constraints strictly."""
    theme = config_dict.get("theme", "dark")
    if theme not in ALLOWED_THEMES:
        raise ValueError(f"Invalid theme: {theme}. Must be one of {', '.join(sorted(ALLOWED_THEMES))}")

    size = config_dict.get("size", 300)
    if not isinstance(size, int) or size < 100 or size > 2000:
        raise ValueError(f"size must be between 100 and 2000, got {size}")

    opacity = config_dict.get("opacity", 0.9)
    if not isinstance(opacity, (int, float)) or opacity < 0.1 or opacity > 1.0:
        raise ValueError(f"Opacity must be between 0.1 and 1.0, got {opacity}")

    poll = config_dict.get("polling_interval_seconds", 2.0)
    if not isinstance(poll, (int, float)) or poll <= 0:
        raise ValueError(f"polling_interval_seconds must be positive, got {poll}")

    position_dict = config_dict.get("position", {})
    pos = WindowPosition(
        x=int(position_dict.get("x", 100)),
        y=int(position_dict.get("y", 100)),
    )

    telltale_dict = config_dict.get("telltale_windows", {})
    telltale = TelltaleWindowsConfig(
        short=int(telltale_dict.get("short", 60)),
        medium=int(telltale_dict.get("medium", 600)),
        long=int(telltale_dict.get("long", 3600)),
    )

    raw_thresholds = config_dict.get("thresholds", {})
    parsed_pairs: Dict[str, ThresholdPair] = {}
    default_pairs = {
        "conpty": (30.0, 60.0),
        "memory_percent": (60.0, 80.0),
        "process_count": (300.0, 500.0),
        "handle_count": (30000.0, 50000.0),
    }

    for key, (def_y, def_r) in default_pairs.items():
        pair_dict = raw_thresholds.get(key, {})
        yellow = float(pair_dict.get("yellow", def_y))
        red = float(pair_dict.get("red", def_r))
        if yellow >= red:
            raise ValueError(f"Yellow threshold ({yellow}) must be less than red threshold ({red}) for {key}")
        parsed_pairs[key] = ThresholdPair(yellow=yellow, red=red)

    thresholds = ThresholdsConfig(
        conpty=parsed_pairs["conpty"],
        memory_percent=parsed_pairs["memory_percent"],
        process_count=parsed_pairs["process_count"],
        handle_count=parsed_pairs["handle_count"],
    )

    return AppConfig(
        polling_interval_seconds=float(poll),
        theme=str(theme),
        size=int(size),
        opacity=float(opacity),
        always_on_top=bool(config_dict.get("always_on_top", True)),
        position=pos,
        thresholds=thresholds,
        telltale_windows=telltale,
        show_driver_label=bool(config_dict.get("show_driver_label", True)),
        show_digital_readout=bool(config_dict.get("show_digital_readout", True)),
        show_session_count=bool(config_dict.get("show_session_count", True)),
    )


class ConfigManager:
    """Manages application configuration lifecycle, observer callbacks, and atomic persistence."""

    def __init__(self, config_path: Optional[Path] = None, cli_args: Optional[argparse.Namespace] = None):
        self.config_path = config_path if config_path is not None else get_default_config_path()
        self._observers: list[Callable[[AppConfig], None]] = []

        if cli_args and getattr(cli_args, "reset_config", False):
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            default_dict = get_default_config_dict()
            tmp_path = self.config_path.with_suffix(".json.tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(default_dict, f, indent=2)
            os.replace(tmp_path, self.config_path)

        loaded_dict = load_config_file(self.config_path)
        if cli_args:
            loaded_dict = merge_cli_overrides(loaded_dict, cli_args)

        self.config: AppConfig = validate_config(loaded_dict)

    def register_observer(self, callback: Callable[[AppConfig], None]) -> None:
        """Register callback for dynamic threshold or setting updates."""
        self._observers.append(callback)

    def notify_observers(self) -> None:
        """Execute registered observer callbacks with current AppConfig."""
        for callback in self._observers:
            callback(self.config)

    def update_thresholds(self, new_thresholds: Dict[str, Dict[str, float]]) -> None:
        """Update threshold pairs dynamically and notify observers if valid."""
        current_dict = asdict(self.config)
        raw_thresholds = current_dict.get("thresholds", {})
        for metric, pair in new_thresholds.items():
            if metric in raw_thresholds:
                if "yellow" in pair:
                    raw_thresholds[metric]["yellow"] = pair["yellow"]
                if "red" in pair:
                    raw_thresholds[metric]["red"] = pair["red"]
        current_dict["thresholds"] = raw_thresholds
        new_config = validate_config(current_dict)
        self.config = new_config
        self.notify_observers()

    def update_geometry(self, x: int, y: int, size: int) -> None:
        """Update window position and size in state, then persist to disk."""
        current_dict = asdict(self.config)
        current_dict["position"] = {"x": x, "y": y}
        current_dict["size"] = size
        new_config = validate_config(current_dict)
        self.config = new_config
        self.save()

    def save(self) -> None:
        """Atomically save current AppConfig state to disk."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        data = asdict(self.config)
        tmp_path = self.config_path.with_suffix(".json.tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, self.config_path)
```

---

### 6.3 `src/boostgauge/app.py` (Add)

**Complete file contents:**

```python
"""Main entry point for BoostGauge application.

Integrates configuration loading, CLI argument parsing, window geometry,
and monitor lifecycle.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from boostgauge.config import ConfigManager, parse_cli_args


def main(args_list: Optional[list[str]] = None) -> int:
    """Bootstraps application configuration and starts main event loop."""
    try:
        cli_args = parse_cli_args(args_list)
        custom_path = Path(cli_args.config) if cli_args.config else None
        manager = ConfigManager(config_path=custom_path, cli_args=cli_args)
        
        # Geometry restoration example: manager.config.position.x, manager.config.position.y
        # Application loop initialization placeholder...
        return 0
    except ValueError as exc:
        print(f"BoostGauge Configuration Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

---

### 6.4 `tests/unit/test_config.py` (Add)

**Complete file contents:**

```python
"""Unit test suite for BoostGauge configuration management module."""

import json
import os
from pathlib import Path
import pytest

from boostgauge.config import (
    AppConfig,
    ConfigManager,
    get_default_config_path,
    load_config_file,
    merge_cli_overrides,
    parse_cli_args,
    validate_config,
)


def test_t010_default_config_file_creation(tmp_path: Path):
    """T010: Test default config file creation when file is missing."""
    config_file = tmp_path / "sub" / "config.json"
    assert not config_file.exists()

    config_dict = load_config_file(config_file)
    assert config_file.exists()
    assert config_dict["theme"] == "dark"
    assert config_dict["polling_interval_seconds"] == 2.0


def test_t020_platform_path_resolution(monkeypatch):
    """T020: Test platform path resolution on Windows vs POSIX."""
    # Test POSIX resolution
    monkeypatch.setattr(os, "name", "posix")
    posix_path = get_default_config_path()
    assert posix_path == Path.home() / ".boostgauge" / "config.json"

    # Test Windows resolution
    monkeypatch.setattr(os, "name", "nt")
    monkeypatch.setenv("APPDATA", "C:\\MockAppData")
    win_path = get_default_config_path()
    assert win_path == Path("C:\\MockAppData") / "boostgauge" / "config.json"


def test_t030_cli_argument_overrides(tmp_path: Path):
    """T030: Test CLI argument overrides over loaded config values."""
    config_file = tmp_path / "config.json"
    load_config_file(config_file)  # create default file

    cli_args = parse_cli_args(["--theme", "neon", "--poll", "5.0", "--no-topmost"])
    manager = ConfigManager(config_path=config_file, cli_args=cli_args)

    assert manager.config.theme == "neon"
    assert manager.config.polling_interval_seconds == 5.0
    assert manager.config.always_on_top is False


def test_t040_custom_config_file_path(tmp_path: Path):
    """T040: Test custom config file path specification via --config."""
    custom_dir = tmp_path / "custom"
    custom_dir.mkdir()
    custom_file = custom_dir / "my_config.json"
    
    custom_data = {
        "polling_interval_seconds": 1.0,
        "theme": "light",
        "size": 400
    }
    with open(custom_file, "w", encoding="utf-8") as f:
        json.dump(custom_data, f)

    cli_args = parse_cli_args(["--config", str(custom_file)])
    manager = ConfigManager(config_path=Path(cli_args.config), cli_args=cli_args)

    assert manager.config_path == custom_file
    assert manager.config.theme == "light"
    assert manager.config.size == 400


def test_t050_window_geometry_persistence(tmp_path: Path):
    """T050: Test window position and size persistence and restoration."""
    config_file = tmp_path / "geometry_config.json"
    manager = ConfigManager(config_path=config_file)

    assert manager.config.position.x == 100
    assert manager.config.position.y == 100
    assert manager.config.size == 300

    # Update geometry and save
    manager.update_geometry(x=250, y=350, size=500)
    assert manager.config.position.x == 250
    assert manager.config.position.y == 350
    assert manager.config.size == 500

    # Verify atomic disk persistence
    with open(config_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["position"]["x"] == 250
    assert data["position"]["y"] == 350
    assert data["size"] == 500


def test_t060_dynamic_threshold_observer_notification(tmp_path: Path):
    """T060: Test dynamic threshold observer callback notification."""
    config_file = tmp_path / "observer_config.json"
    manager = ConfigManager(config_path=config_file)

    notified = []

    def observer_cb(cfg: AppConfig):
        notified.append(cfg.thresholds.conpty.yellow)

    manager.register_observer(observer_cb)
    manager.update_thresholds({"conpty": {"yellow": 45.0, "red": 75.0}})

    assert len(notified) == 1
    assert notified[0] == 45.0
    assert manager.config.thresholds.conpty.yellow == 45.0
    assert manager.config.thresholds.conpty.red == 75.0


def test_t070_invalid_theme_validation(tmp_path: Path):
    """T070: Test validation exception on invalid theme string."""
    invalid_dict = {"theme": "invalid_theme"}
    with pytest.raises(ValueError, match="Invalid theme: invalid_theme"):
        validate_config(invalid_dict)


def test_t080_invalid_opacity_validation():
    """T080: Test validation exception on out-of-bounds opacity."""
    invalid_dict = {"opacity": 1.5}
    with pytest.raises(ValueError, match="Opacity must be between 0.1 and 1.0"):
        validate_config(invalid_dict)


def test_t090_reset_config_flag(tmp_path: Path):
    """T090: Test reset config flag --reset-config overwrites custom settings with defaults."""
    config_file = tmp_path / "custom_config.json"
    custom_data = {"theme": "light", "size": 600}
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(custom_data, f)

    cli_args = parse_cli_args(["--reset-config"])
    manager = ConfigManager(config_path=config_file, cli_args=cli_args)

    assert manager.config.theme == "dark"
    assert manager.config.size == 300

    with open(config_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["theme"] == "dark"
    assert data["size"] == 300
```

## 7. Pattern References

### 7.1 Test Bootstrap Pattern

**File:** `tests/conftest.py` (lines 1-8)

```python
"""Project test bootstrap."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
```

**Relevance:** Demonstrates `pathlib.Path` usage for cross-platform path resolution without hardcoding string separators.

### 7.2 Headless Testing Strategy

**File:** `docs/design/0001-test-strategy.md` (lines 16-27)

```markdown
| Tier | Directory | What lives here | Coverage target | Speed budget |
|---|---|---|---|---|
| Unit | `tests/unit/` | Pure logic with no I/O — math, state machines, parsers, data transforms. | 100% line + branch on touched files | < 1 s for full suite |
```

**Relevance:** Mandates Option C testing — logic in `config.py` runs headlessly without initializing `tkinter.Tk()`.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `import argparse` | stdlib | `src/boostgauge/config.py` |
| `import json` | stdlib | `src/boostgauge/config.py`, `tests/unit/test_config.py` |
| `import os` | stdlib | `src/boostgauge/config.py`, `tests/unit/test_config.py` |
| `import sys` | stdlib | `src/boostgauge/config.py`, `src/boostgauge/app.py` |
| `from dataclasses import dataclass, field, asdict` | stdlib | `src/boostgauge/config.py` |
| `from pathlib import Path` | stdlib | `src/boostgauge/config.py`, `src/boostgauge/app.py`, `tests/unit/test_config.py` |
| `from typing import Any, Callable, Dict, Optional` | stdlib | `src/boostgauge/config.py`, `src/boostgauge/app.py` |
| `import pytest` | dev-dependency | `tests/unit/test_config.py` |

**New Dependencies:** None (uses standard Python library modules only).

## 9. Placeholder

*Reserved for future use to maintain alignment with LLD section numbering.*

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `load_config_file()` | Missing config file path | Default config dictionary created and saved to disk |
| T020 | `get_default_config_path()` | `os.name == 'nt'` vs `'posix'` | Returns `%APPDATA%\boostgauge\config.json` or `~/.boostgauge/config.json` |
| T030 | `merge_cli_overrides()` | `--theme neon --poll 5.0 --no-topmost` | AppConfig has `theme='neon'`, `polling_interval_seconds=5.0`, `always_on_top=False` |
| T040 | `parse_cli_args()` | `--config /path/to/custom.json` | `cli_args.config == "/path/to/custom.json"` |
| T050 | `update_geometry()` | `x=250, y=350, size=500` | Position and size updated in state and written atomically to JSON |
| T060 | `update_thresholds()` | `new_thresholds={"conpty": {"yellow": 45.0, "red": 75.0}}` | Observers notified instantly with updated threshold values |
| T070 | `validate_config()` | `theme="invalid_theme"` | Raises `ValueError` with "Invalid theme: invalid_theme" |
| T080 | `validate_config()` | `opacity=1.5` | Raises `ValueError` with "Opacity must be between 0.1 and 1.0" |
| T090 | `ConfigManager.__init__()` | `--reset-config` | Config file re-written with default JSON values |

## 11. Implementation Notes

### 11.1 Error Handling Convention

All parameter validation errors in `validate_config()` and `load_config_file()` raise explicit `ValueError` exceptions. The application entry point (`src/boostgauge/app.py`) catches `ValueError` at runtime, prints a user-friendly error to `sys.stderr`, and exits with return code `1` (fail-closed model).

### 11.2 Atomic File Persistence Convention

Atomic file writes are implemented in `ConfigManager.save()` and `load_config_file()` by serializing JSON to a temporary file (`config.json.tmp`) in the target directory and using `os.replace(tmp_path, config_path)` to ensure file system safety against sudden application shutdown.

### 11.3 Constants

| Constant | Value | Rationale |
|----------|-------|-----------|
| `ALLOWED_THEMES` | `{"dark", "light", "neon", "classic"}` | Restricts accepted gauge skin color themes |
| `DEFAULT_POLL_INTERVAL` | `2.0` | 2-second default polling frequency for system metrics |
| `DEFAULT_GAUGE_SIZE` | `300` | Standard initial 300x300 pixel gauge window dimension |

### 11.4 Baseline-Independent Property Assertions

Test assertions for configuration management rely strictly on value bounds, data types, standard library `pathlib.Path` comparison, and JSON schema compliance. No baseline images or platform string separator assertions are required.

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #7 |
| Verdict | APPROVED |
| Date | 2026-08-01 |
| Iterations | 0 |
| Finalized | 2026-08-01T12:51:11Z |

### Review Feedback Summary

The implementation spec for Issue #7 is complete, concrete, and highly actionable. All target files are provided with exact, drop-in code implementations, standard library dependencies, explicit error handling, atomic disk persistence logic, and unit test suites. Every test assertion traces directly to specified requirement behaviors without contradiction or ungrounded side-effects.
