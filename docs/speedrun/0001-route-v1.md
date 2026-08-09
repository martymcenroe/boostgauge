# Speed-Run Route v1 — boostgauge zero-to-PyPI

**Status:** Draft (placeholders pending issue triage; see §11)
**Last updated:** 2026-05-09
**Win condition:** YouTube video → X post → stars on AssemblyZero GitHub
**Run budget:** ≤42 attempts (per user, 2026-05-09)

---

## 1. Mission

A single continuous recording from "boostgauge has zero source code on `main`" to "package is live on PyPI, the launched app is visible, the wiki page exists, the landing page exists." Edited in post for YouTube — speed-up of long thinking phases, voiceover narration added later, lap splits as overlay.

The video is marketing for AssemblyZero. The artifact is a stars-on-AZ-GitHub conversion event. boostgauge is the demonstration vehicle.

---

## 2. Recording surfaces

| Pane | Content | Purpose |
|---|---|---|
| Primary | Console (Git Bash / PowerShell) | Where AZ workflow commands run. Where the operator sees output. The "speed-run timer" pane. |
| Secondary | Claude Code session window | Where the agent does the actual workflow execution. Provides the visual interest during long thinking phases. |
| Optional | Browser | At the closing shot — PyPI page + GitHub repo + the launched app side-by-side. |

The console is the canonical surface; AZ workflows must run end-to-end from a plain console without Claude Code being mandatory. (Claude Code is recording-time visual interest, not a runtime dependency.)

---

## 3. Spawn state — what's true before pressing record

### 3.1. AZ side (pinned)

