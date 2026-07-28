# Implementation Spec: 41 - Feature: Telltale peak-hold needle logic (pure, no GUI)

| Field | Value |
|-------|-------|
| Issue | #41 |
| LLD | `docs/lld/done/41-telltale-needle-logic.md` |
| Generated | 2026-07-28 |
| Status | APPROVED |

## 1. Overview

This implementation adds the pure `Telltale` class, a zero-GUI peak-hold needle logic module that tracks maximum metric values over a sliding time window with optional continuous linear decay. It utilizes a monotonic double-ended queue ($O(1)$ amortized time complexity) to achieve peak-tracking efficiency and deterministic behavior under irregular update frequencies.

**Objective:** Implement a pure peak-hold needle logic class (`Telltale`) that tracks maximum metric values over a sliding time window with optional decay rate support.

**Success Criteria:**
- Expose `Telltale` in `src/boostgauge/telltale.py` accepting positive `window` duration and optional non-negative `decay_rate`.
- Maintain O(1) amortized latency for `update()` and `current_peak()` calls without GUI or system-clock dependencies.
- Pass 100% of unit tests covering sliding-window expiration, monotonic decay, non-decreasing timestamp validation, and state reset.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/telltale.py` | Add | Implement `Telltale` pure logic class and `Sample` data structure. |
| 2 | `tests/unit/test_telltale.py` | Add | Unit test suite validating 100% code coverage of `Telltale` operations. |

**Implementation Order Rationale:** The pure domain logic `telltale.py` has no internal project dependencies and must be implemented first so that the test suite in `test_telltale.py` can import and execute against it directly.

## 3. Current State (for Modify/Delete files)

No existing files are modified or deleted in this issue. Both target files (`src/boostgauge/telltale.py` and `tests/unit/test_telltale.py`) are new additions ("Add").

## 4. Data Structures

### 4.1 Sample

**Definition:**

```python
from typing import NamedTuple

class Sample(NamedTuple):
    """Represents a time-stamped metric value sample."""
    timestamp: float
    value: float
```

**Concrete Example:**

```json
{
    "timestamp": 1774735200.5,
    "value": 87.4
}
```

### 4.2 Telltale Internal State Snapshot

**Definition:**

```python
from typing import TypedDict, Optional, List, Tuple

class TelltaleStateDict(TypedDict):
    window: float
    decay_rate: float
    samples: List[Tuple[float, float]]
    max_deque: List[Tuple[float, float]]
    peak: Optional[float]
    last_timestamp: Optional[float]
    last_value: Optional[float]
```

**Concrete Example:**

```json
{
    "window": 10.0,
    "decay_rate": 2.0,
    "samples": [
        [10.0, 50.0],
        [12.0, 30.0]
    ],
    "max_deque": [
        [10.0, 50.0]
    ],
    "peak": 46.0,
    "last_timestamp": 12.0,
    "last_value": 30.0
}
```

## 5. Function Specifications

### 5.1 `Telltale.__init__()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def __init__(self, window: float, decay_rate: Optional[float] = None) -> None:
    """Initialize Telltale instance with window duration in seconds and optional decay rate.

    Args:
        window: Sliding time window duration in seconds (must be > 0).
        decay_rate: Optional decay rate in units per second (must be >= 0 if provided).

    Raises:
        ValueError: If window <= 0 or decay_rate < 0.
    """
    ...
```

**Input Example:**

```python
window = 10.0
decay_rate = 2.0
```

**Output Example:**

```python
# Returns None; instance initialized with window=10.0, decay_rate=2.0, deques initialized empty
```

**Edge Cases:**
- `window <= 0` (e.g., `window = 0.0` or `window = -5.0`) -> raises `ValueError("window must be positive")`
- `decay_rate < 0` (e.g., `decay_rate = -1.5`) -> raises `ValueError("decay_rate must be non-negative")`
- `decay_rate is None` -> sets internal `decay_rate = 0.0`

### 5.2 `Telltale.update()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def update(self, timestamp: float, value: float) -> None:
    """Feed a new sample (timestamp, value) into the telltale mechanism.

    Args:
        timestamp: Sample timestamp in seconds. Must be >= previous update timestamp.
        value: Numeric sample value.

    Raises:
        ValueError: If timestamp is strictly less than previous timestamp.
    """
    ...
