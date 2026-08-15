# Implementation Spec: Issue #41 - Feature: Telltale peak-hold needle logic (pure, no GUI)

| Field | Value |
|-------|-------|
| Issue | #41 |
| LLD | `docs/lld/active/0041-telltale-logic.md` |
| Generated | 2026-08-15 |
| Status | DRAFT |

## 1. Overview

**Objective:** Implement the peak-hold "telltale" logic as a pure, deterministic class `Telltale` that tracks the maximum value reached over a sliding time window with optional linear decay.

**Success Criteria:** A 100% pure logic `Telltale` class that correctly holds peak values, ages out old samples, applies linear decay where configured, and rejects invalid non-monotonic timestamps, fully verified by a comprehensive unit test suite with no GUI dependencies.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/telltale.py` | Add | Implements the pure `Telltale` class and `Sample` data structure. |
| 2 | `tests/unit/test_telltale.py` | Add | 100% pure logic test suite without GUI/Tkinter dependencies covering all scenarios. |

**Implementation Order Rationale:** The test suite depends on the `Telltale` module's implementation, but following TDD they can be developed concurrently. `telltale.py` is written first to establish the API.

## 3. Current State (for Modify/Delete files)

*N/A - All files in this implementation are new additions. No existing files are being modified or deleted.*

## 4. Data Structures

### 4.1 `Sample`

**Definition:**

```python
from dataclasses import dataclass

@dataclass
class Sample:
    timestamp: float
    value: float
```

**Concrete Example:**

```python
Sample(timestamp=1738401200.5, value=85.4)
```

## 5. Function Specifications

### 5.1 `Telltale.__init__()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def __init__(self, window: float | None, decay_rate: float | None = None) -> None:
    """Initialize the telltale with a window duration and optional decay rate."""
    ...
```

**Input Example:**

```python
window = 10.0
decay_rate = 5.0
```

**Output Example:**

```python
# Returns initialized Telltale instance where:
# self._window == 10.0
# self._decay_rate == 5.0
# self._history == []
# self._max_timestamp == float('-inf')
```

**Edge Cases:**
- `window <= 0` -> raises `ValueError("window must be None or greater than zero")`
- `decay_rate <= 0` -> raises `ValueError("decay_rate must be None or greater than zero")`

### 5.2 `Telltale.update()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def update(self, timestamp: float, value: float) -> None:
    """Feed a new sample. Timestamp must be >= any previously fed timestamp since reset."""
    ...
```

**Input Example:**

```python
timestamp = 1.5
value = 100.0
```

**Output Example:**

```python
# Returns None. Internal state updated:
# self._max_timestamp = 1.5
# self._history appends Sample(1.5, 100.0)
```

**Edge Cases:**
- `timestamp < self._max_timestamp` -> raises `ValueError("timestamp must be >= any previously fed timestamp")`
- `timestamp == self._max_timestamp` -> appends successfully without raising

### 5.3 `Telltale.current_peak()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def current_peak(self) -> float | None:
    """Return the maximum contribution among held samples."""
    ...
```

**Input Example:**

```python
# No arguments required. Relies on internal state.
# Suppose state has: window=10.0, _max_timestamp=15.0
# _history = [Sample(0.0, 100.0), Sample(15.0, 40.0)]
```

**Output Example:**

```python
40.0
```

**Edge Cases:**
- `self._history` is empty -> returns `None`
- `window is None` -> samples never age out, max of all history is returned

### 5.4 `Telltale.reset()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def reset(self) -> None:
    """Discard all held samples and reset the timestamp tracker."""
    ...
```

**Input Example:**

```python
# No arguments required.
```

**Output Example:**

```python
# Returns None. Internal state reset:
# self._history = []
# self._max_timestamp = float('-inf')
```

**Edge Cases:**
- Called when already empty -> safely does nothing, state remains empty

## 6. Change Instructions

### 6.1 `src/boostgauge/telltale.py` (Add)

**Complete file contents:**

```python
"""Peak-hold telltale needle logic for boostgauge.

Issue #41: Telltale peak-hold needle logic (pure, no GUI)
"""

from dataclasses import dataclass


@dataclass
class Sample:
    """A single data point recorded by the telltale."""
    timestamp: float
    value: float


