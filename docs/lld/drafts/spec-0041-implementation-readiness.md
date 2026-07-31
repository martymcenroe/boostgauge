# Implementation Spec: Telltale peak-hold needle logic (pure, no GUI)

<!-- Metadata -->
| Field | Value |
|-------|-------|
| Issue | #41 |
| LLD | `docs/lld/active/41-telltale-peak-hold.md` |
| Generated | 2026-07-31 |
| Status | APPROVED |

## 1. Overview

This implementation provides pure, GUI-decoupled peak-hold needle logic (`Telltale`) for resource tachometers. The module tracks historical maximum sample values across a sliding time window and supports an optional linear decay rate for expired peaks while remaining strictly bounded below by the active window's maximum sample.

**Objective:** Add pure peak-hold needle logic (`Telltale`) that tracks maximum sample values over a sliding time window with optional linear decay.

**Success Criteria:**
1. `Telltale` class is exposed in `src/boostgauge/telltale.py` and exported cleanly.
2. `__init__` validates parameters (`window > 0`, `decay_rate >= 0`), raising `ValueError` on invalid inputs.
3. `update()` ingests `(timestamp, value)` samples, enforcing monotonic non-decreasing timestamps in $O(1)$ amortized time.
4. `current_peak()` calculates the maximum active or decayed peak in $O(1)$ amortized time.
5. `reset()` clears all historical state, causing subsequent `current_peak()` calls to return `None` until new updates arrive.
6. 100% test coverage in `tests/unit/test_telltale.py` across all defined test scenarios (010–061).

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/telltale.py` | Add | Core `Sample` frozen dataclass and `Telltale` peak-hold sliding window class |
| 2 | `tests/unit/test_telltale.py` | Add | Unit test suite for peak tracking, monotonic max deque, linear decay, time advancement, edge cases, and reset |

**Implementation Order Rationale:** `src/boostgauge/telltale.py` defines the domain model (`Sample`) and algorithm (`Telltale`) with zero internal or external third-party dependencies. `tests/unit/test_telltale.py` depends on `src/boostgauge/telltale.py` to run unit test verification.

## 3. Current State (for Modify/Delete files)

*No existing files are modified or deleted in this issue. All files are new ("Add").*

### 3.1 `src/boostgauge/telltale.py`

**Relevant excerpt:** N/A (New file being added).

**What changes:** Create new file containing `Sample` dataclass and `Telltale` class logic.

### 3.2 `tests/unit/test_telltale.py`

**Relevant excerpt:** N/A (New file being added).

**What changes:** Create new unit test file covering scenarios 010 through 061.

## 4. Data Structures

### 4.1 `Sample` Frozen Dataclass

**Definition:**

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Sample:
    timestamp: float
    value: float
```

**Concrete Example:**

```json
{
    "timestamp": 1770000000.5,
    "value": 85.4
}
```

### 4.2 Internal `Telltale` State Representation

**Definition:**

```python
from collections import deque
from typing import Optional, TypedDict

class SampleDict(TypedDict):
    timestamp: float
    value: float

class TelltaleStateDict(TypedDict):
    window: float
    decay_rate: Optional[float]
    samples: list[SampleDict]
    max_deque: list[SampleDict]
    decay_peak: Optional[SampleDict]
    last_update_time: Optional[float]
```

**Concrete Example:**

```json
{
    "window": 10.0,
    "decay_rate": 15.0,
    "samples": [
        {"timestamp": 9.0, "value": 40.0}
    ],
    "max_deque": [
        {"timestamp": 9.0, "value": 40.0}
    ],
    "decay_peak": {
        "timestamp": 0.0,
        "value": 100.0
    },
    "last_update_time": 9.0
}
```

## 5. Function Specifications

