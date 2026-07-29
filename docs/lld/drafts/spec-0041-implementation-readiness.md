# Implementation Spec: Feature: Telltale peak-hold needle logic (pure, no GUI)

| Field | Value |
|-------|-------|
| Issue | #41 |
| LLD | `docs/lld/active/41-telltale-peak-hold.md` |
| Generated | 2026-07-29 |
| Status | APPROVED |

## 1. Overview

This implementation specification defines the pure, headless `Telltale` peak-hold needle logic module for the `boostgauge` package. The `Telltale` class tracks peak sample values over a sliding time window with optional linear decay.

**Objective:** Implement a pure Python `Telltale` class in `src/boostgauge/telltale.py` using an $O(1)$ amortized sliding-window maximum algorithm with double-ended queues and analytical linear decay tracking.

**Success Criteria:**
- 100% line and branch test coverage across all methods in `src/boostgauge/telltale.py`.
- Monotonic sliding window max queries run in $O(1)$ amortized time with zero GUI/`tkinter` coupling.
- Monotonic linear decay is mathematically exact, floored by the active window maximum.
- Standard input validation raises `ValueError` on non-positive window durations or negative decay rates.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/telltale.py` | Add | Implements the pure `Telltale` peak-hold needle class with $O(1)$ amortized monotonic deque and linear decay logic. |
| 2 | `tests/unit/test_telltale.py` | Add | Unit test suite covering pre-update state, rising series, window drops, linear decay, decay floor, reset, and parameter validation. |

**Implementation Order Rationale:** `src/boostgauge/telltale.py` defines the underlying logic component and data types. `tests/unit/test_telltale.py` imports `Telltale` from `boostgauge.telltale` to execute test assertions against the implementation.

## 3. Current State (for Modify/Delete files)

No existing files are modified or deleted in this implementation. All target files (`src/boostgauge/telltale.py` and `tests/unit/test_telltale.py`) are new additions (Add).

## 4. Data Structures

### 4.1 SampleTuple

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
    "timestamp": 1774872000.5,
    "value": 85.4
}
```

### 4.2 TelltaleInternalState

**Definition:**

```python
from typing import Optional, TypedDict

class TelltaleInternalState(TypedDict):
    window: float
    decay_rate: Optional[float]
    sample_count: int
    max_deque_count: int
    best_expired_key: Optional[float]
    latest_timestamp: Optional[float]
```

**Concrete Example:**

```json
{
    "window": 10.0,
    "decay_rate": 15.0,
    "sample_count": 2,
    "max_deque_count": 1,
    "best_expired_key": 250.0,
    "latest_timestamp": 12.0
}
```

## 5. Function Specifications

### 5.1 `Telltale.__init__()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def __init__(self, window: float, decay_rate: Optional[float] = None) -> None:
    """Initialize Telltale with window duration in seconds and optional decay rate (units/sec).

    Args:
        window: Sliding window duration in seconds (> 0).
        decay_rate: Optional linear decay rate in units per second (>= 0).

    Raises:
        ValueError: If window <= 0 or decay_rate < 0.
    """
    ...
```

**Input Example:**

```python
window = 10.0
decay_rate = 15.0
```

**Output Example:**

```python
# Instance initialized:
# self.window = 10.0
# self.decay_rate = 15.0
# self._samples = deque()
# self._max_deque = deque()
# self._best_expired_key = None
# self._latest_timestamp = None
```

**Edge Cases:**
- `window = 0.0` or `window = -5.0` -> raises `ValueError("window must be positive")`
- `decay_rate = -1.0` -> raises `ValueError("decay_rate must be non-negative")`

---

### 5.2 `Telltale.update()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def update(self, timestamp: float, value: float) -> None:
    """Feed a new sample (timestamp, value) into the telltale state.

    Args:
        timestamp: Sample timestamp in seconds.
        value: Numerical sample value.
    """
    ...
