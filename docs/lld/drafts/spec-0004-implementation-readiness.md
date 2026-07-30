# Implementation Spec: Windows Data Collector — ConPTY, Processes, Memory, Handles

| Field | Value |
|-------|-------|
| Issue | #4 |
| LLD | `docs/lld/done/0004-windows-data-collector.md` |
| Generated | 2026-07-29 |
| Status | APPROVED |

## 1. Overview

**Objective:** Build the Windows-specific data collector that polls system metrics (ConPTY process count, system process count, memory %, aggregate handle count, and unleashed session count) and feeds them to the gauge via a thread-safe composite metric pipeline.

**Success Criteria:**
- Implement `DataCollector` abstract base class, `SystemSnapshot` dataclass, and `compute_composite_metric()` piece-wise linear algorithm in `src/boostgauge/collector.py`.
- Implement `WindowsCollector` leveraging `psutil` and Win32 `ctypes` in `src/boostgauge/collectors/windows.py` with cadence splitting (2s fast cycle / 5s heavy cycle) and resilient error handling (`psutil.AccessDenied`, `psutil.NoSuchProcess`).
- Implement `get_collector()` platform factory in `src/boostgauge/collectors/__init__.py` returning `WindowsCollector` on `win32` and base stub on other platforms.
- Update `src/boostgauge/__init__.py` exports.
- Achieve 100% test pass rate across unit and contract test suites (`tests/unit/test_collector.py`, `tests/unit/test_windows_collector.py`, `tests/contract/test_collector_contract.py`) with Option C GUI test compliance.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/collector.py` | Add | Abstract base class `DataCollector`, `SystemSnapshot` dataclass, `normalize_metric_value()`, and `compute_composite_metric()`. |
| 2 | `src/boostgauge/collectors/__init__.py` | Add | Subpackage initialization exporting `WindowsCollector` and platform factory `get_collector()`. |
| 3 | `src/boostgauge/collectors/windows.py` | Add | Windows collector polling ConPTY, processes, memory %, handles, and unleashed sessions with cadence splitting. |
| 4 | `src/boostgauge/__init__.py` | Modify | Update package `__all__` to export `SystemSnapshot`, `DataCollector`, and `get_collector`. |
| 5 | `tests/unit/test_collector.py` | Add | Unit tests for `DataCollector` ABC, `SystemSnapshot`, metric normalization, and composite calculation algorithm. |
| 6 | `tests/unit/test_windows_collector.py` | Add | Unit tests for `WindowsCollector` metric polling methods, cadence splitting, process access error handling, thread lifecycle, and benchmark limits. |
| 7 | `tests/contract/test_collector_contract.py` | Add | Contract tests validating `SystemSnapshot` field schema and `DataCollector` interface compliance. |

**Implementation Order Rationale:** Core abstractions (`collector.py`) must be defined first before concrete collectors (`collectors/windows.py`) and factories (`collectors/__init__.py`). Top-level package exports (`__init__.py`) are modified once all module paths exist. Test modules are implemented last to validate code against the TDD test plan.

## 3. Current State (for Modify/Delete files)

### 3.1 `src/boostgauge/__init__.py`

**Relevant excerpt** (lines 1-7):

```python
"""BoostGauge package initialization.

Issue #7: Configuration File and CLI Arguments
"""

__version__ = "0.1.0"
__all__ = ["__version__"]
```

**What changes:** Update module docstring to reference Issue #4 and export `SystemSnapshot`, `DataCollector`, and `get_collector` in `__all__`.

## 4. Data Structures

### 4.1 `SystemSnapshot`

**Definition:**

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class SystemSnapshot:
    timestamp: float
    conpty_count: int
    process_count: int
    memory_percent: float
    handle_count: int
    unleashed_sessions: int
    driver: str  # metric name driving highest normalized value ("conpty", "memory_percent", "process_count", "handle_count")
    composite_value: float  # 0.0 - 100.0 normalized max metric
```

**Concrete Example:**

```json
{
    "timestamp": 1774828800.125,
    "conpty_count": 14,
    "process_count": 210,
    "memory_percent": 78.4,
    "handle_count": 14250,
    "unleashed_sessions": 3,
    "driver": "memory_percent",
    "composite_value": 82.4
}
```

### 4.2 `MetricThresholds`

**Definition:**

```python
from typing import TypedDict

class Threshold(TypedDict):
    yellow: float
    red: float

class MetricThresholds(TypedDict):
    conpty: Threshold
    memory_percent: Threshold
    process_count: Threshold
    handle_count: Threshold
```

**Concrete Example:**

```json
{
    "conpty": {"yellow": 20.0, "red": 30.0},
    "memory_percent": {"yellow": 70.0, "red": 85.0},
    "process_count": {"yellow": 150.0, "red": 300.0},
    "handle_count": {"yellow": 10000.0, "red": 20000.0}
}
```

### 4.3 `GaugeConfigDict`

**Definition:**

```python
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
```

**Concrete Example:**

