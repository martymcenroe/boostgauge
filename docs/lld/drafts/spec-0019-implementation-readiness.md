# Implementation Spec: Feature: history log and CSV export (#19)

<!-- Metadata -->
| Field | Value |
|-------|-------|
| Issue | #19 |
| LLD | `docs/lld/done/19-history-log-csv-export.md` |
| Generated | 2026-07-31 |
| Status | DRAFT |

## 1. Overview

**Objective:** Record system metric snapshots to rolling daily CSV files asynchronously on a background worker thread with automatic daily rotation, gzip compression, and CLI export/replay tools.

**Success Criteria:**
1. Asynchronous non-blocking snapshot enqueuing via background worker thread with 0ms GUI thread latency impact.
2. Auto-rotation of log files (`history-YYYY-MM-DD.csv`), daily gzip compression of logs older than 1 day (`history-YYYY-MM-DD.csv.gz`), and purging of archives exceeding retention bounds (default 7 days).
3. CLI `--export` support for `today` or `YYYY-MM-DD` targets in CSV (default) and JSON (`--format json`) formats.
4. CLI `--replay` command yielding historical snapshots sequentially from both raw CSV and gzipped `.csv.gz` files.
5. Fail-open error handling preventing I/O failures from interrupting GUI execution.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/config.py` | Add | Implements `HistoryConfig` dataclass for log storage, retention, and queue settings. |
| 2 | `src/boostgauge/history.py` | Add | Implements `MetricSnapshot`, CSV formatting/parsing, and thread-safe `HistoryLogger` with daily rotation and gzip archival. |
| 3 | `src/boostgauge/cli.py` | Add | Implements CLI subcommand handlers for `--export` and `--replay`. |
| 4 | `src/boostgauge/app.py` | Add | Integrates `HistoryLogger` background worker lifecycle with main application entry point. |
| 5 | `pyproject.toml` | Modify | Registers `boostgauge` command under `[project.scripts]`. |
| 6 | `tests/unit/test_config.py` | Add | Unit tests for configuration defaults and override handling. |
| 7 | `tests/unit/test_history.py` | Add | Unit tests for snapshot serialization, queue worker, fail-open logging, rotation, compression, and retention purge. |
| 8 | `tests/unit/test_cli.py` | Add | Unit tests for CLI `--export` (CSV/JSON output, exit codes) and `--replay` parsing. |

**Implementation Order Rationale:**
- `config.py` defines configuration structures required by logger and CLI.
- `history.py` provides snapshot models, file serialization, and background worker loop.
- `cli.py` imports `history.py` and `config.py` to handle export and replay commands.
- `app.py` connects `HistoryLogger` lifecycle into the main executable flow.
- `pyproject.toml` registers the CLI binary entrypoint pointing to `cli.py:main_cli`.
- `tests/unit/` modules validate each component according to TDD requirements.

## 3. Current State (for Modify/Delete files)

### 3.1 `pyproject.toml`

**Relevant excerpt** (lines 1-22):

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
dependencies = [
    "psutil (>=7.2.2,<8.0.0)",
    "pillow (>=12.2.0,<13.0.0)",
    "pystray (>=0.19.5,<0.20.0)"
]

[project.urls]
Homepage = "https://boostgauge.martymcenroe.ai"
Repository = "https://github.com/martymcenroe/boostgauge"
Documentation = "https://github.com/martymcenroe/boostgauge/wiki"
Issues = "https://github.com/martymcenroe/boostgauge/issues"
"Built with AssemblyZero" = "https://github.com/martymcenroe/AssemblyZero"
```

**What changes:** Append `[project.scripts]` table declaring `boostgauge = "boostgauge.cli:main_cli"`.

## 4. Data Structures

### 4.1 `MetricSnapshot`

**Definition:**

```python
from typing import NamedTuple

class MetricSnapshot(NamedTuple):
    timestamp: str       # ISO-8601 UTC timestamp string (e.g., "2026-03-17T14:30:00Z")
    conpty: int          # ConPTY allocations count
    memory_pct: float    # System memory usage percentage (0.0 - 100.0)
    process_count: int   # Total active processes
    handle_count: int    # System handle count
    sessions: int        # Active AI coding session count
    composite: float     # Composite pressure score (0.0 - 100.0)
    driver: str          # Collector driver identifier (e.g., "win32", "psutil")
```

**Concrete Example:**

```json
{
    "timestamp": "2026-03-17T14:30:00Z",
    "conpty": 4,
    "memory_pct": 68.5,
    "process_count": 210,
    "handle_count": 45200,
    "sessions": 3,
    "composite": 42.8,
    "driver": "win32"
}
```

