# Implementation Spec: Windows data collector — ConPTY, processes, memory, handles

<!-- Metadata -->
| Field | Value |
|-------|-------|
| Issue | #4 |
| LLD | `docs/lld/done/0004-windows-data-collector.md` |
| Generated | 2026-08-10 |
| Status | DRAFT |

## 1. Overview

Build the Windows-specific data collector that polls system metrics via a single process sweep and feeds them to the gauge.

**Objective:** Build the Windows-specific data collector that polls system metrics via a single process sweep and feeds them to the gauge.

**Success Criteria:**
1. The Windows collector derives ConPTY count, process count, handle count, and unleashed session count from a SINGLE `psutil.process_iter` sweep per tick.
2. The memory percentage is measured using `psutil.virtual_memory().percent` outside the sweep.
3. The collector's CPU overhead must be < 1% at a 2.0-second polling interval.
4. Process sweep handles `NoSuchProcess` and `AccessDenied` exceptions gracefully without crashing.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/collector.py` | Add | Define `SystemSnapshot` dataclass and `DataCollector` abstract base class. |
| 2 | `src/boostgauge/collectors/windows.py` | Add | Implement `WindowsCollector` adhering to ADR 0001 (single sweep). |
| 3 | `tests/unit/test_windows_collector.py` | Add | Unit tests verifying the single sweep mandate and metric accuracy. |

**Implementation Order Rationale:** `collector.py` must be implemented first because it defines the core abstractions (`DataCollector`) and data structures (`SystemSnapshot`) that the Windows implementation relies on. `windows.py` implements the behavior. Finally, the test file `test_windows_collector.py` depends on the implementation.

## 3. Current State (for Modify/Delete files)

*No files are being modified or deleted in this implementation. All files are new additions. Thus, this section is inherently satisfied.*

## 4. Data Structures

### 4.1 SystemSnapshot

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
    driver: str
    composite_value: float
```

**Concrete Example:**

```json
{
    "timestamp": 1691652570.123,
    "conpty_count": 4,
    "process_count": 256,
    "memory_percent": 45.2,
    "handle_count": 12050,
    "unleashed_sessions": 2,
    "driver": "conpty",
    "composite_value": 75.5
}
```

## 5. Function Specifications

### 5.1 `WindowsCollector._collect_snapshot()`

**File:** `src/boostgauge/collectors/windows.py`

**Signature:**

```python
def _collect_snapshot(self) -> SystemSnapshot:
    """Performs the single process sweep and memory read to generate a snapshot."""
    ...
```

**Input Example:**

```python
# Function takes no external arguments but uses internal state
self._thresholds = {
    "conpty": 10.0,
    "memory": 100.0,
    "processes": 500.0,
    "handles": 50000.0
}
self._python_interpreters = {"python.exe", "pythonw.exe"}
```

**Output Example:**

```python
SystemSnapshot(
    timestamp=1691652570.123,
    conpty_count=2,
    process_count=180,
    memory_percent=60.0,
    handle_count=15000,
    unleashed_sessions=1,
    driver="memory",
    composite_value=60.0
)
```

**Edge Cases:**
- Process raises `psutil.NoSuchProcess` when `.info` is accessed -> Exception is caught, loop continues, and process is ignored.
- Process raises `psutil.AccessDenied` when `.info` is accessed -> Exception is caught, loop continues, and process is ignored.
- Empty `cmdline` or `name` returned from `psutil` -> Defaults to empty strings/lists, preventing `TypeError`.

### 5.2 `WindowsCollector._normalize()`

**File:** `src/boostgauge/collectors/windows.py`

**Signature:**

```python
def _normalize(self, value: float, threshold: float) -> float:
    """Map raw metric to 0-100 gauge scale."""
    ...
```

**Input Example:**

```python
value = 250.0
threshold = 500.0
```

**Output Example:**

```python
50.0
```

**Edge Cases:**
- `value >= threshold` -> returns `100.0` to cap the maximum value.
- `threshold <= 0` -> returns `100.0` to avoid `ZeroDivisionError`.

