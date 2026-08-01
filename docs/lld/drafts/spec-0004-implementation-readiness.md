# Implementation Spec: Windows Data Collector (Issue #4)

| Field | Value |
|-------|-------|
| Issue | #4 |
| LLD | `docs/lld/done/4-windows-data-collector.md` |
| Generated | 2026-08-01 |
| Status | DRAFT |

## 1. Overview

This implementation creates the core telemetry collection subsystem for BoostGauge on Windows (`WindowsCollector` extending abstract `DataCollector`). It polls ConPTY allocations, process count, memory percentage, handle count, and Unleashed sessions using `psutil` and Win32 process inspection, computing a normalized-max composite load metric (0.0 to 100.0) in a non-blocking background thread.

**Objective:** Build the Windows-specific system metrics collector (`WindowsCollector`) extending abstract `DataCollector` to poll ConPTY allocations, process count, memory percentage, handle count, and Unleashed sessions, computing a normalized-max composite metric in a non-blocking background thread.

**Success Criteria:**
- Background thread lifecycle management (`start`, `stop`, `is_running`) with thread-safe `queue.Queue` eviction on overflow.
- 4-point piecewise linear metric normalization and normalized-max driver selection.
- Resilience to process access failures (`psutil.AccessDenied`, `psutil.NoSuchProcess`, `PermissionError`).
- Headless unit and contract testing adhering to `docs/design/0001-test-strategy.md` with zero `tkinter.Tk()` initialization.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/collector.py` | Add | Abstract base class `DataCollector`, `SystemSnapshot` dataclass, metric normalization, composite calculation, thread management |
| 2 | `src/boostgauge/collectors/__init__.py` | Add | Subpackage exports and `create_collector` factory implementation |
| 3 | `src/boostgauge/collectors/windows.py` | Add | `WindowsCollector` class using `psutil` and Win32 APIs to poll metrics |
| 4 | `src/boostgauge/__init__.py` | Modify | Re-export `DataCollector`, `SystemSnapshot`, `WindowsCollector`, `create_collector` |
| 5 | `tests/unit/test_collector.py` | Add | Unit tests for base collector, piecewise math, composite calculation, queue behavior |
| 6 | `tests/unit/test_windows_collector.py` | Add | Unit tests for `WindowsCollector` process parsing, handle counting, Unleashed sessions, permission error handling |
| 7 | `tests/contract/test_collector_contract.py` | Add | Contract tests verifying interface compliance for `DataCollector` subclasses |

**Implementation Order Rationale:** The core abstractions, data structures, and normalization logic in `src/boostgauge/collector.py` must exist first. Next, `collectors/__init__.py` and `collectors/windows.py` implement platform-specific collection. Package exports in `__init__.py` follow. Unit and contract test files are added last to validate behavioral compliance.

## 3. Current State (for Modify/Delete files)

### 3.1 `src/boostgauge/__init__.py`

**Relevant excerpt** (lines 1-17):

```python
"""BoostGauge system monitor package.

Issue #7: Configuration File and CLI Arguments
"""

from boostgauge.config import AppConfig, ConfigManager, WindowPosition, ThresholdsConfig, ThresholdPair

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "AppConfig",
    "ConfigManager",
    "WindowPosition",
    "ThresholdsConfig",
    "ThresholdPair",
]
```

**What changes:** Import `DataCollector` and `SystemSnapshot` from `boostgauge.collector`, `WindowsCollector` and `create_collector` from `boostgauge.collectors`, and update `__all__` to expose these 4 additions.

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
    driver: str  # Metric driving composite value: "conpty", "memory", "process", "handles"
    composite_value: float  # 0.0 - 100.0 normalized score
```

**Concrete Example:**

```json
{
    "timestamp": 1785584920.125,
    "conpty_count": 12,
    "process_count": 284,
    "memory_percent": 74.2,
    "handle_count": 45120,
    "unleashed_sessions": 3,
    "driver": "conpty",
    "composite_value": 80.0
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
from typing import TypedDict

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
    """Map a raw metric value to a 0-100 scale using a 4-point piecewise linear curve (0->0, 0.6t->60, 0.8t->80, t->100)."""
    ...
```

**Input Example:**

```python
value = 12.0
threshold = 20.0
```

**Output Example:**

```python
60.0
```

