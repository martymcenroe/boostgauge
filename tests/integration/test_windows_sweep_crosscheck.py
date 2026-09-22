"""ADR 0001 §4 hook 3: the one-call sweep cross-checked against psutil, live.

A wrong struct offset in the `SYSTEM_PROCESS_INFORMATION` parse would miscount
silently, so the real sweep is checked against psutil's independent enumeration
on the running machine.

The two cannot be sampled at the same instant, and they are not even the same
KIND of measurement. The sweep is a single `NtQuerySystemInformation` call, of
the order of a millisecond. psutil's walk opens every process to read its handle
count and takes hundreds of times longer, so the oracle is smeared across its
own window: its first process is counted at one moment and its last at another.
On a machine running several concurrent sessions, churn inside that window
routinely exceeds one process.

Comparing two point samples with a ±1 band was this test's original shape, and
it failed about one run in three (#458). The band was not too tight; the
comparison was the wrong shape — a quantity smeared over an interval was being
held to a single endpoint of it.

So the sweep now BRACKETS the oracle: sweep, oracle, sweep. The oracle must fall
inside the interval the two sweeps span, widened by the slack below. That checks
the smeared quantity against the range it was smeared over.

Detection power is unchanged, which is the point. A wrong struct offset moves
BOTH bracketing sweeps the same way, so the oracle lands outside the interval by
a wide margin. The bracket absorbs churn, not error.

A wide bracket must never become a way to accept a wrong answer, so when the
bracket grows past `INCONCLUSIVE_FRACTION` of the count the machine moved too
much for this comparison to discriminate, and the attempt is retried rather than
passed. If every attempt is inconclusive the test SKIPS and reports what it
measured. It never passes on churn and never fails on it.

psutil's enumeration is used HERE, in a test, as the independent oracle. It
is forbidden in the collector (tests/unit/test_collector_source_pin.py).
"""

from __future__ import annotations

import sys

import psutil
import pytest
from _pytest.outcomes import Failed

from boostgauge.collectors.windows import CONSOLE_HOSTS, WindowsCollector

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows sweep")


def _psutil_oracle():
    rows = conpty = handles = 0
    for p in psutil.process_iter(attrs=["name", "num_handles"], ad_value=None):
        rows += 1
        if (p.info["name"] or "").lower() in CONSOLE_HOSTS:
            conpty += 1
        handles += p.info["num_handles"] or 0
    return rows, conpty, handles


ATTEMPTS = 5

# Slack added outside the bracket. Even two instantaneous enumerations differ by
# a process, so one row and one console host are free; the handle total gets the
# same 1 % this test has always used.
ROW_SLACK = 1
CONPTY_SLACK = 1
HANDLE_SLACK_FRACTION = 0.01

# Above this bracket width, relative to the count, the two sweeps disagree so
# much that the interval would swallow a genuinely wrong answer. Such a sample
# proves nothing and is retried rather than passed.
INCONCLUSIVE_FRACTION = 0.10


def _sweep_counts(collector):
    """One sweep, reduced to the three totals plus the raw rows."""
    rows = collector.nt_sweep()
    return (
        len(rows),
        sum(1 for r in rows if r.name in CONSOLE_HOSTS),
        sum(r.handle_count for r in rows),
        rows,
    )


def _brackets(before, after, observed, slack):
    """Does `observed` lie within [min, max] of the two sweeps, plus slack?"""
    return min(before, after) - slack <= observed <= max(before, after) + slack


def _too_wide(before, after, fraction):
    """Is the bracket so wide it could no longer discriminate?"""
    scale = max(before, after, 1)
    return abs(after - before) > fraction * scale


def test_sweep_matches_psutil_on_this_machine():
    collector = WindowsCollector()
    inconclusive = []
    misses = []

    for _attempt in range(ATTEMPTS):
        b_rows, b_conpty, b_handles, rows = _sweep_counts(collector)
        o_rows, o_conpty, o_handles = _psutil_oracle()
        a_rows, a_conpty, a_handles, _ = _sweep_counts(collector)

        # A sample taken while the machine heaved tells us nothing either way.
        if (_too_wide(b_rows, a_rows, INCONCLUSIVE_FRACTION)
                or _too_wide(b_handles, a_handles, INCONCLUSIVE_FRACTION)):
            inconclusive.append(
                (abs(a_rows - b_rows), abs(a_handles - b_handles))
            )
            continue

        if (_brackets(b_rows, a_rows, o_rows, ROW_SLACK)
                and _brackets(b_conpty, a_conpty, o_conpty, CONPTY_SLACK)
                and _brackets(b_handles, a_handles, o_handles,
                              HANDLE_SLACK_FRACTION * max(o_handles, 1))):
            break

        # Out of bracket on a quiet sample. Not yet a verdict: a process born
        # and reaped entirely inside the oracle's walk is invisible to both
        # bracketing sweeps, which can miss by more than the slack even with a
        # zero-width bracket. A struct-offset defect misses EVERY attempt, so
        # the verdict waits for all of them.
        misses.append(
            f"rows [{b_rows},{a_rows}] vs {o_rows}; "
            f"conpty [{b_conpty},{a_conpty}] vs {o_conpty}; "
            f"handles [{b_handles},{a_handles}] vs {o_handles}"
        )
    else:
        if misses:
            pytest.fail(
                f"sweep failed to bracket psutil on all {len(misses)} quiet "
                "sample(s) — a consistent miss is the struct-offset signal, "
                "not churn.\n  " + "\n  ".join(misses)
            )
        pytest.skip(
            f"machine too busy to compare across {ATTEMPTS} attempts; every "
            f"bracket exceeded {INCONCLUSIVE_FRACTION:.0%} of the count. "
            f"(row, handle) widths: {inconclusive}"
        )

    assert b_rows > 20                      # a real machine, not an empty parse
    assert any(r.name == "system" for r in rows)   # pid 4 is always there
    # The sweep reads rows psutil cannot open, so its handle total is a floor.
    assert b_handles >= o_handles * (1 - HANDLE_SLACK_FRACTION)


def test_the_crosscheck_still_catches_a_miscount(monkeypatch):
    """The bracket must absorb churn without absorbing error.

    Widening a tolerance to stop a flake is the easy repair and the wrong one,
    because the failure it silences is the only thing the test was for. #458
    replaced a point comparison with a bracket, which is strictly more
    permissive, so the permissiveness needs a bound in the suite rather than in
    a commit message.

    This feeds the cross-check a sweep that silently drops rows — the exact
    shape of the `SYSTEM_PROCESS_INFORMATION` offset defect the module docstring
    names — and requires a FAIL. A skip is not acceptable either: it would mean
    the miscount was written off as churn.
    """
    real_sweep = WindowsCollector.nt_sweep
    dropped = 40

    def undercounting_sweep(self):
        rows = real_sweep(self)
        assert len(rows) > dropped, "machine too small for this fixture"
        return rows[:-dropped]

    monkeypatch.setattr(WindowsCollector, "nt_sweep", undercounting_sweep)

    with pytest.raises(Failed) as caught:
        test_sweep_matches_psutil_on_this_machine()

    assert "struct-offset signal" in str(caught.value)
