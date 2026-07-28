# Implementation Spec: Configuration File and CLI Arguments

| Field | Value |
|-------|-------|
| Issue | #7 |
| LLD | `docs/lld/done/0007-config-cli.md` |
| Generated | 2026-07-28 |
| Status | DRAFT |

---

## 1. Overview

This implementation establishes the configuration and command-line argument subsystem for BoostGauge. It provides OS-specific JSON settings persistence, CLI argument parsing via `argparse`, validation logic, dynamic threshold configuration, and window position/size persistence.

**Objective:** Implement a zero-dependency configuration system supporting OS-appropriate default JSON paths, CLI argument overrides, dynamic metric thresholds, and window geometry saving/restoring.

**Success Criteria:**
1. Auto-create default configuration JSON at OS-specific paths (%APPDATA%/boostgauge/config.json on Windows, ~/.boostgauge/config.json on POSIX) on initial execution.
2. Override in-memory configuration using CLI arguments (`--theme`, `--size`, `--poll`, `--opacity`, `--no-topmost`, `--config`, `--reset-config`).
3. Persist and restore window geometry (`position.x`, `position.y`, `size`) cleanly on application shutdown.
4. Validate configuration fields with clear, descriptive human-readable error messages on invalid values or malformed files.

---

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `pyproject.toml` | Modify | Add script entry point `boostgauge = "boostgauge.app:main"` under `[project.scripts]` |
| 2 | `src/boostgauge/__init__.py` | Add | Package initialization file declaring version metadata |
| 3 | `src/boostgauge/config.py` | Add | Core configuration module: data classes, default generators, JSON loading/saving, validation, CLI merging, and geometry updating |
| 4 | `src/boostgauge/app.py` | Add | Main CLI entry point handling argument parsing, configuration initialization, error reporting, and application lifecycle |
| 5 | `tests/unit/test_config.py` | Add | Unit test suite covering loading, saving, CLI overriding, default resetting, path resolution, and validation errors |

**Implementation Order Rationale:**
1. `pyproject.toml` modified first to declare the CLI entry point target.
2. `src/boostgauge/__init__.py` created to establish `boostgauge` as a Python package.
3. `src/boostgauge/config.py` implemented next as the core dependency containing DTOs, loading/saving logic, and validation rules.
4. `src/boostgauge/app.py` built to consume `config.py` and provide the CLI `main()` entry point.
5. `tests/unit/test_config.py` implemented last to validate the complete configuration system in headless isolation.

---

## 3. Current State (for Modify/Delete files)

### 3.1 `pyproject.toml`

**Relevant excerpt** (lines 11-16):

```toml
dependencies = [
    "psutil (>=7.2.2,<8.0.0)",
    "pillow (>=12.2.0,<13.0.0)",
    "pystray (>=0.19.5,<0.20.0)"
]
```

**What changes:** Add `[project.scripts]` section defining `boostgauge = "boostgauge.app:main"` to expose the application executable entry point.

---

## 4. Data Structures

### 4.1 `ThresholdPair` & `ThresholdsConfigDict`

**Definition:**

```python
from typing import TypedDict

class ThresholdPair(TypedDict):
    yellow: float
    red: float

class ThresholdsConfigDict(TypedDict):
    conpty: ThresholdPair
    memory_percent: ThresholdPair
    process_count: ThresholdPair
    handle_count: ThresholdPair
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

### 4.2 `TelltaleWindowsDict` & `PositionDict`

**Definition:**

```python
class TelltaleWindowsDict(TypedDict):
    short: int
    medium: int
    long: int

class PositionDict(TypedDict):
    x: int
    y: int
```

**Concrete Example:**

```json
{
    "telltale_windows": {
        "short": 60,
        "medium": 600,
        "long": 3600
    },
    "position": {
        "x": 120,
        "y": 240
    }
}
```

### 4.3 `GaugeConfig` Dataclass & JSON Representation

**Definition:**

```python
from dataclasses import dataclass, field

@dataclass
class ThresholdsConfig:
    conpty: dict[str, float] = field(default_factory=lambda: {"yellow": 30.0, "red": 60.0})
    memory_percent: dict[str, float] = field(default_factory=lambda: {"yellow": 60.0, "red": 80.0})
    process_count: dict[str, float] = field(default_factory=lambda: {"yellow": 300.0, "red": 500.0})
    handle_count: dict[str, float] = field(default_factory=lambda: {"yellow": 30000.0, "red": 50000.0})

@dataclass
class TelltaleWindowsConfig:
    short: int = 60
    medium: int = 600
    long: int = 3600