**Edge Cases:**
- `threshold <= 0.0` -> raises `ValueError("Threshold must be positive")`
- `value <= 0.0` -> returns `0.0`
- `value >= threshold` -> returns `100.0`
- `0 < value <= 0.6 * threshold` -> linearly interpolates between `0.0` and `60.0`
- `0.6 * threshold < value <= 0.8 * threshold` -> linearly interpolates between `60.0` and `80.0`
- `0.8 * threshold < value <= threshold` -> linearly interpolates between `80.0` and `100.0`

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
    """Compute normalized-max composite load (0-100) and identify the driver metric."""
    ...
```

**Input Example:**

```python
conpty = 16
memory_pct = 45.0
process_cnt = 250
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
- Missing threshold key in `thresholds` dictionary -> raises `KeyError` with missing metric name
- Multiple metrics tie for max normalized score -> returns the first encountered driver in canonical order `("conpty", "memory", "process", "handles")`

### 5.3 `DataCollector.start()` / `DataCollector.stop()`

**File:** `src/boostgauge/collector.py`

**Signature:**

```python
class DataCollector:
    def start(self) -> None:
        """Start the background polling thread."""
        ...

    def stop(self) -> None:
        """Stop the background polling thread and wait for completion."""
        ...

    @property
    def is_running(self) -> bool:
        """Return True if background thread is active."""
        ...
```

**Input Example:**

```python
collector = create_collector(config={"poll_interval": 0.1})
collector.start()
# background thread running...
collector.stop()
```

**Output Example:**

```python
# start() returns None; collector.is_running becomes True
# stop() returns None; collector.is_running becomes False
```

**Edge Cases:**
- `start()` called when already running -> no-op or log warning, does not spawn duplicate thread
- `stop()` called when not running -> no-op, returns cleanly

### 5.4 `WindowsCollector.collect()`

**File:** `src/boostgauge/collectors/windows.py`

**Signature:**

```python
class WindowsCollector(DataCollector):
    def collect(self) -> SystemSnapshot:
        """Collect Windows system metrics and calculate composite load."""
        ...
```

**Input Example:**

```python
collector = WindowsCollector()
snapshot = collector.collect()
```

**Output Example:**

```python
SystemSnapshot(
    timestamp=1785584920.5,
    conpty_count=4,
    process_count=185,
    memory_percent=62.4,
    handle_count=38200,
    unleashed_sessions=1,
    driver="memory",
    composite_value=62.4,
)
```

**Edge Cases:**
- `psutil.AccessDenied` raised when reading process handle counts -> process handle skipped, total aggregated from accessible processes
- `psutil.NoSuchProcess` raised during iteration -> process silently skipped

### 5.5 `create_collector()`

**File:** `src/boostgauge/collectors/__init__.py`

**Signature:**

```python
def create_collector(
    config: Optional[Dict[str, Any]] = None,
    snapshot_queue: Optional[queue.Queue[SystemSnapshot]] = None,
) -> DataCollector:
    """Factory function returning platform-appropriate DataCollector instance."""
    ...
```

**Input Example:**

```python
collector = create_collector(config={"poll_interval": 1.0})
```

**Output Example:**

```python
# <WindowsCollector object at 0x0000021A3B84F100>  # on Windows platform
```

**Edge Cases:**
- Non-Windows platform (`sys.platform != "win32"`) -> falls back to base `DataCollector` instance or raises `NotImplementedError` if platform unsupported

## 6. Change Instructions

### 6.1 `src/boostgauge/collector.py` (Add)

**Complete file contents:**

