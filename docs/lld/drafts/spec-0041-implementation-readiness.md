# Implementation Spec: Feature: Telltale peak-hold needle logic (pure, no GUI)

<!-- Metadata -->
| Field | Value |
|-------|-------|
| Issue | #41 |
| LLD | `docs/lld/active/41-telltale-peak-hold-needle-logic.md` |
| Generated | 2026-08-01 |
| Status | APPROVED |

## 1. Overview

This implementation adds the `Telltale` class to track peak-hold values for tachometer gauge needles using a sliding time window with optional linear decay. The module is strictly pure Python and GUI-independent, ensuring sub-millisecond execution without system clock or `tkinter` dependencies.

**Objective:** Implement a pure, GUI-independent peak-hold telltale needle component tracking maximum values over a sliding time window with optional linear decay.

**Success Criteria:**
- `Telltale` class exposed in `src/boostgauge/telltale.py` accepting `window` (> 0) and optional `decay_rate` (>= 0).
- Monotonic timestamp validation raising `ValueError` on regressive timestamps in `update()` and `current_peak()`.
- Amortized $O(1)$ sample updates using `collections.deque` with automatic expiration pruning.
- Instant drop to window max when a high value ages out (when decay is disabled) or linear decay at `decay_rate` units/sec bounded by the active window max floor (when decay is enabled).
- 100% unit test coverage in `tests/unit/test_telltale.py`.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/telltale.py` | Add | Implements `Telltale` class for sliding-window peak-hold tracking with optional decay. |
| 2 | `tests/unit/test_telltale.py` | Add | Headless unit tests covering window eviction, decay, floor bounds, reset, and timestamp validation. |

**Implementation Order Rationale:** `src/boostgauge/telltale.py` contains the core business logic and state machine. `tests/unit/test_telltale.py` imports and tests `Telltale` directly, so the module must be added first.

## 3. Current State (for Modify/Delete files)

N/A - All files modified in this issue are new additions (`Add`). No existing files are modified or deleted.

For project test environment context, the existing test bootstrap file is shown below:

### 3.1 `tests/conftest.py`

**Relevant excerpt** (lines 1-8):

```python
"""Project test bootstrap."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
```

**What changes:** No changes to `tests/conftest.py`. New unit tests in `tests/unit/test_telltale.py` leverage this bootstrap to import `boostgauge.telltale`.

## 4. Data Structures

### 4.1 Sample

**Definition:**

```python
from typing import Tuple

# Tuple representing (timestamp_seconds, value)
Sample = Tuple[float, float]
```

**Concrete Example:**

```json
[
  [1770000000.0, 42.5],
  [1770000001.0, 85.0],
  [1770000002.5, 60.0]
]
```

### 4.2 TelltaleState

**Definition:**

```python
from typing import Optional, Tuple, TypedDict

class TelltaleState(TypedDict):
    window: float
    decay_rate: Optional[float]
    last_timestamp: Optional[float]
    samples: list[Tuple[float, float]]
```

**Concrete Example:**

```json
{
  "window": 10.0,
  "decay_rate": 15.0,
  "last_timestamp": 1770000002.5,
  "samples": [
    [1770000000.0, 42.5],
    [1770000001.0, 85.0],
    [1770000002.5, 60.0]
  ]
}
```

## 5. Function Specifications

### 5.1 `Telltale.__init__()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def __init__(self, window: float, decay_rate: Optional[float] = None) -> None:
    """Initialize Telltale needle state.

    Args:
        window: Sliding window duration in seconds (> 0).
        decay_rate: Optional linear decay rate in value units/second (>= 0).

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
# Telltale instance initialized with _window=10.0, _decay_rate=15.0, _samples=deque(), _last_timestamp=None
```

**Edge Cases:**
- `window <= 0` (e.g. `window = 0.0` or `window = -5.0`) -> raises `ValueError("Window duration must be positive")`
- `decay_rate < 0` (e.g. `decay_rate = -1.0`) -> raises `ValueError("Decay rate must be non-negative")`

### 5.2 `Telltale.update()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def update(self, timestamp: float, value: float) -> None:
    """Record a new sample timestamp and value.

    Args:
        timestamp: Sample timestamp in seconds.
        value: Numerical reading value.

    Raises:
        ValueError: If timestamp is earlier than the previous sample's timestamp.
    """
    ...