```

**Input Example:**

```python
timestamp = 0.0
value = 100.0
```

**Output Example:**

```python
# None returned. Internal state updated:
# self._latest_timestamp = 0.0
# self._samples = deque([(0.0, 100.0)])
# self._max_deque = deque([(0.0, 100.0)])
```

**Edge Cases:**
- Incoming value is lower than current maximum (e.g. `timestamp = 9.0, value = 40.0`): sample appended to `_samples` and `_max_deque`.
- Incoming value is higher than existing values (e.g. `value = 150.0`): pops smaller values from `_max_deque` back before pushing.

---

### 5.3 `Telltale.current_peak()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def current_peak(self, timestamp: Optional[float] = None) -> Optional[float]:
    """Compute the effective peak value at the specified timestamp (or latest sample timestamp).

    Args:
        timestamp: Optional evaluation timestamp. Defaults to latest sample timestamp.

    Returns:
        The current peak value (floored by window maximum), or None if no samples exist.
    """
    ...
```

**Input Example:**

```python
# State: window=10.0, decay_rate=15.0, updated with (0.0, 100.0) and (9.0, 40.0)
timestamp = 12.0
```

**Output Example:**

```python
70.0
```

**Edge Cases:**
- Called before any `update()` or after `reset()` -> returns `None`
- `timestamp` is `None` -> defaults to `self._latest_timestamp`
- `decay_rate` is `None` or `0.0` -> returns maximum sample value in active window without decay math

---

### 5.4 `Telltale.reset()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def reset(self) -> None:
    """Clear all historical state; subsequent current_peak() calls return None until updated."""
    ...
```

**Input Example:**

```python
# Called on active Telltale instance
tt.reset()
```

**Output Example:**

```python
# None returned. Internal queues cleared:
# self._samples.clear()
# self._max_deque.clear()
# self._best_expired_key = None
# self._latest_timestamp = None
```

**Edge Cases:**
- Calling `reset()` on an already empty instance is a safe no-op.

---

### 5.5 `Telltale._prune_expired()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def _prune_expired(self, evaluation_time: float) -> None:
    """Internal helper to prune samples older than (evaluation_time - window) and track expired max key."""
    ...
```

**Input Example:**

```python
evaluation_time = 12.0  # window = 10.0, cutoff = 2.0
```

**Output Example:**

```python
# Samples with timestamp < 2.0 popped from self._samples.
# If popped sample matches front of self._max_deque, it is popped from self._max_deque.
# If decay_rate > 0, self._best_expired_key updated with max(self._best_expired_key, v_old + decay_rate * (t_old + window)).
```

**Edge Cases:**
- All samples older than cutoff -> all samples pruned, `self._max_deque` becomes empty.

## 6. Change Instructions

### 6.1 `src/boostgauge/telltale.py` (Add)

**Complete file contents:**

```python
"""Pure sliding-window peak-hold needle logic with optional linear decay.

Issue #41: Telltale peak-hold needle logic (pure, no GUI)
"""

from __future__ import annotations

from collections import deque
from typing import Optional, Tuple


