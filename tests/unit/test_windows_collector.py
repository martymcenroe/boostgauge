"""Unit test suite for WindowsCollector polling and permission error resilience.

Issue #4: Feature: Windows data collector — ConPTY, processes, memory, handles
"""

import time
from typing import Any
from unittest.mock import MagicMock, patch, PropertyMock

import psutil
import pytest

from boostgauge.collector import SystemSnapshot
from boostgauge.collectors.windows import WindowsCollector


@pytest.fixture
def mock_psutil():
    """Mock psutil module for WindowsCollector tests."""
    with patch("boostgauge.collectors.windows.psutil") as mock_p:
        mock_mem = MagicMock()
        mock_mem.percent = 55.0
        mock_p.virtual_memory.return_value = mock_mem
        mock_p.pids.return_value = list(range(1, 101))

        p1 = MagicMock()
        p1.info = {"name": "conhost.exe", "num_handles": 150, "cmdline": ["conhost.exe"]}
        p2 = MagicMock()
        p2.info = {
            "name": "python.exe",
            "num_handles": 300,
            "cmdline": ["python.exe", "unleashed-c-session.py"],
        }
        mock_p.process_iter.return_value = [p1, p2]
        mock_p.NoSuchProcess = psutil.NoSuchProcess
        mock_p.AccessDenied = psutil.AccessDenied
        mock_p.ZombieProcess = psutil.ZombieProcess
        yield mock_p


@pytest.fixture
def collector():
    """WindowsCollector instance configured for non-Windows testing."""
    return WindowsCollector(config={"_allow_non_windows_for_testing": True})


def test_windows_collector_poll_metrics(mock_psutil: Any) -> None:
    """Test standard poll_metrics execution returns correctly populated snapshot."""
    col = WindowsCollector(config={"_allow_non_windows_for_testing": True})
    snapshot = col.poll_metrics()

    assert snapshot.conpty_count == 1
    assert snapshot.process_count == 100
    assert snapshot.memory_percent == 55.0
    assert snapshot.handle_count == 450
    assert snapshot.unleashed_sessions == 1
    assert 0.0 <= snapshot.composite_value <= 100.0


def test_windows_collector_snapshot_is_system_snapshot(mock_psutil: Any) -> None:
    """Test poll_metrics returns a SystemSnapshot instance."""
    col = WindowsCollector(config={"_allow_non_windows_for_testing": True})
    snapshot = col.poll_metrics()
    assert isinstance(snapshot, SystemSnapshot)


def test_windows_collector_snapshot_fields_types(mock_psutil: Any) -> None:
    """Test all fields of returned snapshot have correct types."""
    col = WindowsCollector(config={"_allow_non_windows_for_testing": True})
    snapshot = col.poll_metrics()

    assert isinstance(snapshot.timestamp, float)
    assert isinstance(snapshot.conpty_count, int)
    assert isinstance(snapshot.process_count, int)
    assert isinstance(snapshot.memory_percent, float)
    assert isinstance(snapshot.handle_count, int)
    assert isinstance(snapshot.unleashed_sessions, int)
    assert isinstance(snapshot.driver, str)
    assert isinstance(snapshot.composite_value, float)


def test_windows_collector_count_conpty_multiple(mock_psutil: Any) -> None:
    """Test _count_conpty counts multiple conhost.exe and openconsole.exe processes."""
    p1 = MagicMock()
    p1.info = {"name": "conhost.exe", "num_handles": 100, "cmdline": ["conhost.exe"]}
    p2 = MagicMock()
    p2.info = {"name": "conhost.exe", "num_handles": 100, "cmdline": ["conhost.exe"]}
    p3 = MagicMock()
    p3.info = {"name": "openconsole.exe", "num_handles": 100, "cmdline": ["openconsole.exe"]}
    p4 = MagicMock()
    p4.info = {"name": "explorer.exe", "num_handles": 200, "cmdline": ["explorer.exe"]}
    mock_psutil.process_iter.return_value = [p1, p2, p3, p4]

    col = WindowsCollector(config={"_allow_non_windows_for_testing": True})
    count = col._count_conpty()
    assert count == 3