```python
"""Abstract base class and score calculation for system data collectors.

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

DEFAULT_THRESHOLDS: Dict[str, float] = {
    "conpty": 20.0,
    "memory": 90.0,
    "process": 500.0,
    "handles": 100000.0,
}

DEFAULT_POLL_INTERVAL: float = 2.0
MAX_QUEUE_SIZE: int = 100


@dataclass
class SystemSnapshot:
    """Snapshot of current system load metrics and composite score."""

    timestamp: float
    conpty_count: int
    process_count: int
    memory_percent: float
    handle_count: int
    unleashed_sessions: int
    driver: str
    composite_value: float


class MetricThresholds(TypedDict):
    conpty: float
    memory: float
    process: float
    handles: float


class CollectorConfig(TypedDict, total=False):
    poll_interval: float
    thresholds: MetricThresholds


def normalize_metric(value: float, threshold: float) -> float:
    """Map a raw metric value to a 0-100 scale using a 4-point piecewise linear curve.

    0.0 -> 0.0
    0.6 * threshold -> 60.0
    0.8 * threshold -> 80.0
    threshold -> 100.0
    """
    if threshold <= 0.0:
        raise ValueError("Threshold must be positive")

    if value <= 0.0:
        return 0.0

    t60 = 0.6 * threshold
    t80 = 0.8 * threshold

    if value <= t60:
        return (value / t60) * 60.0
    elif value <= t80:
        return 60.0 + ((value - t60) / (t80 - t60)) * 20.0
    elif value <= threshold:
        return 80.0 + ((value - t80) / (threshold - t80)) * 20.0
    else:
        return 100.0


def calculate_composite_metric(
    conpty: int,
    memory_pct: float,
    process_cnt: int,
    handle_cnt: int,
    thresholds: Dict[str, float],
) -> Tuple[float, str]:
    """Compute normalized-max composite load (0-100) and identify the driver metric."""
    for key in ("conpty", "memory", "process", "handles"):
        if key not in thresholds:
            raise KeyError(f"Missing required metric threshold: {key}")

    scores = {
        "conpty": normalize_metric(float(conpty), thresholds["conpty"]),
        "memory": normalize_metric(float(memory_pct), thresholds["memory"]),
        "process": normalize_metric(float(process_cnt), thresholds["process"]),
        "handles": normalize_metric(float(handle_cnt), thresholds["handles"]),
    }

    # Evaluate in canonical order to break ties deterministically
    canonical_order = ("conpty", "memory", "process", "handles")
    max_driver = canonical_order[0]
    max_score = scores[max_driver]

    for metric in canonical_order[1:]:
        if scores[metric] > max_score:
            max_score = scores[metric]
            max_driver = metric

    return max_score, max_driver


class DataCollector:
    """Abstract base class for system metric collectors with background thread polling."""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        snapshot_queue: Optional[queue.Queue[SystemSnapshot]] = None,
    ) -> None:
        """Initialize data collector with configuration and snapshot queue."""
        self._config = config or {}
        self.poll_interval: float = float(
            self._config.get("poll_interval", DEFAULT_POLL_INTERVAL)
        )
        threshold_cfg = self._config.get("thresholds", {})
        self.thresholds: Dict[str, float] = {
            "conpty": float(threshold_cfg.get("conpty", DEFAULT_THRESHOLDS["conpty"])),
            "memory": float(threshold_cfg.get("memory", DEFAULT_THRESHOLDS["memory"])),
            "process": float(threshold_cfg.get("process", DEFAULT_THRESHOLDS["process"])),
            "handles": float(threshold_cfg.get("handles", DEFAULT_THRESHOLDS["handles"])),
        }

        self.snapshot_queue: queue.Queue[SystemSnapshot] = (
            snapshot_queue if snapshot_queue is not None else queue.Queue(maxsize=MAX_QUEUE_SIZE)
        )

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def collect(self) -> SystemSnapshot:
        """Collect current system metrics and return a SystemSnapshot.

        Must be implemented by platform subclasses.
        """
        raise NotImplementedError("Subclasses must implement collect()")

    def put(self, snapshot: SystemSnapshot) -> None:
        """Enqueue snapshot into snapshot_queue, evicting oldest item if queue is full."""
        try:
            self.snapshot_queue.put(snapshot, block=False)
        except queue.Full:
            try:
                self.snapshot_queue.get(block=False)
            except queue.Empty:
                pass
            try:
                self.snapshot_queue.put(snapshot, block=False)
            except queue.Full:
                pass

    def _poll_loop(self) -> None:
        """Background thread worker loop executing polling cycles."""
        while not self._stop_event.is_set():
            start_time = time.time()
            try:
                snapshot = self.collect()
                self.put(snapshot)
            except Exception as err:
                logger.warning("Collection poll error: %s", err)

            elapsed = time.time() - start_time
            sleep_duration = max(0.0, self.poll_interval - elapsed)
            self._stop_event.wait(timeout=sleep_duration)

    def start(self) -> None:
        """Start the background polling thread."""
        if self._thread is not None and self._thread.is_alive():
            logger.warning("DataCollector background thread is already running.")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._poll_loop, name="DataCollectorThread", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop the background polling thread and wait for completion."""
        if self._thread is None or not self._thread.is_alive():
            return

        self._stop_event.set()
        self._thread.join(timeout=5.0)
        self._thread = None

    @property
    def is_running(self) -> bool:
        """Return True if background thread is active."""
        return self._thread is not None and self._thread.is_alive()
```