class Telltale:
    """Pure sliding-window peak-hold needle logic with optional linear decay."""

    def __init__(self, window: float, decay_rate: Optional[float] = None) -> None:
        """Initialize Telltale with window duration in seconds and optional decay rate (units/sec).

        Args:
            window: Sliding window duration in seconds (> 0).
            decay_rate: Optional linear decay rate in units per second (>= 0).

        Raises:
            ValueError: If window <= 0 or decay_rate < 0.
        """
        if window <= 0:
            raise ValueError("window must be positive")
        if decay_rate is not None and decay_rate < 0:
            raise ValueError("decay_rate must be non-negative")

        self.window: float = float(window)
        self.decay_rate: Optional[float] = float(decay_rate) if decay_rate is not None else None

        self._samples: deque[Tuple[float, float]] = deque()
        self._max_deque: deque[Tuple[float, float]] = deque()
        self._best_expired_key: Optional[float] = None
        self._latest_timestamp: Optional[float] = None

    def update(self, timestamp: float, value: float) -> None:
        """Feed a new sample (timestamp, value) into the telltale state.

        Args:
            timestamp: Sample timestamp in seconds.
            value: Numerical sample value.
        """
        t = float(timestamp)
        v = float(value)

        self._latest_timestamp = t
        self._prune_expired(t)

        self._samples.append((t, v))

        while self._max_deque and self._max_deque[-1][1] <= v:
            self._max_deque.pop()
        self._max_deque.append((t, v))

    def _prune_expired(self, evaluation_time: float) -> None:
        """Prune samples older than (evaluation_time - window) from active window queues.

        Args:
            evaluation_time: Timestamp to evaluate window cutoff against.
        """
        cutoff = evaluation_time - self.window
        while self._samples and self._samples[0][0] < cutoff:
            t_old, v_old = self._samples.popleft()
            if self._max_deque and self._max_deque[0] == (t_old, v_old):
                self._max_deque.popleft()

            if self.decay_rate is not None and self.decay_rate > 0:
                expired_key = v_old + self.decay_rate * (t_old + self.window)
                if self._best_expired_key is None or expired_key > self._best_expired_key:
                    self._best_expired_key = expired_key

    def current_peak(self, timestamp: Optional[float] = None) -> Optional[float]:
        """Compute the effective peak value at the specified timestamp (or latest sample timestamp).

        Args:
            timestamp: Optional evaluation timestamp. Defaults to latest sample timestamp.

        Returns:
            The current peak value (floored by window maximum), or None if no samples exist.
        """
        eval_time = timestamp if timestamp is not None else self._latest_timestamp
        if eval_time is None:
            return None

        self._prune_expired(eval_time)

        if not self._samples and self._best_expired_key is None:
            return None

        active_max = self._max_deque[0][1] if self._max_deque else None

        if self.decay_rate is not None and self.decay_rate > 0 and self._best_expired_key is not None:
            decayed_peak = self._best_expired_key - self.decay_rate * eval_time
            if active_max is not None:
                return max(active_max, decayed_peak)
            return decayed_peak

        return active_max

    def reset(self) -> None:
        """Clear all historical state; subsequent current_peak() calls return None until updated."""
        self._samples.clear()
        self._max_deque.clear()
        self._best_expired_key = None
        self._latest_timestamp = None
```

---

### 6.2 `tests/unit/test_telltale.py` (Add)

**Complete file contents:**

```python
"""Unit test suite for pure Telltale peak-hold needle logic.

Issue #41: Telltale peak-hold needle logic (pure, no GUI)
Ref: docs/design/0001-test-strategy.md (Option C / unit tier compliance)
"""

from __future__ import annotations

import pytest

from boostgauge.telltale import Telltale


def test_t010_initialization_and_module_exposure() -> None:
    """T010: Test Telltale initialization and parameter storage."""
    tt = Telltale(window=10.0, decay_rate=15.0)
    assert isinstance(tt, Telltale)
    assert tt.window == 10.0
    assert tt.decay_rate == 15.0


def test_t020_pre_update_peak_return() -> None:
    """T020: Verify current_peak() returns None before any update calls."""
    tt = Telltale(window=10.0)
    assert tt.current_peak() is None
    assert tt.current_peak(timestamp=5.0) is None


def test_t030_single_sample_update() -> None:
    """T030: Verify single sample update returns the exact sample value."""
    tt = Telltale(window=10.0)
    tt.update(timestamp=0.0, value=50.0)
    assert tt.current_peak() == 50.0
    assert tt.current_peak(timestamp=0.0) == 50.0


def test_t040_rising_series_tracking() -> None:
    """T040: Verify peak updates immediately when new maximum sample arrives."""
    tt = Telltale(window=10.0)
    tt.update(timestamp=0.0, value=50.0)
    assert tt.current_peak() == 50.0
    tt.update(timestamp=1.0, value=75.0)
    assert tt.current_peak() == 75.0


