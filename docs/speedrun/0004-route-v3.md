# Speed-Run Route v3 — boostgauge zero-to-PyPI

**Status:** Operational
**Last updated:** 2026-05-22
**Win condition:** YouTube video → X post → stars on AssemblyZero GitHub
**Run budget:** ≤42 attempts (per user, 2026-05-09)
**Supersedes:** `0001-route-v1.md` (archived), `0002-route-v2.md` (this v3 supersedes; v2 remains as historical reference — its feature arc and lap-split targets are still load-bearing)

---

## 1. What changed v2 → v3

- **Spawn-state-tag pattern.** `speedrun-spawn-v1` on boostgauge, `speedrun-v2` on AssemblyZero. Tags pinned 2026-05-22.
- **Attempt-branch workflow** (§8) replaces v2's "reset main with `speedrun_reset.py`". Force-push to main is banned; attempt-branches off the spawn-tag sidestep that entirely. Main stays at the spawn-state commit forever (or until `speedrun-spawn-v2` is intentionally cut).
- **Pre-set version bump per attempt.** Attempt branch `speedrun-attempt-N` starts with one commit that sets `pyproject.toml` version to `v0.1.{N-1}`. The recording starts at that commit, not at the spawn-tag commit.
- **Off-camera dry runs removed** (v2 §4.3) per `feedback-speedrun-no-dry-runs`. The speedrun is a science experiment, not a rehearsal.
- **AZ evolves freely between attempts.** `speedrun-v2` is a naming anchor on AZ, not a version pin. Each attempt records the AZ SHA it ran against in the run log (§11).
- **Pre-flight items 4–7 are RESOLVED** (PyPI Trusted Publisher + v0.0.0 name claim + landing page + spawn-state tags) per 2026-05-22 prep session.

---

## 2. Mission

A single continuous recording from "boostgauge has zero source code on the attempt branch" to "package is live on PyPI, the launched app is visible, the wiki page exists." Edited in post for YouTube.

The video is marketing for AssemblyZero. The artifact is a stars-on-AZ-GitHub conversion event. boostgauge is the demonstration vehicle.

(Unchanged from v2 §1.)

---

## 3. Recording surfaces

| Pane | Content | Purpose |
|---|---|---|
| Primary | Console (Git Bash / PowerShell) | Where AZ workflow commands run. The "speed-run timer" pane. |
| Secondary | Claude Code session window | Where the agent does the workflow execution. Visual interest during long thinking phases. |
| Tertiary | Application window (after phase 2) | The visible boostgauge gauge — appears in phase 2, gets richer in phases 3-5. |
| Optional | Browser at finale | PyPI page + GitHub repo + launched app side-by-side. |

(Unchanged from v2 §3.)

---

## 4. Spawn state — what's true before pressing record

### 4.1. AZ side (anchor, not pin)

- `martymcenroe/AssemblyZero` is at `speedrun-v2` tag (commit `3a30731a5`, 2026-05-22) **OR LATER**. AZ improvements between attempts roll forward; tag is a naming anchor, not a pin.
- Standards #1065–1068, skills #1069/#1070/#1075, instrumentation #1076 per AZ backlog. Note: `tools/speedrun_reset.py` (#1076) is no longer load-bearing under the attempt-branch model — the "reset" is just `git checkout -b speedrun-attempt-N+1 speedrun-spawn-v1`.

### 4.2. boostgauge side (pinned)

- `martymcenroe/boostgauge` `main` is at `speedrun-spawn-v1` tag (commit `cd2dbef`, 2026-05-22). Main does not move during attempts — only between officially-cut spawn-state versions.
- **Visibility: public** (flipped 2026-05-22).
- **PyPI name claimed** via `v0.0.0` placeholder publish; pending publisher promoted to trusted (2026-05-22).
- **Landing page** at https://boostgauge.martymcenroe.ai (Cloudflare Pages from `docs/landing/`, browser-config completed by operator).
- **Wiki** initialized with `Home.md` (2026-05-22).
- **License:** MIT, aligned across `LICENSE`, `pyproject.toml`, and CLAUDE.md (2026-05-22).
- **`release.yml`** wired for OIDC tag-push publish to PyPI.
- **`auto-reviewer.yml`** upgraded to NEW caller format; Cerberus auto-approves PRs (2026-05-22).
- **Open issues for the recorded arc:** #7, #1, #4, #2, #5 — all `lld-ready` (or `lld-needs-revision` for #1 with binding visual spec in `docs/design/0002-aesthetic-v1-stingray.md`).

### 4.3. Operator side

- Recording software tested. Audio levels OK. Font ≥ 14pt for 1080p compression.
- **No off-camera dry runs.** The speedrun is a science experiment; failure on camera is the feature, not a bug to mitigate via prep. Per `feedback-speedrun-no-dry-runs` memory (2026-05-22).
- Run-log entry stub created for the attempt (§11).
- AZ #1109 / #1110 (Codex scheduled-task popup bugs) confirmed fixed or accepted as risk before recording — they will steal focus mid-recording if not.