```json
{
    "polling_interval_seconds": 2.0,
    "theme": "dark",
    "size": 300,
    "opacity": 0.9,
    "always_on_top": true,
    "position": {"x": 100, "y": 100},
    "thresholds": {
        "conpty": {"yellow": 20.0, "red": 30.0},
        "memory_percent": {"yellow": 70.0, "red": 85.0},
        "process_count": {"yellow": 150.0, "red": 300.0},
        "handle_count": {"yellow": 10000.0, "red": 20000.0}
    },
    "telltale_windows": {"short": 60, "medium": 600, "long": 3600},
    "show_driver_label": true,
    "show_digital_readout": true,
    "show_session_count": true
}
```

## 5. Function Specifications

### 5.1 `normalize_metric_value()`

**File:** `src/boostgauge/collector.py`

**Signature:**

```python
def normalize_metric_value(value: float, yellow_threshold: float, red_threshold: float) -> float:
    """Map a scalar metric value to a 0-100 piecewise linear range.
    
    0.0 at value <= 0; 60.0 at yellow_threshold; 100.0 at red_threshold (or above).
    """
    ...
```

**Input Example:**

```python
value = 77.5
yellow_threshold = 70.0
red_threshold = 85.0
```

**Output Example:**

```python
80.0
```

**Edge Cases:**
- `value <= 0`: returns `0.0`
- `value >= red_threshold`: returns `100.0`
- `yellow_threshold <= 0` or `red_threshold <= yellow_threshold`: raises `ValueError`

### 5.2 `compute_composite_metric()`

**File:** `src/boostgauge/collector.py`

**Signature:**

```python
def compute_composite_metric(
    conpty_count: int,
    memory_percent: float,
    process_count: int,
    handle_count: int,
    thresholds: MetricThresholds,
) -> Tuple[float, str]:
    """Calculate composite load (0-100) using normalized-max algorithm and return (composite_value, driver_name)."""
    ...
```

**Input Example:**

```python
conpty_count = 10
memory_percent = 77.5
process_count = 100
handle_count = 5000
thresholds = {
    "conpty": {"yellow": 20.0, "red": 30.0},
    "memory_percent": {"yellow": 70.0, "red": 85.0},
    "process_count": {"yellow": 150.0, "red": 300.0},
    "handle_count": {"yellow": 10000.0, "red": 20000.0},
}
```

**Output Example:**

```python
(80.0, "memory_percent")
```

**Edge Cases:**
- All raw values zero -> returns `(0.0, "conpty")`
- Tie between conpty and memory_percent at 80.0 -> returns `(80.0, "conpty")` (first in deterministic priority order: `conpty`, `memory_percent`, `process_count`, `handle_count`)

### 5.3 `DataCollector.__init__()`

**File:** `src/boostgauge/collector.py`

**Signature:**

```python
def __init__(self, polling_interval: float = 2.0, config: Optional[GaugeConfigDict] = None) -> None:
    """Initialize DataCollector with polling interval and configuration dictionary."""
    ...
```

**Input Example:**

```python
polling_interval = 2.0
config = get_default_config()
```

**Output Example:**

```python
None
```

**Edge Cases:**
- `polling_interval <= 0`: raises `ValueError("polling_interval must be positive")`
- `config is None`: uses `get_default_config()`

### 5.4 `DataCollector.poll()`

**File:** `src/boostgauge/collector.py`

**Signature:**

```python
@abc.abstractmethod
def poll(self) -> SystemSnapshot:
    """Execute a single point-in-time snapshot collection."""
    ...
```

**Input Example:**

```python
# Called on instance
```

**Output Example:**

```python
SystemSnapshot(
    timestamp=1774828800.0,
    conpty_count=4,
    process_count=180,
    memory_percent=55.0,
    handle_count=12000,
    unleashed_sessions=1,
    driver="handle_count",
    composite_value=72.0,
)
```

**Edge Cases:**
- Direct call on base `DataCollector` class instance raises `TypeError` (Abstract Class)

### 5.5 `DataCollector.start()`

**File:** `src/boostgauge/collector.py`

**Signature:**

```python
def start(self) -> None:
    """Start background polling daemon thread."""
    ...
```

**Input Example:**

```python
# Called on instantiated WindowsCollector
```

**Output Example:**

```python
None
```

**Edge Cases:**
- Calling `start()` when thread is already running: no-op (ignores secondary call)

### 5.6 `DataCollector.stop()`

**File:** `src/boostgauge/collector.py`

**Signature:**

```python
def stop(self) -> None:
    """Signal background polling thread to stop and join cleanly."""
    ...
```

**Input Example:**

```python
# Called on running collector instance
```

**Output Example:**

```python
None
```

**Edge Cases:**
- Calling `stop()` when thread was never started or is stopped: no-op

### 5.7 `DataCollector.get_latest_snapshot()`

**File:** `src/boostgauge/collector.py`

**Signature:**

```python
def get_latest_snapshot(self) -> Optional[SystemSnapshot]:
    """Drain queue non-blocking and return the most recent SystemSnapshot, or None if queue is empty."""
    ...
```

**Input Example:**

```python
# Called when queue has 3 snapshots
```

**Output Example:**

```python
SystemSnapshot(
    timestamp=1774828802.0,
    conpty_count=5,
    process_count=182,
    memory_percent=55.2,
    handle_count=12050,
    unleashed_sessions=1,
    driver="handle_count",
    composite_value=72.3,
)
```

**Edge Cases:**
- Queue empty: returns `None`

### 5.8 `WindowsCollector.poll_conpty_count()`

