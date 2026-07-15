# Implementation Spec: Feature: Telltale peak-hold needle logic (pure, no GUI)

| Field | Value |
|-------|-------|
| Issue | #41 |
| LLD | `docs/lld/active/LLD-041.md` |
| Generated | 2026-07-15 |
| Status | APPROVED |

## 1. Overview

This implementation adds the core peak-hold (telltale) needle logic for the boostgauge application. It tracks the maximum value reached over a sliding time window with support for optional decay, using virtual stream timestamps to remain decoupled from the host OS clock.

**Objective:** Implement a pure-logic, GUI-free `Telltale` class that calculates peak-hold tachometer needle positions efficiently in $O(1)$ amortized time.

**Success Criteria:**
- `Telltale` class is correctly exposed in `src/boostgauge/telltale.py` and initializable.
- `update(timestamp, value)` and `current_peak()` run in $O(1)$ amortized time.
- The peak resets immediately to a new high value when exceeded.
- When the sliding time window expires, the peak drops to the next-highest value still within the window.
- If a non-zero `decay_rate` is provided, the peak decays monotonically toward the current value over time.
- `reset()` clears all historical and peak state.
- Inputs are validated: non-positive window duration, negative decay rate, and non-monotonic timestamps raise `ValueError`.
- Automated test suite covers 100% line and branch coverage of `src/boostgauge/telltale.py`.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/__init__.py` | Add | Package initialization file exposing `Telltale` class |
| 2 | `src/boostgauge/telltale.py` | Add | Core class implementing the monotonic deque peak-hold logic |
| 3 | `tests/unit/test_telltale.py` | Add | Unit tests for testing validation, logic correctness, and performance |

**Implementation Order Rationale:**
The package directory structure and the core logic file `telltale.py` must be defined first so that they can be exposed by the package root `__init__.py`. Once the code is in place, the tests in `test_telltale.py` are implemented and run to verify the correctness of the class.

## 3. Current State (for Modify/Delete files)

There are no existing files to modify or delete for this issue. All files mentioned are new additions.

## 4. Data Structures

### 4.1 TelltaleSample

**Definition:**

```python
from typing import TypedDict

class TelltaleSample(TypedDict):
    timestamp: float  # Timestamp when the value was recorded
    value: float      # The actual recorded value
    key: float        # The invariant decay key used for monotonic ordering
```

**Concrete Example:**

```json
{
    "timestamp": 1718451200.5,
    "value": 12.4,
    "key": 859238000.5
}
```

### 4.2 TelltaleHistory

**Definition:**

```python
from typing import TypedDict, List

class TelltaleHistory(TypedDict):
    window: float
    decay_rate: float
    history: List[TelltaleSample]
```

**Concrete Example:**

```json
{
    "window": 10.0,
    "decay_rate": 0.5,
    "history": [
        {
            "timestamp": 1718451200.0,
            "value": 15.0,
            "key": 859225615.0
        },
        {
            "timestamp": 1718451205.0,
            "value": 10.0,
            "key": 859225612.5
        }
    ]
}
```

## 5. Function Specifications

### 5.1 `Telltale.__init__()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def __init__(self, window: float, decay_rate: Optional[float] = None) -> None:
    """Initialize the peak-hold telltale.

    Args:
        window: Sliding window duration in seconds (must be positive).
        decay_rate: Optional decay rate in units/second (must be non-negative).
    """
    ...
```

**Input Example:**

```python
window = 10.0
decay_rate = 1.5
```

**Output Example:**

```python
# Returns None. Initializes:
# self.window = 10.0
# self.decay_rate = 1.5
# self._history = deque()
# self._peak = None
# self._last_t = None
```

**Edge Cases:**
- `window = 0.0` or `window = -5.0` -> Raises `ValueError("Window must be positive.")`
- `decay_rate = -0.5` -> Raises `ValueError("decay_rate must be non-negative.")`

---

### 5.2 `Telltale.update()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def update(self, timestamp: float, value: float) -> None:
    """Feed a new sample into the telltale.

    Args:
        timestamp: The timestamp of the sample. Must be >= the previous timestamp.
        value: The value of the sample.
    """
    ...