def test_t050_window_drop_without_decay() -> None:
    """T050: Verify instant drop to active window max when high ages out without decay."""
    tt = Telltale(window=10.0, decay_rate=None)
    tt.update(timestamp=0.0, value=100.0)
    tt.update(timestamp=9.0, value=40.0)
    assert tt.current_peak(timestamp=9.0) == 100.0
    # At t=11.0, sample at t=0.0 (100.0) is expired (> 10.0 window). Peak drops to 40.0.
    assert tt.current_peak(timestamp=11.0) == 40.0


def test_t060_monotonic_decay_from_expired_high() -> None:
    """T060: Verify linear decay at decay_rate units/sec from departed peak."""
    tt = Telltale(window=10.0, decay_rate=15.0)
    tt.update(timestamp=0.0, value=100.0)
    tt.update(timestamp=9.0, value=40.0)
    # At t=12.0, sample at t=0.0 (100.0) expired at t=10.0.
    # Decayed value at t=12.0 = 100.0 - 15.0 * (12.0 - 10.0) = 70.0.
    assert tt.current_peak(timestamp=12.0) == 70.0


def test_t070_active_window_decay_floor() -> None:
    """T070: Verify active window max acts as floor for linear decay."""
    tt = Telltale(window=10.0, decay_rate=15.0)
    tt.update(timestamp=0.0, value=100.0)
    tt.update(timestamp=9.0, value=40.0)
    # At t=15.0, decayed peak from t=0.0 would be 100.0 - 15.0 * 5.0 = 25.0.
    # However, sample at t=9.0 (40.0) is active in window [5.0, 15.0], flooring peak at 40.0.
    assert tt.current_peak(timestamp=15.0) == 40.0


def test_t080_reset_behavior() -> None:
    """T080: Verify reset clears all historical state and sample queues."""
    tt = Telltale(window=10.0, decay_rate=15.0)
    tt.update(timestamp=0.0, value=100.0)
    assert tt.current_peak() == 100.0

    tt.reset()
    assert tt.current_peak() is None

    # Subsequent update after reset works cleanly
    tt.update(timestamp=20.0, value=30.0)
    assert tt.current_peak() == 30.0


def test_t090_invalid_window_duration_parameter() -> None:
    """T090: Verify ValueError raised when window duration <= 0."""
    with pytest.raises(ValueError, match="window must be positive"):
        Telltale(window=0.0)

    with pytest.raises(ValueError, match="window must be positive"):
        Telltale(window=-5.0)


def test_t100_invalid_decay_rate_parameter() -> None:
    """T100: Verify ValueError raised when decay_rate < 0."""
    with pytest.raises(ValueError, match="decay_rate must be non-negative"):
        Telltale(window=10.0, decay_rate=-1.0)
```

## 7. Pattern References

### 7.1 Configuration Type Annotations & Custom Exceptions Pattern

**File:** `src/boostgauge/config.py` (lines 7-26)

```python
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, TypedDict


class ConfigError(Exception):
    """Raised when configuration file or CLI arguments fail schema or value validation."""

    pass
