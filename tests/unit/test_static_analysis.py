"""Static analysis pin for banned calls.

Issue #4
"""
import ast
from pathlib import Path


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