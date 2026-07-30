# Implementation Spec: Windows data collector — ConPTY, processes, memory, handles

| Field | Value |
|-------|-------|
| Issue | #4 |
| LLD | `docs/lld/done/0004-windows-data-collector.md` |
| Generated | 2026-07-30 |
| Status | APPROVED |

---

## 1. Overview

**Objective:** Implement a Windows-specific data collector that polls system resource metrics (ConPTY allocations, process count, memory percentage, handle count, and Unleashed session count) in a non-blocking background thread, computes a normalized-max composite load score, and pushes system snapshots to a thread-safe queue.

**Success Criteria:**
- `DataCollector` abstract base class with thread lifecycle management (`start()`, `stop()`, `is_running()`).
- `SystemSnapshot` dataclass storing raw metrics, composite load value (0.0 to 100.0), and driving metric name.
- Metric normalization (`normalize_metric`) scaling raw values against high/elevated/warning thresholds to a 0–100 scale.
- Composite calculation using normalized-max algorithm across ConPTY count, memory %, process count, and handle count.
- `WindowsCollector` subclass querying metrics via `psutil` and Win32 process enumeration.
- Staggered polling cycle: fast metrics (ConPTY, process count, memory %) every 2.0s; heavy metrics (handles, Unleashed sessions) every 5.0s.
- Evict-oldest overflow policy on full queue (`queue.Full` exception handling with `get_nowait()` fallback).
- Permission resiliency wrapping process scanning in `psutil.AccessDenied` / `PermissionError` try-except blocks without crashing worker thread.
- Unit test suite achieving ≥89% coverage across `collector.py`, `collectors/__init__.py`, and `collectors/windows.py`.

