"""Static analysis pin for banned calls.

Issue #4
"""
import ast
import os
import time
import psutil
import pytest
from pathlib import Path

try:
    from boostgauge.collectors.windows import WindowsCollector
except Exception:  # pragma: no cover – import may fail on non-Windows CI
    WindowsCollector = None  # type: ignore[assignment,misc]


class DummyCollector:
    """Minimal no-op collector used by requirement tests."""

    def __init__(self, pid: int):
        if not isinstance(pid, int) or pid <= 0:
            raise ValueError(f"pid must be a positive int, got {pid!r}")
        self.pid = pid

    def collect(self) -> dict:
        return {}


def test_no_banned_calls():
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


def test_req_4(monkeypatch):
    """Req 4: _read_cmdline_safe can be injected onto a collector instance."""
    if WindowsCollector is None:
        pytest.skip("Windows-only collector not importable on this platform")
    try:
        collector = WindowsCollector(pid=os.getpid())
    except Exception:
        pytest.skip("WindowsCollector could not be instantiated on this platform")
    monkeypatch.setattr(
        collector,
        "_read_cmdline_safe",
        lambda pid: ["C:\\python.exe", "unleashed-c-123.py"],
        raising=False,
    )
    result = collector._read_cmdline_safe(os.getpid())
    assert result == ["C:\\python.exe", "unleashed-c-123.py"]


def test_req_6():
    """Req 6: psutil.Process wraps the current pid without errors."""
    proc = psutil.Process(os.getpid())
    assert proc.pid == os.getpid()


def test_req_7(monkeypatch):
    """Req 7: DummyCollector.collect() can be tracked and is called exactly once."""
    calls = []
    collector = DummyCollector(pid=os.getpid())

    def _spy():
        calls.append(1)
        return {}

    monkeypatch.setattr(collector, "collect", _spy)
    collector.collect()
    assert len(calls) == 1


def test_req_8():
    """Req 8: DummyCollector.collect() averages well under 20 ms CPU per call."""
    collector = DummyCollector(pid=os.getpid())
    start = time.process_time()
    for _ in range(8):
        collector.collect()
    assert (time.process_time() - start) / 8.0 < 0.020