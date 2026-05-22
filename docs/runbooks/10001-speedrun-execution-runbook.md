# 10001 — Speedrun Execution Runbook

**For:** the operator (Marty) during a recorded boostgauge speedrun attempt.
**Companion to:** `docs/speedrun/0004-route-v3.md` (architectural / procedural design). This runbook is the operational reference you keep open in a second monitor.
**Last updated:** 2026-05-22

---

## 0. What this is

A recipe for actually pressing **Record** and getting through the speedrun. Route v3 explains *what* and *why*; this runbook is *how* — OBS setup, what to click, what to watch for, what to do when things go sideways.

If you only have time to read one thing right now: §2 (pre-flight checklist) and §4 (per-phase cards).

---

## 1. OBS setup

These are starting points. Adapt freely; the operator's recording setup is personal.

### 1.1. Scenes

Suggested three-scene layout. Switch via hotkeys during the take.

| Scene | When to be on it | Sources |
|---|---|---|
| `S1 — Console + Code` | Default. Phase 0 through Phase 5. | (left 60%) Display capture cropped to the terminal pane; (right 40%) Window capture of the Claude Code app window |
| `S2 — Code + App` | Phase 2 first time the gauge appears; Phases 3-5 when the app is visible | (left 60%) Claude Code window; (right 40%) the boostgauge app window once it launches; (full-screen toggle for any "linger on the gauge" demo moments) |
| `S3 — Finale Browser` | Phase 6 (PyPI publish) and Phase 7 (verify) | Browser captures of three tabs: pypi.org/project/boostgauge, github.com/martymcenroe/boostgauge, and the launched app window |

### 1.2. Sources within each scene

Pin these in OBS source list:

- **Display capture** (whole monitor) — for full-screen demo moments
- **Window capture: terminal** — Git Bash or PowerShell, the "speedrun timer pane"
- **Window capture: Claude Code** — the agent's UI
- **Window capture: boostgauge** — only visible after Phase 2; toggle visibility in Phase 2 first-launch
- **Window capture: browser** — for the finale
- **Audio input: microphone** — for live voiceover (or mute and dub in post)
- **Audio output: desktop audio** — capture any system sounds (set to muted unless you want to capture the PyPI publish ding)

### 1.3. Recording settings

Output → Recording:
- **Format:** `mp4` (or `mkv` if you want crash-safe and remux to mp4 in post)
- **Encoder:** `x264` if CPU is plenty; `NVENC H.264` or `AMD H.264` if you have a GPU encoder
- **Bitrate:** ~8 Mbps for 1080p; ~16 Mbps for 1440p
- **Output path:** `~/Videos/boostgauge-speedrun/attempt-N/` (create the folder before recording)

Video:
- **Base canvas:** match your monitor (typically 1920x1080 or 2560x1440)
- **Output (scaled):** same as base unless you want to downscale for file size
- **FPS:** 60 if your monitor is 60Hz+; 30 if you want smaller files and have less motion content

Audio:
- **Sample rate:** 48 kHz
- **Channels:** Stereo

### 1.4. Hotkeys

Bind in OBS settings → Hotkeys. Suggested:
- `Ctrl+Shift+R` — Start recording
- `Ctrl+Shift+S` — Stop recording
- `Ctrl+Shift+1/2/3` — Switch to scene S1 / S2 / S3
- `Ctrl+Shift+M` — Mute / unmute microphone

Make sure these don't conflict with any other apps (especially Claude Code).

### 1.5. Pre-record OBS test

Two minutes before pressing record on the real take:
- Press `Ctrl+Shift+R` to start a test recording
- Switch through all three scenes
- Speak something — confirm mic levels (peaks around -12 dB, not clipping)
- Stop, watch the test file briefly, delete it

---

## 2. Pre-flight checklist

Run through this BEFORE pressing Record on the real take. ~5 minutes.

### 2.1. boostgauge repo state

```bash
git -C /c/Users/mcwiz/Projects/boostgauge fetch origin
git -C /c/Users/mcwiz/Projects/boostgauge log --oneline speedrun-spawn-v1 | head -1
```

