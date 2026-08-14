# Implementation Spec: Feature: configuration file and CLI arguments

<!-- Metadata -->
| Field | Value |
|-------|-------|
| Issue | #7 |
| LLD | `docs/lld/done/7-config.md` |
| Generated | 2026-08-14 |
| Status | APPROVED |

## 1. Overview

**Objective:** Implement a configuration system for thresholds, polling intervals, and window behavior, supporting CLI overrides and specific persistence rules for hand-made window changes.

**Success Criteria:** Provide a configuration module that parses JSON configurations, manages session overrides seamlessly, persists specific hand-made direct GUI manipulations without clobbering direct-file adjustments, and provides robust invalid-file fallback to defaults.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/config.py` | Add | Configuration data structures, validation, and read/write logic |
| 2 | `tests/unit/test_config.py` | Add | Unit tests verifying configuration persistence and read semantics |

**Implementation Order Rationale:** The configuration module logic (`config.py`) must be built first so that tests (`test_config.py`) can accurately import the resulting symbols and ensure coverage criteria are met. Both files are strictly additions with no existing dependencies.

## 3. Current State (for Modify/Delete files)

*This section is intentionally empty. No files are being modified or deleted in this implementation. All files are pure additions.*

## 4. Data Structures

### 4.1 `PositionConfig`

**Definition:**

```python
class PositionConfig(TypedDict):
    x: int
    y: int
```

**Concrete Example:**

```json
{
    "x": 100,
    "y": 100
}
```

### 4.2 `ThresholdConfig`

**Definition:**

```python
class ThresholdConfig(TypedDict):
    yellow: int
    red: int
```

**Concrete Example:**

```json
{
    "yellow": 50,
    "red": 80
}
```

### 4.3 `Thresholds`

**Definition:**

```python
class Thresholds(TypedDict):
    conpty: ThresholdConfig
    memory_percent: ThresholdConfig
    process_count: ThresholdConfig
    handle_count: ThresholdConfig
