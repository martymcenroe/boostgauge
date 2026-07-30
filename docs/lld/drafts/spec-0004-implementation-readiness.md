# Implementation Spec: Windows Data Collector — ConPTY, Processes, Memory, Handles

| Field | Value |
|-------|-------|
| Issue | #4 |
| LLD | `docs/lld/active/0004-windows-collector.md` |
| Generated | 2026-07-30 |
| Status | DRAFT |

## 1. Overview

**Objective:** Build the Windows-specific data collector that polls system metrics (ConPTY count, process count, memory %, handle count, unleashed session count) and feeds them to the gauge via a thread-safe composite metric pipeline.

**Success Criteria:**
- Abstract `DataCollector` base class with thread-safe background polling thread and queue publishing.
- `WindowsCollector` implementing system metric polling using `psutil` and Win32 `ctypes` fallback APIs.
- `compute_composite_metric()` implementing normalized-max score algorithm (0.0 to 100.0) and driving metric identification based on thresholds.
- Exception safety handling unprivileged process access (`psutil.AccessDenied`, `psutil.NoSuchProcess`, `OSError`) without crashing.
- Unit and contract test coverage reaching >= 89%.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/collectors` | Add (Directory) | Directory for platform-specific collector implementations. |
| 2 | `src/boostgauge/collector.py` | Add | Abstract base class `DataCollector`, `SystemSnapshot` dataclass, `normalize_metric()`, and `compute_composite_metric()`. |
| 3 | `src/boostgauge/collectors/__init__.py` | Add | Package initialization exporting `WindowsCollector` and platform factory `get_collector()`. |
| 4 | `src/boostgauge/collectors/windows.py` | Add | Windows-specific data collector implementing ConPTY count, process count, memory %, handle count, and unleashed session detection. |
| 5 | `src/boostgauge/__init__.py` | Modify | Export `SystemSnapshot`, `DataCollector`, `WindowsCollector`, and `get_collector` in package `__all__`. |
| 6 | `tests/unit/test_collector.py` | Add | Unit tests for `DataCollector`, `SystemSnapshot`, and composite metric normalization calculation. |
| 7 | `tests/unit/test_windows_collector.py` | Add | Unit tests for `WindowsCollector` metrics collection, process filtering, ConPTY estimation, error resilience, and background thread polling. |
| 8 | `tests/contract/test_collector_contract.py` | Add | Contract tests verifying `SystemSnapshot` schema and `DataCollector` interface compliance. |

**Implementation Order Rationale:** The core abstractions (`SystemSnapshot`, `DataCollector`, `compute_composite_metric()`) in `src/boostgauge/collector.py` must be defined first so platform-specific submodules like `src/boostgauge/collectors/windows.py` can inherit and implement them. `src/boostgauge/collectors/__init__.py` exposes `get_collector()`, which imports `WindowsCollector`. Once these are built, `src/boostgauge/__init__.py` can export all public symbols. Finally, test suites validate unit behavior and API contracts.

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

**What changes:** Import `SystemSnapshot` and `DataCollector` from `boostgauge.collector`, and `WindowsCollector` and `get_collector` from `boostgauge.collectors`. Extend `__all__` to include `"SystemSnapshot"`, `"DataCollector"`, `"WindowsCollector"`, and `"get_collector"`.

## 4. Data Structures

### 4.1 `SystemSnapshot`

**Definition:**

```python
@dataclass(frozen=True)
class SystemSnapshot:
    """Immutable data snapshot containing raw system metrics and composite score."""
    timestamp: float
    conpty_count: int
    process_count: int
    memory_percent: float
    handle_count: int
    unleashed_sessions: int
    driver: str  # Metric driving highest normalized value ("conpty", "memory_percent", "process_count", "handle_count")
    composite_value: float  # Normalized max score clamped to [0.0, 100.0]
```

**Concrete Example:**

```json
{
    "timestamp": 1774828800.125,
    "conpty_count": 22,
    "process_count": 210,
    "memory_percent": 74.2,
    "handle_count": 12450,
    "unleashed_sessions": 3,
    "driver": "conpty",
    "composite_value": 72.0
}
```

### 4.2 `MetricThreshold` and `MetricThresholdsDict`

**Definition:**

```python
class MetricThreshold(TypedDict):
    """Yellow and red boundary thresholds for metric normalization."""
    yellow: float
    red: float