---

## 5. The route — beat by beat

All commands assume working directory is the attempt branch's worktree on boostgauge, not `main`.

Phases unchanged from v2 §5; just substitute `--repo /c/Users/mcwiz/Projects/boostgauge` and remember that PRs during the take target `speedrun-attempt-N` as base, NOT main.

| Phase | Focus issue | Visible after phase |
|---|---|---|
| 0 (0:00 → 0:30) | Prologue — show issue list + empty `src/` | issue list, empty `src/` tree |
| 1 (0:30 → 12:00) | #7 — Configuration file | `src/boostgauge/config.py` exists; demo loads JSON |
| 2 (12:00 → 42:00) | #1 — Core gauge renderer (first visible artifact) | Static tachometer in a window |
| 3 (42:00 → 58:00) | #4 — Windows data collector | Needle moves with live data |
| 4 (58:00 → 72:00) | #2 — Peak-hold telltale needles | Four colored telltale needles riding the gauge |
| 5 (72:00 → 88:00) | #5 — Always-on-top window + main entry | Full app launches; `boostgauge` command works |
| 6 (88:00 → 95:00) | Tag + publish | `pypi.org/project/boostgauge/0.1.{N-1}/` is live |
| 7 (95:00 → 110:00) | Verify + closing | `pip install boostgauge` works in fresh venv |

For each phase's exact AZ commands and per-phase lap-split targets, see v2 §5 — they remain authoritative.

---

## 6. Lap split targets

Unchanged from v2 §6. Run is "clean" if all splits within 1.2× target; "great" if all within 1.0×.

---

## 7. Known halts and recovery routes

Unchanged from v2 §7. The only delta: a halt that requires a fix to AZ is acceptable — AZ evolves freely between attempts. Apply the fix, restart with a fresh attempt-branch.

---

## 8. Attempt-branch workflow (NEW — replaces v2 §8 "Reset procedure")

The single biggest change in v3. Each recorded attempt happens on its own branch off `speedrun-spawn-v1`. Main never moves during attempts.

### 8.1. Pre-attempt setup (off-camera, not a dry run)

```bash
N=1   # attempt number — bumps for each recorded attempt
VERSION="v0.1.$((N-1))"   # attempt 1 -> v0.1.0, attempt 2 -> v0.1.1, ...

# Branch off the spawn-state tag
git -C /c/Users/mcwiz/Projects/boostgauge fetch origin
git -C /c/Users/mcwiz/Projects/boostgauge checkout -b speedrun-attempt-${N} speedrun-spawn-v1

# Pre-set the version bump on the attempt branch
# (edit pyproject.toml: version = "0.1.{N-1}")
sed -i "s/^version = \".*\"/version = \"0.1.$((N-1))\"/" pyproject.toml
git -C /c/Users/mcwiz/Projects/boostgauge add pyproject.toml
git -C /c/Users/mcwiz/Projects/boostgauge commit -m "chore: bump to ${VERSION} for speedrun attempt ${N}"
git -C /c/Users/mcwiz/Projects/boostgauge push -u origin speedrun-attempt-${N}

# (Optional) Fetch latest AZ if improvements have landed since the previous attempt
git -C /c/Users/mcwiz/Projects/AssemblyZero fetch origin
git -C /c/Users/mcwiz/Projects/AssemblyZero merge --ff-only origin/main

# Open run-log entry stub: data/speedrun/run-log.jsonl
```

### 8.2. During the recorded attempt

- All workflow PRs from `tools/run_implement_from_lld.py` target `speedrun-attempt-${N}` as base, NOT main.
- AZ workflows function identically — the `--repo /c/Users/mcwiz/Projects/boostgauge` arg points at the worktree; the default branch detection picks up the current checkout.
- Phase 6 (tag + publish):
  ```bash
  git -C /c/Users/mcwiz/Projects/boostgauge tag ${VERSION}
  git -C /c/Users/mcwiz/Projects/boostgauge push origin ${VERSION}
  ```
  `release.yml` triggers on the tag push; OIDC handshake; PyPI publishes the version specified by the pre-set `pyproject.toml`.

### 8.3. After the attempt

**On success (Phase 6 completes, PyPI page resolves):**
- Branch `speedrun-attempt-${N}` stays on origin as the archive of the successful run.
- PyPI shows v0.1.{N-1} as latest.
- Run-log entry marks `outcome: accepted`.

**On failure (most common case — user expectation 2026-05-22):**
- Branch stays as archive on origin.
- No tag was pushed → no PyPI publish → no version slot consumed on PyPI.
- BUT the version slot in our sequencing IS consumed: attempt N+1 uses v0.1.{N}, NOT v0.1.{N-1}. **Strict-sequential numbering** — no reuse of unsuccessful attempts' versions.
- Run-log entry marks `outcome: rejected` with `failure_mode` and the AZ SHA used.

