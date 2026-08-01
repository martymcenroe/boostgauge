# Implementation Spec: Windows data collector — ConPTY, processes, memory, handles (#4)

| Field | Value |
|-------|-------|
| Issue | #4 |
| LLD | `docs/lld/done/0004-windows-data-collector.md` |
| Generated | 2026-08-01 |
| Status | APPROVED |

## 1. Overview

This implementation creates the Windows-specific system data collector (`WindowsCollector`) and base data collection framework (`DataCollector`). It continuously polls system metrics (ConPTY pseudo-console allocations, total process counts, virtual memory percentage, open system handles, and active Unleashed sessions) in a non-blocking background thread, computes a normalized-max composite load score (0.0–100.0), and pushes thread-safe snapshots (`SystemSnapshot`) to a consumer queue.

**Objective:** Build a Windows-specific data collector that polls system metrics in a non-blocking background thread, computes a normalized-max composite load score, and pushes system snapshots to a thread-safe queue.

**Success Criteria:**
- `WindowsCollector` accurately polls ConPTY allocations, system process count, memory %, handle count, and Unleashed sessions via `psutil` and Win32 fallback APIs.
- Normalized-max composite calculation correctly identifies the primary resource bottleneck driver.
- Background polling loop operates at configurable intervals (default 2.0s) with < 1.0% CPU overhead.
- Gracefully catches `psutil.AccessDenied` and process termination without killing the collection loop thread.
- Full unit and contract test suites achieving ≥95% coverage without `tkinter` GUI dependency.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/collector.py` | Add | Base `DataCollector` class, `SystemSnapshot` dataclass, metric normalization, composite metric calculation, and background threading loop |
| 2 | `src/boostgauge/collectors/windows.py` | Add | `WindowsCollector` implementation querying ConPTY, psutil metrics, handle counts, and Unleashed sessions |
| 3 | `src/boostgauge/collectors/__init__.py` | Add | Collectors package initializer exporting `WindowsCollector` and `create_collector()` factory function |
| 4 | `src/boostgauge/__init__.py` | Modify | Re-export `DataCollector`, `SystemSnapshot`, `WindowsCollector`, and `create_collector` from package root |
| 5 | `tests/unit/test_collector.py` | Add | Unit tests for base collector, metric normalization, composite score calculation, and queue bounds |
| 6 | `tests/unit/test_windows_collector.py` | Add | Unit tests for `WindowsCollector` polling, ConPTY counting, handle aggregation, and permission fallback |
| 7 | `tests/contract/test_collector_contract.py` | Add | Contract test suite verifying `DataCollector` interface compliance across concrete implementations |

**Implementation Order Rationale:** Base data structures and abstract base classes (`collector.py`) must be implemented first, followed by concrete platform implementation (`collectors/windows.py`) and factory exports (`collectors/__init__.py`, `__init__.py`). Unit tests (`test_collector.py`, `test_windows_collector.py`) and contract tests (`test_collector_contract.py`) are placed last after module definitions exist.

## 3. Current State (for Modify/Delete files)

### 3.1 `src/boostgauge/__init__.py`

**Relevant excerpt** (lines 1-6):

```python
"""BoostGauge package initialization.

Issue #7: Feature configuration file and CLI arguments
"""

__version__ = "0.1.0"
```

**What changes:** Add package root re-exports for `DataCollector`, `SystemSnapshot`, `WindowsCollector`, and `create_collector` alongside `__all__`.

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
    driver: str  # Primary bottleneck driver: "conpty", "memory", "process", "handles"
    composite_value: float  # 0.0 - 100.0 score
```

**Concrete Example:**

```json
{
    "timestamp": 1785567890.123,
    "conpty_count": 12,
    "process_count": 245,
    "memory_percent": 68.5,
    "handle_count": 48200,
    "unleashed_sessions": 3,
    "driver": "conpty",
    "composite_value": 60.0
}
```

### 4.2 `MetricThresholds`

**Definition:**

```python
from typing import TypedDict

class MetricThresholds(TypedDict):
    conpty: float
    memory: float
    process: float
    handles: float
```

**Concrete Example:**

```json
{
    "conpty": 20.0,
    "memory": 90.0,
    "process": 500.0,
    "handles": 100000.0
}
```

### 4.3 `CollectorConfig`

**Definition:**