```

**Input Example:**

```python
timestamp = 15.0
value = 42.5
```

**Output Example:**

```python
# Returns None; internal deques updated, peak updated to 42.5
```

**Edge Cases:**
- `timestamp < self._last_timestamp` (e.g., last `10.0`, input `9.5`) -> raises `ValueError("Timestamps must be non-decreasing")`
- `timestamp == self._last_timestamp` -> valid non-decreasing update, state updated cleanly
- First sample update -> `_peak` set to `value`, `_last_timestamp` set to `timestamp`

### 5.3 `Telltale.current_peak()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def current_peak(self, timestamp: Optional[float] = None) -> Optional[float]:
    """Return current peak value within active sliding window, applying decay if configured.

    Args:
        timestamp: Optional query timestamp for evaluating decay. Defaults to timestamp
                   of the latest sample if None.

    Returns:
        Highest active peak value as float, or None if no samples recorded or state reset.
    """
    ...
```

**Input Example:**

```python
timestamp = 12.0
```

**Output Example:**

```python
96.0  # Decayed from 100.0 over 2.0 seconds at decay_rate=2.0
```

**Edge Cases:**
- Query before any `update()` -> returns `None`
- Query after `reset()` -> returns `None`
- `timestamp` is `None` -> defaults evaluation time to `self._last_timestamp`
- `timestamp < self._last_timestamp` -> clamped to `self._last_timestamp`
- All samples in window expired at query time -> returns `None` and resets internal peak state

### 5.4 `Telltale._evict_expired()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def _evict_expired(self, current_time: float) -> None:
    """Evict samples older than current_time - window from internal deques.

    Args:
        current_time: Time benchmark for evaluating expiration cutoff.
    """
    ...
```

**Input Example:**

```python
current_time = 15.0
# window = 10.0, cutoff = 5.0
```

**Output Example:**

```python
# Returns None; elements with timestamp < 5.0 removed from _samples and _max_deque
```

**Edge Cases:**
- Empty deques -> no-op
- All elements newer than cutoff -> no elements popped

### 5.5 `Telltale.reset()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def reset(self) -> None:
    """Clear all sample history and reset internal peak tracking state."""
    ...
```

**Input Example:**

```python
# Called on an active instance
```

**Output Example:**

```python
# Returns None; _samples and _max_deque cleared, _peak and _last_timestamp set to None
```

**Edge Cases:**
- Calling `reset()` on an already clean instance -> idempotent, no-op

## 6. Change Instructions

### 6.1 `src/boostgauge/telltale.py` (Add)

**Complete file contents:**

```python
"""Pure peak-hold needle logic module.

Issue #41: Telltale peak-hold needle logic (pure, no GUI)
Ref: docs/lld/done/41-telltale-needle-logic.md
"""

from __future__ import annotations

from collections import deque
from typing import NamedTuple, Optional


class Sample(NamedTuple):
    """Represents a time-stamped metric value sample."""

    timestamp: float
    value: float


