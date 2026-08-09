# Speed-Run Route v4 — boostgauge zero-to-PyPI

**Status:** Operational
**Last updated:** 2026-07-15
**Supersedes:** `0004-route-v3.md`. v3's core idea (attempt branches, main never moves) survives; v4 corrects what v3 got wrong about the tooling and folds in what the overnight hardening campaign proved (issue #96).

---

## 1. What changed v3 → v4

1. **The tooling claim is now true.** v3 §8.2 said the build pipeline targets the checked-out branch. It didn't — that was fixed in AssemblyZero on 2026-07-14 (AssemblyZero#1759): every pull request the pipeline opens now targets whatever branch the repo is standing on. Proven live seven times on `hardening-run-1`.
2. **One command per feature.** The take uses `tools/orchestrate.py` (design → review → spec → test-first code → PR, self-cleaning), not the old two-script sequence — which was missing a required middle step and never opened PRs at all.
3. **The arc gains #41.** The gauge renderer (#1) and the memory needles (#2) both consume #41's peak-hold class; building them without it forces the design stage to invent an interface that doesn't exist. New arc: **#7 → #41 → #1 → #4 → #2 → #5**.
4. **Proven, not hoped:** the pipeline built two real features end-to-end during hardening (config #7 and telltale #41 — the latter 14/14 tests, 100% coverage), with design PRs merging themselves into the attempt branch and main untouched throughout.

## 2. Mission (unchanged)

One continuous recording: empty `src/` → working app → live on PyPI. The video markets AssemblyZero; stars on that repo are the win condition; boostgauge is the demonstration.

## 3. The model

- `speedrun-spawn-v1` (a git tag) is the frozen starting line. It must point at current main before attempt 1 (issue #88).
- Each recorded attempt = a branch `speedrun-attempt-N` off the tag. Everything the pipeline produces merges into that branch. **Main never moves during a take.**
- Failed attempts keep their branch (the lab notebook) and burn their version number: attempt N publishes v0.1.N−1, success or not, no reuse.
- AssemblyZero may improve between attempts; record its commit hash per attempt in the run log.

## 4. Per-phase beats

| Phase | Issue | On screen when it lands |
|---|---|---|
| 1 | #7 config file + CLI | config loads, printed to console |
| 2 | #41 peak-hold logic | tests green — the algorithm of the signature feature |
| 3 | #1 gauge face | **first visible product** — the chrome-and-black dial |
| 4 | #4 Windows data collector | the needle moves with live system data |
| 5 | #2 memory needles | spike the machine, watch the peak hold |
| 6 | #5 always-on-top app | `poetry run boostgauge` — the real thing |
| 7 | tag + publish | `pip install boostgauge` works from PyPI |

Commands, timings, and recovery live in the runbook (`docs/runbooks/10001-speedrun-execution-runbook.md`). This doc stays the why.

## 5. Known behaviors (by design, don't be surprised on camera)

- Issues do NOT auto-close when PRs merge into the attempt branch (GitHub only auto-closes on main). Close them on camera.
- The automated reviewer runs on attempt-branch PRs only after issue #90's trigger change lands — do that before attempt 1.
- Leftover side-folders (`boostgauge-N`) can refuse deletion for a minute after a phase while child processes let go — wait, don't force.

## 6. Status of old open decisions

- Attempt-branch model: **live and proven** (was v3's design bet).
- pyproject email + links: **done** (May 22).
- PyPI name + publisher: **done**; publish workflow proven with v0.0.0.
- Landing page, wiki: **done**.
- Remaining before attempt 1: #88 (re-point the tag), #90 (reviewer trigger), and the operator ruling on AssemblyZero#1779 (what the pipeline should do when its final checks fail — see that issue).
