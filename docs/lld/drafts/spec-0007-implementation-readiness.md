# Implementation Spec: Configuration File and CLI Arguments

| Field | Value |
|-------|-------|
| Issue | #7 |
| LLD | `docs/lld/active/0007-config-cli.md` |
| Generated | 2026-07-28 |
| Status | APPROVED |

## 1. Overview

This implementation provides BoostGauge with a complete configuration management system, including default JSON auto-creation, cross-platform default path resolution, atomic file persistence, CLI argument parsing and overrides, runtime schema validation, window state persistence, and dynamic threshold updates.

**Objective:** Implement a robust configuration system with default JSON persistence, CLI argument overrides, runtime validation, and dynamic threshold updates for BoostGauge.

**Success Criteria:**
- Auto-creates default JSON configuration at `%APPDATA%\boostgauge\config.json` (Windows) or `~/.boostgauge/config.json` (POSIX) if missing on first launch.
- Parses CLI options (`--theme`, `--size`, `--poll`, `--opacity`, `--no-topmost`, `--config`, `--reset-config`) and merges them into memory as session overrides without altering disk files unless explicitly requested.
- `--reset-config` flag overwrites disk configuration with default parameters prior to initialization.
- `save_window_state` persists window coordinates and window size atomically to disk.
- Runtime range and type validation enforces constraints, throwing descriptive `ValueError` exceptions for invalid values.
- `update_thresholds` permits dynamic runtime modification of resource metric alert thresholds.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/__init__.py` | Add | Package root initializer and version export |
| 2 | `src/boostgauge/config.py` | Add | Core configuration dataclasses (`GaugeConfig`, etc.), path resolution, atomic disk JSON persistence, schema validation, and threshold update functions |
| 3 | `src/boostgauge/cli.py` | Add | CLI parser definition (`build_cli_parser`), argument parser (`parse_cli_args`), and CLI-to-config override merger (`merge_cli_overrides`) |
| 4 | `src/boostgauge/app.py` | Add | Application entry point executing CLI parsing, configuration loading, override merging, and runtime initialization |
| 5 | `tests/unit/test_config.py` | Add | Unit tests for default creation, path resolution, JSON loading/saving, validation exceptions, atomic writes, and threshold updates |
| 6 | `tests/unit/test_cli.py` | Add | Unit tests for CLI parsing, option flags, default values, invalid choices, and override merging |
| 7 | `tests/integration/test_config_cli_integration.py` | Add | End-to-end integration tests for configuration loading, CLI overriding, reset behavior, custom path loading, and disk state persistence |

**Implementation Order Rationale:**
`src/boostgauge/__init__.py` establishes the package namespace. `src/boostgauge/config.py` defines the base data structures, validation logic, and I/O routines required by all downstream components. `src/boostgauge/cli.py` depends on `config.py` dataclasses to perform CLI argument override mapping. `src/boostgauge/app.py` orchestrates `config.py` and `cli.py` into a unified application lifecycle. Unit tests (`tests/unit/test_config.py` and `tests/unit/test_cli.py`) validate isolated logic, followed by `tests/integration/test_config_cli_integration.py` to confirm end-to-end component integration.

## 3. Current State (for Modify/Delete files)

No existing files are modified or deleted in this implementation. All application modules and test files are newly created under `src/boostgauge/` and `tests/`.

## 4. Data Structures

### 4.1 `ThresholdLevel` & `ThresholdConfig`

**Definition:**

```python
from dataclasses import dataclass, field

@dataclass
class ThresholdLevel:
    yellow: float
    red: float

@dataclass
class ThresholdConfig:
    conpty: ThresholdLevel = field(default_factory=lambda: ThresholdLevel(yellow=30.0, red=60.0))
    memory_percent: ThresholdLevel = field(default_factory=lambda: ThresholdLevel(yellow=60.0, red=80.0))
    process_count: ThresholdLevel = field(default_factory=lambda: ThresholdLevel(yellow=300.0, red=500.0))
    handle_count: ThresholdLevel = field(default_factory=lambda: ThresholdLevel(yellow=30000.0, red=50000.0))
```

**Concrete Example:**

```json
{
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
}
```

### 4.2 `TelltaleWindows`

**Definition:**

```python
from dataclasses import dataclass

@dataclass
class TelltaleWindows:
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

### 4.3 `PositionConfig`

**Definition:**

```python
from dataclasses import dataclass

@dataclass
class PositionConfig:
    x: int = 100
    y: int = 100
```

**Concrete Example:**

```json
{
  "x": 100,
  "y": 100
}
```

### 4.4 `GaugeConfig`

**Definition:**

```python
from dataclasses import dataclass, field

@dataclass
class GaugeConfig:
    polling_interval_seconds: int = 2
    theme: str = "dark"
    size: int = 300
    opacity: float = 0.9
    always_on_top: bool = True
    position: PositionConfig = field(default_factory=PositionConfig)
    thresholds: ThresholdConfig = field(default_factory=ThresholdConfig)
    telltale_windows: TelltaleWindows = field(default_factory=TelltaleWindows)
    show_driver_label: bool = True
    show_digital_readout: bool = True
    show_session_count: bool = True
```