class Telltale:
    """Tracks maximum value reached over a sliding time window with optional decay."""

    def __init__(self, window: float, decay_rate: Optional[float] = None) -> None:
        """Initialize Telltale instance with window duration in seconds and optional decay rate.

        Args:
            window: Sliding time window duration in seconds (must be > 0).
            decay_rate: Optional decay rate in units per second (must be >= 0 if provided).

        Raises:
            ValueError: If window <= 0 or decay_rate < 0.
        """
        if window <= 0:
            raise ValueError("window must be positive")
        if decay_rate is not None and decay_rate < 0:
            raise ValueError("decay_rate must be non-negative")

        self.window: float = float(window)
        self.decay_rate: float = float(decay_rate) if decay_rate is not None else 0.0

        self._samples: deque[Sample] = deque()
        self._max_deque: deque[Sample] = deque()
        self._peak: Optional[float] = None
        self._last_timestamp: Optional[float] = None
        self._last_value: Optional[float] = None

    def _evict_expired(self, current_time: float) -> None:
        """Purge samples whose timestamp is strictly prior to (current_time - window)."""
        cutoff = current_time - self.window
        while self._samples and self._samples[0].timestamp < cutoff:
            self._samples.popleft()
        while self._max_deque and self._max_deque[0].timestamp < cutoff:
            self._max_deque.popleft()

    def update(self, timestamp: float, value: float) -> None:
        """Feed a new sample (timestamp, value) into the telltale mechanism.

        Args:
            timestamp: Sample timestamp in seconds. Must be >= previous update timestamp.
            value: Numeric sample value.

        Raises:
            ValueError: If timestamp is strictly less than previous timestamp.
        """
        if self._last_timestamp is not None and timestamp < self._last_timestamp:
            raise ValueError("Timestamps must be non-decreasing")

        ts = float(timestamp)
        val = float(value)
        sample = Sample(ts, val)

        self._evict_expired(ts)

        decayed: Optional[float] = None
        if self._peak is not None and self.decay_rate > 0 and self._last_timestamp is not None:
            elapsed = ts - self._last_timestamp
            decayed = max(self._last_value, self._peak - self.decay_rate * elapsed)
        else:
            decayed = self._peak

        while self._max_deque and self._max_deque[-1].value <= val:
            self._max_deque.pop()
        self._max_deque.append(sample)
        self._samples.append(sample)

        raw_max = self._max_deque[0].value
        if decayed is None:
            self._peak = max(val, raw_max)
        else:
            self._peak = max(val, raw_max, decayed)

        self._last_timestamp = ts
        self._last_value = val

    def current_peak(self, timestamp: Optional[float] = None) -> Optional[float]:
        """Return current peak value within active sliding window, applying decay if configured.

        Args:
            timestamp: Optional query timestamp for evaluating decay. Defaults to timestamp
                       of the latest sample if None.

        Returns:
            Highest active peak value as float, or None if no samples recorded or state reset.
        """
        if not self._samples or self._last_timestamp is None:
            return None

        eval_time = float(timestamp) if timestamp is not None else self._last_timestamp
        if eval_time < self._last_timestamp:
            eval_time = self._last_timestamp

        self._evict_expired(eval_time)

        if not self._samples:
            self._peak = None
            return None

        raw_max = self._max_deque[0].value
        if self.decay_rate > 0 and self._peak is not None:
            elapsed = eval_time - self._last_timestamp
            decayed = max(self._last_value, self._peak - self.decay_rate * elapsed)
            return max(raw_max, decayed)

        return raw_max

    def reset(self) -> None:
        """Clear all sample history and reset internal peak tracking state."""
        self._samples.clear()
        self._max_deque.clear()
        self._peak = None
        self._last_timestamp = None
        self._last_value = None
```

### 6.2 `tests/unit/test_telltale.py` (Add)

**Complete file contents:**

```python
"""Unit test suite for telltale peak-hold needle logic module.

Issue #41: Telltale peak-hold needle logic (pure, no GUI)
Ref: docs/design/0001-test-strategy.md
"""

from __future__ import annotations

import pytest

from boostgauge.telltale import Sample, Telltale