```python
from typing import Optional, TypedDict

class CollectorConfig(TypedDict, total=False):
    poll_interval: float
    thresholds: MetricThresholds
```

**Concrete Example:**

```json
{
    "poll_interval": 2.0,
    "thresholds": {
        "conpty": 20.0,
        "memory": 90.0,
        "process": 500.0,
        "handles": 100000.0
    }
}
```

## 5. Function Specifications

### 5.1 `normalize_metric()`

**File:** `src/boostgauge/collector.py`

**Signature:**

```python
def normalize_metric(value: float, threshold: float) -> float:
    """Map a raw metric value to a 0.0-100.0 scale relative to maximum nominal threshold."""
    ...
```

**Input Example:**

```python
value = 15.0
threshold = 20.0
```

**Output Example:**

```python
75.0
```

**Edge Cases:**
- `threshold <= 0.0` -> returns `0.0`
- `value <= 0.0` -> returns `0.0`
- `value > threshold` -> returns `100.0` (clamped)

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
    thresholds: Dict[str, float],
) -> Tuple[float, str]:
    """Calculate composite load value (0-100) using normalized-max algorithm and return (composite_value, driver_name)."""
    ...
```

**Input Example:**

```python
conpty = 16
memory_pct = 45.0
process_cnt = 200
handle_cnt = 30000
thresholds = {
    "conpty": 20.0,
    "memory": 90.0,
    "process": 500.0,
    "handles": 100000.0,
}
```

**Output Example:**

```python
(80.0, "conpty")
```

**Edge Cases:**
- Missing threshold key -> falls back to default threshold (`conpty: 20.0`, `memory: 90.0`, `process: 500.0`, `handles: 100000.0`)
- Equal normalized scores -> picks first matching key in tie-breaker order (`conpty` -> `memory` -> `process` -> `handles`)

---

### 5.3 `DataCollector.__init__()`

**File:** `src/boostgauge/collector.py`

**Signature:**

```python
class DataCollector:
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        snapshot_queue: Optional[queue.Queue[SystemSnapshot]] = None,
    ) -> None:
        """Initialize data collector with configuration and thread-safe output queue."""
        ...
```

**Input Example:**

```python
config = {"poll_interval": 1.0, "thresholds": {"conpty": 25.0}}
snapshot_queue = queue.Queue(maxsize=100)
```

**Output Example:**

```python
# Instance initialized with self.poll_interval = 1.0, self.snapshot_queue maxsize=100
```

**Edge Cases:**
- `config is None` -> uses defaults (`poll_interval=2.0`, standard thresholds)
- `snapshot_queue is None` -> instantiates `queue.Queue(maxsize=100)`

---

### 5.4 `DataCollector.start()` & `stop()`

**File:** `src/boostgauge/collector.py`

**Signature:**

```python
def start(self) -> None:
    """Start background polling thread if not already running."""
    ...

def stop(self, timeout: float = 2.0) -> None:
    """Signal background thread to stop and join thread within timeout."""
    ...
```

**Input Example:**

```python
collector.start()
collector.stop(timeout=1.0)
```

**Output Example:**

```python
None
```

**Edge Cases:**
- Calling `start()` when already running -> no-op (safely ignored)
- Calling `stop()` when thread is not started -> no-op
- Thread join timeout exceeded -> continues execution, marks thread stopped state

---

### 5.5 `WindowsCollector.poll_metrics()`

**File:** `src/boostgauge/collectors/windows.py`

**Signature:**

```python
class WindowsCollector(DataCollector):
    def poll_metrics(self) -> SystemSnapshot:
        """Poll Windows system metrics using psutil and Win32 fallback calls."""
        ...
```

**Input Example:**

```python
snapshot = collector.poll_metrics()
```

**Output Example:**

```python
SystemSnapshot(
    timestamp=1785567890.123,
    conpty_count=4,
    process_count=182,
    memory_percent=52.4,
    handle_count=35420,
    unleashed_sessions=1,
    driver="memory",
    composite_value=58.22,
)
```

**Edge Cases:**
- `psutil.AccessDenied` raised when enumerating process handles or command lines -> catches exception, uses 0 or cached count for affected process, continues loop
- Non-Windows platform invocation -> raises `NotImplementedError("WindowsCollector requires Windows platform")` unless mocked

---

### 5.6 `create_collector()`

**File:** `src/boostgauge/collectors/__init__.py`

**Signature:**

```python
def create_collector(
    config: Optional[Dict[str, Any]] = None,
    snapshot_queue: Optional[queue.Queue[SystemSnapshot]] = None,
) -> DataCollector:
    """Instantiate platform-appropriate DataCollector."""
    ...