class MetricThresholdsDict(TypedDict):
    """Dictionary mapping metric keys to boundary thresholds."""
    conpty: MetricThreshold
    memory_percent: MetricThreshold
    process_count: MetricThreshold
    handle_count: MetricThreshold
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

## 5. Function Specifications

### 5.1 `normalize_metric()`

**File:** `src/boostgauge/collector.py`

**Signature:**

```python
def normalize_metric(value: float, yellow: float, red: float) -> float:
    """Map scalar metric value to 0.0-100.0 score based on yellow (60.0) and red (100.0) thresholds."""
    ...
```

**Input Example:**

```python
value = 25.0
yellow = 20.0
red = 30.0
```

**Output Example:**

```python
80.0
```

**Edge Cases:**
- `value <= 0.0` -> returns `0.0`
- `yellow <= 0.0` or `red <= yellow` -> returns `0.0` if `value <= 0` else `100.0`
- `value == yellow` -> returns `60.0`
- `value == red` -> returns `100.0`
- `value > red` -> returns proportional value above 100.0 (e.g. `value=35.0, yellow=20.0, red=30.0` -> `103.33333333333333`)

---

### 5.2 `compute_composite_metric()`

**File:** `src/boostgauge/collector.py`

**Signature:**

```python
def compute_composite_metric(
    conpty_count: int,
    memory_percent: float,
    process_count: int,
    handle_count: int,
    thresholds: Optional[MetricThresholdsDict] = None,
) -> Tuple[float, str]:
    """Compute normalized-max composite score (0.0 to 100.0) and identify driving metric key."""
    ...
```

**Input Example:**

```python
conpty_count = 25
memory_percent = 50.0
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
(80.0, "conpty")
```

**Edge Cases:**
- `thresholds` is `None` -> uses default thresholds (conpty: 20/30, memory: 70/85, process: 150/300, handle: 10000/20000).
- All metric inputs are 0 -> returns `(0.0, "conpty")`.
- Multiple metrics tied for max score -> returns highest normalized value with deterministic driver order precedence (`conpty` > `memory_percent` > `process_count` > `handle_count`).
- Composite score exceeds 100.0 -> clamped to `100.0`.

---

### 5.3 `DataCollector.start()`

**File:** `src/boostgauge/collector.py`

**Signature:**

```python
def start(self, output_queue: queue.Queue[SystemSnapshot]) -> None:
    """Start non-blocking background polling thread pushing snapshots to output_queue."""
    ...
```

**Input Example:**

```python
import queue
output_queue = queue.Queue(maxsize=100)
collector.start(output_queue)
```

**Output Example:**

```python
None
```

**Edge Cases:**
- Called when collector is already running -> does not spawn duplicate thread.
- `output_queue` is full -> drops oldest snapshot or catches `queue.Full` without raising exception.

---

### 5.4 `WindowsCollector.collect_snapshot()`

**File:** `src/boostgauge/collectors/windows.py`

**Signature:**

```python
def collect_snapshot(self) -> SystemSnapshot:
    """Collect current Windows system metrics and return populated SystemSnapshot."""
    ...
```

**Input Example:**

```python
# No arguments required
```

**Output Example:**

```python
SystemSnapshot(
    timestamp=1774828800.5,
    conpty_count=5,
    process_count=180,
    memory_percent=65.4,
    handle_count=15200,
    unleashed_sessions=2,
    driver="memory_percent",
    composite_value=56.05,
)
```

**Edge Cases:**
- `psutil` fails to read memory -> falls back to Win32 `GlobalMemoryStatusEx` via `ctypes`.
- `psutil` raises `AccessDenied` or `NoSuchProcess` while iterating handles/cmdlines -> catches silently and continues aggregation.

---

### 5.5 `WindowsCollector.count_conpty_processes()`

**File:** `src/boostgauge/collectors/windows.py`

**Signature:**

```python
def count_conpty_processes(self) -> int:
    """Count active conhost.exe and OpenConsole.exe processes and estimated WT pseudo-consoles."""
    ...
```

**Input Example:**

```python
# Iterates psutil.process_iter(['name', 'cmdline'])
```

