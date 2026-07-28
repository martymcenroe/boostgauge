# Implementation Spec: Telltale peak-hold needle logic (pure, no GUI)

| Field | Value |
|-------|-------|
| Issue | #41 |
| LLD | `docs/lld/active/41-telltale-peak-hold-needle-logic.md` |
| Generated | 2026-07-28 |
| Status | APPROVED |

## 1. Overview

This implementation provides pure, GUI-independent peak-hold telltale needle logic for tracking maximum telemetry values over a sliding time window with optional linear decay. It enforces strict $O(1)$ amortized sliding window peak queries and updates using a score-transformed monotonic double-ended queue (`collections.deque`).

**Objective:** Implement pure, GUI-independent peak-hold telltale needle logic in `src/boostgauge/telltale.py` that tracks maximum values over a sliding time window with optional linear decay.

**Success Criteria:**
- 100% statement and branch coverage in `tests/unit/test_telltale.py`.
- $O(1)$ amortized insertion (`update`) and query (`current_peak`) performance.
- Full validation of constructor parameters (`window > 0`, `decay_rate >= 0`) and monotonic sample timestamps ($t \ge t_{last}$).
- Decayed peaks dynamically adjust based on time elapsed without dropping below non-expired window samples or `latest_value`.
- `reset()` cleanly clears all historical sample state.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/telltale.py` | Add | Implements the `SampleNode` tuple and `Telltale` class managing sliding window maximum tracking and linear peak decay. |
| 2 | `tests/unit/test_telltale.py` | Add | Unit test suite verifying constructor validation, sliding window expiration, linear decay kinetics, timestamp ordering, and state reset. |

**Implementation Order Rationale:** `src/boostgauge/telltale.py` defines the core data structures and algorithm logic. `tests/unit/test_telltale.py` imports `Telltale` directly, requiring the core module to exist prior to test suite execution.

## 3. Current State (for Modify/Delete files)

N/A - No files with Change Type "Modify" or "Delete" exist for this issue. All target files (`src/boostgauge/telltale.py` and `tests/unit/test_telltale.py`) are new additions ("Add").

## 4. Data Structures

### 4.1 `SampleNode`

**Definition:**

```python
from typing import NamedTuple

class SampleNode(NamedTuple):
    timestamp: float  # Time sample was recorded in seconds
    value: float      # Metric value recorded at timestamp
    score: float      # Monotonic comparison score: value + decay_rate * timestamp
```

**Concrete Example:**

```json
{
    "timestamp": 10.0,
    "value": 50.0,
    "score": 70.0
}
```

### 4.2 `TelltaleStateDict`

**Definition:**

```python
from typing import Optional, TypedDict

class SampleNodeDict(TypedDict):
    timestamp: float
    value: float
    score: float

class TelltaleStateDict(TypedDict):
    window: float
    decay_rate: float
    samples: list[SampleNodeDict]
    latest_timestamp: Optional[float]
    latest_value: Optional[float]
```

**Concrete Example:**

```json
{
    "window": 60.0,
    "decay_rate": 2.0,
    "samples": [
        {
            "timestamp": 10.0,
            "value": 50.0,
            "score": 70.0
        },
        {
            "timestamp": 12.0,
            "value": 30.0,
            "score": 54.0
        }
    ],
    "latest_timestamp": 12.0,
    "latest_value": 30.0
}
```

## 5. Function Specifications

### 5.1 `Telltale.__init__()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def __init__(self, window: float, decay_rate: Optional[float] = None) -> None:
    """Initialize telltale with window duration in seconds and optional decay rate (units/sec)."""
    ...
