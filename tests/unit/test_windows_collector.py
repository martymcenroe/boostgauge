"""Unit tests for WindowsCollector metrics polling and fallback handling.

Issue #4: Windows data collector — ConPTY, processes, memory, handles
"""

from unittest.mock import MagicMock, PropertyMock, patch
import pytest
import psutil

from boostgauge.collectors.windows import WindowsCollector


def test_count_conpty_counts_conhost_and_wt():
    """T010: ConPTY process scanning counts conhost.exe and WindowsTerminal.exe."""
    collector = WindowsCollector()

    p1 = MagicMock()
    p1.info = {"name": "conhost.exe"}
    p2 = MagicMock()
    p2.info = {"name": "WindowsTerminal.exe"}
    p3 = MagicMock()
    p3.info = {"name": "explorer.exe"}

    with patch("psutil.process_iter", return_value=[p1, p2, p3]):
        cnt = collector._count_conpty()
        assert cnt == 2


def test_count_conpty_case_insensitive():
    collector = WindowsCollector()

    p1 = MagicMock()
    p1.info = {"name": "CONHOST.EXE"}
    p2 = MagicMock()
    p2.info = {"name": "windowsterminal.exe"}

    with patch("psutil.process_iter", return_value=[p1, p2]):
        cnt = collector._count_conpty()
        assert cnt == 2


def test_count_conpty_skips_no_such_process():
    """T020: NoSuchProcess during ConPTY iteration is skipped without error."""
    collector = WindowsCollector()

    p_ok = MagicMock()
    p_ok.info = {"name": "conhost.exe"}

    p_bad = MagicMock()
    type(p_bad).info = PropertyMock(side_effect=psutil.NoSuchProcess(pid=999))

    with patch("psutil.process_iter", return_value=[p_ok, p_bad]):
        cnt = collector._count_conpty()
        assert cnt == 1


def test_count_conpty_skips_access_denied():
    collector = WindowsCollector()

    p_ok = MagicMock()
    p_ok.info = {"name": "conhost.exe"}

    p_bad = MagicMock()
    type(p_bad).info = PropertyMock(side_effect=psutil.AccessDenied(pid=999))

    with patch("psutil.process_iter", return_value=[p_ok, p_bad]):
        cnt = collector._count_conpty()
        assert cnt == 1


def test_count_conpty_returns_zero_on_empty():
    collector = WindowsCollector()
    with patch("psutil.process_iter", return_value=[]):
        cnt = collector._count_conpty()
        assert cnt == 0


def test_count_memory_returns_float():
    """T030: Memory percentage matches psutil.virtual_memory().percent."""
    collector = WindowsCollector()

    mock_vmem = MagicMock()
    mock_vmem.percent = 72.4

    with patch("psutil.virtual_memory", return_value=mock_vmem):
        pct = collector._count_memory()
        assert pct == 72.4


def test_count_memory_returns_float_type():
    collector = WindowsCollector()

    mock_vmem = MagicMock()
    mock_vmem.percent = 55

    with patch("psutil.virtual_memory", return_value=mock_vmem):
        pct = collector._count_memory()
        assert isinstance(pct, float)


def test_count_memory_exception_returns_zero():
    collector = WindowsCollector()

    with patch("psutil.virtual_memory", side_effect=Exception("fail")):
        pct = collector._count_memory()
        assert pct == 0.0


def test_count_processes_returns_count():
    """T040: Process count matches len(psutil.pids())."""
    collector = WindowsCollector()

    with patch("psutil.pids", return_value=list(range(1, 151))):
        cnt = collector._count_processes()
        assert cnt == 150


def test_count_processes_exception_returns_zero():
    collector = WindowsCollector()

    with patch("psutil.pids", side_effect=Exception("fail")):
        cnt = collector._count_processes()
        assert cnt == 0


def test_count_handles_aggregates_across_processes():
    """T050: Handle count sums handles across all accessible processes."""
    collector = WindowsCollector()

    p1 = MagicMock()
    p1.info = {"num_handles": 100}
    p2 = MagicMock()
    p2.info = {"num_handles": 200}
    p3 = MagicMock()
    p3.info = {"num_handles": 300}

    with patch("psutil.process_iter", return_value=[p1, p2, p3]):
        handles = collector._count_handles()
        assert handles == 600