```

**Input Example:**

```python
timestamp = 10.0
value = 85.0
```

**Output Example:**

```python
None  # Updates internal deque state and _last_timestamp
```

**Edge Cases:**
- `timestamp` earlier than `_last_timestamp` (e.g. `_last_timestamp = 10.0`, `timestamp = 9.0`) -> raises `ValueError("Timestamp cannot be earlier than previous sample timestamp")`

### 5.3 `Telltale.current_peak()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def current_peak(self, current_time: Optional[float] = None) -> Optional[float]:
    """Compute the active peak value at current_time or the latest sample timestamp.

    Args:
        current_time: Optional explicit evaluation timestamp.

    Returns:
        The peak value bounded by window maximum, or None if no samples exist.

    Raises:
        ValueError: If current_time is earlier than the latest sample timestamp.
    """
    ...
```

**Input Example:**

```python
current_time = 12.0
# Given sample history: [(0.0, 100.0), (9.0, 40.0)] with window=10.0, decay_rate=15.0
```

**Output Example:**

```python
70.0  # 100.0 - 15.0 * (12.0 - 10.0) = 70.0, bounded above window max 40.0
```

**Edge Cases:**
- No samples recorded yet -> returns `None`
- `current_time` earlier than `_last_timestamp` (e.g. `_last_timestamp = 10.0`, `current_time = 8.0`) -> raises `ValueError("current_time cannot be earlier than latest sample timestamp")`

### 5.4 `Telltale.reset()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def reset(self) -> None:
    """Clear all sample history and decay state."""
    ...
```

**Input Example:**

```python
# Telltale instance with active samples
```

**Output Example:**

```python
None  # _samples cleared, _last_timestamp set to None
```

**Edge Cases:**
- Calling `reset()` on an empty `Telltale` instance -> safe no-op, state remains clear.

## 6. Change Instructions

### 6.1 `src/boostgauge/telltale.py` (Add)

**Complete file contents:**

```python
"""Peak-hold telltale needle tracking sliding-window maximums with linear decay.

Issue #41: Feature: Telltale peak-hold needle logic (pure, no GUI)
"""

from collections import deque
from typing import Deque, Optional, Tuple


Sample = Tuple[float, float]