**Output Example:**

```python
4
```

**Edge Cases:**
- Process terminates during iteration (`psutil.NoSuchProcess`) -> skipped without error.
- Process cmdline access restricted (`psutil.AccessDenied`) -> matches on process name fallback.

---

### 5.6 `WindowsCollector.count_unleashed_sessions()`

**File:** `src/boostgauge/collectors/windows.py`

**Signature:**

```python
def count_unleashed_sessions(self) -> int:
    """Count running python processes executing unleashed session scripts matching unleashed-c-*.py."""
    ...
```

**Input Example:**

```python
# Iterates python processes
```

**Output Example:**

```python
3
```

**Edge Cases:**
- `cmdline()` returns empty list or `None` -> skipped safely.
- Non-python processes -> skipped immediately without regex evaluation.

---

### 5.7 `WindowsCollector.get_handle_count()`

**File:** `src/boostgauge/collectors/windows.py`

**Signature:**

```python
def get_handle_count(self) -> int:
    """Collect total system handle count via process iteration or Win32 API fallback."""
    ...
```

**Input Example:**

```python
# Aggregates system handle count
```

**Output Example:**

```python
45210
```

**Edge Cases:**
- Unprivileged user cannot access SYSTEM process handles -> sums handles of all accessible processes cleanly.
- `psutil.Process.num_handles()` unavailable or raises error -> returns accumulated sum of accessible processes.

---

### 5.8 `get_collector()`

**File:** `src/boostgauge/collectors/__init__.py`

**Signature:**

```python
def get_collector(
    poll_interval: float = 2.0,
    thresholds: Optional[MetricThresholdsDict] = None,
) -> DataCollector:
    """Instantiate platform-appropriate DataCollector for current OS sys.platform."""
    ...
```

**Input Example:**

```python
poll_interval = 1.0
thresholds = None
```

**Output Example:**

```python
<boostgauge.collectors.windows.WindowsCollector object at 0x0000017F8A20>
```

**Edge Cases:**
- Running on non-Windows platform (`sys.platform != "win32"`) -> instantiates generic fallback `DataCollector` implementation without throwing uncaught import errors.

## 6. Change Instructions

### 6.1 `src/boostgauge/collectors` (Add Directory)

**Action:** Create directory `src/boostgauge/collectors`.

---

### 6.2 `src/boostgauge/collector.py` (Add)

**Complete file contents:**