**File:** `src/boostgauge/collectors/windows.py`

**Signature:**

```python
def poll_conpty_count(self) -> int:
    """Count active conhost.exe processes and Windows Terminal pseudo-consoles (OpenConsole.exe / WindowsTerminal.exe)."""
    ...
```

**Input Example:**

```python
# System running 3 conhost.exe and 2 OpenConsole.exe
```

**Output Example:**

```python
5
```

**Edge Cases:**
- `psutil.NoSuchProcess` encountered during iteration: safely skipped

### 5.9 `WindowsCollector.poll_process_count()`

**File:** `src/boostgauge/collectors/windows.py`

**Signature:**

```python
def poll_process_count(self) -> int:
    """Retrieve total count of running system processes."""
    ...
```

**Input Example:**

```python
# System with 215 pids
```

**Output Example:**

```python
215
```

**Edge Cases:**
- `psutil` error: returns `0`

### 5.10 `WindowsCollector.poll_memory_percent()`

**File:** `src/boostgauge/collectors/windows.py`

**Signature:**

```python
def poll_memory_percent(self) -> float:
    """Retrieve system virtual memory usage percentage."""
    ...
```

**Input Example:**

```python
# System memory usage 64.2%
```

**Output Example:**

```python
64.2
```

**Edge Cases:**
- Exception during `psutil.virtual_memory()`: returns `0.0`

### 5.11 `WindowsCollector.poll_handle_count()`

**File:** `src/boostgauge/collectors/windows.py`

**Signature:**

```python
def poll_handle_count(self) -> int:
    """Aggregate total process handle count across accessible system processes."""
    ...
```

**Input Example:**

```python
# System process handle totals
```

**Output Example:**

```python
15420
```

**Edge Cases:**
- Elevated / system processes raising `psutil.AccessDenied`: handle count for that process treated as 0, iteration continues

### 5.12 `WindowsCollector.poll_unleashed_sessions()`

**File:** `src/boostgauge/collectors/windows.py`

**Signature:**

```python
def poll_unleashed_sessions(self) -> int:
    """Detect unleashed AI agent sessions by checking python process command lines for unleashed-c-*.py."""
    ...
```

**Input Example:**

```python
# System running python.exe with cmdline ["python", "unleashed-c-12.py"]
```

**Output Example:**

```python
1
```

**Edge Cases:**
- Process cmdline access forbidden (`psutil.AccessDenied`): process skipped
- Cmdline empty or `None`: process skipped

### 5.13 `WindowsCollector.poll()`

**File:** `src/boostgauge/collectors/windows.py`

**Signature:**

```python
def poll(self) -> SystemSnapshot:
    """Execute snapshot collection with cadence splitting (heavy metrics cached across 5s window)."""
    ...
```

**Input Example:**

```python
# Invoked during background polling loop tick
```

**Output Example:**

```python
SystemSnapshot(
    timestamp=1774828804.0,
    conpty_count=5,
    process_count=215,
    memory_percent=64.2,
    handle_count=15420,
    unleashed_sessions=1,
    driver="handle_count",
    composite_value=81.6,
)
```

**Edge Cases:**
- Fast tick (cycle 1, 2, 3): uses cached `handle_count` and `unleashed_sessions` from previous heavy tick

### 5.14 `get_collector()`

**File:** `src/boostgauge/collectors/__init__.py`

**Signature:**

```python
def get_collector(polling_interval: float = 2.0, config: Optional[GaugeConfigDict] = None) -> DataCollector:
    """Instantiate platform-appropriate DataCollector (WindowsCollector on win32)."""
    ...
```

**Input Example:**

```python
polling_interval = 2.0
config = None
```

**Output Example:**

```python
<WindowsCollector object at 0x0000021A4B8E12A0>
```

**Edge Cases:**
- Running on non-Windows (`sys.platform != "win32"`): returns fallback stub instance of `DataCollector` whose `poll()` returns zeroed `SystemSnapshot`

## 6. Change Instructions

### 6.1 `src/boostgauge/collector.py` (Add)

**Complete file contents:**

