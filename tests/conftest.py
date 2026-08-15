"""Project test bootstrap."""

from __future__ import annotations

import sys

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


def pytest_addoption(parser) -> None:
    """Register the baseline-regeneration flag (ruling #271).

    `docs/design/0001-test-strategy.md` §3 binds the visual-regression
    workflow to `pytest --generate-baselines`, and ruling #262 makes
    baselines self-generated from the first accepted render. Neither is
    performable unless the flag exists: pytest rejects an unregistered
    argument outright, and `request.config.getoption("--generate-baselines")`
    raises. The binding doc mandated a flag the repo never provided, which
    made every spec honouring §3 unrunnable.

    Default False, so a missing baseline stays a hard failure and no run
    silently accepts a render a human never looked at.
    """
    parser.addoption(
        "--generate-baselines",
        action="store_true",
        default=False,
        help=(
            "Write the rendered image as the visual-regression baseline for "
            "any test whose baseline is missing or failing. Human-in-the-loop "
            "by design: baselines never regenerate without this flag "
            "(test strategy 0001 §3)."
        ),
    )