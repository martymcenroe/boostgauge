"""Static analysis pin for banned calls.

Issue #4
"""
import ast
import psutil
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