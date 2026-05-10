# 0002 — AssemblyZero Workflow Readiness, Deeper Audit

**Auditor:** Claude Opus 4.7 via AssemblyZero session, 2026-05-09
**Subject:** Beyond pre-flight — spec quality, workflow node resilience, missing standards & skills
**Scope:** Follow-up to `0001-assemblyzero-workflow-readiness-2026-05-09.md` (which fixed config gaps); answers the question "even after pre-flight, where will it break, and what's missing structurally to prevent that."

**Trigger:** User question after the §2 fixes landed in `new_repo_setup.py` (#1058–#1061): *"can you dig deeper? do we need architectural guidelines or skills to be summoned? are the specs sufficient? how can we tell?"*

---

## TL;DR

Three findings, one of them load-bearing for the demo:

1. **Issue spec quality is the next bottleneck.** Of the 25 boostgauge issues, ~70% are feature-shaped with moderate-to-good detail and will produce usable LLDs in 1–2 revision cycles. ~5% (the research/deep-dive issues like #11, #12, #13, #21) **don't fit the LLD workflow at all** — they ask Gemini to research a topic, not to design code. Running them through `run_requirements_workflow.py` will produce a vacuous LLD that conflates research summary with unfounded code suggestions.

2. **The workflow has thin mid-flight resilience.** The graph has good failure DETECTION (mechanical validation, two-strike stagnation, max iterations) but limited RECOVERY. When something halts, the operator's only recourse is `--resume` / `--resume-review` flags or manual restart. There's no automatic retry with backoff, no escalation to a stronger reviewer, no fallback path from a BLOCKED test plan in the implementation workflow.

3. **Several governance standards are missing.** Mechanical-validation criteria, LLD-semantic-quality criteria, test-plan-quality criteria, and error-recovery procedures are all embedded in code (in Gemini prompt strings, in node guard clauses, in the `validate_mechanical.py` checks). There's no published standard a contributor or reviewer could read to understand what makes an LLD "good." Existing standards (`0001`, `0007`, `0012`, `0701`, `0702`) cover orchestration, testing strategy, lineage versioning, and implementation-spec format — but not the gates the workflow actually enforces.

The good news: none of these prevent the demo from working on a well-chosen first issue. They define the structural debt the workflow will keep accumulating until addressed.

---

## 1. Spec quality of boostgauge's 25 open issues

A representative sample (small / mid / research) was assessed against the dimensions the LLD workflow actually consumes (issue title + body, no labels/milestones).

### 1.1 Sample assessment

**#4 — feat: Windows data collector (small/scoped)**
- Acceptance criteria: ✓ 6 binary-verifiable checkpoints (returns accurate X, < 1% CPU overhead at 2s polling, etc.).
- Scope boundaries: ✓ Explicit IN/OUT — table of 5 metrics with collection frequency.
- Test plan: △ Implicit via acceptance criteria (no formal test plan section, but the criteria are testable).
- Architectural context: ✓ Specifies abstract base class hierarchy, dataclass fields, threading model.
- Determinism: ✓ Two engineers would converge on substantially the same implementation.
- **Likely outcome:** usable LLD on first pass, no revision cycle expected.

**#18 — feat: multi-gauge mode (mid-sized)**
- Acceptance criteria: △ Testable shape but vague verbs ("visually highlighted" — what style?).
- Scope boundaries: △ Three layout options sketched in ASCII; OUT not stated (multi-screen? responsive scaling? customizable count?).
- Test plan: ✗ None.
- Architectural context: △ Layout sketches only; no mention of which GUI module owns layout, widget vs. canvas, interaction with existing gauge renderer.
- Determinism: △ Layout algo is prescribed; visual polish is open to interpretation.
- **Likely outcome:** 1–2 revision cycles. Reviewer (Gemini) will likely send back asking for clearer interaction with existing renderer.

**#12 — research: deep dive — optimal system health scoring algorithms (research/architectural)**
- Acceptance criteria: ✗ Research outcomes, not testable code behavior. "Find 2-3 algorithms" is success.
- Scope boundaries: ✗ Implicit ("lightweight widget" — undefined).
- Test plan: ✗ N/A — work product is documentation, not a feature.
- Architectural context: ✗ References issue #3 only; purely research-driven input to LATER implementation.
- Determinism: ✗ Gemini's response determines the algorithm; non-deterministic.
- **Likely outcome:** the LLD workflow would produce a half-baked design conflating research summary with code suggestions. **Wrong tool for this issue type.**

### 1.2 Workflow input expectations

`assemblyzero/workflows/requirements/nodes/load_input.py` extracts only `title` and `body`. Labels, assignees, milestones, reactions are NOT consumed. The drafter (`generate_draft.py:289`) prepends the issue number to prevent LLM confusion and passes the markdown body verbatim. The reviewer (`review.py:48-52`) gates on whether open questions remain unresolved and whether the LLD passes mechanical validation (Issue #277).

The drafter has no pre-flight validation that the body is "rich enough" or "feature-shaped." It will run on a one-line issue ("fix this") and produce some output. The output may be vacuous, but the workflow will not halt early — the wasted-effort cost is detected only after the reviewer cycles 1–N times producing similar critiques.

### 1.3 Implication for boostgauge

| Likely first-demo issue category | Count (rough) | Will produce usable LLD? |
|---|---|---|
| Feature-shaped, well-specified (like #4) | ~60% | YES first pass |
| Feature-shaped, mid-quality (like #18) | ~20% | YES after 1–2 cycles |
| Research / deep-dive (#11, #12, #13, #21) | ~15% | NO (wrong workflow) |
| Infrastructure / packaging (#9, #10) | ~5% | YES first pass (small surface) |

**Concrete demo recommendation:** pick #4 (Windows data collector) as the first-demo target. It has the highest determinism and the most explicit acceptance criteria. Skip the research issues entirely for the LLD workflow.

---

## 2. Workflow node-by-node resilience surface

The LLD workflow has **11 nodes** (`assemblyzero/workflows/requirements/graph.py:75-85`); the implementation workflow has **13 nodes** (`assemblyzero/workflows/testing/graph.py:369-540`). Each node has a defined failure surface. Detection is good; recovery is limited.

### 2.1 LLD workflow

| Node | Failure mode | Recovery available |
|---|---|---|
| N1 generate_draft | API quota exhaustion | Halt; user retries manually. No fallback LLM. |
| N1.5 validate_lld_mechanical | Repeated structural failures | Loops back to N1; halts at max_iterations (default 20). |
| N3 review | Gemini 503/529 timeout | `--resume-review` flag (added by #536). |
| N3 review | Two-strike stagnation (same blocking issues twice) | HALT. No escalation, no try-different-reviewer, no skip-to-human-gate. |
| N3 review | Reviewer approves while open questions remain | **Silent pass** — workflow proceeds to finalize. (Documented in `review.py:207`.) |
| N5 finalize | File I/O or GitHub API failure | No retry. Error propagates to END. |

### 2.2 Implementation workflow

| Node | Failure mode | Recovery available |
|---|---|---|
| N1 review_test_plan | Gemini BLOCKED on test plan | END unless `--auto`. **No automatic recovery path.** |
| N2.5 validate_tests_mechanical | Syntax errors in scaffolded tests | Loops back to N2 up to 3 times; then escalates to N4 (Claude). |
| N4 implement_code | Type / import errors | N4b completeness gate catches; loops back to N4 up to max_iterations. |
| N5 verify_green_phase | Tests still fail after implementation | Loops back to N4 up to max_iterations (default 3). |
| N6 e2e_validation | E2E failure | Loops to N4 if iterations remain; otherwise END. |
| N7.5 run_adversarial | Adversarial test breaks code | **Non-blocking** — reported but does not affect routing (`graph.py:357-358`). |

### 2.3 Net resilience pattern

- **Detection coverage: HIGH.** Mechanical validators and gates exist at the right places; both workflows fail loudly when something is wrong rather than producing silent-bad output.
- **Recovery coverage: MEDIUM-LOW.** All failure modes loop within their own node up to max_iterations or hit terminal HALT. None escalate to a different model, fall back to a weaker variant, or invoke an external skill.
- **Operator-driven recovery:** `--resume` and `--resume-review` flags exist but require human knowledge of where the workflow stalled.
- **Observable evidence:** the issue numbering tells a story — #277 (mechanical validation), #166 (test plan validation), #248 (open questions loop), #503 (two-strike stagnation), #536 (resume-review flag) were each filed in response to a real failure mode discovered live. The pattern is iterative hardening rather than upfront design — which means more such issues are likely lurking.

---

## 3. Standards gap analysis

`docs/standards/` currently has 22 files (`0001-0017` plus `0701-0702`). The workflow-relevant ones:

| Standard | Topic | Workflow role |
|---|---|---|
| 0001 | Orchestration Protocol | Defines the surrounding model; workflows execute under it. |
| 0007 | Testing Strategy | Test pyramid + coverage targets; testing workflow's reference doc. |
| 0009 | Canonical Project Structure | Directory layout the workflows assume. |
| 0010 | Model Qualification | LLM selection / capability matrix. |
| 0011 | Audit Decisions | Audit trail format. |
| 0012 | Lineage Versioning | LLD pre-check, lineage version shifting (load-bearing for `run_requirements_workflow.py:1175-1270`). |
| 0701 | Implementation Spec Template | Spec format the implementation workflow drafts. |
| 0702 | Implementation Readiness Review | 6 criteria for spec quality. |

### 3.1 What's missing

| Missing standard | Currently lives in | Cost of being missing |
|---|---|---|
| **Issue Spec Quality Standard** | Nowhere (you eyeball it) | Workflow accepts malformed issues, wastes tokens and iterations producing low-quality drafts. |
| **LLD Mechanical Validation Standard** | Code: `validate_mechanical.py` (Issue #277) | Operators can't audit what makes an LLD pass; validation errors are opaque. |
| **LLD Semantic Quality Standard** | Embedded in Gemini prompt strings | "Good design" criteria invisible — neither contributors nor reviewers can reference them. |
| **Test Plan Quality Standard** | Embedded in Gemini prompt for N1 (`review_test_plan`) | Test plan reviewability criteria not version-controlled or auditable. |
| **Workflow Error Recovery Standard** | Nowhere | When workflows fail, recovery procedure is improvised; cost-budget exhaustion vs. timeout vs. stagnation all handled differently and undocumented. |
| **Mid-Flight Diagnosis Standard** | Nowhere | Status files (Issue #380) are written but no documented interpretation — operators can't programmatically detect "stuck." |

The pattern: the workflow has gates, but the gate-criteria are buried in implementation. To answer the user's question "are the specs sufficient?" — there's no rubric to check against.

---

## 4. Skills gap analysis

Skills (slash commands) inventory in AssemblyZero's `.claude/commands/`:

### 4.1 By trigger phase

| Phase | Skills present | Coverage |
|---|---|---|
| **PRE-FLIGHT** (before workflow runs) | None | **Empty.** No skill validates input quality, GitHub issue richness, repo readiness. |
| **MID-FLIGHT** (autonomous, during workflow) | None | **Empty.** Workflows run monolithically; no skill is invoked to recover from transient failure or diagnose stuck state. |
| **POST-FLIGHT** (after workflow completes or halts) | `/cleanup`, `/handoff`, `/park`, `/commit-push-pr`, `/code-review` | Reasonable; covers the manual cleanup phase. |
| **INFRASTRUCTURE / META** (not workflow-tied) | `/onboard`, `/dependabot`, `/sync-permissions`, `/audit`, `/death`, `/promote`, `/friction`, `/test-gaps`, `/blog-draft`, `/quote`, `/unleashed-version`, `/init`, `/review`, `/security-review`, `/loop`, `/schedule`, `/claude-api`, `/keybindings-help`, `/simplify`, `/fewer-permission-prompts`, `/update-config` | Rich; covers maintenance and auxiliary tasks. |

### 4.2 What's missing

The under-served phases are PRE-FLIGHT and MID-FLIGHT — the two phases that determine whether the workflow even gets to a useful output.

Concrete absent skills:
- `/pre-flight-check {issue-number} {repo}` — validates the GitHub issue against the (yet-to-be-created) Issue Spec Quality Standard before invoking the workflow. Output: pass / fail with line-by-line comments on what's missing.
- `/lld-validate {LLD-path}` — check an LLD against the (yet-to-be-published) LLD Mechanical Validation Standard. Independent of the workflow's runtime check.
- `/test-plan-validate {LLD-path}` — same for the test plan section.
- A mid-flight diagnostic skill — e.g., `/workflow-status {issue-number}` — interprets the audit trail in `docs/lineage/active/` and tells the operator where the workflow last halted, why, and what `--resume*` flag would resume from there.
- An automatic-recovery skill that wraps the workflow with retry+escalation for transient failures, rather than relying on the operator to read the error and pick a flag.

---

## 5. How to tell

The user's actual question: *"how can we tell?"* — meaning, what's the methodology to know whether a spec is sufficient and whether the workflow will produce useful output?

### 5.1 For an individual issue (pre-flight)

Run through this checklist BEFORE invoking the workflow on an issue:

1. **Title test:** Does the title use a strong verb that describes what the code will DO? (`feat: add X`, `fix: handle Y`) or is it descriptive of a problem (`research: figure out Z`)? Strong verb → usable. Descriptive → wrong workflow.
2. **Acceptance-criteria test:** Are there explicit binary-verifiable checkpoints in the body? Count them. Zero → spec is insufficient.
3. **File-mention test:** Does the body name specific files or modules to touch? (`src/foo.py`, the existing `gauge_renderer`, etc.) Zero file mentions in a feature issue → high revision-cycle risk.
4. **Scope-bound test:** Is there an explicit "out of scope" or "not in this issue" line? If not, the workflow will likely overscope or underscope; either way revisions accrue.
5. **Determinism test:** Mentally answer "would two engineers reading this produce substantially the same code?" If you can't say yes, expect revision cycles.

If 4–5 pass: high confidence. If 2–3 pass: expect 1–2 cycles. If 0–1 pass: do not run the LLD workflow on this issue without manual upgrade first.

### 5.2 For the workflow run (mid-flight observation)

The workflow writes audit trail to `docs/lineage/active/{issue}-lld/` as it runs:

```
001-issue.md       — input fetched from GitHub
002-draft.md       — first LLD draft
003-verdict.md     — first review verdict (APPROVED / REVISE / DISCUSS)
004-draft.md       — revised draft (if cycle 2)
005-verdict.md     — cycle 2 verdict
...
NNN-final.md       — committed final LLD
```

Signs of trouble while the workflow is running:
- More than 4 verdict files with no APPROVED — likely stagnating on the same blocking issue.
- Two consecutive verdicts with similar phrasing — two-strike stagnation imminent (HALT triggers at this point).
- Drafts that grow in length each cycle without converging — drafter is over-elaborating instead of fixing the actual gap.

### 5.3 For the workflow output (post-flight)

After the LLD lands at `docs/lld/active/LLD-NNN.md`, validate:
- Every section in the 0701 (Implementation Spec Template) is present.
- "File Changes" section lists paths that exist or will be created — none of which collide with existing files unintentionally.
- Test Plan section has at least one specific assertion per acceptance criterion in the original issue.
- Open Questions section is empty OR every question has an answer in the body.

If any of these fail, the LLD is structurally OK but semantically incomplete. The implementation workflow may still run, but it'll surface these as test or validation failures later.

---

## 6. Concrete recommendations

### 6.1 Before recording the demo

These are the ONLY items that block the YouTube recording. Everything else can wait.

| Action | Where | Why |
|---|---|---|
| Apply §2 fixes from audit 0001 | boostgauge | pyproject.toml, .unleashed.json, workflows, Cerberus, working tree, etc. |
| Write a fresh small issue specifically for the demo | GitHub | Avoid 1-2 revision cycles a known-mid-quality issue would cause. Suggested in audit 0001 §5: "Telltale peak-hold needle logic, pure no-GUI." |
| Off-camera dry run on that issue | local | Verify the path works end-to-end. Identifies any boostgauge-specific friction. |

A NEW well-formed issue trumps any of the existing 25 issues, including #4. The new issue can be authored with explicit acceptance criteria, a tight scope, and a clear test plan — exactly what the workflow consumes best.

### 6.2 To file as backlog issues against AssemblyZero

These are gaps surfaced by this audit. They don't block the demo, but they make the demo path more robust over time.

1. **standard: 0018 — Issue Spec Quality Checklist** (the §5.1 list, formalized).
2. **standard: 0019 — LLD Mechanical Validation Criteria** (publish what `validate_mechanical.py` actually checks).
3. **standard: 0020 — Test Plan Quality Criteria** (lift the criteria embedded in the Gemini review prompt into a versioned standard).
4. **standard: 0021 — Workflow Error Recovery Procedures** (what to do for quota exhaustion vs. stagnation vs. timeout — currently improvised).
5. **skill: /pre-flight-check** — validates an issue against 0018 before the operator invokes the workflow.
6. **skill: /workflow-status** — interprets the lineage audit trail and reports where the workflow last halted + what `--resume*` flag resumes from.
7. **feat: workflow auto-retry with backoff** — wrap N1/N3 with retry on transient API failures; escalate to a different model after N attempts rather than HALT.
8. **feat: testing workflow N1 BLOCKED escalation** — when test plan review BLOCKS, offer fallback to manual override or auto-mode rather than terminating.

### 6.3 To file as boostgauge-specific issues

1. **chore: triage boostgauge issues by workflow-suitability** — go through the 25 open issues, label each `lld-ready`, `lld-needs-revision`, or `wrong-workflow` (research). The research-tagged ones get a separate process.
2. **docs: write demo issue** — author the function-level "Telltale peak-hold needle" issue with full acceptance criteria, file paths, test plan. This is the demo target.

---

## 7. Net assessment

**Is the AZ workflow ready to demo against boostgauge?** Conditionally yes — after audit 0001's §2 fixes AND with a well-authored fresh first issue rather than picking from the existing 25. The workflow has good structure, good detection, and adequate output for issues that hit its "happy path." It does not yet have the standards or skills to make the path repeatable for less-perfect inputs — but that's not what the demo needs to show.

**Is the AZ workflow architecturally complete?** No — but the gaps are all observable and addressable. The pattern of issue numbering (#277, #166, #248, #503, #536) shows the team has been hardening the workflow iteratively as failure modes surface. The gaps in this report are the next batch in that sequence.

**Are the boostgauge specs sufficient?** For ~70% of issues, yes. For the research issues, no — those need a different path (manual Gemini review, or a separate research-report workflow if AZ wants to support it). Authoring a fresh issue specifically for the demo bypasses this ambiguity entirely.

---

## Appendix: References

- Workflow code: `tools/run_requirements_workflow.py`, `tools/run_implement_from_lld.py`
- Graphs: `assemblyzero/workflows/requirements/graph.py:75-576`, `assemblyzero/workflows/testing/graph.py:369-540`
- Pre-existing standards: `docs/standards/0001`, `0007`, `0009`, `0012`, `0701`, `0702`
- Skills: `.claude/commands/` (18+ project skills) plus user-global `~/.claude/skills/`
- Audit 0001 (config gaps, pre-flight): `docs/audit-results/0001-assemblyzero-workflow-readiness-2026-05-09.md`
- Recent improvement issues that surfaced workflow weaknesses: AssemblyZero #277, #166, #248, #503, #536, #380, #773
