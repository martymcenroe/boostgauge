# 0003 — Campaign Timing Dashboard (Spec)

**Status:** Approved spec, build deferred (tracked in the build issue)
**Author:** agent session 2026-08-01, operator-directed
**Scope:** boostgauge speedrun campaign; generator intended to be repo-generic

## 1. Purpose

One stacked-bar chart answering "where did the campaign's wall-clock go":
runs over time, with each day's bar split into **run time** (the pipeline
working) and **diagnose+fix time** (a human/agent repairing the pipeline
between failed runs). ~100 runs exist across the campaign.

## 2. Data sources (inventory, ranked)

| Source | Location | What it gives | Era |
|---|---|---|---|
| Events logs | `data/speedrun/runs/run-issue{N}-{HHMMSS}-events.log` | START / LAUNCH / CHILD EXITED / EXIT lines, **local-time** stamps (`2026-07-31 10:20:40 START issue=#7 ... pid=...`) | 2026-07-31 onward (59 files at spec time) |
| Heartbeat logs | same dir, `*-heartbeat.log` | 15s beats; last beat = time of death for uncatchable kills | same |
| Orchestrator stdout | same dir, `run-issue{N}-{HHMMSS}.log` | per-stage table (`lld passed 54.2s` ...), `[ORCHESTRATOR] Duration: Ns` | same |
| Launcher narration | `detached-launcher.log` (append-only, multi-run) | redraw markers (`#N attempt K/M failed ... redrawing`), gate self-heal lines | 2026-07-31 evening onward |
| Campaign ledger | boostgauge issue #96 comments (via `gh`) | per-roll narrative timings for the pre-instrumentation era (run8–run11b: e.g. 313s, 984s, 1244s rolls) | 2026-07-28 → 07-30 |
| Dry-run artifacts | `data/speedrun/dryrun-2026-07-28/` | demo outputs, partial timing | 07-28 |
| AZ fix record | AssemblyZero PR/issue timestamps (`gh`), issues #2015–#2068 | evidence for classifying gaps as fix time | 07-31 onward |

**Runs are saved** — the log triplet persists per run; nothing needs
reconstruction for the instrumented era. The pre-instrumentation era is
reconstructed from ledger comments only as far as it supports honest bars
(coarser is fine; mark those bars visually as reconstructed).

## 3. Definitions and conventions (normative)

1. **Run** — one `START` line in an events log. One roll of one issue.
2. **Run time** — `EXIT` timestamp − `START` timestamp. When no `EXIT`
   exists (uncatchable kill), use last heartbeat − `START` and tag the run
   `killed`.
3. **Timezone** — **local US Central throughout.** The logs are already
   local wall-clock. No UTC anywhere in parsing, bucketing, labels, or
   output. (Do not "normalize" through UTC; a run at 23:50 belongs to the
   date printed in its START line.)
4. **Bucketing convention — run START date.** A run started 23:50 that
   exits 01:20 counts entirely on the start date. This is THE convention;
   applies to fix-gaps too (attributed to the failed run's start date).
5. **Diagnose+fix time** — for each **failed** run: the gap between its
   terminal timestamp and the next `START`/`LAUNCH` in any events log or
   the launcher narration, classified:
   - gap ≤ 120s → **automation overhead** (self-heal/redraw); excluded
     from both segments (it is noise at day scale).
   - gap > 120s **and** ≥1 AssemblyZero commit landed on origin/main
     within the gap (`git log --since --until` on AZ main, local time) →
     **diagnose+fix time**, attributed to the failed run's start date.
   - gap > 120s with no AZ commit in it → **unattributed idle**; excluded,
     but totaled in a footnote so exclusions are visible, not silent.
   The last run of the dataset has no following start; its gap is nil.
6. **Successful runs** contribute run time only.

## 4. The chart

- **Form:** stacked bar, one bar per local date.
- **Segments:** bottom = total run time (hours); top = total diagnose+fix
  time (hours).
- **Per-bar annotation at the top: the day's run count** (this is the
  "number of runs as a legend at the top" requirement — count sits above
  each bar; the segment legend itself is standard corner placement).
- **X labels:** local dates (`Jul 28` … ). **Y:** hours.
- Reconstructed-era bars get a lighter hatch + footnote.
- Follow the dataviz skill when building (load it before writing chart
  code); matplotlib; PNG output to `data/speedrun/analysis/` plus the
  parsed per-run table as CSV beside it (`runs.csv`: start_local, issue,
  outcome, run_seconds, fix_seconds_attributed, source).

## 5. Generator

- Lives in AssemblyZero `tools/` (fleet tooling home), reads a target
  repo's `data/speedrun/runs/` via `--repo`, plus `gh` for ledger-era
  reconstruction (optional flag `--ledger-issue 96`).
- Read-only; no mutation of any repo state; output only under the target
  repo's `data/speedrun/analysis/`.
- Deterministic: same inputs → same CSV bytes (sorted), so diffs are
  reviewable.

## 6. Out of scope

- Building it now (context-constrained session end; build tracked in the
  build issue).
- Per-stage stacking (lld/spec/impl) — noted as a natural v2; the stdout
  stage tables already carry the data.
- Cost/token accounting.

## 7. Acceptance (for the build)

- Parses all 59+ instrumented events logs without error; killed runs get
  heartbeat-fallback durations.
- A run crossing midnight appears only on its start date (test with a
  synthetic 23:50→01:20 log).
- Gap classification produces zero fix-time on a day with no AZ commits.
- Chart renders with per-bar run counts and the two segments; numbers in
  the CSV sum to the bar heights.