@dataclass
class PositionConfig:
    x: int = 100
    y: int = 100

@dataclass
class GaugeConfig:
    polling_interval_seconds: float = 2.0
    theme: str = "dark"
    size: int = 300
    opacity: float = 0.9
    always_on_top: bool = True
    position: PositionConfig = field(default_factory=PositionConfig)
    thresholds: ThresholdsConfig = field(default_factory=ThresholdsConfig)
    telltale_windows: TelltaleWindowsConfig = field(default_factory=TelltaleWindowsConfig)
    show_driver_label: bool = True
    show_digital_readout: bool = True
    show_session_count: bool = True
```

**Concrete Example:**

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
        "conpty": {"yellow": 30.0, "red": 60.0},
        "memory_percent": {"yellow": 60.0, "red": 80.0},
        "process_count": {"yellow": 300.0, "red": 500.0},
        "handle_count": {"yellow": 30000.0, "red": 50000.0}
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

### 4.4 `CLIArgs` Dataclass

**Definition:**

```python
@dataclass
class CLIArgs:
    theme: str | None = None
    size: int | None = None
    poll: float | None = None
    opacity: float | None = None
    no_topmost: bool = False
    config: str | None = None
    reset_config: bool = False
```

**Concrete Example:**

```json
{
    "theme": "neon",
    "size": 350,
    "poll": 1.5,
    "opacity": 0.95,
    "no_topmost": true,
    "config": "/custom/path/config.json",
    "reset_config": false
}
```

---

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
# No parameters
```

**Output Example:**

```python
# On Windows:
Path("C:/Users/mcwiz/AppData/Roaming/boostgauge/config.json")
# On POSIX:
Path("/home/user/.boostgauge/config.json")
```

**Edge Cases:**
- `%APPDATA%` environment variable unset on Windows -> falls back to `Path.home() / "AppData" / "Roaming" / "boostgauge" / "config.json"`.

---

### 5.2 `get_default_config()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def get_default_config() -> GaugeConfig:
    """Return a GaugeConfig instance initialized with default values."""
    ...
```

**Input Example:**

```python
# No parameters
```

**Output Example:**

```python
GaugeConfig(
    polling_interval_seconds=2.0,
    theme="dark",
    size=300,
    opacity=0.9,
    always_on_top=True,
    position=PositionConfig(x=100, y=100),
    thresholds=ThresholdsConfig(
        conpty={"yellow": 30.0, "red": 60.0},
        memory_percent={"yellow": 60.0, "red": 80.0},
        process_count={"yellow": 300.0, "red": 500.0},
        handle_count={"yellow": 30000.0, "red": 50000.0},
    ),
    telltale_windows=TelltaleWindowsConfig(short=60, medium=600, long=3600),
    show_driver_label=True,
    show_digital_readout=True,
    show_session_count=True,
)
```

**Edge Cases:**
- None; returns standard object instance.

---

### 5.3 `load_config()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def load_config(config_path: Path | None = None) -> GaugeConfig:
    """Load config from JSON file; auto-create with defaults if missing. Raise ValueError on malformed JSON or invalid schema."""
    ...
```

**Input Example:**

```python
config_path = Path("C:/Users/mcwiz/AppData/Roaming/boostgauge/config.json")
```

**Output Example:**

```python
GaugeConfig(
    polling_interval_seconds=2.0,
    theme="dark",
    size=300,
    opacity=0.9,
    always_on_top=True,
    position=PositionConfig(x=100, y=100),
    thresholds=ThresholdsConfig(),
    telltale_windows=TelltaleWindowsConfig(),
    show_driver_label=True,
    show_digital_readout=True,
    show_session_count=True,
)
```

**Edge Cases:**
- `config_path` is `None` -> defaults to `get_default_config_path()`.
- File does not exist -> auto-creates directory structure, calls `save_config()` with defaults, and returns `GaugeConfig()`.
- File contains invalid JSON syntax -> raises `ValueError("Failed to parse configuration JSON: ...")`.
- File contains unexpected data types -> raises `ValueError("Invalid configuration schema: ...")`.

---

### 5.4 `save_config()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def save_config(config: GaugeConfig, config_path: Path | None = None) -> None:
    """Serialize and write GaugeConfig instance to JSON file atomically."""
    ...