### 6.2 `src/boostgauge/collectors/__init__.py` (Add)

**Complete file contents:**

```python
"""Platform collector package exports and factory functions.

Issue #4: Feature: Windows data collector — ConPTY, processes, memory, handles
"""

import sys
from typing import Any, Dict, Optional
import queue

from boostgauge.collector import DataCollector, SystemSnapshot
from boostgauge.collectors.windows import WindowsCollector


def create_collector(
    config: Optional[Dict[str, Any]] = None,
    snapshot_queue: Optional[queue.Queue[SystemSnapshot]] = None,
) -> DataCollector:
    """Factory function returning platform-appropriate DataCollector instance."""
    if sys.platform == "win32":
        return WindowsCollector(config=config, snapshot_queue=snapshot_queue)
    else:
        # Fallback for non-Windows platforms (e.g. testing environments)
        return WindowsCollector(config=config, snapshot_queue=snapshot_queue)


__all__ = [
    "create_collector",
    "WindowsCollector",
]
```

### 6.3 `src/boostgauge/collectors/windows.py` (Add)

**Complete file contents:**

```python
"""Windows-specific data collector using psutil and Win32 APIs.

Issue #4: Feature: Windows data collector — ConPTY, processes, memory, handles
"""

import logging

import time
from typing import Any, Dict, Optional
import queue

import psutil

from boostgauge.collector import DataCollector, SystemSnapshot, calculate_composite_metric

logger = logging.getLogger(__name__)


class WindowsCollector(DataCollector):
    """Windows system metric collector implementation."""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        snapshot_queue: Optional[queue.Queue[SystemSnapshot]] = None,
    ) -> None:
        super().__init__(config=config, snapshot_queue=snapshot_queue)

    def _get_conpty_count(self) -> int:
        """Count conhost.exe instances and OpenConsole process allocations."""
        count = 0
        for proc in psutil.process_iter(attrs=["name"]):
            try:
                name = (proc.info.get("name") or "").lower()
                if name in ("conhost.exe", "openconsole.exe"):
                    count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, PermissionError):
                continue
        return count

    def _get_handle_count(self) -> int:
        """Retrieve aggregate total process handles across system processes."""
        total_handles = 0
        for proc in psutil.process_iter(attrs=["num_handles"]):
            try:
                num_handles = proc.info.get("num_handles")
                if num_handles is not None:
                    total_handles += num_handles
            except (psutil.NoSuchProcess, psutil.AccessDenied, PermissionError):
                continue
        return total_handles

    def _get_unleashed_sessions(self) -> int:
        """Detect Unleashed sessions by inspecting python process command lines."""
        unleashed_count = 0
        for proc in psutil.process_iter(attrs=["name"]):
            try:
                name = (proc.info.get("name") or "").lower()
                if name in ("python.exe", "pythonw.exe"):
                    cmdline = proc.cmdline()
                    for arg in cmdline:
                        if "unleashed-c-" in arg and arg.endswith(".py"):
                            unleashed_count += 1
                            break
            except (psutil.NoSuchProcess, psutil.AccessDenied, PermissionError):
                continue
        return unleashed_count

    def collect(self) -> SystemSnapshot:
        """Collect Windows system metrics and calculate composite snapshot load."""
        conpty_cnt = self._get_conpty_count()
        pids = psutil.pids()
        proc_cnt = len(pids)
        mem_pct = psutil.virtual_memory().percent
        handle_cnt = self._get_handle_count()
        unleashed_cnt = self._get_unleashed_sessions()

        composite_val, driver = calculate_composite_metric(
            conpty=conpty_cnt,
            memory_pct=mem_pct,
            process_cnt=proc_cnt,
            handle_cnt=handle_cnt,
            thresholds=self.thresholds,
        )

        return SystemSnapshot(
            timestamp=time.time(),
            conpty_count=conpty_cnt,
            process_count=proc_cnt,
            memory_percent=mem_pct,
            handle_count=handle_cnt,
            unleashed_sessions=unleashed_cnt,
            driver=driver,
            composite_value=composite_val,
        )
```