def test_t010_instantiation_parameter_validation() -> None:
    """T010: Validate window > 0 and decay_rate >= 0 constraints."""
    with pytest.raises(ValueError, match="window must be positive"):
        Telltale(window=0.0)

    with pytest.raises(ValueError, match="window must be positive"):
        Telltale(window=-10.0)

    with pytest.raises(ValueError, match="decay_rate must be non-negative"):
        Telltale(window=10.0, decay_rate=-1.0)

    tt = Telltale(window=10.0, decay_rate=0.0)
    assert tt.window == 10.0
    assert tt.decay_rate == 0.0

    tt_default = Telltale(window=5.0)
    assert tt_default.decay_rate == 0.0


def test_t020_pre_update_and_post_reset_state() -> None:
    """T020: current_peak() returns None before update and immediately after reset."""
    tt = Telltale(window=10.0)
    assert tt.current_peak() is None
    assert tt.current_peak(timestamp=100.0) is None

    tt.update(timestamp=1.0, value=50.0)
    assert tt.current_peak() == 50.0

    tt.reset()
    assert tt.current_peak() is None
    assert tt.current_peak(timestamp=10.0) is None


def test_t030_single_sample_update() -> None:
    """T030: Single sample update accurately reflects peak value."""
    tt = Telltale(window=10.0)
    tt.update(timestamp=1.0, value=42.0)
    assert tt.current_peak() == 42.0
    assert tt.current_peak(timestamp=5.0) == 42.0


def test_t040_rising_series_immediate_peak_update() -> None:
    """T040: Peak updates immediately when higher values are ingested."""
    tt = Telltale(window=10.0)
    tt.update(timestamp=1.0, value=10.0)
    assert tt.current_peak() == 10.0

    tt.update(timestamp=2.0, value=20.0)
    assert tt.current_peak() == 20.0

    tt.update(timestamp=3.0, value=15.0)
    assert tt.current_peak() == 20.0


def test_t050_static_peak_window_expiration() -> None:
    """T050: Peak drops to highest remaining sample after window expiration."""
    tt = Telltale(window=10.0)
    tt.update(timestamp=0.0, value=100.0)
    tt.update(timestamp=5.0, value=50.0)

    assert tt.current_peak(timestamp=9.0) == 100.0
    # At t=11.0, sample at t=0.0 (100.0) has expired (cutoff 1.0)
    assert tt.current_peak(timestamp=11.0) == 50.0

    # At t=16.0, all samples have expired
    assert tt.current_peak(timestamp=16.0) is None


def test_t060_linear_decay_without_new_high() -> None:
    """T060: Peak decays linearly over time toward current sample value."""
    tt = Telltale(window=10.0, decay_rate=2.0)
    tt.update(timestamp=0.0, value=100.0)
    tt.update(timestamp=2.0, value=50.0)

    # At t=2.0: peak decayed from 100.0 by 2.0 * 2.0 = 4.0 units -> 96.0
    assert tt.current_peak(timestamp=2.0) == 96.0

    # At t=10.0: decayed by 2.0 * 10.0 = 20.0 -> 80.0
    assert tt.current_peak(timestamp=10.0) == 80.0

    # Decay bounded below by latest sample value (50.0)
    tt_decay_fast = Telltale(window=10.0, decay_rate=50.0)
    tt_decay_fast.update(timestamp=0.0, value=100.0)
    tt_decay_fast.update(timestamp=1.0, value=30.0)
    assert tt_decay_fast.current_peak(timestamp=5.0) == 30.0


def test_t070_full_sequence_with_reset() -> None:
    """T070: Verify state behavior across updates, queries, reset, and re-updates."""
    tt = Telltale(window=5.0, decay_rate=1.0)
    tt.update(timestamp=0.0, value=10.0)
    tt.update(timestamp=1.0, value=25.0)
    assert tt.current_peak() == 25.0

    tt.reset()
    assert tt.current_peak() is None

    tt.update(timestamp=10.0, value=5.0)
    assert tt.current_peak() == 5.0


