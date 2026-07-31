# Implementation Spec: Telltale Peak-Hold Needle Logic (Pure, No GUI)

<!-- Metadata -->
| Field | Value |
|-------|-------|
| Issue | #41 |
| LLD | `docs/lld/active/41-telltale-peak-hold-needle-logic.md` |
| Generated | 2026-07-31 |
| Status | APPROVED |

## 1. Overview

This implementation adds the pure, headless `Telltale` peak-hold needle tracking class to `src/boostgauge/telltale.py`. It tracks maximum metric values over a sliding time window with optional rate-limited monotonic decay and a window-maximum floor.

**Objective:** Implement pure, headless `Telltale` peak-hold needle logic in `src/boostgauge/telltale.py` to track maximum values over a sliding window with optional rate-limited decay.

**Success Criteria:**
- `Telltale` class initialized with positive float `window` duration and optional non-negative `decay_rate`.
- `update(timestamp, value)` updates sliding window state and peak tracking in $O(1)$ amortized time while enforcing non-decreasing timestamps.
- `current_peak(timestamp=None)` calculates the decaying peak anchored at window departure time ($t_{\text{depart}} = t_{\text{sample}} + \text{window}$), floored by the active sliding window maximum.
- `reset()` completely clears all sample history and resets peak state to `None`.
- 100% test coverage achieved in `tests/unit/test_telltale.py`.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/telltale.py` | Add | Core `Telltale` sliding-window peak-hold state tracker with optional decay |
| 2 | `tests/unit/test_telltale.py` | Add | Unit test suite covering windowing, decay, flooring, validation, and reset behaviors |

**Implementation Order Rationale:** `src/boostgauge/telltale.py` defines the primary data structure (`Sample`) and core logic class (`Telltale`). Implementing `telltale.py` first allows `tests/unit/test_telltale.py` to import and validate the implementation directly.

## 3. Current State (for Modify/Delete files)

No existing files are modified or deleted in this issue. Both target files (`src/boostgauge/telltale.py` and `tests/unit/test_telltale.py`) are new additions to the repository.

## 4. Data Structures

### 4.1 `Sample` (Internal Sample Container)

**Definition:**

```python
class Sample:
    """Internal sample container representing a timestamped metric value."""
    __slots__ = ("timestamp", "value")

    def __init__(self, timestamp: float, value: float) -> None:
        self.timestamp = float(timestamp)
        self.value = float(value)
```

**Concrete Example:**

```json
{
    "timestamp": 1700000000.0,
    "value": 85.5
}
```

### 4.2 `TelltaleStateDict` (Internal State Representation)

**Definition:**

```python
from typing import Optional, TypedDict

class SampleDict(TypedDict):
    timestamp: float
    value: float

class TelltaleStateDict(TypedDict):
    window: float
    decay_rate: Optional[float]
    peak_val: Optional[float]
    peak_depart_time: Optional[float]
    last_timestamp: Optional[float]
    samples: list[SampleDict]
```

**Concrete Example:**

```json
{
    "window": 10.0,
    "decay_rate": 15.0,
    "peak_val": 100.0,
    "peak_depart_time": 10.0,
    "last_timestamp": 9.0,
    "samples": [
        {"timestamp": 0.0, "value": 100.0},
        {"timestamp": 9.0, "value": 40.0}
    ]
}
```

## 5. Function Specifications

### 5.1 `Telltale.__init__()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def __init__(self, window: float, decay_rate: Optional[float] = None) -> None:
    """Initialize Telltale with window duration (seconds) and optional decay_rate (units/sec)."""
    ...
```

**Input Example:**

```python
window = 10.0
decay_rate = 15.0
```

**Output Example:**

```python
# Returns None (initializes instance variables)
# self.window == 10.0
# self.decay_rate == 15.0
# self._samples == deque()
# self._peak_val is None
# self._peak_depart_time is None
# self._last_timestamp is None
```

**Edge Cases:**
- `window <= 0` (e.g. `0.0` or `-5.0`) -> raises `ValueError("window must be strictly positive (> 0)")`
- Non-numeric `window` (e.g. `"10"`) -> raises `TypeError("window must be a float or int")`
- `decay_rate < 0` (e.g. `-1.0`) -> raises `ValueError("decay_rate must be non-negative (>= 0)")`
- Non-numeric non-None `decay_rate` (e.g. `"15"`) -> raises `TypeError("decay_rate must be a float, int, or None")`

---

### 5.2 `Telltale.update()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def update(self, timestamp: float, value: float) -> None:
    """Feed a new (timestamp, value) sample and update internal sliding window state."""
    ...