```

**Input Example:**

```python
config = GaugeConfig(theme="neon", size=400)
config_path = Path("/tmp/test_config.json")
```

**Output Example:**

```python
None
```

**Edge Cases:**
- Parent directory does not exist -> parent directory created with `mkdir(parents=True, exist_ok=True)`.
- Interrupted write -> writes to temporary file `.config.json.tmp` first, then atomically replaces via `Path.replace()`.

---

### 5.5 `parse_cli_args()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def parse_cli_args(args: list[str] | None = None) -> CLIArgs:
    """Parse command line arguments into CLIArgs object."""
    ...
```

**Input Example:**

```python
args = ["--theme", "neon", "--size", "400", "--poll", "1.0", "--no-topmost"]
```

**Output Example:**

```python
CLIArgs(
    theme="neon",
    size=400,
    poll=1.0,
    opacity=None,
    no_topmost=True,
    config=None,
    reset_config=False,
)
```

**Edge Cases:**
- `args` is `None` -> reads from `sys.argv[1:]`.
- Invalid flag or wrong type (e.g. `--size abc`) -> `argparse` prints error to `sys.stderr` and raises `SystemExit(2)`.

---

### 5.6 `merge_config_and_args()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def merge_config_and_args(config: GaugeConfig, cli_args: CLIArgs) -> GaugeConfig:
    """Apply non-None CLI argument overrides to GaugeConfig instance."""
    ...
```

**Input Example:**

```python
config = GaugeConfig(theme="dark", size=300, always_on_top=True)
cli_args = CLIArgs(theme="light", size=400, no_topmost=True)
```

**Output Example:**

```python
GaugeConfig(
    polling_interval_seconds=2.0,
    theme="light",
    size=400,
    opacity=0.9,
    always_on_top=False,
    position=PositionConfig(x=100, y=100),
    thresholds=ThresholdsConfig(),
    telltale_windows=TelltaleWindowsConfig(),
    show_driver_label=True,
    show_digital_readout=True,
    show_session_count=True,
)
```

**Edge Cases:**
- `cli_args` attributes are `None` / `False` -> original `config` values preserved without modification.

---

### 5.7 `validate_config()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def validate_config(config: GaugeConfig) -> list[str]:
    """Validate configuration fields and return list of validation error strings if invalid."""
    ...
```

**Input Example:**

```python
config = GaugeConfig(
    opacity=1.5,
    polling_interval_seconds=-1.0,
    size=0,
    theme="invalid_theme",
    thresholds=ThresholdsConfig(conpty={"yellow": 70.0, "red": 50.0}),
)
```

**Output Example:**

```python
[
    "opacity must be between 0.0 and 1.0, got 1.5",
    "polling_interval_seconds must be > 0, got -1.0",
    "size must be > 0, got 0",
    "theme must be one of ('dark', 'light', 'neon', 'classic'), got 'invalid_theme'",
    "threshold yellow value (70.0) must be less than red value (50.0) for conpty",
]
```

**Edge Cases:**
- All fields valid -> returns empty list `[]`.

---

### 5.8 `reset_config_to_defaults()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def reset_config_to_defaults(config_path: Path | None = None) -> GaugeConfig:
    """Overwrite config file at config_path with default configuration and return default GaugeConfig."""
    ...
```

**Input Example:**

```python
config_path = Path("/tmp/existing_config.json")
```

**Output Example:**

```python
GaugeConfig(
    polling_interval_seconds=2.0,
    theme="dark",
    size=300,
    opacity=0.9,
    always_on_top=True,
    position=PositionConfig(x=100, y=100),
    thresholds=ThresholdsConfig(),
    telltale_windows=TelltaleWindowsConfig(),
    show_driver_label=True,
    show_digital_readout=True,
    show_session_count=True,
)
```

**Edge Cases:**
- Existing file overwritten with standard factory default JSON payload.

---

### 5.9 `update_window_geometry()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def update_window_geometry(
    config: GaugeConfig,
    position: tuple[int, int],
    size: int,
    config_path: Path | None = None,
) -> GaugeConfig:
    """Update position and size in GaugeConfig and persist to config file on exit."""
    ...
```

**Input Example:**

```python
config = GaugeConfig(size=300, position=PositionConfig(x=100, y=100))
position = (250, 350)
size = 400
config_path = Path("/tmp/test_config.json")
```

**Output Example:**

```python
GaugeConfig(
    size=400,
    position=PositionConfig(x=250, y=350),
    polling_interval_seconds=2.0,
    theme="dark",
    opacity=0.9,
    always_on_top=True,
    thresholds=ThresholdsConfig(),
    telltale_windows=TelltaleWindowsConfig(),
    show_driver_label=True,
    show_digital_readout=True,
    show_session_count=True,
)
```

**Edge Cases:**
- `config_path` is `None` -> uses default config path and updates file on disk.

---

### 5.10 `main()`

**File:** `src/boostgauge/app.py`

**Signature:**

```python
def main(sys_args: list[str] | None = None) -> int:
    """Main CLI entry point for boostgauge."""
    ...
