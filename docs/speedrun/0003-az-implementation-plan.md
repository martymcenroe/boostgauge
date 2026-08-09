# 0003 — AssemblyZero Implementation Plan (12 issues backing the speed-run)

**Status:** Plan document (no execution started).
**Last updated:** 2026-05-09
**Driver:** boostgauge speed-run readiness. All 12 issues filed during the 2026-05-09 audit pass + scope discussion.
**Companion docs:** `0001-route-v1.md` (archived), `0002-route-v2.md` (operational route), audit-results `0001` and `0002`.

---

## 1. Context

The boostgauge speed-run (zero-to-PyPI in one continuous take, target ≤42 attempts) requires AssemblyZero hardening across four areas:

1. **PyPI publishing pipeline** — AZ has no notion of "publish to PyPI" today.
2. **Resilience under transient failures** — current workflow halts on any Gemini 503 / quota / stagnation.
3. **Visual verification** — boostgauge is a GUI; AZ has no skill for "does this look right."
4. **Reproducibility & instrumentation** — speed-runs need lap splits, failure classifiers, and reset scripts.

Plus governance debt the audit surfaced (4 missing standards) and one meta-deliverable (readiness audit runbook for the NEXT repo onboarding).

All 12 issues live as open backlog in AZ (`gh issue list --repo martymcenroe/AssemblyZero --state open --search "1065..1076"`).

---

## 2. Issue inventory

| # | Title | Type | Effort | Speed-run criticality |
|---|---|---|---|---|
| 1065 | standard: 0018 — Issue Spec Quality Checklist | Doc | 30-60 min | Doc; backs #1069 |
| 1066 | standard: 0019 — LLD Mechanical Validation Criteria | Doc | 30-60 min | Doc |
| 1067 | standard: 0020 — Test Plan Quality Criteria | Doc | 30-60 min | Doc |
| 1068 | standard: 0021 — Workflow Error Recovery Procedures | Doc | 60-90 min | Doc; backs #1070 |
| 1069 | feat: `/pre-flight-check` skill | Skill (markdown) | 45-60 min | Helpful, not blocking |
| 1070 | feat: `/workflow-status` skill | Skill (markdown) | 45-60 min | Helpful for halts during runs |
| 1071 | **feat: workflow auto-retry with backoff** | Code (workflow nodes) | 2-4 hr | **CRITICAL PATH** |
| 1072 | feat: testing workflow — BLOCKED test plan recovery | Code (workflow graph) | 1-2 hr | High-value (workaround: `--auto`) |
| 1073 | feat: runbook 0933 + `/readiness-audit` skill | Doc + skill | 2-3 hr | Future-onboarding; low for THIS demo |
| 1074 | **feat: PyPI publishing pipeline** | Code (`new_repo_setup.py` + `release.yml` + runbook 0934) | 3-4 hr | **CRITICAL PATH** |
| 1075 | **feat: `/visual-verify` skill** | Skill (markdown) v1 | 45-60 min | **CRITICAL PATH** |
| 1076 | **feat: speed-run instrumentation** | Code (4 deliverables) | 4-6 hr | **CRITICAL PATH** |

**Critical-path total: 4 issues, ~10-15 hours of focused work.**
**Full backlog total: 12 issues, ~18-30 hours including review cycles + merge overhead.**

---

## 3. Dependencies

```
#1065 ─────────────────► #1069 (/pre-flight-check uses standard 0018)
                                │
#1066 ──┐                       │
#1067 ──┤                       │
        │                       ▼
#1071 ────► #1068 ──────► #1070 (/workflow-status uses standard 0021)
              │
              │
#1072 ────────┘ (independent but better after error-recovery std)

#1074 (PyPI) — independent, no AZ deps
#1075 (/visual-verify v1) — independent, no AZ deps
#1076 (instrumentation) — independent, no AZ deps; SHARES FILES with #1071

#1073 (readiness audit) — last; references all above
```

Real coupling concerns:
- **#1071 ↔ #1076.** Both modify `assemblyzero/workflows/{requirements,testing}/nodes/*`. Ship sequentially to avoid merge conflicts. Recommend #1071 first (smaller surface).
- **#1072 ↔ #1071.** #1072 modifies the workflow graph; #1071 wraps node calls. They could collide. Ship #1071 first; #1072 second.

Everything else is parallel-safe.

---

## 4. Recommended phased sequencing

### Phase A — Foundations (parallel, no file conflicts)

Ship in any order or in parallel:

- **#1065** standard 0018 (`docs/standards/0018-issue-spec-quality.md`) — pure doc.
- **#1066** standard 0019 (`docs/standards/0019-lld-mechanical-validation.md`) — pure doc; lift criteria from `assemblyzero/workflows/requirements/nodes/validate_mechanical.py`.
- **#1067** standard 0020 (`docs/standards/0020-test-plan-quality.md`) — pure doc; lift criteria from the Gemini test-plan-review prompt.
- **#1075** `/visual-verify` skill v1 (`.claude/commands/visual-verify.md`) — markdown skill.
- **#1074** PyPI pipeline — `tools/new_repo_setup.py` extension + `release.yml` template + `docs/runbooks/0934-pypi-trusted-publisher-setup.md`.

**Phase A can ship as 5 parallel PRs. ~6-9 hours of focused work.**

### Phase B — Workflow resilience (sequential due to file overlap)

Ship in this order:

1. **#1071** auto-retry with backoff — wraps N1 (drafter) + N3 (reviewer) + N4 (implementer) with retry/backoff. New module `assemblyzero/utils/retry.py` plus decorator/wrapper integration.
2. **#1076** speed-run instrumentation — 4 deliverables in one PR (or split if convenient): lap splits hooked into existing nodes, failure-mode classifier on HALT, `tools/speedrun_reset.py`, `data/speedrun/run-log.jsonl` writer.
3. **#1072** testing workflow BLOCKED recovery — adds `N1_revise_test_plan` node + `--test-plan-policy` flag.

**Phase B is 3 sequential PRs. ~7-12 hours of focused work.**

### Phase C — Standards + skills that depend on Phase B

- **#1068** standard 0021 (`docs/standards/0021-workflow-error-recovery.md`) — references the auto-retry from #1071 and the failure classifier from #1076.
- **#1069** `/pre-flight-check` skill (`.claude/commands/pre-flight-check.md`) — implements standard 0018 (#1065).
- **#1070** `/workflow-status` skill (`.claude/commands/workflow-status.md`) — interprets lineage trail; references standard 0021 (#1068).

**Phase C is 3 parallel PRs. ~3-4 hours of focused work.**

### Phase D — Meta deliverable (last)

- **#1073** runbook 0933 + `/readiness-audit` skill — references all preceding standards and skills. Documents the "next repo onboarding" methodology.

**Phase D is 1 PR. ~2-3 hours.**

---

## 5. Per-issue acceptance + verification

Each issue's filed body has full acceptance criteria. Quick reference:

| # | Verify by |
|---|---|
| 1065 | New file at `docs/standards/0018-issue-spec-quality.md`; 5-7 dimensions documented; 3 example issues classified. |
| 1066 | New file `docs/standards/0019-...`; every check in `validate_mechanical.py` documented. |
| 1067 | New file `docs/standards/0020-...`; criteria from Gemini test-plan-review prompt lifted. |
| 1068 | New file `docs/standards/0021-...`; 5 failure modes covered with command-level recovery examples. |
| 1069 | `.claude/commands/pre-flight-check.md` exists; manual test against well-formed issue returns PROCEED, against research issue returns WRONG WORKFLOW. |
| 1070 | `.claude/commands/workflow-status.md` exists; tested against a halted workflow (manual or fixture). |
| 1071 | New module `assemblyzero/utils/retry.py`; tests inject 503 → workflow recovers; `--retry-policy` flag works. |
| 1072 | New `N1_revise_test_plan` node; tests cover revise-success, revise-exhaust, strict-mode unchanged. |
| 1073 | `docs/runbooks/0933-...md` exists; `.claude/commands/readiness-audit.md` exists; manual run produces audit pair. |
| 1074 | `new_repo_setup.py` extension produces repo with `release.yml` + entry point + URLs; tag push triggers publish; runbook 0934 covers the browser step. |
| 1075 | `.claude/commands/visual-verify.md` exists; tested against a sample image. |
| 1076 | Lap splits file written by both workflows; reset script restores spawn state on a fresh repo; run log writes one entry per attempt. |

---

## 6. Risk callouts

### 6.1. Phase A is mostly parallel — but has one tricky one

**#1074 (PyPI pipeline)** modifies `tools/new_repo_setup.py`, which was just heavily edited (#1058, #1059, #1061, #1063). The next session needs to re-read the current state of that file before extending. Some of the structural choices made in #1058 (e.g., `--lang` flag pattern) inform how #1074's `--no-pypi` flag should be added.

### 6.2. Phase B sequencing is non-negotiable

#1071 + #1076 + #1072 all touch workflow node files. Concurrent PRs WILL conflict. Ship sequentially with clean rebases.

### 6.3. Test infrastructure for #1071 + #1072

These workflow-graph changes need integration-style tests that mock the LLM client. AZ's existing test harness has fixtures for this (look at `tests/test_audit_deferred_scope.py` for the mock pattern; reuse). If this gets unwieldy, consider filing a smaller follow-up to add a `tests/fixtures/mock_llm.py` helper.

