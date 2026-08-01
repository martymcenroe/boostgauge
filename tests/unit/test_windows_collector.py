"""Unit tests for WindowsCollector process parsing, handle counting, Unleashed sessions, permission error handling.

Issue #4: Feature: Windows data collector — ConPTY, processes, memory, handles
"""

from unittest.mock import MagicMock, patch
import pytest
import psutil

from boostgauge.collectors.windows import WindowsCollector
from boostgauge.collector import SystemSnapshot


def _make_proc(name, num_handles=None, cmdline=None):
    proc = MagicMock()
    info = {"name": name}
    if num_handles is not None:
        info["num_handles"] = num_handles
    proc.info = info
    if cmdline is not None:
        proc.cmdline.return_value = cmdline
    else:
        proc.cmdline.return_value = []
    return proc


def test_get_conpty_count_conhost_and_openconsole():
    procs = [
        _make_proc("conhost.exe"),
        _make_proc("OpenConsole.exe"),
        _make_proc("explorer.exe"),
        _make_proc("cmd.exe"),
    ]
    with patch("psutil.process_iter", return_value=procs):
        collector = WindowsCollector()
        assert collector._get_conpty_count() == 2


def test_get_conpty_count_none():
    procs = [_make_proc("explorer.exe"), _make_proc("notepad.exe")]
    with patch("psutil.process_iter", return_value=procs):
        collector = WindowsCollector()
        assert collector._get_conpty_count() == 0


def test_get_conpty_count_case_insensitive():
    procs = [_make_proc("CONHOST.EXE"), _make_proc("openconsole.exe")]
    with patch("psutil.process_iter", return_value=procs):
        collector = WindowsCollector()
        assert collector._get_conpty_count() == 2


def test_get_conpty_count_skips_access_denied():
    proc_ok = _make_proc("conhost.exe")
    proc_denied = MagicMock()
    proc_denied.info.get.side_effect = psutil.AccessDenied(pid=99)

    with patch("psutil.process_iter", return_value=[proc_ok, proc_denied]):
        collector = WindowsCollector()
        assert collector._get_conpty_count() == 1


def test_get_conpty_count_skips_no_such_process():
    proc_ok = _make_proc("conhost.exe")
    proc_gone = MagicMock()
    proc_gone.info.get.side_effect = psutil.NoSuchProcess(pid=100)

    with patch("psutil.process_iter", return_value=[proc_ok, proc_gone]):
        collector = WindowsCollector()
        assert collector._get_conpty_count() == 1


def test_get_conpty_count_skips_permission_error():
    proc_ok = _make_proc("openconsole.exe")
    proc_perm = MagicMock()
    proc_perm.info.get.side_effect = PermissionError("access denied")

    with patch("psutil.process_iter", return_value=[proc_ok, proc_perm]):
        collector = WindowsCollector()
        assert collector._get_conpty_count() == 1


def test_get_handle_count_sums_handles():
    procs = [
        _make_proc("svchost.exe", num_handles=500),
        _make_proc("explorer.exe", num_handles=1000),
        _make_proc("chrome.exe", num_handles=2500),
    ]
    with patch("psutil.process_iter", return_value=procs):
        collector = WindowsCollector()
        assert collector._get_handle_count() == 4000


def test_get_handle_count_skips_none_handles():
    proc_with = _make_proc("svchost.exe", num_handles=1500)
    proc_without = MagicMock()
    proc_without.info = {"num_handles": None}

    with patch("psutil.process_iter", return_value=[proc_with, proc_without]):
        collector = WindowsCollector()
        assert collector._get_handle_count() == 1500


def test_get_handle_count_skips_access_denied():
    proc_ok = _make_proc("svchost.exe", num_handles=1500)
    proc_denied = MagicMock()
    proc_denied.info.get.side_effect = psutil.AccessDenied(pid=123)

    with patch("psutil.process_iter", return_value=[proc_ok, proc_denied]):
        collector = WindowsCollector()
        assert collector._get_handle_count() == 1500