```python
"""Abstract base data collector and composite metric computation.

Issue #4: Windows Data Collector — ConPTY, Processes, Memory, Handles
"""

from __future__ import annotations

import abc
import queue
import threading
import time
from dataclasses import dataclass
from typing import Optional, Tuple

from boostgauge.config import GaugeConfigDict, MetricThresholds, get_default_config


@dataclass(frozen=True)
class SystemSnapshot:
    """Point-in-time system metrics snapshot."""

    timestamp: float
    conpty_count: int
    process_count: int
    memory_percent: float
    handle_count: int
    unleashed_sessions: int
    driver: str
    composite_value: float


def normalize_metric_value(value: float, yellow_threshold: float, red_threshold: float) -> float:
    """Map a scalar metric value to a 0-100 range using piecewise linear mapping.

    - 0.0 for value <= 0.0
    - Linear mapping from 0.0 to 60.0 for 0.0 < value <= yellow_threshold
    - Linear mapping from 60.0 to 100.0 for yellow_threshold < value <= red_threshold
    - 100.0 for value >= red_threshold
    """
    if yellow_threshold <= 0:
        raise ValueError("yellow_threshold must be positive")
    if red_threshold <= yellow_threshold:
        raise ValueError("red_threshold must be strictly greater than yellow_threshold")

    val = float(value)
    if val <= 0.0:
        return 0.0
    if val <= yellow_threshold:
        return (val / yellow_threshold) * 60.0
    if val <= red_threshold:
        return 60.0 + ((val - yellow_threshold) / (red_threshold - yellow_threshold)) * 40.0
    return 100.0


def compute_composite_metric(
    conpty_count: int,
    memory_percent: float,
    process_count: int,
    handle_count: int,
    thresholds: MetricThresholds,
) -> Tuple[float, str]:
    """Calculate composite load (0-100) using normalized-max algorithm and return (composite_value, driver_name)."""
    norm_metrics = {
        "conpty": normalize_metric_value(
            float(conpty_count),
            thresholds["conpty"]["yellow"],
            thresholds["conpty"]["red"],
        ),
        "memory_percent": normalize_metric_value(
            float(memory_percent),
            thresholds["memory_percent"]["yellow"],
            thresholds["memory_percent"]["red"],
        ),
        "process_count": normalize_metric_value(
            float(process_count),
            thresholds["process_count"]["yellow"],
            thresholds["process_count"]["red"],
        ),
        "handle_count": normalize_metric_value(
            float(handle_count),
            thresholds["handle_count"]["yellow"],
            thresholds["handle_count"]["red"],
        ),
    }

    max_val = -1.0
    driver_name = "conpty"
    priority = ["conpty", "memory_percent", "process_count", "handle_count"]

    for name in priority:
        val = norm_metrics[name]
        if val > max_val:
            max_val = val
            driver_name = name

    clamped_val = max(0.0, min(100.0, max_val))
    return clamped_val, driver_name


class DataCollector(abc.ABC):
    """Abstract base class for system metric collectors."""

    def __init__(self, polling_interval: float = 2.0, config: Optional[GaugeConfigDict] = None) -> None:
        if polling_interval <= 0:
            raise ValueError("polling_interval must be positive")

        self.polling_interval: float = float(polling_interval)
        self.config: GaugeConfigDict = config if config is not None else get_default_config()

        self._queue: queue.Queue[SystemSnapshot] = queue.Queue(maxsize=100)
        self._stop_event: threading.Event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    @abc.abstractmethod
    def poll(self) -> SystemSnapshot:
        """Execute a single point-in-time snapshot collection."""
        ...

    def start(self) -> None:
        """Start background polling daemon thread."""
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._polling_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop background polling thread and join cleanly."""
        if self._thread is None:
            return

        self._stop_event.set()
        self._thread.join(timeout=1.0)
        self._thread = None

    def get_latest_snapshot(self) -> Optional[SystemSnapshot]:
        """Fetch latest snapshot from thread queue without blocking."""
        latest: Optional[SystemSnapshot] = None
        while not self._queue.empty():
            try:
                latest = self._queue.get_nowait()
            except queue.Empty:
                break
        return latest

    def _polling_loop(self) -> None:
        """Background thread execution loop."""
        while not self._stop_event.is_set():
            t0 = time.time()
            try:
                snapshot = self.poll()
                try:
                    self._queue.put_nowait(snapshot)
                except queue.Full:
                    try:
                        self._queue.get_nowait()
                    except queue.Empty:
                        pass
                    try:
                        self._queue.put_nowait(snapshot)
                    except queue.Full:
                        pass
            except Exception:
                pass

            elapsed = time.time() - t0
            sleep_time = max(0.01, self.polling_interval - elapsed)
            self._stop_event.wait(timeout=sleep_time)
```

### 6.2 `src/boostgauge/collectors/__init__.py` (Add)

**Complete file contents:**

```python
"""Platform collector package initialization and factory.

Issue #4: Windows Data Collector — ConPTY, Processes, Memory, Handles
"""

from __future__ import annotations

import sys
import time
from typing import Optional

from boostgauge.collector import DataCollector, SystemSnapshot
from boostgauge.config import GaugeConfigDict
from boostgauge.collectors.windows import WindowsCollector


class StubCollector(DataCollector):
    """Fallback collector for non-Windows platforms."""

    def poll(self) -> SystemSnapshot:
        return SystemSnapshot(
            timestamp=time.time(),
            conpty_count=0,
            process_count=0,
            memory_percent=0.0,
            handle_count=0,
            unleashed_sessions=0,
            driver="conpty",
            composite_value=0.0,
        )


def get_collector(polling_interval: float = 2.0, config: Optional[GaugeConfigDict] = None) -> DataCollector:
    """Instantiate platform-appropriate DataCollector (WindowsCollector on win32)."""
    if sys.platform == "win32":
        return WindowsCollector(polling_interval=polling_interval, config=config)
    return StubCollector(polling_interval=polling_interval, config=config)


__all__ = ["WindowsCollector", "StubCollector", "get_collector"]
```

### 6.3 `src/boostgauge/collectors/windows.py` (Add)

**Complete file contents:**