```

**Input Example:**

```python
window = 60.0
decay_rate = 2.0
```

**Output Example:**

```python
# Returns None. Instance initialized with:
# self._window = 60.0
# self._decay_rate = 2.0
# self._deque = deque()
# self._latest_timestamp = None
# self._latest_value = None
```

**Edge Cases:**
- `window <= 0` -> raises `ValueError("window must be greater than zero")`
- `decay_rate < 0` -> raises `ValueError("decay_rate must be non-negative")`

### 5.2 `Telltale.update()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def update(self, timestamp: float, value: float) -> None:
    """Record a new metric sample at the given timestamp and update internal peak state."""
    ...
```

**Input Example:**

```python
timestamp = 10.0
value = 50.0
```

**Output Example:**

```python
# Returns None. Internal state updated:
# self._latest_timestamp = 10.0
# self._latest_value = 50.0
# Monotonic deque contains SampleNode(timestamp=10.0, value=50.0, score=70.0)
```

**Edge Cases:**
- `timestamp < self._latest_timestamp` -> raises `ValueError("timestamps must be non-decreasing")`
- Non-numeric timestamp or value -> Python raises standard `TypeError` / `ValueError` on `float()` conversion

### 5.3 `Telltale.current_peak()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def current_peak(self, timestamp: Optional[float] = None) -> Optional[float]:
    """Return highest active value within window at target timestamp, applying decay if configured."""
    ...
```

**Input Example:**

```python
# After update(t=10.0, v=50.0) with decay_rate=2.0 and window=60.0
timestamp = 15.0
```

**Output Example:**

```python
40.0  # Calculated as 50.0 - 2.0 * (15.0 - 10.0)
```

**Edge Cases:**
- Uninitialized state (`_latest_timestamp is None`) -> returns `None`
- `timestamp < self._latest_timestamp` -> raises `ValueError("evaluation timestamp cannot precede latest update")`
- All samples pruned due to window expiry -> returns `None`
- Decayed peak drops below `latest_value` -> returns `latest_value` (clamped)

### 5.4 `Telltale.reset()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def reset(self) -> None:
    """Clear all historical state and reset current peak to None."""
    ...
```

**Input Example:**

```python
# Called on a Telltale instance containing historical samples
telltale.reset()
```

**Output Example:**

```python
# Returns None. Internal deque cleared, _latest_timestamp = None, _latest_value = None
```

**Edge Cases:**
- Executing `reset()` on an already clean / uninitialized instance is a safe no-op.

### 5.5 `Telltale._prune_expired()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def _prune_expired(self, current_t: float) -> None:
    """Remove nodes from the front of the deque older than current_t - window."""
    ...
```

**Input Example:**

```python
current_t = 15.0  # with self._window = 5.0 (cutoff_t = 10.0)
```

**Output Example:**

```python
# Returns None. Nodes with node.timestamp < 10.0 are popped from the left of self._deque.
```

**Edge Cases:**
- Empty deque -> no-op.

## 6. Change Instructions

### 6.1 `src/boostgauge/telltale.py` (Add)

**Complete file contents:**

```python
"""Peak-hold telltale needle logic module.

Issue #41: Telltale peak-hold needle logic (pure, no GUI)
"""

from __future__ import annotations

from collections import deque
from typing import Deque, NamedTuple, Optional


class SampleNode(NamedTuple):
    """Represents an ingested metric sample and its monotonic score."""

    timestamp: float
    value: float
    score: float