```

**Input Example:**

```python
collector = create_collector(config={"poll_interval": 2.0})
```

**Output Example:**

```text
<boostgauge.collectors.windows.WindowsCollector object at 0x0000021A89FB0190>
```

**Edge Cases:**
- Non-Windows OS (`sys.platform != 'win32'`) -> falls back to returning base `DataCollector` stub or raises `NotImplementedError` based on runtime configuration.

## 6. Change Instructions

### 6.1 `src/boostgauge/collector.py` (Add)

**Complete file contents:**

```python
"""Abstract base class for system data collectors, normalization, and composite metric calculation.

Issue #4: Feature: Windows data collector — ConPTY, processes, memory, handles
"""

from dataclasses import dataclass
import logging
import queue
import sys
import threading
import time
from typing import Any, Dict, Optional, Tuple, TypedDict

logger = logging.getLogger(__name__)


@dataclass
class SystemSnapshot:
    """Immutable snapshot of system metrics at a specific timestamp."""

    timestamp: float
    conpty_count: int
    process_count: int
    memory_percent: float
    handle_count: int
    unleashed_sessions: int
    driver: str
    composite_value: float


DEFAULT_THRESHOLDS: Dict[str, float] = {
    "conpty": 20.0,
    "memory": 90.0,
    "process": 500.0,
    "handles": 100000.0,
}


def normalize_metric(value: float, threshold: float) -> float:
    """Map a raw metric value to a 0.0-100.0 scale relative to metric threshold."""
    if threshold <= 0.0 or value <= 0.0:
        return 0.0
    return min(100.0, (float(value) / float(threshold)) * 100.0)


def calculate_composite_metric(
    conpty: int,
    memory_pct: float,
    process_cnt: int,
    handle_cnt: int,
    thresholds: Dict[str, float],
) -> Tuple[float, str]:
    """Calculate composite load value (0-100) using normalized-max algorithm and return (composite_value, driver)."""
    t_conpty = thresholds.get("conpty", DEFAULT_THRESHOLDS["conpty"])
    t_memory = thresholds.get("memory", DEFAULT_THRESHOLDS["memory"])
    t_process = thresholds.get("process", DEFAULT_THRESHOLDS["process"])
    t_handles = thresholds.get("handles", DEFAULT_THRESHOLDS["handles"])

    norm_scores = {
        "conpty": normalize_metric(float(conpty), t_conpty),
        "memory": normalize_metric(float(memory_pct), t_memory),
        "process": normalize_metric(float(process_cnt), t_process),
        "handles": normalize_metric(float(handle_cnt), t_handles),
    }

    # Driver evaluation priority for tie-breaking: conpty > memory > process > handles
    priority = ["conpty", "memory", "process", "handles"]
    best_driver = "conpty"
    max_val = -1.0

    for driver_key in priority:
        val = norm_scores[driver_key]
        if val > max_val:
            max_val = val
            best_driver = driver_key

    return round(max_val, 2), best_driver


class DataCollector:
    """Abstract base class for platform-specific system resource data collectors."""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        snapshot_queue: Optional[queue.Queue[SystemSnapshot]] = None,
    ) -> None:
        """Initialize data collector with configuration and thread-safe output queue."""
        self.config = config or {}
        self.poll_interval: float = float(self.config.get("poll_interval", 2.0))
        self.thresholds: Dict[str, float] = dict(DEFAULT_THRESHOLDS)

        user_thresholds = self.config.get("thresholds")
        if isinstance(user_thresholds, dict):
            for k, v in user_thresholds.items():
                if k in self.thresholds and isinstance(v, (int, float)):
                    self.thresholds[k] = float(v)

        if snapshot_queue is not None:
            self.snapshot_queue = snapshot_queue
        else:
            self.snapshot_queue = queue.Queue(maxsize=100)

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start background polling thread if not already running."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="BoostGaugeCollectorThread")
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        """Signal background thread to stop and join thread within timeout."""
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    def poll_metrics(self) -> SystemSnapshot:
        """Abstract method: Poll raw system metrics and return SystemSnapshot."""
        raise NotImplementedError("Subclasses must implement poll_metrics()")

    def _run_loop(self) -> None:
        """Main background loop polling metrics and pushing to snapshot_queue."""
        while not self._stop_event.is_set():
            start_time = time.monotonic()
            try:
                snapshot = self.poll_metrics()
                if self.snapshot_queue.full():
                    try:
                        self.snapshot_queue.get_nowait()
                    except queue.Empty:
                        pass
                self.snapshot_queue.put_nowait(snapshot)
            except Exception as err:
                logger.warning("Error during system metrics collection: %s", err, exc_info=True)

            elapsed = time.monotonic() - start_time
            sleep_duration = max(0.05, self.poll_interval - elapsed)
            self._stop_event.wait(timeout=sleep_duration)