```

**Input Example:**

```python
timestamp = 9.0
value = 40.0
```

**Output Example:**

```python
# Returns None (mutates internal deque and peak state)
```

**Edge Cases:**
- Non-numeric `timestamp` or `value` -> raises `TypeError("timestamp and value must be numeric")`
- `timestamp < self._last_timestamp` -> raises `ValueError("Monotonically non-decreasing timestamps required")`
- `timestamp == self._last_timestamp` -> valid (multiple samples at same time step allowed)

---

### 5.3 `Telltale.current_peak()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def current_peak(self, timestamp: Optional[float] = None) -> Optional[float]:
    """Return highest value in active window, applying decay if configured. Returns None if uninitialized."""
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
- Uninitialized state (no samples fed or post-reset) -> returns `None`
- `timestamp` is provided and `timestamp < self._last_timestamp` -> raises `ValueError("Query timestamp cannot precede last update timestamp")`
- `decay_rate` is `None` or `0.0` -> returns exact maximum value of samples remaining in active window (`window_max`)
- All samples expired from window without floor -> returns `None` if window becomes empty

---

### 5.4 `Telltale.reset()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def reset(self) -> None:
    """Clear all sample history and reset peak state to None."""
    ...
```

**Input Example:**

```python
# Called on active instance
tt.reset()
```

**Output Example:**

```python
# Returns None
# self.current_peak() returns None
```

**Edge Cases:**
- Idempotent: Calling `reset()` on a fresh or already reset instance raises no error and maintains clean state.

## 6. Change Instructions

### 6.1 `src/boostgauge/telltale.py` (Add)

**Complete file contents:**

```python
"""Telltale peak-hold needle logic module.

Issue #41: Telltale peak-hold needle logic (pure, no GUI).
Tracks maximum metric values over a sliding time window with optional rate-limited decay.
"""

from __future__ import annotations

from collections import deque
from typing import Deque, Optional


class Sample:
    """Internal sample container representing a timestamped metric value."""

    __slots__ = ("timestamp", "value")

    def __init__(self, timestamp: float, value: float) -> None:
        self.timestamp = float(timestamp)
        self.value = float(value)


class Telltale:
    """Tracks the maximum value reached over a sliding time window with optional decay."""

    def __init__(self, window: float, decay_rate: Optional[float] = None) -> None:
        """Initialize Telltale with window duration (seconds) and optional decay_rate (units/sec)."""
        if isinstance(window, bool) or not isinstance(window, (int, float)):
            raise TypeError("window must be a float or int")
        if window <= 0:
            raise ValueError("window must be strictly positive (> 0)")

        if decay_rate is not None:
            if isinstance(decay_rate, bool) or not isinstance(decay_rate, (int, float)):
                raise TypeError("decay_rate must be a float, int, or None")
            if decay_rate < 0:
                raise ValueError("decay_rate must be non-negative (>= 0)")

        self.window: float = float(window)
        self.decay_rate: Optional[float] = (
            float(decay_rate) if decay_rate is not None else None
        )

        self._samples: Deque[Sample] = deque()
        self._peak_val: Optional[float] = None
        self._peak_depart_time: Optional[float] = None
        self._last_timestamp: Optional[float] = None

    def update(self, timestamp: float, value: float) -> None:
        """Feed a new (timestamp, value) sample and update internal sliding window state."""
        if (
            isinstance(timestamp, bool)
            or not isinstance(timestamp, (int, float))
            or isinstance(value, bool)
            or not isinstance(value, (int, float))
        ):
            raise TypeError("timestamp and value must be numeric")

        t = float(timestamp)
        v = float(value)

        if self._last_timestamp is not None and t < self._last_timestamp:
            raise ValueError(
                f"Timestamp {t} is older than last timestamp {self._last_timestamp}"
            )

        # Evict expired samples prior to computing effective peak
        cutoff = t - self.window
        while self._samples and self._samples[0].timestamp < cutoff:
            self._samples.popleft()

        # Compute current effective peak at time `t` BEFORE updating peak anchor
        effective_peak: Optional[float] = None
        if self._samples:
            window_max = max(s.value for s in self._samples)
            if self.decay_rate is None or self.decay_rate == 0:
                effective_peak = window_max
            else:
                assert self._peak_val is not None
                assert self._peak_depart_time is not None
                if t <= self._peak_depart_time:
                    decayed_peak = self._peak_val
                else:
                    elapsed = t - self._peak_depart_time
                    decayed_peak = self._peak_val - (self.decay_rate * elapsed)
                effective_peak = max(decayed_peak, window_max)

        if effective_peak is None or v >= effective_peak:
            self._peak_val = v
            self._peak_depart_time = t + self.window

        self._samples.append(Sample(t, v))
        self._last_timestamp = t

    def current_peak(self, timestamp: Optional[float] = None) -> Optional[float]:
        """Return highest value in active window, applying decay if configured.

        Returns None if uninitialized or window is empty.
        """
        if not self._samples:
            return None

        if timestamp is not None:
            if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)):
                raise TypeError("timestamp must be a float or int")
            t_query = float(timestamp)
            if self._last_timestamp is not None and t_query < self._last_timestamp:
                raise ValueError(
                    f"Query timestamp {t_query} cannot precede last update timestamp {self._last_timestamp}"
                )
        else:
            assert self._last_timestamp is not None
            t_query = self._last_timestamp

        # Evict expired samples relative to query timestamp
        cutoff = t_query - self.window
        while self._samples and self._samples[0].timestamp < cutoff:
            self._samples.popleft()

        if not self._samples:
            return None

        window_max = max(s.value for s in self._samples)

        if self.decay_rate is None or self.decay_rate == 0:
            return window_max

        assert self._peak_val is not None
        assert self._peak_depart_time is not None

        if t_query <= self._peak_depart_time:
            decayed_peak = self._peak_val
        else:
            elapsed = t_query - self._peak_depart_time
            decayed_peak = self._peak_val - (self.decay_rate * elapsed)

        return max(decayed_peak, window_max)

    def reset(self) -> None:
        """Clear all sample history and reset peak state to None."""
        self._samples.clear()
        self._peak_val = None
        self._peak_depart_time = None
        self._last_timestamp = None