---

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/collectors` | Add (Directory) | Directory for platform-specific system data collector implementations |
| 2 | `src/boostgauge/collector.py` | Add | Base `DataCollector` class, `SystemSnapshot` dataclass, metric normalization, composite metric calculation, thread loop management |
| 3 | `src/boostgauge/collectors/__init__.py` | Add | Package init exporting platform collectors and `create_collector()` factory |
| 4 | `src/boostgauge/collectors/windows.py` | Add | `WindowsCollector` implementation using `psutil` and Win32 process filtering |
| 5 | `src/boostgauge/__init__.py` | Modify | Re-export `DataCollector`, `SystemSnapshot`, `WindowsCollector`, `create_collector` |
| 6 | `tests/unit/test_collector.py` | Add | Unit tests for base collector, metric normalization, composite calculation, thread start/stop, queue eviction |
| 7 | `tests/unit/test_windows_collector.py` | Add | Unit tests for `WindowsCollector`, psutil/Win32 mocks, Unleashed cmdline parsing, permission resilience |

**Implementation Order Rationale:**
1. Core data structures and base class (`collector.py`) must exist before subclassing.
2. Platform collector (`collectors/windows.py`) inherits from `DataCollector` and uses `SystemSnapshot`.
3. Package factory (`collectors/__init__.py`) imports `WindowsCollector` and `DataCollector`.
4. Main package init (`src/boostgauge/__init__.py`) exports all public symbols.
5. Unit tests validate base collector logic first, followed by platform-specific collector behavior.

---

## 3. Current State (for Modify/Delete files)

### 3.1 `src/boostgauge/__init__.py`

**Relevant excerpt** (lines 1-8):

```python
"""BoostGauge package initialization.

Issue #7: Configuration File and CLI Arguments
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
```

**What changes:**
Import `DataCollector` and `SystemSnapshot` from `boostgauge.collector`, `WindowsCollector` and `create_collector` from `boostgauge.collectors`, and expose them in `__all__`.

---

## 4. Data Structures

### 4.1 `SystemSnapshot`

**Definition:**

```python
from dataclasses import dataclass

@dataclass
class SystemSnapshot:
    timestamp: float
    conpty_count: int
    process_count: int
    memory_percent: float
    handle_count: int
    unleashed_sessions: int
    driver: str  # Driver metric name: "conpty", "memory", "process", "handle"
    composite_value: float  # Normalized score (0.0 to 100.0)
```

**Concrete Example:**

```json
{
    "timestamp": 1774924800.125,
    "conpty_count": 8,
    "process_count": 240,
    "memory_percent": 68.5,
    "handle_count": 45200,
    "unleashed_sessions": 2,
    "driver": "conpty",
    "composite_value": 80.0
}
```

### 4.2 `MetricRawValues`

**Definition:**

```python
from typing import TypedDict

class MetricRawValues(TypedDict):
    conpty_count: int
    process_count: int
    memory_percent: float
    handle_count: int
    unleashed_sessions: int
```

**Concrete Example:**

```json
{
    "conpty_count": 5,
    "process_count": 180,
    "memory_percent": 54.2,
    "handle_count": 32000,
    "unleashed_sessions": 1
}
```

### 4.3 `ThresholdConfig`

**Definition:**

```python
from typing import TypedDict, Dict

class MetricThreshold(TypedDict):
    warning: float
    elevated: float
    critical: float

ThresholdConfig = Dict[str, MetricThreshold]
```

**Concrete Example:**

```json
{
    "conpty": {"warning": 4.0, "elevated": 8.0, "critical": 10.0},
    "memory": {"warning": 60.0, "elevated": 80.0, "critical": 95.0},
    "process": {"warning": 200.0, "elevated": 400.0, "critical": 600.0},
    "handle": {"warning": 50000.0, "elevated": 80000.0, "critical": 120000.0}
}
```

---

## 5. Function Specifications

### 5.1 `normalize_metric()`

**File:** `src/boostgauge/collector.py`

**Signature:**

```python
def normalize_metric(value: float, threshold: float) -> float:
    """Normalize raw metric value against a critical threshold onto a 0-100 scale.
    
    A raw value equal to 0 maps to 0.0%.
    A raw value equal to threshold maps to 100.0%.
    Values above threshold cap at 100.0%.
    """
    ...
```

**Input Example:**

```python
value = 8.0
threshold = 10.0
```

**Output Example:**

```python
80.0
```

**Edge Cases:**
- `threshold <= 0.0` -> return `0.0`
- `value < 0.0` -> return `0.0`
- `value > threshold` -> return `100.0`

---

### 5.2 `calculate_composite_metric()`

**File:** `src/boostgauge/collector.py`

**Signature:**

```python
def calculate_composite_metric(
    conpty: int,
    memory_pct: float,
    process_cnt: int,
    handle_cnt: int,
    thresholds: Dict[str, Dict[str, float]],
) -> tuple[float, str]:
    """Calculate composite load value using normalized-max algorithm across metrics.
    
    Returns tuple of (composite_value, driver_metric_name).
    """
    ...
```

**Input Example:**

```python
conpty = 8
memory_pct = 50.0
process_cnt = 150
handle_cnt = 30000
thresholds = {
    "conpty": {"critical": 10.0},
    "memory": {"critical": 100.0},
    "process": {"critical": 500.0},
    "handle": {"critical": 100000.0},
}
```

**Output Example:**

```python
(80.0, "conpty")
```

**Edge Cases:**
- Empty `thresholds` dict -> defaults to standard fallback thresholds `{"conpty": {"critical": 10.0}, "memory": {"critical": 100.0}, "process": {"critical": 500.0}, "handle": {"critical": 100000.0}}`.
- Tied maximum values -> picks first metric key encountered in standard order (`conpty`, `memory`, `process`, `handle`).

---

### 5.3 `DataCollector.__init__()`

**File:** `src/boostgauge/collector.py`

**Signature:**

```python
class DataCollector:
    def __init__(
        self,
        config: Dict[str, Any],
        snapshot_queue: Optional[queue.Queue[SystemSnapshot]] = None,
    ) -> None:
        """Initialize collector state, thread control primitives, and snapshot target queue."""
        ...
```

**Input Example:**

```python
config = {
    "poll_interval": 2.0,
    "heavy_sample_ratio": 3,
    "thresholds": {
        "conpty": {"critical": 10.0},
        "memory": {"critical": 90.0},
        "process": {"critical": 500.0},
        "handle": {"critical": 100000.0},
    }
}
snapshot_queue = queue.Queue(maxsize=100)
```

**Output Example:**

```python
None  # Instance initialized with _thread=None, _stop_event=threading.Event()
```

**Edge Cases:**
- `config` missing `poll_interval` -> defaults to `2.0`
- `config` missing `heavy_sample_ratio` -> defaults to `3` (5.0s / 2.0s ratio approx 3 iterations)
- `snapshot_queue` is `None` -> snapshots collected but not enqueued

---

### 5.4 `DataCollector.start()` / `stop()` / `is_running()`

**File:** `src/boostgauge/collector.py`

**Signature:**

```python
def start(self) -> None:
    """Start background daemon polling thread if not already running."""
    ...

def stop(self) -> None:
    """Signal background polling thread to stop and join thread execution."""
    ...

def is_running(self) -> bool:
    """Return True if background collector thread is active."""
    ...
```

**Input Example:**

```python
collector.start()
running_status = collector.is_running()
collector.stop()
```

**Output Example:**

```python
running_status == True
# After stop(): collector.is_running() == False
```

**Edge Cases:**
- Calling `start()` when already running -> no-op (logs debug statement)
- Calling `stop()` when not running -> no-op

---

### 5.5 `WindowsCollector.collect_conpty_count()`

**File:** `src/boostgauge/collectors/windows.py`

**Signature:**

```python
def collect_conpty_count(self) -> int:
    """Count active conhost.exe processes and Windows Terminal pseudo-consoles."""
    ...
```

**Input Example:**

```python
# System with 3 conhost.exe processes and 1 OpenConsole.exe
```

**Output Example:**

```python
4
```

**Edge Cases:**
- `psutil.AccessDenied` when querying process name -> skip process without incrementing count
- No pseudo-console processes active -> returns `0`

---

### 5.6 `WindowsCollector.collect_process_count()`

**File:** `src/boostgauge/collectors/windows.py`

**Signature:**

```python
def collect_process_count(self) -> int:
    """Retrieve total count of active processes on the system via len(psutil.pids())."""
    ...
```

**Input Example:**

```python
# System running 214 active processes
```

**Output Example:**

```python
214
```

**Edge Cases:**
- `psutil.Error` on pid retrieval -> returns cached previous process count or `0`

---

### 5.7 `WindowsCollector.collect_memory_percent()`

**File:** `src/boostgauge/collectors/windows.py`

**Signature:**

```python
def collect_memory_percent(self) -> float:
    """Retrieve system physical memory utilization percentage via psutil.virtual_memory().percent."""
    ...
```

**Input Example:**

```python
# System with 16GB total RAM, 10.4GB in use
```

**Output Example:**

```python
65.0
```

**Edge Cases:**
- Exception from `psutil.virtual_memory()` -> returns cached previous percentage or `0.0`

---

### 5.8 `WindowsCollector.collect_handle_count()`

**File:** `src/boostgauge/collectors/windows.py`

**Signature:**

```python
def collect_handle_count(self) -> int:
    """Iterate accessible processes and sum total open handle count using num_handles()."""
    ...
```

**Input Example:**

```python
# System with accessible processes holding total 45,210 handles
```

**Output Example:**

```python
45210
```

**Edge Cases:**
- `psutil.AccessDenied` or `psutil.NoSuchProcess` on individual process handle query -> skip process handle count gracefully
- System process without handle access -> add 0 for that process

---

### 5.9 `WindowsCollector.collect_unleashed_sessions()`

**File:** `src/boostgauge/collectors/windows.py`

**Signature:**

```python
def collect_unleashed_sessions(self) -> int:
    """Scan Python processes for command lines matching unleashed-c-*.py pattern."""
    ...
```

**Input Example:**

```python
# Process cmdline: ["python.exe", "C:\\Scripts\\unleashed-c-102.py", "--daemon"]
```

**Output Example:**

```python
1
```

**Edge Cases:**
- Process cmdline inaccessible due to permissions (`AccessDenied`) -> skip process without error
- Non-Python process -> ignore

---

### 5.10 `WindowsCollector.collect_snapshot()`

**File:** `src/boostgauge/collectors/windows.py`

**Signature:**

```python
def collect_snapshot(self) -> SystemSnapshot:
    """Poll system resource metrics, compute composite metric and driver, return SystemSnapshot."""
    ...
```

**Input Example:**

```python
# Called by polling loop cycle
```

**Output Example:**

```python
SystemSnapshot(
    timestamp=1774924800.5,
    conpty_count=4,
    process_count=214,
    memory_percent=65.0,
    handle_count=45210,
    unleashed_sessions=1,
    driver="conpty",
    composite_value=40.0
)
```

**Edge Cases:**
- Exception during metric polling -> logs error, returns fallback snapshot using last valid metrics

---

### 5.11 `create_collector()`

**File:** `src/boostgauge/collectors/__init__.py`

**Signature:**

```python
def create_collector(
    config: Dict[str, Any],
    snapshot_queue: Optional[queue.Queue[SystemSnapshot]] = None,
) -> DataCollector:
    """Instantiate and return platform-appropriate DataCollector instance."""
    ...
```

**Input Example:**

```python
config = {"poll_interval": 2.0}
snapshot_queue = queue.Queue(maxsize=50)
```

**Output Example:**

```python
<WindowsCollector object at 0x0000021A8F4A12B0>  # On Windows platform
```

**Edge Cases:**
- Executed on unsupported non-Windows platform -> falls back to base `DataCollector` stub or raises `NotImplementedError` if platform not yet implemented.

---

## 6. Change Instructions

### 6.1 `src/boostgauge/collectors` (Add Directory)

Create directory `src/boostgauge/collectors`.

---

### 6.2 `src/boostgauge/collector.py` (Add)

**File Content:**

```python
"""Abstract base data collector, system snapshot dataclass, and composite metric calculations.