## 6. Change Instructions

### 6.1 `src/boostgauge/collector.py` (Add)

**Complete file contents:**

```python
"""Base data collector abstractions.

Issue #4: Windows data collector — ConPTY, processes, memory, handles
"""

import abc
from dataclasses import dataclass

@dataclass
class SystemSnapshot:
    """Snapshot of system resource metrics at a point in time."""
    timestamp: float
    conpty_count: int
    process_count: int
    memory_percent: float
    handle_count: int
    unleashed_sessions: int
    driver: str
    composite_value: float


class DataCollector(abc.ABC):
    """Abstract base class for system metric collectors."""
    
    @abc.abstractmethod
    def start(self) -> None:
        """Start the background polling thread."""
        pass # pragma: no cover

    @abc.abstractmethod
    def stop(self) -> None:
        """Signal the background thread to stop and wait for it to exit."""
        pass # pragma: no cover
```

### 6.2 `src/boostgauge/collectors/windows.py` (Add)

**Complete file contents:**

```python
"""Windows-specific system metric collector.

Issue #4: Windows data collector — ConPTY, processes, memory, handles
"""

import queue
import threading
import time
from typing import Dict, Optional

import psutil

from boostgauge.collector import DataCollector, SystemSnapshot


class WindowsCollector(DataCollector):
    def __init__(
        self, 
        target_queue: queue.Queue, 
        poll_interval: float = 2.0, 
        thresholds: Optional[Dict[str, float]] = None
    ):
        """Initialize the collector with a target queue and thresholds for normalization."""
        self._target_queue = target_queue
        self.poll_interval = poll_interval
        self._thresholds = thresholds or {
            "conpty": 10.0,
            "memory": 100.0,
            "processes": 500.0,
            "handles": 50000.0
        }
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._python_interpreters = {"python.exe", "pythonw.exe"}

    def start(self) -> None:
        """Start the background polling thread."""
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Signal the background thread to stop and wait for it to exit."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join()

    def _poll_loop(self) -> None:
        """Background thread loop that polls metrics every interval."""
        while not self._stop_event.is_set():
            snapshot = self._collect_snapshot()
            try:
                self._target_queue.put_nowait(snapshot)
            except queue.Full:
                pass
            
            # Wait for poll_interval, interrupting if stop is requested
            self._stop_event.wait(self.poll_interval)

    def _collect_snapshot(self) -> SystemSnapshot:
        """Performs the single process sweep and memory read to generate a snapshot."""
        conpty = 0
        process_count = 0
        handles = 0
        unleashed = 0
        
        for proc in psutil.process_iter(attrs=["name", "num_handles", "cmdline"]):
            try:
                info = proc.info
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

            process_count += 1
            
            name = info.get("name")
            name_lower = name.lower() if name else ""
            
            if name_lower in ("conhost.exe", "openconsole.exe"):
                conpty += 1
                
            num_handles = info.get("num_handles")
            if num_handles is not None:
                handles += num_handles
                
            if name_lower in self._python_interpreters:
                cmdline = info.get("cmdline") or []
                if any("unleashed-c-" in arg for arg in cmdline):
                    unleashed += 1

        memory = psutil.virtual_memory().percent
        
        norm_conpty = self._normalize(conpty, self._thresholds.get("conpty", 10.0))
        norm_mem = self._normalize(memory, self._thresholds.get("memory", 100.0))
        norm_proc = self._normalize(process_count, self._thresholds.get("processes", 500.0))
        norm_handles = self._normalize(handles, self._thresholds.get("handles", 50000.0))
        
        metrics = {
            "conpty": norm_conpty,
            "memory": norm_mem,
            "processes": norm_proc,
            "handles": norm_handles
        }
        
        driver = max(metrics.items(), key=lambda x: x[1])[0]
        composite_value = metrics[driver]

        return SystemSnapshot(
            timestamp=time.time(),
            conpty_count=conpty,
            process_count=process_count,
            memory_percent=memory,
            handle_count=handles,
            unleashed_sessions=unleashed,
            driver=driver,
            composite_value=composite_value
        )

    def _normalize(self, value: float, threshold: float) -> float:
        """Map raw metric to 0-100 gauge scale."""
        if threshold <= 0:
            return 100.0
        normalized = (float(value) / threshold) * 100.0
        return min(100.0, normalized)
```