class Telltale:
    """Tracks the peak value of a time series over a sliding window with optional decay."""

    def __init__(self, window: float | None, decay_rate: float | None = None) -> None:
        """Initialize the telltale with a window duration and optional decay rate.
        
        Args:
            window: Duration in seconds to hold a peak without decay, or None for all-time.
            decay_rate: Units per second to decrease a value after it ages out of the window.
        """
        if window is not None and window <= 0:
            raise ValueError("window must be None or greater than zero")
        if decay_rate is not None and decay_rate <= 0:
            raise ValueError("decay_rate must be None or greater than zero")
            
        self._window = window
        self._decay_rate = decay_rate
        self._history: list[Sample] = []
        self._max_timestamp: float = float('-inf')

    def update(self, timestamp: float, value: float) -> None:
        """Feed a new sample.
        
        Args:
            timestamp: The time of the sample. Must be >= any previously fed timestamp.
            value: The value of the sample.
            
        Raises:
            ValueError: If timestamp is less than a previously fed timestamp.
        """
        if self._max_timestamp != float('-inf') and timestamp < self._max_timestamp:
            raise ValueError("timestamp must be >= any previously fed timestamp")
            
        self._history.append(Sample(timestamp, value))
        self._max_timestamp = timestamp

    def current_peak(self) -> float | None:
        """Return the maximum contribution among held samples."""
        if not self._history:
            return None
            
        max_contribution = float('-inf')
        
        for sample in self._history:
            age = self._max_timestamp - sample.timestamp
            
            if self._window is None or age <= self._window:
                contribution = sample.value
            elif self._decay_rate is None:
                continue
            else:
                departure_time = sample.timestamp + self._window
                elapsed = self._max_timestamp - departure_time
                contribution = sample.value - (self._decay_rate * elapsed)
                
            if contribution > max_contribution:
                max_contribution = contribution
                
        return max_contribution if max_contribution != float('-inf') else None

    def reset(self) -> None:
        """Discard all held samples and reset the timestamp tracker."""
        self._history.clear()
        self._max_timestamp = float('-inf')
```

### 6.2 `tests/unit/test_telltale.py` (Add)

**Complete file contents:**

See Section 10.1 for the complete contents of this file (test functions covering all scenarios). The file will structure as follows:

```python
"""Unit tests for the pure Telltale peak-hold logic."""

import pytest
from boostgauge.telltale import Telltale

# Test functions from Section 10.1 go here verbatim.
```

## 7. Pattern References

### 7.1 DataClass usage

**File:** `src/boostgauge/collector.py` (lines 6-10)

```python
from dataclasses import dataclass

@dataclass
class SystemSnapshot:
    """Snapshot of system resource metrics at a point in time."""
```

**Relevance:** The new `Sample` object should use standard library `dataclass` just as `SystemSnapshot` does, avoiding heavier constructs like `pydantic` for simple in-memory value types.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `from dataclasses import dataclass` | stdlib | `src/boostgauge/telltale.py` |
| `import pytest` | external | `tests/unit/test_telltale.py` |
| `from boostgauge.telltale import Telltale` | internal | `tests/unit/test_telltale.py` |

**New Dependencies:** None (pure stdlib usage in source, pytest already standard for tests).

## 9. Placeholder

*Reserved for future use to maintain alignment with LLD section numbering.*

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `current_peak()` | `Telltale(10.0)` | `None` |
| T020 | `reset()` | `Telltale(10.0).reset()` | `None` |
| T030 | `current_peak()` | `up(3, 42.5)` | `42.5` |
| T040 | `current_peak()` | `up(0,10), up(1,20), up(2,30)` | `30.0` |
| T050 | `current_peak()` | `T(10, 15).up(0,100), up(5,0)` | `100.0` |
| T060 | `current_peak()` | `up(0,100), up(10,0)` | `100.0` |
| T070 | `current_peak()` | `up(5,1), up(5,3)` | `3.0` |
| T080 | `reset()` | `T(10,15).up(0,100), reset(), up(10.5,7)`| `7.0` |
| T090 | `update()` | `up(5,1), up(4.9,9)` | Raises `ValueError`, Peak `1.0`|
| T100 | `reset()` | `up(100,1), reset(), up(10,7)`| `7.0` |
| T110 | `current_peak()` | `T(10).up(0,100), up(9,40), up(10.5,0)`| `40.0` |
| T120 | `current_peak()` | `T(10).up(0,-5), up(11,-20)` | `-20.0` |
| T130 | `current_peak()` | `T(10, 15).up(0,100), up(9,40), up(12,0)` | `70.0` |
| T140 | `current_peak()` | Same as D1, then `up(15,0)` | `40.0` |
| T150 | `current_peak()` | Same as D1, then `up(12.5,80)` | `80.0` |
| T160 | `current_peak()` | `T(10,15).up(0,100), up(5,90), up(16,0)` | `75.0` |
| T170 | `current_peak()` | Same as D1, read 3 times | `70.0` (all 3 times) |
| T180 | `current_peak()` | `T(None).up(0,100), up(1M,5)` | `100.0` |
| T190 | `current_peak()` | `T(None, 15).up(0,100), up(1M,5)` | `100.0` |
| T200 | `__init__()` | `Telltale(0)` | Raises `ValueError` |
| T210 | `__init__()` | `Telltale(10, -3)` | Raises `ValueError` |
| T220 | `update()` | `up(5,1), up(4.9,1)` | Raises `ValueError` |
| T230 | `update()` | `up(5,1), up(5,3)` | `current_peak() == 3.0` |

### 10.1 Per-criterion test functions

```python
def test_req_5_t010_fresh_construction():
    # Freshly constructed returns None (REQ-5)
    # Expected: None
    t = Telltale(10.0)
    assert t.current_peak() is None