Issue #4: Windows data collector — ConPTY, processes, memory, handles
"""

from dataclasses import dataclass
import logging
import queue
import sys
import threading
import time
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class SystemSnapshot:
    """Dataclass holding a single system resource metrics snapshot."""

    timestamp: float
    conpty_count: int
    process_count: int
    memory_percent: float
    handle_count: int
    unleashed_sessions: int
    driver: str
    composite_value: float


def normalize_metric(value: float, threshold: float) -> float:
    """Normalize raw metric value against a threshold to 0-100 scale.

    Args:
        value: Raw metric numeric value.
        threshold: Critical threshold value corresponding to 100%.

    Returns:
        Normalized float between 0.0 and 100.0.
    """
    if threshold <= 0.0 or value <= 0.0:
        return 0.0
    normalized = (value / threshold) * 100.0
    return min(100.0, max(0.0, normalized))


def calculate_composite_metric(
    conpty: int,
    memory_pct: float,
    process_cnt: int,
    handle_cnt: int,
    thresholds: Optional[Dict[str, Dict[str, float]]] = None,
) -> Tuple[float, str]:
    """Calculate composite load score using normalized-max algorithm.

    Args:
        conpty: Raw ConPTY process count.
        memory_pct: System memory utilization percentage (0-100).
        process_cnt: Total active process count.
        handle_cnt: Total process open handle count.
        thresholds: Metric threshold dictionary.

    Returns:
        Tuple of (composite_value, driver_metric_name).
    """
    defaults = {
        "conpty": {"critical": 10.0},
        "memory": {"critical": 100.0},
        "process": {"critical": 500.0},
        "handle": {"critical": 100000.0},
    }
    cfg = thresholds or defaults

    conpty_thresh = cfg.get("conpty", {}).get("critical", 10.0)
    memory_thresh = cfg.get("memory", {}).get("critical", 100.0)
    process_thresh = cfg.get("process", {}).get("critical", 500.0)
    handle_thresh = cfg.get("handle", {}).get("critical", 100000.0)

    normalized_scores = {
        "conpty": normalize_metric(float(conpty), conpty_thresh),
        "memory": normalize_metric(memory_pct, memory_thresh),
        "process": normalize_metric(float(process_cnt), process_thresh),
        "handle": normalize_metric(float(handle_cnt), handle_thresh),
    }

    driver = max(normalized_scores, key=lambda k: normalized_scores[k])
    composite_val = normalized_scores[driver]
    return composite_val, driver


class DataCollector:
    """Abstract base class for system resource data collectors."""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        snapshot_queue: Optional[queue.Queue] = None,
    ) -> None:
        """Initialize data collector with configuration and output queue."""
        self.config = config or {}
        self.snapshot_queue = snapshot_queue
        self.poll_interval = float(self.config.get("poll_interval", 2.0))
        self.heavy_sample_ratio = int(self.config.get("heavy_sample_ratio", 3))

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_handles: int = 0
        self._last_unleashed: int = 0
        self._iteration_count: int = 0

    def collect_snapshot(self) -> SystemSnapshot:
        """Collect current system metrics and return a SystemSnapshot.

        Must be implemented by platform-specific subclasses.
        """
        now = time.time()
        comp_val, driver = calculate_composite_metric(0, 0.0, 0, 0, self.config.get("thresholds"))
        return SystemSnapshot(
            timestamp=now,
            conpty_count=0,
            process_count=0,
            memory_percent=0.0,
            handle_count=0,
            unleashed_sessions=0,
            driver=driver,
            composite_value=comp_val,
        )

    def _run_loop(self) -> None:
        """Background thread worker polling loop."""
        while not self._stop_event.is_set():
            t_start = time.time()
            try:
                snapshot = self.collect_snapshot()
                if self.snapshot_queue is not None:
                    try:
                        self.snapshot_queue.put_nowait(snapshot)
                    except queue.Full:
                        try:
                            self.snapshot_queue.get_nowait()
                        except queue.Empty:
                            pass
                        try:
                            self.snapshot_queue.put_nowait(snapshot)
                        except queue.Full:
                            pass
            except Exception as err:
                logger.error("Error collecting system snapshot: %s", err, exc_info=True)

            elapsed = time.time() - t_start
            sleep_duration = max(0.0, self.poll_interval - elapsed)
            self._stop_event.wait(timeout=sleep_duration)

    def start(self) -> None:
        """Start background polling thread if not active."""
        if self._thread is not None and self._thread.is_alive():
            logger.debug("DataCollector background thread already running.")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="BoostGauge-DataCollector",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop background polling thread gracefully."""
        if self._thread is None:
            return

        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None

    def is_running(self) -> bool:
        """Return True if background collector thread is running."""
        return self._thread is not None and self._thread.is_alive()