**Concrete Example:**

```json
{
  "polling_interval_seconds": 2,
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
    """Return platform-specific default configuration file path (%APPDATA%/boostgauge/config.json or ~/.boostgauge/config.json)."""
    ...
```

**Input Example:**

```python
# No arguments
```

**Output Example:**

```python
# Windows:
Path("C:/Users/mcwiz/AppData/Roaming/boostgauge/config.json")
# POSIX:
Path("/home/user/.boostgauge/config.json")
```

**Edge Cases:**
- `%APPDATA%` environment variable absent on Windows -> fall back to `Path.home() / ".boostgauge" / "config.json"`.

### 5.2 `get_default_config()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def get_default_config() -> GaugeConfig:
    """Instantiate and return a GaugeConfig object populated with default parameters."""
    ...
```

**Input Example:**

```python
# No arguments
```

**Output Example:**

```python
GaugeConfig(
    polling_interval_seconds=2,
    theme="dark",
    size=300,
    opacity=0.9,
    always_on_top=True,
    position=PositionConfig(x=100, y=100),
    thresholds=ThresholdConfig(
        conpty=ThresholdLevel(yellow=30.0, red=60.0),
        memory_percent=ThresholdLevel(yellow=60.0, red=80.0),
        process_count=ThresholdLevel(yellow=300.0, red=500.0),
        handle_count=ThresholdLevel(yellow=30000.0, red=50000.0),
    ),
    telltale_windows=TelltaleWindows(short=60, medium=600, long=3600),
    show_driver_label=True,
    show_digital_readout=True,
    show_session_count=True,
)
```

**Edge Cases:**
- None. Always returns fresh dataclass instances.

### 5.3 `validate_config()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def validate_config(raw_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Validate raw configuration dictionary against schema constraints, raising ValueError for invalid entries."""
    ...
```

**Input Example:**

```python
raw_dict = {
    "polling_interval_seconds": 2,
    "theme": "dark",
    "size": 300,
    "opacity": 0.9,
    "always_on_top": True,
    "position": {"x": 100, "y": 100},
    "thresholds": {
        "conpty": {"yellow": 30.0, "red": 60.0},
        "memory_percent": {"yellow": 60.0, "red": 80.0},
        "process_count": {"yellow": 300.0, "red": 500.0},
        "handle_count": {"yellow": 30000.0, "red": 50000.0},
    },
    "telltale_windows": {"short": 60, "medium": 600, "long": 3600},
    "show_driver_label": True,
    "show_digital_readout": True,
    "show_session_count": True,
}
```

**Output Example:**

```python
{
    "polling_interval_seconds": 2,
    "theme": "dark",
    "size": 300,
    "opacity": 0.9,
    "always_on_top": True,
    "position": {"x": 100, "y": 100},
    "thresholds": {
        "conpty": {"yellow": 30.0, "red": 60.0},
        "memory_percent": {"yellow": 60.0, "red": 80.0},
        "process_count": {"yellow": 300.0, "red": 500.0},
        "handle_count": {"yellow": 30000.0, "red": 50000.0},
    },
    "telltale_windows": {"short": 60, "medium": 600, "long": 3600},
    "show_driver_label": True,
    "show_digital_readout": True,
    "show_session_count": True,
}
```

**Edge Cases:**
- `opacity = 1.5` -> raises `ValueError("opacity must be between 0.1 and 1.0, got 1.5")`
- `theme = "cyberpunk"` -> raises `ValueError("theme must be one of ['dark', 'light'], got 'cyberpunk'")`
- `thresholds.conpty.yellow = 80.0, red = 50.0` -> raises `ValueError("conpty yellow threshold (80.0) must be less than red threshold (50.0)")`
- `polling_interval_seconds = 0` -> raises `ValueError("polling_interval_seconds must be >= 1, got 0")`

### 5.4 `load_config()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def load_config(config_path: Optional[Path] = None) -> GaugeConfig:
    """Load configuration from specified path or default location, auto-creating default file if absent."""
    ...
```

**Input Example:**

```python
config_path = Path("/tmp/custom_config.json")
```

**Output Example:**

```python
GaugeConfig(
    polling_interval_seconds=2,
    theme="dark",
    size=300,
    opacity=0.9,
    always_on_top=True,
    position=PositionConfig(x=100, y=100),
    thresholds=ThresholdConfig(...),
    telltale_windows=TelltaleWindows(...),
    show_driver_label=True,
    show_digital_readout=True,
    show_session_count=True,
)
```

**Edge Cases:**
- Specified path does not exist -> creates parent directories, writes default configuration to disk, and returns default `GaugeConfig`.
- Config file contains invalid JSON syntax -> raises `ValueError("Failed to decode JSON config at ...")`.
- Config file contains out-of-range values -> raises `ValueError` from `validate_config`.

### 5.5 `save_config()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def save_config(config: GaugeConfig, config_path: Optional[Path] = None) -> None:
    """Atomically serialize GaugeConfig dataclass instance to JSON file on disk."""
    ...
```

**Input Example:**

```python
config = GaugeConfig(theme="light", size=400)
config_path = Path("/tmp/custom_config.json")
```

**Output Example:**

```python
None
```

**Edge Cases:**
- Parent directory missing -> creates directory recursively (`parents=True, exist_ok=True`).
- Write operation interrupted -> writes to `.tmp` file first, then atomically replaces target file (`Path.replace()`).

### 5.6 `build_cli_parser()`

**File:** `src/boostgauge/cli.py`

**Signature:**

```python
def build_cli_parser() -> argparse.ArgumentParser:
    """Construct and configure the argparse parser with all supported command line options."""
    ...
```

**Input Example:**

```python
# No arguments
```

**Output Example:**

```python
<argparse.ArgumentParser object at 0x7f8a12345670>
```

**Edge Cases:**
- None. Returns pre-configured parser instance.

### 5.7 `parse_cli_args()`

**File:** `src/boostgauge/cli.py`

**Signature:**

```python
def parse_cli_args(args: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse raw command line argument strings into structured Namespace object."""
    ...
```

**Input Example:**

```python
args = ["--theme", "light", "--size", "400", "--poll", "1"]
```

**Output Example:**

```python
argparse.Namespace(
    theme="light",
    size=400,
    poll=1,
    opacity=None,
    no_topmost=False,
    config=None,
    reset_config=False,
)
```

**Edge Cases:**
- `args = None` -> parses `sys.argv[1:]`.
- Invalid flag provided -> `argparse` outputs error message and exits or raises SystemExit.

### 5.8 `merge_cli_overrides()`

**File:** `src/boostgauge/cli.py`

**Signature:**

```python
def merge_cli_overrides(config: GaugeConfig, parsed_args: argparse.Namespace) -> GaugeConfig:
    """Apply non-None CLI options onto existing GaugeConfig instance without altering disk state."""
    ...
```

**Input Example:**

```python
config = GaugeConfig(theme="dark", size=300, always_on_top=True)
parsed_args = argparse.Namespace(
    theme="light",
    size=400,
    poll=None,
    opacity=None,
    no_topmost=True,
    config=None,
    reset_config=False,
)
```

**Output Example:**

```python
GaugeConfig(
    polling_interval_seconds=2,
    theme="light",
    size=400,
    opacity=0.9,
    always_on_top=False,
    position=PositionConfig(x=100, y=100),
    thresholds=ThresholdConfig(...),
    telltale_windows=TelltaleWindows(...),
    show_driver_label=True,
    show_digital_readout=True,
    show_session_count=True,
)
```

**Edge Cases:**
- All CLI fields are `None` / `False` -> returns un-mutated `config`.
- Disk configuration file is NOT altered during merging.

### 5.9 `save_window_state()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def save_window_state(config: GaugeConfig, position: Tuple[int, int], size: int, config_path: Optional[Path] = None) -> None:
    """Update window position and size attributes in GaugeConfig and persist updated state to disk."""
    ...
```

**Input Example:**

```python
config = GaugeConfig(size=300)
position = (250, 300)
size = 350
config_path = Path("/tmp/config.json")
```

**Output Example:**

```python
None
```

**Edge Cases:**
- Disk write permission failure -> catches `OSError` and re-raises with clear context or logs warning without crashing UI.

### 5.10 `update_thresholds()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def update_thresholds(config: GaugeConfig, new_thresholds: Dict[str, Dict[str, float]], config_path: Optional[Path] = None) -> GaugeConfig:
    """Update active resource metric thresholds dynamically at runtime and optionally persist changes."""
    ...
```

**Input Example:**

```python
config = GaugeConfig()
new_thresholds = {
    "conpty": {"yellow": 40.0, "red": 70.0}
}
config_path = Path("/tmp/config.json")
```

**Output Example:**

```python
GaugeConfig(
    thresholds=ThresholdConfig(
        conpty=ThresholdLevel(yellow=40.0, red=70.0),
        memory_percent=ThresholdLevel(yellow=60.0, red=80.0),
        process_count=ThresholdLevel(yellow=300.0, red=500.0),
        handle_count=ThresholdLevel(yellow=30000.0, red=50000.0),
    ),
    ...
)
```

**Edge Cases:**
- `yellow >= red` in `new_thresholds` -> raises `ValueError("conpty yellow threshold (70.0) must be less than red threshold (40.0)")`.
- Unknown metric name in `new_thresholds` -> ignored or raises `ValueError`.

## 6. Change Instructions

### 6.1 `src/boostgauge/__init__.py` (Add)

**Complete file contents:**

```python
"""BoostGauge core package initializer."""

__version__ = "0.1.0"

__all__ = ["__version__"]
```

### 6.2 `src/boostgauge/config.py` (Add)

**Complete file contents:**

```python
"""Configuration data models, default generation, JSON persistence, validation, and dynamic updates.

Issue #7: Configuration File and CLI Arguments
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Tuple, Optional
from pathlib import Path
import json
import os
import sys

__all__ = [
    "GaugeConfig",
    "PositionConfig",
    "ThresholdConfig",
    "ThresholdLevel",
    "TelltaleWindows",
    "get_default_config_path",
    "get_default_config",
    "validate_config",
    "dict_to_gauge_config",
    "load_config",
    "save_config",
    "save_window_state",
    "update_thresholds",
]

ALLOWED_THEMES = {"dark", "light"}
MIN_POLLING_INTERVAL = 1
MIN_GAUGE_SIZE = 100
MAX_GAUGE_SIZE = 2000
MIN_OPACITY = 0.1
MAX_OPACITY = 1.0


@dataclass
class ThresholdLevel:
    yellow: float
    red: float


@dataclass
class ThresholdConfig:
    conpty: ThresholdLevel = field(default_factory=lambda: ThresholdLevel(yellow=30.0, red=60.0))
    memory_percent: ThresholdLevel = field(default_factory=lambda: ThresholdLevel(yellow=60.0, red=80.0))
    process_count: ThresholdLevel = field(default_factory=lambda: ThresholdLevel(yellow=300.0, red=500.0))
    handle_count: ThresholdLevel = field(default_factory=lambda: ThresholdLevel(yellow=30000.0, red=50000.0))


@dataclass
class TelltaleWindows:
    short: int = 60
    medium: int = 600
    long: int = 3600


@dataclass
class PositionConfig:
    x: int = 100
    y: int = 100


@dataclass
class GaugeConfig:
    polling_interval_seconds: int = 2
    theme: str = "dark"
    size: int = 300
    opacity: float = 0.9
    always_on_top: bool = True
    position: PositionConfig = field(default_factory=PositionConfig)
    thresholds: ThresholdConfig = field(default_factory=ThresholdConfig)
    telltale_windows: TelltaleWindows = field(default_factory=TelltaleWindows)
    show_driver_label: bool = True
    show_digital_readout: bool = True
    show_session_count: bool = True


def get_default_config_path() -> Path:
    """Return platform-specific default configuration file path."""
    if sys.platform == "win32" or os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "boostgauge" / "config.json"
    return Path.home() / ".boostgauge" / "config.json"


def get_default_config() -> GaugeConfig:
    """Instantiate and return a GaugeConfig object populated with default parameters."""
    return GaugeConfig()


def validate_config(raw_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Validate raw configuration dictionary against schema constraints."""
    if not isinstance(raw_dict, dict):
        raise ValueError(f"Configuration root must be a dictionary, got {type(raw_dict).__name__}")

    poll = raw_dict.get("polling_interval_seconds", 2)
    if not isinstance(poll, int) or poll < MIN_POLLING_INTERVAL:
        raise ValueError(f"polling_interval_seconds must be an integer >= {MIN_POLLING_INTERVAL}, got {poll}")

    theme = raw_dict.get("theme", "dark")
    if theme not in ALLOWED_THEMES:
        raise ValueError(f"theme must be one of {sorted(list(ALLOWED_THEMES))}, got '{theme}'")

    size = raw_dict.get("size", 300)
    if not isinstance(size, int) or size < MIN_GAUGE_SIZE or size > MAX_GAUGE_SIZE:
        raise ValueError(f"size must be an integer between {MIN_GAUGE_SIZE} and {MAX_GAUGE_SIZE}, got {size}")

    opacity = raw_dict.get("opacity", 0.9)
    if not isinstance(opacity, (int, float)) or opacity < MIN_OPACITY or opacity > MAX_OPACITY:
        raise ValueError(f"opacity must be between {MIN_OPACITY} and {MAX_OPACITY}, got {opacity}")

    always_on_top = raw_dict.get("always_on_top", True)
    if not isinstance(always_on_top, bool):
        raise ValueError(f"always_on_top must be a boolean, got {type(always_on_top).__name__}")

    pos = raw_dict.get("position")
    if pos is not None and not isinstance(pos, dict):
        raise ValueError(f"position must be a dictionary or omitted, got {type(pos).__name__}")
    if isinstance(pos, dict):
        if "x" in pos and not isinstance(pos["x"], int):
            raise ValueError(f"position.x must be an integer, got {pos['x']}")
        if "y" in pos and not isinstance(pos["y"], int):
            raise ValueError(f"position.y must be an integer, got {pos['y']}")

    thresholds = raw_dict.get("thresholds")
    if thresholds is not None and not isinstance(thresholds, dict):
        raise ValueError(f"thresholds must be a dictionary or omitted, got {type(thresholds).__name__}")

    telltale_windows = raw_dict.get("telltale_windows")
    if telltale_windows is not None and not isinstance(telltale_windows, dict):
        raise ValueError(f"telltale_windows must be a dictionary or omitted, got {type(telltale_windows).__name__}")

    default_threshold_defaults = {
        "conpty": (30.0, 60.0),
        "memory_percent": (60.0, 80.0),
        "process_count": (300.0, 500.0),
        "handle_count": (30000.0, 50000.0),
    }

    if isinstance(thresholds, dict):
        for metric, (def_y, def_r) in default_threshold_defaults.items():
            if metric in thresholds:
                t_val = thresholds[metric]
                if t_val is not None and not isinstance(t_val, dict):
                    raise ValueError(f"thresholds.{metric} must be a dictionary or omitted, got {type(t_val).__name__}")
                if isinstance(t_val, dict):
                    yellow = t_val.get("yellow", def_y)
                    red = t_val.get("red", def_r)
                    if yellow >= red:
                        raise ValueError(f"{metric} yellow threshold ({yellow}) must be less than red threshold ({red})")

    return raw_dict


def dict_to_gauge_config(d: Dict[str, Any]) -> GaugeConfig:
    """Convert validated configuration dictionary into a GaugeConfig dataclass."""
    pos_data = d.get("position") or {}
    position = PositionConfig(
        x=pos_data.get("x", 100),
        y=pos_data.get("y", 100),
    )

    t_data = d.get("thresholds") or {}
    def parse_level(key: str, default_y: float, default_r: float) -> ThresholdLevel:
        sub = t_data.get(key) or {}
        return ThresholdLevel(
            yellow=float(sub.get("yellow", default_y)),
            red=float(sub.get("red", default_r)),
        )

    thresholds = ThresholdConfig(
        conpty=parse_level("conpty", 30.0, 60.0),
        memory_percent=parse_level("memory_percent", 60.0, 80.0),
        process_count=parse_level("process_count", 300.0, 500.0),
        handle_count=parse_level("handle_count", 30000.0, 50000.0),
    )

    tw_data = d.get("telltale_windows") or {}
    telltale = TelltaleWindows(
        short=tw_data.get("short", 60),
        medium=tw_data.get("medium", 600),
        long=tw_data.get("long", 3600),
    )

    config = GaugeConfig(
        polling_interval_seconds=d.get("polling_interval_seconds", 2),
        theme=d.get("theme", "dark"),
        size=d.get("size", 300),
        opacity=float(d.get("opacity", 0.9)),
        always_on_top=d.get("always_on_top", True),
        position=position,
        thresholds=thresholds,
        telltale_windows=telltale,
        show_driver_label=d.get("show_driver_label", True),
        show_digital_readout=d.get("show_digital_readout", True),
        show_session_count=d.get("show_session_count", True),
    )
    validate_config(asdict(config))
    return config


def load_config(config_path: Optional[Path] = None) -> GaugeConfig:
    """Load configuration from specified path or default location, auto-creating default file if absent."""
    path = config_path if config_path is not None else get_default_config_path()
    if not path.exists():
        config = get_default_config()
        save_config(config, path)
        return config

    try:
        with open(path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
    except Exception as e:
        raise ValueError(f"Failed to decode JSON config at {path}: {e}") from e

    validated = validate_config(raw_data)
    return dict_to_gauge_config(validated)


def save_config(config: GaugeConfig, config_path: Optional[Path] = None) -> None:
    """Atomically serialize GaugeConfig dataclass instance to JSON file on disk."""
    path = config_path if config_path is not None else get_default_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")

    data = asdict(config)
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    tmp_path.replace(path)


def save_window_state(config: GaugeConfig, position: Tuple[int, int], size: int, config_path: Optional[Path] = None) -> None:
    """Update window position and size attributes in GaugeConfig and persist updated state to disk."""
    config.position.x = position[0]
    config.position.y = position[1]
    config.size = size
    save_config(config, config_path)


def update_thresholds(config: GaugeConfig, new_thresholds: Dict[str, Dict[str, float]], config_path: Optional[Path] = None) -> GaugeConfig:
    """Update active resource metric thresholds dynamically at runtime and optionally persist changes."""
    for metric, levels in new_thresholds.items():
        if hasattr(config.thresholds, metric):
            current = getattr(config.thresholds, metric)
            new_yellow = levels.get("yellow", current.yellow)
            new_red = levels.get("red", current.red)
            if new_yellow >= new_red:
                raise ValueError(f"{metric} yellow threshold ({new_yellow}) must be less than red threshold ({new_red})")
            setattr(config.thresholds, metric, ThresholdLevel(yellow=float(new_yellow), red=float(new_red)))

    validate_config(asdict(config))
    if config_path is not None:
        save_config(config, config_path)
    return config
```

### 6.3 `src/boostgauge/cli.py` (Add)

**Complete file contents:**

```python
"""CLI argument parser definition, option handling, and CLI-to-config override mapping logic.

Issue #7: Configuration File and CLI Arguments
"""

import argparse
from dataclasses import asdict
from typing import Optional, List
from pathlib import Path
from boostgauge.config import GaugeConfig, validate_config


def build_cli_parser() -> argparse.ArgumentParser:
    """Construct and configure the argparse parser with all supported command line options."""
    parser = argparse.ArgumentParser(
        prog="boostgauge",
        description="Lightweight system tachometer for monitoring AI agent resource pressure.",
    )
    parser.add_argument(
        "--theme",
        type=str,
        choices=["dark", "light"],
        help="UI color theme (dark or light)",
    )
    parser.add_argument(
        "--size",
        type=int,
        help="Gauge window size in pixels (100-2000)",
    )
    parser.add_argument(
        "--poll",
        type=int,
        help="System metric polling interval in seconds",
    )
    parser.add_argument(
        "--opacity",
        type=float,
        help="Window opacity (0.1 - 1.0)",
    )
    parser.add_argument(
        "--no-topmost",
        action="store_true",
        default=False,
        help="Disable always-on-top window behavior",
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to custom JSON configuration file",
    )
    parser.add_argument(
        "--reset-config",
        action="store_true",
        default=False,
        help="Reset configuration file to default values on disk",
    )
    return parser


def parse_cli_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse raw command line argument strings into structured Namespace object."""
    parser = build_cli_parser()
    return parser.parse_args(args)


def merge_cli_overrides(config: GaugeConfig, parsed_args: argparse.Namespace) -> GaugeConfig:
    """Apply non-None CLI options onto existing GaugeConfig instance without altering disk state."""
    if parsed_args.theme is not None:
        config.theme = parsed_args.theme
    if parsed_args.size is not None:
        config.size = parsed_args.size
    if parsed_args.poll is not None:
        config.polling_interval_seconds = parsed_args.poll
    if parsed_args.opacity is not None:
        config.opacity = parsed_args.opacity
    if parsed_args.no_topmost:
        config.always_on_top = False

    validate_config(asdict(config))
    return config
```

### 6.4 `src/boostgauge/app.py` (Add)

**Complete file contents:**

```python
"""Application entry point executing CLI parsing, config loading, and runtime initialization.

Issue #7: Configuration File and CLI Arguments
"""

from typing import Optional, List
from pathlib import Path
from boostgauge.config import (
    GaugeConfig,
    get_default_config,
    get_default_config_path,
    load_config,
    save_config,
)
from boostgauge.cli import parse_cli_args, merge_cli_overrides


def main(args: Optional[List[str]] = None) -> GaugeConfig:
    """Run BoostGauge configuration initialization lifecycle and return active config."""
    parsed_args = parse_cli_args(args)
    config_path = Path(parsed_args.config) if parsed_args.config else get_default_config_path()

    if parsed_args.reset_config:
        config = get_default_config()
        save_config(config, config_path)
    else:
        config = load_config(config_path)

    merged_config = merge_cli_overrides(config, parsed_args)
    return merged_config


if __name__ == "__main__":
    main()
```

### 6.5 `tests/unit/test_config.py` (Add)

**Complete file contents:**

```python
"""Unit tests for configuration loading, saving, validation, and threshold updates.

Issue #7: Configuration File and CLI Arguments
"""

import json
from pathlib import Path
import pytest
from boostgauge.config import (
    GaugeConfig,
    PositionConfig,
    ThresholdConfig,
    ThresholdLevel,
    get_default_config,
    get_default_config_path,
    load_config,
    save_config,
    save_window_state,
    update_thresholds,
    validate_config,
)


def test_get_default_config_path():
    path = get_default_config_path()
    assert isinstance(path, Path)
    assert path.name == "config.json"


def test_get_default_config():
    config = get_default_config()
    assert config.polling_interval_seconds == 2
    assert config.theme == "dark"
    assert config.size == 300
    assert config.opacity == 0.9
    assert config.always_on_top is True
    assert config.position.x == 100
    assert config.position.y == 100


def test_auto_create_config_file(tmp_path):
    target = tmp_path / "sub" / "config.json"
    assert not target.exists()
    config = load_config(target)
    assert target.exists()
    assert config.theme == "dark"


def test_save_and_load_config(tmp_path):
    target = tmp_path / "config.json"
    config = get_default_config()
    config.theme = "light"
    config.size = 450
    save_config(config, target)

    loaded = load_config(target)
    assert loaded.theme == "light"
    assert loaded.size == 450


def test_save_window_state(tmp_path):
    target = tmp_path / "config.json"
    config = get_default_config()
    save_window_state(config, (250, 350), 400, target)

    loaded = load_config(target)
    assert loaded.position.x == 250
    assert loaded.position.y == 350
    assert loaded.size == 400


def test_validate_config_invalid_theme():
    raw = {"theme": "cyberpunk"}
    with pytest.raises(ValueError, match="theme must be one of"):
        validate_config(raw)


def test_validate_config_invalid_opacity():
    raw = {"opacity": 1.5}
    with pytest.raises(ValueError, match="opacity must be between"):
        validate_config(raw)


def test_validate_config_threshold_yellow_ge_red():
    raw = {
        "thresholds": {
            "conpty": {"yellow": 80.0, "red": 50.0}
        }
    }
    with pytest.raises(ValueError, match="yellow threshold .* must be less than red threshold"):
        validate_config(raw)


def test_validate_config_null_position():
    raw = {"position": None}
    with pytest.raises(ValueError, match="position must be a dictionary or omitted"):
        validate_config(raw)


def test_validate_config_partial_threshold_yellow_ge_default_red():
    raw = {
        "thresholds": {
            "conpty": {"yellow": 80.0}
        }
    }
    with pytest.raises(ValueError, match="yellow threshold .* must be less than red threshold"):
        validate_config(raw)


def test_update_thresholds_dynamic(tmp_path):
    target = tmp_path / "config.json"
    config = get_default_config()
    save_config(config, target)

    updated = update_thresholds(
        config,
        {"conpty": {"yellow": 40.0, "red": 70.0}},
        config_path=target,
    )
    assert updated.thresholds.conpty.yellow == 40.0
    assert updated.thresholds.conpty.red == 70.0

    loaded = load_config(target)
    assert loaded.thresholds.conpty.yellow == 40.0
    assert loaded.thresholds.conpty.red == 70.0
```

### 6.6 `tests/unit/test_cli.py` (Add)

**Complete file contents:**

```python
"""Unit tests for CLI argument parsing and override merging.

Issue #7: Configuration File and CLI Arguments
"""

import pytest
from boostgauge.config import get_default_config
from boostgauge.cli import parse_cli_args, merge_cli_overrides


def test_parse_cli_args_defaults():
    args = parse_cli_args([])
    assert args.theme is None
    assert args.size is None
    assert args.poll is None
    assert args.opacity is None
    assert args.no_topmost is False
    assert args.config is None
    assert args.reset_config is False


def test_parse_cli_args_valid_values():
    args = parse_cli_args([
        "--theme", "light",
        "--size", "400",
        "--poll", "1",
        "--opacity", "0.8",
        "--no-topmost",
        "--reset-config",
    ])
    assert args.theme == "light"
    assert args.size == 400
    assert args.poll == 1
    assert args.opacity == 0.8
    assert args.no_topmost is True
    assert args.reset_config is True


def test_merge_cli_overrides():
    config = get_default_config()
    args = parse_cli_args([
        "--theme", "light",
        "--size", "500",
        "--no-topmost",
    ])
    merged = merge_cli_overrides(config, args)
    assert merged.theme == "light"
    assert merged.size == 500
    assert merged.always_on_top is False
    # Unspecified options remain default
    assert merged.opacity == 0.9
```

### 6.7 `tests/integration/test_config_cli_integration.py` (Add)

**Complete file contents:**

```python
"""Integration tests for configuration loading, CLI overrides, reset behavior, and file persistence.

Issue #7: Configuration File and CLI Arguments
"""

from pathlib import Path
import json
from boostgauge.config import get_default_config, save_config, load_config
from boostgauge.app import main


def test_integration_cli_overrides_memory_only(tmp_path):
    target = tmp_path / "config.json"
    config = get_default_config()
    config.theme = "dark"
    save_config(config, target)

    # Execute main with custom config path and CLI theme override
    result = main(["--config", str(target), "--theme", "light"])
    assert result.theme == "light"

    # Disk file must remain unchanged ("dark")
    loaded_from_disk = load_config(target)
    assert loaded_from_disk.theme == "dark"


def test_integration_reset_config_flag(tmp_path):
    target = tmp_path / "config.json"
    config = get_default_config()
    config.theme = "light"
    config.size = 500
    save_config(config, target)

    # Execute main with --reset-config
    result = main(["--config", str(target), "--reset-config"])
    assert result.theme == "dark"
    assert result.size == 300

    # Disk file must be reset to default ("dark")
    loaded_from_disk = load_config(target)
    assert loaded_from_disk.theme == "dark"
    assert loaded_from_disk.size == 300


def test_integration_custom_config_path(tmp_path):
    custom_target = tmp_path / "custom_dir" / "my_config.json"
    config = get_default_config()
    config.opacity = 0.5
    save_config(config, custom_target)

    result = main(["--config", str(custom_target)])
    assert result.opacity == 0.5
    assert custom_target.exists()
```

## 7. Pattern References

### 7.1 Pytest Setup Pattern

**File:** `tests/conftest.py` (lines 1-8)

```python
"""Project test bootstrap."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
```

**Relevance:** Demonstrates path manipulation using `Path` standard library object, maintaining platform independence across Windows and POSIX operating systems.

### 7.2 Pytest Configuration Discovery

**File:** `pyproject.toml` (lines 35-40)

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
```

**Relevance:** Establishes module and function naming patterns (`test_*.py`, `test_*`) enforced for test discovery in `tests/unit/` and `tests/integration/`.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `dataclasses.dataclass`, `field`, `asdict` | stdlib | `src/boostgauge/config.py`, `src/boostgauge/cli.py` |
| `typing.Dict`, `Any`, `Tuple`, `Optional`, `List` | stdlib | `src/boostgauge/config.py`, `src/boostgauge/cli.py`, `src/boostgauge/app.py` |
| `pathlib.Path` | stdlib | `src/boostgauge/config.py`, `src/boostgauge/cli.py`, `src/boostgauge/app.py`, test files |
| `json` | stdlib | `src/boostgauge/config.py`, test files |
| `os`, `sys` | stdlib | `src/boostgauge/config.py` |
| `argparse` | stdlib | `src/boostgauge/cli.py`, `src/boostgauge/app.py` |
| `pytest` | dev dependency (`pyproject.toml`) | `tests/unit/test_config.py`, `tests/unit/test_cli.py`, `tests/integration/test_config_cli_integration.py` |

**New Dependencies:** None required. All core logic uses standard library modules.

## 9. Placeholder

*Reserved for future use to maintain alignment with LLD section numbering.*

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `load_config()` | Non-existent path (`tmp_path / "sub" / "config.json"`) | File auto-created on disk, returns default `GaugeConfig` |
| T020 | `parse_cli_args()` | `["--theme", "light", "--size", "400", "--poll", "1", "--opacity", "0.8", "--no-topmost", "--reset-config"]` | `Namespace(theme="light", size=400, poll=1, opacity=0.8, no_topmost=True, reset_config=True)` |
| T030 | `merge_cli_overrides()` / `main()` | Disk `theme: dark`, CLI `--theme light` | Active `config.theme == "light"`, disk file remains `"dark"` |
| T040 | `main()` | `--reset-config` flag provided | Disk `config.json` overwritten with default values |
| T050 | `load_config()` / `main()` | `--config custom_path` | Settings loaded from custom path |
| T060 | `save_window_state()` | `position=(250, 350)`, `size=400` | `config.json` updated with `x=250, y=350, size=400` |
| T070 | `validate_config()` | Invalid theme `"cyberpunk"`, invalid opacity `1.5`, yellow >= red `80/50` | Raises `ValueError` with descriptive message |
| T080 | `update_thresholds()` | `{"conpty": {"yellow": 40.0, "red": 70.0}}` | Active thresholds updated and persisted to disk |

## 11. Implementation Notes

### 11.1 Atomic Persistence & File Safety Strategy

To prevent configuration corruption in the event of abrupt application exit or power loss during write operations:
- `save_config` serializes the current `GaugeConfig` dataclass to a `.json.tmp` file alongside the target file.
- `tmp_path.replace(path)` performs an atomic replace operation on both Windows and POSIX filesystems.
- Parent directories are created recursively (`parents=True, exist_ok=True`) prior to initiating file writes.

### 11.2 Path Resolution Strategy & Platform Independence

Configuration directory selection prioritizes native platform conventions:
- On Windows (`sys.platform == "win32"` or `os.name == "nt"`), `%APPDATA%\boostgauge\config.json` is used.
- On POSIX (Linux / macOS), `~/.boostgauge/config.json` is used.
- In test suites, path assertions compare `pathlib.Path` objects directly (`path.name == "config.json"`) or examine `path.parts`, preventing false failures caused by string path separator differences across operating systems (Issue #1841).

### 11.3 Error Handling & Schema Validation Rules

- `validate_config` checks data types and range bounds for all configuration fields.
- Range bounds: `polling_interval_seconds >= 1`, `100 <= size <= 2000`, `0.1 <= opacity <= 1.0`, `yellow < red` for all metric thresholds.
- If validation fails or JSON decoding fails during loading, a `ValueError` with a descriptive message is raised, failing closed safely.

### 11.4 Constants & Allowed Values Table

| Constant | Value | Rationale |
|----------|-------|-----------|
| `ALLOWED_THEMES` | `{"dark", "light"}` | Standard visual themes supported by tachometer rendering engine |
| `MIN_POLLING_INTERVAL` | `1` | Prevent CPU starvation from sub-second metric collection loops |
| `MIN_GAUGE_SIZE` | `100` | Minimum readable tachometer rendering size in pixels |
| `MAX_GAUGE_SIZE` | `2000` | Upper display boundary for 4K workstation displays |
| `MIN_OPACITY` | `0.1` | Prevents window from becoming completely invisible |
| `MAX_OPACITY` | `1.0` | Maximum standard window opacity |

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3 explicitly notes no files are modified/deleted)
- [x] Every data structure has a concrete JSON/YAML example (Section 4)
- [x] Every function has input/output examples with realistic values (Section 5)
- [x] Change instructions are diff-level specific with complete python code (Section 6)
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
| Finalized | 2026-07-28T10:00:00Z |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #7 |
| Verdict | APPROVED |
| Date | 2026-07-28 |
| Iterations | 1 |
| Finalized | 2026-07-28T15:01:16Z |

### Review Feedback Summary

\nThe revised implementation spec for Issue #7 is complete, concrete, and highly detailed. The recent revisions successfully address edge cases surrounding `None` values and partial dictionary inputs for nested configuration objects (such as `position`, `thresholds`, and `telltale_windows`), while providing fully written code implementations and comprehensive unit/integration test coverage. An autonomous AI agent can execute these instructions directly with a >80% first-try success rate without ...
