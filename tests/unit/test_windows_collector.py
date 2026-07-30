"""Unit tests for WindowsCollector metrics querying, process filtering, handle enumeration, and permission error fallback.

Issue #4: Windows data collector — ConPTY, processes, memory, handles
"""

import queue
import time
from unittest.mock import MagicMock, patch

import psutil
import pytest

from boostgauge.collectors.windows import WindowsCollector, UNLEASHED_REGEX
from boostgauge.collectors import create_collector
from boostgauge.collector import SystemSnapshot


@pytest.fixture
def mock_psutil_processes():
    """Fixture returning mocked psutil processes for ConPTY and Unleashed scanning."""
    p1 = MagicMock()
    p1.info = {"name": "conhost.exe"}

    p2 = MagicMock()
    p2.info = {"name": "python.exe"}
    p2.cmdline.return_value = ["python.exe", "C:\\Scripts\\unleashed-c-401.py"]

    p3 = MagicMock()
    p3.info = {"name": "explorer.exe"}
    p3.cmdline.return_value = ["explorer.exe"]

    return [p1, p2, p3]


def test_collect_conpty_count(mock_psutil_processes):
    """T020: Test conhost.exe process counting for ConPTY metric."""
    collector = WindowsCollector()
    with patch("psutil.process_iter", return_value=mock_psutil_processes):
        count = collector.collect_conpty_count()
        assert count == 1


def test_collect_conpty_count_multiple():
    """T020: Test counting multiple ConPTY process types."""
    p1 = MagicMock()
    p1.info = {"name": "conhost.exe"}
    p2 = MagicMock()
    p2.info = {"name": "OpenConsole.exe"}
    p3 = MagicMock()
    p3.info = {"name": "WindowsTerminal.exe"}
    p4 = MagicMock()
    p4.info = {"name": "notepad.exe"}

    collector = WindowsCollector()
    with patch("psutil.process_iter", return_value=[p1, p2, p3, p4]):
        count = collector.collect_conpty_count()
        assert count == 3


def test_collect_conpty_count_access_denied():
    """T070: Test that AccessDenied on individual process is skipped gracefully."""
    p1 = MagicMock()
    p1.info = {"name": "conhost.exe"}

    p2 = MagicMock()
    p2.info = MagicMock()
    p2.info.get = MagicMock(side_effect=psutil.AccessDenied(pid=2))

    p3 = MagicMock()
    p3.info = {"name": "conhost.exe"}

    collector = WindowsCollector()
    with patch("psutil.process_iter", return_value=[p1, p2, p3]):
        count = collector.collect_conpty_count()
        assert count == 2


def test_collect_conpty_count_no_conpty_processes():
    """T020: Test zero ConPTY count when no matching processes exist."""
    p1 = MagicMock()
    p1.info = {"name": "explorer.exe"}
    p2 = MagicMock()
    p2.info = {"name": "svchost.exe"}

    collector = WindowsCollector()
    with patch("psutil.process_iter", return_value=[p1, p2]):
        count = collector.collect_conpty_count()
        assert count == 0


def test_collect_conpty_count_returns_cached_on_error():
    """T020: Test that cached value is returned when process_iter raises."""
    collector = WindowsCollector()
    collector._cached_conpty = 5

    with patch("psutil.process_iter", side_effect=Exception("iter failed")):
        count = collector.collect_conpty_count()
        assert count == 5


def test_collect_unleashed_sessions(mock_psutil_processes):
    """T040: Test unleashed session detection matching unleashed-c-*.py pattern."""
    collector = WindowsCollector()
    with patch("psutil.process_iter", return_value=mock_psutil_processes):
        count = collector.collect_unleashed_sessions()
        assert count == 1


def test_collect_unleashed_sessions_multiple():
    """T040: Test counting multiple unleashed sessions."""
    p1 = MagicMock()
    p1.info = {"name": "python.exe"}
    p1.cmdline.return_value = ["python.exe", "unleashed-c-101.py"]

    p2 = MagicMock()
    p2.info = {"name": "python3.exe"}
    p2.cmdline.return_value = ["python3.exe", "C:\\path\\unleashed-c-202.py", "--daemon"]

    p3 = MagicMock()
    p3.info = {"name": "python.exe"}
    p3.cmdline.return_value = ["python.exe", "other_script.py"]

    collector = WindowsCollector()
    with patch("psutil.process_iter", return_value=[p1, p2, p3]):
        count = collector.collect_unleashed_sessions()
        assert count == 2