### 4.2 `HistoryConfig`

**Definition:**

```python
from dataclasses import dataclass

@dataclass
class HistoryConfig:
    log_dir: str = "~/.boostgauge"
    poll_interval_sec: float = 2.0
    retention_days: int = 7
    compress_old_logs: bool = True
    max_queue_size: int = 1000
```

**Concrete Example:**

```json
{
    "log_dir": "~/.boostgauge",
    "poll_interval_sec": 2.0,
    "retention_days": 7,
    "compress_old_logs": true,
    "max_queue_size": 1000
}
```

## 5. Function Specifications

### 5.1 `format_snapshot_csv()`

**File:** `src/boostgauge/history.py`

**Signature:**

```python
def format_snapshot_csv(snapshot: MetricSnapshot) -> str:
    """Format a MetricSnapshot into a single CSV row string (without trailing newline)."""
    ...
```

**Input Example:**

```python
snapshot = MetricSnapshot(
    timestamp="2026-03-17T14:30:00Z",
    conpty=4,
    memory_pct=68.5,
    process_count=210,
    handle_count=45200,
    sessions=3,
    composite=42.8,
    driver="win32"
)
```

**Output Example:**

```python
"2026-03-17T14:30:00Z,4,68.5,210,45200,3,42.8,win32"
```

**Edge Cases:**
- `snapshot.driver` contains formula tokens (`=`, `+`, `-`, `@`) -> strip or sanitize leading token character to prevent CSV injection.

---

### 5.2 `parse_snapshot_row()`

**File:** `src/boostgauge/history.py`

**Signature:**

```python
def parse_snapshot_row(row: dict[str, str]) -> MetricSnapshot:
    """Parse a CSV dictionary row into a strongly-typed MetricSnapshot tuple."""
    ...
```

**Input Example:**

```python
row = {
    "timestamp": "2026-03-17T14:30:00Z",
    "conpty": "4",
    "memory_pct": "68.5",
    "process_count": "210",
    "handle_count": "45200",
    "sessions": "3",
    "composite": "42.8",
    "driver": "win32"
}
```

**Output Example:**

```python
MetricSnapshot(
    timestamp="2026-03-17T14:30:00Z",
    conpty=4,
    memory_pct=68.5,
    process_count=210,
    handle_count=45200,
    sessions=3,
    composite=42.8,
    driver="win32"
)
```

**Edge Cases:**
- Invalid numeric field -> raises `ValueError` with clear context message.

---

### 5.3 `HistoryLogger.__init__()`

**File:** `src/boostgauge/history.py`

**Signature:**

```python
def __init__(self, config: Optional[HistoryConfig] = None) -> None:
    """Initialize history logger configuration, worker thread, queue, and shutdown event."""
    ...
```

**Input Example:**

```python
config = HistoryConfig(log_dir="/tmp/test_logs", retention_days=14)
```

**Output Example:**

```python
# Returns HistoryLogger instance with queue initialized, worker stopped until start() called.
```

**Edge Cases:**
- `config` is `None` -> instantiates default `HistoryConfig()`.

---

### 5.4 `HistoryLogger.start()` and `HistoryLogger.stop()`

**File:** `src/boostgauge/history.py`

**Signature:**

```python
def start(self) -> None:
    """Start background worker thread."""
    ...

def stop(self) -> None:
    """Signal worker thread stop, flush remaining queue items to disk, and join worker thread."""
    ...
```

**Input Example:**

```python
logger = HistoryLogger()
logger.start()
# ... enqueuing snapshots ...
logger.stop()
```

**Output Example:**

```python
# None. Worker thread cleanly terminates and all pending queued snapshots are written.
```

**Edge Cases:**
- `stop()` called when thread not started -> returns immediately without error.

---

### 5.5 `HistoryLogger.log_snapshot()`

**File:** `src/boostgauge/history.py`

**Signature:**

```python
def log_snapshot(self, snapshot: MetricSnapshot) -> None:
    """Enqueue a snapshot for non-blocking background disk write."""
    ...
```

**Input Example:**

```python
snapshot = MetricSnapshot("2026-03-17T14:30:00Z", 4, 68.5, 210, 45200, 3, 42.8, "win32")
logger.log_snapshot(snapshot)
```

**Output Example:**

```python
# None. Item placed into internal Queue(maxsize=1000).
```

**Edge Cases:**
- Queue full (`maxsize` reached) -> drop oldest item using `queue.get_nowait()`, put new item, and log warning without raising exception.

---