```

**Relevance:** Standardizes `from __future__ import annotations`, standard typing imports (`Optional`, `TypedDict`), docstring style, and explicit validation error handling across the `boostgauge` package.

---

### 7.2 Unit Test Module Structure Pattern

**File:** `tests/unit/test_config.py` (lines 1-27)

```python
"""Unit test suite for configuration management module.

Issue #7: Configuration File and CLI Arguments
Ref: docs/design/0001-test-strategy.md (Option C compliance)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
```

**Relevance:** Standardizes test module header docstring format, issue referencing, pytest imports, and function docstring conventions (`T010: ...`) used throughout unit tests.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `from __future__ import annotations` | stdlib | `src/boostgauge/telltale.py`, `tests/unit/test_telltale.py` |
| `from collections import deque` | stdlib | `src/boostgauge/telltale.py` |
| `from typing import Optional, Tuple, TypedDict` | stdlib | `src/boostgauge/telltale.py` |
| `import pytest` | pytest | `tests/unit/test_telltale.py` |
| `from boostgauge.telltale import Telltale` | internal | `tests/unit/test_telltale.py` |

**New Dependencies:** None required.

## 9. Placeholder

*Reserved for future use to maintain alignment with LLD section numbering.*

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `Telltale.__init__()` | `window=10.0, decay_rate=15.0` | `isinstance(tt, Telltale)` |
| T020 | `Telltale.current_peak()` | Pre-update call | `None` |
| T030 | `Telltale.update()`, `current_peak()` | `update(0.0, 50.0)` | `50.0` |
| T040 | `Telltale.update()`, `current_peak()` | `update(0.0, 50.0)`, `update(1.0, 75.0)` | `75.0` |
| T050 | `Telltale.current_peak()` | `window=10, decay=None`, `(0, 100)`, `(9, 40)` at `t=11` | `40.0` |
| T060 | `Telltale.current_peak()` | `window=10, decay=15`, `(0, 100)`, `(9, 40)` at `t=12` | `70.0` |
| T070 | `Telltale.current_peak()` | `window=10, decay=15`, `(0, 100)`, `(9, 40)` at `t=15` | `40.0` |
| T080 | `Telltale.reset()` | `update(0.0, 100.0)`, `reset()`, `current_peak()` | `None` |
| T090 | `Telltale.__init__()` | `window=0.0` or `window=-5.0` | Raises `ValueError` |
| T100 | `Telltale.__init__()` | `decay_rate=-1.0` | Raises `ValueError` |

## 11. Implementation Notes

### 11.1 Mathematical Formulation of Expired Decay Invariant

For any sample $(t_i, v_i)$ that expires at timestamp $t_{\text{expire}, i} = t_i + \text{window}$, its linear decay value at query time $t \ge t_{\text{expire}, i}$ is given by:

$$D_i(t) = v_i - \text{decay\_rate} \times (t - (t_i + \text{window})) = (v_i + \text{decay\_rate} \times (t_i + \text{window})) - \text{decay\_rate} \times t$$

Defining the time-invariant key $K_i = v_i + \text{decay\_rate} \times (t_i + \text{window})$, we observe that $D_i(t) = K_i - \text{decay\_rate} \times t$. Since $\text{decay\_rate} \times t$ subtracts identically for all expired samples, the sample with the maximum key $K_i$ yields the strictly maximum decayed value for all $t$. Tracking scalar `_best_expired_key = max(K_i)` guarantees $O(1)$ space and time complexity without storing historical arrays.

### 11.2 Error Handling & Input Validation Convention

The `Telltale.__init__()` method validates numeric parameters:
- If `window <= 0`, it raises `ValueError("window must be positive")`.
- If `decay_rate < 0`, it raises `ValueError("decay_rate must be non-negative")`.

### 11.3 Time Complexity & Memory Constraints

- `update()`: $O(1)$ amortized time complexity (each sample is pushed once and popped at most once from `_samples` and `_max_deque`).
- `current_peak()`: $O(1)$ amortized time complexity (prunes expired samples up to evaluation timestamp).
- Memory footprint: $O(W)$ where $W$ is the number of active samples within the sliding window `[timestamp - window, timestamp]`.

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3 - noted that all files are new)
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
| Date | 2026-07-29 |
| Iterations | 1 |
| Finalized | 2026-07-29T12:50:00Z |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #41 |
| Verdict | APPROVED |
| Date | 2026-07-29 |
| Iterations | 0 |
| Finalized | 2026-07-29T17:49:27Z |

### Review Feedback Summary

The implementation spec for Issue #41 (Telltale peak-hold needle logic) is exemplary and provides complete, concrete, and fully executable details for an autonomous AI agent to implement the feature with >80% first-try success rate.

Key Evaluations:
1. Completeness & Concreteness: Both target files (`src/boostgauge/telltale.py` and `tests/unit/test_telltale.py`) provide complete, production-ready source code with full type annotations. Data structures include TypedDict definitions and concrete ...