```

---

### 6.2 `src/boostgauge/collectors/windows.py` (Add)

**Complete file contents:**

```python
"""Windows-specific system data collector implementation using psutil and Win32 APIs.

Issue #4: Feature: Windows data collector — ConPTY, processes, memory, handles
"""

import logging
import queue
import sys
import time
from typing import Any, Dict, Optional

import psutil

from boostgauge.collector import DataCollector, SystemSnapshot, calculate_composite_metric

logger = logging.getLogger(__name__)


class WindowsCollector(DataCollector):
    """Windows-specific data collector using psutil and Win32 handle enumeration."""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        snapshot_queue: Optional[queue.Queue[SystemSnapshot]] = None,
    ) -> None:
        """Initialize Windows collector."""
        super().__init__(config=config, snapshot_queue=snapshot_queue)
        if sys.platform != "win32" and not config.get("_allow_non_windows_for_testing", False):
            raise NotImplementedError("WindowsCollector requires Windows operating system")

    def _count_conpty(self) -> int:
        """Count conhost.exe processes and OpenConsole pseudo-consoles."""
        conpty_count = 0
        for proc in psutil.process_iter(["name"]):
            try:
                pname = (proc.info.get("name") or "").lower()
                if pname in ("conhost.exe", "openconsole.exe"):
                    conpty_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return conpty_count

    def _get_handle_count(self) -> int:
        """Query aggregate handle count across accessible processes."""
        total_handles = 0
        for proc in psutil.process_iter(["num_handles"]):
            try:
                num_h = proc.info.get("num_handles")
                if num_h and isinstance(num_h, int):
                    total_handles += num_h
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return total_handles

    def _count_unleashed_sessions(self) -> int:
        """Count active Python processes running unleashed session scripts."""
        unleashed_count = 0
        for proc in psutil.process_iter(["name", "cmdline"]):
            try:
                pname = (proc.info.get("name") or "").lower()
                if pname.startswith("python"):
                    cmdline = proc.info.get("cmdline") or []
                    cmd_str = " ".join(cmdline).lower()
                    if "unleashed-c-" in cmd_str:
                        unleashed_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return unleashed_count

    def poll_metrics(self) -> SystemSnapshot:
        """Poll Windows system metrics and return SystemSnapshot."""
        timestamp = time.time()
        conpty_cnt = self._count_conpty()
        proc_cnt = len(psutil.pids())
        mem_pct = float(psutil.virtual_memory().percent)
        handle_cnt = self._get_handle_count()
        unleashed_cnt = self._count_unleashed_sessions()

        composite_val, driver_name = calculate_composite_metric(
            conpty=conpty_cnt,
            memory_pct=mem_pct,
            process_cnt=proc_cnt,
            handle_cnt=handle_cnt,
            thresholds=self.thresholds,
        )

        return SystemSnapshot(
            timestamp=timestamp,
            conpty_count=conpty_cnt,
            process_count=proc_cnt,
            memory_percent=mem_pct,
            handle_count=handle_cnt,
            unleashed_sessions=unleashed_cnt,
            driver=driver_name,
            composite_value=composite_val,
        )
```

---

### 6.3 `src/boostgauge/collectors/__init__.py` (Add)

**Complete file contents:**

```python
"""Collectors package initialization and factory function.

Issue #4: Feature: Windows data collector — ConPTY, processes, memory, handles
"""

import queue
import sys
from typing import Any, Dict, Optional, Type

from boostgauge.collector import DataCollector, SystemSnapshot
from boostgauge.collectors.windows import WindowsCollector


