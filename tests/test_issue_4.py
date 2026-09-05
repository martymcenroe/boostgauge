"""Test file for Issue #4.

Emitted by AssemblyZero from the implementation spec's Section 10
test functions. Bodies are the spec's own, verbatim (#2316).
"""

# TDD: this import fails until the implementation exists (RED phase)
from boostgauge.collector import *  # noqa: F401, F403


def test_req_1():
    # ConPTY count matches psutil within 1 (REQ-1) -- expected: Assertion passes without error.
    import psutil
    collector = WindowsCollector({})
    
    matched = False
    for _ in range(3):
        snap = collector.collect()
        c_count = 0
        for p in psutil.process_iter(['name']):
            try:
                if (p.info['name'] or "").lower() in ("conhost.exe", "openconsole.exe"):
                    c_count += 1
            except Exception:
                pass
        if abs(snap.conpty_count - c_count) <= 1:
            matched = True
            break
            
    assert matched, "Failed to match ConPTY counts within tolerance after 3 attempts"


def test_req_2():
    # Process and handle count matches psutil (REQ-2) -- expected: Assertion passes.
    import psutil
    collector = WindowsCollector({})
    
    matched = False
    for _ in range(3):
        snap = collector.collect()
        p_count = 0
        h_count = 0
        for p in psutil.process_iter(['num_handles']):
            p_count += 1
            try:
                h_count += p.info['num_handles'] or 0
            except Exception:
                pass
        if (abs(snap.process_count - p_count) <= 1 and 
            h_count > 0 and abs(snap.handle_count - h_count) / h_count <= 0.01):
            matched = True
            break
            
    assert matched, "Failed to match process and handle counts within tolerance after 3 attempts"


def test_req_3(monkeypatch):
    # Memory direct read (REQ-3) -- expected: snap.memory_percent == 77.7
    import collections
    vmem = collections.namedtuple('vmem', ['percent'])
    monkeypatch.setattr("psutil.virtual_memory", lambda: vmem(percent=77.7))
    collector = WindowsCollector({})
    snap = collector.collect()
    assert snap.memory_percent == 77.7


def test_req_4(monkeypatch):
    # Unleashed session matching (REQ-4) -- expected: _is_unleashed_session returns True for exact pattern.
    collector = WindowsCollector({})
    monkeypatch.setattr(collector, "_read_cmdline_safe", lambda pid: ["C:\\python.exe", "unleashed-c-123.py"])
    assert collector._is_unleashed_session("python.exe", 12345)


def test_req_5():
    # Non-blocking poll thread (REQ-5) -- expected: starts without blocking main.
    collector = DummyCollector({}, poll_interval=0.01)
    collector.start()
    assert collector._thread.is_alive()
    collector.stop()


def test_req_6(monkeypatch):
    # Permission error handling (REQ-6) -- expected: _read_cmdline_safe returns [].
    def mock_cmdline(*args): raise psutil.AccessDenied()
    monkeypatch.setattr(psutil.Process, "cmdline", mock_cmdline)
    collector = WindowsCollector({})
    assert collector._read_cmdline_safe(0) == []


def test_req_7(monkeypatch):
    # Single sweep pin (REQ-7) -- expected: NtQuerySystemInformation called exactly once per loop.
    import ctypes
    calls = []
    def mock_query(*args):
        calls.append(1)
        return 0
    monkeypatch.setattr(ctypes.windll.ntdll, "NtQuerySystemInformation", mock_query)
    collector = WindowsCollector({})
    collector.collect()
    assert len(calls) == 1


def test_req_8():
    # CPU overhead benchmark (REQ-8) -- expected: execution time < 20ms per tick.
    import time
    collector = WindowsCollector({})
    collector.collect()
    start = time.process_time()
    for _ in range(8):
        collector.collect()
    assert (time.process_time() - start) / 8.0 < 0.020


def test_req_9():
    # Normalized-max logic (REQ-9) -- expected: returns correctly formatted driver and composite.
    collector = DummyCollector({"conpty": {"yellow": 10.0, "red": 20.0}})
    val, driver = collector._compute_composite({"conpty": 15.0})
    assert driver == "conpty"
    assert val == 70.0


def test_req_10():
    # Source code AST sweep (REQ-10) -- expected: no process_iter found.
    import ast
    from pathlib import Path
    windows_file = Path("src") / "boostgauge" / "collectors" / "windows.py"
    if not windows_file.exists():
        return
        
    content = windows_file.read_text(encoding="utf-8")
    tree = ast.parse(content)
    
    banned_found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            if node.attr in ("process_iter", "pids") and isinstance(node.value, ast.Name) and node.value.id == "psutil":
                banned_found = True
                
    assert not banned_found, "psutil.process_iter or pids was found in windows.py"


def test_value_error():
    import pytest
    with pytest.raises(ValueError):
        DummyCollector({}, poll_interval=-1.0)


def test_not_implemented_error():
    import pytest
    with pytest.raises(NotImplementedError):
        DataCollector.collect(None)