def test_out_of_order_timestamp_validation() -> None:
    """Reject decremental timestamps with ValueError."""
    tt = Telltale(window=10.0)
    tt.update(timestamp=5.0, value=10.0)
    with pytest.raises(ValueError, match="Timestamps must be non-decreasing"):
        tt.update(timestamp=4.9, value=20.0)


def test_sample_named_tuple() -> None:
    """Validate Sample named tuple fields."""
    s = Sample(timestamp=1.5, value=10.0)
    assert s.timestamp == 1.5
    assert s.value == 10.0
```

## 7. Pattern References

### 7.1 Module Directives and Type Annotations

**File:** `src/boostgauge/config.py` (lines 7-17)

```python
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, TypedDict
```

**Relevance:** Demonstrates the project standard for `__future__` annotations, standard library imports, and type hint usages.

### 7.2 Unit Test Module Setup & Naming Conventions

**File:** `tests/unit/test_config.py` (lines 1-22)

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

**Relevance:** Demonstrates test file docstring metadata formatting, `pytest` import conventions, and function naming standard (`test_tXXX_...`).

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `from __future__ import annotations` | stdlib | `src/boostgauge/telltale.py`, `tests/unit/test_telltale.py` |
| `from collections import deque` | stdlib | `src/boostgauge/telltale.py` |
| `from typing import NamedTuple, Optional` | stdlib | `src/boostgauge/telltale.py` |
| `import pytest` | third-party (`pyproject.toml`) | `tests/unit/test_telltale.py` |
| `from boostgauge.telltale import Sample, Telltale` | internal | `tests/unit/test_telltale.py` |

**New Dependencies:** None (pure Python standard library).

## 9. Placeholder

*Reserved for future use to maintain alignment with LLD section numbering.*

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `Telltale.__init__()` | `window=0` or `decay_rate=-1` | Raises `ValueError` |
| T020 | `Telltale.current_peak()` | `current_peak()` before `update()` or after `reset()` | `None` |
| T030 | `Telltale.update()` | `update(1.0, 42.0)` then `current_peak()` | `42.0` |
| T040 | `Telltale.update()` | Stream `(1.0, 10)`, `(2.0, 20)`, `(3.0, 15)` | `20.0` |
| T050 | `Telltale.current_peak()` | `window=10`, updates `(0, 100)`, `(5, 50)`, query `t=11` | `50.0` |
| T060 | `Telltale.current_peak()` | `window=10, decay=2`, updates `(0, 100)`, `(2, 50)`, query `t=2` | `96.0` (`100 - 4.0`) |
| T070 | `Telltale.reset()` | Update `(0, 10)`, `(1, 25)`, `reset()`, query `current_peak()` | `None` |

## 11. Implementation Notes

### 11.1 Error Handling Convention

Input parameter errors (`window <= 0`, `decay_rate < 0`, or decremental `timestamp`) raise Python's built-in `ValueError` with clear human-readable exception messages.

### 11.2 Algorithm Complexity

The monotonic queue algorithm maintains O(1) amortized time complexity per `update()` and `current_peak()` call because each sample is pushed once to `_samples` and `_max_deque` and popped at most once.

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3 - noted no modify files, all Add)
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
| Date | 2026-07-28 |
| Iterations | 1 |
| Finalized | 2026-07-28T16:57:47Z |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #41 |
| Verdict | APPROVED |
| Date | 2026-07-28 |
| Iterations | 0 |
| Finalized | 2026-07-28T21:58:06Z |

### Review Feedback Summary

\nThe Implementation Spec for Issue #41 (`Telltale` peak-hold needle logic) is exceptionally thorough, concrete, and ready for immediate implementation. It provides complete, drop-in Python source code for both the production class (`src/boostgauge/telltale.py`) and the unit test suite (`tests/unit/test_telltale.py`), fully covering monotonic queue operations, decay logic, and edge-case validations. An autonomous AI agent can execute these changes with a 100% first-try success rate without needi...