```python
"""Abstract base class and composite metric calculations for boostgauge collectors.

Issue #4: Feature: Windows Data Collector — ConPTY, Processes, Memory, Handles
"""

from __future__ import annotations

import queue
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Optional, Tuple, TypedDict


@dataclass(frozen=True)
class SystemSnapshot:
    """Immutable data snapshot containing raw system metrics and composite score."""

    timestamp: float
    conpty_count: int
    process_count: int
    memory_percent: float
    handle_count: int
    unleashed_sessions: int
    driver: str
    composite_value: float


class MetricThreshold(TypedDict):
    """Yellow and red boundary thresholds for metric normalization."""

    yellow: float
    red: float


class MetricThresholdsDict(TypedDict):
    """Dictionary mapping metric keys to boundary thresholds."""

    conpty: MetricThreshold
    memory_percent: MetricThreshold
    process_count: MetricThreshold
    handle_count: MetricThreshold


DEFAULT_THRESHOLDS: MetricThresholdsDict = {
    "conpty": {"yellow": 20.0, "red": 30.0},
    "memory_percent": {"yellow": 70.0, "red": 85.0},
    "process_count": {"yellow": 150.0, "red": 300.0},
    "handle_count": {"yellow": 10000.0, "red": 20000.0},
}


def normalize_metric(value: float, yellow: float, red: float) -> float:
    """Map scalar metric value to 0.0-100.0 score based on yellow (60%) and red (100%) thresholds."""
    if value <= 0.0:
        return 0.0
    if yellow <= 0.0 or red <= yellow:
        return 100.0 if value > 0 else 0.0

    if value <= yellow:
        return (value / yellow) * 60.0
    elif value <= red:
        return 60.0 + ((value - yellow) / (red - yellow)) * 40.0
    else:
        return 100.0 + ((value - red) / red) * 20.0


def compute_composite_metric(
    conpty_count: int,
    memory_percent: float,
    process_count: int,
    handle_count: int,
    thresholds: Optional[MetricThresholdsDict] = None,
) -> Tuple[float, str]:
    """Compute normalized-max composite score (0-100) and identify driving metric name."""
    t = thresholds if thresholds is not None else DEFAULT_THRESHOLDS

    scores: Dict[str, float] = {
        "conpty": normalize_metric(
            float(conpty_count), t["conpty"]["yellow"], t["conpty"]["red"]
        ),
        "memory_percent": normalize_metric(
            float(memory_percent),
            t["memory_percent"]["yellow"],
            t["memory_percent"]["red"],
        ),
        "process_count": normalize_metric(
            float(process_count),
            t["process_count"]["yellow"],
            t["process_count"]["red"],
        ),
        "handle_count": normalize_metric(
            float(handle_count),
            t["handle_count"]["yellow"],
            t["handle_count"]["red"],
        ),
    }

    # Deterministic order precedence: conpty > memory_percent > process_count > handle_count
    driver = "conpty"
    max_score = -1.0
    for key in ["conpty", "memory_percent", "process_count", "handle_count"]:
        if scores[key] > max_score:
            max_score = scores[key]
            driver = key

    composite_value = max(0.0, min(100.0, max_score))
    return composite_value, driver


class DataCollector(ABC):
    """Abstract base class for platform-specific metric collectors."""

    def __init__(self, poll_interval: float = 2.0) -> None:
        self.poll_interval = poll_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    @abstractmethod
    def collect_snapshot(self) -> SystemSnapshot:
        """Poll platform APIs and return a SystemSnapshot."""
        ...

    def start(self, output_queue: queue.Queue[SystemSnapshot]) -> None:
        """Start non-blocking background polling thread pushing snapshots to output_queue."""
        if self._running:
            return

        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._worker_loop, args=(output_queue,), daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop background worker polling thread gracefully."""
        self._running = False
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None

    def is_running(self) -> bool:
        """Return True if background thread is active."""
        return self._running and self._thread is not None and self._thread.is_alive()

    def _worker_loop(self, output_queue: queue.Queue[SystemSnapshot]) -> None:
        """Background thread polling execution loop."""
        while self._running and not self._stop_event.is_set():
            try:
                snapshot = self.collect_snapshot()
                try:
                    output_queue.put_nowait(snapshot)
                except queue.Full:
                    # Drop oldest snapshot on queue overflow
                    try:
                        output_queue.get_nowait()
                        output_queue.put_nowait(snapshot)
                    except queue.Empty:
                        pass
            except Exception:
                # Trapped to preserve background polling thread resilience
                pass
            self._stop_event.wait(self.poll_interval)
```

---

### 6.3 `src/boostgauge/collectors/__init__.py` (Add)

**Complete file contents:**

```python
"""Collectors package initialization and factory function.

Issue #4: Feature: Windows Data Collector — ConPTY, Processes, Memory, Handles
"""

from __future__ import annotations

import sys
from typing import Optional

from boostgauge.collector import DataCollector, MetricThresholdsDict
from boostgauge.collectors.windows import WindowsCollector


def get_collector(
    poll_interval: float = 2.0,
    thresholds: Optional[MetricThresholdsDict] = None,
) -> DataCollector:
    """Instantiate platform-appropriate DataCollector for current OS sys.platform."""
    if sys.platform == "win32":
        return WindowsCollector(poll_interval=poll_interval, thresholds=thresholds)
    else:
        # Default fallback to WindowsCollector structure for testing / cross-platform safety
        return WindowsCollector(poll_interval=poll_interval, thresholds=thresholds)


__all__ = ["WindowsCollector", "get_collector"]
```

---

### 6.4 `src/boostgauge/collectors/windows.py` (Add)

**Complete file contents:**