def test_collect_unleashed_sessions_access_denied():
    """T040/T070: Test that AccessDenied on cmdline access is skipped gracefully."""
    p1 = MagicMock()
    p1.info = {"name": "python.exe"}
    p1.cmdline.return_value = ["python.exe", "unleashed-c-101.py"]

    p2 = MagicMock()
    p2.info = {"name": "python.exe"}
    p2.cmdline.side_effect = psutil.AccessDenied(pid=2)

    collector = WindowsCollector()
    with patch("psutil.process_iter", return_value=[p1, p2]):
        count = collector.collect_unleashed_sessions()
        assert count == 1


def test_collect_unleashed_sessions_no_python():
    """T040: Test that non-Python processes are ignored."""
    p1 = MagicMock()
    p1.info = {"name": "notepad.exe"}
    p1.cmdline.return_value = ["notepad.exe", "unleashed-c-101.py"]

    collector = WindowsCollector()
    with patch("psutil.process_iter", return_value=[p1]):
        count = collector.collect_unleashed_sessions()
        assert count == 0


def test_collect_unleashed_sessions_returns_cached_on_error():
    """T040: Test that cached value is returned on iteration error."""
    collector = WindowsCollector()
    collector._last_unleashed = 3

    with patch("psutil.process_iter", side_effect=Exception("iter failed")):
        count = collector.collect_unleashed_sessions()
        assert count == 3


def test_collect_memory_and_processes():
    """T030: Test querying virtual memory % and process count."""
    collector = WindowsCollector()
    with patch("psutil.pids", return_value=[1, 2, 3, 4, 5]), patch(
        "psutil.virtual_memory"
    ) as mock_mem:
        mock_mem.return_value.percent = 62.5
        assert collector.collect_process_count() == 5
        assert collector.collect_memory_percent() == 62.5


def test_collect_process_count_returns_cached_on_error():
    """T030: Test cached process count returned on psutil error."""
    collector = WindowsCollector()
    collector._cached_procs = 42

    with patch("psutil.pids", side_effect=psutil.Error("pids failed")):
        count = collector.collect_process_count()
        assert count == 42


def test_collect_memory_percent_returns_cached_on_error():
    """T030: Test cached memory percent returned on exception."""
    collector = WindowsCollector()
    collector._cached_memory = 55.5

    with patch("psutil.virtual_memory", side_effect=Exception("mem failed")):
        pct = collector.collect_memory_percent()
        assert pct == 55.5


def test_collect_handle_count_with_permission_denied():
    """T070: Test handle count collection with AccessDenied exception resilience."""
    p1 = MagicMock()
    p1.num_handles.return_value = 150

    p2 = MagicMock()
    p2.num_handles.side_effect = psutil.AccessDenied(pid=2)

    collector = WindowsCollector()
    with patch("psutil.process_iter", return_value=[p1, p2]):
        total_handles = collector.collect_handle_count()
        assert total_handles == 150


def test_collect_handle_count_no_such_process():
    """T070: Test handle count skips NoSuchProcess exceptions."""
    p1 = MagicMock()
    p1.num_handles.return_value = 200

    p2 = MagicMock()
    p2.num_handles.side_effect = psutil.NoSuchProcess(pid=2)

    p3 = MagicMock()
    p3.num_handles.return_value = 300

    collector = WindowsCollector()
    with patch("psutil.process_iter", return_value=[p1, p2, p3]):
        total_handles = collector.collect_handle_count()
        assert total_handles == 500


def test_collect_handle_count_returns_cached_on_error():
    """T070: Test cached handle count returned on iteration error."""
    collector = WindowsCollector()
    collector._last_handles = 99999

    with patch("psutil.process_iter", side_effect=Exception("iter failed")):
        total = collector.collect_handle_count()
        assert total == 99999


def test_collect_handle_count_sums_all_processes():
    """T030: Test handle count sums accessible processes correctly."""
    processes = []
    for h in [100, 200, 300, 400]:
        p = MagicMock()
        p.num_handles.return_value = h
        processes.append(p)

    collector = WindowsCollector()
    with patch("psutil.process_iter", return_value=processes):
        total = collector.collect_handle_count()
        assert total == 1000


def test_windows_collector_snapshot():
    """T010/T060: Test full snapshot collection cycle on WindowsCollector."""
    collector = WindowsCollector(config={"heavy_sample_ratio": 1})
    with patch.object(collector, "collect_conpty_count", return_value=3), patch.object(
        collector, "collect_process_count", return_value=120
    ), patch.object(collector, "collect_memory_percent", return_value=20.0), patch.object(
        collector, "collect_handle_count", return_value=25000
    ), patch.object(
        collector, "collect_unleashed_sessions", return_value=2
    ):
        snapshot = collector.collect_snapshot()
        assert snapshot.conpty_count == 3
        assert snapshot.process_count == 120
        assert snapshot.memory_percent == 20.0
        assert snapshot.handle_count == 25000
        assert snapshot.unleashed_sessions == 2
        assert snapshot.composite_value == 30.0
        assert snapshot.driver == "conpty"