Expected: the spawn-tag commit message starts with the most recent prep PR (currently `chore: pyproject polish` per the 2026-05-22 re-pointing).

### 2.2. AssemblyZero repo state

```bash
git -C /c/Users/mcwiz/Projects/AssemblyZero fetch origin
git -C /c/Users/mcwiz/Projects/AssemblyZero log --oneline -1
git -C /c/Users/mcwiz/Projects/AssemblyZero status --short
```

Expected: clean tree, on `main`, up-to-date with origin. If there are uncommitted local changes (from prior session prep), either commit them OR stash them OR accept and note in the run-log.

### 2.3. Attempt-branch creation (substitute N)

```bash
N=1   # attempt number
VERSION_TAG="v0.1.$((N-1))"

git -C /c/Users/mcwiz/Projects/boostgauge checkout -b speedrun-attempt-${N} speedrun-spawn-v1

# Bump pyproject version
python -c "
import re, pathlib
p = pathlib.Path('/c/Users/mcwiz/Projects/boostgauge/pyproject.toml')
p.write_text(re.sub(r'^version = \".*\"', f'version = \"0.1.${N-1}\"', p.read_text(), count=1, flags=re.M))
print('bumped to 0.1.${N-1}')
"

git -C /c/Users/mcwiz/Projects/boostgauge add pyproject.toml
git -C /c/Users/mcwiz/Projects/boostgauge commit -m "chore: bump to ${VERSION_TAG} for speedrun attempt ${N}"
git -C /c/Users/mcwiz/Projects/boostgauge push -u origin speedrun-attempt-${N}
```

### 2.4. Focus-stealer kills

Before pressing Record, kill or disable anything that could pop a window or steal focus mid-recording:

- Windows Update notifications: settings → Update & Security → pause for 1 week
- Slack / Discord / Teams: quit fully (closing windows isn't enough; they'll re-notify)
- Email clients: quit
- Antivirus scheduled scans: defer or disable for the hour
- Scheduled tasks that pop consoles: AZ #1109 / #1110 Codex tasks (check status; should be fixed-or-paused)

### 2.5. Window arrangement (S1 default)

- Monitor 1 (recorded): terminal on left, Claude Code on right
- Monitor 2 (not recorded): this runbook open + the boostgauge app once it launches (Phase 5+ moves the app to Monitor 1 for the take)
- Wall clock visible somewhere on Monitor 1 (system clock, OBS overlay, or a manual clock widget)
- Fonts ≥ 14pt in terminal and Claude Code for 1080p compression

### 2.6. Run-log stub

Open `data/speedrun/run-log.jsonl` (create the file if it doesn't exist). Append:

```json
{"attempt": 1, "branch": "speedrun-attempt-1", "version_target": "v0.1.0", "az_sha": "<paste git log -1 --format=%H from AZ>", "started_at": "<fill in after pressing Record>", "ended_at": null, "outcome": null, "splits_met": 0, "splits_missed": 0, "failure_mode": null, "notes": ""}
```

Update fields as the attempt progresses; finalize at the end.

### 2.7. Last-second verifications

- [ ] OBS test recording sounded + looked OK
- [ ] All three scenes switch correctly via hotkeys
- [ ] Mic levels peak around -12 dB, not clipping
- [ ] Monitor 1 has no notification bubbles up right now
- [ ] Coffee is within arm's reach (this matters more than you'd think for a 110-minute take)

---

## 3. Pressing record

When ready:

1. Press `Ctrl+Shift+R` (start recording)
2. Switch to scene S1 if not already
3. **Wait 5 seconds** before doing anything — gives you a clean head on the cut
4. Voiceover (live or for post): "We're going to ship a Python package on PyPI from zero code, end-to-end, in one continuous run. Watch the timer."
5. Begin Phase 0 (see §4.0)