```

**Input Example:**

```python
sys_args = ["--theme", "neon", "--size", "350"]
```

**Output Example:**

```python
0
```

**Edge Cases:**
- `--reset-config` flag provided -> resets config file to defaults, logs message, returns 0.
- Validation errors present -> prints errors to `sys.stderr`, returns 1.
- `SystemExit(2)` from `argparse` -> returns exit code 2.

---

## 6. Change Instructions

### 6.1 `pyproject.toml` (Modify)

**Change 1:** Add `[project.scripts]` section after line 15:

```diff
 dependencies = [
     "psutil (>=7.2.2,<8.0.0)",
     "pillow (>=12.2.0,<13.0.0)",
     "pystray (>=0.19.5,<0.20.0)"
 ]
 
+[project.scripts]
+boostgauge = "boostgauge.app:main"
+
 [project.urls]
```

---

### 6.2 `src/boostgauge/__init__.py` (Add)

**Complete file contents:**

```python
"""BoostGauge application package."""

__version__ = "0.1.0"
```

---

### 6.3 `src/boostgauge/config.py` (Add)

**Complete file contents:**

```python
"""Configuration file management and CLI arguments for BoostGauge.

Issue #7: Feature: Configuration File and CLI Arguments
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
import sys
from typing import Any

VALID_THEMES = ("dark", "light", "neon", "classic")


@dataclass
class ThresholdsConfig:
    conpty: dict[str, float] = field(default_factory=lambda: {"yellow": 30.0, "red": 60.0})
    memory_percent: dict[str, float] = field(default_factory=lambda: {"yellow": 60.0, "red": 80.0})
    process_count: dict[str, float] = field(default_factory=lambda: {"yellow": 300.0, "red": 500.0})
    handle_count: dict[str, float] = field(default_factory=lambda: {"yellow": 30000.0, "red": 50000.0})


@dataclass
class TelltaleWindowsConfig:
    short: int = 60
    medium: int = 600
    long: int = 3600


@dataclass
class PositionConfig:
    x: int = 100
    y: int = 100


@dataclass
class GaugeConfig:
    polling_interval_seconds: float = 2.0
    theme: str = "dark"
    size: int = 300
    opacity: float = 0.9
    always_on_top: bool = True
    position: PositionConfig = field(default_factory=PositionConfig)
    thresholds: ThresholdsConfig = field(default_factory=ThresholdsConfig)
    telltale_windows: TelltaleWindowsConfig = field(default_factory=TelltaleWindowsConfig)
    show_driver_label: bool = True
    show_digital_readout: bool = True
    show_session_count: bool = True


@dataclass
class CLIArgs:
    theme: str | None = None
    size: int | None = None
    poll: float | None = None
    opacity: float | None = None
    no_topmost: bool = False
    config: str | None = None
    reset_config: bool = False


def get_default_config_path() -> Path:
    """Return platform-specific default config path (%APPDATA%/boostgauge/config.json on Windows, ~/.boostgauge/config.json on POSIX)."""
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        base_dir = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
        return base_dir / "boostgauge" / "config.json"
    return Path.home() / ".boostgauge" / "config.json"


def get_default_config() -> GaugeConfig:
    """Return a GaugeConfig instance initialized with default values."""
    return GaugeConfig()


def _dict_to_config(data: dict[str, Any]) -> GaugeConfig:
    """Helper to convert nested dictionary into GaugeConfig object."""
    config = GaugeConfig()
    if "polling_interval_seconds" in data:
        config.polling_interval_seconds = float(data["polling_interval_seconds"])
    if "theme" in data:
        config.theme = str(data["theme"])
    if "size" in data:
        config.size = int(data["size"])
    if "opacity" in data:
        config.opacity = float(data["opacity"])
    if "always_on_top" in data:
        config.always_on_top = bool(data["always_on_top"])
    if "show_driver_label" in data:
        config.show_driver_label = bool(data["show_driver_label"])
    if "show_digital_readout" in data:
        config.show_digital_readout = bool(data["show_digital_readout"])
    if "show_session_count" in data:
        config.show_session_count = bool(data["show_session_count"])

    if "position" in data and isinstance(data["position"], dict):
        pos_data = data["position"]
        config.position = PositionConfig(
            x=int(pos_data.get("x", 100)),
            y=int(pos_data.get("y", 100)),
        )

    if "thresholds" in data and isinstance(data["thresholds"], dict):
        thresh_data = data["thresholds"]
        config.thresholds = ThresholdsConfig(
            conpty=thresh_data.get("conpty", {"yellow": 30.0, "red": 60.0}),
            memory_percent=thresh_data.get("memory_percent", {"yellow": 60.0, "red": 80.0}),
            process_count=thresh_data.get("process_count", {"yellow": 300.0, "red": 500.0}),
            handle_count=thresh_data.get("handle_count", {"yellow": 30000.0, "red": 50000.0}),
        )

    if "telltale_windows" in data and isinstance(data["telltale_windows"], dict):
        tw_data = data["telltale_windows"]
        config.telltale_windows = TelltaleWindowsConfig(
            short=int(tw_data.get("short", 60)),
            medium=int(tw_data.get("medium", 600)),
            long=int(tw_data.get("long", 3600)),
        )

    return config


def load_config(config_path: Path | None = None) -> GaugeConfig:
    """Load config from JSON file; auto-create with defaults if missing. Raise ValueError on malformed JSON or invalid schema."""
    target_path = config_path if config_path is not None else get_default_config_path()
    if not target_path.exists():
        default_cfg = get_default_config()
        save_config(default_cfg, target_path)
        return default_cfg

    try:
        content = target_path.read_text(encoding="utf-8")
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse configuration JSON at {target_path}: {exc}") from exc
    except Exception as exc:
        raise ValueError(f"Failed to read configuration file at {target_path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Invalid configuration schema at {target_path}: top-level element must be a JSON object")

    try:
        return _dict_to_config(data)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid configuration schema at {target_path}: {exc}") from exc


def save_config(config: GaugeConfig, config_path: Path | None = None) -> None:
    """Serialize and write GaugeConfig instance to JSON file atomically."""
    target_path = config_path if config_path is not None else get_default_config_path()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.with_name(f".{target_path.name}.tmp")
    data = asdict(config)
    temp_path.write_text(json.dumps(data, indent=4), encoding="utf-8")
    temp_path.replace(target_path)


def parse_cli_args(args: list[str] | None = None) -> CLIArgs:
    """Parse command line arguments into CLIArgs object."""
    parser = argparse.ArgumentParser(
        prog="boostgauge",
        description="Lightweight system tachometer with peak-hold needles",
    )
    parser.add_argument("--theme", choices=VALID_THEMES, help="Tachometer visual theme")
    parser.add_argument("--size", type=int, help="Gauge window size in pixels")
    parser.add_argument("--poll", type=float, help="Polling interval in seconds")
    parser.add_argument("--opacity", type=float, help="Window transparency (0.0 to 1.0)")
    parser.add_argument("--no-topmost", action="store_true", help="Disable always-on-top window setting")
    parser.add_argument("--config", type=str, help="Path to custom JSON configuration file")
    parser.add_argument("--reset-config", action="store_true", help="Reset configuration file to defaults")

    parsed = parser.parse_args(args if args is not None else sys.argv[1:])
    return CLIArgs(
        theme=parsed.theme,
        size=parsed.size,
        poll=parsed.poll,
        opacity=parsed.opacity,
        no_topmost=parsed.no_topmost,
        config=parsed.config,
        reset_config=parsed.reset_config,
    )


def merge_config_and_args(config: GaugeConfig, cli_args: CLIArgs) -> GaugeConfig:
    """Apply non-None CLI argument overrides to GaugeConfig instance."""
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


def validate_config(config: GaugeConfig) -> list[str]:
    """Validate configuration fields and return list of validation error strings if invalid."""
    errors: list[str] = []
    if not (0.0 <= config.opacity <= 1.0):
        errors.append(f"opacity must be between 0.0 and 1.0, got {config.opacity}")
    if config.polling_interval_seconds <= 0:
        errors.append(f"polling_interval_seconds must be > 0, got {config.polling_interval_seconds}")
    if config.size <= 0:
        errors.append(f"size must be > 0, got {config.size}")
    if config.theme not in VALID_THEMES:
        errors.append(f"theme must be one of {VALID_THEMES}, got '{config.theme}'")

    for metric_name in ("conpty", "memory_percent", "process_count", "handle_count"):
        metric_dict = getattr(config.thresholds, metric_name, None)
        if isinstance(metric_dict, dict):
            yellow = metric_dict.get("yellow", 0.0)
            red = metric_dict.get("red", 0.0)
            if yellow >= red:
                errors.append(f"threshold yellow value ({yellow}) must be less than red value ({red}) for {metric_name}")

    return errors


def reset_config_to_defaults(config_path: Path | None = None) -> GaugeConfig:
    """Overwrite config file at config_path with default configuration and return default GaugeConfig."""
    target_path = config_path if config_path is not None else get_default_config_path()
    default_config = get_default_config()
    save_config(default_config, target_path)
    return default_config


def update_window_geometry(
    config: GaugeConfig,
    position: tuple[int, int],
    size: int,
    config_path: Path | None = None,
) -> GaugeConfig:
    """Update position and size in GaugeConfig and persist to config file on exit."""
    config.position.x = position[0]
    config.position.y = position[1]
    config.size = size
    save_config(config, config_path)
    return config
```

---

### 6.4 `src/boostgauge/app.py` (Add)

**Complete file contents:**

```python
"""Application CLI entry point integrating argparse CLI options, configuration loading, and application initialization.