def test_windows_collector_snapshot_is_system_snapshot():
    """T060: Test that collect_snapshot returns a SystemSnapshot instance."""
    collector = WindowsCollector(config={"heavy_sample_ratio": 1})
    with patch.object(collector, "collect_conpty_count", return_value=0), patch.object(
        collector, "collect_process_count", return_value=0
    ), patch.object(collector, "collect_memory_percent", return_value=0.0), patch.object(
        collector, "collect_handle_count", return_value=0
    ), patch.object(
        collector, "collect_unleashed_sessions", return_value=0
    ):
        snapshot = collector.collect_snapshot()
        assert isinstance(snapshot, SystemSnapshot)


def test_windows_collector_snapshot_timestamp():
    """T060: Test that snapshot timestamp is a positive float."""
    collector = WindowsCollector(config={"heavy_sample_ratio": 1})
    with patch.object(collector, "collect_conpty_count", return_value=0), patch.object(
        collector, "collect_process_count", return_value=0
    ), patch.object(collector, "collect_memory_percent", return_value=0.0), patch.object(
        collector, "collect_handle_count", return_value=0
    ), patch.object(
        collector, "collect_unleashed_sessions", return_value=0
    ):
        snapshot = collector.collect_snapshot()
        assert isinstance(snapshot.timestamp, float)
        assert snapshot.timestamp > 0


def test_windows_collector_heavy_metrics_staggered():
    """T060: Test that heavy metrics are only collected every heavy_sample_ratio iterations."""
    collector = WindowsCollector(config={"heavy_sample_ratio": 3})
    collector._last_handles = 99999
    collector._last_unleashed = 2

    with patch.object(collector, "collect_conpty_count", return_value=1), patch.object(
        collector, "collect_process_count", return_value=100
    ), patch.object(collector, "collect_memory_percent", return_value=30.0), patch.object(
        collector, "collect_handle_count", return_value=99999
    ) as mock_handles, patch.object(
        collector, "collect_unleashed_sessions", return_value=5
    ) as mock_unleashed:
        collector._iteration_count = 0
        snapshot0 = collector.collect_snapshot()
        assert mock_handles.call_count == 1
        assert mock_unleashed.call_count == 1

        collector._iteration_count = 1
        snapshot1 = collector.collect_snapshot()
        assert mock_handles.call_count == 1
        assert mock_unleashed.call_count == 1
        assert snapshot1.handle_count == 99999

        collector._iteration_count = 3
        snapshot3 = collector.collect_snapshot()
        assert mock_handles.call_count == 2
        assert mock_unleashed.call_count == 2


def test_windows_collector_iteration_count_increments():
    """T060: Test that _iteration_count increments with each collect_snapshot call."""
    collector = WindowsCollector(config={"heavy_sample_ratio": 1})
    assert collector._iteration_count == 0

    with patch.object(collector, "collect_conpty_count", return_value=0), patch.object(
        collector, "collect_process_count", return_value=0
    ), patch.object(collector, "collect_memory_percent", return_value=0.0), patch.object(
        collector, "collect_handle_count", return_value=0
    ), patch.object(
        collector, "collect_unleashed_sessions", return_value=0
    ):
        collector.collect_snapshot()
        assert collector._iteration_count == 1
        collector.collect_snapshot()
        assert collector._iteration_count == 2


def test_windows_collector_defaults():
    """T010: Test WindowsCollector instantiation with default values."""
    collector = WindowsCollector()
    assert collector.poll_interval == 2.0
    assert collector.heavy_sample_ratio == 3
    assert not collector.is_running()
    assert collector._cached_conpty == 0
    assert collector._cached_procs == 0
    assert collector._cached_memory == 0.0


def test_windows_collector_custom_config():
    """T010: Test WindowsCollector instantiation with custom config."""
    config = {"poll_interval": 5.0, "heavy_sample_ratio": 5}
    collector = WindowsCollector(config=config)
    assert collector.poll_interval == 5.0
    assert collector.heavy_sample_ratio == 5


def test_windows_collector_with_queue():
    """T010: Test WindowsCollector instantiation with a snapshot queue."""
    q = queue.Queue(maxsize=50)
    collector = WindowsCollector(snapshot_queue=q)
    assert collector.snapshot_queue is q