### 8.4. Cleanup vs. preservation

- **Don't delete failed attempt branches.** They're the evidence of the science experiment. Blog narrates each.
- After ~20 attempts the branch list will be cluttered. Periodic archive: rename old branches `archive/speedrun-attempt-N` to declutter `gh pr list` views, optionally.

---

## 9. Take-acceptance criteria

Unchanged from v2 §9.

---

## 10. Recording / post-production notes

Unchanged from v2 §10.

---

## 11. Run log

`data/speedrun/run-log.jsonl`. One entry per attempt. Extended schema:

```json
{
  "attempt": 1,
  "branch": "speedrun-attempt-1",
  "version_target": "v0.1.0",
  "az_sha": "3a30731a5",
  "started_at": "2026-05-22T19:00:00Z",
  "ended_at": "2026-05-22T20:45:00Z",
  "outcome": "accepted",
  "splits_met": 14,
  "splits_missed": 0,
  "failure_mode": null,
  "notes": "..."
}
```

New fields vs v2: `branch`, `version_target`, `az_sha`.

---

## 12. Open decisions

### 12.1. Feature arc — RESOLVED ✓ (v2)
#7 → #1 → #4 → #2 → #5.

### 12.2. Landing page — RESOLVED ✓ (2026-05-22)
Cloudflare Pages from `docs/landing/` at `boostgauge.martymcenroe.ai`.

### 12.3. Visual reference for the gauge — DEFERRED to v4
Canonical Stingray image at `images/aesthetic-v1-stingray-canonical.jpg` is the binding spec. AZ #1075 visual-verify gates phase 2.

### 12.4. Wiki content — RESOLVED ✓ (2026-05-22)
`Home.md` populated with status, links, and doc roadmap. Future pages (Architecture, Configuration, Skins, Platforms) added as features ship.

### 12.5. Voice cloning — DEFERRED to v4+
Per v2 §12.5.

### 12.6. #34 follow-up — STILL OPEN
- **#35** (Telltale demo issue): close as redundant with #2, or keep as a smaller dry-run target? Note: with no dry runs, "smaller dry-run target" framing is dead. Recommendation: close as superseded by #2.
- **#25** (umbrella issue): close as superseded by decomposed #1-#7.
- **#3** (composite metric algorithm): fold into #4's scope?

### 12.7. PyPI version reuse — RESOLVED ✓ (2026-05-22)
**Strict sequential.** Failed attempts consume their version slot. No reuse.

### 12.8. Author email — STILL OPEN
`pyproject.toml` still shows `cto@thrivetech.ai`. Plan was to switch to `opensource@martymcenroe.ai` (Cloudflare alias set up 2026-05-22). Lands as a small PR before attempt 1's tag-push so v0.1.0 metadata shows the new email.

### 12.9. `[project.urls]` — NEW, STILL OPEN
PyPI v0.0.0 has no Homepage / Repository / Documentation links — `pyproject.toml` lacks a `[project.urls]` block. Lands in the same PR as 12.8.

---

## 13. Versioning

- **v1** (`0001-route-v1.md`) — archived.
- **v2** (`0002-route-v2.md`) — superseded by this doc. Feature arc, lap splits, and recovery-route tables remain authoritative cross-references.
- **v3** (this doc) — attempt-branch workflow, spawn-state tags, no-dry-runs rule, status snapshot of pre-flight items.
- **v4** — post-first-attempt revision, incorporating whatever the first recorded attempt reveals.

---

## 14. References

- **Spawn-state tags:**
  - `speedrun-spawn-v1` (boostgauge `cd2dbef`)
  - `speedrun-v2` (AssemblyZero `3a30731a5`)
- **Audit 0001 / 0002:** `docs/audit-results/` — feature-arc + spec-quality references; still valid.
- **Test strategy:** `docs/design/0001-test-strategy.md` — Option C (off-screen PIL render; no `tkinter.Tk()` in tests). Load-bearing constraint.
- **Aesthetic spec:** `docs/design/0002-aesthetic-v1-stingray.md` — binding visual spec for #1 (Phase 2). Canonical image at `images/aesthetic-v1-stingray-canonical.jpg`.
- **Triage of 26 boostgauge issues:** closed issue #34 (summary comment).
- **Memory rules in scope:**
  - `feedback-speedrun-no-dry-runs` — no off-camera rehearsal.
  - `feedback-fword-censorship` — profanity removed entirely from any saved/committed content.
  - `feedback-az-tools-user-runs-script` — classic-PAT tooling stays user-driven.
  - `feedback-verify-external-service-behavior` — verify, don't assert, on PyPI/GitHub/Cloudflare policy specifics.