Issue #7: Feature: Configuration File and CLI Arguments
"""

from __future__ import annotations

from pathlib import Path
import sys

from boostgauge.config import (
    get_default_config_path,
    load_config,
    merge_config_and_args,
    parse_cli_args,
    reset_config_to_defaults,
    validate_config,
)


def main(sys_args: list[str] | None = None) -> int:
    """Main CLI entry point for boostgauge."""
    try:
        cli_args = parse_cli_args(sys_args)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    config_path = Path(cli_args.config) if cli_args.config else get_default_config_path()

    if cli_args.reset_config:
        reset_config_to_defaults(config_path)
        print(f"Reset configuration to defaults at {config_path}")
        return 0

    try:
        config = load_config(config_path)
    except ValueError as err:
        print(f"Error loading configuration: {err}", file=sys.stderr)
        return 1

    config = merge_config_and_args(config, cli_args)
    validation_errors = validate_config(config)

    if validation_errors:
        print("Configuration validation errors:", file=sys.stderr)
        for error in validation_errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

---

### 6.5 `tests/unit/test_config.py` (Add)

**Complete file contents:**

```python
"""Unit test suite for configuration file loading, saving, CLI parsing, validation, and geometry updates.

Issue #7: Feature: Configuration File and CLI Arguments
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import pytest