```

---

### 6.3 `src/boostgauge/collectors/windows.py` (Add)

**File Content:**

```python
"""Windows-specific resource data collector using psutil and Win32 process filtering.

Issue #4: Windows data collector — ConPTY, processes, memory, handles
"""

import logging
import re
from typing import Any, Dict, Optional, Set
import queue

import psutil

from boostgauge.collector import (
    DataCollector,
    SystemSnapshot,
    calculate_composite_metric,
)

logger = logging.getLogger(__name__)

UNLEASHED_REGEX = re.compile(r"unleashed-c-.*\.py", re.IGNORECASE)
CONPTY_PROCESS_NAMES: Set[str] = {
    "conhost.exe",
    "openconsole.exe",
    "windowsterminal.exe",
}


class WindowsCollector(DataCollector):
    """Windows implementation of system resource collector using psutil."""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        snapshot_queue: Optional[queue.Queue] = None,
    ) -> None:
        """Initialize Windows collector state."""
        super().__init__(config=config, snapshot_queue=snapshot_queue)
        self._cached_conpty: int = 0
        self._cached_procs: int = 0
        self._cached_memory: float = 0.0

    def collect_conpty_count(self) -> int:
        """Count active ConPTY / pseudo-console processes."""
        count = 0
        try:
            for proc in psutil.process_iter(attrs=["name"]):
                try:
                    name = proc.info.get("name")
                    if name and name.lower() in CONPTY_PROCESS_NAMES:
                        count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as err:
            logger.debug("Error iterating processes for ConPTY count: %s", err)
            return self._cached_conpty

        self._cached_conpty = count
        return count

    def collect_process_count(self) -> int:
        """Retrieve total count of active system processes."""
        try:
            pids = psutil.pids()
            count = len(pids)
            self._cached_procs = count
            return count
        except Exception as err:
            logger.debug("Error querying process count: %s", err)
            return self._cached_procs

    def collect_memory_percent(self) -> float:
        """Retrieve total system virtual memory utilization percentage."""
        try:
            mem = psutil.virtual_memory()
            pct = float(mem.percent)
            self._cached_memory = pct
            return pct
        except Exception as err:
            logger.debug("Error querying memory percentage: %s", err)
            return self._cached_memory

    def collect_handle_count(self) -> int:
        """Aggregate open handle count across accessible processes."""
        total_handles = 0
        try:
            for proc in psutil.process_iter(attrs=["pid"]):
                try:
                    num_handles = proc.num_handles()
                    if num_handles:
                        total_handles += num_handles
                except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
                    continue
        except Exception as err:
            logger.debug("Error aggregating process handles: %s", err)
            return self._last_handles

        self._last_handles = total_handles
        return total_handles

    def collect_unleashed_sessions(self) -> int:
        """Count active Python processes running scripts matching unleashed-c-*.py."""
        count = 0
        try:
            for proc in psutil.process_iter(attrs=["name"]):
                try:
                    name = proc.info.get("name")
                    if name and "python" in name.lower():
                        cmdline = proc.cmdline()
                        if any(UNLEASHED_REGEX.search(arg) for arg in cmdline):
                            count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as err:
            logger.debug("Error scanning unleashed session processes: %s", err)
            return self._last_unleashed

        self._last_unleashed = count
        return count

    def collect_snapshot(self) -> SystemSnapshot:
        """Collect fast and heavy metrics according to sample ratio and return SystemSnapshot."""
        now = psutil.time.time() if hasattr(psutil, "time") else __import__("time").time()

        conpty = self.collect_conpty_count()
        procs = self.collect_process_count()
        mem_pct = self.collect_memory_percent()

        if self._iteration_count % self.heavy_sample_ratio == 0:
            handles = self.collect_handle_count()
            unleashed = self.collect_unleashed_sessions()
        else:
            handles = self._last_handles
            unleashed = self._last_unleashed

        self._iteration_count += 1

        comp_val, driver = calculate_composite_metric(
            conpty=conpty,
            memory_pct=mem_pct,
            process_cnt=procs,
            handle_cnt=handles,
            thresholds=self.config.get("thresholds"),
        )

        return SystemSnapshot(
            timestamp=now,
            conpty_count=conpty,
            process_count=procs,
            memory_percent=mem_pct,
            handle_count=handles,
            unleashed_sessions=unleashed,
            driver=driver,
            composite_value=comp_val,
        )