### 6.4. #1073 has soft dependencies on everything

Don't ship #1073 until phases A-C are stable. Otherwise the runbook references in #1073 will be incorrect. Ship #1073 LAST.

### 6.5. Effort estimates assume agent-driven implementation

Each effort estimate (e.g., "2-4 hr") assumes Claude doing the work via the standard PR cycle. Operator review + decision time is not included. Add ~30 min per PR for human review.

### 6.6. Speed-run-blocking subset is FOUR issues

If time pressure hits, the minimum viable subset for the speed-run is:
1. **#1074** (PyPI pipeline) — without it, no publishing.
2. **#1075** (`/visual-verify`) — without it, no gauge gate in phase 2.
3. **#1076** (instrumentation) — without it, no reproducibility.
4. **#1071** (auto-retry) — without it, every transient halt kills the take.

These 4 alone are ~10-15 hours. Everything else (8 issues) is doc/skill polish that improves the workflow but doesn't gate the demo.

---

## 7. Total effort estimate

| Phase | Issues | PRs | Focused work | Wall (incl. reviews) |
|---|---|---|---|---|
| A | 5 | 5 | 6-9 hr | 8-12 hr |
| B | 3 | 3 | 7-12 hr | 9-15 hr |
| C | 3 | 3 | 3-4 hr | 4-6 hr |
| D | 1 | 1 | 2-3 hr | 3-4 hr |
| **Total** | **12** | **12** | **18-28 hr** | **24-37 hr** |

Across multi-day stretches with operator reviews, realistic completion: **~5-8 working days** at ~4 hr/day of focused agent work plus reviews.

For just the **critical 4** (#1071, #1074, #1075, #1076): **~12-18 hr focused, ~2-3 days**.

---

## 8. Open decisions before execution

These don't block planning but affect how an executor agent should interpret ambiguity:

1. **Standards house style.** Are AZ standards written in a particular voice (decision-focused, narrative, prescriptive)? Look at existing `docs/standards/0001-0017` for the convention before drafting #1065-1068.
2. **Skill v1 vs. v2.** #1069, #1070, #1075 are markdown-only skills in this plan. Future iterations could add Python wrappers for batch invocation. Default: ship markdown v1; defer Python wrapping unless the skill volume warrants it.
3. **#1076 split decision.** Speed-run instrumentation is 4 deliverables (lap splits, classifier, reset, run log). One PR vs. four PRs is a granularity call. Default: one PR for cohesion; split if any sub-deliverable hits scope creep.
4. **#1074 PyPI Trusted Publisher.** The browser-only step on PyPI's side is not automatable. Runbook 0934 documents it. The first repo using the new pipeline will need this configured manually before the first tag push works.
5. **Backwards compatibility on #1059/#1060 changes to `.unleashed.json`.** Old repos still have `assemblyZero: false` and `pickupThresholdMinutes: 10`. A fleet-rollout script could backfill — out of scope here, file separately if desired.

---

## 9. Pickup notes for the next session

Anyone resuming this plan should:

1. **Read this doc first** (`0003-az-implementation-plan.md`) plus `0002-route-v2.md` for the speed-run context.
2. **Verify state:** `gh issue list --repo martymcenroe/AssemblyZero --state open --search "1065..1076"` should return all 12.
3. **Start with Phase A.** Pick the lowest-overhead doc-only issues (#1065, #1066, #1067) first to build momentum and confirm the standards house style.
4. **Run each PR through the standard cycle** documented in root `CLAUDE.md` § Merging PRs (Universal): poll `mergeable_state` until `clean`, squash-merge, ff-merge main locally, delete branch, prune.
5. **Track progress in this doc.** Update §4's Phase tables with ✓ as items land. Future-you needs to see which issues are done without checking GitHub.
6. **Phase B is the riskiest** — three workflow-touching PRs in series. If a halt happens mid-phase-B, the conflict resolution gets ugly. Stop, ask, re-plan.
7. **Don't ship #1073 early.** It references everything; ship it last when Phases A-C are stable.

---

## 10. References

- AZ issues: #1065, #1066, #1067, #1068, #1069, #1070, #1071, #1072, #1073, #1074, #1075, #1076 (all open at plan time).
- Speed-run route: `docs/speedrun/0002-route-v2.md`.
- Audit findings: `docs/audit-results/0001-...md`, `docs/audit-results/0002-...md`.
- Boostgauge prep issues: #31, #32, #33, #36 (separate track; speed-run prep, not AZ work).
- Boostgauge open decisions: #34 closed; #35 / #25 / #3 housekeeping pending.