The timer overlay (if AZ #1076 ever ships `speedrun_overlay.py`) starts now. Otherwise, your wall clock and the OBS recording timer are the references.

---

## 4. Per-phase quick-reference cards

Source of truth for phase content + lap-split targets: Route v3 §5 / §6, which inherits from v2 §5 / §6. This section is just the operator's checklist version.

### 4.0. Phase 0 — Prologue (0:00 → 0:30)

```bash
gh issue list --repo martymcenroe/boostgauge --label lld-ready --state open
git -C /c/Users/mcwiz/Projects/boostgauge log --oneline -3
```

Show: the issue list + empty `src/`. Voiceover the mission.

**Visible:** issue list, empty `src/` tree, current branch (`speedrun-attempt-N`).

### 4.1. Phase 1 — #7 Configuration file (0:30 → ~12:00)

```bash
cd /c/Users/mcwiz/Projects/AssemblyZero
PYTHONUNBUFFERED=1 poetry run python tools/run_requirements_workflow.py \
    --type lld --issue 7 --repo /c/Users/mcwiz/Projects/boostgauge --yes

PYTHONUNBUFFERED=1 poetry run python tools/run_implement_from_lld.py \
    --issue 7 --repo /c/Users/mcwiz/Projects/boostgauge
```

**Splits:** `lld_approved` t+150s; `pr_merged` t+9m.
**Visible:** `src/boostgauge/config.py` exists; demo loads JSON.

### 4.2. Phase 2 — #1 Core gauge renderer (12:00 → ~42:00)

```bash
cd /c/Users/mcwiz/Projects/AssemblyZero
PYTHONUNBUFFERED=1 poetry run python tools/run_requirements_workflow.py \
    --type lld --issue 1 --repo /c/Users/mcwiz/Projects/boostgauge --yes

PYTHONUNBUFFERED=1 poetry run python tools/run_implement_from_lld.py \
    --issue 1 --repo /c/Users/mcwiz/Projects/boostgauge
```

When the renderer lands:

```bash
cd /c/Users/mcwiz/Projects/boostgauge
poetry run python -c "from boostgauge.gauge import demo; demo(value=50)"
```

**Splits:** `lld_approved` t+8m; `pr_merged` t+25m; `gauge_window_visible` t+27m.

**THIS IS THE FIRST VISIBLE-PRODUCT MOMENT.** Switch to scene S2 here. Linger on the gauge ≥ 10 seconds. Voiceover: "And there it is — a gauge in a window."

### 4.3. Phase 3 — #4 Windows data collector (42:00 → ~58:00)

```bash
cd /c/Users/mcwiz/Projects/AssemblyZero
PYTHONUNBUFFERED=1 poetry run python tools/run_requirements_workflow.py \
    --type lld --issue 4 --repo /c/Users/mcwiz/Projects/boostgauge --yes

PYTHONUNBUFFERED=1 poetry run python tools/run_implement_from_lld.py \
    --issue 4 --repo /c/Users/mcwiz/Projects/boostgauge
```

Demo wiring:

```bash
poetry run python -c "
from boostgauge.collectors.windows import WindowsCollector
from boostgauge.gauge import demo_with_data
demo_with_data(WindowsCollector(), duration=10)
"
```

**Splits:** `lld_approved` t+3m from phase start; `pr_merged` t+13m; `gauge_needle_moving` t+15m.

**Demo move:** spawn 10 processes (open 10 PowerShell windows quickly), watch the needle climb. Voiceover: "Live data."

### 4.4. Phase 4 — #2 Peak-hold telltale needles (58:00 → ~72:00)

```bash
cd /c/Users/mcwiz/Projects/AssemblyZero
PYTHONUNBUFFERED=1 poetry run python tools/run_requirements_workflow.py \
    --type lld --issue 2 --repo /c/Users/mcwiz/Projects/boostgauge --yes

PYTHONUNBUFFERED=1 poetry run python tools/run_implement_from_lld.py \
    --issue 2 --repo /c/Users/mcwiz/Projects/boostgauge
```

**Splits:** `lld_approved` t+3m; `pr_merged` t+11m; `telltale_visible` t+13m.

**Demo move:** deliberately spike a metric — spawn 10 processes again, watch the 1m telltale catch the peak and hold while the main needle drops back. Voiceover: "Tachometer with memory."

### 4.5. Phase 5 — #5 Always-on-top window + main entry (72:00 → ~88:00)

```bash
cd /c/Users/mcwiz/Projects/AssemblyZero
PYTHONUNBUFFERED=1 poetry run python tools/run_requirements_workflow.py \
    --type lld --issue 5 --repo /c/Users/mcwiz/Projects/boostgauge --yes

PYTHONUNBUFFERED=1 poetry run python tools/run_implement_from_lld.py \
    --issue 5 --repo /c/Users/mcwiz/Projects/boostgauge
```

**Splits:** `lld_approved` t+3m; `pr_merged` t+13m; `app_launches_locally` t+15m.

After implementation, run locally to confirm:

```bash
cd /c/Users/mcwiz/Projects/boostgauge
poetry run boostgauge
```

**Demo move:** drag the always-on-top window over an existing app to show it stays on top. Voiceover: "Always there. Always watching."

### 4.6. Phase 6 — Tag + publish (88:00 → ~95:00)

```bash
cd /c/Users/mcwiz/Projects/boostgauge
git tag v0.1.0   # or whatever N-1 is for this attempt
git push origin v0.1.0
gh run watch --repo martymcenroe/boostgauge   # watch release.yml live
```

**Splits:** `tag_pushed` t+5s; `release_workflow_started` t+30s; `pypi_published` t+5m.

**Switch to scene S3 here** (the browser scene). Open the PyPI page in real-time as it goes live. Voiceover: "And we are on PyPI."

### 4.7. Phase 7 — Verify + closing (95:00 → ~110:00)

```bash
python -m venv /tmp/boostgauge-smoke
source /tmp/boostgauge-smoke/Scripts/activate
pip install boostgauge
boostgauge
```

**Splits:** `install_smoke_passed` t+1m; `app_launched_from_pypi` t+2m.

**Closing shot (S3):** browser tabs side-by-side — PyPI page, GitHub repo, and the launched app window. Hold for 5-10 seconds. Voiceover (or post): "Star AssemblyZero on GitHub if you want to see how this works."

**Stop recording** (`Ctrl+Shift+S`).

---

## 5. During-recording recovery

Cross-references Route v3 §7 (which inherits from v2 §7). The shortest version:

| Symptom | First check | Recovery |
|---|---|---|
| Gemini stalls / 503 / quota | `gemini-rotate.py --status` (per `AssemblyZero/docs/prompts/gemini-rotation-instructions.md`) | Wait + `--resume-review`. If all credentials exhausted: **STOP**, mark attempt failed, address quota, retry tomorrow. |
| Two-strike stagnation (N3 HALT) | Read the verdict in the workflow output | Manual edit to the LLD, then `--resume`. If still stuck: cut take. |
| Mech-validation hit max-iterations | Workflow error message | Manual fix to LLD; cut take if doesn't recover quickly. |
| Test plan BLOCKED (impl workflow) | N1 output | Re-run with `--auto` if AZ supports it; otherwise cut take. |
| Coverage target missed | N5 output | Edit test or accept; usually cut take. |
| PR check blocked (Cerberus didn't approve) | `gh pr checks` and the auto-reviewer workflow run | If `auto-reviewer.yml` errored: secret missing → cut take. If pr-sentinel: read sentinel error. |
| Visual-verify FAIL on Phase 2 | AZ #1075 output | Iterate the LLD or cut take. |
| PyPI publish failed | `gh run view <id>` for `release.yml` | Almost always config — cut take. |
| Cross-feature integration breaks | Manual test in the demo step | Identify which feature regressed; cut take. |

**Rule of thumb:** if a halt is recoverable in < 60 seconds without breaking the speedrun narrative, recover. If recovery requires off-camera fiddling or a clean state, cut the take, mark the run-log entry `outcome: rejected`, prep attempt N+1.

---

## 6. Post-recording

### 6.1. Save the artifact

OBS dropped the file at `~/Videos/boostgauge-speedrun/attempt-N/`. Rename to a descriptive name:

```bash
mv ~/Videos/boostgauge-speedrun/attempt-N/<obs-default-name>.mp4 \
   ~/Videos/boostgauge-speedrun/attempt-N/attempt-N-<outcome>-<duration>.mp4
```

E.g. `attempt-1-accepted-108m.mp4` or `attempt-3-rejected-45m-cerberus-block.mp4`.

### 6.2. Finalize the run-log entry

Update `data/speedrun/run-log.jsonl` for this attempt:

```json
{
  "attempt": 1,
  "branch": "speedrun-attempt-1",
  "version_target": "v0.1.0",
  "az_sha": "...",
  "started_at": "2026-XX-XX...",
  "ended_at": "2026-XX-XX...",
  "outcome": "accepted",
  "splits_met": 13,
  "splits_missed": 1,
  "failure_mode": null,
  "notes": "Gauge took 30s longer than target in Phase 2 (one revision cycle on the LLD)."
}
```

### 6.3. Attempt branch handling

Branch `speedrun-attempt-N` stays on origin as the archive of this attempt. **Do not delete.**

If you accumulate too many branches and want to declutter:

```bash
git -C /c/Users/mcwiz/Projects/boostgauge branch -m speedrun-attempt-N archive/speedrun-attempt-N
git -C /c/Users/mcwiz/Projects/boostgauge push origin archive/speedrun-attempt-N
git -C /c/Users/mcwiz/Projects/boostgauge push origin :speedrun-attempt-N
```

(Renames locally + on origin. The new name `archive/...` keeps the branch visible but groups it.)

### 6.4. Blog draft seeding

For interesting attempts (good + bad), seed a draft in `dispatch/drafts/boostgauge/`:

```bash
TODAY=$(date +%F)
cat > /c/Users/mcwiz/Projects/dispatch/drafts/boostgauge/${TODAY}-attempt-N-<slug>.md << 'EOF'
# Attempt N: <one-line outcome>

*Speedrun run-log entry: data/speedrun/run-log.jsonl attempt N.*

[Write the story while it's fresh: what worked, what broke, what we'd do differently next attempt.]
EOF
```

The blog narrates each attempt; per the science-experiment framing, even rejected attempts are valuable data.

### 6.5. Next attempt

If the outcome was `rejected` and you want to try again immediately:
- Identify the failure mode
- If it requires an AZ fix: land the AZ fix first (PR + merge in AssemblyZero), THEN start attempt N+1 — AZ evolves freely between attempts.
- Increment N (attempt 2 → 3, etc.). The version slot bumps in sync: `v0.1.{N-1}` becomes `v0.1.{N}`.
- Run §2 (pre-flight) again, including a fresh §2.3 attempt-branch creation.

---

## 7. When to stop and regroup

The user's hard rule (per `feedback-speedrun-no-dry-runs` memory): the speedrun is a science experiment. Failure on camera is the feature, not a bug.

But there's a difference between "failure that captures something interesting" and "failure that wasted an hour." If you've had 3+ rejected attempts in a row with the same failure mode, **stop**. Either:
- Fix the underlying cause (in AZ or in the LLD or in boostgauge spawn-state)
- Cut a new spawn-state-v2 if the fix lives on boostgauge main
- Cut speedrun-v3 on AZ if the fix is structural

The 42-attempt budget is for the recording run-up + the actual attempts. Burn 5 attempts on a fixable problem is wasteful; fix once, attempt cleanly.

---

## 8. References

- `docs/speedrun/0004-route-v3.md` — architectural reference. **The runbook (this doc) is the operator-facing how-to; the route is the why.**
- `docs/audit-results/0001-...md` and `0002-...md` — historical audit; feature-arc and spec-quality references.
- `AssemblyZero/docs/babysit-protocol.md` — what to expect during AZ workflow runs (read once if you haven't).
- `AssemblyZero/docs/prompts/gemini-rotation-instructions.md` — quota-exhaustion recovery.
- `AssemblyZero/tools/run_requirements_workflow.py` — the LLD workflow.
- `AssemblyZero/tools/run_implement_from_lld.py` — the implementation workflow.

**Memory rules in scope during a recorded attempt:**
- `feedback-speedrun-no-dry-runs` — no off-camera rehearsal.
- `feedback-az-tools-user-runs-script` — classic-PAT-using AZ tools stay user-driven.
- `feedback-fword-censorship` — profanity removed entirely from any commit or saved content.
- `feedback-verify-external-service-behavior` — verify, don't assert, on PyPI/GitHub/Cloudflare specifics.
