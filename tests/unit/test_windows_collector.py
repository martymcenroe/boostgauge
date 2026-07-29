"""Unit tests for WindowsCollector metrics collection and exception handling.

Issue #4: Feature: Windows Data Collector — ConPTY, Processes, Memory, Handles
"""

from __future__ import annotations

import time
from typing import Any, List
from unittest.mock import MagicMock, patch

import psutil
import pytest

from boostgauge.collectors.windows import WindowsCollector
from boostgauge.collector import SystemSnapshot


class DummyProc:
    """Mock process object for psutil inspection tests."""

    def __init__(self, info: dict[str, Any]) -> None:
        self.info = info


def test_count_conpty_processes() -> None:
    mock_procs = [
        DummyProc({"name": "conhost.exe"}),
        DummyProc({"name": "OpenConsole.exe"}),
        DummyProc({"name": "svchost.exe"}),
        DummyProc({"name": "CONHOST.EXE"}),
    ]

    with patch("psutil.process_iter", return_value=mock_procs):
        collector = WindowsCollector()
        assert collector._count_conpty() == 3


def test_count_conpty_zero_when_no_conhost() -> None:
    mock_procs = [
        DummyProc({"name": "svchost.exe"}),
        DummyProc({"name": "explorer.exe"}),
        DummyProc({"name": "notepad.exe"}),
    ]

    with patch("psutil.process_iter", return_value=mock_procs):
        collector = WindowsCollector()
        assert collector._count_conpty() == 0


def test_count_unleashed_sessions() -> None:
    mock_procs = [
        DummyProc({"name": "python.exe", "cmdline": ["python.exe", "unleashed-c-123.py"]}),
        DummyProc({"name": "python3.exe", "cmdline": ["python3", "script.py"]}),
        DummyProc({"name": "python.exe", "cmdline": ["python.exe", "UNLEASHED-C-456.PY"]}),
    ]

    with patch("psutil.process_iter", return_value=mock_procs):
        collector = WindowsCollector()
        assert collector._count_unleashed_sessions() == 2


def test_count_unleashed_sessions_empty_cmdline_skipped() -> None:
    mock_procs = [
        DummyProc({"name": "python.exe", "cmdline": None}),
        DummyProc({"name": "python.exe", "cmdline": []}),
        DummyProc({"name": "python.exe", "cmdline": ["python.exe", "unleashed-c-99.py"]}),
    ]

    with patch("psutil.process_iter", return_value=mock_procs):
        collector = WindowsCollector()
        assert collector._count_unleashed_sessions() == 1


def test_count_unleashed_sessions_non_python_skipped() -> None:
    mock_procs = [
        DummyProc({"name": "node.exe", "cmdline": ["node.exe", "unleashed-c-1.py"]}),
        DummyProc({"name": "python.exe", "cmdline": ["python.exe", "unleashed-c-2.py"]}),
    ]

    with patch("psutil.process_iter", return_value=mock_procs):
        collector = WindowsCollector()
        assert collector._count_unleashed_sessions() == 1


def test_permission_denied_handled_gracefully() -> None:
    def proc_iter_side_effect(attrs: List[str]) -> List[Any]:
        p1 = MagicMock()
        p1.info = {"name": "conhost.exe"}
        p2 = MagicMock()
        type(p2).info = property(fget=MagicMock(side_effect=psutil.AccessDenied(123)))
        return [p1, p2]

    with patch("psutil.process_iter", side_effect=proc_iter_side_effect):
        collector = WindowsCollector()
        assert collector._count_conpty() == 1


def test_no_such_process_skipped_in_conpty_count() -> None:
    def proc_iter_side_effect(attrs: List[str]) -> List[Any]:
        p1 = MagicMock()
        p1.info = {"name": "conhost.exe"}
        p2 = MagicMock()
        type(p2).info = property(fget=MagicMock(side_effect=psutil.NoSuchProcess(999)))
        p3 = MagicMock()
        p3.info = {"name": "OpenConsole.exe"}
        return [p1, p2, p3]

    with patch("psutil.process_iter", side_effect=proc_iter_side_effect):
        collector = WindowsCollector()
        assert collector._count_conpty() == 2


def test_get_process_and_handle_counts_with_sampling() -> None:
    mock_procs = [
        DummyProc({"num_handles": 100}),
        DummyProc({"num_handles": 200}),
        DummyProc({"num_handles": 50}),
    ]

    with patch("psutil.process_iter", return_value=mock_procs):
        collector = WindowsCollector()
        proc_count, handle_count = collector._get_process_and_handle_counts(sample_handles=True)
        assert proc_count == 3
        assert handle_count == 350


def test_get_process_and_handle_counts_without_sampling() -> None:
    mock_procs = [
        DummyProc({"num_handles": 100}),
        DummyProc({"num_handles": 200}),
    ]

    with patch("psutil.process_iter", return_value=mock_procs):
        collector = WindowsCollector()
        collector._cached_handle_count = 999
        proc_count, handle_count = collector._get_process_and_handle_counts(sample_handles=False)
        assert proc_count == 2
        assert handle_count == 999