def test_get_handle_count_skips_no_such_process():
    proc_ok = _make_proc("svchost.exe", num_handles=800)
    proc_gone = MagicMock()
    proc_gone.info.get.side_effect = psutil.NoSuchProcess(pid=200)

    with patch("psutil.process_iter", return_value=[proc_ok, proc_gone]):
        collector = WindowsCollector()
        assert collector._get_handle_count() == 800


def test_get_handle_count_skips_permission_error():
    proc_ok = _make_proc("svchost.exe", num_handles=600)
    proc_perm = MagicMock()
    proc_perm.info.get.side_effect = PermissionError("denied")

    with patch("psutil.process_iter", return_value=[proc_ok, proc_perm]):
        collector = WindowsCollector()
        assert collector._get_handle_count() == 600


def test_get_handle_count_empty():
    with patch("psutil.process_iter", return_value=[]):
        collector = WindowsCollector()
        assert collector._get_handle_count() == 0


def test_get_unleashed_sessions_detects_pattern():
    proc = _make_proc("python.exe", cmdline=["python.exe", "scripts/unleashed-c-runner.py"])
    with patch("psutil.process_iter", return_value=[proc]):
        collector = WindowsCollector()
        assert collector._get_unleashed_sessions() == 1


def test_get_unleashed_sessions_detects_pythonw():
    proc = _make_proc("pythonw.exe", cmdline=["pythonw.exe", "unleashed-c-session.py"])
    with patch("psutil.process_iter", return_value=[proc]):
        collector = WindowsCollector()
        assert collector._get_unleashed_sessions() == 1


def test_get_unleashed_sessions_ignores_non_matching_cmdline():
    proc = _make_proc("python.exe", cmdline=["python.exe", "other_script.py"])
    with patch("psutil.process_iter", return_value=[proc]):
        collector = WindowsCollector()
        assert collector._get_unleashed_sessions() == 0


def test_get_unleashed_sessions_ignores_non_python():
    proc = _make_proc("node.exe", cmdline=["node.exe", "unleashed-c-runner.py"])
    with patch("psutil.process_iter", return_value=[proc]):
        collector = WindowsCollector()
        assert collector._get_unleashed_sessions() == 0


def test_get_unleashed_sessions_multiple():
    proc1 = _make_proc("python.exe", cmdline=["python.exe", "unleashed-c-alpha.py"])
    proc2 = _make_proc("python.exe", cmdline=["python.exe", "unleashed-c-beta.py"])
    proc3 = _make_proc("python.exe", cmdline=["python.exe", "manage.py"])
    with patch("psutil.process_iter", return_value=[proc1, proc2, proc3]):
        collector = WindowsCollector()
        assert collector._get_unleashed_sessions() == 2


def test_get_unleashed_sessions_must_end_with_py():
    proc = _make_proc("python.exe", cmdline=["python.exe", "unleashed-c-runner.txt"])
    with patch("psutil.process_iter", return_value=[proc]):
        collector = WindowsCollector()
        assert collector._get_unleashed_sessions() == 0


def test_get_unleashed_sessions_skips_access_denied():
    proc_ok = _make_proc("python.exe", cmdline=["python.exe", "unleashed-c-runner.py"])
    proc_denied = MagicMock()
    proc_denied.info = {"name": "python.exe"}
    proc_denied.cmdline.side_effect = psutil.AccessDenied(pid=55)

    with patch("psutil.process_iter", return_value=[proc_ok, proc_denied]):
        collector = WindowsCollector()
        assert collector._get_unleashed_sessions() == 1


def test_get_unleashed_sessions_skips_no_such_process():
    proc_ok = _make_proc("python.exe", cmdline=["python.exe", "unleashed-c-runner.py"])
    proc_gone = MagicMock()
    proc_gone.info = {"name": "python.exe"}
    proc_gone.cmdline.side_effect = psutil.NoSuchProcess(pid=66)

    with patch("psutil.process_iter", return_value=[proc_ok, proc_gone]):
        collector = WindowsCollector()
        assert collector._get_unleashed_sessions() == 1