### 5.6 `HistoryLogger.rotate_logs()`

**File:** `src/boostgauge/history.py`

**Signature:**

```python
def rotate_logs(self) -> None:
    """Perform daily rotation, compress historical logs > 1 day old, and purge logs > retention_days old."""
    ...
```

**Input Example:**

```python
# Invoked internally by worker loop or directly in tests.
logger.rotate_logs()
```

**Output Example:**

```python
# None. Older history-YYYY-MM-DD.csv files converted to .csv.gz and stale files deleted.
```

**Edge Cases:**
- File permissions error during gzip compression or purge -> caught by try/except block, warning logged, processing continues (fail open).

---

### 5.7 `export_history()`

**File:** `src/boostgauge/cli.py`

**Signature:**

```python
def export_history(
    target_date: str,
    format_type: str = "csv",
    config: Optional[HistoryConfig] = None
) -> str:
    """Export history data for 'today' or 'YYYY-MM-DD' in 'csv' or 'json' format."""
    ...
```

**Input Example:**

```python
target_date = "2026-03-17"
format_type = "json"
```

**Output Example:**

```python
'[{"timestamp": "2026-03-17T14:30:00Z", "conpty": 4, "memory_pct": 68.5, "process_count": 210, "handle_count": 45200, "sessions": 3, "composite": 42.8, "driver": "win32"}]'
```

**Edge Cases:**
- `target_date` invalid (not `today` or regex `^\d{4}-\d{2}-\d{2}$`) -> raises `ValueError`.
- Target log file (`history-YYYY-MM-DD.csv` or `.csv.gz`) does not exist -> raises `FileNotFoundError`.

---

### 5.8 `replay_history()`

**File:** `src/boostgauge/cli.py`

**Signature:**

```python
def replay_history(
    file_path: str,
    config: Optional[HistoryConfig] = None
) -> list[MetricSnapshot]:
    """Parse raw CSV or gzipped CSV log file and return ordered list of MetricSnapshot items."""
    ...
```

**Input Example:**

```python
file_path = "~/.boostgauge/history-2026-03-17.csv.gz"
```

**Output Example:**

```python
[
    MetricSnapshot("2026-03-17T14:30:00Z", 4, 68.5, 210, 45200, 3, 42.8, "win32")
]
```

**Edge Cases:**
- File path ends with `.gz` -> opens via standard library `gzip.open()`.

---

### 5.9 `main_cli()`

**File:** `src/boostgauge/cli.py`

**Signature:**

```python
def main_cli(args: Optional[list[str]] = None) -> int:
    """CLI entrypoint processing --export and --replay flags."""
    ...
```

**Input Example:**

```python
args = ["--export", "today", "--format", "json"]
```

**Output Example:**

```python
0  # Exit status code (0 for success, 1 for file not found or invalid args)
```

**Edge Cases:**
- Target log missing -> prints error message to `sys.stderr` and returns `1`.

## 6. Change Instructions

### 6.1 `src/boostgauge/config.py` (Add)

**Complete file contents:**

```python
"""Configuration management for boostgauge history logging.

Issue #19: Feature: history log and CSV export
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class HistoryConfig:
    """Configuration options for metric history logging, rotation, and retention."""

    log_dir: str = "~/.boostgauge"
    poll_interval_sec: float = 2.0
    retention_days: int = 7
    compress_old_logs: bool = True
    max_queue_size: int = 1000

    @property
    def resolved_log_dir(self) -> Path:
        """Return expanded Path object for the configured log directory."""
        return Path(self.log_dir).expanduser().resolve()
```

---

### 6.2 `src/boostgauge/history.py` (Add)

**Complete file contents:**