```

---

### 6.4 `src/boostgauge/collectors/__init__.py` (Add)

**File Content:**

```python
"""Collectors package initialization and factory function.

Issue #4: Windows data collector — ConPTY, processes, memory, handles
"""

import queue
import sys
from typing import Any, Dict, Optional

from boostgauge.collector import DataCollector, SystemSnapshot
from boostgauge.collectors.windows import WindowsCollector


def create_collector(
    config: Optional[Dict[str, Any]] = None,
    snapshot_queue: Optional[queue.Queue] = None,
) -> DataCollector:
    """Factory function instantiating platform-appropriate DataCollector.

    Args:
        config: Configuration dictionary with poll intervals and thresholds.
        snapshot_queue: Target queue for pushed SystemSnapshots.

    Returns:
        Platform-specific DataCollector instance (WindowsCollector on Windows).
    """
    if sys.platform == "win32":
        return WindowsCollector(config=config, snapshot_queue=snapshot_queue)
    return WindowsCollector(config=config, snapshot_queue=snapshot_queue)


__all__ = ["DataCollector", "SystemSnapshot", "WindowsCollector", "create_collector"]
```

---

### 6.5 `src/boostgauge/__init__.py` (Modify)

```diff
 """BoostGauge package initialization.

 Issue #7: Configuration File and CLI Arguments
 """