class Telltale:
    """Tracks sliding-window peak values with optional linear decay."""

    def __init__(self, window: float, decay_rate: Optional[float] = None) -> None:
        """Initialize telltale with window duration in seconds and optional decay rate (units/sec)."""
        if window <= 0:
            raise ValueError("window must be greater than zero")
        if decay_rate is not None and decay_rate < 0:
            raise ValueError("decay_rate must be non-negative")

        self._window: float = float(window)
        self._decay_rate: float = float(decay_rate) if decay_rate is not None else 0.0
        self._deque: Deque[SampleNode] = deque()
        self._latest_timestamp: Optional[float] = None
        self._latest_value: Optional[float] = None

    def update(self, timestamp: float, value: float) -> None:
        """Record a new metric sample at the given timestamp and update internal peak state."""
        t = float(timestamp)
        v = float(value)

        if self._latest_timestamp is not None and t < self._latest_timestamp:
            raise ValueError("timestamps must be non-decreasing")

        self._latest_timestamp = t
        self._latest_value = v

        score = v + (self._decay_rate * t)
        node = SampleNode(timestamp=t, value=v, score=score)

        while self._deque and self._deque[-1].score <= node.score:
            self._deque.pop()

        self._deque.append(node)
        self._prune_expired(t)

    def current_peak(self, timestamp: Optional[float] = None) -> Optional[float]:
        """Return highest active value within window at target timestamp, applying decay if configured."""
        if self._latest_timestamp is None:
            return None

        eval_t = float(timestamp) if timestamp is not None else self._latest_timestamp
        if eval_t < self._latest_timestamp:
            raise ValueError("evaluation timestamp cannot precede latest update")

        self._prune_expired(eval_t)

        if not self._deque:
            return None

        head = self._deque[0]
        decayed_peak = head.value - (self._decay_rate * (eval_t - head.timestamp))

        assert self._latest_value is not None
        return max(decayed_peak, self._latest_value)

    def reset(self) -> None:
        """Clear all historical state and reset current peak to None."""
        self._deque.clear()
        self._latest_timestamp = None
        self._latest_value = None

    def _prune_expired(self, current_t: float) -> None:
        """Remove nodes from the front of the deque older than current_t - window."""
        cutoff_t = current_t - self._window
        while self._deque and self._deque[0].timestamp < cutoff_t:
            self._deque.popleft()
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

from boostgauge.telltale import Telltale


def test_t010_instantiation_and_parameter_bounds() -> None:
    """T010: Validate constructor accepts valid window and decay_rate parameters."""
    tt = Telltale(window=60.0, decay_rate=1.0)
    assert tt._window == 60.0
    assert tt._decay_rate == 1.0

    tt_no_decay = Telltale(window=10.0)
    assert tt_no_decay._decay_rate == 0.0


def test_t020_invalid_parameters_raise_value_error() -> None:
    """T020: Validate constructor raises ValueError for non-positive window or negative decay_rate."""
    with pytest.raises(ValueError, match="window must be greater than zero"):
        Telltale(window=0.0)

    with pytest.raises(ValueError, match="window must be greater than zero"):
        Telltale(window=-5.0)

    with pytest.raises(ValueError, match="decay_rate must be non-negative"):
        Telltale(window=10.0, decay_rate=-0.5)


def test_t030_uninitialized_and_post_reset_state() -> None:
    """T030: Validate current_peak returns None prior to update and after reset."""
    tt = Telltale(window=10.0, decay_rate=1.0)
    assert tt.current_peak() is None
    assert tt.current_peak(timestamp=5.0) is None

    tt.update(timestamp=1.0, value=50.0)
    assert tt.current_peak() == 50.0

    tt.reset()
    assert tt.current_peak() is None


def test_t040_out_of_order_timestamp_rejection() -> None:
    """T040: Validate update and current_peak raise ValueError on timestamp regression."""
    tt = Telltale(window=10.0)
    tt.update(timestamp=10.0, value=50.0)

    with pytest.raises(ValueError, match="timestamps must be non-decreasing"):
        tt.update(timestamp=9.5, value=60.0)

    with pytest.raises(ValueError, match="evaluation timestamp cannot precede latest update"):
        tt.current_peak(timestamp=8.0)


def test_t050_single_sample_peak_evaluation() -> None:
    """T050: Validate single update peak matches inserted sample value."""
    tt = Telltale(window=10.0)
    tt.update(timestamp=1.0, value=42.0)
    assert tt.current_peak() == 42.0
    assert tt.current_peak(timestamp=1.0) == 42.0