class Telltale:
    """Tracks peak values over a sliding time window with optional linear decay."""

    def __init__(self, window: float, decay_rate: Optional[float] = None) -> None:
        """Initialize Telltale needle state.

        Args:
            window: Sliding window duration in seconds (> 0).
            decay_rate: Optional linear decay rate in value units/second (>= 0).

        Raises:
            ValueError: If window <= 0 or decay_rate < 0.
        """
        if window <= 0:
            raise ValueError("Window duration must be positive")
        if decay_rate is not None and decay_rate < 0:
            raise ValueError("Decay rate must be non-negative")

        self._window: float = float(window)
        self._decay_rate: Optional[float] = (
            float(decay_rate) if decay_rate is not None else None
        )
        self._samples: Deque[Sample] = deque()
        self._last_timestamp: Optional[float] = None

    def update(self, timestamp: float, value: float) -> None:
        """Record a new sample timestamp and value.

        Args:
            timestamp: Sample timestamp in seconds.
            value: Numerical reading value.

        Raises:
            ValueError: If timestamp is earlier than the previous sample's timestamp.
        """
        t = float(timestamp)
        v = float(value)

        if self._last_timestamp is not None and t < self._last_timestamp:
            raise ValueError(
                "Timestamp cannot be earlier than previous sample timestamp"
            )

        self._last_timestamp = t
        self._samples.append((t, v))
        self._prune_samples(t)

    def current_peak(self, current_time: Optional[float] = None) -> Optional[float]:
        """Compute the active peak value at current_time or the latest sample timestamp.

        Args:
            current_time: Optional explicit evaluation timestamp.

        Returns:
            The peak value bounded by window maximum, or None if no samples exist.

        Raises:
            ValueError: If current_time is earlier than the latest sample timestamp.
        """
        if not self._samples or self._last_timestamp is None:
            return None

        eval_time = (
            self._last_timestamp
            if current_time is None
            else float(current_time)
        )

        if current_time is not None and eval_time < self._last_timestamp:
            raise ValueError(
                "current_time cannot be earlier than latest sample timestamp"
            )

        active_vals = [
            v for (t, v) in self._samples if eval_time - t <= self._window
        ]

        if not active_vals and not self._samples:
            return None

        window_max = max(active_vals) if active_vals else None

        if self._decay_rate is None or self._decay_rate == 0:
            return window_max

        effective_peak = window_max
        for t, v in self._samples:
            if eval_time <= t + self._window:
                eff = v
            else:
                decay_elapsed = eval_time - (t + self._window)
                eff = v - (self._decay_rate * decay_elapsed)
                if eff <= 0:
                    continue
            if effective_peak is None or eff > effective_peak:
                effective_peak = eff

        if window_max is not None and effective_peak < window_max:
            return window_max

        return effective_peak

    def reset(self) -> None:
        """Clear all sample history and decay state."""
        self._samples.clear()
        self._last_timestamp = None

    def _prune_samples(self, current_time: float) -> None:
        """Evict expired samples that can no longer influence active peak or decay."""
        while self._samples:
            t, v = self._samples[0]
            if self._decay_rate is None or self._decay_rate == 0:
                if current_time - t > self._window:
                    self._samples.popleft()
                else:
                    break
            else:
                max_retention = self._window + max(0.0, v / self._decay_rate)
                if current_time - t > max_retention:
                    self._samples.popleft()
                else:
                    break
```

### 6.2 `tests/unit/test_telltale.py` (Add)

**Complete file contents:**

```python
"""Headless unit tests for Telltale peak-hold needle logic.

Issue #41: Feature: Telltale peak-hold needle logic (pure, no GUI)
"""

import pytest

from boostgauge.telltale import Telltale


def test_t010_instantiation_and_config_validation():
    """T010: Accepts valid window/decay; raises ValueError on non-positive window or negative decay."""
    tt = Telltale(window=10.0, decay_rate=15.0)
    assert tt._window == 10.0
    assert tt._decay_rate == 15.0

    with pytest.raises(ValueError, match="Window duration must be positive"):
        Telltale(window=0.0)

    with pytest.raises(ValueError, match="Window duration must be positive"):
        Telltale(window=-5.0)

    with pytest.raises(ValueError, match="Decay rate must be non-negative"):
        Telltale(window=10.0, decay_rate=-1.0)


def test_t020_pre_first_update_return():
    """T020: current_peak() returns None before any sample update."""
    tt = Telltale(window=10.0, decay_rate=5.0)
    assert tt.current_peak() is None
    assert tt.current_peak(current_time=5.0) is None


def test_t030_single_sample_peak():
    """T030: current_peak() returns single value when one sample is recorded."""
    tt = Telltale(window=10.0)
    tt.update(timestamp=1.0, value=42.0)
    assert tt.current_peak() == 42.0
    assert tt.current_peak(current_time=5.0) == 42.0


def test_t040_monotonic_timestamp_validation():
    """T040: update() and current_peak() raise ValueError on timestamp regression."""
    tt = Telltale(window=10.0)
    tt.update(timestamp=10.0, value=50.0)

    with pytest.raises(ValueError, match="Timestamp cannot be earlier than previous sample timestamp"):
        tt.update(timestamp=9.0, value=60.0)

    with pytest.raises(ValueError, match="current_time cannot be earlier than latest sample timestamp"):
        tt.current_peak(current_time=8.0)