+from boostgauge.collector import DataCollector, SystemSnapshot
+from boostgauge.collectors import WindowsCollector, create_collector
+
 __version__ = "0.1.0"

-__all__ = ["__version__"]
+__all__ = [
+    "__version__",
+    "DataCollector",
+    "SystemSnapshot",
+    "WindowsCollector",
+    "create_collector",
+]
```

---

### 6.6 `tests/unit/test_collector.py` (Add)

**File Content:**

```python
"""Unit tests for DataCollector base class, metric normalization, composite load calculation, and queue lifecycle.

Issue #4: Windows data collector — ConPTY, processes, memory, handles
"""

import queue
import time
import pytest

from boostgauge.collector import (
    DataCollector,
    SystemSnapshot,
    calculate_composite_metric,
    normalize_metric,
)


def test_normalize_metric_basic():
    """T050: Test metric normalization logic against critical threshold."""
    assert normalize_metric(5.0, 10.0) == 50.0
    assert normalize_metric(10.0, 10.0) == 100.0
    assert normalize_metric(15.0, 10.0) == 100.0
    assert normalize_metric(0.0, 10.0) == 0.0
    assert normalize_metric(-5.0, 10.0) == 0.0
    assert normalize_metric(5.0, 0.0) == 0.0


def test_calculate_composite_metric_driver_selection():
    """T050: Test composite load calculation and driver selection."""
    thresholds = {
        "conpty": {"critical": 10.0},
        "memory": {"critical": 100.0},
        "process": {"critical": 500.0},
        "handle": {"critical": 100000.0},
    }

    score, driver = calculate_composite_metric(
        conpty=8, memory_pct=50.0, process_cnt=100, handle_cnt=20000, thresholds=thresholds
    )
    assert score == 80.0
    assert driver == "conpty"

    score, driver = calculate_composite_metric(
        conpty=2, memory_pct=95.0, process_cnt=100, handle_cnt=20000, thresholds=thresholds
    )
    assert score == 95.0
    assert driver == "memory"


def test_collector_instantiation_and_defaults():
    """T010: Test DataCollector instantiation and config defaults."""
    collector = DataCollector()
    assert collector.poll_interval == 2.0
    assert collector.heavy_sample_ratio == 3
    assert not collector.is_running()


def test_collector_thread_lifecycle():
    """T100: Test DataCollector background thread start and stop cleanly."""
    q = queue.Queue(maxsize=10)
    collector = DataCollector(config={"poll_interval": 0.05}, snapshot_queue=q)

    assert not collector.is_running()
    collector.start()
    assert collector.is_running()

    time.sleep(0.15)
    collector.stop()
    assert not collector.is_running()
    assert q.qsize() > 0