```

---

### 6.2 `tests/unit/test_telltale.py` (Add)

**Complete file contents:**

```python
"""Unit test suite for Telltale peak-hold logic module.

Issue #41: Telltale peak-hold needle logic (pure, no GUI).
"""

import pytest
from boostgauge.telltale import Telltale


def test_t010_instantiation_validation() -> None:
    """T010: Validates instantiation with valid window and decay_rate parameters."""
    tt = Telltale(window=10.0, decay_rate=15.0)
    assert tt.window == 10.0
    assert tt.decay_rate == 15.0
    assert tt.current_peak() is None

    tt_no_decay = Telltale(window=5.0)
    assert tt_no_decay.window == 5.0
    assert tt_no_decay.decay_rate is None


def test_t015_parameter_error_handling() -> None:
    """T015: Raises ValueError/TypeError on invalid initialization arguments."""
    with pytest.raises(ValueError, match="strictly positive"):
        Telltale(window=0.0)

    with pytest.raises(ValueError, match="strictly positive"):
        Telltale(window=-1.0)

    with pytest.raises(TypeError, match="float or int"):
        Telltale(window="invalid")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="float or int"):
        Telltale(window=True)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="non-negative"):
        Telltale(window=10.0, decay_rate=-5.0)

    with pytest.raises(TypeError, match="float, int, or None"):
        Telltale(window=10.0, decay_rate="invalid")  # type: ignore[arg-type]


def test_t020_single_value_update() -> None:
    """T020: Feed single sample and verify current_peak returns sample value."""
    tt = Telltale(window=10.0)
    tt.update(0.0, 50.0)
    assert tt.current_peak() == 50.0


def test_t025_monotonic_timestamp_validation() -> None:
    """T025: Raises ValueError on non-monotonic (decreasing) timestamps."""
    tt = Telltale(window=10.0)
    tt.update(10.0, 50.0)
    with pytest.raises(ValueError, match="older than last timestamp"):
        tt.update(5.0, 60.0)


def test_t030_pre_first_update_state() -> None:
    """T030: Fresh instance current_peak() returns None."""
    tt = Telltale(window=10.0)
    assert tt.current_peak() is None
    assert tt.current_peak(timestamp=5.0) is None


def test_t035_post_reset_state() -> None:
    """T035: current_peak() returns None after reset()."""
    tt = Telltale(window=10.0)
    tt.update(0.0, 50.0)
    assert tt.current_peak() == 50.0
    tt.reset()
    assert tt.current_peak() is None