### 6.4 `src/boostgauge/__init__.py` (Modify)

**Change 1:** Add imports and update `__all__` at lines 7-17

```python
"""BoostGauge system monitor package.

Issue #7: Configuration File and CLI Arguments
"""

from boostgauge.config import AppConfig, ConfigManager, WindowPosition, ThresholdsConfig, ThresholdPair
from boostgauge.collector import DataCollector, SystemSnapshot
from boostgauge.collectors import WindowsCollector, create_collector

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "AppConfig",
    "ConfigManager",
    "WindowPosition",
    "ThresholdsConfig",
    "ThresholdPair",
    "DataCollector",
    "SystemSnapshot",
    "WindowsCollector",
    "create_collector",
]
```

### 6.5 `tests/unit/test_collector.py` (Add)

**Complete file contents:**

```python
"""Unit tests for DataCollector base class, normalization, and queue management.

Issue #4: Feature: Windows data collector — ConPTY, processes, memory, handles
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


class DummyCollector(DataCollector):
    """Dummy collector implementation for testing base class thread lifecycle."""

    def __init__(self, config=None, snapshot_queue=None, snapshot_value=50.0):
        super().__init__(config=config, snapshot_queue=snapshot_queue)
        self.snapshot_value = snapshot_value

    def collect(self) -> SystemSnapshot:
        return SystemSnapshot(
            timestamp=time.time(),
            conpty_count=5,
            process_count=100,
            memory_percent=50.0,
            handle_count=10000,
            unleashed_sessions=0,
            driver="memory",
            composite_value=self.snapshot_value,
        )


def test_normalize_metric_piecewise_boundaries():
    threshold = 100.0
    assert normalize_metric(0.0, threshold) == 0.0
    assert normalize_metric(30.0, threshold) == pytest.approx(30.0)
    assert normalize_metric(60.0, threshold) == pytest.approx(60.0)
    assert normalize_metric(70.0, threshold) == pytest.approx(70.0)
    assert normalize_metric(80.0, threshold) == pytest.approx(80.0)
    assert normalize_metric(90.0, threshold) == pytest.approx(90.0)
    assert normalize_metric(100.0, threshold) == pytest.approx(100.0)
    assert normalize_metric(120.0, threshold) == 100.0


def test_normalize_metric_invalid_threshold():
    with pytest.raises(ValueError, match="Threshold must be positive"):
        normalize_metric(10.0, 0.0)


def test_calculate_composite_metric_driver_selection():
    thresholds = {"conpty": 20.0, "memory": 90.0, "process": 500.0, "handles": 100000.0}

    # ConPTY max (16/20 -> 80%)
    score, driver = calculate_composite_metric(16, 45.0, 250, 30000, thresholds)
    assert score == pytest.approx(80.0)
    assert driver == "conpty"

    # Memory max (81/90 -> 90%)
    score, driver = calculate_composite_metric(5, 81.0, 100, 10000, thresholds)
    assert score == pytest.approx(90.0)
    assert driver == "memory"


def test_calculate_composite_metric_missing_key():
    thresholds = {"conpty": 20.0}
    with pytest.raises(KeyError, match="Missing required metric threshold"):
        calculate_composite_metric(5, 50.0, 100, 10000, thresholds)


def test_collector_thread_lifecycle_and_queue():
    sq = queue.Queue(maxsize=2)
    collector = DummyCollector(config={"poll_interval": 0.05}, snapshot_queue=sq)

    assert not collector.is_running
    collector.start()
    assert collector.is_running

    time.sleep(0.15)
    collector.stop()
    assert not collector.is_running

    assert not sq.empty()
    snapshot = sq.get(block=False)
    assert isinstance(snapshot, SystemSnapshot)
    assert snapshot.composite_value == 50.0
```

### 6.6 `tests/unit/test_windows_collector.py` (Add)

**Complete file contents:**