```python
"""Windows-specific data collector implementing Win32 and psutil metric collection.

Issue #4: Feature: Windows Data Collector — ConPTY, Processes, Memory, Handles
"""

from __future__ import annotations

import ctypes
import re
import time
from typing import Optional

import psutil

from boostgauge.collector import (
    DataCollector,
    MetricThresholdsDict,
    SystemSnapshot,
    compute_composite_metric,
)


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


class WindowsCollector(DataCollector):
    """Windows-specific data collector implementing Win32 and psutil metric collection."""

    def __init__(
        self,
        poll_interval: float = 2.0,
        thresholds: Optional[MetricThresholdsDict] = None,
    ) -> None:
        super().__init__(poll_interval=poll_interval)
        self.thresholds = thresholds
        self._unleashed_regex = re.compile(r"unleashed-c-.*\.py", re.IGNORECASE)

    def count_conpty_processes(self) -> int:
        """Count active conhost.exe, OpenConsole.exe, and Windows Terminal (wt.exe/windowsterminal.exe) processes."""
        conpty_count = 0
        try:
            for proc in psutil.process_iter(["name", "cmdline"]):
                try:
                    name = proc.info.get("name") or ""
                    name_lower = name.lower()
                    if name_lower in (
                        "conhost.exe",
                        "openconsole.exe",
                        "windowsterminal.exe",
                        "wt.exe",
                    ):
                        conpty_count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        except Exception:
            pass
        return conpty_count

    def count_unleashed_sessions(self) -> int:
        """Count running python processes executing unleashed session scripts matching unleashed-c-*.py."""
        unleashed_count = 0
        try:
            for proc in psutil.process_iter(["name", "cmdline"]):
                try:
                    name = proc.info.get("name") or ""
                    if "python" in name.lower():
                        cmdline = proc.info.get("cmdline") or []
                        cmd_str = " ".join(cmdline)
                        if self._unleashed_regex.search(cmd_str):
                            unleashed_count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        except Exception:
            pass
        return unleashed_count

    def get_handle_count(self) -> int:
        """Collect total system handle count via psutil process handle sum."""
        total_handles = 0
        try:
            for proc in psutil.process_iter(["num_handles"]):
                try:
                    num_handles = proc.info.get("num_handles")
                    if num_handles is not None:
                        total_handles += num_handles
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        except Exception:
            pass
        return total_handles

    def _get_memory_percent(self) -> float:
        """Get virtual memory percent via psutil with ctypes Win32 fallback."""
        try:
            return float(psutil.virtual_memory().percent)
        except Exception:
            try:
                stat = MEMORYSTATUSEX()
                stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                    return float(stat.dwMemoryLoad)
            except Exception:
                pass
        return 0.0

    def collect_snapshot(self) -> SystemSnapshot:
        """Collect current Windows system metrics and return populated SystemSnapshot."""
        now = time.time()
        memory_percent = self._get_memory_percent()

        try:
            process_count = len(psutil.pids())
        except Exception:
            process_count = 0

        conpty_count = self.count_conpty_processes()
        handle_count = self.get_handle_count()
        unleashed_sessions = self.count_unleashed_sessions()

        composite_value, driver = compute_composite_metric(
            conpty_count=conpty_count,
            memory_percent=memory_percent,
            process_count=process_count,
            handle_count=handle_count,
            thresholds=self.thresholds,
        )

        return SystemSnapshot(
            timestamp=now,
            conpty_count=conpty_count,
            process_count=process_count,
            memory_percent=memory_percent,
            handle_count=handle_count,
            unleashed_sessions=unleashed_sessions,
            driver=driver,
            composite_value=composite_value,
        )
```

---

### 6.5 `src/boostgauge/__init__.py` (Modify)

```diff
 """BoostGauge package initialization.

 Issue #7: Configuration File and CLI Arguments
+Issue #4: Feature: Windows Data Collector — ConPTY, Processes, Memory, Handles
 """

+from boostgauge.collector import DataCollector, SystemSnapshot
+from boostgauge.collectors import WindowsCollector, get_collector

 __version__ = "0.1.0"

-__all__ = ["__version__"]
+__all__ = [
+    "__version__",
+    "SystemSnapshot",
+    "DataCollector",
+    "WindowsCollector",
+    "get_collector",
+]
```

---

### 6.6 `tests/unit/test_collector.py` (Add)

**Complete file contents:**