def test_t040_rising_series_tracking() -> None:
    """T040: Peak immediately tracks maximum value in a rising series."""
    tt = Telltale(window=10.0)
    tt.update(0.0, 10.0)
    assert tt.current_peak() == 10.0
    tt.update(1.0, 20.0)
    assert tt.current_peak() == 20.0
    tt.update(2.0, 30.0)
    assert tt.current_peak() == 30.0


def test_t045_new_high_reset() -> None:
    """T045: Peak resets immediately to new high when value exceeds active peak."""
    tt = Telltale(window=10.0, decay_rate=15.0)
    tt.update(0.0, 100.0)
    tt.update(5.0, 40.0)
    assert tt.current_peak() == 100.0
    tt.update(6.0, 120.0)
    assert tt.current_peak() == 120.0


def test_t050_static_peak_window_expiration_no_decay() -> None:
    """T050: Without decay, peak drops to None when single high ages out of window."""
    tt = Telltale(window=10.0, decay_rate=None)
    tt.update(0.0, 100.0)
    assert tt.current_peak(0.0) == 100.0
    assert tt.current_peak(9.9) == 100.0
    assert tt.current_peak(10.1) is None


def test_t055_multi_sample_window_drop_no_decay() -> None:
    """T055: Without decay, peak drops instantly to new window max when high ages out."""
    tt = Telltale(window=10.0, decay_rate=None)
    tt.update(0.0, 100.0)
    tt.update(5.0, 40.0)
    assert tt.current_peak(9.0) == 100.0
    assert tt.current_peak(11.0) == 40.0


def test_t060_discriminating_decay_case() -> None:
    """T060: Peak decays at decay_rate starting from high departure time (t=10.0)."""
    tt = Telltale(window=10.0, decay_rate=15.0)
    tt.update(0.0, 100.0)
    tt.update(9.0, 40.0)

    assert tt.current_peak(0.0) == 100.0
    assert tt.current_peak(9.0) == 100.0
    assert tt.current_peak(10.0) == 100.0
    # At t=12.0: departure was t=10.0. Elapsed = 2.0s. Decayed peak = 100 - (15 * 2) = 70.0.
    assert tt.current_peak(12.0) == 70.0


def test_t065_decay_floor_case() -> None:
    """T065: Decaying peak is floored at active window maximum value."""
    tt = Telltale(window=10.0, decay_rate=15.0)
    tt.update(0.0, 100.0)
    tt.update(9.0, 40.0)

    # At t=15.0: departure was t=10.0. Decayed = 100 - (15 * 5) = 25.0. Floor = 40.0.
    assert tt.current_peak(15.0) == 40.0


def test_t070_unfloored_decay_continuous_drop() -> None:
    """T070: Peak decays smoothly down when no remaining sample floors it."""
    tt = Telltale(window=10.0, decay_rate=10.0)
    tt.update(0.0, 100.0)
    tt.update(9.0, 0.0)
    assert tt.current_peak(11.0) == 90.0
    assert tt.current_peak(15.0) == 50.0


def test_t080_reset_clears_all_history() -> None:
    """T080: Subsequent update after reset starts with clean state."""
    tt = Telltale(window=10.0, decay_rate=15.0)
    tt.update(0.0, 100.0)
    tt.reset()
    assert tt.current_peak() is None
    tt.update(1.0, 20.0)
    assert tt.current_peak() == 20.0


def test_t085_multiple_reset_calls() -> None:
    """T085: Multiple reset() calls are safe and idempotent."""
    tt = Telltale(window=10.0)
    tt.reset()
    tt.reset()
    assert tt.current_peak() is None
```

## 7. Pattern References

### 7.1 Pytest Configuration & Test Import Mode

**File:** `pyproject.toml` (lines 35-43)

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-ra --strict-markers --import-mode=importlib"
```

**Relevance:** Demonstrates project test discovery rules. `tests/unit/test_telltale.py` adheres to `test_*.py` naming convention and standard `pytest` assertions.

---

### 7.2 Dataclass / Memory Slot Optimization Pattern

**File:** `src/boostgauge/telltale.py` (lines 13-20)

```python
class Sample:
    """Internal sample container representing a timestamped metric value."""
    __slots__ = ("timestamp", "value")

    def __init__(self, timestamp: float, value: float) -> None:
        self.timestamp = float(timestamp)
        self.value = float(value)
```

