"""The mandated baseline flag exists and defaults off (ruling #271).

`docs/design/0001-test-strategy.md` §3 binds the visual-regression workflow
to `pytest --generate-baselines`, and ruling #262 makes baselines
self-generated from the first accepted render. The flag was mandated by the
binding doc while nothing registered it: pytest rejected the argument, and
any test reading the option raised. The spec reviewer caught it during
run-issue1-014959 — "an unregistered pytest CLI flag that will crash the
test runner" — after it had silently made every conforming spec unrunnable.

These tests are the reason it cannot regress: the doc mandating a flag is
not the same as the flag existing.
"""
from __future__ import annotations

import pytest


def test_the_flag_is_registered(request) -> None:
    """The call the strategy doc's workflow depends on must not raise."""
    assert request.config.getoption("--generate-baselines") in (True, False)


def test_the_flag_defaults_to_off(request) -> None:
    """A missing baseline stays a hard failure unless a human asks otherwise.

    Were the default True, an ordinary run would write baselines for itself
    and every visual test would pass by construction, comparing a render
    against a copy of itself.

    Skipped when the suite is itself invoked with the flag — in that run the
    option is legitimately True, and the default is what this pins.
    """
    if request.config.getoption("--generate-baselines"):
        pytest.skip("invoked with --generate-baselines; the default is unobservable here")
    assert request.config.getoption("--generate-baselines") is False


def test_the_strategy_doc_and_the_registration_agree() -> None:
    """§3 names where the flag lives; if it moves, this fails."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    strategy = (root / "docs" / "design" / "0001-test-strategy.md").read_text(
        encoding="utf-8"
    )
    conftest = (root / "tests" / "conftest.py").read_text(encoding="utf-8")

    assert "--generate-baselines" in strategy
    assert "tests/conftest.py" in strategy, (
        "§3 must name where the flag is registered"
    )
    assert "pytest_addoption" in conftest
    assert '"--generate-baselines"' in conftest