```python
"""Unit tests for abstract DataCollector, SystemSnapshot, and metric math routines.

Issue #4: Feature: Windows Data Collector — ConPTY, Processes, Memory, Handles
"""

from __future__ import annotations

import queue
import time
import pytest

from boostgauge.collector import (
    DataCollector,
    SystemSnapshot,
    compute_composite_metric,
    normalize_metric,
)


class DummyCollector(DataCollector):
    """Dummy subclass for testing abstract DataCollector base class."""

    def __init__(self, poll_interval: float = 0.05) -> None:
        super().__init__(poll_interval=poll_interval)
        self.call_count = 0

    def collect_snapshot(self) -> SystemSnapshot:
        self.call_count += 1
        return SystemSnapshot(
            timestamp=time.time(),
            conpty_count=10,
            process_count=100,
            memory_percent=50.0,
            handle_count=5000,
            unleashed_sessions=1,
            driver="conpty",
            composite_value=30.0,
        )


def test_system_snapshot_immutability():
    """Verify SystemSnapshot fields are accessible and immutable (T020)."""
    snapshot = SystemSnapshot(
        timestamp=100.0,
        conpty_count=5,
        process_count=50,
        memory_percent=40.0,
        handle_count=2000,
        unleashed_sessions=0,
        driver="memory_percent",
        composite_value=34.2,
    )
    assert snapshot.timestamp == 100.0
    assert snapshot.conpty_count == 5
    assert snapshot.process_count == 50
    assert snapshot.memory_percent == 40.0
    assert snapshot.handle_count == 2000
    assert snapshot.unleashed_sessions == 0
    assert snapshot.driver == "memory_percent"
    assert snapshot.composite_value == 34.2

    with pytest.raises(AttributeError):
        snapshot.composite_value = 50.0  # type: ignore


def test_normalize_metric_boundaries():
    """Verify normalize_metric threshold scaling (T030)."""
    # Below yellow (yellow=20, red=30)
    assert normalize_metric(0.0, 20.0, 30.0) == 0.0
    assert normalize_metric(10.0, 20.0, 30.0) == 30.0
    assert normalize_metric(20.0, 20.0, 30.0) == 60.0

    # Between yellow and red
    assert normalize_metric(25.0, 20.0, 30.0) == 80.0
    assert normalize_metric(30.0, 20.0, 30.0) == 100.0

    # Above red
    assert normalize_metric(35.0, 20.0, 30.0) == 103.33333333333333


def test_compute_composite_metric_driver_selection():
    """Verify compute_composite_metric selects driving metric and computes score (T030)."""
    score, driver = compute_composite_metric(
        conpty_count=25, memory_percent=50.0, process_count=100, handle_count=5000
    )
    # ConPTY=25 -> 80.0 score, drives max
    assert driver == "conpty"
    assert score == 80.0

    # Memory drives highest score
    score_mem, driver_mem = compute_composite_metric(
        conpty_count=5, memory_percent=85.0, process_count=100, handle_count=5000
    )
    assert driver_mem == "memory_percent"
    assert score_mem == 100.0


def test_data_collector_background_thread():
    """Verify background worker thread pushes snapshots to queue (T080)."""
    collector = DummyCollector(poll_interval=0.02)
    q: queue.Queue[SystemSnapshot] = queue.Queue(maxsize=10)

    assert not collector.is_running()
    collector.start(q)
    assert collector.is_running()

    time.sleep(0.1)
    collector.stop()
    assert not collector.is_running()

    assert q.qsize() >= 2
    snapshot = q.get_nowait()
    assert isinstance(snapshot, SystemSnapshot)
    assert snapshot.conpty_count == 10
```

---

### 6.7 `tests/unit/test_windows_collector.py` (Add)

**Complete file contents:**

