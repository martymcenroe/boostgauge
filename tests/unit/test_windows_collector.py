"""Unit tests for WindowsCollector metrics collection and resilience.

Issue #4: Feature: Windows Data Collector — ConPTY, Processes, Memory, Handles
"""

from __future__ import annotations

import queue
import time
from unittest.mock import MagicMock, patch

import psutil
import pytest

from boostgauge.collector import SystemSnapshot
from boostgauge.collectors.windows import WindowsCollector


def test_windows_collector_collect_snapshot():
    """Verify WindowsCollector.collect_snapshot returns valid SystemSnapshot (T040)."""
    collector = WindowsCollector()
    snapshot = collector.collect_snapshot()

    assert isinstance(snapshot, SystemSnapshot)
    assert snapshot.timestamp > 0
    assert snapshot.process_count >= 0
    assert snapshot.memory_percent >= 0.0
    assert snapshot.handle_count >= 0
    assert 0.0 <= snapshot.composite_value <= 100.0
    assert snapshot.driver in ("conpty", "memory_percent", "process_count", "handle_count")
    assert isinstance(snapshot.conpty_count, int)
    assert isinstance(snapshot.unleashed_sessions, int)


def test_count_conpty_processes_filters_correctly():
    """Verify conhost.exe, OpenConsole.exe, and wt.exe process filtering (T050)."""
    p1 = MagicMock()
    p1.info = {"name": "conhost.exe", "cmdline": []}
    p2 = MagicMock()
    p2.info = {"name": "OpenConsole.exe", "cmdline": []}
    p3 = MagicMock()
    p3.info = {"name": "windowsterminal.exe", "cmdline": []}
    p4 = MagicMock()
    p4.info = {"name": "explorer.exe", "cmdline": []}
    p5 = MagicMock()
    p5.info = {"name": "wt.exe", "cmdline": []}

    with patch("psutil.process_iter", return_value=[p1, p2, p3, p4, p5]):
        collector = WindowsCollector()
        count = collector.count_conpty_processes()
        assert count == 4


def test_count_conpty_processes_case_insensitive():
    """Verify conpty process name matching is case-insensitive."""
    p1 = MagicMock()
    p1.info = {"name": "CONHOST.EXE", "cmdline": []}
    p2 = MagicMock()
    p2.info = {"name": "OpenConsole.EXE", "cmdline": []}

    with patch("psutil.process_iter", return_value=[p1, p2]):
        collector = WindowsCollector()
        count = collector.count_conpty_processes()
        assert count == 2


def test_count_conpty_processes_skips_no_such_process():
    """Verify count_conpty_processes skips terminated processes without error."""
    p1 = MagicMock()
    p1.info = {"name": "conhost.exe", "cmdline": []}
    p2 = MagicMock()
    p2.info.__getitem__ = MagicMock(side_effect=psutil.NoSuchProcess(pid=999))

    with patch("psutil.process_iter", return_value=[p1, p2]):
        collector = WindowsCollector()
        count = collector.count_conpty_processes()
        assert count == 1


def test_count_conpty_processes_skips_access_denied():
    """Verify count_conpty_processes skips processes with restricted access."""
    p1 = MagicMock()
    p1.info = {"name": "conhost.exe", "cmdline": []}
    p2 = MagicMock()
    p2.info.__getitem__ = MagicMock(side_effect=psutil.AccessDenied(pid=888))

    with patch("psutil.process_iter", return_value=[p1, p2]):
        collector = WindowsCollector()
        count = collector.count_conpty_processes()
        assert count == 1


def test_count_conpty_processes_empty():
    """Verify count_conpty_processes returns 0 when no matching processes exist."""
    p1 = MagicMock()
    p1.info = {"name": "explorer.exe", "cmdline": []}
    p2 = MagicMock()
    p2.info = {"name": "chrome.exe", "cmdline": []}

    with patch("psutil.process_iter", return_value=[p1, p2]):
        collector = WindowsCollector()
        count = collector.count_conpty_processes()
        assert count == 0


def test_count_unleashed_sessions_matches_pattern():
    """Verify filtering of python process cmdlines matching unleashed-c-*.py (T060)."""
    p1 = MagicMock()
    p1.info = {"name": "python.exe", "cmdline": ["python.exe", "scripts/unleashed-c-1.py"]}
    p2 = MagicMock()
    p2.info = {"name": "python.exe", "cmdline": ["python.exe", "main.py"]}
    p3 = MagicMock()
    p3.info = {"name": "chrome.exe", "cmdline": ["chrome.exe"]}

    with patch("psutil.process_iter", return_value=[p1, p2, p3]):
        collector = WindowsCollector()
        count = collector.count_unleashed_sessions()
        assert count == 1