from boostgauge.app import main
from boostgauge.config import (
    CLIArgs,
    GaugeConfig,
    PositionConfig,
    ThresholdsConfig,
    get_default_config,
    get_default_config_path,
    load_config,
    merge_config_and_args,
    parse_cli_args,
    reset_config_to_defaults,
    save_config,
    update_window_geometry,
    validate_config,
)


def test_t010_auto_create_default_config_on_first_launch(tmp_path: Path) -> None:
    """T010: Auto-create default config on first launch if missing."""
    config_file = tmp_path / "boostgauge" / "config.json"
    assert not config_file.exists()

    config = load_config(config_file)
    assert config_file.exists()
    assert config == get_default_config()


def test_t020_load_config_from_custom_path(tmp_path: Path) -> None:
    """T020: Load config from custom file path via load_config."""
    config_file = tmp_path / "custom" / "my_config.json"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    custom_data = {
        "polling_interval_seconds": 3.5,
        "theme": "neon",
        "size": 450,
        "opacity": 0.85,
        "always_on_top": False,
    }
    config_file.write_text(json.dumps(custom_data), encoding="utf-8")

    config = load_config(config_file)
    assert config.theme == "neon"
    assert config.size == 450
    assert config.polling_interval_seconds == 3.5
    assert config.opacity == 0.85
    assert config.always_on_top is False


def test_t030_reset_config_using_reset_flag(tmp_path: Path) -> None:
    """T030: Reset existing config file to defaults via reset_config_to_defaults."""
    config_file = tmp_path / "config.json"
    modified_config = GaugeConfig(theme="neon", size=500)
    save_config(modified_config, config_file)

    loaded = load_config(config_file)
    assert loaded.theme == "neon"

    reset_cfg = reset_config_to_defaults(config_file)
    assert reset_cfg.theme == "dark"

    reloaded = load_config(config_file)
    assert reloaded.theme == "dark"
    assert reloaded.size == 300