### 6.3 `tests/unit/test_windows_collector.py` (Add)

**Complete file contents:**

```python
"""Unit tests for the Windows collector.

Issue #4: Windows data collector
"""

import queue
import time
from unittest import mock

import pytest
import psutil

from boostgauge.collectors.windows import WindowsCollector


@pytest.fixture
def collector():
    q = queue.Queue()
    return WindowsCollector(target_queue=q, poll_interval=2.0)


def test_single_sweep_validation(collector):
    """T010: psutil.process_iter called exactly once per snapshot."""
    with mock.patch("psutil.process_iter", return_value=[]) as mock_iter, \
         mock.patch("psutil.virtual_memory") as mock_mem:
        mock_mem.return_value.percent = 50.0
        
        collector._collect_snapshot()
        
        mock_iter.assert_called_once_with(attrs=["name", "num_handles", "cmdline"])


def test_memory_read_validation(collector):
    """T020: virtual_memory called once per snapshot."""
    with mock.patch("psutil.process_iter", return_value=[]), \
         mock.patch("psutil.virtual_memory") as mock_mem:
        mock_mem.return_value.percent = 50.0
        
        snapshot = collector._collect_snapshot()
        
        mock_mem.assert_called_once()
        assert snapshot.memory_percent == 50.0


def test_mid_walk_exception_handling(collector):
    """T030: Process raises NoSuchProcess or AccessDenied; thread skips and continues."""
    mock_proc1 = mock.Mock()
    type(mock_proc1).info = mock.PropertyMock(side_effect=psutil.NoSuchProcess(1))
    
    mock_proc2 = mock.Mock()
    type(mock_proc2).info = mock.PropertyMock(side_effect=psutil.AccessDenied(2))
    
    mock_proc3 = mock.Mock()
    type(mock_proc3).info = mock.PropertyMock(return_value={"name": "test.exe", "num_handles": 10, "cmdline": []})

    with mock.patch("psutil.process_iter", return_value=[mock_proc1, mock_proc2, mock_proc3]), \
         mock.patch("psutil.virtual_memory") as mock_mem:
        mock_mem.return_value.percent = 10.0
        
        snapshot = collector._collect_snapshot()
        
        assert snapshot.process_count == 1
        assert snapshot.handle_count == 10


def test_process_counting(collector):
    """T040: Returns total count of processed rows."""
    procs = []
    for _ in range(5):
        m = mock.Mock()
        type(m).info = mock.PropertyMock(return_value={"name": "dummy.exe", "num_handles": 1, "cmdline": []})
        procs.append(m)
        
    with mock.patch("psutil.process_iter", return_value=procs), \
         mock.patch("psutil.virtual_memory") as mock_mem:
        mock_mem.return_value.percent = 10.0
        
        snapshot = collector._collect_snapshot()
        
        assert snapshot.process_count == 5


def test_conpty_filtering(collector):
    """T050: Matches case-insensitive conhost.exe and openconsole.exe."""
    names = ["ConHost.exe", "openconsole.exe", "other.exe"]
    procs = []
    for name in names:
        m = mock.Mock()
        type(m).info = mock.PropertyMock(return_value={"name": name, "num_handles": 1, "cmdline": []})
        procs.append(m)
        
    with mock.patch("psutil.process_iter", return_value=procs), \
         mock.patch("psutil.virtual_memory") as mock_mem:
        mock_mem.return_value.percent = 10.0
        
        snapshot = collector._collect_snapshot()
        
        assert snapshot.conpty_count == 2


def test_handle_aggregation(collector):
    """T060: Sums num_handles across all read processes."""
    procs = []
    for handles in [10, 20]:
        m = mock.Mock()
        type(m).info = mock.PropertyMock(return_value={"name": "dummy.exe", "num_handles": handles, "cmdline": []})
        procs.append(m)
        
    with mock.patch("psutil.process_iter", return_value=procs), \
         mock.patch("psutil.virtual_memory") as mock_mem:
        mock_mem.return_value.percent = 10.0
        
        snapshot = collector._collect_snapshot()
        
        assert snapshot.handle_count == 30


def test_unleashed_session_matching(collector):
    """T070: Matches python interpreters running unleashed-c-*.py."""
    mock_proc1 = mock.Mock()
    type(mock_proc1).info = mock.PropertyMock(return_value={
        "name": "pythonw.exe", 
        "num_handles": 10, 
        "cmdline": ["pythonw.exe", "unleashed-c-123.py"]
    })
    
    with mock.patch("psutil.process_iter", return_value=[mock_proc1]), \
         mock.patch("psutil.virtual_memory") as mock_mem:
        mock_mem.return_value.percent = 10.0
        
        snapshot = collector._collect_snapshot()
        
        assert snapshot.unleashed_sessions == 1


def test_background_thread_lifecycle(collector):
    """T080: Starts, pushes to queue, and stops gracefully."""
    with mock.patch.object(collector, "_collect_snapshot") as mock_collect:
        mock_collect.return_value = "fake_snapshot"
        collector.poll_interval = 0.01  # Fast poll for test
        
        collector.start()
        time.sleep(0.05)
        collector.stop()
        
        assert mock_collect.called
        assert not collector._target_queue.empty()
        assert collector._target_queue.get() == "fake_snapshot"
        assert not collector._thread.is_alive()


def test_normalized_max_logic():
    """T090: Returns the max normalized metric and its driver name."""
    q = queue.Queue()
    # Thresholds: conpty=10, mem=100, proc=100, handles=100
    collector = WindowsCollector(target_queue=q, poll_interval=2.0, thresholds={
        "conpty": 10.0,
        "memory": 100.0,
        "processes": 100.0,
        "handles": 100.0
    })
    
    mock_proc = mock.Mock()
    # 5 conpty = 50% composite score
    type(mock_proc).info = mock.PropertyMock(return_value={"name": "conhost.exe", "num_handles": 0, "cmdline": []})
    
    with mock.patch("psutil.process_iter", return_value=[mock_proc]*5), \
         mock.patch("psutil.virtual_memory") as mock_mem:
        # memory = 10%
        mock_mem.return_value.percent = 10.0
        
        snapshot = collector._collect_snapshot()
        
        assert snapshot.driver == "conpty"
        assert snapshot.composite_value == 50.0


def test_default_config_validation():
    """T100: Polling interval defaults to 2.0s."""
    q = queue.Queue()
    collector = WindowsCollector(target_queue=q)
    assert collector.poll_interval == 2.0


@pytest.mark.live
def test_cpu_overhead():
    """T110: CPU < 1% over interval."""
    # Live execution test ensuring the background thread completes intervals properly.
    q = queue.Queue()
    collector = WindowsCollector(target_queue=q, poll_interval=2.0)
    
    process = psutil.Process()
    process.cpu_percent(interval=None)
    
    start_time = time.time()
    collector.start()
    time.sleep(2.5)
    collector.stop()
    duration = time.time() - start_time
    
    cpu_usage = process.cpu_percent(interval=None)
    
    assert duration >= 2.5
    assert cpu_usage < 1.0
    assert not collector._thread.is_alive()
```