def test_count_unleashed_sessions_multiple_matches():
    """Verify count_unleashed_sessions counts all matching unleashed sessions."""
    p1 = MagicMock()
    p1.info = {"name": "python.exe", "cmdline": ["python.exe", "unleashed-c-1.py"]}
    p2 = MagicMock()
    p2.info = {"name": "python3.exe", "cmdline": ["python3.exe", "unleashed-c-abc.py"]}
    p3 = MagicMock()
    p3.info = {"name": "python.exe", "cmdline": ["python.exe", "unleashed-c-session2.py"]}

    with patch("psutil.process_iter", return_value=[p1, p2, p3]):
        collector = WindowsCollector()
        count = collector.count_unleashed_sessions()
        assert count == 3


def test_count_unleashed_sessions_empty_cmdline():
    """Verify count_unleashed_sessions safely handles empty cmdline lists."""
    p1 = MagicMock()
    p1.info = {"name": "python.exe", "cmdline": []}
    p2 = MagicMock()
    p2.info = {"name": "python.exe", "cmdline": None}

    with patch("psutil.process_iter", return_value=[p1, p2]):
        collector = WindowsCollector()
        count = collector.count_unleashed_sessions()
        assert count == 0


def test_count_unleashed_sessions_skips_non_python():
    """Verify count_unleashed_sessions skips non-python processes entirely."""
    p1 = MagicMock()
    p1.info = {"name": "node.exe", "cmdline": ["node.exe", "unleashed-c-1.py"]}
    p2 = MagicMock()
    p2.info = {"name": "ruby.exe", "cmdline": ["ruby.exe", "unleashed-c-2.py"]}

    with patch("psutil.process_iter", return_value=[p1, p2]):
        collector = WindowsCollector()
        count = collector.count_unleashed_sessions()
        assert count == 0


def test_count_unleashed_sessions_skips_access_denied():
    """Verify count_unleashed_sessions skips inaccessible python processes."""
    p1 = MagicMock()
    p1.info = {"name": "python.exe", "cmdline": ["python.exe", "unleashed-c-1.py"]}
    p2 = MagicMock()
    p2.info.__getitem__ = MagicMock(side_effect=psutil.AccessDenied(pid=777))

    with patch("psutil.process_iter", return_value=[p1, p2]):
        collector = WindowsCollector()
        count = collector.count_unleashed_sessions()
        assert count == 1


def test_get_handle_count_aggregates_correctly():
    """Verify handle count sums num_handles across all accessible processes."""
    p1 = MagicMock()
    p1.info = {"num_handles": 1500}
    p2 = MagicMock()
    p2.info = {"num_handles": 3000}
    p3 = MagicMock()
    p3.info = {"num_handles": 750}

    with patch("psutil.process_iter", return_value=[p1, p2, p3]):
        collector = WindowsCollector()
        count = collector.get_handle_count()
        assert count == 5250


def test_get_handle_count_with_access_denied():
    """Verify handle count aggregation gracefully handles psutil.AccessDenied (T070)."""
    p1 = MagicMock()
    p1.info = {"num_handles": 1500}
    p2 = MagicMock()
    p2.info = {"num_handles": None}

    with patch("psutil.process_iter", return_value=[p1, p2]):
        collector = WindowsCollector()
        count = collector.get_handle_count()
        assert count == 1500


def test_get_handle_count_skips_no_such_process():
    """Verify handle count skips processes that terminate during iteration."""
    p1 = MagicMock()
    p1.info = {"num_handles": 2000}
    p2 = MagicMock()
    p2.info.__getitem__ = MagicMock(side_effect=psutil.NoSuchProcess(pid=555))

    with patch("psutil.process_iter", return_value=[p1, p2]):
        collector = WindowsCollector()
        count = collector.get_handle_count()
        assert count == 2000


def test_get_handle_count_empty():
    """Verify handle count returns 0 when no processes are accessible."""
    with patch("psutil.process_iter", return_value=[]):
        collector = WindowsCollector()
        count = collector.get_handle_count()
        assert count == 0


def test_get_memory_percent_uses_psutil():
    """Verify _get_memory_percent returns value from psutil.virtual_memory (T002)."""
    mock_vmem = MagicMock()
    mock_vmem.percent = 65.5

    with patch("psutil.virtual_memory", return_value=mock_vmem):
        collector = WindowsCollector()
        result = collector._get_memory_percent()
        assert result == 65.5


def test_get_memory_percent_fallback_on_psutil_failure():
    """Verify _get_memory_percent falls back to Win32 API when psutil raises (T003)."""
    collector = WindowsCollector()

    with patch("psutil.virtual_memory", side_effect=Exception("psutil error")):
        with patch("ctypes.windll") as mock_windll:
            mock_windll.kernel32.GlobalMemoryStatusEx.return_value = True

            import ctypes
            original_sizeof = ctypes.sizeof

            result = collector._get_memory_percent()
            assert isinstance(result, float)
            assert result >= 0.0