```python
"""Metric snapshot logging, async worker thread, daily rotation, and gzip archival.

Issue #19: Feature: history log and CSV export
"""

import csv
import gzip
import logging
from datetime import datetime, timezone
from pathlib import Path
import queue
import re
import threading
from typing import NamedTuple, Optional

from boostgauge.config import HistoryConfig

logger = logging.getLogger(__name__)

CSV_HEADER = [
    "timestamp",
    "conpty",
    "memory_pct",
    "process_count",
    "handle_count",
    "sessions",
    "composite",
    "driver",
]


class MetricSnapshot(NamedTuple):
    """Immutable snapshot of system metrics at a point in time."""

    timestamp: str
    conpty: int
    memory_pct: float
    process_count: int
    handle_count: int
    sessions: int
    composite: float
    driver: str


def sanitize_csv_field(value: str) -> str:
    """Prevent CSV formula injection by stripping leading execution tokens."""
    if value and value[0] in ("=", "+", "-", "@"):
        return "'" + value
    return value


def format_snapshot_csv(snapshot: MetricSnapshot) -> str:
    """Format a MetricSnapshot into a single CSV row string."""
    safe_driver = sanitize_csv_field(snapshot.driver)
    return f"{snapshot.timestamp},{snapshot.conpty},{snapshot.memory_pct},{snapshot.process_count},{snapshot.handle_count},{snapshot.sessions},{snapshot.composite},{safe_driver}"


def parse_snapshot_row(row: dict[str, str]) -> MetricSnapshot:
    """Parse a CSV header-keyed dictionary row into a MetricSnapshot object."""
    return MetricSnapshot(
        timestamp=row["timestamp"],
        conpty=int(row["conpty"]),
        memory_pct=float(row["memory_pct"]),
        process_count=int(row["process_count"]),
        handle_count=int(row["handle_count"]),
        sessions=int(row["sessions"]),
        composite=float(row["composite"]),
        driver=row["driver"],
    )


class HistoryLogger:
    """Asynchronous background worker logger for metric snapshots."""

    def __init__(self, config: Optional[HistoryConfig] = None) -> None:
        self.config = config or HistoryConfig()
        self.log_dir = self.config.resolved_log_dir
        self.queue: queue.Queue[Optional[MetricSnapshot]] = queue.Queue(
            maxsize=self.config.max_queue_size
        )
        self.shutdown_event = threading.Event()
        self.worker_thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start the background log processing worker thread."""
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.shutdown_event.clear()
        self.worker_thread = threading.Thread(
            target=self._worker_loop, daemon=True, name="HistoryLoggerWorker"
        )
        self.worker_thread.start()

    def stop(self) -> None:
        """Signal worker stop, flush queue, and terminate worker thread."""
        self.shutdown_event.set()
        if self.worker_thread and self.worker_thread.is_alive():
            try:
                self.queue.put(None, timeout=0.5)
            except queue.Full:
                pass
            self.worker_thread.join(timeout=3.0)

    def log_snapshot(self, snapshot: MetricSnapshot) -> None:
        """Enqueue snapshot for async disk writing. Drop oldest if full."""
        try:
            self.queue.put_nowait(snapshot)
        except queue.Full:
            try:
                dropped = self.queue.get_nowait()
                logger.warning("HistoryLogger queue full, dropped snapshot %s", dropped)
                self.queue.put_nowait(snapshot)
            except Exception as err:
                logger.error("Failed to enqueue snapshot fail-open: %s", err)

    def _get_log_filename(self, date_str: str) -> Path:
        return self.log_dir / f"history-{date_str}.csv"

    def rotate_logs(self) -> None:
        """Compress logs older than 1 day and purge logs older than retention period."""
        if not self.log_dir.exists():
            return

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_pattern = re.compile(r"^history-(\d{4}-\d{2}-\d{2})\.csv$")
        gz_pattern = re.compile(r"^history-(\d{4}-\d{2}-\d{2})\.csv\.gz$")
        now_date = datetime.now(timezone.utc).date()

        for file_path in list(self.log_dir.iterdir()):
            match = gz_pattern.match(file_path.name) or log_pattern.match(
                file_path.name
            )
            if match:
                file_date_str = match.group(1)
                try:
                    file_date = datetime.strptime(file_date_str, "%Y-%m-%d").date()
                    age_days = (now_date - file_date).days
                    if age_days > self.config.retention_days:
                        file_path.unlink(missing_ok=True)
                except Exception as err:
                    logger.error("Failed retention purge for %s: %s", file_path, err)

        if self.config.compress_old_logs:
            for file_path in list(self.log_dir.iterdir()):
                match_csv = log_pattern.match(file_path.name)
                if match_csv:
                    file_date_str = match_csv.group(1)
                    if file_date_str != today_str:
                        gz_path = self.log_dir / f"history-{file_date_str}.csv.gz"
                        try:
                            with open(file_path, "rb") as f_in:
                                with gzip.open(gz_path, "wb") as f_out:
                                    f_out.writelines(f_in)
                            file_path.unlink()
                        except Exception as err:
                            logger.error("Failed to gzip %s: %s", file_path, err)

    def _write_snapshot(self, snapshot: MetricSnapshot) -> None:
        date_str = snapshot.timestamp.split("T")[0]
        file_path = self._get_log_filename(date_str)
        write_header = not file_path.exists()
        try:
            with open(file_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if write_header:
                    writer.writerow(CSV_HEADER)
                writer.writerow(
                    [
                        snapshot.timestamp,
                        snapshot.conpty,
                        snapshot.memory_pct,
                        snapshot.process_count,
                        snapshot.handle_count,
                        snapshot.sessions,
                        snapshot.composite,
                        sanitize_csv_field(snapshot.driver),
                    ]
                )
        except Exception as err:
            logger.error("Fail-open error writing snapshot to %s: %s", file_path, err)

    def _worker_loop(self) -> None:
        self.rotate_logs()
        while not self.shutdown_event.is_set() or not self.queue.empty():
            try:
                item = self.queue.get(timeout=0.2)
                if item is None:
                    break
                self._write_snapshot(item)
                self.queue.task_done()
            except queue.Empty:
                continue
            except Exception as err:
                logger.error("Error in HistoryLogger worker loop: %s", err)
```