def test_t050_rising_sample_series():
    """T050: Peak resets upward immediately on new high."""
    tt = Telltale(window=10.0)
    tt.update(timestamp=0.0, value=50.0)
    assert tt.current_peak() == 50.0

    tt.update(timestamp=1.0, value=80.0)
    assert tt.current_peak() == 80.0

    tt.update(timestamp=2.0, value=60.0)
    assert tt.current_peak() == 80.0


def test_t060_hard_hold_window_drop():
    """T060: Peak drops instantly to window max when former high ages out (no decay)."""
    tt = Telltale(window=10.0, decay_rate=None)
    tt.update(timestamp=0.0, value=100.0)
    tt.update(timestamp=5.0, value=30.0)

    assert tt.current_peak(current_time=9.0) == 100.0
    assert tt.current_peak(current_time=11.0) == 30.0


def test_t070_linear_decay_tracking():
    """T070: Peak decays linearly at decay_rate from departed high."""
    tt = Telltale(window=10.0, decay_rate=15.0)
    tt.update(timestamp=0.0, value=100.0)
    tt.update(timestamp=9.0, value=40.0)

    # At t=12.0, sample 1 (t=0.0, v=100) departed window at t=10.0. Elapsed decay = 2.0s.
    # Decayed value = 100.0 - (15.0 * 2.0) = 70.0. Window max = 40.0.
    assert tt.current_peak(current_time=12.0) == 70.0


def test_t080_decay_floor_bound():
    """T080: Peak decay stops at active window maximum floor."""
    tt = Telltale(window=10.0, decay_rate=15.0)
    tt.update(timestamp=0.0, value=100.0)
    tt.update(timestamp=9.0, value=40.0)

    # At t=15.0, decay would be 100 - 15*5 = 25.0, but window max is 40.0.
    assert tt.current_peak(current_time=15.0) == 40.0


def test_t090_reset_behavior():
    """T090: reset() clears all state; subsequent current_peak() returns None."""
    tt = Telltale(window=10.0, decay_rate=5.0)
    tt.update(timestamp=0.0, value=100.0)
    assert tt.current_peak() == 100.0

    tt.reset()
    assert tt.current_peak() is None

    tt.update(timestamp=1.0, value=50.0)
    assert tt.current_peak() == 50.0


def test_t100_negative_sample_pruning_retention():
    """T100: Negative sample values are retained for full window duration."""
    tt = Telltale(window=10.0, decay_rate=15.0)
    tt.update(timestamp=0.0, value=-20.0)
    assert tt.current_peak(current_time=5.0) == -20.0


def test_t110_expired_decay_query_without_update():
    """T110: Querying current_peak long after sample decay returns None rather than negative infinity."""
    tt = Telltale(window=10.0, decay_rate=15.0)
    tt.update(timestamp=0.0, value=100.0)
    assert tt.current_peak(current_time=100.0) is None
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

**Relevance:** Demonstrates path initialization convention ensuring `src` is in `sys.path` for headless unit tests.

### 7.2 Pytest Import Mode Configuration