def test_t040_override_config_via_cli_args() -> None:
    """T040: Override config settings using parse_cli_args and merge_config_and_args."""
    cli_args = parse_cli_args(
        ["--theme", "light", "--size", "400", "--poll", "5.0", "--opacity", "0.8", "--no-topmost"]
    )
    base_config = get_default_config()
    merged = merge_config_and_args(base_config, cli_args)

    assert merged.theme == "light"
    assert merged.size == 400
    assert merged.polling_interval_seconds == 5.0
    assert merged.opacity == 0.8
    assert merged.always_on_top is False


def test_t050_save_and_restore_window_geometry(tmp_path: Path) -> None:
    """T050: update_window_geometry updates DTO and writes updated values to disk."""
    config_file = tmp_path / "config.json"
    config = get_default_config()
    save_config(config, config_file)

    updated = update_window_geometry(config, (250, 350), 400, config_file)
    assert updated.position.x == 250
    assert updated.position.y == 350
    assert updated.size == 400

    reloaded = load_config(config_file)
    assert reloaded.position.x == 250
    assert reloaded.position.y == 350
    assert reloaded.size == 400


def test_t060_dynamic_threshold_update_in_memory() -> None:
    """T060: Modifying threshold dictionary updates active configuration immediately."""
    config = get_default_config()
    assert config.thresholds.conpty["yellow"] == 30.0

    config.thresholds.conpty["yellow"] = 45.0
    assert config.thresholds.conpty["yellow"] == 45.0


def test_t070_validation_failure_on_out_of_range_opacity() -> None:
    """T070: validate_config returns error string for opacity outside 0.0-1.0 range."""
    config = get_default_config()
    config.opacity = 1.5
    errors = validate_config(config)

    assert len(errors) > 0
    assert any("opacity" in err for err in errors)


def test_t080_validation_failure_on_invalid_theme_or_poll_interval() -> None:
    """T080: validate_config returns descriptive errors for invalid inputs."""
    config = get_default_config()
    config.theme = "invalid_theme"
    config.polling_interval_seconds = -1.0
    config.thresholds.conpty = {"yellow": 80.0, "red": 50.0}

    errors = validate_config(config)
    assert len(errors) == 3
    assert any("theme" in err for err in errors)
    assert any("polling_interval_seconds" in err for err in errors)
    assert any("threshold yellow value" in err for err in errors)


def test_default_config_path_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test platform-dependent default config path resolution comparing pathlib.Path objects."""
    # Test POSIX resolution
    monkeypatch.setattr(sys, "platform", "linux")
    posix_path = get_default_config_path()
    assert posix_path == Path.home() / ".boostgauge" / "config.json"

    # Test Windows resolution
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", "C:\\Users\\TestUser\\AppData\\Roaming")
    win_path = get_default_config_path()
    assert win_path == Path("C:\\Users\\TestUser\\AppData\\Roaming") / "boostgauge" / "config.json"


def test_app_main_success(tmp_path: Path) -> None:
    """Test main entry point executing successfully with CLI options."""
    config_file = tmp_path / "config.json"
    args = ["--config", str(config_file), "--theme", "neon"]
    exit_code = main(args)
    assert exit_code == 0
    loaded = load_config(config_file)
    assert loaded.theme == "neon"


def test_app_main_invalid_config(tmp_path: Path) -> None:
    """Test main entry point handling invalid configuration options."""
    config_file = tmp_path / "config.json"
    args = ["--config", str(config_file), "--size", "-50"]
    exit_code = main(args)
    assert exit_code == 1
```

---

## 7. Pattern References

### 7.1 Path Resolution and Standard Test Bootstrap

**File:** `tests/conftest.py` (lines 1-8)

```python
"""Project test bootstrap."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
```

**Relevance:** Standard project path resolution using `pathlib.Path` and `from __future__ import annotations`. Used in `src/boostgauge/config.py` and `tests/unit/test_config.py`.

---

### 7.2 Pytest Configuration Standards

**File:** `pyproject.toml` (lines 35-41)

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-ra --strict-markers"
```

**Relevance:** Test discovery parameters defining naming standards (`test_*.py`, `test_*`) for all unit tests created in `tests/unit/test_config.py`.

---

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `from __future__ import annotations` | stdlib | All Python modules |
| `import argparse` | stdlib | `src/boostgauge/config.py` |
| `from dataclasses import dataclass, field, asdict` | stdlib | `src/boostgauge/config.py` |
| `import json` | stdlib | `src/boostgauge/config.py`, `tests/unit/test_config.py` |
| `import os` | stdlib | `src/boostgauge/config.py` |
| `from pathlib import Path` | stdlib | All Python modules |
| `import sys` | stdlib | `src/boostgauge/config.py`, `src/boostgauge/app.py`, `tests/unit/test_config.py` |
| `from typing import Any, TypedDict` | stdlib | `src/boostgauge/config.py` |
| `import pytest` | dev dependency (`pyproject.toml`) | `tests/unit/test_config.py` |