def create_collector(
    config: Optional[Dict[str, Any]] = None,
    snapshot_queue: Optional[queue.Queue[SystemSnapshot]] = None,
) -> DataCollector:
    """Factory function to instantiate the platform-appropriate DataCollector."""
    cfg = config or {}
    if sys.platform == "win32" or cfg.get("_allow_non_windows_for_testing", False):
        return WindowsCollector(config=cfg, snapshot_queue=snapshot_queue)
    raise NotImplementedError(f"Platform '{sys.platform}' is not supported yet")


__all__ = [
    "DataCollector",
    "SystemSnapshot",
    "WindowsCollector",
    "create_collector",
]
```

---

### 6.4 `src/boostgauge/__init__.py` (Modify)

**Change 1:** Add imports and updated `__all__` list.

```diff
 """BoostGauge package initialization.

 Issue #7: Feature configuration file and CLI arguments
+Issue #4: Feature: Windows data collector — ConPTY, processes, memory, handles
 """

+from boostgauge.collector import DataCollector, SystemSnapshot
+from boostgauge.collectors import WindowsCollector, create_collector

 __version__ = "0.1.0"
+
+__all__ = [
+    "DataCollector",
+    "SystemSnapshot",
+    "WindowsCollector",
+    "create_collector",
+    "__version__",
+]
```

---

### 6.5 `tests/unit/test_collector.py` (Add)

**Complete file contents:**

```python
"""Unit test suite for base DataCollector and composite metric calculations.

Issue #4: Feature: Windows data collector — ConPTY, processes, memory, handles
"""

import queue
import time
from typing import Any, Dict, Optional
import pytest

from boostgauge.collector import (
    DEFAULT_THRESHOLDS,
    DataCollector,
    SystemSnapshot,
    calculate_composite_metric,
    normalize_metric,
)


class DummyCollector(DataCollector):
    """Concrete DummyCollector for testing base class behavior."""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        snapshot_queue: Optional[queue.Queue[SystemSnapshot]] = None,
        fail_poll: bool = False,
    ) -> None:
        super().__init__(config=config, snapshot_queue=snapshot_queue)
        self.fail_poll = fail_poll
        self.poll_count = 0

    def poll_metrics(self) -> SystemSnapshot:
        self.poll_count += 1
        if self.fail_poll:
            raise RuntimeError("Simulated polling exception")
        return SystemSnapshot(
            timestamp=time.time(),
            conpty_count=10,
            process_count=100,
            memory_percent=45.0,
            handle_count=10000,
            unleashed_sessions=1,
            driver="conpty",
            composite_value=50.0,
        )


def test_normalize_metric_bounds() -> None:
    """Verify normalization mapping and boundary clamping."""
    assert normalize_metric(10.0, 20.0) == 50.0
    assert normalize_metric(0.0, 20.0) == 0.0
    assert normalize_metric(25.0, 20.0) == 100.0
    assert normalize_metric(10.0, 0.0) == 0.0


def test_calculate_composite_metric_driver_selection() -> None:
    """Verify max normalized driver selection."""
    thresholds = {"conpty": 20.0, "memory": 100.0, "process": 500.0, "handles": 100000.0}

    # ConPTY bottleneck: 15/20 = 75%
    val, driver = calculate_composite_metric(15, 50.0, 100, 10000, thresholds)
    assert val == 75.0
    assert driver == "conpty"

    # Memory bottleneck: 90/100 = 90%
    val, driver = calculate_composite_metric(5, 90.0, 100, 10000, thresholds)
    assert val == 90.0
    assert driver == "memory"


def test_collector_thread_lifecycle_and_queue() -> None:
    """Verify collector start, background polling into queue, and clean stop."""
    q: queue.Queue[SystemSnapshot] = queue.Queue(maxsize=10)
    collector = DummyCollector(config={"poll_interval": 0.05}, snapshot_queue=q)

    collector.start()
    time.sleep(0.15)
    collector.stop(timeout=1.0)

    assert not collector._thread.is_alive()
    assert q.qsize() >= 1
    snapshot = q.get_nowait()
    assert isinstance(snapshot, SystemSnapshot)
    assert snapshot.conpty_count == 10