**Relevance:** Standard Python `__slots__` pattern minimizing memory footprint for high-frequency sliding window entries.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `from __future__ import annotations` | stdlib | `src/boostgauge/telltale.py` |
| `from collections import deque` | stdlib | `src/boostgauge/telltale.py` |
| `from typing import Deque, Optional` | stdlib | `src/boostgauge/telltale.py` |
| `import pytest` | dev dependency | `tests/unit/test_telltale.py` |
| `from boostgauge.telltale import Telltale` | internal | `tests/unit/test_telltale.py` |

**New Dependencies:** None (uses standard library modules `collections` and `typing`).

## 9. Placeholder

*Reserved for future alignment with LLD section structure.*

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `Telltale.__init__()` | `window=10.0, decay_rate=15.0` | Valid instance; `window=10.0`, `decay_rate=15.0` |
| T015 | `Telltale.__init__()` | `window=0.0` or `decay_rate=-1.0` | Raises `ValueError` / `TypeError` |
| T020 | `Telltale.update()` | `update(0.0, 50.0)` | `current_peak() == 50.0` |
| T025 | `Telltale.update()` | `update(10.0, 50.0)` then `update(5.0, 60.0)` | Raises `ValueError` |
| T030 | `Telltale.current_peak()` | Query fresh uninitialized instance | `None` |
| T035 | `Telltale.current_peak()` | `update(0.0, 50.0)` then `reset()` | `None` |
| T040 | `Telltale.update()` | `(0.0, 10.0), (1.0, 20.0), (2.0, 30.0)` | `current_peak() == 30.0` |
| T045 | `Telltale.update()` | `(0.0, 100.0), (5.0, 40.0), (6.0, 120.0)` | `current_peak() == 120.0` |
| T050 | `Telltale.current_peak()` | `window=10, decay=None, (0.0, 100.0)`, query `t=10.1` | `None` |
| T055 | `Telltale.current_peak()` | `window=10, decay=None, (0.0, 100.0), (5.0, 40.0)`, query `t=11.0` | `40.0` |
| T060 | `Telltale.current_peak()` | `window=10, decay=15, (0.0, 100.0), (9.0, 40.0)`, query `t=12.0` | `70.0` |
| T065 | `Telltale.current_peak()` | Same series as T060, query `t=15.0` | `40.0` |
| T070 | `Telltale.current_peak()` | `window=10, decay=10, (0.0, 100.0), (9.0, 0.0)`, query `t=11.0` | `90.0` |
| T080 | `Telltale.reset()` | `(0.0, 100.0), reset(), (1.0, 20.0)` | `current_peak() == 20.0` |
| T085 | `Telltale.reset()` | `reset()` on fresh/reset instance | Idempotent, returns `None` |

## 11. Implementation Notes

### 11.1 Error Handling Convention

All input parameter validation errors use standard Python exceptions (`ValueError` for invalid value ranges such as `window <= 0`, `decay_rate < 0`, or out-of-order timestamps; `TypeError` for non-numeric types). Boolean types are explicitly checked and rejected to prevent Python's implicit `bool` -> `int` coercion (e.g. `isinstance(True, int)` is `True`).

### 11.2 Performance & Amortized $O(1)$ Guarantees

Using `collections.deque` allows $O(1)$ push and popleft operations for sliding window sample eviction. Computing `window_max` uses standard Python `max()` over active window samples ($N \le 60$ entries for 1Hz–60Hz updates over standard window sizes).

### 11.3 Mathematical Decay Formulation

Decay rate anchor calculation:
$$t_{\text{depart}} = t_{\text{high\_sample}} + \text{window}$$
$$\text{decayed\_peak}(t) = V_{\text{high}} - \text{decay\_rate} \times \max(0, t - t_{\text{depart}})$$
$$\text{effective\_peak}(t) = \max(\text{decayed\_peak}(t), \text{window\_max}(t))$$

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3 - N/A noted for new files)
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
| Finalized | 2026-07-31T13:25:00Z |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #41 |
| Verdict | APPROVED |
| Date | 2026-07-31 |
| Iterations | 2 |
| Finalized | 2026-07-31T18:24:58Z |

### Review Feedback Summary

The revised implementation spec fully addresses the previous review feedback by adding the floor sample `(9.0, 0.0)` to test scenario T070. All test assertions now strictly trace to the specified class behavior and sliding window mechanics. The spec is complete, highly concrete, technically feasible, and ready for autonomous implementation with a >80% first-try success rate.