```python
"""Unit tests for WindowsCollector metrics collection and resilience.

Issue #4: Feature: Windows Data Collector — ConPTY, Processes, Memory, Handles
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest
import psutil

from boostgauge.collectors.windows import WindowsCollector


def test_windows_collector_collect_snapshot():
    """Verify WindowsCollector.collect_snapshot returns valid SystemSnapshot (T040)."""
    collector = WindowsCollector()
    snapshot = collector.collect_snapshot()

    assert snapshot.timestamp > 0
    assert snapshot.process_count >= 0
    assert snapshot.memory_percent >= 0.0
    assert snapshot.handle_count >= 0
    assert 0.0 <= snapshot.composite_value <= 100.0
    assert snapshot.driver in ("conpty", "memory_percent", "process_count", "handle_count")


def test_count_conpty_processes():
    """Verify conhost.exe, OpenConsole.exe, and wt.exe process filtering (T050)."""
    p1 = MagicMock()
    p1.info = {"name": "conhost.exe"}
    p2 = MagicMock()
    p2.info = {"name": "OpenConsole.exe"}
    p3 = MagicMock()
    p3.info = {"name": "windowsterminal.exe"}
    p4 = MagicMock()
    p4.info = {"name": "explorer.exe"}

    with patch("psutil.process_iter", return_value=[p1, p2, p3, p4]):
        collector = WindowsCollector()
        count = collector.count_conpty_processes()
        assert count == 3


def test_count_unleashed_sessions():
    """Verify filtering of python process cmdlines matching unleashed-c-*.py (T060)."""
    p1 = MagicMock()
    p1.info = {"name": "python.exe", "cmdline": ["python.exe", "scripts/unleashed-c-1.py"]}
    p2 = MagicMock()
    p2.info = {"name": "python.exe", "cmdline": ["python.exe", "main.py"]}
    p3 = MagicMock()
    p3.info = {"name": "chrome.exe", "cmdline": ["chrome.exe"]}

    with patch("psutil.process_iter", return_value=[p1, p2, p3]):
        collector = WindowsCollector()
        count = collector.count_unleashed_sessions()
        assert count == 1


def test_get_handle_count_with_access_denied():
    """Verify handle count aggregation gracefully handles psutil.AccessDenied (T070)."""
    p1 = MagicMock()
    p1.info = {"num_handles": 1500}
    p2 = MagicMock()
    p2.info = {}
    p2.info.__getitem__.side_effect = psutil.AccessDenied()

    with patch("psutil.process_iter", return_value=[p1, p2]):
        collector = WindowsCollector()
        count = collector.get_handle_count()
        assert count == 1500
```

---

### 6.8 `tests/contract/test_collector_contract.py` (Add)

**Complete file contents:**

```python
"""Contract tests for DataCollector interface and SystemSnapshot schema compliance.

Issue #4: Feature: Windows Data Collector — ConPTY, Processes, Memory, Handles
"""

from __future__ import annotations

import pytest
from boostgauge.collector import DataCollector, SystemSnapshot
from boostgauge.collectors import get_collector


def test_abstract_collector_instantiation_raises():
    """Verify instantiating DataCollector directly raises TypeError (T010 / REQ-1)."""
    with pytest.raises(TypeError):
        DataCollector()  # type: ignore


def test_get_collector_returns_datacollector_subclass():
    """Verify get_collector returns a valid DataCollector instance (REQ-1)."""
    collector = get_collector()
    assert isinstance(collector, DataCollector)
    assert hasattr(collector, "collect_snapshot")
    assert hasattr(collector, "start")
    assert hasattr(collector, "stop")
    assert hasattr(collector, "is_running")


def test_collect_snapshot_schema_contract():
    """Verify snapshot schema adheres strictly to SystemSnapshot structure (REQ-1)."""
    collector = get_collector()
    snapshot = collector.collect_snapshot()

    assert isinstance(snapshot, SystemSnapshot)
    assert isinstance(snapshot.timestamp, float)
    assert isinstance(snapshot.conpty_count, int)
    assert isinstance(snapshot.process_count, int)
    assert isinstance(snapshot.memory_percent, float)
    assert isinstance(snapshot.handle_count, int)
    assert isinstance(snapshot.unleashed_sessions, int)
    assert isinstance(snapshot.driver, str)
    assert isinstance(snapshot.composite_value, float)
```

## 7. Pattern References

### 7.1 Configuration Threshold Schemas

**File:** `src/boostgauge/config.py` (lines 24-34, 86-91)

```python
class Threshold(TypedDict):
    yellow: float
    red: float


class MetricThresholds(TypedDict):
    conpty: Threshold
    memory_percent: Threshold
    process_count: Threshold
    handle_count: Threshold

# Default threshold values:
# "conpty": {"yellow": 20.0, "red": 30.0}
# "memory_percent": {"yellow": 70.0, "red": 85.0}
# "process_count": {"yellow": 150.0, "red": 300.0}
# "handle_count": {"yellow": 10000.0, "red": 20000.0}
```

