# 136 — Implementation Report (Issue #36)

**Issue:** [#36 — docs/test: choose tkinter testing approach + design GUI render test strategy](https://github.com/martymcenroe/boostgauge/issues/36)
**Branch:** `36-test-strategy`
**Author:** Claude Opus 4.7 (1M context)
**Date:** 2026-05-11

## Summary

Authored `docs/design/0001-test-strategy.md` — the canonical test strategy for boostgauge. Locks in Option C (render to off-screen `PIL.Image`; tkinter Canvas is a display-only surface) as the load-bearing architectural constraint that keeps the test suite headless, fast, and stable on Windows.

## Decision: Option C

Option A (real `tkinter.Tk()` in tests) rejected on headless + Windows flakiness. Option B (mock the Canvas API) rejected because the gauge's correctness *is* its pixel output — a mocked Canvas silently passes when the renderer draws at the wrong coordinates. Option C splits responsibility cleanly: renderers produce a `PIL.Image`; tkinter Canvas displays the image via `PhotoImage`. Tests exercise the renderer; they never instantiate Tk.

This is now a load-bearing constraint enforced by §8 of the doc: any LLD proposing `tkinter.Tk()` in tests is rejected without further review.

## Changes

| File | Action | Description |
|---|---|---|
| `docs/design/0001-test-strategy.md` | Added | 8 sections — purpose, test pyramid, Tkinter mode decision, visual regression baseline, install smoke, E2E, CI integration, LLD reference rules. |

No source code changes. No test changes. This is a doc-only commit.

## Acceptance Status

| Acceptance criterion | Status | Evidence |
|---|---|---|
| `docs/design/0001-test-strategy.md` exists with all 6 sections from issue body | ✓ | All 6 covered: §1 Test Pyramid, §2 Tkinter Mode, §3 Visual Regression Baseline, §4 Install Smoke, §5 E2E Healthcheck, §6 CI Integration. (Plus §7 spike deferral note, §8 LLD reference rules.) |
| Spike commit exists: one example test per tier (unit, render-pixel, install-smoke, e2e), passing locally | **Deferred** | Filed as follow-up issue (see closing comment) — spikes need minimal stubs of renderer/package/app, none of which exist in the greenfield repo. Per Closing Discipline, follow-up issue is filed before #36 closes. |
| Strategy referenced from CLAUDE.md and from each future LLD's "Test Plan" section | **Forward-binding** | The doc itself (§8) defines the rule that all future LLDs MUST reference it and lists the rejection criteria for non-compliance. CLAUDE.md update is a follow-up touch — deferred so as not to bundle CLAUDE.md edits into this PR. |

## Deferred Scope

Two items deferred to follow-up issues (filed before #36 closes per Closing Discipline):

1. **Spike commits per tier** — filed as a new "test: spike commits per test-strategy 0001" issue.
2. **CLAUDE.md cross-reference** — a one-line edit pointing future LLDs at this doc. Will land with the first LLD that adopts this strategy (likely the LLD for #41).

## References

- Parent issue: #36
- Strategy applies to: every future LLD; #41 (Telltale) is the first real consumer
- Audit context: `docs/audit-results/0001-...` §3.5 (test framework decisions), AZ readiness audit 0002 §6.1