### 5.1 `Telltale.__init__()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def __init__(self, window: float, decay_rate: Optional[float] = None) -> None:
    """Initialize Telltale with window duration in seconds and optional decay_rate.

    Args:
        window: Duration of the sliding time window in seconds (> 0).
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
None
```

**Edge Cases:**
- `window = 0.0` or `window = -5.0` -> raises `ValueError("Window must be positive")`
- `decay_rate = -1.0` -> raises `ValueError("Decay rate must be non-negative")`

### 5.2 `Telltale.update()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def update(self, timestamp: float, value: float) -> None:
    """Feed a new sample (timestamp, value) into the telltale history.

    Args:
        timestamp: Monotonic sample timestamp in seconds.
        value: Scalar sample metric value.

    Raises:
        ValueError: If timestamp is smaller than the previous update timestamp.
    """
    ...
```

**Input Example:**

```python
timestamp = 10.0
value = 100.0
```

**Output Example:**

```python
None
```

**Edge Cases:**
- `timestamp < self._last_update_time` (e.g. `_last_update_time = 10.0`, `timestamp = 9.9`) -> raises `ValueError("Timestamps must be non-decreasing")`
- `timestamp == self._last_update_time` (e.g. `10.0 == 10.0`) -> valid, ingested cleanly.

### 5.3 `Telltale.current_peak()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def current_peak(self, timestamp: Optional[float] = None) -> Optional[float]:
    """Return the highest value within the active window, considering decay.

    Args:
        timestamp: Query timestamp in seconds. Defaults to latest sample timestamp.

    Returns:
        The active peak value, or None if no samples have been recorded or state is reset.

    Raises:
        ValueError: If query timestamp is behind the latest sample update.
    """
    ...
```

**Input Example:**

```python
timestamp = 12.0
```

**Output Example:**

```python
70.0
```

**Edge Cases:**
- Called before any `update()` call -> returns `None`
- `timestamp < self._last_update_time` -> raises `ValueError("Query timestamp cannot be behind latest sample update")`
- Called after `reset()` -> returns `None`

### 5.4 `Telltale._advance_to()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def _advance_to(self, t_target: float) -> None:
    """Evict expired samples relative to t_target and update decay tracking."""
    ...
```

**Input Example:**

```python
t_target = 12.0
```

**Output Example:**

```python
None
```

**Edge Cases:**
- Evicts expired samples where `sample.timestamp < t_target - window`.
- Retains expired sample in `_decay_peak` if its calculated decay value at `t_target` exceeds the existing decay candidate.
- Clears `_decay_peak` when its calculated decay value drops to `<= 0`.

### 5.5 `Telltale.reset()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def reset(self) -> None:
    """Clear all sample history and reset internal peak state."""
    ...
```

**Input Example:**

```python
# No parameters
```

**Output Example:**

```python
None
```

**Edge Cases:**
- Called on fresh instance -> no-op, clears empty deques safely.

## 6. Change Instructions

### 6.1 `src/boostgauge/telltale.py` (Add)

**Complete file contents:**

```python
"""Peak-hold telltale needle logic for system gauges.