def test_windows_collector_count_conpty_zero(mock_psutil: Any) -> None:
    """Test _count_conpty returns 0 when no conhost or openconsole processes exist."""
    p1 = MagicMock()
    p1.info = {"name": "explorer.exe", "num_handles": 200, "cmdline": ["explorer.exe"]}
    mock_psutil.process_iter.return_value = [p1]

    col = WindowsCollector(config={"_allow_non_windows_for_testing": True})
    count = col._count_conpty()
    assert count == 0


def test_windows_collector_count_conpty_case_insensitive(mock_psutil: Any) -> None:
    """Test _count_conpty handles case variations in process names."""
    p1 = MagicMock()
    p1.info = {"name": "ConHost.EXE", "num_handles": 100, "cmdline": []}
    mock_psutil.process_iter.return_value = [p1]

    col = WindowsCollector(config={"_allow_non_windows_for_testing": True})
    count = col._count_conpty()
    assert count == 1


def test_windows_collector_get_handle_count(mock_psutil: Any) -> None:
    """Test _get_handle_count aggregates handles across processes."""
    p1 = MagicMock()
    p1.info = {"name": "foo.exe", "num_handles": 100, "cmdline": []}
    p2 = MagicMock()
    p2.info = {"name": "bar.exe", "num_handles": 200, "cmdline": []}
    mock_psutil.process_iter.return_value = [p1, p2]

    col = WindowsCollector(config={"_allow_non_windows_for_testing": True})
    total = col._get_handle_count()
    assert total == 300


def test_windows_collector_get_handle_count_skips_none(mock_psutil: Any) -> None:
    """Test _get_handle_count skips processes with None handle count."""
    p1 = MagicMock()
    p1.info = {"name": "foo.exe", "num_handles": None, "cmdline": []}
    p2 = MagicMock()
    p2.info = {"name": "bar.exe", "num_handles": 150, "cmdline": []}
    mock_psutil.process_iter.return_value = [p1, p2]

    col = WindowsCollector(config={"_allow_non_windows_for_testing": True})
    total = col._get_handle_count()
    assert total == 150


def test_windows_collector_count_unleashed_sessions(mock_psutil: Any) -> None:
    """Test _count_unleashed_sessions detects python processes with unleashed-c- in cmdline."""
    p1 = MagicMock()
    p1.info = {"name": "python.exe", "num_handles": 100, "cmdline": ["python.exe", "unleashed-c-session1.py"]}
    p2 = MagicMock()
    p2.info = {"name": "python.exe", "num_handles": 100, "cmdline": ["python.exe", "other_script.py"]}
    mock_psutil.process_iter.return_value = [p1, p2]

    col = WindowsCollector(config={"_allow_non_windows_for_testing": True})
    count = col._count_unleashed_sessions()
    assert count == 1


def test_windows_collector_count_unleashed_multiple_sessions(mock_psutil: Any) -> None:
    """Test _count_unleashed_sessions counts multiple active sessions."""
    p1 = MagicMock()
    p1.info = {"name": "python.exe", "num_handles": 100, "cmdline": ["python.exe", "unleashed-c-1.py"]}
    p2 = MagicMock()
    p2.info = {"name": "python3.exe", "num_handles": 100, "cmdline": ["python3.exe", "unleashed-c-2.py"]}
    p3 = MagicMock()
    p3.info = {"name": "notepad.exe", "num_handles": 50, "cmdline": ["notepad.exe"]}
    mock_psutil.process_iter.return_value = [p1, p2, p3]

    col = WindowsCollector(config={"_allow_non_windows_for_testing": True})
    count = col._count_unleashed_sessions()
    assert count == 2


def test_windows_collector_count_unleashed_zero(mock_psutil: Any) -> None:
    """Test _count_unleashed_sessions returns 0 when no unleashed sessions present."""
    p1 = MagicMock()
    p1.info = {"name": "explorer.exe", "num_handles": 200, "cmdline": ["explorer.exe"]}
    mock_psutil.process_iter.return_value = [p1]

    col = WindowsCollector(config={"_allow_non_windows_for_testing": True})
    count = col._count_unleashed_sessions()
    assert count == 0


