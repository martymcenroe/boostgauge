# 0001 — AssemblyZero Workflow Readiness Audit

**Auditor:** Claude Opus 4.7 via AssemblyZero session, 2026-05-09
**Subject:** `martymcenroe/boostgauge` running the AssemblyZero LLD + implementation workflows
**Trigger:** User wants to record a verbose demo session on YouTube; preflight check before pressing record.

---

## TL;DR

**The repo will fail within the first 90 seconds of either workflow.** The failure modes are clearly identified below and almost all are pre-flight fixable in under an hour. Two are structural (missing `pyproject.toml`, no test runner installed) and would be live on camera within the first phase. After fixing the items in §2 (Critical), there is a reasonable chance of recording a clean run on a small, well-scoped first issue.

**Recommended posture:** do NOT press record until §2 is green. Items in §3 will degrade quality but not crash the workflow. Items in §4 are polish.

The repo is greenfield (4 commits, zero source code, 25 queued issues, no tests, no CI). That's actually a good blank slate — there's no pre-existing technical debt to navigate. But "blank slate" also means **the workflow has nothing to bootstrap from** until you give it a runnable Python project.

---

## 1. State of play

| Surface | Status | Evidence |
|---|---|---|
| Repo bootstrapped via `new_repo_setup.py` | ✓ | commit `b1f9885 chore: initialize project with AssemblyZero` |
| `CLAUDE.md` + `GEMINI.md` present | ✓ | 113 + 47 lines respectively |
| `.unleashed.json` present | ✓ but `assemblyZero: false` |
| Security hooks deployed | ✓ | 3 hooks in `.claude/hooks/` |
| `docs/lld/active/`, `docs/lld/done/`, `docs/reports/active/` scaffolded | ✓ | empty `.gitkeep` files only |
| `src/` and `tools/` scaffolded | ✓ | empty |
| `tests/` scaffolded across 12 test categories | ✓ | empty (no conftest, no tests) |
| 25 open issues queued | ✓ | full feature roadmap |
| `pyproject.toml` declaring Python deps | ✗ | **no dependency manifest in repo** |
| Test framework wired up | ✗ | no pytest config, no installed runner |
| GitHub Actions workflows | ✗ | removed in `e1528b7 chore: remove workflows (PAT lacks workflow scope)` |
| Branch protection on `main` | ✗ (or unreadable) | API returns 403 |
| Cerberus secrets (auto-reviewer) | ? | PAT can't read; likely absent given workflow removal |
| Issue labels for AZ workflow gates | ✗ | only default GitHub labels (`bug`, `documentation`, etc.) |
| Gemini credentials | ✓ (assumed) | user has run `audit_deferred_scope` successfully today, same path |
| Working tree clean | ✗ | 1 modified file (`GEMINI.md`), 4 untracked items |
| Stale remote branches | ✗ | `26-cleanup-security-hooks`, `fix/remove-model-override` both abandoned |

---

## 2. Critical pre-flight blocks (FIX BEFORE RECORDING)

These cause the workflow to fail in the first phase. Each has a concrete fix.

### 2.1. No `pyproject.toml` → implementation workflow cannot run pytest

**The blocker.** AssemblyZero's implementation workflow (`tools/run_implement_from_lld.py`) is TDD-driven: red phase runs `pytest` against new tests, green phase runs `pytest --cov` to measure coverage. The boostgauge repo has zero Python dependency declaration — no `pyproject.toml`, no `setup.py`, no `requirements.txt`. There is no installed test runner, no virtual environment.

**On-camera failure:** Around 60-90 seconds in, after the LLD is loaded and the workflow tries to scaffold tests, you'll see something like:
```
[red phase] running: pytest tests/unit/test_foo.py
FileNotFoundError: pytest
```

**Fix (under 15 minutes):**

```bash
cd /c/Users/mcwiz/Projects/boostgauge

# Initialize a Poetry project. Use Python 3.10+ to match CLAUDE.md tech stack.
poetry init --name boostgauge \
  --python "^3.10" \
  --description "Real-time system monitor styled like a racing tachometer" \
  --license MIT \
  --no-interaction

# Add the runtime dependencies declared in CLAUDE.md.
poetry add psutil pillow pystray
# tkinter is stdlib on Windows, no add needed.

# Add dev dependencies — pytest + coverage are mandatory for AZ workflow.
poetry add --group dev pytest pytest-cov

# Verify the venv installs cleanly.
poetry install
poetry run pytest --version
```

After this, commit `pyproject.toml` and `poetry.lock`. The implementation workflow will now find a real test runner.

### 2.2. No `conftest.py` or pytest config → test discovery may find zero tests