Issue #41: Telltale peak-hold needle logic (pure, no GUI)
"""

from collections import deque
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Sample:
    """Represents a single system sample with a timestamp and scalar value."""

    timestamp: float
    value: float


class Telltale:
    """Tracks peak values over a sliding time window with optional linear decay."""

    def __init__(self, window: float, decay_rate: Optional[float] = None) -> None:
        """Initialize Telltale with window duration in seconds and optional decay_rate.

        Args:
            window: Sliding time window duration in seconds (> 0).
            decay_rate: Optional linear decay rate in units per second (>= 0).

        Raises:
            ValueError: If window <= 0 or decay_rate < 0.
        """
        if window <= 0:
            raise ValueError("Window must be positive")
        if decay_rate is not None and decay_rate < 0:
            raise ValueError("Decay rate must be non-negative")

        self._window: float = float(window)
        self._decay_rate: Optional[float] = (
            float(decay_rate) if decay_rate is not None else None
        )
        self._samples: deque[Sample] = deque()
        self._max_deque: deque[Sample] = deque()
        self._decay_peak: Optional[Sample] = None
        self._last_update_time: Optional[float] = None

    def update(self, timestamp: float, value: float) -> None:
        """Feed a new sample (timestamp, value) into the telltale history.

        Args:
            timestamp: Sample timestamp in seconds.
            value: Scalar sample value.

        Raises:
            ValueError: If timestamp is earlier than the previous update timestamp.
        """
        if self._last_update_time is not None and timestamp < self._last_update_time:
            raise ValueError("Timestamps must be non-decreasing")

        ts = float(timestamp)
        val = float(value)
        self._last_update_time = ts
        new_sample = Sample(ts, val)

        while self._max_deque and self._max_deque[-1].value <= val:
            self._max_deque.pop()
        self._max_deque.append(new_sample)
        self._samples.append(new_sample)

        self._advance_to(ts)

    def current_peak(self, timestamp: Optional[float] = None) -> Optional[float]:
        """Return the highest value within the active window, considering decay.

        Args:
            timestamp: Optional query timestamp. Defaults to latest sample timestamp.

        Returns:
            The peak value, or None if no samples have been recorded.

        Raises:
            ValueError: If timestamp is earlier than the latest update timestamp.
        """
        if self._last_update_time is None:
            return None

        t_query = float(timestamp) if timestamp is not None else self._last_update_time
        if t_query < self._last_update_time:
            raise ValueError("Query timestamp cannot be behind latest sample update")

        self._advance_to(t_query)

        active_window_max: Optional[float] = (
            self._max_deque[0].value if self._max_deque else None
        )

        decayed_val: Optional[float] = None
        if self._decay_peak is not None and self._decay_rate is not None and self._decay_rate > 0:
            expired_time = t_query - (self._decay_peak.timestamp + self._window)
            if expired_time >= 0:
                calc_decay = self._decay_peak.value - (self._decay_rate * expired_time)
                if calc_decay > 0:
                    decayed_val = calc_decay

        if active_window_max is None and decayed_val is None:
            return None
        if active_window_max is None:
            return decayed_val
        if decayed_val is None:
            return active_window_max

        return max(active_window_max, decayed_val)

    def _advance_to(self, t_target: float) -> None:
        """Evict expired samples relative to t_target and update decay tracking."""
        cutoff = t_target - self._window
        while self._samples and self._samples[0].timestamp < cutoff:
            expired_sample = self._samples.popleft()

            if self._max_deque and self._max_deque[0].timestamp == expired_sample.timestamp:
                self._max_deque.popleft()

            if self._decay_rate is not None and self._decay_rate > 0:
                exp_time = t_target - (expired_sample.timestamp + self._window)
                exp_decayed = expired_sample.value - (self._decay_rate * exp_time)
                if exp_decayed > 0:
                    if self._decay_peak is None:
                        self._decay_peak = expired_sample
                    else:
                        curr_exp_time = t_target - (self._decay_peak.timestamp + self._window)
                        curr_decayed = self._decay_peak.value - (self._decay_rate * curr_exp_time)
                        if exp_decayed >= curr_decayed:
                            self._decay_peak = expired_sample

        if self._decay_peak is not None and self._decay_rate is not None and self._decay_rate > 0:
            curr_exp_time = t_target - (self._decay_peak.timestamp + self._window)
            if self._decay_peak.value - (self._decay_rate * curr_exp_time) <= 0:
                self._decay_peak = None

    def reset(self) -> None:
        """Clear all sample history and reset internal peak state."""
        self._samples.clear()
        self._max_deque.clear()
        self._decay_peak = None
        self._last_update_time = None
```

### 6.2 `tests/unit/test_telltale.py` (Add)

**Complete file contents:**

```python
"""Unit tests for Telltale peak-hold sliding window and decay tracking.