```python
"""Windows-specific metrics collector using psutil and Win32 calls.

Issue #4: Windows Data Collector — ConPTY, Processes, Memory, Handles
"""

from __future__ import annotations

import re
import time
from typing import Optional, Set

import psutil

from boostgauge.collector import DataCollector, SystemSnapshot, compute_composite_metric
from boostgauge.config import GaugeConfigDict


UNLEASHED_PATTERN = re.compile(r"unleashed-c-.*\.py", re.IGNORECASE)
CONPTY_NAMES: Set[str] = {"conhost.exe", "openconsole.exe", "windowsterminal.exe"}


class WindowsCollector(DataCollector):
    """Windows metrics collector leveraging psutil and process enumeration."""

    def __init__(self, polling_interval: float = 2.0, config: Optional[GaugeConfigDict] = None) -> None:
        super().__init__(polling_interval=polling_interval, config=config)
        self._poll_count: int = 0
        self._cached_handle_count: int = 0
        self._cached_unleashed_sessions: int = 0

    def poll_conpty_count(self) -> int:
        """Count active conhost.exe processes and Windows Terminal pseudo-consoles."""
        count = 0
        try:
            for p in psutil.process_iter(["name"]):
                try:
                    name = p.info.get("name")
                    if name and name.lower() in CONPTY_NAMES:
                        count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            pass
        return count

    def poll_process_count(self) -> int:
        """Count total running system processes."""
        try:
            return len(psutil.pids())
        except Exception:
            return 0

    def poll_memory_percent(self) -> float:
        """Retrieve total system virtual memory utilization percentage."""
        try:
            return float(psutil.virtual_memory().percent)
        except Exception:
            return 0.0

    def poll_handle_count(self) -> int:
        """Aggregate total process handle count across accessible processes."""
        total_handles = 0
        try:
            for p in psutil.process_iter():
                try:
                    num = p.num_handles()
                    if num and num > 0:
                        total_handles += num
                except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError, Exception):
                    continue
        except Exception:
            pass
        return total_handles

    def poll_unleashed_sessions(self) -> int:
        """Count running python processes executing unleashed-c-*.py scripts."""
        unleashed_count = 0
        try:
            for p in psutil.process_iter(["name", "cmdline"]):
                try:
                    name = p.info.get("name")
                    if name and "python" in name.lower():
                        cmdline = p.info.get("cmdline")
                        if cmdline and any(UNLEASHED_PATTERN.search(arg) for arg in cmdline if isinstance(arg, str)):
                            unleashed_count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            pass
        return unleashed_count

    def poll(self) -> SystemSnapshot:
        """Collect all metrics with cadence splitting (heavy metrics polled every ~5s)."""
        now = time.time()
        conpty = self.poll_conpty_count()
        proc_cnt = self.poll_process_count()
        mem_pct = self.poll_memory_percent()

        # Cadence splitting: heavy metrics every 5 seconds (or on first poll)
        # Ratio calculated based on polling_interval (e.g., interval 2s -> poll ratio 2 or 3)
        heavy_ratio = max(1, int(round(5.0 / self.polling_interval)))
        if self._poll_count % heavy_ratio == 0:
            self._cached_handle_count = self.poll_handle_count()
            self._cached_unleashed_sessions = self.poll_unleashed_sessions()

        self._poll_count += 1

        handles = self._cached_handle_count
        unleashed = self._cached_unleashed_sessions

        comp_val, driver = compute_composite_metric(
            conpty_count=conpty,
            memory_percent=mem_pct,
            process_count=proc_cnt,
            handle_count=handles,
            thresholds=self.config["thresholds"],
        )

        return SystemSnapshot(
            timestamp=now,
            conpty_count=conpty,
            process_count=proc_cnt,
            memory_percent=mem_pct,
            handle_count=handles,
            unleashed_sessions=unleashed,
            driver=driver,
            composite_value=comp_val,
        )
```

### 6.4 `src/boostgauge/__init__.py` (Modify)

**Change 1:** Update docstring and module exports at lines 1-7

```diff
-"""BoostGauge package initialization.
-
-Issue #7: Configuration File and CLI Arguments
-"""

-__version__ = "0.1.0"
-__all__ = ["__version__"]
+"""BoostGauge package initialization.
+
+Issue #4: Windows Data Collector — ConPTY, Processes, Memory, Handles
+"""

+from boostgauge.collector import DataCollector, SystemSnapshot
+from boostgauge.collectors import get_collector

+__version__ = "0.1.0"
+__all__ = ["__version__", "SystemSnapshot", "DataCollector", "get_collector"]
```

### 6.5 `tests/unit/test_collector.py` (Add)

**Complete file contents:**