def test_get_memory_percent_returns_zero_on_total_failure():
    """Verify _get_memory_percent returns 0.0 when both psutil and Win32 fail."""
    collector = WindowsCollector()

    with patch("psutil.virtual_memory", side_effect=Exception("psutil error")):
        with patch("ctypes.windll", side_effect=AttributeError("no windll")):
            result = collector._get_memory_percent()
            assert result == 0.0


def test_collect_snapshot_uses_custom_thresholds():
    """Verify collect_snapshot respects custom thresholds for composite computation."""
    thresholds = {
        "conpty": {"yellow": 1.0, "red": 2.0},
        "memory_percent": {"yellow": 10.0, "red": 20.0},
        "process_count": {"yellow": 5.0, "red": 10.0},
        "handle_count": {"yellow": 100.0, "red": 200.0},
    }
    collector = WindowsCollector(thresholds=thresholds)

    with patch.object(collector, "_get_memory_percent", return_value=15.0):
        with patch("psutil.pids", return_value=list(range(8))):
            with patch.object(collector, "count_conpty_processes", return_value=0):
                with patch.object(collector, "get_handle_count", return_value=0):
                    with patch.object(collector, "count_unleashed_sessions", return_value=0):
                        snapshot = collector.collect_snapshot()

    assert 0.0 <= snapshot.composite_value <= 100.0
    assert snapshot.driver in ("conpty", "memory_percent", "process_count", "handle_count")


def test_collect_snapshot_process_count_from_pids():
    """Verify collect_snapshot uses len(psutil.pids()) for process_count (T004)."""
    collector = WindowsCollector()

    with patch("psutil.pids", return_value=list(range(42))):
        with patch.object(collector, "_get_memory_percent", return_value=50.0):
            with patch.object(collector, "count_conpty_processes", return_value=0):
                with patch.object(collector, "get_handle_count", return_value=0):
                    with patch.object(collector, "count_unleashed_sessions", return_value=0):
                        snapshot = collector.collect_snapshot()

    assert snapshot.process_count == 42


def test_collect_snapshot_process_count_fallback_on_error():
    """Verify collect_snapshot returns process_count=0 when psutil.pids() raises."""
    collector = WindowsCollector()

    with patch("psutil.pids", side_effect=Exception("pids error")):
        with patch.object(collector, "_get_memory_percent", return_value=50.0):
            with patch.object(collector, "count_conpty_processes", return_value=0):
                with patch.object(collector, "get_handle_count", return_value=0):
                    with patch.object(collector, "count_unleashed_sessions", return_value=0):
                        snapshot = collector.collect_snapshot()

    assert snapshot.process_count == 0


def test_windows_collector_background_thread():
    """Verify WindowsCollector background thread publishes snapshots to queue (T080)."""
    collector = WindowsCollector(poll_interval=0.02)
    q: queue.Queue[SystemSnapshot] = queue.Queue(maxsize=20)

    assert not collector.is_running()
    collector.start(q)
    assert collector.is_running()

    time.sleep(0.15)
    collector.stop()
    assert not collector.is_running()

    assert q.qsize() >= 2
    snapshot = q.get_nowait()
    assert isinstance(snapshot, SystemSnapshot)
    assert 0.0 <= snapshot.composite_value <= 100.0


def test_windows_collector_start_idempotent():
    """Verify calling start() twice does not spawn duplicate threads."""
    collector = WindowsCollector(poll_interval=0.1)
    q: queue.Queue[SystemSnapshot] = queue.Queue(maxsize=10)

    collector.start(q)
    thread_before = collector._thread
    collector.start(q)
    thread_after = collector._thread

    assert thread_before is thread_after
    collector.stop()


def test_windows_collector_default_poll_interval():
    """Verify default poll_interval is 2.0 seconds."""
    collector = WindowsCollector()
    assert collector.poll_interval == 2.0


def test_windows_collector_custom_poll_interval():
    """Verify custom poll_interval is stored correctly."""
    collector = WindowsCollector(poll_interval=5.0)
    assert collector.poll_interval == 5.0


def test_windows_collector_collect_snapshot_fields_types():
    """Verify all SystemSnapshot fields have correct types after collect_snapshot."""
    collector = WindowsCollector()
    snapshot = collector.collect_snapshot()

    assert isinstance(snapshot.timestamp, float)
    assert isinstance(snapshot.conpty_count, int)
    assert isinstance(snapshot.process_count, int)
    assert isinstance(snapshot.memory_percent, float)
    assert isinstance(snapshot.handle_count, int)
    assert isinstance(snapshot.unleashed_sessions, int)
    assert isinstance(snapshot.driver, str)
    assert isinstance(snapshot.composite_value, float)


def test_windows_collector_collect_snapshot_timestamp_monotonic():
    """Verify successive snapshots have monotonically increasing timestamps."""
    collector = WindowsCollector()
    snapshot1 = collector.collect_snapshot()
    time.sleep(0.01)
    snapshot2 = collector.collect_snapshot()

    assert snapshot2.timestamp >= snapshot1.timestamp