def test_windows_collector_thread_lifecycle():
    """T100: Test WindowsCollector background thread start and stop."""
    collector = WindowsCollector(config={"poll_interval": 0.05, "heavy_sample_ratio": 1})

    with patch.object(collector, "collect_conpty_count", return_value=0), patch.object(
        collector, "collect_process_count", return_value=0
    ), patch.object(collector, "collect_memory_percent", return_value=0.0), patch.object(
        collector, "collect_handle_count", return_value=0
    ), patch.object(
        collector, "collect_unleashed_sessions", return_value=0
    ):
        assert not collector.is_running()
        collector.start()
        assert collector.is_running()
        collector.stop()
        assert not collector.is_running()


def test_windows_collector_pushes_to_queue():
    """T060: Test WindowsCollector pushes SystemSnapshot objects to the queue."""
    q = queue.Queue(maxsize=10)
    collector = WindowsCollector(
        config={"poll_interval": 0.05, "heavy_sample_ratio": 1},
        snapshot_queue=q,
    )

    with patch.object(collector, "collect_conpty_count", return_value=1), patch.object(
        collector, "collect_process_count", return_value=50
    ), patch.object(collector, "collect_memory_percent", return_value=40.0), patch.object(
        collector, "collect_handle_count", return_value=10000
    ), patch.object(
        collector, "collect_unleashed_sessions", return_value=0
    ):
        collector.start()
        time.sleep(0.2)
        collector.stop()

    assert q.qsize() > 0
    snapshot = q.get_nowait()
    assert isinstance(snapshot, SystemSnapshot)
    assert snapshot.conpty_count == 1


def test_create_collector_factory():
    """T010: Test create_collector factory function."""
    collector = create_collector(config={})
    assert isinstance(collector, WindowsCollector)


def test_create_collector_factory_with_queue():
    """T010: Test create_collector factory passes queue correctly."""
    q = queue.Queue(maxsize=50)
    collector = create_collector(config={}, snapshot_queue=q)
    assert isinstance(collector, WindowsCollector)
    assert collector.snapshot_queue is q


def test_create_collector_factory_none_config():
    """T010: Test create_collector factory with None config uses defaults."""
    collector = create_collector()
    assert isinstance(collector, WindowsCollector)
    assert collector.poll_interval == 2.0


def test_unleashed_regex_matches_pattern():
    """T040: Test UNLEASHED_REGEX matches expected patterns."""
    assert UNLEASHED_REGEX.search("unleashed-c-123.py") is not None
    assert UNLEASHED_REGEX.search("unleashed-c-abc.py") is not None
    assert UNLEASHED_REGEX.search("C:\\Scripts\\unleashed-c-401.py") is not None
    assert UNLEASHED_REGEX.search("UNLEASHED-C-999.PY") is not None


def test_unleashed_regex_does_not_match_unrelated():
    """T040: Test UNLEASHED_REGEX does not match unrelated script names."""
    assert UNLEASHED_REGEX.search("other_script.py") is None
    assert UNLEASHED_REGEX.search("unleashed.py") is None
    assert UNLEASHED_REGEX.search("unleashed-c-.txt") is None


def test_collect_conpty_count_case_insensitive():
    """T020: Test ConPTY process name matching is case-insensitive."""
    p1 = MagicMock()
    p1.info = {"name": "ConHost.EXE"}

    p2 = MagicMock()
    p2.info = {"name": "OPENCONSOLE.EXE"}

    collector = WindowsCollector()
    with patch("psutil.process_iter", return_value=[p1, p2]):
        count = collector.collect_conpty_count()
        assert count == 2


def test_windows_collector_composite_metric_driver():
    """T050: Test that snapshot driver is set by normalized-max algorithm."""
    collector = WindowsCollector(
        config={
            "heavy_sample_ratio": 1,
            "thresholds": {
                "conpty": {"critical": 10.0},
                "memory": {"critical": 100.0},
                "process": {"critical": 500.0},
                "handle": {"critical": 100000.0},
            },
        }
    )
    with patch.object(collector, "collect_conpty_count", return_value=2), patch.object(
        collector, "collect_process_count", return_value=100
    ), patch.object(collector, "collect_memory_percent", return_value=90.0), patch.object(
        collector, "collect_handle_count", return_value=10000
    ), patch.object(
        collector, "collect_unleashed_sessions", return_value=0
    ):
        snapshot = collector.collect_snapshot()
        assert snapshot.driver == "memory"
        assert snapshot.composite_value == 90.0


def test_windows_collector_start_noop_when_running():
    """T100: Test start() is a no-op when thread already running."""
    collector = WindowsCollector(config={"poll_interval": 0.5})
    collector.start()
    thread_before = collector._thread
    collector.start()
    assert collector._thread is thread_before
    collector.stop()


def test_windows_collector_stop_noop_when_not_running():
    """T100: Test stop() is safe to call when not running."""
    collector = WindowsCollector()
    assert not collector.is_running()
    collector.stop()
    assert not collector.is_running()