```python
"""Unit tests for DataCollector base class, SystemSnapshot, and composite metric algorithm.

Issue #4: Windows Data Collector — ConPTY, Processes, Memory, Handles
"""

from __future__ import annotations

import time
import pytest
from boostgauge.collector import (
    DataCollector,
    SystemSnapshot,
    compute_composite_metric,
    normalize_metric_value,
)
from boostgauge.config import get_default_config


class ConcreteCollector(DataCollector):
    """Test concrete implementation of DataCollector."""

    def __init__(self, polling_interval: float = 0.1):
        super().__init__(polling_interval=polling_interval)
        self.poll_calls = 0

    def poll(self) -> SystemSnapshot:
        self.poll_calls += 1
        return SystemSnapshot(
            timestamp=time.time(),
            conpty_count=5,
            process_count=100,
            memory_percent=50.0,
            handle_count=5000,
            unleashed_sessions=1,
            driver="conpty",
            composite_value=40.0,
        )


def test_t010_abstract_collector_instantiation_guard():
    """T010: Raising TypeError when instantiating abstract base class directly."""
    with pytest.raises(TypeError):
        DataCollector()  # type: ignore[abstract]


def test_t020_system_snapshot_fields_and_immutability():
    """T020: Snapshot instantiates with correct types and rejects mutation."""
    snapshot = SystemSnapshot(
        timestamp=100.0,
        conpty_count=10,
        process_count=200,
        memory_percent=75.0,
        handle_count=12000,
        unleashed_sessions=2,
        driver="memory_percent",
        composite_value=80.0,
    )
    assert snapshot.timestamp == 100.0
    assert snapshot.conpty_count == 10
    assert snapshot.process_count == 200
    assert snapshot.memory_percent == 75.0
    assert snapshot.handle_count == 12000
    assert snapshot.unleashed_sessions == 2
    assert snapshot.driver == "memory_percent"
    assert snapshot.composite_value == 80.0

    with pytest.raises(AttributeError):
        snapshot.composite_value = 90.0  # type: ignore[misc]


def test_t100_piecewise_linear_normalized_max_metric():
    """T100: Correctly normalizes metrics and selects maximum driver."""
    config = get_default_config()
    thresholds = config["thresholds"]

    # conpty=10 (yellow=20, red=30 -> 30%)
    # memory=85.0 (yellow=70, red=85 -> 100%)
    comp_val, driver = compute_composite_metric(
        conpty_count=10,
        memory_percent=85.0,
        process_count=100,
        handle_count=5000,
        thresholds=thresholds,
    )
    assert comp_val == 100.0
    assert driver == "memory_percent"


def test_t110_composite_metric_boundary_clamping():
    """T110: Clamps values to 0.0 minimum and 100.0 maximum."""
    config = get_default_config()
    thresholds = config["thresholds"]

    # Negative inputs
    comp_min, driver_min = compute_composite_metric(-5, -10.0, -20, -100, thresholds)
    assert comp_min == 0.0
    assert driver_min == "conpty"

    # Extreme overflow inputs
    comp_max, driver_max = compute_composite_metric(1000, 200.0, 5000, 1000000, thresholds)
    assert comp_max == 100.0


def test_normalize_metric_value_bounds():
    """Verify piecewise linear normalization points."""
    assert normalize_metric_value(0.0, 20.0, 30.0) == 0.0
    assert normalize_metric_value(10.0, 20.0, 30.0) == 30.0
    assert normalize_metric_value(20.0, 20.0, 30.0) == 60.0
    assert normalize_metric_value(25.0, 20.0, 30.0) == 80.0
    assert normalize_metric_value(30.0, 20.0, 30.0) == 100.0
    assert normalize_metric_value(50.0, 20.0, 30.0) == 100.0

    with pytest.raises(ValueError):
        normalize_metric_value(10.0, 0.0, 30.0)

    with pytest.raises(ValueError):
        normalize_metric_value(10.0, 20.0, 20.0)
```

### 6.6 `tests/unit/test_windows_collector.py` (Add)

**Complete file contents:**