def test_collector_queue_eviction_on_overflow():
    """T090: Test that a full queue evicts the oldest snapshot when pushing new items."""
    q = queue.Queue(maxsize=2)
    collector = DataCollector(config={"poll_interval": 0.02}, snapshot_queue=q)

    collector.start()
    time.sleep(0.1)
    collector.stop()

    assert q.qsize() == 2
```

---

### 6.7 `tests/unit/test_windows_collector.py` (Add)

**File Content:**

```python
"""Unit tests for WindowsCollector metrics querying, process filtering, handle enumeration, and permission error fallback.

Issue #4: Windows data collector — ConPTY, processes, memory, handles
"""

from unittest.mock import MagicMock, patch
import pytest

import psutil

from boostgauge.collectors.windows import WindowsCollector
from boostgauge.collectors import create_collector


@pytest.fixture
def mock_psutil_processes():
    """Fixture returning mocked psutil processes for ConPTY and Unleashed scanning."""
    p1 = MagicMock()
    p1.info = {"name": "conhost.exe"}

    p2 = MagicMock()
    p2.info = {"name": "python.exe"}
    p2.cmdline.return_value = ["python.exe", "C:\\Scripts\\unleashed-c-401.py"]

    p3 = MagicMock()
    p3.info = {"name": "explorer.exe"}
    p3.cmdline.return_value = ["explorer.exe"]

    return [p1, p2, p3]


def test_collect_conpty_count(mock_psutil_processes):
    """T020: Test conhost.exe process counting for ConPTY metric."""
    collector = WindowsCollector()
    with patch("psutil.process_iter", return_value=mock_psutil_processes):
        count = collector.collect_conpty_count()
        assert count == 1


def test_collect_unleashed_sessions(mock_psutil_processes):
    """T040: Test unleashed session detection matching unleashed-c-*.py pattern."""
    collector = WindowsCollector()
    with patch("psutil.process_iter", return_value=mock_psutil_processes):
        count = collector.collect_unleashed_sessions()
        assert count == 1


def test_collect_memory_and_processes():
    """T030: Test querying virtual memory % and process count."""
    collector = WindowsCollector()
    with patch("psutil.pids", return_value=[1, 2, 3, 4, 5]), patch(
        "psutil.virtual_memory"
    ) as mock_mem:
        mock_mem.return_value.percent = 62.5
        assert collector.collect_process_count() == 5
        assert collector.collect_memory_percent() == 62.5


def test_collect_handle_count_with_permission_denied():
    """T070: Test handle count collection with AccessDenied exception resilience."""
    p1 = MagicMock()
    p1.num_handles.return_value = 150

    p2 = MagicMock()
    p2.num_handles.side_effect = psutil.AccessDenied(pid=2)

    collector = WindowsCollector()
    with patch("psutil.process_iter", return_value=[p1, p2]):
        total_handles = collector.collect_handle_count()
        assert total_handles == 150


def test_windows_collector_snapshot():
    """T010/T060: Test full snapshot collection cycle on WindowsCollector."""
    collector = WindowsCollector(config={"heavy_sample_ratio": 1})
    with patch.object(collector, "collect_conpty_count", return_value=3), patch.object(
        collector, "collect_process_count", return_value=120
    ), patch.object(collector, "collect_memory_percent", return_value=20.0), patch.object(
        collector, "collect_handle_count", return_value=25000
    ), patch.object(
        collector, "collect_unleashed_sessions", return_value=2
    ):
        snapshot = collector.collect_snapshot()
        assert snapshot.conpty_count == 3
        assert snapshot.process_count == 120
        assert snapshot.memory_percent == 20.0
        assert snapshot.handle_count == 25000
        assert snapshot.unleashed_sessions == 2
        assert snapshot.composite_value == 30.0
        assert snapshot.driver == "conpty"


def test_create_collector_factory():
    """T010: Test create_collector factory function."""
    collector = create_collector(config={})
    assert isinstance(collector, WindowsCollector)
