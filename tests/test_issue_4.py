"""Test file for Issue #4.

Emitted by AssemblyZero from the implementation spec's Section 10
test functions. Bodies are the spec's own, verbatim (#2316).
"""

import pytest
from unittest.mock import patch

@pytest.fixture
def mock_windows_collector(): pass

@pytest.fixture
def mocked_ntquery_struct(): pass

@pytest.fixture
def mocked_ntquery_struct_python(): pass

@pytest.fixture
def live_windows_collector(): pass

# tests/unit/test_collector.py

# TDD: this import fails until the implementation exists (RED phase)
from boostgauge.collector import *  # noqa: F401, F403


def test_req_1(mock_windows_collector, mocked_ntquery_struct):
    # Mocked sweep counts ConPTY (REQ-1) -- expected: snapshot.conpty_count == 2
    snapshot = mock_windows_collector.sweep()
    assert snapshot.conpty_count == 2


def test_req_3(mock_windows_collector, mocked_ntquery_struct_python):
    # Unleashed session identification (REQ-3) -- expected: snapshot.unleashed_sessions == 1
    with patch('psutil.Process.cmdline', return_value=["python", "unleashed-c-1.py"]):
        snapshot = mock_windows_collector.sweep()
        assert snapshot.unleashed_sessions == 1


def test_req_4(mock_windows_collector):
    # Non-blocking thread execution (REQ-4) -- expected: queue returns SystemSnapshot
    mock_windows_collector.start()
    snapshot = mock_windows_collector.get_queue().get(timeout=1.0)
    mock_windows_collector.stop()
    assert snapshot is not None


def test_req_5(mock_windows_collector, mocked_ntquery_struct_python):
    # AccessDenied graceful skip (REQ-5) -- expected: snapshot returns successfully without crash
    import psutil
    with patch('psutil.Process.cmdline', side_effect=psutil.AccessDenied(pid=1234)):
        snapshot = mock_windows_collector.sweep()
        assert snapshot.unleashed_sessions == 0


def test_req_6(mock_windows_collector):
    # Single sweep verification (REQ-6) -- expected: call_count == 1
    with patch.object(mock_windows_collector, 'nt_query', return_value=0) as mock_call:
        mock_windows_collector.sweep()
        assert mock_call.call_count == 1


def test_req_8(mock_windows_collector):
    # Normalized-max composite calculation (REQ-8) -- expected: driver == "memory_percent", composite_value == 100.0
    mock_windows_collector.thresholds = {"memory_percent": {"yellow": 60, "red": 80}}
    comp, driver = mock_windows_collector._compute_composite(0, 80.0, 0, 0)
    assert driver == "memory_percent"
    assert comp == 100.0

# tests/integration/test_windows_collector.py


def test_req_1_live(live_windows_collector):
    # Live cross-check of ConPTY (REQ-1) -- expected: abs(sweep_conpty - psutil_conpty) <= 1
    import psutil
    snapshot = live_windows_collector.sweep()
    psutil_conpty = sum(1 for p in psutil.process_iter(['name']) if p.info['name'] and p.info['name'].lower() in ("conhost.exe", "openconsole.exe"))
    assert abs(snapshot.conpty_count - psutil_conpty) <= 1


def test_req_2_live(live_windows_collector):
    # Live cross-check of processes and handles (REQ-2) -- expected: count match ±1, handles within 1%
    import psutil
    snapshot = live_windows_collector.sweep()
    
    psutil_procs = 0
    psutil_handles = 0
    for p in psutil.process_iter(['num_handles']):
        psutil_procs += 1
        try:
            psutil_handles += p.info.get('num_handles', 0)
        except Exception:
            pass
            
    assert abs(snapshot.process_count - psutil_procs) <= 1
    if psutil_handles > 0:
        assert abs(snapshot.handle_count - psutil_handles) / psutil_handles <= 0.01

# tests/benchmark/test_windows_collector.py


def test_req_7_benchmark(live_windows_collector):
    # Benchmark sweep performance (REQ-7) -- expected: mean execution time < 20ms
    import time
    latencies = []
    for _ in range(8):
        start = time.process_time()
        live_windows_collector.sweep()
        latencies.append(time.process_time() - start)
        time.sleep(0.01)
    
    mean_time = sum(latencies) / len(latencies)
    assert mean_time < 0.020