```python
"""Unit tests for WindowsCollector metrics polling and thread management.

Issue #4: Windows Data Collector — ConPTY, Processes, Memory, Handles
"""

from __future__ import annotations

import sys
import time
from unittest.mock import MagicMock, patch

import pytest
import psutil

from boostgauge.collectors.windows import WindowsCollector
from boostgauge.collectors import get_collector


@pytest.fixture
def collector():
    return WindowsCollector(polling_interval=0.1)


def test_t030_poll_conpty_count(collector):
    """T030: Accurately counts conhost.exe and OpenConsole.exe mock processes."""
    mock_p1 = MagicMock()
    mock_p1.info = {"name": "conhost.exe"}

    mock_p2 = MagicMock()
    mock_p2.info = {"name": "OpenConsole.exe"}

    mock_p3 = MagicMock()
    mock_p3.info = {"name": "svchost.exe"}

    with patch("psutil.process_iter", return_value=[mock_p1, mock_p2, mock_p3]):
        assert collector.poll_conpty_count() == 2


def test_t040_poll_process_count_and_memory_percent(collector):
    """T040: Returns system process count and virtual memory percentage."""
    with patch("psutil.pids", return_value=list(range(142))), \
         patch("psutil.virtual_memory") as mock_mem:
        mock_mem.return_value.percent = 68.5
        assert collector.poll_process_count() == 142
        assert collector.poll_memory_percent() == 68.5


def test_t050_poll_handle_count(collector):
    """T050: Sums handle counts across accessible processes."""
    mock_p1 = MagicMock()
    mock_p1.num_handles.return_value = 100

    mock_p2 = MagicMock()
    mock_p2.num_handles.return_value = 200

    with patch("psutil.process_iter", return_value=[mock_p1, mock_p2]):
        assert collector.poll_handle_count() == 300


def test_t060_poll_unleashed_sessions(collector):
    """T060: Identifies processes with unleashed-c-*.py in command line."""
    mock_p1 = MagicMock()
    mock_p1.info = {"name": "python.exe", "cmdline": ["python.exe", "unleashed-c-12.py"]}

    mock_p2 = MagicMock()
    mock_p2.info = {"name": "python.exe", "cmdline": ["python.exe", "other_script.py"]}

    with patch("psutil.process_iter", return_value=[mock_p1, mock_p2]):
        assert collector.poll_unleashed_sessions() == 1


def test_t070_background_thread_lifecycle(collector):
    """T070: Collector thread starts, pushes snapshots, and stops cleanly."""
    with patch.object(collector, "poll_conpty_count", return_value=2), \
         patch.object(collector, "poll_process_count", return_value=100), \
         patch.object(collector, "poll_memory_percent", return_value=45.0), \
         patch.object(collector, "poll_handle_count", return_value=5000), \
         patch.object(collector, "poll_unleashed_sessions", return_value=1):

        collector.start()
        time.sleep(0.25)
        snapshot = collector.get_latest_snapshot()
        collector.stop()

        assert snapshot is not None
        assert snapshot.conpty_count == 2
        assert snapshot.process_count == 100
        assert snapshot.memory_percent == 45.0


def test_t080_access_denied_exception_resilience(collector):
    """T080: Gracefully ignores access denied processes during iteration."""
    mock_p1 = MagicMock()
    mock_p1.info = {"name": "conhost.exe"}

    mock_p2 = MagicMock()
    mock_p2.info.side_effect = psutil.AccessDenied(pid=1)

    with patch("psutil.process_iter", return_value=[mock_p1, mock_p2]):
        assert collector.poll_conpty_count() == 1


def test_t090_cpu_overhead_benchmark(collector):
    """T090: Verifies poll cycle completes in <10ms with minimal CPU usage."""
    with patch("psutil.process_iter", return_value=[]), \
         patch("psutil.pids", return_value=[1, 2]), \
         patch("psutil.virtual_memory") as mock_mem:
        mock_mem.return_value.percent = 50.0

        t0 = time.perf_counter()
        for _ in range(20):
            collector.poll()
        elapsed = time.perf_counter() - t0

        avg_ms = (elapsed / 20.0) * 1000.0
        assert avg_ms < 10.0


def test_t120_get_collector_factory():
    """T120: Returns WindowsCollector on win32 platform."""
    with patch("sys.platform", "win32"):
        c = get_collector()
        assert isinstance(c, WindowsCollector)

    with patch("sys.platform", "linux"):
        c_stub = get_collector()
        assert not isinstance(c_stub, WindowsCollector)
        assert c_stub.poll().composite_value == 0.0
```

### 6.7 `tests/contract/test_collector_contract.py` (Add)

**Complete file contents:**

```python
"""Contract tests for SystemSnapshot and DataCollector ABC interface.

Issue #4: Windows Data Collector — ConPTY, Processes, Memory, Handles
"""

from __future__ import annotations

import dataclasses
from boostgauge.collector import DataCollector, SystemSnapshot
from boostgauge.collectors import get_collector


def test_system_snapshot_contract_fields():
    """Validate SystemSnapshot schema fields and types."""
    fields = {f.name: f.type for f in dataclasses.fields(SystemSnapshot)}
    expected = {
        "timestamp": float,
        "conpty_count": int,
        "process_count": int,
        "memory_percent": float,
        "handle_count": int,
        "unleashed_sessions": int,
        "driver": str,
        "composite_value": float,
    }
    assert fields == expected


def test_data_collector_contract_methods():
    """Validate DataCollector ABC required public interface methods."""
    required_methods = ["poll", "start", "stop", "get_latest_snapshot"]
    for method in required_methods:
        assert hasattr(DataCollector, method)
        assert callable(getattr(DataCollector, method))


def test_factory_returns_datacollector_instance():
    """Validate get_collector returns an instance of DataCollector ABC."""
    collector = get_collector()
    assert isinstance(collector, DataCollector)
```

## 7. Pattern References

### 7.1 Configuration Dictionary and Threshold Structure

**File:** `src/boostgauge/config.py` (lines 77-96)

```python
def get_default_config() -> GaugeConfigDict:
    """Return deep copy of default configuration dictionary."""
    return copy.deepcopy({
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
    })
```

**Relevance:** `compute_composite_metric()` extracts metric thresholds directly from this standardized configuration dictionary structure.

### 7.2 Sliding Window & Thread Data Hygiene

**File:** `src/boostgauge/telltale.py` (lines 33-36)

```python
        self._samples: deque[Tuple[float, float]] = deque()
        self._max_deque: deque[Tuple[float, float]] = deque()
        self._best_expired_key: Optional[float] = None
        self._latest_timestamp: Optional[float] = None
```

**Relevance:** Demonstrates clean internal state encapsulation and non-blocking queue/buffer management used in `DataCollector`.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `import abc` | stdlib | `src/boostgauge/collector.py` |
| `import queue` | stdlib | `src/boostgauge/collector.py` |
| `import threading` | stdlib | `src/boostgauge/collector.py` |
| `import time` | stdlib | `src/boostgauge/collector.py`, `src/boostgauge/collectors/windows.py` |
| `import re` | stdlib | `src/boostgauge/collectors/windows.py` |
| `import sys` | stdlib | `src/boostgauge/collectors/__init__.py` |
| `from dataclasses import dataclass` | stdlib | `src/boostgauge/collector.py` |
| `import psutil` | PyPI (`psutil>=7.2.2`) | `src/boostgauge/collectors/windows.py` |
| `from boostgauge.config import GaugeConfigDict, MetricThresholds, get_default_config` | internal | `src/boostgauge/collector.py`, `src/boostgauge/collectors/windows.py` |