def test_count_handles_skips_access_denied_process():
    """T060: AccessDenied processes are skipped during handle aggregation."""
    collector = WindowsCollector()

    p_ok = MagicMock()
    p_ok.info = {"num_handles": 150}

    p_bad = MagicMock()
    type(p_bad).info = PropertyMock(side_effect=psutil.AccessDenied(pid=999))

    with patch("psutil.process_iter", return_value=[p_ok, p_bad]):
        handles = collector._count_handles()
        assert handles == 150


def test_count_handles_skips_no_such_process():
    collector = WindowsCollector()

    p_ok = MagicMock()
    p_ok.info = {"num_handles": 250}

    p_bad = MagicMock()
    type(p_bad).info = PropertyMock(side_effect=psutil.NoSuchProcess(pid=999))

    with patch("psutil.process_iter", return_value=[p_ok, p_bad]):
        handles = collector._count_handles()
        assert handles == 250


def test_count_handles_skips_zombie_process():
    collector = WindowsCollector()

    p_ok = MagicMock()
    p_ok.info = {"num_handles": 100}

    p_zombie = MagicMock()
    type(p_zombie).info = PropertyMock(side_effect=psutil.ZombieProcess(pid=999))

    with patch("psutil.process_iter", return_value=[p_ok, p_zombie]):
        handles = collector._count_handles()
        assert handles == 100


def test_count_handles_skips_none_num_handles():
    collector = WindowsCollector()

    p_ok = MagicMock()
    p_ok.info = {"num_handles": 100}

    p_none = MagicMock()
    p_none.info = {"num_handles": None}

    with patch("psutil.process_iter", return_value=[p_ok, p_none]):
        handles = collector._count_handles()
        assert handles == 100


def test_count_handles_system_error_returns_cached():
    """T100: System-level error during handle scan reuses cached count."""
    collector = WindowsCollector()
    collector._cached_handle_count = 42000

    with patch("psutil.process_iter", side_effect=Exception("system error")):
        handles = collector._count_handles()
        assert handles == 42000


def test_count_unleashed_sessions_detects_process():
    """T070: Unleashed session detection finds python processes with unleashed-c-*.py."""
    collector = WindowsCollector()

    p1 = MagicMock()
    p1.info = {"name": "python.exe", "cmdline": ["python.exe", "unleashed-c-123.py"]}
    p2 = MagicMock()
    p2.info = {"name": "python.exe", "cmdline": ["python.exe", "other_script.py"]}

    with patch("psutil.process_iter", return_value=[p1, p2]):
        sessions = collector._count_unleashed_sessions()
        assert sessions == 1


def test_count_unleashed_sessions_multiple():
    collector = WindowsCollector()

    p1 = MagicMock()
    p1.info = {"name": "python.exe", "cmdline": ["python.exe", "unleashed-c-1.py"]}
    p2 = MagicMock()
    p2.info = {"name": "python3.exe", "cmdline": ["python3.exe", "unleashed-c-2.py"]}
    p3 = MagicMock()
    p3.info = {"name": "python.exe", "cmdline": ["python.exe", "main.py"]}

    with patch("psutil.process_iter", return_value=[p1, p2, p3]):
        sessions = collector._count_unleashed_sessions()
        assert sessions == 2


def test_count_unleashed_sessions_ignores_non_python():
    collector = WindowsCollector()

    p1 = MagicMock()
    p1.info = {"name": "node.exe", "cmdline": ["node.exe", "unleashed-c-1.py"]}

    with patch("psutil.process_iter", return_value=[p1]):
        sessions = collector._count_unleashed_sessions()
        assert sessions == 0


def test_count_unleashed_sessions_skips_access_denied():
    collector = WindowsCollector()

    p_ok = MagicMock()
    p_ok.info = {"name": "python.exe", "cmdline": ["python.exe", "unleashed-c-1.py"]}

    p_bad = MagicMock()
    type(p_bad).info = PropertyMock(side_effect=psutil.AccessDenied(pid=999))

    with patch("psutil.process_iter", return_value=[p_ok, p_bad]):
        sessions = collector._count_unleashed_sessions()
        assert sessions == 1


def test_count_unleashed_sessions_system_error_returns_cached():
    collector = WindowsCollector()
    collector._cached_unleashed_count = 3

    with patch("psutil.process_iter", side_effect=Exception("system error")):
        sessions = collector._count_unleashed_sessions()
        assert sessions == 3