def test_t060_immediate_peak_update_on_new_high() -> None:
    """T060: Validate rising metric sequence updates peak instantly."""
    tt = Telltale(window=10.0)
    tt.update(timestamp=1.0, value=10.0)
    assert tt.current_peak() == 10.0

    tt.update(timestamp=2.0, value=25.0)
    assert tt.current_peak() == 25.0

    tt.update(timestamp=3.0, value=15.0)
    assert tt.current_peak() == 25.0


def test_t070_sliding_window_expiration_drop() -> None:
    """T070: Validate peak drops to next highest non-expired sample when old high expires."""
    tt = Telltale(window=5.0, decay_rate=0.0)
    tt.update(timestamp=1.0, value=100.0)
    tt.update(timestamp=3.0, value=50.0)
    tt.update(timestamp=4.0, value=20.0)

    # At t=5.0, peak is 100.0 (t=1.0 sample is active: cutoff is 0.0)
    assert tt.current_peak(timestamp=5.0) == 100.0

    # At t=7.0, t=1.0 sample (100.0) expires (cutoff is 2.0). Peak drops to 50.0 (t=3.0 sample).
    assert tt.current_peak(timestamp=7.0) == 50.0

    # At t=9.0, t=3.0 sample expires (cutoff is 4.0). Peak drops to 20.0 (t=4.0 sample).
    assert tt.current_peak(timestamp=9.0) == 20.0


def test_t080_linear_decay_kinetics_and_clamping() -> None:
    """T080: Validate peak decays linearly and clamps to latest_value."""
    tt = Telltale(window=10.0, decay_rate=2.0)
    tt.update(timestamp=0.0, value=100.0)

    # Initial peak at t=0.0 is 100.0
    assert tt.current_peak(timestamp=0.0) == 100.0

    # At t=5.0, decayed peak = 100.0 - 2.0 * 5.0 = 90.0
    assert tt.current_peak(timestamp=5.0) == 90.0

    # At t=10.0, decayed peak = 100.0 - 2.0 * 10.0 = 80.0
    assert tt.current_peak(timestamp=10.0) == 80.0

    # Update with lower value 85.0 at t=10.0
    tt.update(timestamp=10.0, value=85.0)
    # Peak decayed to 80.0 from t=0 sample, but latest_value is 85.0, so peak clamps to 85.0
    assert tt.current_peak(timestamp=10.0) == 85.0


def test_t090_complete_state_reset() -> None:
    """T090: Validate reset clears deque and historical state completely."""
    tt = Telltale(window=10.0, decay_rate=1.0)
    tt.update(timestamp=1.0, value=50.0)
    tt.update(timestamp=2.0, value=75.0)

    assert tt.current_peak() == 75.0

    tt.reset()
    assert tt.current_peak() is None
    assert tt._latest_timestamp is None
    assert tt._latest_value is None
    assert len(tt._deque) == 0

    # Can accept new updates after reset cleanly
    tt.update(timestamp=10.0, value=30.0)
    assert tt.current_peak() == 30.0