- AZ pinned to a specific commit. Tag the commit (`speedrun-v1`) so attempts replay against an identical AZ.
- All filed standards (#1065-1068) and skills (#1069, #1070, #1075) at v1 quality. Not perfect — speed-run-good-enough.
- `tools/speedrun_reset.py` (#1076 deliverable) installed and tested.
- `tools/speedrun_overlay.py` produces the lap-split JSON the post-production step consumes.

### 3.2. boostgauge side (clean)

- `git status --short` returns empty (boostgauge #31).
- No stale remote branches (boostgauge #31).
- `pyproject.toml` + `poetry.lock` + `tests/conftest.py` committed (boostgauge #32).
- `auto-reviewer.yml` deployed and Cerberus secrets verified (boostgauge #33).
- Issue triage complete (boostgauge #34): every open issue labeled `lld-ready` / `lld-needs-revision` / `wrong-workflow`.
- The 5–6 demo issues (TBD — see §11) authored or verified `lld-ready`.
- `release.yml` deployed (after AZ #1074 ships).
- PyPI Trusted Publisher configured for `martymcenroe/boostgauge` (one-time browser step per AZ #1074 runbook).
- GitHub repo wiki enabled, with a placeholder `Home.md`.
- Landing page setup: TBD (GitHub Pages on `main`/`docs` branch? Cloudflare Worker? — see §11).

### 3.3. Operator side

- Recording software tested (OBS / equivalent). Audio levels OK if narrating. Resolution + font-size legible at YouTube 1080p compression.
- Off-camera dry runs completed:
  - **Minimum:** 2 successful end-to-end dry runs.
  - **Recommended:** 5+ dry runs to establish best-time baseline.
  - **Sanity gate:** the most recent dry run was within the last 24 hours and used the same AZ pinned commit.
- Reset between attempts: `poetry run python tools/speedrun_reset.py --repo /c/Users/mcwiz/Projects/boostgauge` (idempotent; per AZ #1076).
- Run log entry started for this attempt.

---

## 4. The route — beat by beat

This is a placeholder route assuming **5 features** + final publish. Will be refined once boostgauge issue triage (#34) names the specific features.

### Phase 0 — Prologue (0:00 → 0:30)

- Show `gh issue list --repo martymcenroe/boostgauge --label lld-ready --state open`.
- Show `git -C boostgauge log --oneline -3` — confirm zero source code on main.
- (Voiceover in post: "We're going to ship a Python package on PyPI from zero code, end to end, in one continuous run.")

### Phase 1 — Feature A (0:30 → ~10:00)

**Issue: TBD-A** — smallest pure-logic feature. Likely candidate: Telltale (boostgauge #35 once authored).

```bash
cd /c/Users/mcwiz/Projects/AssemblyZero
PYTHONUNBUFFERED=1 poetry run python tools/run_requirements_workflow.py \
    --type lld --issue {A} --repo /c/Users/mcwiz/Projects/boostgauge --yes
```

**Lap splits (target):**
- `lld_drafted` — t+90s
- `lld_approved` — t+150s

```bash
PYTHONUNBUFFERED=1 poetry run python tools/run_implement_from_lld.py \
    --issue {A} --repo /c/Users/mcwiz/Projects/boostgauge
```

**Lap splits (target):**
- `red_phase_passed` — t+120s after impl start
- `green_phase_passed` — t+250s after impl start
- `pr_merged` — t+340s after impl start

### Phase 2 — Feature B (~10:00 → ~22:00)

**Issue: TBD-B** — second small feature. Likely candidate: config loader.

(Same template as Phase 1.)

### Phase 3 — Feature C (~22:00 → ~38:00)

**Issue: TBD-C** — data collector. Larger feature; expect longer LLD + impl phases.

### Phase 4 — Feature D (~38:00 → ~55:00)

**Issue: TBD-D** — gauge renderer. The visual centerpiece. Visual-verify (AZ #1075) gate runs here.

### Phase 5 — Feature E (~55:00 → ~75:00)

**Issue: TBD-E** — main entry / app integration. Wires features A-D into a launchable program.

### Phase 6 — Publish (~75:00 → ~95:00)

```bash
cd /c/Users/mcwiz/Projects/boostgauge
git tag v0.1.0
git push origin v0.1.0
# release.yml triggers; OIDC auth to PyPI; poetry build + poetry publish
```

**Lap splits (target):**
- `tag_pushed` — t+5s
- `pypi_published` — t+45s

### Phase 7 — Verify + closing (~95:00 → ~110:00)

```bash
# Fresh venv install smoke
python -m venv /tmp/boostgauge-smoke
/tmp/boostgauge-smoke/Scripts/activate
pip install boostgauge
boostgauge   # window opens; tachometer renders
```

**Closing shot:** browser tabs side-by-side — PyPI package page + GitHub repo + launched app window.

(Voiceover in post: "Total wall-clock: NN minutes. Star AssemblyZero on GitHub if you want to see how it works.")

**Estimated total raw recording: ~110 minutes. Edited to YouTube: ~12-18 minutes.**

---

## 5. Lap split targets (cumulative from t=0)

Each split is a `(beat, t_seconds)` pair written to `data/speedrun/{attempt}.json` by AZ #1076.

| Beat | Cumulative target |
|---|---|
| `attempt_started` | 0:00 |
| `feature_A_lld_approved` | 2:30 |
| `feature_A_pr_merged` | 8:00 |
| `feature_B_pr_merged` | 18:00 |
| `feature_C_pr_merged` | 32:00 |
| `feature_D_pr_merged` | 50:00 |
| `feature_E_pr_merged` | 70:00 |
| `tag_pushed` | 75:00 |
| `pypi_published` | 76:00 |
| `install_smoke_passed` | 80:00 |
| `app_launched` | 81:00 |
| `attempt_complete` | 85:00 |

**Run is "clean" if all splits within 1.2× of target.** Run is "great" if all within 1.0× of target.

---

## 6. Known halts and recovery routes

When something halts on camera, the operator does ONE of:

1. **Cut + re-shoot from spawn state** (default for take-1 through ~take-30). Reset, re-press record. Lose the take.
2. **Show recovery on camera** (only for the right kinds of halts on later takes). Some halts can be turned into demos of AZ's resilience. Use sparingly.
3. **Splice in B-roll** (post-production). Pre-record successful runs of each phase; if take dies in phase 4, splice in the phase 4 B-roll.

Per known failure mode:

| Failure | Detection | On-camera recovery story | Off-camera recovery |
|---|---|---|---|
| Gemini 503/529 | Reviewer timeout, status code logged | Wait + show `/workflow-status` + run `--resume-review` | After AZ #1071 (auto-retry), automatic. Cut take if not auto-recovered within 60s. |
| Two-strike stagnation | N3 HALT after same-blocking-issues twice | Show the verdict, manual edit, resume | Cut take. The LLD needs work; do it off-camera. |
| Mech-validation max-iterations | N1.5 hit max | Show validator error, manual fix to LLD | Cut take. |
| Test plan BLOCKED | Implementation N1 returned BLOCKED | Run `--auto` flag (after AZ #1072 ships, the recovery node handles this) | Pre-AZ-#1072: cut take; revise LLD test plan. |
| Coverage target missed | N5 ran but coverage < target | Show why; edit test or accept lower coverage with `--coverage-target` flag | Cut take. |
| PR check blocked (Cerberus didn't approve) | `mergeable_state: blocked` after pr-sentinel passed | Show secret config, redeploy if needed | Spawn-state should have caught this. Hard cut. |
| Visual verify FAIL on the renderer | AZ #1075 returns FAIL | Show the verdict, iterate the LLD or impl | Cut take. The renderer needs work. |
| PyPI publish failed | release.yml workflow failed | Show the error, fix forward | Almost always a config issue. Cut take; fix Trusted Publisher config off-camera. |

---

## 7. Reset procedure between attempts

```bash
# Run from anywhere — script knows the boostgauge path.
cd /c/Users/mcwiz/Projects/AssemblyZero
poetry run python tools/speedrun_reset.py \
    --repo /c/Users/mcwiz/Projects/boostgauge \
    --all-issues   # resets every demo issue, not just one
```

Verifies "spawn state restored" (idempotent). Adds a row to the run log via AZ #1076.

---

## 8. Take-acceptance criteria

A take is **accepted** for YouTube post-production iff:

- [ ] All lap splits hit (within 1.2× target).
- [ ] No halts that required cuts visible in the recording.
- [ ] PyPI publish succeeded; `pip install boostgauge` works in a fresh venv.
- [ ] App launches and renders something recognizable.
- [ ] Visual-verify (#1075) passes on the final rendered gauge.
- [ ] Total raw runtime ≤ 130 minutes.
- [ ] Recording quality acceptable (audio, video, terminal legibility).

A take is **provisional** (could be salvaged with B-roll splicing) if:

- [ ] Two or fewer recoverable halts, each with B-roll available.
- [ ] One missed split off by < 2× target.

A take is **rejected** if:

- More than two halts; OR
- A halt without B-roll coverage; OR
- App fails to launch on `pip install`; OR
- Recording quality unusable.

---

## 9. Run log

`data/speedrun/run-log.jsonl` (per AZ #1076). One entry per attempt:

```json
{"attempt": N, "started_at": "...", "ended_at": "...", "outcome": "accepted|provisional|rejected", "splits_met": 12, "splits_missed": 0, "failure_mode": null, "notes": "..."}
```

Review the log between attempts to identify systematic issues. Specifically:
- Same failure mode 3+ times → file an AZ issue or fix the spec.
- Same beat consistently slow → optimize the spec for that beat.
- Split N consistently fast → great; that's a real improvement.

---

## 10. Recording / post-production notes

### 10.1. During recording

- Recording starts BEFORE the first `gh issue list`. Capture the spawn state visibly.
- Capture both panes (console + Claude Code session) at native resolution.
- Console font ≥ 14pt for YouTube legibility.
- Wall-clock visible somewhere (system clock, OBS overlay, or `tools/speedrun_overlay.py` output).

### 10.2. Post-production checklist

- Speed up Gemini-thinking phases to 4-8x.
- Speed up `poetry install` and similar long-running stdlib commands to 4-8x.
- KEEP at 1x: PR creation, merge, PyPI publish, install smoke. These are the dramatic beats.
- Add lap-split overlay (read from `data/speedrun/{attempt}.json`).
- Add voiceover (your voice, eventually voice-cloned per the user's roadmap).
- Title cards at phase boundaries.
- Closing call to action: "Star AssemblyZero on GitHub" with the URL on screen for ≥ 5 seconds.

### 10.3. Distribution

- YouTube upload with timestamps in description (linking to each phase).
- X post with the YouTube link + a 30-second teaser clip + the GitHub repo URL.
- Pin the X post to the profile.

---

## 11. Open decisions (need user input before route v2)

These are placeholder-shaped in v1 and need to be locked before the off-camera dry runs start.

### 11.1. Which 5–6 features for the demo arc?

Depends on boostgauge issue triage (boostgauge #34) being done. Candidate ordering:

1. Telltale peak-hold needle (boostgauge #35, to be authored) — small, pure logic.
2. Config loader — small, pure logic.
3. Windows data collector (boostgauge #4) — mid-sized, has acceptance criteria.
4. Gauge renderer — visual centerpiece. Needs LLD authoring; current issues are fragments.
5. Main entry / app integration — wires it together.

User decision: lock this list, including the EXACT issue numbers/titles.

### 11.2. Landing page approach

Options:
- GitHub Pages on `main`/`docs/` (zero infra).
- Cloudflare Worker on `boostgauge.dev` or similar (matches AZ pattern).
- Deferred (just rely on GitHub repo README).

### 11.3. Visual reference for the gauge

User mentioned (2026-05-09): generate a target gauge image via Nano Banana / Gemini 3 Image as the spec input, then visual-verify against it. Marked "far down the road" — but for the speed-run, having a reference image makes the visual-verify gate produce stable verdicts. Filing as a future enhancement under AZ #1075. Consider whether to include in v1 of the speed-run or defer to v2.

### 11.4. Wiki content source

The closing shot mentions "the wiki page exists." What goes on it? Options:
- Auto-generated from the README.
- Authored as a separate prep task before recording.
- Skipped for v1.

### 11.5. Voice cloning timeline

User mentioned ~6 months. For v1 of the route, narration is silent recording + post-edited voiceover (operator's natural voice). Voice clone integration goes in route v2 if and when it's ready.

---

## 12. Versioning

- v1 (this doc): structure + placeholders. Drafted 2026-05-09 from the speed-run scope discussion.
- v2: feature list locked + landing page + wiki decisions made. Filed as a follow-up issue once #34 (issue triage) is done.
- v3+: each significant change to the route after a take that revealed something.

---

## 13. References

- Boostgauge readiness audit 0001 (config gaps): `docs/audit-results/0001-assemblyzero-workflow-readiness-2026-05-09.md`.
- Boostgauge readiness audit 0002 (deeper, spec/standards/skills gaps): `docs/audit-results/0002-assemblyzero-deeper-readiness-2026-05-09.md`.
- AZ issues backing this route: #1065-#1076 (standards, skills, instrumentation, PyPI pipeline, visual verify).
- Boostgauge prep issues: #31 (cleanup), #32 (Python bootstrap), #33 (Cerberus + workflows), #34 (issue triage), #35 (Telltale demo issue), #36 (test strategy).