```

**Input Example:**

```python
timestamp = 10.0
value = 7.5
```

**Output Example:**

```python
# Returns None. Updates state internals.
```

**Edge Cases:**
- `timestamp` is less than `self._last_t` (e.g. `timestamp = 3.0` after `5.0`) -> Raises `ValueError("Timestamps must be monotonically increasing.")`
- Deque is empty -> Appends first item, updates `self._peak` to `value`.
- Eviction of old elements -> Elements with `timestamp < (current_timestamp - self.window)` are popped from the left of the deque.
- Keys matching or lower -> Pops items from the right of the deque if their invariant key is `<= current_key`.

---

### 5.3 `Telltale.current_peak()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def current_peak(self) -> Optional[float]:
    """Get the current peak-hold value.

    Returns:
        The peak value, or None if no samples have been received or after reset().
    """
    ...
```

**Input Example:**

```python
# No arguments
```

**Output Example:**

```python
7.25
```

**Edge Cases:**
- Called before any updates -> Returns `None`
- Called after `reset()` -> Returns `None`
- Decay rate is `None` -> Returns the exact max value remaining in the window.

---

### 5.4 `Telltale.reset()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def reset(self) -> None:
    """Reset the telltale's state and clear history."""
    ...
```

**Input Example:**

```python
# No arguments
```

**Output Example:**

```python
# Returns None. Resets internals to:
# self._history = deque()
# self._peak = None
# self._last_t = None
```

**Edge Cases:**
- Can be called at any time (even if already reset) without raising an error.

## 6. Change Instructions

### 6.1 `src/boostgauge/__init__.py` (Add)

**Complete file contents:**

```python
"""boostgauge package.

Issue #41: Feature: Telltale peak-hold needle logic (pure, no GUI)
"""

from boostgauge.telltale import Telltale

__all__ = ["Telltale"]
```

### 6.2 `src/boostgauge/telltale.py` (Add)

**Complete file contents:**

```python
"""Peak-hold telltale needle logic.

Issue #41: Feature: Telltale peak-hold needle logic (pure, no GUI)
"""

from collections import deque
from typing import Optional, TypedDict


class TelltaleSample(TypedDict):
    timestamp: float
    value: float
    key: float


class Telltale:
    """Tracks the peak value reached over a sliding time window with optional decay."""

    def __init__(self, window: float, decay_rate: Optional[float] = None) -> None:
        """Initialize the peak-hold telltale.

        Args:
            window: Sliding window duration in seconds (must be positive).
            decay_rate: Optional decay rate in units/second (must be non-negative).
        """
        if window <= 0:
            raise ValueError("Window must be positive.")
        if decay_rate is not None and decay_rate < 0:
            raise ValueError("decay_rate must be non-negative.")

        self.window = window
        self.decay_rate = decay_rate
        self._history: deque[TelltaleSample] = deque()
        self._peak: Optional[float] = None
        self._last_t: Optional[float] = None

    def update(self, timestamp: float, value: float) -> None:
        """Feed a new sample into the telltale.

        Args:
            timestamp: The timestamp of the sample. Must be >= the previous timestamp.
            value: The value of the sample.
        """
        if self._last_t is not None and timestamp < self._last_t:
            raise ValueError("Timestamps must be monotonically increasing.")

        self._last_t = timestamp
        cutoff = timestamp - self.window

        # 1. Expire old elements outside the window
        while self._history and self._history[0]["timestamp"] < cutoff:
            self._history.popleft()

        # 2. Compute invariant decay key
        if self.decay_rate is not None:
            key = value + self.decay_rate * timestamp
        else:
            key = value

        # 3. Maintain monotonic order (remove items with smaller/equal keys from back)
        while self._history and self._history[-1]["key"] <= key:
            self._history.pop()

        # 4. Append new sample
        self._history.append({
            "timestamp": timestamp,
            "value": value,
            "key": key
        })

        # 5. Update computed peak
        front = self._history[0]
        if self.decay_rate is not None:
            self._peak = front["key"] - self.decay_rate * timestamp
        else:
            self._peak = front["value"]

    def current_peak(self) -> Optional[float]:
        """Get the current peak-hold value.

        Returns:
            The peak value, or None if no samples have been received or after reset().
        """
        return self._peak

    def reset(self) -> None:
        """Reset the telltale's state and clear history."""
        self._history.clear()
        self._peak = None
        self._last_t = None