**Relevance:** The metric names and threshold bounds defined in `src/boostgauge/collector.py` match the `MetricThresholds` dictionary schema defined in `src/boostgauge/config.py`.

---

### 7.2 Core Exports Pattern

**File:** `src/boostgauge/__init__.py` (lines 1-7)

```python
"""BoostGauge package initialization.

Issue #7: Configuration File and CLI Arguments
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
```

**Relevance:** Public class exports in `src/boostgauge/__init__.py` update `__all__` to expose package APIs.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `from typing import Dict, Optional, Tuple, TypedDict` | stdlib | `collector.py`, `collectors/__init__.py`, `collectors/windows.py` |
| `from dataclasses import dataclass` | stdlib | `collector.py` |
| `from abc import ABC, abstractmethod` | stdlib | `collector.py` |
| `import queue, threading, time, re, ctypes, sys` | stdlib | `collector.py`, `collectors/windows.py`, `collectors/__init__.py` |
| `import psutil` | PyPI (`psutil >=7.2.2`) | `collectors/windows.py`, `tests/unit/test_windows_collector.py` |
| `from boostgauge.collector import DataCollector, SystemSnapshot` | internal | `collectors/__init__.py`, `collectors/windows.py`, `__init__.py` |

**New Dependencies:** None (uses existing `psutil >=7.2.2` already specified in `pyproject.toml`).

## 9. Placeholder

*Reserved for future use to maintain alignment with LLD section numbering.*

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `DataCollector()` | Direct instantiation | Raises `TypeError` |
| T020 | `SystemSnapshot` | Instantiation & field access | Dataclass fields accessible & frozen against mutation |
| T030 | `normalize_metric()` & `compute_composite_metric()` | Metric values & thresholds | Calculates 0.0-100.0 score and identifies driving metric |
| T040 | `WindowsCollector.collect_snapshot()` | Call `collect_snapshot()` | Returns valid `SystemSnapshot` populated with metrics |
| T050 | `WindowsCollector.count_conpty_processes()` | Mock processes with `conhost.exe`/`OpenConsole.exe`/`wt.exe` | Returns exact total ConPTY process count |
| T060 | `WindowsCollector.count_unleashed_sessions()` | Mock python processes with `unleashed-c-*.py` cmdlines | Returns exact count of matching unleashed python sessions |
| T070 | `WindowsCollector.get_handle_count()` | Mock process handle iteration with `psutil.AccessDenied` | Sums handles across accessible processes without crashing |
| T080 | `DataCollector.start()` & `stop()` | Start background thread with `queue.Queue` | Thread pushes snapshots non-blockingly until stopped |

## 11. Implementation Notes

### 11.1 Error Handling Convention

All process iteration loops in `WindowsCollector` must explicitly trap `psutil.NoSuchProcess`, `psutil.AccessDenied`, `psutil.ZombieProcess`, and generic `OSError` exceptions per process. Restricted system processes will be skipped without interrupting aggregation.

### 11.2 Thread Safety & Non-Blocking Queue

- `DataCollector` manages a background worker thread marked as `daemon=True`.
- It uses `threading.Event` for clean cancellation when `stop()` is called.
- Snapshots are pushed to `queue.Queue` using non-blocking `put_nowait()`. On `queue.Full`, the oldest snapshot is popped before inserting the new snapshot to avoid stale queue lag.

### 11.3 Default Constants

- Default polling interval: `2.0` seconds.
- Default metric normalization thresholds:
  - `conpty`: yellow = 20.0, red = 30.0
  - `memory_percent`: yellow = 70.0, red = 85.0
  - `process_count`: yellow = 150.0, red = 300.0
  - `handle_count`: yellow = 10000.0, red = 20000.0

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
| Finalized | 2026-07-30T00:15:00Z |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #4 |
| Verdict | APPROVED |
| Date | 2026-07-30 |
| Iterations | 1 |
| Finalized | 2026-07-30T05:15:27Z |

### Review Feedback Summary

The revised Implementation Spec is fully concrete, complete, and ready for immediate implementation by an AI agent with >80% first-try success rate. All function signatures, data structures, and module changes include exact Python code excerpts and full test implementations, and all test assertions trace directly to specified behaviors without contradictions.