def test_req_3_t020_reset_clears_history():
    # Reset clears history to None (REQ-3)
    # Expected: None
    t = Telltale(10.0)
    t.update(0.0, 100.0)
    t.reset()
    assert t.current_peak() is None

def test_req_6_t030_single_sample():
    # Single sample (REQ-6)
    # Expected: 42.5
    t = Telltale(10.0)
    t.update(3.0, 42.5)
    assert t.current_peak() == 42.5

def test_req_6_t040_rising_series():
    # Rising series (REQ-6)
    # Expected: 30.0
    t = Telltale(10.0)
    t.update(0.0, 10.0)
    t.update(1.0, 20.0)
    t.update(2.0, 30.0)
    assert t.current_peak() == 30.0

def test_req_9_t050_in_window_values_never_decay():
    # In-window values never decay (REQ-9)
    # Expected: 100.0
    t = Telltale(10.0, 15.0)
    t.update(0.0, 100.0)
    t.update(5.0, 0.0)
    assert t.current_peak() == 100.0

def test_req_6_t060_closed_boundary():
    # Closed boundary (REQ-6)
    # Expected: 100.0
    t = Telltale(10.0)
    t.update(0.0, 100.0)
    t.update(10.0, 0.0)
    assert t.current_peak() == 100.0

def test_req_13_t070_equal_timestamps():
    # Equal timestamps (REQ-13)
    # Expected: 3.0
    t = Telltale(10.0)
    t.update(5.0, 1.0)
    t.update(5.0, 3.0)
    assert t.current_peak() == 3.0

def test_req_3_t080_reset_discards_tracks():
    # Reset discards decay tracks (REQ-3)
    # Expected: 7.0
    t = Telltale(10.0, 15.0)
    t.update(0.0, 100.0)
    t.reset()
    t.update(10.5, 7.0)
    assert t.current_peak() == 7.0

def test_req_10_t090_reject_protects_history():
    # Rejected update protects history (REQ-10)
    # Expected: 1.0
    t = Telltale(10.0)
    t.update(5.0, 1.0)
    with pytest.raises(ValueError):
        t.update(4.9, 9.0)
    assert t.current_peak() == 1.0

def test_req_2_t100_contract_restarts_at_reset():
    # Restart monotonic contract (REQ-2)
    # Expected: 7.0 (no exception)
    t = Telltale(10.0)
    t.update(100.0, 1.0)
    t.reset()
    t.update(10.0, 7.0)
    assert t.current_peak() == 7.0

def test_req_8_t110_hard_hold_drop():
    # Hard hold drop - sample drops cleanly without decay (REQ-8)
    # Expected: 40.0
    t = Telltale(10.0)
    t.update(0.0, 100.0)
    t.update(9.0, 40.0)
    t.update(10.5, 0.0)
    assert t.current_peak() == 40.0

def test_req_8_t120_exclusion_not_a_zero():
    # Exclusion is not a zero (REQ-8)
    # Expected: -20.0
    t = Telltale(10.0)
    t.update(0.0, -5.0)
    t.update(11.0, -20.0)
    assert t.current_peak() == -20.0

def test_req_9_t130_decay_track():
    # Decay track (REQ-9)
    # Expected: 70.0
    t = Telltale(10.0, 15.0)
    t.update(0.0, 100.0)
    t.update(9.0, 40.0)
    t.update(12.0, 0.0)
    # Elapsed departure: 12 - 10 = 2 seconds
    # Decay: 2 * 15.0 = 30.0 -> 100 - 30 = 70.0
    assert t.current_peak() == 70.0

def test_req_6_t140_decay_floor():
    # Decay floor (REQ-6)
    # Expected: 40.0
    t = Telltale(10.0, 15.0)
    t.update(0.0, 100.0)
    t.update(9.0, 40.0)
    t.update(12.0, 0.0)
    t.update(15.0, 0.0)
    # At 15: 100 decays by 5*15=75 -> 25.0. But 40.0 is in window (age=6). Peak=40.0.
    assert t.current_peak() == 40.0