def test_windows_collector_access_denied_conpty(mock_psutil: Any) -> None:
    """Test _count_conpty handles AccessDenied gracefully."""
    p_denied = MagicMock()
    p_denied.info = PropertyMock(side_effect=psutil.AccessDenied(pid=99))
    type(p_denied).info = PropertyMock(side_effect=psutil.AccessDenied(pid=99))

    p_ok = MagicMock()
    p_ok.info = {"name": "conhost.exe", "num_handles": 100, "cmdline": []}
    mock_psutil.process_iter.return_value = [p_denied, p_ok]

    col = WindowsCollector(config={"_allow_non_windows_for_testing": True})
    # Should not raise; denied process skipped
    count = col._count_conpty()
    assert count >= 0


def test_windows_collector_access_denied_handles(mock_psutil: Any) -> None:
    """Test _get_handle_count handles AccessDenied gracefully, skipping denied processes."""
    p_denied = MagicMock()
    type(p_denied).info = PropertyMock(side_effect=psutil.AccessDenied(pid=99))

    p_ok = MagicMock()
    p_ok.info = {"name": "bar.exe", "num_handles": 250, "cmdline": []}
    mock_psutil.process_iter.return_value = [p_denied, p_ok]

    col = WindowsCollector(config={"_allow_non_windows_for_testing": True})
    total = col._get_handle_count()
    assert total >= 0


def test_windows_collector_no_such_process_skipped(mock_psutil: Any) -> None:
    """Test that NoSuchProcess exceptions during iteration are silently skipped."""
    p_gone = MagicMock()
    type(p_gone).info = PropertyMock(side_effect=psutil.NoSuchProcess(pid=42))

    p_ok = MagicMock()
    p_ok.info = {"name": "conhost.exe", "num_handles": 80, "cmdline": []}
    mock_psutil.process_iter.return_value = [p_gone, p_ok]

    col = WindowsCollector(config={"_allow_non_windows_for_testing": True})
    count = col._count_conpty()
    assert count >= 0


def test_windows_collector_driver_in_valid_set(mock_psutil: Any) -> None:
    """Test poll_metrics returns a driver name from the valid set."""
    col = WindowsCollector(config={"_allow_non_windows_for_testing": True})
    snapshot = col.poll_metrics()
    assert snapshot.driver in ("conpty", "memory", "process", "handles")


def test_windows_collector_composite_value_range(mock_psutil: Any) -> None:
    """Test composite_value is always within [0.0, 100.0]."""
    col = WindowsCollector(config={"_allow_non_windows_for_testing": True})
    snapshot = col.poll_metrics()
    assert 0.0 <= snapshot.composite_value <= 100.0


def test_windows_collector_timestamp_is_recent(mock_psutil: Any) -> None:
    """Test snapshot timestamp is a recent Unix timestamp."""
    before = time.time()
    col = WindowsCollector(config={"_allow_non_windows_for_testing": True})
    snapshot = col.poll_metrics()
    after = time.time()
    assert before <= snapshot.timestamp <= after


def test_windows_collector_inherits_data_collector() -> None:
    """Test WindowsCollector is a subclass of DataCollector."""
    from boostgauge.collector import DataCollector
    col = WindowsCollector(config={"_allow_non_windows_for_testing": True})
    assert isinstance(col, DataCollector)


def test_windows_collector_default_poll_interval() -> None:
    """Test default poll_interval is 2.0 seconds."""
    col = WindowsCollector(config={"_allow_non_windows_for_testing": True})
    assert col.poll_interval == 2.0


def test_windows_collector_custom_poll_interval() -> None:
    """Test custom poll_interval is respected."""
    col = WindowsCollector(config={"poll_interval": 0.5, "_allow_non_windows_for_testing": True})
    assert col.poll_interval == 0.5


def test_windows_collector_custom_queue() -> None:
    """Test WindowsCollector accepts a custom snapshot queue."""
    import queue
    q: queue.Queue[SystemSnapshot] = queue.Queue(maxsize=50)
    col = WindowsCollector(config={"_allow_non_windows_for_testing": True}, snapshot_queue=q)
    assert col.snapshot_queue is q