def test_collector_queue_overflow_evicts_oldest() -> None:
    """Verify queue drops oldest element when full."""
    q: queue.Queue[SystemSnapshot] = queue.Queue(maxsize=2)
    collector = DummyCollector(config={"poll_interval": 0.02}, snapshot_queue=q)

    collector.start()
    time.sleep(0.1)
    collector.stop(timeout=1.0)

    assert q.qsize() == 2


def test_collector_unhandled_exception_resilience() -> None:
    """Verify background loop continues after poll_metrics exception."""
    collector = DummyCollector(config={"poll_interval": 0.02}, fail_poll=True)
    collector.start()
    time.sleep(0.08)
    collector.stop(timeout=1.0)

    assert collector.poll_count >= 2
```

---

### 6.6 `tests/unit/test_windows_collector.py` (Add)

**Complete file contents:**

```python
"""Unit test suite for WindowsCollector polling and permission error resilience.

Issue #4: Feature: Windows data collector — ConPTY, processes, memory, handles
"""

from unittest.mock import MagicMock, patch
import pytest

from boostgauge.collectors.windows import WindowsCollector


@pytest.fixture
def mock_psutil() -> Any:
    """Mock psutil process iterator and virtual_memory."""
    with patch("boostgauge.collectors.windows.psutil") as mock_p:
        # Virtual memory mock
        mock_mem = MagicMock()
        mock_mem.percent = 55.0
        mock_p.virtual_memory.return_value = mock_mem
        mock_p.pids.return_value = list(range(1, 101))

        # Process iterator mock
        p1 = MagicMock()
        p1.info = {"name": "conhost.exe", "num_handles": 150, "cmdline": ["conhost.exe"]}
        p2 = MagicMock()
        p2.info = {
            "name": "python.exe",
            "num_handles": 300,
            "cmdline": ["python.exe", "unleashed-c-session.py"],
        }
        mock_p.process_iter.return_value = [p1, p2]
        yield mock_p


def test_windows_collector_poll_metrics(mock_psutil: Any) -> None:
    """Test standard poll_metrics execution on Windows."""
    collector = WindowsCollector(config={"_allow_non_windows_for_testing": True})
    snapshot = collector.poll_metrics()

    assert snapshot.conpty_count == 1
    assert snapshot.process_count == 100
    assert snapshot.memory_percent == 55.0
    assert snapshot.handle_count == 450
    assert snapshot.unleashed_sessions == 1
    assert 0.0 <= snapshot.composite_value <= 100.0


def test_windows_collector_access_denied_handling(mock_psutil: Any) -> None:
    """Test handling of psutil.AccessDenied during process enumeration."""
    import psutil

    def proc_iter_side_effect(*args: Any, **kwargs: Any) -> Any:
        p_denied = MagicMock()
        p_denied.info = {}
        # Accessing properties raises AccessDenied
        type(p_denied).info = property(lambda self: (_ for _ in ()).throw(psutil.AccessDenied(pid=99)))
        return [p_denied]

    mock_psutil.process_iter.side_effect = proc_iter_side_effect

    collector = WindowsCollector(config={"_allow_non_windows_for_testing": True})
    snapshot = collector.poll_metrics()

    assert snapshot.conpty_count == 0
    assert snapshot.handle_count == 0
    assert snapshot.unleashed_sessions == 0
```

---

### 6.7 `tests/contract/test_collector_contract.py` (Add)

**Complete file contents:**

```python
"""Contract test suite verifying DataCollector interface compliance across implementations.

Issue #4: Feature: Windows data collector — ConPTY, processes, memory, handles
"""

import queue
import time
from typing import Type
import pytest

from boostgauge.collector import DataCollector, SystemSnapshot
from boostgauge.collectors.windows import WindowsCollector


def test_collector_contract_interface() -> None:
    """Verify collector class adheres strictly to DataCollector contract."""
    q: queue.Queue[SystemSnapshot] = queue.Queue()
    collector = WindowsCollector(
        config={"poll_interval": 0.05, "_allow_non_windows_for_testing": True},
        snapshot_queue=q,
    )

    assert hasattr(collector, "start")
    assert hasattr(collector, "stop")
    assert hasattr(collector, "poll_metrics")

    # Verify poll_metrics returns valid SystemSnapshot instance
    snapshot = collector.poll_metrics()
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

### 7.1 Configuration & Base Structure

**File:** `src/boostgauge/config.py` (lines 15-40)