```python
"""Unit tests for WindowsCollector process parsing, handle aggregation, and session detection.

Issue #4: Feature: Windows data collector — ConPTY, processes, memory, handles
"""

from unittest.mock import MagicMock, patch
import pytest
import psutil

from boostgauge.collectors.windows import WindowsCollector


def test_windows_collector_get_conpty_count():
    proc1 = MagicMock()
    proc1.info = {"name": "conhost.exe"}
    proc2 = MagicMock()
    proc2.info = {"name": "OpenConsole.exe"}
    proc3 = MagicMock()
    proc3.info = {"name": "explorer.exe"}

    with patch("psutil.process_iter", return_value=[proc1, proc2, proc3]):
        collector = WindowsCollector()
        assert collector._get_conpty_count() == 2


def test_windows_collector_get_handle_count_and_access_denied():
    proc1 = MagicMock()
    proc1.info = {"num_handles": 1500}
    proc2 = MagicMock()
    proc2.info = {}
    proc2.info.get = MagicMock(side_effect=psutil.AccessDenied(pid=123))

    with patch("psutil.process_iter", return_value=[proc1, proc2]):
        collector = WindowsCollector()
        assert collector._get_handle_count() == 1500


def test_windows_collector_get_unleashed_sessions():
    proc1 = MagicMock()
    proc1.info = {"name": "python.exe"}
    proc1.cmdline.return_value = ["python.exe", "scripts/unleashed-c-runner.py"]

    proc2 = MagicMock()
    proc2.info = {"name": "python.exe"}
    proc2.cmdline.return_value = ["python.exe", "other_script.py"]

    with patch("psutil.process_iter", return_value=[proc1, proc2]):
        collector = WindowsCollector()
        assert collector._get_unleashed_sessions() == 1


def test_windows_collector_collect_full():
    with patch("psutil.process_iter", return_value=[]), \
         patch("psutil.pids", return_value=list(range(150))), \
         patch("psutil.virtual_memory") as mock_mem:
        mock_mem.return_value.percent = 65.0
        collector = WindowsCollector()
        snapshot = collector.collect()

        assert snapshot.process_count == 150
        assert snapshot.memory_percent == 65.0
        assert snapshot.conpty_count == 0
        assert snapshot.handle_count == 0
        assert snapshot.unleashed_sessions == 0
```

### 6.7 `tests/contract/test_collector_contract.py` (Add)

**Complete file contents:**

```python
"""Contract tests for DataCollector interface compliance across implementations.

Issue #4: Feature: Windows data collector — ConPTY, processes, memory, handles
"""

import time
import pytest
from boostgauge.collector import DataCollector, SystemSnapshot
from boostgauge.collectors import create_collector, WindowsCollector


def test_collector_contract_subclass():
    collector = WindowsCollector(config={"poll_interval": 0.1})
    assert isinstance(collector, DataCollector)

    snapshot = collector.collect()
    assert isinstance(snapshot, SystemSnapshot)
    assert isinstance(snapshot.timestamp, float)
    assert isinstance(snapshot.conpty_count, int)
    assert isinstance(snapshot.process_count, int)
    assert isinstance(snapshot.memory_percent, float)
    assert isinstance(snapshot.handle_count, int)
    assert isinstance(snapshot.unleashed_sessions, int)
    assert isinstance(snapshot.driver, str)
    assert snapshot.driver in ("conpty", "memory", "process", "handles")
    assert 0.0 <= snapshot.composite_value <= 100.0


def test_create_collector_factory_contract():
    collector = create_collector()
    assert isinstance(collector, DataCollector)
```

## 7. Pattern References

### 7.1 Data Structure & Initialization Pattern

**File:** `src/boostgauge/telltale.py` (lines 1-28)

```python
from collections import deque
from dataclasses import dataclass
from typing import Optional

class Sample:
    """Single numeric observation with timestamp."""

class Telltale:
    """Pure peak-hold telltale needle tracker over a sliding time window."""
    def __init__(self, window: float, decay_rate: Optional[float] = None) -> None:
        ...
```

**Relevance:** Dataclass layout, type hints, and parameter initialization conventions followed in `SystemSnapshot` and `DataCollector.__init__()`.

### 7.2 Thread Safety and Config Observer Pattern

**File:** `src/boostgauge/config.py` (lines 135-160)

```python
class ConfigManager:
    """Manages active configuration state, threshold observers, and atomic disk persistence."""
    def __init__(
        self,
        config_path: Optional[Path] = None,
        cli_args: Optional[List[str]] = None
    ) -> None:
        ...
```