def test_req_6_t150_new_high_beats_track():
    # New high beats track (REQ-6)
    # Expected: 80.0
    t = Telltale(10.0, 15.0)
    t.update(0.0, 100.0)
    t.update(9.0, 40.0)
    t.update(12.0, 0.0)
    t.update(12.5, 80.0)
    # At 12.5: 100 decays by 2.5*15=37.5 -> 62.5. Peak=80.0.
    assert t.current_peak() == 80.0

def test_req_9_t160_departed_highs_keep_tracks():
    # Departed highs keep tracks (REQ-9)
    # Expected: 75.0
    t = Telltale(10.0, 15.0)
    t.update(0.0, 100.0)
    t.update(5.0, 90.0)
    t.update(16.0, 0.0)
    # At 16:
    # 100 left at 10. Elapsed 6. 6*15=90. Contribution 10.
    # 90 left at 15. Elapsed 1. 1*15=15. Contribution 75.
    assert t.current_peak() == 75.0

def test_req_4_t170_purity_under_decay():
    # Purity under decay (REQ-4)
    # Expected: 70.0 (consecutively)
    t = Telltale(10.0, 15.0)
    t.update(0.0, 100.0)
    t.update(9.0, 40.0)
    t.update(12.0, 0.0)
    v1 = t.current_peak()
    v2 = t.current_peak()
    v3 = t.current_peak()
    assert v1 == v2 == v3 == 70.0

def test_req_1_t180_all_time_window():
    # All-time window (REQ-1)
    # Expected: 100.0
    t = Telltale(None)
    t.update(0.0, 100.0)
    t.update(1_000_000.0, 5.0)
    assert t.current_peak() == 100.0

def test_req_7_t190_all_time_ignores_decay():
    # All-time ignores decay (REQ-7)
    # Expected: 100.0
    t = Telltale(None, 15.0)
    t.update(0.0, 100.0)
    t.update(1_000_000.0, 5.0)
    assert t.current_peak() == 100.0

def test_req_11_t200_invalid_window():
    # Invalid window (REQ-11)
    # Expected: ValueError
    with pytest.raises(ValueError):
        Telltale(0.0)

def test_req_12_t210_invalid_decay_rate():
    # Invalid decay_rate (REQ-12)
    # Expected: ValueError
    with pytest.raises(ValueError):
        Telltale(10.0, -3.0)

def test_req_10_t220_rejected_update_raises():
    # Rejected update raises (REQ-10)
    # Expected: ValueError
    t = Telltale(10.0)
    t.update(5.0, 1.0)
    with pytest.raises(ValueError):
        t.update(4.9, 1.0)

def test_req_13_t230_equal_update_accepted():
    # Equal update accepted (REQ-13)
    # Expected: 3.0 (no exception)
    t = Telltale(10.0)
    t.update(5.0, 1.0)
    t.update(5.0, 3.0)
    assert t.current_peak() == 3.0
```

## 11. Implementation Notes

### 11.1 Time Strategy
The `Telltale` uses purely relative virtual timestamps. It never imports `time` and has no concept of "now" outside the timestamps provided to its `update()` method. This guarantees deterministic behavior and prevents tests from becoming flaky.

### 11.2 Monotonic Enforcement
A strict monotonic check `timestamp >= self._max_timestamp` is enforced. A failure mode where the user inadvertently passes an older timestamp raises an immediate `ValueError` to prevent silently corrupting the sliding window arithmetic.

### 11.3 State Lifecycle
The `current_peak()` calculation processes age continuously during reads, relying strictly on `self._max_timestamp`. State mutations (trimming historical array length) are not included in this spec to keep the behavior strictly matching the logic flow from the LLD; if `_history` grows indefinitely over an unbounded session, a garbage collection logic can be added later without breaking the public contract.

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3)
- [x] Every data structure has a concrete JSON/YAML example (Section 4)
- [x] Every **non-test** function has input/output examples with realistic values (Section 5)
- [x] Every LLD pass criterion has a test function (Section 10.1)
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
| Date | 2026-08-15 |
| Iterations | 1 |
| Finalized | 2026-08-15T01:55:12-05:00 |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #41 |
| Verdict | APPROVED |
| Date | 2026-08-15 |
| Iterations | 0 |
| Finalized | 2026-08-15T06:58:30Z |

### Review Feedback Summary

The implementation spec is exceptionally well-written and concrete. It provides exact Python code that correctly implements the LLD's purely mathematical sliding window design. The test suite maintains strict 1-to-1 traceability with the requirements, accurately verifying complex behaviors like multiple decay tracks, hard hold drops, monotonic violations, and state purity without introducing any contradictions or untraceable assertions.