```

**Concrete Example:**

```json
{
    "conpty": {
        "yellow": 50,
        "red": 80
    },
    "memory_percent": {
        "yellow": 70,
        "red": 90
    },
    "process_count": {
        "yellow": 200,
        "red": 300
    },
    "handle_count": {
        "yellow": 5000,
        "red": 10000
    }
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

### 4.5 `AppConfig`

**Definition:**

```python
class AppConfig(TypedDict):
    polling_interval_seconds: int
    theme: str
    size: int
    opacity: float
    always_on_top: bool
    position: PositionConfig
    thresholds: Thresholds
    telltale_windows: TelltaleWindows
    show_driver_label: bool
    show_digital_readout: bool
    show_session_count: bool
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
            "yellow": 50,
            "red": 80
        },
        "memory_percent": {
            "yellow": 70,
            "red": 90
        },
        "process_count": {
            "yellow": 200,
            "red": 300
        },
        "handle_count": {
            "yellow": 5000,
            "red": 10000
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

### 4.6 `SessionState`

**Definition:**

```python
class SessionState(TypedDict):
    config_file_path: str
    active_config: AppConfig
    hand_changed_position: Optional[PositionConfig]
    hand_changed_size: Optional[int]
    reset_config_flag: bool
```

**Concrete Example:**

```json
{
    "config_file_path": "C:/Users/User/.boostgauge/config.json",
    "active_config": {
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
                "yellow": 50,
                "red": 80
            },
            "memory_percent": {
                "yellow": 70,
                "red": 90
            },
            "process_count": {
                "yellow": 200,
                "red": 300
            },
            "handle_count": {
                "yellow": 5000,
                "red": 10000
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
    },
    "hand_changed_position": null,
    "hand_changed_size": 400,
    "reset_config_flag": false
}
```

## 5. Function Specifications

### 5.1 `load_config()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def load_config(path: str, reset_flag: bool, cli_overrides: dict) -> AppConfig:
    """Loads config, handles reset and auto-creation, applies CLI overrides. Logs INFO on read/write."""
    ...
```

**Input Example:**

```python
path = "C:/temp/config.json"
reset_flag = False
cli_overrides = {"size": 500}
```

**Output Example:**

```python
{
    "polling_interval_seconds": 2,
    "theme": "dark",
    "size": 500,
    "opacity": 0.9,
    "always_on_top": True,
    "position": {"x": 100, "y": 100},
    "thresholds": {
        "conpty": {"yellow": 50, "red": 80},
        "memory_percent": {"yellow": 70, "red": 90},
        "process_count": {"yellow": 200, "red": 300},
        "handle_count": {"yellow": 5000, "red": 10000}
    },
    "telltale_windows": {"short": 60, "medium": 600, "long": 3600},
    "show_driver_label": True,
    "show_digital_readout": True,
    "show_session_count": True
}
```

**Edge Cases:**
- `path` file contains invalid JSON -> triggers `mitigate_invalid_config` and raises `ValueError`.
- `path` parent directory does not exist -> creates parent directories implicitly when saving default config.
- `reset_flag` is True -> overwrites existing file with defaults before reading.

### 5.2 `apply_threshold_updates()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def apply_threshold_updates(path: str, current_config: AppConfig) -> AppConfig:
    """Re-reads config from disk and applies ONLY threshold updates to current_config. Logs INFO on reload."""
    ...
```

**Input Example:**

```python
path = "C:/temp/config.json"
current_config = {
    # Full default AppConfig except for thresholds
    "thresholds": {
        "conpty": {"yellow": 50, "red": 80},
        "memory_percent": {"yellow": 70, "red": 90},
        "process_count": {"yellow": 200, "red": 300},
        "handle_count": {"yellow": 5000, "red": 10000}
    },
    "theme": "dark",
    "size": 300
}
```

**Output Example:**

```python
{
    "thresholds": {
        "conpty": {"yellow": 50, "red": 70}, # 'red' value was modified on disk to 70
        "memory_percent": {"yellow": 70, "red": 90},
        "process_count": {"yellow": 200, "red": 300},
        "handle_count": {"yellow": 5000, "red": 10000}
    },
    "theme": "dark", # Unchanged, even if disk was modified
    "size": 300
}
```

**Edge Cases:**
- The file on disk was deleted -> returns the original `current_config` without raising an error.
- The file contains malformed JSON -> returns `current_config` and logs error.

### 5.3 `save_session_changes()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def save_session_changes(path: str, hand_changed_position: Optional[PositionConfig], hand_changed_size: Optional[int]) -> None:
    """Writes exactly the hand-changed keys (position/size) to the config file on exit. Logs INFO on save."""
    ...
```

**Input Example:**

```python
path = "C:/temp/config.json"
hand_changed_position = {"x": 150, "y": 150}
hand_changed_size = None
```

**Output Example:**

```python
None # Writes directly to C:/temp/config.json updating ONLY "position" field.
```

**Edge Cases:**
- Both `hand_changed_position` and `hand_changed_size` are `None` -> Function does a no-op; no disk write.
- File on disk is malformed JSON -> Performs no writes and logs an error to avoid data corruption.

### 5.4 `mitigate_invalid_config()`

**File:** `src/boostgauge/config.py`

**Signature:**

```python
def mitigate_invalid_config(path: str, raw_data: str) -> None:
    """Handles and isolates config load failures safely, ensuring fallback to defaults without data loss. Logs ERROR on invalid config."""
    ...
```

**Input Example:**

```python
path = "C:/temp/config.json"
raw_data = '{"size": 300, "theme": "dark", ...' # Incomplete JSON string
```

**Output Example:**

```python
None # Moves C:/temp/config.json to C:/temp/config.json.corrupt and writes default to C:/temp/config.json.
```

**Edge Cases:**
- Backup corrupt file already exists -> Overwrites the previous corrupt backup.

## 6. Change Instructions

### 6.1 `src/boostgauge/config.py` (Add)

**Action:** Create the file `src/boostgauge/config.py`.

**Contents Description:**
1. Import necessary libraries (`json`, `os`, `logging`, `tempfile`, `pathlib.Path`, and `typing` structures).
2. Define the `TypedDict` configurations from Section 4.
3. Define a module-level constant `DEFAULT_CONFIG` representing the AppConfig baseline values.
4. Implement `load_config(path: str, reset_flag: bool, cli_overrides: dict) -> AppConfig`. Ensure it creates parent directories using `Path.mkdir(parents=True, exist_ok=True)`. Read JSON, merge it into a deep copy of `DEFAULT_CONFIG` to fill missing keys, and overlay `cli_overrides`. If file missing, populate `DEFAULT_CONFIG` via atomic write tempfile.
5. Implement `apply_threshold_updates(path: str, current_config: AppConfig) -> AppConfig`. Read file, cherry-pick the `thresholds` dictionary, and update a copied instance of `current_config`.
6. Implement `save_session_changes(path: str, hand_changed_position: Optional[PositionConfig], hand_changed_size: Optional[int]) -> None`. Read file into dict. Merge `hand_changed_position` into `disk_dict["position"]` and `hand_changed_size` into `disk_dict["size"]` if not None. Save atomically via `tempfile` rename to `path`.
7. Implement `mitigate_invalid_config(path: str, raw_data: str) -> None`. Rename `path` to `path + ".corrupt"`. Dump `DEFAULT_CONFIG` atomically to `path`. Raise `ValueError("Invalid JSON")`.

### 6.2 `tests/unit/test_config.py` (Add)

**Action:** Create the file `tests/unit/test_config.py`.

**Contents Description:**
1. Import `pytest`, `json`.
2. Import functions from `boostgauge.config`.
3. Implement 22 test methods spanning `test_req_010` through `test_req_220` according to the scenarios outlined in LLD section 10.1.
4. Pass `tmp_path` fixture to every test to isolate files. Compare paths rigorously using pathlib, ignoring explicit slashes.
5. Follow all assertions directly as specified in the expected behavior list in Section 10.

## 7. Pattern References

### 7.1 Standard Collector Imports

**File:** `src/boostgauge/collectors/windows.py` (lines 3-8)

```python
import queue
import threading
import time
from typing import Dict, Optional
import psutil
```

**Relevance:** Represents the project's standard import grouping pattern (stdlib followed by typing, then 3rd party). `config.py` should follow the same module standard for imports (`import json`, `import logging`, `import tempfile`, etc., followed by `typing` imports).

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `import json` | stdlib | `src/boostgauge/config.py`, `tests/unit/test_config.py` |
| `import os` | stdlib | `src/boostgauge/config.py` |
| `import logging` | stdlib | `src/boostgauge/config.py` |
| `import tempfile` | stdlib | `src/boostgauge/config.py` |
| `from pathlib import Path` | stdlib | `src/boostgauge/config.py`, `tests/unit/test_config.py` |
| `from typing import TypedDict, Optional, Dict, Any` | stdlib | `src/boostgauge/config.py` |
| `import pytest` | 3rd party | `tests/unit/test_config.py` |

**New Dependencies:** None

## 9. Placeholder

*Reserved for future use to maintain alignment with LLD section numbering.*

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `load_config()` | `path=tmp, reset=False, cli={}` | File created, `active["size"] == 300` |
| T020 | `load_config()` | `path=tmp(size 200), reset=False, cli={"size": 400}` | `active["size"] == 400`, `file["size"] == 200` |
| T030 | `load_config()` | `path=tmp(size 200), reset=False, cli={}` | `active["size"] == 200` |
| T040 | `load_config()` | `path=tmp, reset=True, cli={"size": 500}` | `active["size"] == 500`, `file["size"] == 300` |
| T050 | `apply_threshold_updates()`| `path=tmp(red 70)` | `active["thresholds"]["conpty"]["red"] == 70` |
| T060 | `save_session_changes()` | `path=tmp, size=400, theme="light"` | `file["size"] == 400`, `file["theme"] == "light"` |
| T070 | `save_session_changes()` | `path=tmp(size 500), size=400` | `file["size"] == 400` |
| T080 | `save_session_changes()` | `path=tmp, no args` | File byte-identical (`hash` equivalent) |
| T090 | `save_session_changes()` | `path=tmp, not moved` | File `"position": {"x": 100, "y": 100}` |
| T100 | `save_session_changes()` | `path=tmp, moved=150,150` | File `"position": {"x": 150, "y": 150}` |
| T110 | `save_session_changes()` | `path=tmp(reset), not moved` | File `"position": {"x": 100, "y": 100}` |
| T120 | `save_session_changes()` | `path=tmp(reset), moved=150,150` | File `"position": {"x": 150, "y": 150}` |
| T130 | `save_session_changes()` | `path=tmp, size=None` | File `"size": 300` |
| T140 | `save_session_changes()` | `path=tmp, size=400` | File `"size": 400` |
| T150 | `save_session_changes()` | `path=tmp, cli=500, size=None` | File `"size": 300` |
| T160 | `save_session_changes()` | `path=tmp, cli=500, size=400` | File `"size": 400` |
| T170 | `save_session_changes()` | `path=tmp(reset), size=None` | File `"size": 300` |
| T180 | `save_session_changes()` | `path=tmp(reset), size=400` | File `"size": 400` |
| T190 | `save_session_changes()` | `path=tmp(reset), cli=500, size=None`| File `"size": 300` |
| T200 | `save_session_changes()` | `path=tmp(reset), cli=500, size=400` | File `"size": 400` |
| T210 | `load_config()` | `path=tmp(invalid)` | Raises `ValueError("Invalid JSON")` |
| T220 | `apply_threshold_updates()`| `path=tmp(theme="light")` | `active["theme"] == "dark"` |

### 10.1 Per-criterion test functions

```python
import json
import pytest
from pathlib import Path
from boostgauge.config import load_config, apply_threshold_updates, save_session_changes, mitigate_invalid_config

def test_req_010(tmp_path):
    # First run auto-create (REQ-1)
    config_file = tmp_path / "config.json"
    active_config = load_config(str(config_file), reset_flag=False, cli_overrides={})
    assert config_file.exists()
    with open(config_file, "r") as f:
        disk_data = json.load(f)
    assert disk_data["size"] == 300
    assert active_config["size"] == 300

def test_req_020(tmp_path):
    # Launch order overrides (REQ-2)
    config_file = tmp_path / "config.json"
    with open(config_file, "w") as f:
        json.dump({"size": 200}, f)
    active_config = load_config(str(config_file), reset_flag=False, cli_overrides={"size": 400})
    assert active_config["size"] == 400
    with open(config_file, "r") as f:
        disk_data = json.load(f)
    assert disk_data["size"] == 200

def test_req_030(tmp_path):
    # File coordinates used (REQ-3)
    config_file = tmp_path / "config.json"
    load_config(str(config_file), reset_flag=False, cli_overrides={})
    with open(config_file, "w") as f:
        json.dump({"size": 200, "position": {"x": 120, "y": 120}}, f)
    active_config = load_config(str(config_file), reset_flag=False, cli_overrides={})
    assert active_config["size"] == 200
    assert active_config["position"] == {"x": 120, "y": 120}

def test_req_040(tmp_path):
    # Reset behavior (REQ-4)
    config_file = tmp_path / "config.json"
    load_config(str(config_file), reset_flag=False, cli_overrides={})
    with open(config_file, "w") as f:
        json.dump({"size": 200}, f)
    active_config = load_config(str(config_file), reset_flag=True, cli_overrides={"size": 500})
    assert active_config["size"] == 500
    with open(config_file, "r") as f:
        disk_data = json.load(f)
    assert disk_data["size"] == 300

def test_req_050(tmp_path):
    # Threshold reload (REQ-5)
    config_file = tmp_path / "config.json"
    active_config = load_config(str(config_file), reset_flag=False, cli_overrides={})
    with open(config_file, "r") as f:
        disk_data = json.load(f)
    disk_data["thresholds"]["conpty"]["red"] = 70
    with open(config_file, "w") as f:
        json.dump(disk_data, f)
    new_config = apply_threshold_updates(str(config_file), active_config)
    assert new_config["thresholds"]["conpty"]["red"] == 70

def test_req_060(tmp_path):
    # Exit writes changed (REQ-6)
    config_file = tmp_path / "config.json"
    load_config(str(config_file), reset_flag=False, cli_overrides={})
    with open(config_file, "r") as f:
        disk_data = json.load(f)
    disk_data["theme"] = "light"
    with open(config_file, "w") as f:
        json.dump(disk_data, f)
    save_session_changes(str(config_file), hand_changed_position=None, hand_changed_size=400)
    with open(config_file, "r") as f:
        disk_data2 = json.load(f)
    assert disk_data2["size"] == 400
    assert disk_data2["theme"] == "light"

def test_req_070(tmp_path):
    # Direct edit collision (REQ-7)
    config_file = tmp_path / "config.json"
    load_config(str(config_file), reset_flag=False, cli_overrides={})
    with open(config_file, "r") as f:
        disk_data = json.load(f)
    disk_data["size"] = 500
    with open(config_file, "w") as f:
        json.dump(disk_data, f)
    save_session_changes(str(config_file), hand_changed_position=None, hand_changed_size=400)
    with open(config_file, "r") as f:
        disk_data2 = json.load(f)
    assert disk_data2["size"] == 400

def test_req_080(tmp_path):
    # Untouched session (REQ-8)
    config_file = tmp_path / "config.json"
    load_config(str(config_file), reset_flag=False, cli_overrides={})
    with open(config_file, "rb") as f:
        b1 = f.read()
    save_session_changes(str(config_file), hand_changed_position=None, hand_changed_size=None)
    with open(config_file, "rb") as f:
        b2 = f.read()
    assert b1 == b2

def test_req_090(tmp_path):
    # Position not moved (REQ-9)
    config_file = tmp_path / "config.json"
    load_config(str(config_file), reset_flag=False, cli_overrides={})
    save_session_changes(str(config_file), hand_changed_position=None, hand_changed_size=None)
    with open(config_file, "r") as f:
        disk_data = json.load(f)
    assert disk_data["position"] == {"x": 100, "y": 100}

def test_req_100(tmp_path):
    # Position moved (REQ-10)
    config_file = tmp_path / "config.json"
    load_config(str(config_file), reset_flag=False, cli_overrides={})
    save_session_changes(str(config_file), hand_changed_position={"x": 150, "y": 150}, hand_changed_size=None)
    with open(config_file, "r") as f:
        disk_data = json.load(f)
    assert disk_data["position"] == {"x": 150, "y": 150}

def test_req_110(tmp_path):
    # Position reset not moved (REQ-11)
    config_file = tmp_path / "config.json"
    load_config(str(config_file), reset_flag=True, cli_overrides={})
    save_session_changes(str(config_file), hand_changed_position=None, hand_changed_size=None)
    with open(config_file, "r") as f:
        disk_data = json.load(f)
    assert disk_data["position"] == {"x": 100, "y": 100}

def test_req_120(tmp_path):
    # Position reset moved (REQ-12)
    config_file = tmp_path / "config.json"
    load_config(str(config_file), reset_flag=True, cli_overrides={})
    save_session_changes(str(config_file), hand_changed_position={"x": 150, "y": 150}, hand_changed_size=None)
    with open(config_file, "r") as f:
        disk_data = json.load(f)
    assert disk_data["position"] == {"x": 150, "y": 150}

def test_req_130(tmp_path):
    # Size not resized (REQ-13)
    config_file = tmp_path / "config.json"
    load_config(str(config_file), reset_flag=False, cli_overrides={})
    save_session_changes(str(config_file), hand_changed_position=None, hand_changed_size=None)
    with open(config_file, "r") as f:
        disk_data = json.load(f)
    assert disk_data["size"] == 300

def test_req_140(tmp_path):
    # Size resized (REQ-14)
    config_file = tmp_path / "config.json"
    load_config(str(config_file), reset_flag=False, cli_overrides={})
    save_session_changes(str(config_file), hand_changed_position=None, hand_changed_size=400)
    with open(config_file, "r") as f:
        disk_data = json.load(f)
    assert disk_data["size"] == 400

def test_req_150(tmp_path):
    # Size CLI not resized (REQ-15)
    config_file = tmp_path / "config.json"
    load_config(str(config_file), reset_flag=False, cli_overrides={"size": 500})
    save_session_changes(str(config_file), hand_changed_position=None, hand_changed_size=None)
    with open(config_file, "r") as f:
        disk_data = json.load(f)
    assert disk_data["size"] == 300

def test_req_160(tmp_path):
    # Size CLI resized (REQ-16)
    config_file = tmp_path / "config.json"
    load_config(str(config_file), reset_flag=False, cli_overrides={"size": 500})
    save_session_changes(str(config_file), hand_changed_position=None, hand_changed_size=400)
    with open(config_file, "r") as f:
        disk_data = json.load(f)
    assert disk_data["size"] == 400

def test_req_170(tmp_path):
    # Size reset not resized (REQ-17)
    config_file = tmp_path / "config.json"
    load_config(str(config_file), reset_flag=True, cli_overrides={})
    save_session_changes(str(config_file), hand_changed_position=None, hand_changed_size=None)
    with open(config_file, "r") as f:
        disk_data = json.load(f)
    assert disk_data["size"] == 300

def test_req_180(tmp_path):
    # Size reset resized (REQ-18)
    config_file = tmp_path / "config.json"
    load_config(str(config_file), reset_flag=True, cli_overrides={})
    save_session_changes(str(config_file), hand_changed_position=None, hand_changed_size=400)
    with open(config_file, "r") as f:
        disk_data = json.load(f)
    assert disk_data["size"] == 400

def test_req_190(tmp_path):
    # Size reset CLI not resized (REQ-19)
    config_file = tmp_path / "config.json"
    load_config(str(config_file), reset_flag=True, cli_overrides={"size": 500})
    save_session_changes(str(config_file), hand_changed_position=None, hand_changed_size=None)
    with open(config_file, "r") as f:
        disk_data = json.load(f)
    assert disk_data["size"] == 300

def test_req_200(tmp_path):
    # Size reset CLI resized (REQ-20)
    config_file = tmp_path / "config.json"
    load_config(str(config_file), reset_flag=True, cli_overrides={"size": 500})
    save_session_changes(str(config_file), hand_changed_position=None, hand_changed_size=400)
    with open(config_file, "r") as f:
        disk_data = json.load(f)
    assert disk_data["size"] == 400

def test_req_210(tmp_path):
    # Invalid values (REQ-21)
    config_file = tmp_path / "config.json"
    with open(config_file, "w") as f:
        f.write('{"polling_interval_seconds": "fast"')
    with pytest.raises(ValueError, match="Invalid JSON"):
        load_config(str(config_file), reset_flag=False, cli_overrides={})

def test_req_220(tmp_path):
    # Non-threshold edit (REQ-22)
    config_file = tmp_path / "config.json"
    active_config = load_config(str(config_file), reset_flag=False, cli_overrides={})
    with open(config_file, "r") as f:
        disk_data = json.load(f)
    disk_data["theme"] = "light"
    with open(config_file, "w") as f:
        json.dump(disk_data, f)
    new_config = apply_threshold_updates(str(config_file), active_config)
    assert new_config["theme"] == "dark"
```

## 11. Implementation Notes

### 11.1 Error Handling Convention

The module expects disk I/O and JSON parsing to be cleanly isolated. Any invalid configuration data should hit `mitigate_invalid_config`, which preserves user data under a `.corrupt` extension before throwing `ValueError("Invalid JSON")` to force the app's startup to fail cleanly.

### 11.2 Atomic Write Convention

File saves must use `tempfile.NamedTemporaryFile(delete=False)` configured to the exact destination directory (to avoid cross-device linking errors), dump the payload, close the handler, and then `os.replace` the temp file over the target `path`.

### 11.3 Constants

| Constant | Value | Rationale |
|----------|-------|-----------|
| `DEFAULT_CONFIG` | Complete Dict | Represents a deterministic fallback state explicitly mandated for missing/reset scenarios. |

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3) - *Not applicable, Additions only*
- [x] Every data structure has a concrete JSON/YAML example (Section 4)
- [x] Every **non-test** function has input/output examples with realistic values (Section 5)
- [x] Every LLD pass criterion has a test function (Section 10.1)
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
| Date | 2026-08-14 |
| Iterations | 1 |
| Finalized | 2026-08-14T06:20:26Z |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #7 |
| Verdict | APPROVED |
| Date | 2026-08-14 |
| Iterations | 1 |
| Finalized | 2026-08-14T06:27:07Z |

### Review Feedback Summary

The spec resolves previous traceability and behavior contradiction issues. `test_req_020` now correctly expects `disk_data["size"] == 200`, properly aligning with `load_config`'s specified behavior to merge missing keys in-memory without blindly writing them back to disk. Function specifications, expected inputs/outputs, edge cases, and test assertions are concrete, internally consistent, and highly executable by an autonomous agent without requiring further clarification.