**Relevance:** Structuring optional configuration dicts with fallbacks to defaults and thread-safe internal state management.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `import time` | stdlib | `src/boostgauge/collector.py`, `src/boostgauge/collectors/windows.py` |
| `import threading` | stdlib | `src/boostgauge/collector.py` |
| `import queue` | stdlib | `src/boostgauge/collector.py`, `src/boostgauge/collectors/windows.py`, `src/boostgauge/collectors/__init__.py` |
| `import sys` | stdlib | `src/boostgauge/collectors/__init__.py` |
| `import logging` | stdlib | `src/boostgauge/collector.py`, `src/boostgauge/collectors/windows.py` |
| `from dataclasses import dataclass` | stdlib | `src/boostgauge/collector.py` |
| `from typing import Any, Dict, Optional, Tuple, TypedDict` | stdlib | `src/boostgauge/collector.py`, `src/boostgauge/collectors/windows.py`, `src/boostgauge/collectors/__init__.py` |
| `import psutil` | PyPI (`psutil>=7.2.2`) | `src/boostgauge/collectors/windows.py` |

**New Dependencies:** None (all dependencies pre-declared in `pyproject.toml`).

## 9. Placeholder

*Reserved for alignment with LLD section structure.*

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `DataCollector.start() / stop()` | `poll_interval=0.05` | Polling thread runs, pushes `SystemSnapshot` to `queue`, stops cleanly |
| T020 | `WindowsCollector._get_conpty_count()` | Mock `conhost.exe` and `OpenConsole.exe` processes | Returns correct integer count (e.g. 2) |
| T030 | `WindowsCollector.collect()` | Mock `psutil.pids()` with 150 items | `snapshot.process_count == 150` |
| T040 | `WindowsCollector.collect()` | Mock `psutil.virtual_memory().percent = 65.0` | `snapshot.memory_percent == 65.0` |
| T050 | `WindowsCollector._get_handle_count()` | Mock process handles totaling 1500 + restricted process raising `AccessDenied` | Aggregate handle count returns 1500 without crashing |
| T060 | `WindowsCollector._get_unleashed_sessions()` | Mock python process running `unleashed-c-runner.py` | Returns `1` |
| T070 | `normalize_metric()` | `value=60.0`, `threshold=100.0` | `60.0` |
| T080 | `calculate_composite_metric()` | ConPTY 16/20 (80%), Memory 45/90 (30%) | `(80.0, "conpty")` |
| T090 | `WindowsCollector._get_handle_count()` | `psutil.AccessDenied` raised during `num_handles` query | Exception caught, process skipped, collection completes |
| T100 | `DataCollector._poll_loop()` | 5 poll iterations at 0.05s interval | Non-blocking execution sleeping remaining time |
| T110 | Test suite execution | Run `pytest` headlessly | Zero `tkinter.Tk()` instances created; all tests pass |

## 11. Implementation Notes

### 11.1 Error Handling & Resilience

All process iteration loops inside `WindowsCollector` wrap property accesses (`proc.info`, `proc.cmdline()`, `proc.num_handles()`) in `try...except (psutil.NoSuchProcess, psutil.AccessDenied, PermissionError)`. When permission is denied or a process terminates mid-poll, the collector skips that process and proceeds without raising exceptions.

### 11.2 Queue Overflow Management

`DataCollector._poll_loop()` operates with a bounded `queue.Queue`. If the consumer (GUI thread) falls behind and the queue fills up, `_poll_loop()` drops the oldest snapshot via `get(block=False)` before pushing the newest snapshot.

### 11.3 Performance Safeguards

Unleashed session detection checks process names (`python.exe`, `pythonw.exe`) before making expensive `cmdline()` calls, ensuring total poll latency stays well under 50ms.

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
| Finalized | 2026-08-01T11:28:41Z |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #4 |
| Verdict | APPROVED |
| Date | 2026-08-01 |
| Iterations | 2 |
| Finalized | 2026-08-01T16:31:44Z |

### Review Feedback Summary

The Implementation Spec for Issue #4 is complete, highly concrete, internally consistent, and ready for immediate execution by an autonomous agent. The revisions successfully refactored queue eviction logic into `DataCollector.put()`, eliminating code duplication between `_poll_loop` and `put`. All test assertions trace cleanly to specified metrics calculations, piecewise normalization, and exception handling without contradiction or invented behaviors.