**File:** `pyproject.toml` (lines 35-44)

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
# importlib mode: the tiered test tree (unit/visual/integration) may reuse
# basenames like test_gauge.py; default prepend mode dies at collection on
# the first duplicate (#129 — killed pipeline phase 3 three times).
addopts = "-ra --strict-markers --import-mode=importlib"
```

**Relevance:** Shows pytest setup and importlib mode required for platform-independent test discovery.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `from collections import deque` | stdlib | `src/boostgauge/telltale.py` |
| `from typing import Deque, Optional, Tuple` | stdlib | `src/boostgauge/telltale.py` |
| `import pytest` | dev-dependency | `tests/unit/test_telltale.py` |

**New Dependencies:** None (uses standard library and existing dev test dependencies).

## 9. Placeholder

*Reserved for future use to maintain alignment with LLD section numbering.*

## 10. Test Mapping

| Test ID | Scenario Description | Input | Expected Output |
|---------|----------------------|-------|-----------------|
| T010 | Instantiation & config validation (REQ-1) | `Telltale(10.0, 15.0)` / `Telltale(-1.0)` | Valid instance created / Raises `ValueError` |
| T020 | Pre-first-update query (REQ-3) | `Telltale(10.0)` without `update()` | `current_peak()` returns `None` |
| T030 | Single sample peak query (REQ-3) | `update(1.0, 42.0)` | `current_peak()` returns `42.0` |
| T040 | Monotonic timestamp validation (REQ-2, REQ-4) | `update(10.0, 50.0)` then `update(9.0, 60.0)` or `current_peak(8.0)` | Raises `ValueError` |
| T050 | Rising sample series (REQ-5) | `update(0.0, 50.0)`, `update(1.0, 80.0)` | `current_peak()` returns `80.0` |
| T060 | Window drop without decay (REQ-6) | `window=10, decay=None`, `update(0.0, 100.0)`, `update(5.0, 30.0)` at `t=11.0` | `current_peak()` returns `30.0` |
| T070 | Linear decay tracking (REQ-7) | `window=10, decay=15`, `update(0.0, 100.0)`, `update(9.0, 40.0)` at `t=12.0` | `current_peak()` returns `70.0` |
| T080 | Decay floor bounded by window max (REQ-8) | `window=10, decay=15`, `update(0.0, 100.0)`, `update(9.0, 40.0)` at `t=15.0` | `current_peak()` returns `40.0` |
| T090 | Reset behavior (REQ-9) | `update(0.0, 100.0)`, `reset()`, `current_peak()` | `current_peak()` returns `None` |
| T100 | Negative sample retention | `window=10, decay=15`, `update(0.0, -20.0)` at `t=5.0` | `current_peak()` returns `-20.0` |
| T110 | Expired decay query without update | `window=10, decay=15`, `update(0.0, 100.0)` at `t=100.0` | `current_peak()` returns `None` |

## 11. Implementation Notes

### 11.1 Error Handling & Monotonicity Rules

- Both `update(timestamp, value)` and `current_peak(current_time)` validate chronological monotonicity against `self._last_timestamp`.
- If an incoming `timestamp` or explicit `current_time` is less than `self._last_timestamp`, `ValueError` is raised immediately.

### 11.2 Amortized O(1) Pruning Mechanics

- Samples are stored in `collections.deque`.
- `_prune_samples(current_time)` pops expired samples from the left of the deque.
- Without decay, samples older than `window` are popped.
- With linear decay, samples are retained until their decayed contribution falls below 0 (i.e. `retention = window + max(0.0, value / decay_rate)`).

### 11.3 Constants & Bounds

| Parameter | Type / Bound | Description |
|-----------|--------------|-------------|
| `window` | `float > 0` | Duration of active sliding window in seconds |
| `decay_rate` | `Optional[float] >= 0` | Linear decay rate in value units per second |

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3 - N/A noted for Add files)
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
| Finalized | 2026-08-01T05:12:00Z |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #41 |
| Verdict | APPROVED |
| Date | 2026-08-01 |
| Iterations | 1 |
| Finalized | 2026-08-01T10:13:45Z |

### Review Feedback Summary

The revised spec is complete, concrete, and fully executable. It provides exact, non-ambiguous code implementations for `src/boostgauge/telltale.py` and `tests/unit/test_telltale.py`. All 11 unit test cases (T010–T110) cleanly trace to requirements REQ-1 through REQ-9 and Section 11 pruning rules without contradiction. The recent diff correctly handles negative sample retention via `max(0.0, v / decay_rate)` in sample pruning and returns `None` for expired decay queries long after window expiry.