---

### 6.3 `src/boostgauge/cli.py` (Add)

**Complete file contents:**

```python
"""CLI entrypoint for boostgauge history export and replay commands.

Issue #19: Feature: history log and CSV export
"""

import argparse
import csv
import gzip
import json
from datetime import datetime, timezone
from pathlib import Path
import re
import sys
from typing import Optional

from boostgauge.config import HistoryConfig
from boostgauge.history import MetricSnapshot, parse_snapshot_row

DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def export_history(
    target_date: str,
    format_type: str = "csv",
    config: Optional[HistoryConfig] = None,
) -> str:
    """Export historical metric snapshots for a date in CSV or JSON format."""
    config = config or HistoryConfig()
    log_dir = config.resolved_log_dir

    if target_date == "today":
        resolved_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    elif DATE_REGEX.match(target_date):
        resolved_date = target_date
    else:
        raise ValueError(f"Invalid target date: {target_date}")

    csv_path = log_dir / f"history-{resolved_date}.csv"
    gz_path = log_dir / f"history-{resolved_date}.csv.gz"

    if csv_path.exists():
        open_fn = lambda p: open(p, "r", encoding="utf-8")
        target_path = csv_path
    elif gz_path.exists():
        open_fn = lambda p: gzip.open(p, "rt", encoding="utf-8")
        target_path = gz_path
    else:
        raise FileNotFoundError(
            f"No log file found for date {resolved_date} in {log_dir}"
        )

    with open_fn(target_path) as f:
        reader = csv.DictReader(f)
        snapshots = [parse_snapshot_row(row) for row in reader]

    if format_type.lower() == "json":
        return json.dumps([s._asdict() for s in snapshots], indent=2)
    elif format_type.lower() == "csv":
        with open_fn(target_path) as f:
            return f.read().strip()
    else:
        raise ValueError(f"Unsupported format type: {format_type}")


def replay_history(
    file_path: str,
    config: Optional[HistoryConfig] = None,
) -> list[MetricSnapshot]:
    """Parse a CSV or gzipped CSV history file for post-session replay."""
    config = config or HistoryConfig()
    path = Path(file_path).expanduser()
    target_path = path if path.is_absolute() else config.resolved_log_dir / path

    if not target_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if target_path.name.endswith(".gz"):
        open_fn = lambda p: gzip.open(p, "rt", encoding="utf-8")
    else:
        open_fn = lambda p: open(p, "r", encoding="utf-8")

    with open_fn(target_path) as f:
        reader = csv.DictReader(f)
        return [parse_snapshot_row(row) for row in reader]


def main_cli(args: Optional[list[str]] = None) -> int:
    """CLI entry point parsing command line flags."""
    parser = argparse.ArgumentParser(
        prog="boostgauge",
        description="BoostGauge CLI export and replay utilities",
    )
    parser.add_argument(
        "--export",
        metavar="TARGET",
        help="Export historical snapshots for 'today' or YYYY-MM-DD",
    )
    parser.add_argument(
        "--format",
        choices=["csv", "json"],
        default="csv",
        help="Export output format (default: csv)",
    )
    parser.add_argument(
        "--replay",
        metavar="FILE",
        help="Path to snapshot CSV or CSV.GZ log file to replay",
    )

    cli_args = parser.parse_args(args)

    if cli_args.export:
        try:
            output = export_history(cli_args.export, format_type=cli_args.format)
            print(output)
            return 0
        except Exception as err:
            sys.stderr.write(f"Export error: {err}\n")
            return 1

    if cli_args.replay:
        try:
            records = replay_history(cli_args.replay)
            print(json.dumps([r._asdict() for r in records], indent=2))
            return 0
        except Exception as err:
            sys.stderr.write(f"Replay error: {err}\n")
            return 1

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main_cli())
```