def test_get_process_and_handle_counts_access_denied_falls_back_to_zero() -> None:
    def proc_iter_side_effect(attrs: List[str]) -> List[Any]:
        p1 = MagicMock()
        p1.info = {"num_handles": 100}
        p2 = MagicMock()
        type(p2).info = property(fget=MagicMock(side_effect=psutil.AccessDenied(456)))
        p3 = MagicMock()
        p3.info = {"num_handles": 50}
        return [p1, p2, p3]

    with patch("psutil.process_iter", side_effect=proc_iter_side_effect):
        collector = WindowsCollector()
        proc_count, handle_count = collector._get_process_and_handle_counts(sample_handles=True)
        assert proc_count == 3
        assert handle_count == 150


def test_get_process_and_handle_counts_none_handles_skipped() -> None:
    mock_procs = [
        DummyProc({"num_handles": None}),
        DummyProc({"num_handles": 75}),
    ]

    with patch("psutil.process_iter", return_value=mock_procs):
        collector = WindowsCollector()
        proc_count, handle_count = collector._get_process_and_handle_counts(sample_handles=True)
        assert proc_count == 2
        assert handle_count == 75


def test_collect_snapshot_returns_system_snapshot() -> None:
    mock_memory = MagicMock()
    mock_memory.percent = 55.2

    mock_procs_iter = [
        DummyProc({"name": "conhost.exe"}),
        DummyProc({"name": "svchost.exe", "num_handles": 200}),
        DummyProc({"name": "python.exe", "cmdline": ["python.exe", "unleashed-c-1.py"]}),
    ]

    with patch("psutil.virtual_memory", return_value=mock_memory):
        with patch("psutil.process_iter", return_value=mock_procs_iter):
            collector = WindowsCollector()
            collector._last_5s_poll = 0.0
            snapshot = collector.collect_snapshot(1785240005.0)

    assert isinstance(snapshot, SystemSnapshot)
    assert snapshot.timestamp == 1785240005.0
    assert snapshot.memory_percent == pytest.approx(55.2)
    assert snapshot.conpty_count >= 0
    assert snapshot.process_count >= 0
    assert snapshot.handle_count >= 0
    assert snapshot.unleashed_sessions >= 0
    assert snapshot.driver in ("conpty", "memory", "process", "handle")
    assert 0.0 <= snapshot.composite_value <= 100.0


def test_collect_snapshot_slow_metrics_cached_within_5s() -> None:
    mock_memory = MagicMock()
    mock_memory.percent = 40.0

    mock_procs = [DummyProc({"name": "svchost.exe", "num_handles": 100})]

    with patch("psutil.virtual_memory", return_value=mock_memory):
        with patch("psutil.process_iter", return_value=mock_procs):
            collector = WindowsCollector()
            now = time.time()
            collector._last_5s_poll = 0.0
            collector._cached_handle_count = 0
            collector._cached_unleashed_sessions = 0

            snapshot1 = collector.collect_snapshot(now)
            cached_handles_after_first = collector._cached_handle_count

            collector._cached_handle_count = 99999
            snapshot2 = collector.collect_snapshot(now + 1.0)

    assert snapshot2.handle_count == 99999


def test_collect_snapshot_slow_metrics_refreshed_after_5s() -> None:
    mock_memory = MagicMock()
    mock_memory.percent = 40.0

    mock_procs = [DummyProc({"name": "svchost.exe", "num_handles": 300})]

    with patch("psutil.virtual_memory", return_value=mock_memory):
        with patch("psutil.process_iter", return_value=mock_procs):
            collector = WindowsCollector()
            now = time.time()
            collector._last_5s_poll = now - 6.0
            collector._cached_handle_count = 99999

            snapshot = collector.collect_snapshot(now)

    assert snapshot.handle_count != 99999


def test_windows_collector_is_datacollector_subclass() -> None:
    from boostgauge.collector import DataCollector
    collector = WindowsCollector()
    assert isinstance(collector, DataCollector)


def test_windows_collector_config_passed_through() -> None:
    config = {"poll_interval": 3.0, "threshold_conpty": 20}
    collector = WindowsCollector(config=config)
    assert collector.poll_interval == 3.0
    assert collector.config["threshold_conpty"] == 20


def test_unleashed_pattern_case_insensitive() -> None:
    mock_procs = [
        DummyProc({"name": "Python.EXE", "cmdline": ["Python.EXE", "UNLEASHED-C-UPPER.PY"]}),
        DummyProc({"name": "python.exe", "cmdline": ["python.exe", "unleashed-c-lower.py"]}),
        DummyProc({"name": "PYTHON3", "cmdline": ["PYTHON3", "Unleashed-C-Mixed.Py"]}),
    ]

    with patch("psutil.process_iter", return_value=mock_procs):
        collector = WindowsCollector()
        assert collector._count_unleashed_sessions() == 3