Issue #41: Telltale peak-hold needle logic (pure, no GUI)
"""

import pytest

from boostgauge.telltale import Sample, Telltale


def test_scenario_010_expose_telltale_class():
    """Scenario 010: Expose Telltale class in src/boostgauge/telltale.py (REQ-1)."""
    tt = Telltale(window=10.0)
    assert isinstance(tt, Telltale)
    sample = Sample(timestamp=1.0, value=50.0)
    assert sample.timestamp == 1.0
    assert sample.value == 50.0


def test_scenario_020_valid_initialization():
    """Scenario 020: Valid window and decay_rate initialization (REQ-2)."""
    tt = Telltale(window=10.0, decay_rate=5.0)
    assert tt._window == 10.0
    assert tt._decay_rate == 5.0

    tt_no_decay = Telltale(window=60.0)
    assert tt_no_decay._window == 60.0
    assert tt_no_decay._decay_rate is None


def test_scenario_021_invalid_window_raises_value_error():
    """Scenario 021: Invalid window <= 0 raises ValueError (REQ-2)."""
    with pytest.raises(ValueError, match="Window must be positive"):
        Telltale(window=0.0)

    with pytest.raises(ValueError, match="Window must be positive"):
        Telltale(window=-1.0)


def test_scenario_022_invalid_negative_decay_rate_raises_value_error():
    """Scenario 022: Invalid negative decay_rate raises ValueError (REQ-2)."""
    with pytest.raises(ValueError, match="Decay rate must be non-negative"):
        Telltale(window=10.0, decay_rate=-5.0)


def test_scenario_030_single_sample_update():
    """Scenario 030: Single sample update (REQ-3)."""
    tt = Telltale(window=10.0)
    tt.update(timestamp=1.0, value=25.0)
    assert len(tt._samples) == 1
    assert tt._last_update_time == 1.0


def test_scenario_031_monotonic_timestamp_progression():
    """Scenario 031: Monotonic timestamp progression (REQ-3)."""
    tt = Telltale(window=10.0)
    tt.update(timestamp=1.0, value=10.0)
    tt.update(timestamp=2.0, value=20.0)
    tt.update(timestamp=2.0, value=25.0)  # Same timestamp allowed
    assert tt._last_update_time == 2.0


def test_scenario_032_decreasing_timestamp_raises_value_error():
    """Scenario 032: Decreasing timestamp update raises ValueError (REQ-3)."""
    tt = Telltale(window=10.0)
    tt.update(timestamp=10.0, value=50.0)
    with pytest.raises(ValueError, match="Timestamps must be non-decreasing"):
        tt.update(timestamp=9.5, value=60.0)


def test_scenario_040_pre_first_update_current_peak_returns_none():
    """Scenario 040: Pre-first-update current_peak returns None (REQ-4)."""
    tt = Telltale(window=10.0)
    assert tt.current_peak() is None
    assert tt.current_peak(timestamp=5.0) is None


def test_scenario_041_single_sample_current_peak_equals_value():
    """Scenario 041: Single sample current_peak equals sample value (REQ-4)."""
    tt = Telltale(window=10.0)
    tt.update(timestamp=5.0, value=42.0)
    assert tt.current_peak() == 42.0
    assert tt.current_peak(timestamp=5.0) == 42.0


def test_scenario_042_rising_series_peak_equals_maximum():
    """Scenario 042: Rising series peak equals maximum value so far (REQ-4)."""
    tt = Telltale(window=10.0)
    tt.update(timestamp=1.0, value=10.0)
    assert tt.current_peak() == 10.0
    tt.update(timestamp=2.0, value=30.0)
    assert tt.current_peak() == 30.0
    tt.update(timestamp=3.0, value=20.0)
    assert tt.current_peak() == 30.0  # Max remains 30.0


def test_scenario_043_window_expiration_without_decay_drops_peak():
    """Scenario 043: Window expiration without decay drops peak to active window maximum (REQ-4)."""
    tt = Telltale(window=10.0)
    tt.update(timestamp=0.0, value=100.0)
    tt.update(timestamp=5.0, value=40.0)
    assert tt.current_peak(timestamp=5.0) == 100.0

    # At t=10.1, sample at t=0.0 (value=100.0) is expired (cutoff=0.1)
    assert tt.current_peak(timestamp=10.1) == 40.0


def test_scenario_050_decay_enabled_former_high_descends():
    """Scenario 050: Decay enabled former high ages out descending at decay_rate (REQ-5)."""
    tt = Telltale(window=10.0, decay_rate=15.0)
    tt.update(timestamp=0.0, value=100.0)
    tt.update(timestamp=9.0, value=40.0)

    # At t=12.0, sample (0.0, 100.0) expired at t=10.0.
    # Expired duration = 12.0 - 10.0 = 2.0s.
    # Decayed value = 100.0 - (15.0 * 2.0) = 70.0.
    assert tt.current_peak(timestamp=12.0) == 70.0


def test_scenario_051_decay_floor_bounded_by_active_window_max():
    """Scenario 051: Decay floor bounded strictly by active window maximum (REQ-5)."""
    tt = Telltale(window=10.0, decay_rate=15.0)
    tt.update(timestamp=0.0, value=100.0)
    tt.update(timestamp=9.0, value=40.0)

    # At t=15.0, sample (0.0, 100.0) decay = 100 - 15*(15-10) = 25.0.
    # Active window max from (9.0, 40.0) is 40.0.
    # MAX(40.0, 25.0) = 40.0 (floored by active window max).
    assert tt.current_peak(timestamp=15.0) == 40.0


def test_scenario_052_new_higher_sample_resets_decaying_peak():
    """Scenario 052: New higher sample immediately resets decaying peak upward (REQ-5)."""
    tt = Telltale(window=10.0, decay_rate=15.0)
    tt.update(timestamp=0.0, value=100.0)
    assert tt.current_peak(timestamp=12.0) == 70.0

    # Ingest new spike of 120.0 at t=12.5
    tt.update(timestamp=12.5, value=120.0)
    assert tt.current_peak(timestamp=12.5) == 120.0


def test_scenario_060_reset_clears_sample_history_and_decay():
    """Scenario 060: Reset clears sample history and decay state returning None (REQ-6)."""
    tt = Telltale(window=10.0, decay_rate=15.0)
    tt.update(timestamp=0.0, value=100.0)
    tt.update(timestamp=5.0, value=50.0)
    assert tt.current_peak() == 100.0

    tt.reset()
    assert tt.current_peak() is None
    assert len(tt._samples) == 0
    assert len(tt._max_deque) == 0
    assert tt._decay_peak is None
    assert tt._last_update_time is None


def test_scenario_061_update_after_reset_reestablishes_tracking():
    """Scenario 061: Update following reset re-establishes peak tracking (REQ-6)."""
    tt = Telltale(window=10.0, decay_rate=15.0)
    tt.update(timestamp=0.0, value=100.0)
    tt.reset()

    tt.update(timestamp=20.0, value=80.0)
    assert tt.current_peak() == 80.0
    assert tt.current_peak(timestamp=20.0) == 80.0


def test_query_behind_latest_update_raises_value_error():
    """Edge case: Query timestamp earlier than latest sample update timestamp."""
    tt = Telltale(window=10.0)
    tt.update(timestamp=10.0, value=50.0)
    with pytest.raises(ValueError, match="Query timestamp cannot be behind latest sample update"):
        tt.current_peak(timestamp=9.0)
```

## 7. Pattern References

### 7.1 Test Bootstrap Pattern

**File:** `tests/conftest.py` (lines 1-8)

```python
"""Project test bootstrap."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
```

**Relevance:** Demonstrates standard project path insertion for pure unit tests resolving against `src/boostgauge`.

### 7.2 Pytest importlib Mode & Unit Conventions

**File:** `pyproject.toml` (lines 35-43)

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-ra --strict-markers --import-mode=importlib"
```

