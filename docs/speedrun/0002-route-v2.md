# Speed-Run Route v2 — boostgauge zero-to-PyPI

> **⚠️ SUPERSEDED 2026-05-22 by `0004-route-v3.md`.**
> v2 remains in the repo as historical reference — its feature arc (§5),
> lap splits (§6), and known-halts recovery table (§7) are still
> load-bearing references in v3. The reset procedure (§8) and the
> dry-runs section (§4.3) are obsolete; see v3 §8 and `feedback-speedrun-no-dry-runs`.

**Status:** SUPERSEDED — Operational draft (features locked; landing page + wiki content still open per §12.2 / §12.4)
**Last updated:** 2026-05-09
**Win condition:** YouTube video → X post → stars on AssemblyZero GitHub
**Run budget:** ≤42 attempts (per user, 2026-05-09)
**Supersedes:** `0001-route-v1.md` (v1 archived; structure preserved, placeholders resolved here)

---

## 1. Mission

A single continuous recording from "boostgauge has zero source code on `main`" to "package is live on PyPI, the launched app is visible, the wiki page exists." Edited in post for YouTube.

The video is marketing for AssemblyZero. The artifact is a stars-on-AZ-GitHub conversion event. boostgauge is the demonstration vehicle.

---

## 2. What changed v1 → v2

- **Feature arc locked.** v1 had `TBD-A` through `TBD-E`; v2 has #7 → #1 → #4 → #2 → #5.
- **Reordering.** Original arc put #2 (telltales) in phase 2. That had no visible output until phase 4 (gauge renderer). v2 puts #1 (gauge renderer) in phase 2 so a visible gauge appears within the first ~30 minutes of the recording.
- **Lap split targets calibrated.** v1's targets were placeholder; v2's are based on each feature's actual complexity (lld-ready vs. lld-needs-revision, size, integration depth).
- **"What's visible after this phase" column added.** Each phase now declares its demo-ammunition output.

---

## 3. Recording surfaces

| Pane | Content | Purpose |
|---|---|---|
| Primary | Console (Git Bash / PowerShell) | Where AZ workflow commands run. The "speed-run timer" pane. |
| Secondary | Claude Code session window | Where the agent does the workflow execution. Visual interest during long thinking phases. |
| Tertiary | Application window (after phase 2) | The visible boostgauge gauge — appears in phase 2, gets richer in phases 3-5. |
| Optional | Browser at finale | PyPI page + GitHub repo + launched app side-by-side. |

---

## 4. Spawn state — what's true before pressing record

### 4.1. AZ side (pinned)