---

### 6.4 `src/boostgauge/app.py` (Add)

**Complete file contents:**

```python
"""Main application entry point integrating HistoryLogger lifecycle.

Issue #19: Feature: history log and CSV export
"""

import logging
from typing import Optional

from boostgauge.config import HistoryConfig
from boostgauge.history import HistoryLogger

logger = logging.getLogger(__name__)


class BoostGaugeApp:
    """Application runner integrating UI and background services."""

    def __init__(self, config: Optional[HistoryConfig] = None) -> None:
        self.config = config or HistoryConfig()
        self.history_logger = HistoryLogger(self.config)

    def start(self) -> None:
        """Start background services."""
        logger.info("Starting HistoryLogger background worker...")
        self.history_logger.start()

    def stop(self) -> None:
        """Stop background services cleanly."""
        logger.info("Stopping HistoryLogger background worker...")
        self.history_logger.stop()


def main() -> int:
    """Application entrypoint."""
    app = BoostGaugeApp()
    app.start()
    app.stop()
    return 0


if __name__ == "__main__":
    main()
```

---

### 6.5 `pyproject.toml` (Modify)

```diff
 [project.urls]
 Homepage = "https://boostgauge.martymcenroe.ai"
 Repository = "https://github.com/martymcenroe/boostgauge"
 Documentation = "https://github.com/martymcenroe/boostgauge/wiki"
 Issues = "https://github.com/martymcenroe/boostgauge/issues"
 "Built with AssemblyZero" = "https://github.com/martymcenroe/AssemblyZero"

+[project.scripts]
+boostgauge = "boostgauge.cli:main_cli"
+
 [build-system]
 requires = ["poetry-core>=2.0.0,<3.0.0"]
 build-backend = "poetry.core.masonry.api"
```

---

### 6.6 `tests/unit/test_config.py` (Add)

**Complete file contents:**

```python
"""Unit tests for HistoryConfig.

Issue #19: Feature: history log and CSV export
"""

from pathlib import Path

from boostgauge.config import HistoryConfig


def test_history_config_defaults():
    config = HistoryConfig()
    assert config.poll_interval_sec == 2.0
    assert config.retention_days == 7
    assert config.compress_old_logs is True
    assert config.max_queue_size == 1000
    assert config.resolved_log_dir == Path.home() / ".boostgauge"


def test_history_config_overrides(tmp_path):
    custom_dir = str(tmp_path / "custom_logs")
    config = HistoryConfig(
        log_dir=custom_dir,
        poll_interval_sec=5.0,
        retention_days=14,
        compress_old_logs=False,
        max_queue_size=500,
    )
    assert config.retention_days == 14
    assert config.resolved_log_dir == (tmp_path / "custom_logs").resolve()
```

---

### 6.7 `tests/unit/test_history.py` (Add)

**Complete file contents:**