**Relevance:** Governs module loading and test discovery standards for unit test suites located under `tests/unit/`.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `from collections import deque` | stdlib | `src/boostgauge/telltale.py` |
| `from dataclasses import dataclass` | stdlib | `src/boostgauge/telltale.py` |
| `from typing import Optional` | stdlib | `src/boostgauge/telltale.py` |
| `import pytest` | dev dependency | `tests/unit/test_telltale.py` |
| `from boostgauge.telltale import Sample, Telltale` | internal | `tests/unit/test_telltale.py` |

**New Dependencies:** None (uses standard library and existing dev dependency `pytest`).

## 9. Placeholder

*Reserved for future use to maintain alignment with LLD section numbering.*

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `Telltale.__init__()`, `Sample.__init__()` | `Telltale(window=10.0)`, `Sample(1.0, 50.0)` | Exposes `Telltale` class, creates immutable sample (REQ-1) |
| T020 | `Telltale.__init__()` | `window=10.0, decay_rate=5.0` | `_window=10.0, _decay_rate=5.0` stored cleanly (REQ-2) |
| T021 | `Telltale.__init__()` | `window=0.0` / `window=-1.0` | Raises `ValueError("Window must be positive")` (REQ-2) |
| T022 | `Telltale.__init__()` | `window=10.0, decay_rate=-5.0` | Raises `ValueError("Decay rate must be non-negative")` (REQ-2) |
| T030 | `Telltale.update()` | `timestamp=1.0, value=25.0` | Appends sample, updates `_last_update_time` (REQ-3) |
| T031 | `Telltale.update()` | `t=1.0, v=10`, `t=2.0, v=20`, `t=2.0, v=25` | Ingests non-decreasing timestamps cleanly (REQ-3) |
| T032 | `Telltale.update()` | `t=10.0, v=50`, then `t=9.5, v=60` | Raises `ValueError("Timestamps must be non-decreasing")` (REQ-3) |
| T040 | `Telltale.current_peak()` | Pre-update query `t=None` or `t=5.0` | Returns `None` (REQ-4) |
| T041 | `Telltale.current_peak()` | `update(5.0, 42.0)`, query `t=5.0` | Returns `42.0` (REQ-4) |
| T042 | `Telltale.current_peak()` | `(1,10), (2,30), (3,20)`, query `t=3.0` | Returns `30.0` (REQ-4) |
| T043 | `Telltale.current_peak()` | `w=10, decay=None, (0,100), (5,40)`, query `t=10.1` | Returns `40.0` (hard window drop without decay) (REQ-4) |
| T050 | `Telltale.current_peak()` | `w=10, decay=15, (0,100), (9,40)`, query `t=12.0` | Returns `70.0` (`100 - 15 * (12 - 10)`) (REQ-5) |
| T051 | `Telltale.current_peak()` | `w=10, decay=15, (0,100), (9,40)`, query `t=15.0` | Returns `40.0` (floored at active window max) (REQ-5) |
| T052 | `Telltale.current_peak()` | Decaying peak at `t=12.0`, update `(12.5, 120.0)` | Returns `120.0` immediately (REQ-5) |
| T060 | `Telltale.reset()` | `(0,100), (5,50)`, call `reset()` | Clears internal deques; `current_peak()` returns `None` (REQ-6) |
| T061 | `Telltale.update()` | `(0,100)`, `reset()`, update `(20,80)` | Returns `80.0` cleanly (REQ-6) |