```

## 7. Pattern References

### 7.1 Type Hints and Class Architecture Pattern

**File:** `src/boostgauge/config.py` (lines 7-25)

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

**Relevance:** Demonstrates module imports standardizing `from __future__ import annotations`, standard library `typing` hints, clear docstring formatting, and custom exception bounds across the `boostgauge` codebase.

### 7.2 Unit Test Design and Execution Pattern

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

**Relevance:** Establishes the exact unit test header, pytest metadata, naming conventions (`test_tNNN_*`), and docstring traceability standards required by `docs/design/0001-test-strategy.md`.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `from __future__ import annotations` | stdlib | `src/boostgauge/telltale.py`, `tests/unit/test_telltale.py` |
| `from collections import deque` | stdlib | `src/boostgauge/telltale.py` |
| `from typing import Deque, NamedTuple, Optional` | stdlib | `src/boostgauge/telltale.py` |
| `import pytest` | PyPI (`pytest`) | `tests/unit/test_telltale.py` |

**New Dependencies:** None (Standard library Python components only).

## 9. Placeholder

*Reserved for future use to maintain alignment with LLD section numbering.*

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `Telltale.__init__()` | `window=60.0, decay_rate=1.0` | Instantiates `Telltale` with `_window=60.0`, `_decay_rate=1.0` |
| T020 | `Telltale.__init__()` | `window=0.0` or `decay_rate=-0.5` | Raises `ValueError` |
| T030 | `Telltale.current_peak()` | Fresh instance or post-`reset()` | Returns `None` |
| T040 | `Telltale.update()`, `current_peak()` | `update(10.0, 50)`, then `update(9.5, 60)` or `current_peak(8.0)` | Raises `ValueError` for timestamp regression |
| T050 | `Telltale.update()`, `current_peak()` | `update(1.0, 42.0)` | `current_peak(1.0) == 42.0` |
| T060 | `Telltale.update()`, `current_peak()` | `update(1.0, 10)`, `update(2.0, 25)`, `update(3.0, 15)` | `current_peak() == 25.0` |
| T070 | `Telltale._prune_expired()`, `current_peak()` | `window=5.0`: `update(1.0, 100)`, `update(3.0, 50)`, query `current_peak(7.0)` | `current_peak(7.0) == 50.0` (t=1.0 sample expired) |
| T080 | `Telltale.current_peak()` | `decay_rate=2.0`: `update(0.0, 100)`, queries at t=5.0, 10.0 | `current_peak(5.0) == 90.0`, `current_peak(10.0) == 80.0` (clamped to `latest_value`) |
| T090 | `Telltale.reset()` | `update(1.0, 50.0)`, `reset()`, `current_peak()` | `current_peak() is None`, `_deque` empty |

## 11. Implementation Notes

### 11.1 Error Handling Convention

All parameter validations and runtime state constraint failures raise standard Python `ValueError` with explicit, descriptive error strings (`"window must be greater than zero"`, `"decay_rate must be non-negative"`, `"timestamps must be non-decreasing"`, `"evaluation timestamp cannot precede latest update"`).

### 11.2 Monotonic Deque Scoring Convention

To achieve true $O(1)$ amortized sliding-window maximum calculation under linear decay, samples are assigned a transformed score upon entry:

$$\text{score} = v + d \times t$$

Because the decayed peak value of any sample at evaluation time $t_{eval}$ is given by:

$$v_{decayed} = v - d \times (t_{eval} - t) = (v + d \times t) - d \times t_{eval} = \text{score} - d \times t_{eval}$$

And because $- d \times t_{eval}$ is identical for all active samples at $t_{eval}$, the candidate with the highest transformed $\text{score}$ is strictly guaranteed to yield the highest decayed peak value. Maintaining a deque in monotonically decreasing order of $\text{score}$ allows instant $O(1)$ access to the active maximum via `self._deque[0]`.

### 11.3 Constants and Default Values

| Parameter | Default Value | Rationale |
|-----------|---------------|-----------|
| `decay_rate` | `0.0` (when `None`) | Preserves hard hold (no decay) by default unless linear decay is explicitly specified |

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3) - *N/A documented for 100% Add files*
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
| Finalized | 2026-07-28T16:49:55Z |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #41 |
| Verdict | APPROVED |
| Date | 2026-07-28 |
| Iterations | 0 |
| Finalized | 2026-07-28T21:50:10Z |

### Review Feedback Summary

\nThe Implementation Spec for Issue #41 (Telltale peak-hold needle logic) is exceptionally thorough, concrete, and fully executable. It provides complete, copy-ready Python implementations for both the source module `src/boostgauge/telltale.py` and the unit test suite `tests/unit/test_telltale.py`, accompanied by concrete JSON data structure examples and mathematical justifications for the $O(1)$ monotonic deque score transformation. An autonomous AI agent can implement this spec with 100% first...