def test_count_unleashed_sessions_empty_cmdline():
    collector = WindowsCollector()

    p1 = MagicMock()
    p1.info = {"name": "python.exe", "cmdline": []}

    with patch("psutil.process_iter", return_value=[p1]):
        sessions = collector._count_unleashed_sessions()
        assert sessions == 0


def test_collect_raw_metrics_returns_expected_keys():
    collector = WindowsCollector()

    with patch.object(collector, "_count_conpty", return_value=4), \
         patch.object(collector, "_count_processes", return_value=182), \
         patch.object(collector, "_count_memory", return_value=54.2), \
         patch.object(collector, "_count_handles", return_value=34500), \
         patch.object(collector, "_count_unleashed_sessions", return_value=2):
        result = collector._collect_raw_metrics()

    assert set(result.keys()) == {
        "conpty_count",
        "process_count",
        "memory_percent",
        "handle_count",
        "unleashed_sessions",
    }
    assert result["conpty_count"] == 4
    assert result["process_count"] == 182
    assert result["memory_percent"] == 54.2
    assert result["handle_count"] == 34500
    assert result["unleashed_sessions"] == 2


def test_collect_raw_metrics_uses_cached_handle_count():
    """Handle count is cached and reused within 5s stagger interval."""
    collector = WindowsCollector()
    collector._cached_handle_count = 99999
    collector._last_handle_time = float("inf")  # forces cache hit

    with patch.object(collector, "_count_conpty", return_value=1), \
         patch.object(collector, "_count_processes", return_value=10), \
         patch.object(collector, "_count_memory", return_value=10.0), \
         patch.object(collector, "_count_handles") as mock_handles, \
         patch.object(collector, "_count_unleashed_sessions", return_value=0):
        result = collector._collect_raw_metrics()
        mock_handles.assert_not_called()

    assert result["handle_count"] == 99999


def test_collect_raw_metrics_uses_cached_unleashed_count():
    """Unleashed count is cached and reused within 5s stagger interval."""
    collector = WindowsCollector()
    collector._cached_unleashed_count = 7
    collector._last_unleashed_time = float("inf")  # forces cache hit

    with patch.object(collector, "_count_conpty", return_value=1), \
         patch.object(collector, "_count_processes", return_value=10), \
         patch.object(collector, "_count_memory", return_value=10.0), \
         patch.object(collector, "_count_handles", return_value=100), \
         patch.object(collector, "_count_unleashed_sessions") as mock_unleashed:
        result = collector._collect_raw_metrics()
        mock_unleashed.assert_not_called()

    assert result["unleashed_sessions"] == 7


def test_collect_raw_metrics_refreshes_handle_after_interval():
    """Handle count is refreshed after the 5s stagger interval elapses."""
    import time
    collector = WindowsCollector()
    collector._last_handle_time = time.time() - 10.0  # expired

    with patch.object(collector, "_count_conpty", return_value=1), \
         patch.object(collector, "_count_processes", return_value=10), \
         patch.object(collector, "_count_memory", return_value=10.0), \
         patch.object(collector, "_count_handles", return_value=55000) as mock_handles, \
         patch.object(collector, "_count_unleashed_sessions", return_value=0):
        result = collector._collect_raw_metrics()
        mock_handles.assert_called_once()

    assert result["handle_count"] == 55000


def test_windows_collector_init_defaults():
    collector = WindowsCollector()
    assert collector._last_handle_time == 0.0
    assert collector._last_unleashed_time == 0.0
    assert collector._cached_handle_count == 0
    assert collector._cached_unleashed_count == 0


def test_windows_collector_poll_returns_snapshot():
    from boostgauge.collector import SystemSnapshot
    collector = WindowsCollector()

    with patch.object(collector, "_collect_raw_metrics", return_value={
        "conpty_count": 3,
        "process_count": 120,
        "memory_percent": 45.0,
        "handle_count": 20000,
        "unleashed_sessions": 1,
    }):
        snapshot = collector.poll()

    assert isinstance(snapshot, SystemSnapshot)
    assert snapshot.conpty_count == 3
    assert snapshot.process_count == 120
    assert snapshot.memory_percent == 45.0
    assert snapshot.handle_count == 20000
    assert snapshot.unleashed_sessions == 1
    assert isinstance(snapshot.driver, str)
    assert 0.0 <= snapshot.composite_value <= 100.0