## 7. Pattern References

### 7.1 Queue-Based Consumer Notification Pattern

**File:** `src/boostgauge/app.py` (lines 42-50)

```python
def _process_queue(self):
    """Consumer pattern matching the WindowsCollector producer queue logic."""
    try:
        while True:
            snapshot = self.queue.get_nowait()
            self._update_ui(snapshot)
    except queue.Empty:
        pass
    self.root.after(100, self._process_queue)
```

**Relevance:** Demonstrates why `WindowsCollector` uses `self._target_queue.put_nowait()` and non-blocking background threads. The main GUI strictly consumes via `get_nowait()` polling via `tkinter.after`, necessitating thread-safe queue emission without ever blocking the UI loop.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `import abc` | stdlib | `collector.py` |
| `import queue` | stdlib | `windows.py`, `test_windows_collector.py` |
| `import threading` | stdlib | `windows.py` |
| `import time` | stdlib | `windows.py`, `test_windows_collector.py` |
| `from typing import Dict, Optional` | stdlib | `windows.py` |
| `from dataclasses import dataclass` | stdlib | `collector.py` |
| `import psutil` | external | `windows.py`, `test_windows_collector.py` |
| `import pytest` | external | `test_windows_collector.py` |
| `from unittest import mock` | stdlib | `test_windows_collector.py` |