def test_windows_collector_thread_lifecycle(mock_psutil: Any) -> None:
    """Test start/stop thread lifecycle for WindowsCollector."""
    import queue as q_module
    q: q_module.Queue[SystemSnapshot] = q_module.Queue(maxsize=10)
    col = WindowsCollector(
        config={"poll_interval": 0.05, "_allow_non_windows_for_testing": True},
        snapshot_queue=q,
    )
    col.start()
    time.sleep(0.15)
    col.stop(timeout=1.0)

    assert not col._thread.is_alive()
    assert q.qsize() >= 1


def test_windows_collector_queue_receives_snapshot(mock_psutil: Any) -> None:
    """Test that background thread pushes SystemSnapshot instances to the queue."""
    import queue as q_module
    q: q_module.Queue[SystemSnapshot] = q_module.Queue(maxsize=10)
    col = WindowsCollector(
        config={"poll_interval": 0.05, "_allow_non_windows_for_testing": True},
        snapshot_queue=q,
    )
    col.start()
    time.sleep(0.15)
    col.stop(timeout=1.0)

    snapshot = q.get_nowait()
    assert isinstance(snapshot, SystemSnapshot)


def test_windows_collector_process_count_from_pids(mock_psutil: Any) -> None:
    """Test process_count matches the length of psutil.pids() return value."""
    mock_psutil.pids.return_value = list(range(1, 201))
    col = WindowsCollector(config={"_allow_non_windows_for_testing": True})
    snapshot = col.poll_metrics()
    assert snapshot.process_count == 200


def test_windows_collector_memory_percent_from_virtual_memory(mock_psutil: Any) -> None:
    """Test memory_percent matches psutil.virtual_memory().percent."""
    mock_mem = MagicMock()
    mock_mem.percent = 72.3
    mock_psutil.virtual_memory.return_value = mock_mem
    col = WindowsCollector(config={"_allow_non_windows_for_testing": True})
    snapshot = col.poll_metrics()
    assert snapshot.memory_percent == 72.3


def test_windows_collector_empty_process_list(mock_psutil: Any) -> None:
    """Test poll_metrics handles empty process list gracefully."""
    mock_psutil.process_iter.return_value = []
    mock_psutil.pids.return_value = []

    col = WindowsCollector(config={"_allow_non_windows_for_testing": True})
    snapshot = col.poll_metrics()

    assert snapshot.conpty_count == 0
    assert snapshot.process_count == 0
    assert snapshot.handle_count == 0
    assert snapshot.unleashed_sessions == 0


def test_windows_collector_benchmark(mock_psutil: Any) -> None:
    """Test 10 consecutive poll_metrics calls complete in under 500ms total."""
    col = WindowsCollector(config={"_allow_non_windows_for_testing": True})

    start = time.monotonic()
    for _ in range(10):
        col.poll_metrics()
    elapsed = time.monotonic() - start

    assert elapsed < 0.5, f"10 poll_metrics calls took {elapsed:.3f}s, expected < 0.5s"


def test_windows_collector_handle_count_integer(mock_psutil: Any) -> None:
    """Test handle_count is always a non-negative integer."""
    col = WindowsCollector(config={"_allow_non_windows_for_testing": True})
    snapshot = col.poll_metrics()
    assert isinstance(snapshot.handle_count, int)
    assert snapshot.handle_count >= 0


def test_windows_collector_conpty_count_integer(mock_psutil: Any) -> None:
    """Test conpty_count is always a non-negative integer."""
    col = WindowsCollector(config={"_allow_non_windows_for_testing": True})
    snapshot = col.poll_metrics()
    assert isinstance(snapshot.conpty_count, int)
    assert snapshot.conpty_count >= 0


def test_windows_collector_unleashed_count_integer(mock_psutil: Any) -> None:
    """Test unleashed_sessions is always a non-negative integer."""
    col = WindowsCollector(config={"_allow_non_windows_for_testing": True})
    snapshot = col.poll_metrics()
    assert isinstance(snapshot.unleashed_sessions, int)
    assert snapshot.unleashed_sessions >= 0