def test_get_unleashed_sessions_skips_permission_error():
    proc_ok = _make_proc("python.exe", cmdline=["python.exe", "unleashed-c-runner.py"])
    proc_perm = MagicMock()
    proc_perm.info = {"name": "python.exe"}
    proc_perm.cmdline.side_effect = PermissionError("denied")

    with patch("psutil.process_iter", return_value=[proc_ok, proc_perm]):
        collector = WindowsCollector()
        assert collector._get_unleashed_sessions() == 1


def test_collect_returns_system_snapshot():
    with patch("psutil.process_iter", return_value=[]), \
         patch("psutil.pids", return_value=list(range(150))), \
         patch("psutil.virtual_memory") as mock_mem:
        mock_mem.return_value.percent = 65.0
        collector = WindowsCollector()
        snapshot = collector.collect()

        assert isinstance(snapshot, SystemSnapshot)
        assert snapshot.process_count == 150
        assert snapshot.memory_percent == 65.0
        assert snapshot.conpty_count == 0
        assert snapshot.handle_count == 0
        assert snapshot.unleashed_sessions == 0


def test_collect_snapshot_composite_in_range():
    with patch("psutil.process_iter", return_value=[]), \
         patch("psutil.pids", return_value=list(range(100))), \
         patch("psutil.virtual_memory") as mock_mem:
        mock_mem.return_value.percent = 50.0
        collector = WindowsCollector()
        snapshot = collector.collect()

        assert 0.0 <= snapshot.composite_value <= 100.0
        assert snapshot.driver in ("conpty", "memory", "process", "handles")


def test_collect_snapshot_timestamp_is_float():
    with patch("psutil.process_iter", return_value=[]), \
         patch("psutil.pids", return_value=[]), \
         patch("psutil.virtual_memory") as mock_mem:
        mock_mem.return_value.percent = 0.0
        collector = WindowsCollector()
        snapshot = collector.collect()

        assert isinstance(snapshot.timestamp, float)
        assert snapshot.timestamp > 0.0


def test_collect_with_conpty_processes():
    conhost = _make_proc("conhost.exe", num_handles=200)
    with patch("psutil.process_iter", return_value=[conhost]), \
         patch("psutil.pids", return_value=list(range(50))), \
         patch("psutil.virtual_memory") as mock_mem:
        mock_mem.return_value.percent = 30.0
        collector = WindowsCollector()
        snapshot = collector.collect()

        assert snapshot.conpty_count == 1
        assert snapshot.handle_count == 200


def test_collect_resilient_to_all_error_types():
    proc_access = MagicMock()
    proc_access.info.get.side_effect = psutil.AccessDenied(pid=1)

    proc_gone = MagicMock()
    proc_gone.info.get.side_effect = psutil.NoSuchProcess(pid=2)

    proc_perm = MagicMock()
    proc_perm.info.get.side_effect = PermissionError("denied")

    with patch("psutil.process_iter", return_value=[proc_access, proc_gone, proc_perm]), \
         patch("psutil.pids", return_value=[]), \
         patch("psutil.virtual_memory") as mock_mem:
        mock_mem.return_value.percent = 0.0
        collector = WindowsCollector()
        snapshot = collector.collect()

        assert snapshot.conpty_count == 0
        assert snapshot.handle_count == 0


def test_windows_collector_default_thresholds():
    collector = WindowsCollector()
    assert collector.thresholds["conpty"] == 20.0
    assert collector.thresholds["memory"] == 90.0
    assert collector.thresholds["process"] == 500.0
    assert collector.thresholds["handles"] == 100000.0


def test_windows_collector_custom_config():
    config = {
        "poll_interval": 0.5,
        "thresholds": {
            "conpty": 10.0,
            "memory": 85.0,
            "process": 400.0,
            "handles": 80000.0,
        },
    }
    collector = WindowsCollector(config=config)
    assert collector.poll_interval == 0.5
    assert collector.thresholds["conpty"] == 10.0
    assert collector.thresholds["memory"] == 85.0
    assert collector.thresholds["process"] == 400.0
    assert collector.thresholds["handles"] == 80000.0