- AZ pinned to a tagged commit (`speedrun-v1`, `speedrun-v2`, etc.).
- Standards #1065-1068, skills #1069/#1070/#1075, instrumentation #1076 at v1 quality (per backlog).
- `tools/speedrun_reset.py` (#1076) installed and tested.

### 4.2. boostgauge side (clean)

- All boostgauge prep issues closed: #31 cleanup, #32 Python bootstrap, #33 Cerberus + workflows, #36 test strategy.
- `release.yml` deployed (after AZ #1074 ships).
- PyPI Trusted Publisher configured for `martymcenroe/boostgauge`.
- Repo wiki enabled with placeholder Home.md.
- Landing page setup: TBD (§12.2).

### 4.3. Operator side

- Recording software tested. Audio levels OK. Font ≥ 14pt for 1080p compression.
- Off-camera dry runs:
  - **Minimum:** 2 successful end-to-end dry runs.
  - **Recommended:** 5+ dry runs to establish best-time baseline.
- Reset between attempts: `poetry run python tools/speedrun_reset.py --repo /c/Users/mcwiz/Projects/boostgauge --all-issues`
- Run log entry started for this attempt.

---

## 5. The route — beat by beat

### Phase 0 — Prologue (0:00 → 0:30)

```bash
gh issue list --repo martymcenroe/boostgauge --label lld-ready --state open
git -C /c/Users/mcwiz/Projects/boostgauge log --oneline -3
```

(Voiceover: "We're going to ship a Python package on PyPI from zero code, end-to-end, in one continuous run. Watch the timer.")

**Visible after this phase:** issue list + empty src/ tree.

### Phase 1 — #7 Configuration file (0:30 → ~12:00)

**Why first:** smallest, pure JSON, deterministic. Warmup with maximum determinism. Establishes the LLD → impl → merge cycle visibly.

```bash
cd /c/Users/mcwiz/Projects/AssemblyZero
PYTHONUNBUFFERED=1 poetry run python tools/run_requirements_workflow.py \
    --type lld --issue 7 --repo /c/Users/mcwiz/Projects/boostgauge --yes

PYTHONUNBUFFERED=1 poetry run python tools/run_implement_from_lld.py \
    --issue 7 --repo /c/Users/mcwiz/Projects/boostgauge
```

**Lap split targets (from start of phase):**
- `lld_approved` — t+150s
- `pr_merged` — t+9m

**Visible after this phase:** `src/boostgauge/config.py` exists; running a quick test script prints loaded JSON. **Not visually exciting.** Demo value: establishes the cycle works.

### Phase 2 — #1 Core gauge renderer (12:00 → ~42:00)

**Why second:** first visible artifact. A static gauge appears in a window. Hits the audience's first "ooh" moment within the first half of the video. Gates the `/visual-verify` skill (AZ #1075).

**Caveat:** `lld-needs-revision` — visual polish is subjective. Expect 1-2 review cycles. Budget +10 min vs. an `lld-ready` issue.

```bash
cd /c/Users/mcwiz/Projects/AssemblyZero
PYTHONUNBUFFERED=1 poetry run python tools/run_requirements_workflow.py \
    --type lld --issue 1 --repo /c/Users/mcwiz/Projects/boostgauge --yes

PYTHONUNBUFFERED=1 poetry run python tools/run_implement_from_lld.py \
    --issue 1 --repo /c/Users/mcwiz/Projects/boostgauge
```

After implementation, run a quick demo script to show the gauge:
```bash
cd /c/Users/mcwiz/Projects/boostgauge
poetry run python -c "from boostgauge.gauge import demo; demo(value=50)"
```

**Lap split targets:**
- `lld_approved` — t+8m (allows for 1-2 revision cycles)
- `pr_merged` — t+25m
- `gauge_window_visible` — t+27m (first time a gauge renders on screen)

**Visible after this phase:** **a static tachometer-style gauge in a window.** The needle is hardcoded at value 50 for now. **First visual milestone — capture this on screen for ≥10 seconds.**

### Phase 3 — #4 Windows data collector (42:00 → ~58:00)

**Why third:** lld-ready with the cleanest acceptance criteria of any boostgauge issue. Once shipped, wires the static gauge from phase 2 to live data. The needle moves.

```bash
cd /c/Users/mcwiz/Projects/AssemblyZero
PYTHONUNBUFFERED=1 poetry run python tools/run_requirements_workflow.py \
    --type lld --issue 4 --repo /c/Users/mcwiz/Projects/boostgauge --yes

PYTHONUNBUFFERED=1 poetry run python tools/run_implement_from_lld.py \
    --issue 4 --repo /c/Users/mcwiz/Projects/boostgauge
```

After implementation, run a demo wiring collector + gauge:
```bash
poetry run python -c "
from boostgauge.collectors.windows import WindowsCollector
from boostgauge.gauge import demo_with_data
demo_with_data(WindowsCollector(), duration=10)
"
```

**Lap split targets:**
- `lld_approved` — t+3m from phase start
- `pr_merged` — t+13m
- `gauge_needle_moving` — t+15m (gauge driven by live data)

**Visible after this phase:** **gauge needle moves in real-time** as ConPTY count, memory, processes change. Open a few processes; watch the needle climb.

### Phase 4 — #2 Peak-hold telltale needles (58:00 → ~72:00)

**Why fourth:** lld-ready, builds on the visual canvas from phase 2 + data from phase 3. The signature feature — what makes boostgauge different from any other system monitor.

```bash
cd /c/Users/mcwiz/Projects/AssemblyZero
PYTHONUNBUFFERED=1 poetry run python tools/run_requirements_workflow.py \
    --type lld --issue 2 --repo /c/Users/mcwiz/Projects/boostgauge --yes

PYTHONUNBUFFERED=1 poetry run python tools/run_implement_from_lld.py \
    --issue 2 --repo /c/Users/mcwiz/Projects/boostgauge
```

**Lap split targets:**
- `lld_approved` — t+3m from phase start
- `pr_merged` — t+11m
- `telltale_visible` — t+13m (4 colored peak-hold needles riding the gauge)

**Visible after this phase:** **four colored telltale needles** beside the main needle. Demo move: deliberately spike a metric (e.g., spawn 10 processes), watch the 1m telltale catch the peak and hold while the main needle drops back.

### Phase 5 — #5 Always-on-top window + main entry (72:00 → ~88:00)

**Why fifth:** integrates everything. Wires #1 + #2 + #4 + #7 into a launchable application. The `__main__:main` entry point lives here. After this phase, `boostgauge` is a runnable command.

```bash
cd /c/Users/mcwiz/Projects/AssemblyZero
PYTHONUNBUFFERED=1 poetry run python tools/run_requirements_workflow.py \
    --type lld --issue 5 --repo /c/Users/mcwiz/Projects/boostgauge --yes

PYTHONUNBUFFERED=1 poetry run python tools/run_implement_from_lld.py \
    --issue 5 --repo /c/Users/mcwiz/Projects/boostgauge
```

**Lap split targets:**
- `lld_approved` — t+3m from phase start
- `pr_merged` — t+13m
- `app_launches_locally` — t+15m (`poetry run boostgauge` opens the app)

**Visible after this phase:** **full app launches** — always-on-top window, draggable, frameless, with all features from phases 1-4 wired together. Run it locally before tagging.

### Phase 6 — Tag + publish (88:00 → ~95:00)

```bash
cd /c/Users/mcwiz/Projects/boostgauge
git tag v0.1.0
git push origin v0.1.0
# release.yml triggers; OIDC auth to PyPI; poetry build + poetry publish.
gh run watch --repo martymcenroe/boostgauge   # watch the release workflow live
```

**Lap split targets:**
- `tag_pushed` — t+5s
- `release_workflow_started` — t+30s
- `pypi_published` — t+5m

**Visible after this phase:** PyPI page exists at `https://pypi.org/project/boostgauge/0.1.0/`. Show it in the browser.

### Phase 7 — Verify + closing (95:00 → ~110:00)

```bash
python -m venv /tmp/boostgauge-smoke
source /tmp/boostgauge-smoke/Scripts/activate    # or .\bin\activate on PowerShell
pip install boostgauge
boostgauge   # window opens; full UX
```

**Closing shot:** browser tabs side-by-side — PyPI package page, GitHub repo, and the launched app window.

(Voiceover in post: "Total wall-clock: NN minutes. Star AssemblyZero on GitHub if you want to see how this works.")

**Estimated total raw recording: ~110 minutes. Edited to YouTube: ~12-18 minutes.**

---

## 6. Lap split targets (cumulative from t=0)

| Beat | Cumulative target |
|---|---|
| `attempt_started` | 0:00 |
| `phase_1_pr_merged` (#7 config) | 12:00 |
| `phase_2_gauge_window_visible` (#1) | 39:00 |
| `phase_2_pr_merged` (#1) | 42:00 |
| `phase_3_gauge_needle_moving` (#4) | 57:00 |
| `phase_3_pr_merged` (#4) | 58:00 |
| `phase_4_telltale_visible` (#2) | 71:00 |
| `phase_4_pr_merged` (#2) | 72:00 |
| `phase_5_app_launches_locally` (#5) | 87:00 |
| `phase_5_pr_merged` (#5) | 88:00 |
| `tag_pushed` | 88:30 |
| `pypi_published` | 93:00 |
| `install_smoke_passed` | 95:00 |
| `app_launched_from_pypi` | 96:00 |
| `attempt_complete` | 100:00 |

**Run is "clean" if all splits within 1.2× target. "Great" if all within 1.0×.**

---

## 7. Known halts and recovery routes

(Unchanged from v1 §6.)

| Failure | Detection | On-camera recovery story | Off-camera recovery |
|---|---|---|---|
| Gemini 503/529 | Reviewer timeout | Wait + show `/workflow-status` + run `--resume-review` | After AZ #1071 (auto-retry), automatic. Cut take if not auto-recovered within 60s. |
| Two-strike stagnation | N3 HALT after same-blocking-issues twice | Show the verdict, manual edit, resume | Cut take. The LLD needs work; do it off-camera. |
| Mech-validation max-iterations | N1.5 hit max | Show validator error, manual fix to LLD | Cut take. |
| Test plan BLOCKED | Implementation N1 returned BLOCKED | Run `--auto` flag (after AZ #1072) | Pre-AZ-#1072: cut take. |
| Coverage target missed | N5 ran but coverage < target | Show why; edit test or accept lower coverage | Cut take. |
| PR check blocked (Cerberus didn't approve) | `mergeable_state: blocked` after pr-sentinel passed | Show secret config, redeploy if needed | Spawn-state should have caught this. Hard cut. |
| Visual-verify FAIL on phase 2 (#1) | AZ #1075 returns FAIL | Show the verdict, iterate the LLD | Cut take. The renderer needs work. |
| PyPI publish failed | release.yml workflow failed | Show error, fix forward | Almost always a config issue. Cut take. |
| Cross-feature integration breaks | Phase 3+ needle doesn't move; phase 4+ telltales don't appear | Run integration test; identify which feature regressed | Cut take. The previous phase's LLD missed an interface. |

---

## 8. Reset procedure between attempts

```bash
cd /c/Users/mcwiz/Projects/AssemblyZero
poetry run python tools/speedrun_reset.py \
    --repo /c/Users/mcwiz/Projects/boostgauge \
    --all-issues
```

(Per AZ #1076 — script doesn't exist yet.)

Verifies "spawn state restored." Adds row to run log.

---

## 9. Take-acceptance criteria

A take is **accepted** for YouTube post-production iff:

- [ ] All lap splits hit (within 1.2× target).
- [ ] No halts that required cuts.
- [ ] PyPI publish succeeded; `pip install boostgauge` works in fresh venv.
- [ ] App launches and renders. Needle moves with live data. Telltales hold peaks.
- [ ] Visual-verify (#1075) passes on phase 2 + final state.
- [ ] Total raw runtime ≤ 130 min.
- [ ] Recording quality acceptable.

A take is **provisional** (B-roll splice candidate) if ≤ 2 recoverable halts with B-roll available, OR one missed split off by < 2× target.

A take is **rejected** if > 2 halts, no B-roll coverage, app fails to launch, or recording quality unusable.

---

## 10. Recording / post-production notes

(Substantively unchanged from v1 §10.)

### 10.1. During recording

- Recording starts BEFORE the first `gh issue list`. Capture spawn state visibly.
- Capture both panes (console + Claude Code session) at native resolution.
- Console font ≥ 14pt for YouTube 1080p compression.
- Wall-clock visible (system clock, OBS overlay, or `tools/speedrun_overlay.py` output per AZ #1076).

### 10.2. Post-production

- Speed up Gemini-thinking phases to 4-8x.
- Speed up `poetry install` and similar long stdlib commands to 4-8x.
- KEEP at 1x: PR creation, merge, PyPI publish, install smoke, **and the gauge-window-appears moment in phase 2**.
- Add lap-split overlay (read from `data/speedrun/{attempt}.json`).
- Add voiceover (operator's voice; voice-cloned in a future iteration).
- Title cards at phase boundaries with the visible artifact name (e.g., "Phase 2 — A gauge appears").
- Closing call to action: "Star AssemblyZero on GitHub" with URL on screen ≥ 5 sec.

### 10.3. Distribution

- YouTube upload with phase timestamps in description.
- X post with YouTube link + 30-sec teaser clip + AZ repo URL.
- Pin the X post to the profile.

---

## 11. Run log

Per AZ #1076: `data/speedrun/run-log.jsonl`. One entry per attempt.

```json
{"attempt": N, "started_at": "...", "ended_at": "...", "outcome": "accepted|provisional|rejected", "splits_met": 14, "splits_missed": 0, "failure_mode": null, "notes": "..."}
```

---

## 12. Open decisions (still need user input)

### 12.1. Which 5–6 features for the demo arc — RESOLVED ✓

#7 → #1 → #4 → #2 → #5. Locked 2026-05-09 from boostgauge #34 triage.

### 12.2. Landing page approach — STILL OPEN

Options:
- GitHub Pages on `main`/`docs/` (zero infra).
- Cloudflare Worker on `boostgauge.dev` or similar.
- Skip; rely on GitHub repo README.

### 12.3. Visual reference for the gauge — STILL OPEN, deferred

User mentioned (2026-05-09): generate a target gauge image via Nano Banana / Gemini 3 Image as the spec input, then visual-verify against it. Filed as future enhancement under AZ #1075. Defer to v3 of the route.

### 12.4. Wiki content source — STILL OPEN

Options:
- Auto-generated from the README.
- Authored as a separate prep task before recording.
- Skipped for v1.

### 12.5. Voice cloning timeline — DEFERRED

User mentioned ~6 months. Route v2 assumes silent recording + post-edited voiceover. Voice clone integration goes in route v3 if/when ready.

### 12.6. Pending #34 follow-up decisions — STILL OPEN

From the triage summary on closed issue #34:
- **#35** (Telltale demo issue): close as redundant with #2, or keep as a smaller dry-run target?
- **#25** (umbrella issue): close as superseded by decomposed #1-#7?
- **#3** (composite metric algorithm): fold into #4's scope?

These don't block recording but are housekeeping for the speed-run prep phase.

---

## 13. Versioning

- v1: structure + placeholders (`0001-route-v1.md`, archived).
- v2 (this doc): feature arc locked + visible-progression reorder + calibrated lap splits.
- v3: landing page + wiki content decided + #35/#25/#3 housekeeping resolved.
- v4+: each significant change after a take that revealed something.

---

## 14. References

- Audit 0001 (config gaps): `docs/audit-results/0001-assemblyzero-workflow-readiness-2026-05-09.md`.
- Audit 0002 (deeper, spec/standards/skills): `docs/audit-results/0002-assemblyzero-deeper-readiness-2026-05-09.md`.
- Triage of 26 boostgauge issues: closed issue #34 (summary comment).
- AZ backlog issues backing this route: #1065-#1076 (standards, skills, instrumentation, PyPI pipeline, visual verify).
- boostgauge prep issues: #31-#33, #36 (#34 closed; #35 pending decision).