Even with pytest installed, the boostgauge `tests/` directory has 12 sub-categories (`unit/`, `integration/`, `e2e/`, `compliance/`, `accessibility/`, `benchmark/`, `contract/`, `harness/`, `security/`, `smoke/`, `visual/`, `fixtures/`) and no `conftest.py`. Default pytest discovery rules will find tests, but the workflow's red-phase gate (`assemblyzero/workflows/testing/nodes/verify_red_phase.py`) expects collected tests to fail.

**Fix (under 5 minutes):**

```bash
# In pyproject.toml, add a [tool.pytest.ini_options] section.
```

Append to `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-ra --strict-markers"
```

This makes test discovery deterministic across the 12 sub-dirs.

### 2.3. No GitHub Actions workflows → no CI gate, no Cerberus auto-approve

The `e1528b7` commit removed all `.github/workflows/` because the PAT in use lacked `workflow` scope. Result: no CI runs on PRs, no `auto-reviewer.yml` to authenticate Cerberus, and likely no Cerberus secrets configured either.

**Consequence on camera:** when the implementation workflow finishes and you try `gh pr merge --squash`, the PR will be in `mergeable_state: blocked` (no required check has passed). You'd be stuck on camera with nothing to do.

**Fix (under 30 minutes, requires the classic-PAT flow):**

This is the path documented in runbook `docs/runbooks/0927-new-repo-human-checklist.md` in AssemblyZero. Two parts:

1. **Re-run `tools/new_repo_setup.py` in audit mode** to redeploy `auto-reviewer.yml` via the in-process classic PAT (Contents API path; doesn't need fine-grained-PAT `workflow` scope). Or, simpler: copy a known-good `auto-reviewer.yml` from another martymcenroe repo (e.g., `Talos`, `unleashed`) and ship it via Contents API using `tools/_pat_session.classic_pat_session()` per ADR-0216.

2. **Deploy Cerberus secrets:**
```bash
# Generate .pem at https://github.com/settings/apps/cerberus-az
poetry run python /c/Users/mcwiz/Projects/AssemblyZero/tools/deploy_cerberus_secrets.py \
    /c/Users/mcwiz/Downloads/cerberus-az.<datestamp>.private-key.pem
# Then revoke the .pem in browser and rm the local file.
```

Without this, every PR will require you to manually approve via the GitHub UI — workable for the demo, but ugly on camera.

**Alternate (faster, uglier):** disable branch protection's "1 approving review" requirement for the demo by setting it to 0 reviews required. Lets PRs merge without Cerberus. Re-enable after recording. Requires admin scope on the PAT — same scope problem that started this whole pickle.

### 2.4. Working tree is dirty → worktree creation will surface the mess

The implementation workflow creates `boostgauge-{issue_number}` as a sibling worktree from `main`. `git worktree add` from a dirty branch is technically allowed, but the modified `GEMINI.md` and 4 untracked items will appear in the worktree's status output and pollute the demo.

**Fix (under 2 minutes):**

```bash
cd /c/Users/mcwiz/Projects/boostgauge
git -C . status --short
# Decide which to commit, which to delete, which to gitignore.
# Likely actions:
#   git add GEMINI.md docs/session-logs/2026-03-19.md
#   git commit -m "docs: pre-demo cleanup"
#   echo "blueprint/" >> .gitignore     # OR commit it
#   rm docs/unleashed-restart-handoff.md  # if obsolete
git push origin main
```

### 2.5. Stale remote branches → `git fetch` output is noisy

Branches `26-cleanup-security-hooks` and `fix/remove-model-override` exist on origin and are not on main. They show up in `git branch -a` and pollute any prune output.

**Fix (under 1 minute):**

```bash
gh api -X DELETE repos/martymcenroe/boostgauge/git/refs/heads/26-cleanup-security-hooks
gh api -X DELETE repos/martymcenroe/boostgauge/git/refs/heads/fix/remove-model-override
git -C /c/Users/mcwiz/Projects/boostgauge fetch --prune origin
```

If these branches reflect unfinished work, transfer the work to a fresh issue first.

### 2.6. `.unleashed.json` has `assemblyZero: false`

The current `.unleashed.json`:
```json
{
  "profile": "default",
  "claude": {"effort": "max"},
  "assemblyZero": false,
  "onboard": {
    "auto": true,
    "pickupThresholdMinutes": 10,
    "guide": null,
    "plan": null
  }
}
```

`assemblyZero: false` tells the `/onboard` skill not to read AssemblyZero's CLAUDE.md when a session starts here. For demo purposes you probably want this `true` so when you `/onboard` in the boostgauge directory, the agent has full AZ rule context.

`pickupThresholdMinutes: 10` is a deprecated field per the latest `/onboard` skill (pickup is event-ordered now). Not a blocker; just noise.

**Fix (under 1 minute):**

Edit to:
```json
{
  "profile": "default",
  "claude": {"effort": "max"},
  "assemblyZero": true,
  "onboard": {
    "auto": true,
    "guide": null,
    "plan": null
  }
}
```

---

## 3. Soft blocks (will degrade quality but not crash)

These don't stop the workflow but produce noisy or incorrect output that's awkward on camera.

### 3.1. No issue labels relevant to AZ workflow

GitHub repo has only the default labels (`bug`, `documentation`, `duplicate`, `enhancement`, `good first issue`, `help wanted`, `invalid`, `question`, `wontfix`). The LLD workflow doesn't strictly require labels but downstream tools (governance gates, classification) may expect labels like `lld-approved`, `governance-passed`, etc.

**Optional fix (under 5 minutes):**

```bash
gh label create lld-needed --color FFA500 --description "Has GitHub issue, needs LLD" --repo martymcenroe/boostgauge
gh label create lld-approved --color 28A745 --description "LLD reviewed and approved" --repo martymcenroe/boostgauge
gh label create implementation --color 0E8A16 --description "Implementation in progress" --repo martymcenroe/boostgauge
```

### 3.2. No `docs/standards/` or `docs/runbooks/` content

Both directories are scaffolded with `.gitkeep` only. AssemblyZero's `analyze_codebase` node reads these for project conventions to feed into the LLD draft. Boostgauge has none, so the LLD draft will be generic Python rather than tuned to the project's tachometer-rendering vocabulary.

This is OK — the LLD will still be valid — but the LLD won't reference any project-specific conventions because there are none to reference.

### 3.3. No `pyproject.toml` poetry venv → `analyze_codebase` may produce empty deps section

Same root cause as 2.1. Even after fixing 2.1, the `analyze_codebase` node runs early in the LLD workflow; the first run may have a thin "Dependencies" section in the LLD because there's no installed history yet. Acceptable, but worth knowing.

### 3.4. Empty `src/` → first LLD's "File Changes" section will all be additions

Every LLD will have only `Add` operations, no `Modify`. Not a problem, just visual.

### 3.5. `docs/00003-file-inventory.md` has wrong number prefix

AZ uses 4-digit numeric prefixes (`0003-`). This file has 5 digits (`00003-`). Either rename or delete; otherwise audits looking for `0003-file-inventory.md` won't find it.

```bash
git mv docs/00003-file-inventory.md docs/0003-file-inventory.md
# (verify content is still relevant; if obsolete, just delete)
```

### 3.6. `blueprint/` directory is non-canonical

Contains JSON dumps from issue planning (`issues.json`, `architectural-constraint-issues.json`, etc.). Doesn't match any AZ standard. Will get inventoried as "uncategorized" by any audit run. Either: (a) move into `docs/blueprint/` to bring it under `docs/`, or (b) commit + add to `.gitignore` if it's meant to be local-only.

### 3.7. `docs/unleashed-restart-handoff.md` is one-off transition cruft

If obsolete, delete it. Otherwise move it under `docs/handoffs/` or similar.

---

## 4. Optional polish (post-demo)

- `docs/adrs/` is empty. After the first feature lands, write an ADR-0001 capturing the "logic vs visuals decoupling" decision (per blueprint architectural constraints).
- `docs/lineage/` is empty. The first LLD workflow run will populate `docs/lineage/active/{issue}-lld/`.
- `tools/` is empty. As the project grows, project-specific tools land here (e.g., `tools/render_gauge_test_image.py`).
- `tests/visual/` is scaffolded. Visual diff tests for the gauge renderer will eventually land here.

---

## 5. Recommended demo approach

### Pick a small first issue

Of the 25 open issues, the demo benefits from picking a SMALL, BOUNDED feature. Avoid the full-GUI features (#1-#8 likely span the whole tachometer rendering). Look for:

- **A pure-logic feature** (no GUI) — testable headlessly. Example candidates from the blueprint architectural constraints: telltale peak-hold logic, time-window decay calculations, abstract data collector interface.
- **A small utility** — config loading, log rotation, etc.
- **A small Win32 wrapper** — single ConPTY allocation counter; small surface area.

Open issues #11, #12, #13, #21 are research/deep-dive issues; skip those. Issues #1-#8 are likely too big for one demo. Issue #9 (CI/CD) is plumbing — could itself be a fine demo, but conflicts with §2.3 above. Issue #10 (packaging) is too late-stage for a first demo.

**Suggested pick:** create a NEW small issue specifically for the demo. Title: `feat: add Telltale peak-hold needle logic (pure, no GUI)`. Body: 2-3 sentences describing the math (current value comes in; needle drops slowly back from the peak unless a new higher value resets it). Acceptance: 100% test coverage, no GUI dependency. This is the cleanest possible demo target — it's a function-level feature with deterministic tests.

### Demo cadence

Phase 1 (LLD workflow): ~5-15 minutes wall. The Gemini reviewer + Claude drafter iterate ~5-10 times. Cost: $0.50-$2.00 in tokens.

Phase 2 (implementation workflow): ~20-45 minutes wall. Red phase, green phase, refactor, coverage check. Cost: $1.00-$4.00 in tokens.

Phase 3 (PR + merge): ~5 minutes wall. PR creation, branch-protection green, Cerberus auto-approves, you merge.

Total: 30-60 minutes of recording for one issue. **Editable in post.** Don't try to ship in real-time on first take.

### Off-camera dry run first

Before pressing record:

1. Apply all §2 fixes above.
2. Pick a small issue (or create one).
3. Run the LLD workflow: `cd /c/Users/mcwiz/Projects/AssemblyZero && poetry run python tools/run_requirements_workflow.py --type lld --issue {N} --repo /c/Users/mcwiz/Projects/boostgauge --yes`. Watch where it fails. Fix anything that crops up. Repeat until it produces an LLD without errors.
4. Run the implementation workflow: `cd /c/Users/mcwiz/Projects/AssemblyZero && PYTHONUNBUFFERED=1 poetry run python tools/run_implement_from_lld.py --issue {N} --repo /c/Users/mcwiz/Projects/boostgauge`. Same — fix and iterate until clean.
5. THEN delete the worktree, the branch, and the LLD/lineage artifacts. Reset to a clean state. **Now press record** and re-run the same workflow against the same issue. The cache is mostly cold (LLM calls re-execute), but you've already verified the path works.

This is the difference between "we'll figure it out on camera" and "we know it works; we just have to ride it." The user explicitly does not want the former.

---

## 6. Pre-flight checklist (paste this and check items off)

```
Pre-flight for AssemblyZero on boostgauge — 2026-05-09

§2 Critical:
[ ] 2.1 — pyproject.toml + poetry.lock committed, pytest installed
[ ] 2.2 — pyproject.toml has [tool.pytest.ini_options] block
[ ] 2.3 — auto-reviewer.yml deployed; Cerberus secrets verified
        (or: branch protection review-requirement temporarily lowered)
[ ] 2.4 — working tree clean (git status --short = empty)
[ ] 2.5 — stale remote branches deleted
[ ] 2.6 — .unleashed.json has assemblyZero: true; deprecated field removed

§3 Soft (recommended):
[ ] 3.1 — labels created: lld-needed, lld-approved, implementation
[ ] 3.5 — 00003-file-inventory.md renamed/deleted
[ ] 3.6 — blueprint/ moved into docs/ or gitignored
[ ] 3.7 — unleashed-restart-handoff.md deleted if obsolete

Pre-record dry run:
[ ] Off-camera LLD workflow succeeded for chosen issue
[ ] Off-camera implementation workflow succeeded for chosen issue
[ ] Off-camera PR opened, checks passed, merge succeeded
[ ] Worktree, branch, and lineage artifacts cleaned up to reset state
[ ] Tested camera/audio/screen capture
[ ] CLAUDECODE='' set; PYTHONUNBUFFERED=1 set in shell env
[ ] Disk space + battery + network all good
```

---

## 7. Honest assessment

**Realistic outcome with §2 done:** moderate confidence the LLD workflow runs to completion on a small first issue. Implementation workflow has more moving parts (worktree, pytest, coverage, PR creation) and is more likely to surface a surprise mid-flight.

**Realistic outcome without §2 done:** the workflow fails before producing useful output. Recording would be embarrassing rather than instructive.

**Realistic outcome with both §2 AND a successful off-camera dry run:** high confidence the on-camera run works because you've already proven the path on the same code, same workflow, same model.

**Estimated total time to readiness:** 1.5-3 hours (mostly §2.3 if you have to deploy Cerberus, plus the dry-run).

The user's instinct ("it won't work in 5 seconds") is correct as-is. After §2 + dry run, that flips: it most likely will.

---

## Appendix: Citations

For every claim about AZ assumptions, cite-paths to AssemblyZero source:
- LLD workflow entry: `tools/run_requirements_workflow.py`
- Implementation workflow entry: `tools/run_implement_from_lld.py`
- Required directories: `assemblyzero/workflows/requirements/audit.py:34-39` (`docs/lineage/active`, `docs/lld/active`, `docs/lld/done`, `docs/lld/lld-status.json`)
- Test runner expectation: `assemblyzero/workflows/testing/nodes/verify_red_phase.py`, `verify_green_phase.py`
- Worktree creation: `tools/run_implement_from_lld.py:101-163`
- Path validator: `assemblyzero/workflows/testing/path_validator.py`
- Standard 0009 (canonical structure): `docs/standards/0009-canonical-project-structure.md`
- Cerberus deploy: `tools/deploy_cerberus_secrets.py` + runbook `0927-new-repo-human-checklist.md`
- ADR-0216 (in-process PAT pattern): `docs/adrs/0216-in-process-classic-pat-decryption.md`
