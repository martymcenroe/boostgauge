# Implementation Spec: Feature: Telltale peak-hold needle logic (pure, no GUI)

| Field | Value |
|-------|-------|
| Issue | #41 |
| LLD | `docs/lld/done/41-telltale-peak-hold-logic.md` |
| Generated | 2026-08-01 |
| Status | APPROVED |

## 1. Overview

This implementation specification provides exact technical details to implement the pure, headless `Telltale` class in `src/boostgauge/telltale.py` and its test suite in `tests/unit/test_telltale.py`. `Telltale` tracks maximum values over a sliding time window with optional continuous linear decay using a monotonic double-ended queue.

**Objective:** Implement the `Telltale` peak-hold needle logic tracking maximum values over a sliding time window with optional decay in a pure, headless Python class.

**Success Criteria:**
- Expose `Telltale` class in `src/boostgauge/telltale.py` accepting constructor parameters `window` (float > 0) and `decay_rate` (float >= 0 or None).
- Achieve O(1) amortized time complexity per `update()` and `current_peak()` call via dual-deque sliding window management.
- Implement continuous time-anchored linear decay with the sliding window floor rule enforced continuous via `max(win_max, decayed_peak)` (operator ruling #125).
- Reach 100% test coverage in `tests/unit/test_telltale.py` with fast headless unit tests (< 0.2s total execution time) and zero GUI dependencies.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/telltale.py` | Add | Exposes `Telltale` class for pure peak-hold needle sliding-window logic. |
| 2 | `tests/unit/test_telltale.py` | Add | Pure logic unit tests verifying sliding window, decay, floor, non-monotonic timestamp error, performance, and reset state transitions. |

**Implementation Order Rationale:** `src/boostgauge/telltale.py` contains the core `Telltale` domain logic without external dependencies. `tests/unit/test_telltale.py` imports `Telltale` from `src/boostgauge/telltale.py` to run automated tests.

## 3. Current State (for Modify/Delete files)

*No files are modified or deleted in this issue. Both target files (`src/boostgauge/telltale.py` and `tests/unit/test_telltale.py`) are new additions. The test configuration in `tests/conftest.py` already bootstraps `src` into Python's module path.*

### 3.1 `tests/conftest.py` (Reference Context)

**Relevant excerpt** (lines 1-8):

```python
"""Project test bootstrap."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
```

**What changes:** No changes required. This existing configuration enables direct imports via `from boostgauge.telltale import Telltale`.

## 4. Data Structures

### 4.1 `SampleTuple`

**Definition:**

```python
from typing import TypedDict

class SampleTuple(TypedDict):
    timestamp: float
    value: float
```

**Concrete Example:**

```json
{
    "timestamp": 1722500000.0,
    "value": 85.5
}
```

### 4.2 `TelltaleState`

**Definition:**

```python
from typing import TypedDict, Optional, List, Tuple

class TelltaleState(TypedDict):
    window: float
    decay_rate: Optional[float]
    samples: List[Tuple[float, float]]
    max_deque: List[Tuple[float, float]]
    anchor_expire: Optional[float]
    anchor_value: Optional[float]
    last_timestamp: Optional[float]
```

**Concrete Example:**

```json
{
    "window": 10.0,
    "decay_rate": 15.0,
    "samples": [
        [9.0, 40.0],
        [12.0, 30.0]
    ],
    "max_deque": [
        [9.0, 40.0],
        [12.0, 30.0]
    ],
    "anchor_expire": 10.0,
    "anchor_value": 100.0,
    "last_timestamp": 12.0
}
```

## 5. Function Specifications

### 5.1 `Telltale.__init__()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def __init__(self, window: float, decay_rate: Optional[float] = None) -> None:
    """Initialize Telltale with sliding window duration (seconds) and optional decay rate (units/second)."""
    ...
```

**Input Example:**

```python
window = 10.0
decay_rate = 15.0
```

**Output Example:**

```python
# Returns None (initializes internal state attributes: self.window = 10.0, self.decay_rate = 15.0)
```

**Edge Cases:**
- `window <= 0` (e.g. `0.0` or `-5.0`) -> raises `ValueError("window must be > 0")`
- `decay_rate < 0` (e.g. `-1.0`) -> raises `ValueError("decay_rate must be >= 0")`
- Non-numeric or NaN/Inf inputs -> raises `TypeError("window must be a finite real number")` or `TypeError("decay_rate must be a finite real number or None")`

---

### 5.2 `Telltale.update()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def update(self, timestamp: float, value: float) -> None:
    """Feed a new sample (timestamp, value) into the telltale and update internal peak state."""
    ...
```

**Input Example:**

```python
timestamp = 12.0
value = 30.0
```

**Output Example:**

```python
# Returns None. Updates self._samples, self._max_deque, self._last_timestamp, and anchor state.
```

**Edge Cases:**
- Non-monotonic timestamp (`timestamp < self._last_timestamp`) -> raises `ValueError(f"Non-monotonic timestamp received: {timestamp} < {self._last_timestamp}")`
- NaN or infinite `timestamp` / `value` -> raises `TypeError("timestamp must be a finite real number")` or `TypeError("value must be a finite real number")`
- Automatic eviction of samples where `sample_timestamp < timestamp - window`

---

### 5.3 `Telltale.current_peak()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def current_peak(self) -> Optional[float]:
    """Return the highest value within the active window, adjusted for decay, or None if empty/reset."""
    ...
```

**Input Example:**

```python
# Called on Telltale state with window=10.0, decay_rate=15.0 after update(0.0, 100.0), update(9.0, 40.0), update(12.0, 30.0)
```

**Output Example:**

```python
70.0
```

**Edge Cases:**
- Called before any `update()` -> returns `None`
- Called after `reset()` -> returns `None`
- `decay_rate` is `None` or `0.0` -> returns exact maximum value of samples in window (`win_max`)
- Decayed peak drops below `win_max` -> returns `win_max` (floor rule)

---

### 5.4 `Telltale.reset()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def reset(self) -> None:
    """Clear all historical samples and peak tracking state."""
    ...
```

**Input Example:**

```python
# Called on an active Telltale instance with historical updates
```

**Output Example:**

```python
# Returns None. Clears self._samples and self._max_deque, resets anchor and last_timestamp to None.
```

**Edge Cases:**
- Calling `reset()` on an already empty instance succeeds without error.
- Subsequent call to `current_peak()` immediately returns `None`.

## 6. Change Instructions

### 6.1 `src/boostgauge/telltale.py` (Add)

**Complete file contents:**

```python
"""Peak-hold telltale needle logic with continuous sliding window decay.

Issue #41: Feature: Telltale peak-hold needle logic (pure, no GUI)
"""

from collections import deque
import math
from typing import Deque, Optional, Tuple


class Telltale:
    """Pure peak-hold needle logic tracking maximum values over a sliding time window with optional decay."""

    def __init__(self, window: float, decay_rate: Optional[float] = None) -> None:
        """Initialize Telltale with sliding window duration (seconds) and optional decay rate (units/second)."""
        if not isinstance(window, (int, float)) or math.isnan(window) or math.isinf(window):
            raise TypeError("window must be a finite real number")
        if window <= 0:
            raise ValueError("window must be > 0")

        if decay_rate is not None:
            if not isinstance(decay_rate, (int, float)) or math.isnan(decay_rate) or math.isinf(decay_rate):
                raise TypeError("decay_rate must be a finite real number or None")
            if decay_rate < 0:
                raise ValueError("decay_rate must be >= 0")

        self.window: float = float(window)
        self.decay_rate: Optional[float] = float(decay_rate) if decay_rate is not None else None

        self._samples: Deque[Tuple[float, float]] = deque()
        self._max_deque: Deque[Tuple[float, float]] = deque()
        self._anchor_expire: Optional[float] = None
        self._anchor_value: Optional[float] = None
        self._last_timestamp: Optional[float] = None

    def _compute_decayed_peak(self, t: float) -> Optional[float]:
        """Calculate decayed peak value from current anchor at timestamp t."""
        if self._anchor_value is None or self._anchor_expire is None:
            return None
        if self.decay_rate is None or self.decay_rate == 0.0:
            return self._anchor_value
        if t <= self._anchor_expire:
            return self._anchor_value
        elapsed_decay = t - self._anchor_expire
        return self._anchor_value - (self.decay_rate * elapsed_decay)

    def update(self, timestamp: float, value: float) -> None:
        """Feed a new sample (timestamp, value) into the telltale and update internal peak state."""
        if not isinstance(timestamp, (int, float)) or math.isnan(timestamp) or math.isinf(timestamp):
            raise TypeError("timestamp must be a finite real number")
        if not isinstance(value, (int, float)) or math.isnan(value) or math.isinf(value):
            raise TypeError("value must be a finite real number")

        t = float(timestamp)
        v = float(value)

        if self._last_timestamp is not None and t < self._last_timestamp:
            raise ValueError(f"Non-monotonic timestamp received: {t} < {self._last_timestamp}")

        self._last_timestamp = t

        # 1. Prune samples older than cutoff (t - window)
        cutoff = t - self.window
        while self._samples and self._samples[0][0] < cutoff:
            self._samples.popleft()
        while self._max_deque and self._max_deque[0][0] < cutoff:
            self._max_deque.popleft()

        # 2. Append new sample
        self._samples.append((t, v))

        # 3. Maintain monotonic decreasing deque for window maximum
        while self._max_deque and self._max_deque[-1][1] <= v:
            self._max_deque.pop()
        self._max_deque.append((t, v))

        win_max = self._max_deque[0][1]

        # 4. Update decay anchor state
        decayed = self._compute_decayed_peak(t)
        if self._anchor_value is None or decayed is None or v >= decayed:
            self._anchor_value = v
            self._anchor_expire = t + self.window
        else:
            if decayed <= win_max:
                self._anchor_value = win_max
                self._anchor_expire = self._max_deque[0][0] + self.window

    def current_peak(self) -> Optional[float]:
        """Return the highest value within the active window, adjusted for decay, or None if empty/reset."""
        if not self._samples or self._last_timestamp is None:
            return None

        win_max = self._max_deque[0][1]
        if self.decay_rate is None or self.decay_rate == 0.0:
            return win_max

        decayed_peak = self._compute_decayed_peak(self._last_timestamp)
        if decayed_peak is None:
            return win_max

        # Floor is always the highest value remaining in the active window
        return max(win_max, decayed_peak)

    def reset(self) -> None:
        """Clear all historical samples and peak tracking state."""
        self._samples.clear()
        self._max_deque.clear()
        self._anchor_expire = None
        self._anchor_value = None
        self._last_timestamp = None
```

---

### 6.2 `tests/unit/test_telltale.py` (Add)

**Complete file contents:**

```python
"""Unit tests for pure telltale peak-hold needle logic.

Issue #41: Feature: Telltale peak-hold needle logic (pure, no GUI)
"""

import time
import pytest
from boostgauge.telltale import Telltale


def test_t010_constructor_parameter_validation() -> None:
    """Validate window > 0 and decay_rate >= 0 constructors raise ValueError/TypeError on bad inputs."""
    tt = Telltale(window=10.0, decay_rate=15.0)
    assert tt.window == 10.0
    assert tt.decay_rate == 15.0

    tt_no_decay = Telltale(window=5.0)
    assert tt_no_decay.window == 5.0
    assert tt_no_decay.decay_rate is None

    with pytest.raises(ValueError, match="window must be > 0"):
        Telltale(window=0.0)

    with pytest.raises(ValueError, match="window must be > 0"):
        Telltale(window=-1.0)

    with pytest.raises(ValueError, match="decay_rate must be >= 0"):
        Telltale(window=10.0, decay_rate=-5.0)

    with pytest.raises(TypeError):
        Telltale(window=float("nan"))


def test_t020_pre_first_update_peak_check() -> None:
    """Verify current_peak() returns None prior to receiving any updates."""
    tt = Telltale(window=10.0, decay_rate=15.0)
    assert tt.current_peak() is None


def test_t030_single_sample_peak_check() -> None:
    """Verify single sample update updates peak."""
    tt = Telltale(window=10.0, decay_rate=15.0)
    tt.update(0.0, 50.0)
    assert tt.current_peak() == 50.0


def test_t040_rising_series_peak_check() -> None:
    """Verify rising series immediately updates peak on new high."""
    tt = Telltale(window=10.0, decay_rate=15.0)
    tt.update(0.0, 10.0)
    assert tt.current_peak() == 10.0
    tt.update(1.0, 20.0)
    assert tt.current_peak() == 20.0
    tt.update(2.0, 50.0)
    assert tt.current_peak() == 50.0


def test_t050_static_peak_aging_out_no_decay() -> None:
    """Verify static peak without decay drops instantly when high ages out."""
    tt = Telltale(window=10.0, decay_rate=None)
    tt.update(0.0, 100.0)
    tt.update(5.0, 40.0)
    assert tt.current_peak() == 100.0
    tt.update(11.0, 30.0)
    assert tt.current_peak() == 40.0


def test_t060_decay_descending_calculation() -> None:
    """Verify peak decays monotonically at decay_rate from departed high."""
    tt = Telltale(window=10.0, decay_rate=10.0)
    tt.update(0.0, 100.0)
    assert tt.current_peak() == 100.0
    # At t=10.0, expire reached
    tt.update(10.0, 20.0)
    assert tt.current_peak() == 100.0
    # At t=12.0, high at t=0.0 (100.0) has aged out, decay elapsed = 2.0s -> 100 - (10 * 2) = 80.0
    tt.update(12.0, 20.0)
    assert tt.current_peak() == 80.0


def test_t070_discriminating_case_verification() -> None:
    """Verify discriminating scenario: (0.0, 100.0) and (9.0, 40.0) with win=10, decay=15 yields 70.0 at t=12.0."""
    tt = Telltale(window=10.0, decay_rate=15.0)
    tt.update(0.0, 100.0)
    tt.update(9.0, 40.0)
    assert tt.current_peak() == 100.0
    tt.update(12.0, 30.0)
    assert tt.current_peak() == 70.0


def test_t080_decay_floor_verification() -> None:
    """Verify floor rule: peak decays down to window max (40.0) and does not drop below it at t=15.0."""
    tt = Telltale(window=10.0, decay_rate=15.0)
    tt.update(0.0, 100.0)
    tt.update(9.0, 40.0)
    tt.update(12.0, 30.0)
    assert tt.current_peak() == 70.0
    tt.update(15.0, 20.0)
    assert tt.current_peak() == 40.0


def test_t090_reset_state_clearing() -> None:
    """Verify reset() clears all internal state so current_peak() returns None."""
    tt = Telltale(window=10.0, decay_rate=15.0)
    tt.update(0.0, 100.0)
    assert tt.current_peak() == 100.0
    tt.reset()
    assert tt.current_peak() is None
    tt.update(1.0, 25.0)
    assert tt.current_peak() == 25.0


def test_t100_out_of_order_timestamp_guard() -> None:
    """Verify non-monotonic timestamp raises ValueError."""
    tt = Telltale(window=10.0, decay_rate=15.0)
    tt.update(10.0, 50.0)
    with pytest.raises(ValueError, match="Non-monotonic timestamp received"):
        tt.update(5.0, 60.0)


def test_t110_large_stream_performance_smoke() -> None:
    """Verify 100,000 updates execute in < 0.2s demonstrating O(1) amortized complexity."""
    tt = Telltale(window=10.0, decay_rate=5.0)
    start = time.perf_counter()
    for i in range(100_000):
        t = i * 0.1
        v = (i % 100) * 1.5
        tt.update(t, v)
        _ = tt.current_peak()
    elapsed = time.perf_counter() - start
    assert elapsed < 0.2, f"Execution time {elapsed:.3f}s exceeded 0.2s budget"
```

## 7. Pattern References

### 7.1 Python Module & Test Import Setup

**File:** `tests/conftest.py` (lines 1-8)

```python
"""Project test bootstrap."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
```

**Relevance:** Demonstrates how test execution imports source files cleanly from `src/boostgauge/` without packaging overhead.

### 7.2 Project Package Metadata

**File:** `pyproject.toml` (lines 1-15)

```toml
[project]
name = "boostgauge"
version = "0.1.0"
description = "Real-time system monitor styled like a racing tachometer"
authors = [
    {name = "Marty McEnroe",email = "opensource@martymcenroe.ai"}
]
license = {text = "MIT"}
readme = "README.md"
requires-python = ">=3.10,<4"
```

**Relevance:** Establishes Python 3.10+ requirement, allowing standard type annotations (`Optional[float]`, `Deque[Tuple[float, float]]`, etc.).

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `from collections import deque` | stdlib | `src/boostgauge/telltale.py` |
| `import math` | stdlib | `src/boostgauge/telltale.py` |
| `from typing import Deque, Optional, Tuple` | stdlib | `src/boostgauge/telltale.py` |
| `import time` | stdlib | `tests/unit/test_telltale.py` |
| `import pytest` | external (`pyproject.toml`) | `tests/unit/test_telltale.py` |
| `from boostgauge.telltale import Telltale` | internal | `tests/unit/test_telltale.py` |

**New Dependencies:** None (uses standard Python library and existing test runner `pytest`).

## 9. Placeholder

*Reserved for future alignment with LLD section numbering.*

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output | Pass Criteria |
|---------|---------------|-------|-----------------|---------------|
| T010 | `Telltale.__init__()` | `window=-1.0` or `decay_rate=-5.0` | Raises `ValueError` | Exception raised matching pattern |
| T020 | `Telltale.current_peak()` | Un-updated `Telltale(10.0)` | `None` | `tt.current_peak() is None` |
| T030 | `Telltale.update()` | `update(0.0, 50.0)` | `50.0` | `tt.current_peak() == 50.0` |
| T040 | `Telltale.update()` | `update(0.0, 10.0)`, `update(1.0, 20.0)` | `20.0` | `tt.current_peak() == 20.0` |
| T050 | `Telltale.current_peak()` | `(0.0, 100.0)`, `(5.0, 40.0)` checked at `t=11.0` (no decay) | `40.0` | `tt.current_peak() == 40.0` |
| T060 | `Telltale.current_peak()` | `(0.0, 100.0)` with `decay_rate=10.0` checked at `t=12.0` | `80.0` | `tt.current_peak() == 80.0` |
| T070 | `Telltale.current_peak()` | `(0.0, 100.0)`, `(9.0, 40.0)` with `win=10, decay=15` checked at `t=12.0` | `70.0` | `tt.current_peak() == 70.0` |
| T080 | `Telltale.current_peak()` | Same series checked at `t=15.0` | `40.0` | `tt.current_peak() == 40.0` (floor rule) |
| T090 | `Telltale.reset()` | `update(0.0, 100.0)` followed by `reset()` | `None` | `tt.current_peak() is None` |
| T100 | `Telltale.update()` | `update(10.0, 50.0)` then `update(5.0, 60.0)` | Raises `ValueError` | `ValueError` raised on non-monotonic `t` |
| T110 | `Telltale.update()` | 100,000 streaming updates | Execution time < 0.2s | Test completes within budget |

### Baseline-Independent Test Assertions

Because `Telltale` is a pure headless calculation class, all test assertions compute mathematical exact values (e.g. `100.0 - 15.0 * (12.0 - 10.0) == 70.0`) and floor bounds (`max(40.0, 25.0) == 40.0`) directly without requiring visual baseline images or baseline comparison files.

## 11. Implementation Notes

### 11.1 Error Handling & Fail-Closed Behavior

- Parameter validation in `__init__` and `update` raises explicit `ValueError` or `TypeError` immediately when non-finite, negative, or non-monotonic values are provided.
- `reset()` provides safe state recovery, restoring the object to a clean pre-first-update state.

### 11.2 Performance & Memory Constraints

- Dual-deque design ensures operations are amortized O(1).
- Pruning on every `update()` guarantees memory size per `Telltale` instance stays bounded under continuous execution.

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3 - noted N/A for modify/delete, reference context provided)
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
| Issue | #41 |
| Verdict | APPROVED |
| Date | 2026-08-01 |
| Iterations | 1 |
| Finalized | 2026-08-01T08:32:13-05:00 |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #41 |
| Verdict | APPROVED |
| Date | 2026-08-01 |
| Iterations | 0 |
| Finalized | 2026-08-01T13:32:55Z |

### Review Feedback Summary

The implementation spec provides clear, concrete, and complete instructions for implementing the pure Telltale peak-hold logic and unit tests. Complete code and test files are provided with exact diff-level specificity. All assertions in the test suite trace directly to requirements in the LLD (including decay, sliding window eviction, non-monotonic timestamp handling, and the window maximum floor rule per Operator Ruling #125). Amortized O(1) performance and fail-closed validation are properly ...