**New Dependencies:** None (`psutil` is already defined in `pyproject.toml`).

## 9. Placeholder

*Reserved for future use to maintain alignment with LLD section numbering.*

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `_collect_snapshot()` | `mock_psutil_process_iter` | One call with `attrs=["name", "num_handles", "cmdline"]` |
| T020 | `_collect_snapshot()` | `mock_virtual_memory` | One call, memory percent returned properly in snapshot |
| T030 | `_collect_snapshot()` | `psutil.NoSuchProcess` / `psutil.AccessDenied` exceptions | Exceptions are swallowed, sweep continues without crashing |
| T040 | `_collect_snapshot()` | 5 mocked valid rows | `snapshot.process_count == 5` |
| T050 | `_collect_snapshot()` | mock row `name="ConHost.exe"` | `snapshot.conpty_count == 1` |
| T060 | `_collect_snapshot()` | mock rows with handles 10 and 20 | `snapshot.handle_count == 30` |
| T070 | `_collect_snapshot()` | mock row `pythonw.exe` running `unleashed-c-123.py` | `snapshot.unleashed_sessions == 1` |
| T080 | `start()` and `stop()` | None | Thread starts, queues item, stops cleanly |
| T090 | `_collect_snapshot()` | Various mock resources | Identifies max normalized metric and its driver name |
| T100 | `__init__()` | No interval provided | `poll_interval == 2.0` |
| T110 | `start()` / `stop()` | Live system resources | Sub-second execution overhead without crashes |

## 11. Implementation Notes

### 11.1 Error Handling Convention

The `psutil.process_iter` walk strictly ignores all `NoSuchProcess` and `AccessDenied` exceptions during the `proc.info` dictionary evaluation. A process dying mid-walk should never crash the collector, nor should it abort the entire sweep for that interval. We intentionally read properties synchronously inside the loop to ensure volatile processes are filtered out properly. 

### 11.2 Constants

| Constant | Value | Rationale |
|----------|-------|-----------|
| `default_poll_interval` | `2.0` | Provides a real-time feel to the tachometer GUI while minimizing overhead and adhering to the CPU budget defined in the LLD. |

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3) - *Not applicable, all files are new additions*
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
| Date | 2026-08-10 |
| Iterations | 1 |
| Finalized | 2026-08-10T02:49:30-05:00 |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #4 |
| Verdict | APPROVED |
| Date | 2026-08-10 |
| Iterations | 1 |
| Finalized | 2026-08-10T08:00:28Z |

### Review Feedback Summary

The spec is exceptionally concrete and executable, providing full file contents that leave no ambiguity for an AI agent. The previous review feedback has been successfully addressed: the `test_cpu_overhead` test (T110) now explicitly asserts the CPU utilization (`cpu_usage < 1.0`) and uses the required 2.0-second interval, fixing the prior traceability gap. Every assertion in the test suite maps flawlessly to a stated LLD requirement, including exception handling (T030), normalized maximum compu...
