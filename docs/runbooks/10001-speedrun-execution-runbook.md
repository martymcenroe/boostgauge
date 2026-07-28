# 10001 — Speedrun Execution Runbook (v2)

**For:** Marty, during a recorded boostgauge speedrun attempt.
**Companion:** `docs/speedrun/0005-route-v4.md` (the why). This doc is the how — keep it open on the second monitor.
**Last updated:** 2026-07-15 (rewritten after the overnight hardening campaign, issue #96 — 7 test runs, 9 upstream fixes)

---

## 0. The one-paragraph version

You sit on a fresh `speedrun-attempt-N` branch. For each feature you run **one command**; the pipeline designs it, reviews the design, writes the code test-first, runs the tests, and opens a pull request. You merge that PR (one command, instant), pull, and show the demo. Six features, then tag and publish to PyPI. Main never moves.

---

## 1. OBS setup

Same three scenes as before:

| Scene | When | Shows |
|---|---|---|
| S1 Console + Code | default | terminal (left), Claude Code window (right) |
| S2 Code + App | first gauge onward | Claude Code + the running app |
| S3 Browser | publish + finale | PyPI page, GitHub repo, running app |

Settings that matter:
- **Record as MKV, not MP4.** A crash at minute 100 of an MP4 loses everything; MKV survives and converts losslessly afterward. Non-negotiable.
- 1080p60, ~8 Mbps, mic peaking around −12 dB.
- Hotkeys: Ctrl+Shift+R record, Ctrl+Shift+S stop, Ctrl+Shift+1/2/3 scenes.
- Do a 2-minute test recording; watch it back; delete it.

---

## 2. Pre-flight (15 minutes, all of it matters)

### 2.1 Machine hygiene — nothing may pop onto the screen
- Focus Assist ON. Slack/Discord/mail fully quit. Windows Update paused.
- Scheduled-task flash risk is resolved fleet-wide (comp-environ ADR-0006, 2026-07-27): the flash class — InteractiveToken tasks with console actions — was converted to silent wscript launchers, and the Codex-* tasks are S4U, which cannot draw on the interactive desktop at all. Paranoia check: `tools/verify_converted_tasks.py` in comp-environ.
- Close other Claude/agent sessions — a solo machine keeps the take stable.
- **Use a dedicated clean browser profile for scene S3** — no bookmarks, logged-in notification bell off. A GitHub notification can flash a private repo's name onto footage you can never unpublish.
- 15+ GB free disk for the recording.

### 2.2 boostgauge ready
```bash
cd /c/Users/mcwiz/Projects/boostgauge
git fetch origin
poetry install
poetry run python -c "import PIL, psutil, pystray, tkinter; print('deps OK')"
```
If `poetry install` complains about the lock file, stop and fix that first — it means a dependency change didn't regenerate the lock (this killed a test run once; see #94).

### 2.3 AssemblyZero ready
```bash
cd /c/Users/mcwiz/Projects/AssemblyZero
git fetch origin && git merge --ff-only origin/main
git status --short   # expect clean
```

### 2.4 Gemini ready
Confirm credential rotation shows all credentials available (the pipeline prints `[PREFLIGHT] Gemini: 4/4 credentials` at each stage — if pre-flight shows fewer, resolve before recording).

### 2.5 Start the attempt branch
```bash
N=1                                  # attempt number
cd /c/Users/mcwiz/Projects/boostgauge
git checkout -b speedrun-attempt-${N} speedrun-spawn-v1
sed -i "s/^version = \".*\"/version = \"0.1.$((N-1))\"/" pyproject.toml
# Attempt 1: pyproject already carries 0.1.0, so the sed is a no-op — only
# commit when there is a real change, or the commit fails on camera.
git diff --quiet pyproject.toml || { git add pyproject.toml && \
    git commit -m "chore: bump to v0.1.$((N-1)) for speedrun attempt ${N}"; }
git push -u origin speedrun-attempt-${N}
```
The tag `speedrun-spawn-v1` must point at current main (see issue #88 for the re-point). Verify:
```bash
git rev-parse speedrun-spawn-v1^{commit} && git rev-parse origin/main
```
Same hash = good.

### 2.6 Run-log stub
Append a line to `data/speedrun/run-log.jsonl` (create if missing): attempt number, branch, version target, AssemblyZero commit hash, start time.

---

## 3. Press record

Ctrl+Shift+R, scene S1, breathe for 5 seconds, then:
```bash
gh issue list --repo martymcenroe/boostgauge --label lld-ready --state open
ls src/
```
Empty `src/`, fourteen lld-ready issues on the board — today's arc is six of them (#7 → #41 → #1 → #4 → #2 → #5). Say the mission out loud. Go.

---

## 4. The build loop — same three steps, six times

**The arc: #7 → #41 → #1 → #4 → #2 → #5** (config → peak-hold logic → gauge face → live data → memory needles → the app).

For each issue N:

### Step A — one command builds the feature
```bash
cd /c/Users/mcwiz/Projects/AssemblyZero
PYTHONUNBUFFERED=1 poetry run python tools/orchestrate.py \
    --issue N --repo /c/Users/mcwiz/Projects/boostgauge --no-gate-pr
```
This runs the whole pipeline: design → design review → design PR (merges itself) → spec → test-first implementation → tests must pass → implementation PR opens. Typical time: 5–10 minutes for logic features, longer for the gauge face.

Watch for: `[EDIT-SCRIPT] ... byte-identical` (good), `Results: N passed, 0 failed` (the tests really ran), and the final `PR: https://...` line.

### Step B — merge and pull (seconds)
```bash
cd /c/Users/mcwiz/Projects/boostgauge
git branch --show-current        # MUST say speedrun-attempt-N — if not, STOP
gh pr merge <PR-number> --squash --repo martymcenroe/boostgauge
git pull
```
Two rules learned the hard way:
- **Always `git pull` after the merge.** The next feature is built from whatever your checkout has — skip the pull and feature N+1 gets built against a tree that's missing feature N.
- GitHub only auto-closes issues when PRs merge into main. Yours merge into the attempt branch, so **close the issue yourself on camera** (`gh issue close N`) — it's a good beat anyway.

### Step C — show it
Run the demo from the merged PR's description or the issue's acceptance criteria (NOT from a stale script — the real command is whatever the pipeline actually built). First gauge on screen = switch to scene S2 and let it breathe for ten seconds.

### If a phase fails
The pipeline halts with a `Resume:` hint. On camera: read the error, say what you see, run the resume. That's the science. If it needs off-camera surgery, stop recording, note the time, and treat it like a cut take (§6).

---

## 5. Publish (after all six merge)

```bash
cd /c/Users/mcwiz/Projects/boostgauge
git tag v0.1.$((N-1))
git push origin v0.1.$((N-1))
gh run watch --repo martymcenroe/boostgauge
```
Scene S3. The release workflow builds and publishes to PyPI (proven working — v0.0.0 went through it). Then the finale:
```bash
python -m venv /tmp/smoke && source /tmp/smoke/Scripts/activate
pip install boostgauge
boostgauge
```
Installed from PyPI, running on screen, next to the GitHub repo. Stop recording.

---

## 6. After a cut take

A stopped take leaves work-in-progress behind. Sweep it:
- Close any open pipeline PRs on the attempt branch (`gh pr list`), with a one-line comment.
- Remove leftover side-folders: `git worktree list` in boostgauge; `git worktree remove <path>` for any `boostgauge-N*` entries (they may refuse for a minute or two while child processes let go of files — wait and retry, never force).
- The attempt branch stays on GitHub as the record of the attempt. Next attempt gets N+1 and version v0.1.N. Never reuse version numbers.

---

## 7. Before you upload

One deliberate pass of the raw footage (see issue #93):
- No keys/tokens visible in any terminal frame or error dump.
- No pop-up dialogs appeared (if a passphrase prompt appeared on camera, investigate before publishing).
- No private repository names in any notification, tab, or terminal output.
- Skim the frames around every error — error dumps are where leaks live.
Write one sign-off line in the run log, then upload.