```

### 6.3 `tests/unit/test_telltale.py` (Add)

**Complete file contents:**

```python
"""Unit tests for the peak-hold telltale needle logic.

Issue #41: Feature: Telltale peak-hold needle logic (pure, no GUI)
"""

import time
import pytest
from boostgauge.telltale import Telltale


def test_telltale_init() -> None:
    """Verify class exposure and valid initialization (T010)."""
    t = Telltale(window=60.0, decay_rate=0.5)
    assert t.window == 60.0
    assert t.decay_rate == 0.5
    assert t.current_peak() is None


def test_telltale_invalid_init() -> None:
    """Verify initialization validation (T070)."""
    with pytest.raises(ValueError, match="Window must be positive."):
        Telltale(window=0.0)
    with pytest.raises(ValueError, match="Window must be positive."):
        Telltale(window=-5.0)
    with pytest.raises(ValueError, match="decay_rate must be non-negative."):
        Telltale(window=5.0, decay_rate=-1.0)


def test_telltale_pre_update_peak() -> None:
    """Verify pre-first-update peak returns None (T090)."""
    t = Telltale(window=10.0)
    assert t.current_peak() is None


def test_telltale_non_monotonic_timestamp() -> None:
    """Verify non-monotonic timestamp rejection (T100)."""
    t = Telltale(window=10.0)
    t.update(5.0, 10.0)
    with pytest.raises(ValueError, match="Timestamps must be monotonically increasing."):
        t.update(3.0, 5.0)


def test_telltale_reset_to_new_high() -> None:
    """Verify reset to new high value when exceeded (T030)."""
    t = Telltale(window=10.0)
    t.update(0.0, 5.0)
    assert t.current_peak() == 5.0
    t.update(1.0, 10.0)
    assert t.current_peak() == 10.0


def test_telltale_window_expiry() -> None:
    """Verify window expiry drops peak to next-highest value (T040)."""
    t = Telltale(window=10.0)
    t.update(0.0, 10.0)
    t.update(5.0, 5.0)
    assert t.current_peak() == 10.0
    t.update(11.0, 2.0)
    # 10.0 expired (11.0 - 0.0 > 10). Next highest in window is 5.0.
    assert t.current_peak() == 5.0


def test_telltale_monotonic_decay() -> None:
    """Verify monotonic decay towards current value (T050)."""
    t = Telltale(window=10.0, decay_rate=1.0)
    t.update(0.0, 10.0)
    assert t.current_peak() == 10.0
    # Decays from 10.0 by 1.0/sec for 5 seconds -> 5.0
    t.update(5.0, 3.0)
    assert t.current_peak() == 5.0


def test_telltale_decay_bounded_by_current() -> None:
    """Verify decay is bounded by the current value (T080)."""
    t = Telltale(window=10.0, decay_rate=1.0)
    t.update(0.0, 10.0)
    # Decays from 10.0 by 1.0/sec for 12 seconds -> -2.0.
    # At t=12, the first sample at t=0 has expired. The current value is 5.0.
    # Peak must not drop below the current value of 5.0.
    t.update(12.0, 5.0)
    assert t.current_peak() == 5.0


def test_telltale_reset_clears_state() -> None:
    """Verify reset clears all history and peak state (T060)."""
    t = Telltale(window=10.0, decay_rate=1.0)
    t.update(0.0, 10.0)
    assert t.current_peak() == 10.0
    t.reset()
    assert t.current_peak() is None
    # Re-verify that updates work after reset
    t.update(5.0, 8.0)
    assert t.current_peak() == 8.0