```python
"""Unit tests for HistoryLogger async worker, rotation, compression, and purging.

Issue #19: Feature: history log and CSV export
"""

import gzip
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from boostgauge.config import HistoryConfig
from boostgauge.history import (
    HistoryLogger,
    MetricSnapshot,
    format_snapshot_csv,
    parse_snapshot_row,
)


@pytest.fixture
def sample_snapshot():
    return MetricSnapshot(
        timestamp="2026-03-17T14:30:00Z",
        conpty=4,
        memory_pct=68.5,
        process_count=210,
        handle_count=45200,
        sessions=3,
        composite=42.8,
        driver="win32",
    )


def test_format_and_parse_snapshot(sample_snapshot):
    row_str = format_snapshot_csv(sample_snapshot)
    assert "2026-03-17T14:30:00Z,4,68.5,210,45200,3,42.8,win32" in row_str

    fields = row_str.split(",")
    row_dict = {
        "timestamp": fields[0],
        "conpty": fields[1],
        "memory_pct": fields[2],
        "process_count": fields[3],
        "handle_count": fields[4],
        "sessions": fields[5],
        "composite": fields[6],
        "driver": fields[7],
    }
    parsed = parse_snapshot_row(row_dict)
    assert parsed == sample_snapshot


def test_async_snapshot_write(tmp_path, sample_snapshot):
    config = HistoryConfig(log_dir=str(tmp_path))
    logger = HistoryLogger(config)
    logger.start()
    logger.log_snapshot(sample_snapshot)
    logger.stop()

    expected_file = tmp_path / "history-2026-03-17.csv"
    assert expected_file.exists()
    content = expected_file.read_text(encoding="utf-8")
    assert "timestamp,conpty,memory_pct" in content
    assert "2026-03-17T14:30:00Z" in content


def test_queue_flush_on_stop(tmp_path, sample_snapshot):
    config = HistoryConfig(log_dir=str(tmp_path))
    logger = HistoryLogger(config)
    logger.start()
    for i in range(5):
        s = sample_snapshot._replace(conpty=i)
        logger.log_snapshot(s)
    logger.stop()

    expected_file = tmp_path / "history-2026-03-17.csv"
    lines = [line for line in expected_file.read_text(encoding="utf-8").splitlines() if line]
    assert len(lines) == 6  # Header + 5 records


def test_daily_rotation_and_gzip_compression(tmp_path):
    config = HistoryConfig(log_dir=str(tmp_path), compress_old_logs=True)
    yesterday_str = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d")
    old_csv = tmp_path / f"history-{yesterday_str}.csv"
    old_csv.write_text("timestamp,conpty...\n2026-03-15T00:00:00Z,1,10.0,1,1,1,1.0,win32\n")

    logger = HistoryLogger(config)
    logger.rotate_logs()

    assert not old_csv.exists()
    gz_file = tmp_path / f"history-{yesterday_str}.csv.gz"
    assert gz_file.exists()

    with gzip.open(gz_file, "rt", encoding="utf-8") as f:
        content = f.read()
        assert "2026-03-15T00:00:00Z" in content


def test_retention_purge(tmp_path):
    config = HistoryConfig(log_dir=str(tmp_path), retention_days=7)
    stale_date_str = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%d")
    stale_gz = tmp_path / f"history-{stale_date_str}.csv.gz"
    stale_gz.write_bytes(b"dummy gz content")

    logger = HistoryLogger(config)
    logger.rotate_logs()

    assert not stale_gz.exists()
```

---

### 6.8 `tests/unit/test_cli.py` (Add)

**Complete file contents:**

```python
"""Unit tests for boostgauge CLI --export and --replay commands.

Issue #19: Feature: history log and CSV export
"""

from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from boostgauge.cli import export_history, main_cli, replay_history
from boostgauge.config import HistoryConfig


@pytest.fixture
def setup_log_files(tmp_path):
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    csv_file = tmp_path / f"history-{today_str}.csv"
    csv_content = (
        "timestamp,conpty,memory_pct,process_count,handle_count,sessions,composite,driver\n"
        f"{today_str}T10:00:00Z,2,50.0,100,2000,1,25.0,win32\n"
    )
    csv_file.write_text(csv_content, encoding="utf-8")
    return HistoryConfig(log_dir=str(tmp_path)), today_str


def test_cli_export_today_csv(setup_log_files):
    config, today_str = setup_log_files
    output = export_history("today", format_type="csv", config=config)
    assert "timestamp,conpty,memory_pct" in output
    assert f"{today_str}T10:00:00Z" in output


def test_cli_export_json_format(setup_log_files):
    config, today_str = setup_log_files
    output = export_history("today", format_type="json", config=config)
    data = json.loads(output)
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["conpty"] == 2
    assert data[0]["driver"] == "win32"


def test_cli_export_missing_file_error(tmp_path):
    config = HistoryConfig(log_dir=str(tmp_path))
    with pytest.raises(FileNotFoundError):
        export_history("1999-01-01", config=config)


def test_main_cli_missing_file_exit_code(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "boostgauge.cli.HistoryConfig",
        lambda: HistoryConfig(log_dir=str(tmp_path)),
    )
    exit_code = main_cli(["--export", "1999-01-01"])
    assert exit_code == 1


def test_replay_history(setup_log_files):
    config, today_str = setup_log_files
    log_file = config.resolved_log_dir / f"history-{today_str}.csv"
    records = replay_history(str(log_file))
    assert len(records) == 1
    assert records[0].conpty == 2
    assert records[0].driver == "win32"
```

## 7. Pattern References

### 7.1 Path Resolution and Test Environment Bootstrapping

**File:** `tests/conftest.py` (lines 1-8)

```python
"""Project test bootstrap."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
```

**Relevance:** Demonstrates standard project path resolution using `pathlib.Path` objects and sys.path manipulation.

---

