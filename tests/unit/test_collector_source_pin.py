"""ADR 0001 §4 hook 2: a source-level pin that no collector module enumerates twice.

No `psutil.pids`, no `psutil.process_iter`, no `Get-Process`; exactly one call
site of `NtQuerySystemInformation(`. If a future change adds a second walk, this
test names the file.
"""

from __future__ import annotations

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "boostgauge"
COLLECTOR_SOURCES = [SRC / "collector.py", *sorted((SRC / "collectors").glob("*.py"))]

FORBIDDEN = ("psutil.pids", "process_iter", "Get-Process", "wmi", "WMI")


def _code_only(text: str) -> str:
    """Source with docstrings and comment lines removed.

    The module docstrings legitimately NAME `process_iter` and
    `NtQuerySystemInformation(...)` to explain the design; only code counts.
    """
    text = re.sub(r'"""[\s\S]*?"""', "", text)
    return "\n".join(line for line in text.splitlines()
                     if not line.lstrip().startswith("#"))


def _sources():
    return {p.relative_to(SRC.parent).as_posix(): _code_only(p.read_text(encoding="utf-8"))
            for p in COLLECTOR_SOURCES}


def test_collector_sources_exist():
    names = set(_sources())
    assert "boostgauge/collector.py" in names
    assert "boostgauge/collectors/windows.py" in names


def test_no_second_enumeration_anywhere():
    offenders = [f"{name}: {token}"
                 for name, code in _sources().items()
                 for token in FORBIDDEN if token in code]
    assert offenders == [], f"a second enumeration path is present: {offenders}"


def test_exactly_one_nt_query_call_site():
    call_sites = {name: len(re.findall(r"\bquery\(|NtQuerySystemInformation\(", code))
                  for name, code in _sources().items()}
    # windows.py: the bound function is invoked once, inside nt_sweep's loop
    assert call_sites["boostgauge/collectors/windows.py"] == 1, call_sites
    assert sum(call_sites.values()) == 1, call_sites