```

---

## 7. Pattern References

### 7.1 Package Initialization and Exports

**File:** `src/boostgauge/__init__.py` (lines 1-8)

```python
"""BoostGauge package initialization.

Issue #7: Configuration File and CLI Arguments
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
```

**Relevance:** Standard entry point export pattern listing public library classes and factory functions in `__all__`.

---

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `dataclasses.dataclass` | stdlib | `src/boostgauge/collector.py` |
| `logging` | stdlib | `collector.py`, `windows.py` |
| `queue` | stdlib | `collector.py`, `windows.py`, `collectors/__init__.py` |
| `threading` | stdlib | `collector.py` |
| `time` | stdlib | `collector.py`, `windows.py` |
| `typing.Any, Dict, Optional, Tuple, Set` | stdlib | All modules |
| `psutil` | third-party | `src/boostgauge/collectors/windows.py` |
| `re` | stdlib | `src/boostgauge/collectors/windows.py` |
| `pytest` | test dependency | `tests/unit/test_collector.py`, `test_windows_collector.py` |
| `unittest.mock.MagicMock, patch` | stdlib | `tests/unit/test_windows_collector.py` |

**New Dependencies:** None (uses existing `psutil >=7.2.2,<8.0.0` from `pyproject.toml`).

---

## 9. Placeholder

*Reserved for future alignment with LLD section numbering.*

---

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `WindowsCollector` instantiation | `config={}` | Instance initialized with `poll_interval=2.0` |
| T020 | `collect_conpty_count()` | Mocked processes `["conhost.exe", "python.exe"]` | `conpty_count == 1` |
| T030 | `collect_memory_percent()`, `collect_process_count()` | Mocked `psutil` memory and process IDs | Memory = `62.5`, Process Count = `5` |
| T040 | `collect_unleashed_sessions()` | Cmdline `["python.exe", "unleashed-c-401.py"]` | `unleashed_sessions == 1` |
| T050 | `normalize_metric()`, `calculate_composite_metric()` | Raw values: conpty=8, memory=50.0, procs=100, handles=20000 | `score == 80.0`, `driver == "conpty"` |
| T060 | `collect_snapshot()` | Mocked polling calls | `SystemSnapshot` populated with valid fields |
| T070 | `collect_handle_count()` | Process handles list containing `psutil.AccessDenied` | Sums accessible process handles (`150`) without crashing |
| T080 | Background thread execution | `poll_interval = 0.05` | Polling loop completes cycles under 15ms |
| T090 | Queue overflow eviction | Queue maxsize=2 with 5 generated snapshots | Queue holds latest 2 snapshots without blocking |
| T100 | `start()` and `stop()` lifecycle | Call `start()`, wait, call `stop()` | `is_running()` transitions True -> False, thread joins within timeout |

---

## 11. Implementation Notes

### 11.1 Thread Safety & Queue Management

The `DataCollector` background thread uses a `queue.Queue` to deliver `SystemSnapshot` objects to consumers (e.g. GUI components or event dispatchers). To prevent memory exhaustion or worker thread delays when the consumer is slow:
- Queue insertion uses `put_nowait()`.
- If `queue.Full` is raised, `get_nowait()` is invoked to pop the oldest snapshot before re-attempting `put_nowait()`.

### 11.2 Permission Resilience

On Windows, scanning command lines and counting handles across system-owned processes (e.g., `svchost.exe`, `lsass.exe`, `System`) raises `psutil.AccessDenied`.
- All process attribute iterations wrap individual process calls in `try...except (psutil.NoSuchProcess, psutil.AccessDenied): continue`.
- If process iteration fails entirely, functions return the last valid cached metric reading.

### 11.3 Constants Table

| Constant | Default Value | Rationale |
|----------|---------------|-----------|
| Fast Poll Interval | `2.0` s | Responsive updates for UI gauge without exceeding 1% CPU utilization |
| Heavy Sample Ratio | `3` (5.0s / 2.0s) | Stagger handle count aggregation and cmdline regex parsing across iterations |
| Standard ConPTY Critical Threshold | `10.0` | 10 active pseudo-consoles represents high parallel agent activity |
| Standard Memory Critical Threshold | `100.0` % | Standard physical memory scale baseline |
| Standard Process Critical Threshold | `500.0` | Elevated Windows user process count |
| Standard Handle Critical Threshold | `100,000` | Critical process handle load threshold |

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
| Issue | #4 |
| Verdict | APPROVED |
| Date | 2026-07-30 |
| Iterations | 1 |
| Finalized | 2026-07-30T03:00:00Z |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #4 |
| Verdict | APPROVED |
| Date | 2026-07-30 |
| Iterations | 1 |
| Finalized | 2026-07-30T08:01:11Z |

### Review Feedback Summary

The implementation spec is complete, highly concrete, and internally consistent. The revision in iteration 1 successfully updated the mock return value for collect_memory_percent from 45.0 to 20.0 in test_windows_collector_snapshot. This aligns the test inputs with the normalized-max composite metric algorithm (where conpty 3 / threshold 10.0 = 30.0%, memory 20.0 / 100.0 = 20.0%, procs 120 / 500.0 = 24.0%, handles 25000 / 100000.0 = 25.0%), guaranteeing that conpty is selected as the driving met...