### 7.2 Project Configuration and Dependency Registrations

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
dependencies = [
    "psutil (>=7.2.2,<8.0.0)",
    "pillow (>=12.2.0,<13.0.0)",
    "pystray (>=0.19.5,<0.20.0)"
]
```

**Relevance:** Direct pattern for modifying project script entry points under `[project.scripts]`.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `import csv` | stdlib | `src/boostgauge/history.py`, `src/boostgauge/cli.py` |
| `import gzip` | stdlib | `src/boostgauge/history.py`, `src/boostgauge/cli.py` |
| `import queue` | stdlib | `src/boostgauge/history.py` |
| `import threading` | stdlib | `src/boostgauge/history.py` |
| `import argparse` | stdlib | `src/boostgauge/cli.py` |
| `from dataclasses import dataclass` | stdlib | `src/boostgauge/config.py` |
| `from pathlib import Path` | stdlib | `src/boostgauge/config.py`, `src/boostgauge/history.py`, `src/boostgauge/cli.py`, tests |
| `from typing import NamedTuple, Optional` | stdlib | `src/boostgauge/history.py`, `src/boostgauge/cli.py` |

**New Dependencies:** None (uses standard Python library).

## 9. Placeholder

*Reserved for alignment with LLD section numbering.*

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `HistoryLogger.log_snapshot()` | Valid `MetricSnapshot` | File `history-YYYY-MM-DD.csv` written asynchronously |
| T020 | `HistoryLogger.stop()` | Enqueued snapshots, call `stop()` | All snapshots flushed to disk, thread exits cleanly |
| T030 | `HistoryLogger._write_snapshot()` | Fail-open write error | Warning logged, worker loop continues alive |
| T040 | `HistoryLogger._write_snapshot()` | Midnight date rollover snapshot | Output written to new daily `history-YYYY-MM-DD.csv` file |
| T050 | `HistoryLogger.rotate_logs()` | `history-YYYY-MM-DD.csv` > 1 day old | File converted to `history-YYYY-MM-DD.csv.gz` |
| T060 | `HistoryLogger.rotate_logs()` | Archives > 7 days old | Files older than retention period purged |
| T070 | `export_history()` | `export_history("today", "csv")` | Header + data rows returned as string |
| T080 | `export_history()` | `export_history("today", "json")` | Valid JSON array string of snapshot objects |
| T090 | `main_cli()` | `main_cli(["--export", "1999-01-01"])` | Prints error to stderr, returns exit code 1 |
| T100 | `replay_history()` | Path to uncompressed `.csv` | Returns `list[MetricSnapshot]` |
| T110 | `replay_history()` | Path to `.csv.gz` file | Decompresses and returns `list[MetricSnapshot]` |
| T120 | `format_snapshot_csv()` | `MetricSnapshot` tuple | Single CSV row string matching schema |
| T130 | `HistoryConfig` | Custom `retention_days=14` | Config object holds 14-day retention value |

## 11. Implementation Notes

### 11.1 Thread Safety & Queue Overflows

`HistoryLogger` utilizes Python's thread-safe `queue.Queue`. To guarantee 0ms latency impact on Tkinter UI rendering, `log_snapshot()` uses `put_nowait()`. If the queue reaches maximum capacity (`maxsize=1000`), the logger pops the oldest snapshot to make room for the incoming item and logs a warning.

### 11.2 Error Handling & Fail-Open Policy

Disk I/O operations in the background worker loop are wrapped in try-except blocks. If file write or compression fails (e.g. due to permissions or disk space limits), the exception is logged to standard Python logging without raising or crashing the background worker thread or main application.

### 11.3 Cross-Platform Path Handling

Per Issue #1841 rules, all path comparisons in code and unit tests must evaluate `pathlib.Path` objects (`path == Path.home() / ".boostgauge"`) instead of checking string endings or hardcoding slash separators.

### 11.4 Constants & Defaults

| Constant | Default Value | Rationale |
|----------|---------------|-----------|
| `log_dir` | `~/.boostgauge` | Standard user-space configuration and log directory |
| `retention_days` | `7` | Keeps disk footprint below 1MB while preserving weekly history |
| `max_queue_size` | `1000` | Bounds background queue memory usage (< 2MB) |

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
| Issue | #19 |
| Verdict | APPROVED |
| Date | 2026-07-31 |
| Iterations | 1 |
| Finalized | 2026-07-31T01:05:00Z |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #19 |
| Verdict | APPROVED |
| Date | 2026-07-31 |
| Iterations | 1 |
| Finalized | 2026-07-31T06:06:25Z |

### Review Feedback Summary

The implementation spec for Issue #19 is complete, concrete, and fully executable by an autonomous AI agent. All files to be created or modified have complete code implementations or clear diffs. Data structures and function signatures include concrete examples. All assertions in the test suite trace directly to specified behaviors in the spec (async snapshot logging, queue flushing on shutdown, daily rotation, gzip archival, retention purge, CSV/JSON CLI export, and log replay). Platform path h...