```python
class BoostGaugeConfig(TypedDict):
    theme: str
    update_interval_ms: int
    telltale_decay_rate: float
    window_position: WindowPosition
    thresholds: ThresholdsConfig
    telltale_windows: TelltaleWindowsConfig
```

**Relevance:** Dict-based configuration loading, fallback defaults, and `TypedDict` schema conventions used throughout `boostgauge`.

### 7.2 Core Gauge Pure Logic Pattern

**File:** `src/boostgauge/gauge.py` (lines 20-35)

```python
def _validate_render_args(
    value: float,
    size: Tuple[int, int],
    config: Optional[Dict[str, Any]],
) -> Tuple[float, Tuple[int, int]]:
    """Validate metric value bounds (clamped 0-100) and target image dimensions."""
    ...
```

**Relevance:** Defensive bounds checking, default fallback merging, and non-gui pure logic execution patterns.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `import psutil` | PyPI (`psutil >= 7.2.2`) | `src/boostgauge/collectors/windows.py` |
| `from dataclasses import dataclass` | stdlib | `src/boostgauge/collector.py` |
| `import queue` | stdlib | `src/boostgauge/collector.py`, `src/boostgauge/collectors/windows.py` |
| `import threading` | stdlib | `src/boostgauge/collector.py` |
| `import time` | stdlib | `src/boostgauge/collector.py`, `src/boostgauge/collectors/windows.py` |
| `from typing import Any, Dict, Optional, Tuple, TypedDict` | stdlib | All files |

**New Dependencies:** None (uses existing `psutil` dependency from `pyproject.toml`).

## 9. Placeholder

*Reserved for future alignment with LLD section numbering.*

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `WindowsCollector._count_conpty()` | Process list with 3 `conhost.exe` | `conpty_count == 3` |
| T020 | `WindowsCollector.poll_metrics()` | Mocked psutil `mem=45.5`, `pids=150`, `handles=12000` | `process_count == 150`, `memory_percent == 45.5`, `handle_count == 12000` |
| T030 | `WindowsCollector._count_unleashed_sessions()` | Python proc with `unleashed-c-1.py` in cmdline | `unleashed_sessions == 1` |
| T040 | `DataCollector.start()` / `_run_loop()` | Sleep 0.15s with poll_interval=0.05s | Queue receives ≥1 `SystemSnapshot` |
| T050 | `calculate_composite_metric()` | `conpty=15/20` (75%), `memory=45/90` (50%) | `composite_value == 75.0`, `driver == "conpty"` |
| T060 | `WindowsCollector.poll_metrics()` | `psutil.AccessDenied` raised during proc iter | Handled gracefully, returns snapshot without exception |
| T070 | `WindowsCollector.poll_metrics()` benchmark | 10 consecutive `poll_metrics()` calls | Average execution duration < 50ms |
| T080 | `DataCollector._run_loop()` | Full queue (`maxsize=2`) | Evicts oldest snapshot, places latest without block |
| T090 | `DataCollector.stop()` | Call `stop()` on running thread | Thread joins cleanly (`is_alive() == False`) |
| T100 | `DataCollector._run_loop()` | `poll_metrics()` raises `RuntimeError` | Exception logged, loop continues next poll |

## 11. Implementation Notes

### 11.1 Platform Guarding & Test Isolation

`WindowsCollector.__init__` checks `sys.platform == 'win32'`. To permit headless unit testing on Linux/macOS CI runners, an internal parameter `_allow_non_windows_for_testing: True` in `config` allows test instantiation when `psutil` is mocked.

### 11.2 Queue Full Handling Policy

When `snapshot_queue.full()` is `True`, `_run_loop()` executes a non-blocking `get_nowait()` to pop the stalest snapshot prior to `put_nowait()`. This prevents GUI memory growth and thread starvation if the GUI rendering loop is temporarily delayed.

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
| Date | 2026-08-01 |
| Iterations | 1 |
| Finalized | 2026-08-01T05:25:00Z |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #4 |
| Verdict | APPROVED |
| Date | 2026-08-01 |
| Iterations | 1 |
| Finalized | 2026-08-01T10:25:35Z |

### Review Feedback Summary

The revised implementation spec is complete, highly specific, and fully executable by an autonomous AI agent. Complete source code and test implementations are provided for all files. All test assertions trace directly to specified behaviors, and previous review items (code block formatting and contract test instantiation) have been cleanly resolved.