**New Dependencies:** None (standard library `argparse`, `json`, `pathlib`, `dataclasses` used exclusively).

---

## 9. Placeholder

*Reserved for future workflow alignment.*

---

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output | Assertion Strategy |
|---------|---------------|-------|-----------------|--------------------|
| T010 | `load_config()` | `config_path = tmp_path / "boostgauge" / "config.json"` | Returns default `GaugeConfig` & creates file | Check file exists & compare `config == get_default_config()` |
| T020 | `load_config()` | Custom `config.json` with `theme="neon", size=450` | `GaugeConfig` with overridden values | Check `config.theme == "neon"` & `config.size == 450` |
| T030 | `reset_config_to_defaults()` | Existing modified `config.json` | Returns default `GaugeConfig` & rewrites file | Compare reloaded `theme == "dark"` & `size == 300` |
| T040 | `merge_config_and_args()` | Base `GaugeConfig` + `CLIArgs(theme="light", size=400)` | Merged `GaugeConfig` instance | Compare `merged.theme == "light"` & `merged.size == 400` |
| T050 | `update_window_geometry()` | `config`, `position=(250, 350)`, `size=400` | Updated `GaugeConfig` saved to disk | Compare `reloaded.position.x == 250` & `size == 400` |
| T060 | In-memory threshold mutation | `config.thresholds.conpty["yellow"] = 45.0` | Active DTO threshold updated | Compare `config.thresholds.conpty["yellow"] == 45.0` |
| T070 | `validate_config()` | `GaugeConfig` with `opacity=1.5` | Non-empty list containing error string | Assert `any("opacity" in err for err in errors)` |
| T080 | `validate_config()` | `GaugeConfig` with `theme="invalid"`, `poll=-1.0`, invalid threshold | List containing 3 specific error strings | Assert `len(errors) == 3` & check error substrings |

*Note: Path assertions compare `pathlib.Path` objects directly (`posix_path == Path.home() / ".boostgauge" / "config.json"`) per platform-independence guidelines.*

---

## 11. Implementation Notes

### 11.1 Error Handling Convention

All functions parsing or loading configuration handle errors gracefully:
- File loading or parsing failures raise `ValueError` with descriptive message strings.
- CLI argument errors cause `main()` in `app.py` to print clean messages to `sys.stderr` and return non-zero exit codes (1 for validation/config error, 2 for CLI parse error).

### 11.2 Logging & User Feedback Convention

Terminal user feedback follows these formats:
- Reset notification: `Reset configuration to defaults at {config_path}`
- Validation error header: `Configuration validation errors:`
- Individual error bullets: `  - {error}`

### 11.3 Constants & Default Configuration Table

| Parameter | Default Value | Validation Range / Allowed Values |
|-----------|---------------|----------------------------------|
| `polling_interval_seconds` | `2.0` | `> 0` |
| `theme` | `"dark"` | `("dark", "light", "neon", "classic")` |
| `size` | `300` | `> 0` |
| `opacity` | `0.9` | `0.0 <= opacity <= 1.0` |
| `always_on_top` | `True` | `bool` |
| `position` | `{"x": 100, "y": 100}` | Integers |
| `thresholds.conpty` | `{"yellow": 30.0, "red": 60.0}` | `yellow < red` |
| `thresholds.memory_percent` | `{"yellow": 60.0, "red": 80.0}` | `yellow < red` |
| `thresholds.process_count` | `{"yellow": 300.0, "red": 500.0}` | `yellow < red` |
| `thresholds.handle_count` | `{"yellow": 30000.0, "red": 50000.0}` | `yellow < red` |

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
| Finalized | 2026-07-28T15:44:00Z |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #7 |
| Verdict | APPROVED |
| Date | 2026-07-28 |
| Iterations | 0 |
| Finalized | 2026-07-28T20:44:29Z |

### Review Feedback Summary

\nThe Implementation Spec for Issue #7 (*Configuration File and CLI Arguments*) is exceptionally detailed, complete, and concrete. It provides exact Python implementations, diffs, dataclass definitions, function specifications, and a comprehensive test suite for all target files. An autonomous AI agent can execute this spec directly without asking clarifying questions and achieve a high first-try success rate.\n\n## Blocking Issues\nNo blocking issues found.\n\n## High Priority Issues\nNo high-p...