## 11. Implementation Notes

### 11.1 Error Handling Convention

- Parameter validation in `__init__()`, `update()`, and `current_peak()` uses standard `ValueError` with clear, human-readable error messages.
- Queries prior to any data ingestion return `None` rather than raising exceptions.

### 11.2 Algorithm & Complexity Mechanics

- **Monotonic Max Deque:** `_max_deque` maintains samples in strictly decreasing value order. When a new sample arrives, all back items with `value <= new_sample.value` are popped in $O(1)$ amortized time. The front of `_max_deque` always holds the current active window maximum.
- **Single Decay Candidate:** All expired samples decay at the identical uniform rate `decay_rate`. Consequently, their relative order of decayed values does not change over time. When samples pass out of the active window (`s.timestamp < t_target - window`), the sample producing the highest remaining decay value at `t_target` is stored in `_decay_peak`.
- **Active Floor Bounding:** `current_peak()` evaluates `max(active_window_max, decayed_val)` so the decay curve never drops below the highest value among samples currently inside the active window.

### 11.3 Baseline-Independent Assertions

- All test assertions in `tests/unit/test_telltale.py` compute exact mathematical values (e.g. `100.0 - 15.0 * 2.0 = 70.0`) based on pure inputs without relying on external state, GUI baseline images, or environment configuration.

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
| Issue | #41 |
| Verdict | APPROVED |
| Date | 2026-07-31 |
| Iterations | 1 |
| Finalized | 2026-07-31T13:44:10-05:00 |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #41 |
| Verdict | APPROVED |
| Date | 2026-07-31 |
| Iterations | 0 |
| Finalized | 2026-07-31T18:44:50Z |

### Review Feedback Summary

The implementation spec for Issue #41 provides comprehensive, diff-ready Python source code and unit tests for the pure Telltale peak-hold needle logic. All function specifications, data structures, and algorithms (dual-deque sliding window with single-candidate linear decay tracking for O(1) amortized performance) are fully specified with concrete examples and edge cases. Every test assertion across scenarios 010–061 traces directly to requirements REQ-1 through REQ-6 and computes exact mathema...