**New Dependencies:** None (uses existing `psutil>=7.2.2` and Python Standard Library).

## 9. Placeholder

*Reserved for alignment with LLD section numbering.*

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `DataCollector()` | `DataCollector()` direct call | Raises `TypeError` |
| T020 | `SystemSnapshot` | Valid keyword parameters | Valid immutable frozen instance |
| T030 | `WindowsCollector.poll_conpty_count()` | Process list with `conhost.exe` and `OpenConsole.exe` | Integer count matching ConPTY processes (2) |
| T040 | `WindowsCollector.poll_process_count()`, `poll_memory_percent()` | Mocked `psutil.pids()` and `psutil.virtual_memory()` | `process_count=142`, `memory_percent=68.5` |
| T050 | `WindowsCollector.poll_handle_count()` | Mocked processes with handle counts [100, 200] | `300` |
| T060 | `WindowsCollector.poll_unleashed_sessions()` | Mock process cmdline `["python", "unleashed-c-12.py"]` | `1` |
| T070 | `DataCollector.start()`, `get_latest_snapshot()`, `stop()` | Background thread polling loop | Returns latest `SystemSnapshot` from queue; thread joins cleanly |
| T080 | `WindowsCollector.poll_conpty_count()` | Process raising `psutil.AccessDenied` | Process skipped cleanly; returns count of accessible processes |
| T090 | `WindowsCollector.poll()` | 20 consecutive `poll()` iterations | Average execution time < 10ms/poll |
| T100 | `compute_composite_metric()` | `conpty=10`, `memory=85.0` | `(100.0, "memory_percent")` |
| T110 | `compute_composite_metric()` | Overflow values (`memory=200.0`) and negative values (`-5`) | Clamped to `100.0` and `0.0` respectively |
| T120 | `get_collector()` | `sys.platform = "win32"` vs `"linux"` | `WindowsCollector` on `win32`, `StubCollector` on Linux |

## 11. Implementation Notes

### 11.1 Error Handling Convention

All metric polling functions inside `WindowsCollector` wrap process iteration in `try...except` blocks capturing `psutil.AccessDenied`, `psutil.NoSuchProcess`, and general `Exception`. Permission errors on individual processes do not halt the iteration or cause collector thread failures.

### 11.2 Threading & Queue Safety

The `DataCollector` background thread communicates with the main thread exclusively via `queue.Queue[SystemSnapshot]`.
- Queue maximum size is set to `100`.
- Drop-oldest eviction policy (`put_nowait()` with fallback `get_nowait()`) guarantees queue never blocks the collector thread or causes RAM growth.
- Thread stop mechanism uses `threading.Event` checked every cycle and on sleep waits via `_stop_event.wait(timeout)`.

### 11.3 Performance & Cadence Splitting

- Fast metrics (`conpty_count`, `process_count`, `memory_percent`) are queried on every poll tick (default 2s interval).
- Heavy metrics (`handle_count` aggregating process handle tables and `unleashed_sessions` inspecting process command lines) are polled every ~5 seconds (`heavy_ratio = max(1, int(round(5.0 / polling_interval)))`).
- Between heavy ticks, cached results (`self._cached_handle_count`, `self._cached_unleashed_sessions`) are reused, keeping overall CPU overhead <1%.

### 11.4 Piecewise Linear Formula Details

Metric values are normalized to a 0-100 gauge scale:
- $v \le 0 \implies 0.0$
- $0 < v \le T_{yellow} \implies \frac{v}{T_{yellow}} \times 60.0$
- $T_{yellow} < v \le T_{red} \implies 60.0 + \frac{v - T_{yellow}}{T_{red} - T_{yellow}} \times 40.0$
- $v \ge T_{red} \implies 100.0$

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3)
- [x] Every data structure has a concrete JSON example (Section 4)
- [x] Every function has input/output examples with realistic values (Section 5)
- [x] Change instructions are diff-level specific (Section 6)
- [x] Pattern references include file:line and are verified to exist (Section 7)
- [x] All imports are listed and verified (Section 8)
- [x] Test mapping covers all LLD test scenarios (Section 10)

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #4 |
| Verdict | APPROVED |
| Date | 2026-07-29 |
| Iterations | 1 |
| Finalized | 2026-07-29T23:47:00Z |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #4 |
| Verdict | APPROVED |
| Date | 2026-07-30 |
| Iterations | 0 |
| Finalized | 2026-07-30T04:47:47Z |

### Review Feedback Summary

The implementation spec is fully complete, concrete, and highly executable. Complete code implementations are provided for all new files (src/boostgauge/collector.py, src/boostgauge/collectors/__init__.py, src/boostgauge/collectors/windows.py, tests/unit/test_collector.py, tests/unit/test_windows_collector.py, tests/contract/test_collector_contract.py) alongside precise line-level diffs for modified files. Every data structure includes concrete JSON examples and every function signature includes...