def test_telltale_performance() -> None:
    """Verify O(1) amortized update and retrieval efficiency (T020)."""
    t = Telltale(window=10.0, decay_rate=0.5)
    start_time = time.perf_counter()
    for i in range(10000):
        t.update(float(i) * 0.001, float(i % 100))
        t.current_peak()
    end_time = time.perf_counter()
    duration = end_time - start_time
    assert duration < 0.2
```

## 7. Pattern References

### 7.1 Testing Bootstrap Pattern

**File:** [conftest.py](file:///C:/Users/mcwiz/Projects/boostgauge/tests/conftest.py) (lines 1-8)

```python
"""Project test bootstrap."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
```

**Relevance:** This file demonstrates the workspace path configuration for testing modules in the `src/` directory. Since this is the first feature implementation in the codebase, there are no existing domain logic modules or tests to reference, so we base our testing bootstrap configuration on this file.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `from collections import deque` | stdlib | `src/boostgauge/telltale.py` |
| `from typing import Optional, TypedDict` | stdlib | `src/boostgauge/telltale.py` |
| `import time` | stdlib | `tests/unit/test_telltale.py` |
| `import pytest` | external | `tests/unit/test_telltale.py` |
| `from boostgauge.telltale import Telltale` | internal | `tests/unit/test_telltale.py` |

**New Dependencies:** None (no pyproject.toml additions required).

## 9. Placeholder

*Reserved for future use to maintain alignment with LLD section numbering.*

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `Telltale.__init__()` | `window=60.0`, `decay_rate=0.5` | `window` = 60.0, `decay_rate` = 0.5, peak is `None` |
| T020 | `Telltale.update()` / `current_peak()` | 10,000 updates sequentially | Executes in under 0.2 seconds |
| T030 | `Telltale.update()` | `update(0.0, 5.0)`, `update(1.0, 10.0)` | `current_peak()` = 10.0 |
| T040 | `Telltale.update()` | `window=10`, updates `(0, 10)`, `(5, 5)`, `(11, 2)` | `current_peak()` = 5.0 at t=11 |
| T050 | `Telltale.update()` | `window=10`, `decay=1.0`, updates `(0, 10)`, `(5, 3)` | `current_peak()` = 5.0 at t=5 |
| T060 | `Telltale.reset()` | `update(0.0, 10.0)`, `reset()` | `current_peak()` = `None` |
| T070 | `Telltale.__init__()` | `window=0.0` / `decay_rate=-1.0` | Raises `ValueError` |
| T080 | `Telltale.update()` | `window=10`, `decay=1.0`, updates `(0, 10)`, `(12, 5)` | `current_peak()` = 5.0 (bounded by current) |
| T090 | `Telltale.current_peak()` | Called before updates | `None` |
| T100 | `Telltale.update()` | `update(5.0, 10.0)`, `update(3.0, 5.0)` | Raises `ValueError` (non-monotonic) |

## 11. Implementation Notes

### 11.1 Mathematical Optimization Choice

We maintain mathematical equivalence of peak decay using an invariant key: 

$$K = V + decay\_rate \times t$$

This maps the time-varying decay peak-hold search to a static sliding-window maximum query, yielding $O(1)$ amortized performance for both updates and queries. State updates are driven entirely by virtual timestamps passed to `update()`, avoiding any real-world clock dependencies.

### 11.2 Error Handling Convention

For invalid configuration parameters or non-monotonic timestamps, we raise a standard `ValueError` with clear descriptive messages.

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3) - *N/A, documented as none.*
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
| Date | 2026-07-15 |
| Iterations | 1 |
| Finalized | 2026-07-15T00:44:45-05:00 |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #41 |
| Verdict | APPROVED |
| Date | 2026-07-15 |
| Iterations | 0 |
| Finalized | 2026-07-15T05:45:09Z |

### Review Feedback Summary

\nThe implementation spec is exceptionally complete, concrete, and feasible. It provides exact, fully functional Python code for both the domain logic and its corresponding unit tests. By using a monotonic deque with an invariant key mathematical transformation, the design achieves the requested $O(1)$ amortized complexity while keeping virtual time decoupled from the system clock.\n\n## Blocking Issues\nNo blocking issues found.\n\n## High Priority Issues\nNo high-priority issues found.\n\n## S...
