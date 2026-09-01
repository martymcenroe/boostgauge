# ADR 0001: All Process-Derived Metrics Come From One Sweep Per Tick

**Status:** Accepted
**Date:** 2026-08-09
**Amended:** 2026-09-01 — the sweep mechanism (§2.1, §3, §4), by operator
ruling on #405. The principle is unchanged; the call that implements it is.
**Issues:** #224 (the cadence ruling this completes), #233 and #234 (the
conflicts that forced it to be written down as architecture), #405 (the
measurement that replaced the mechanism)

## 1. Context

The collector reads four metrics that require knowledge of the process
table: process count, ConPTY count, total handle count, and unleashed
session count. Walking the process table is the expensive operation in
this program, and the monitor exists to watch a machine under load, so
the monitor being a load is self-defeating. The `< 1% CPU` acceptance
criterion in #4 exists to catch exactly that.

The original issue text accumulated per-metric prescriptions from before
this was understood: a per-metric cadence table (removed by the #224
ruling), a recommendation of "direct Win32 API for ConPTY-specific
counting," and a process-count row suggesting `Get-Process` or
`len(psutil.pids())`. Each of those implies its own walk or its own
independent OS query. The requirements-consistency gate caught both
survivors contradicting the single-sweep mandate during a live roll
(2026-08-09, run-issue4-181102) and filed #233 and #234. The operator's
ruling, verbatim in spirit: everything must be derived in a single
iteration.

The first version of this ADR then bound the sweep to
`psutil.process_iter` and named `cmdline` as the expensive attribute,
because `cmdline` forces the OS to open every process. Measured before
implementation on 2026-09-01 (#405), that was wrong on both counts:
`cmdline` cost 13 ms per tick; `num_handles` cost 422 ms, because psutil
also opens every process to read it — one `OpenProcess` per row, every
tick. That is 21 % of a core at a 2 s tick, on a machine with 373
processes, against a criterion of 1 %. A single
`NtQuerySystemInformation(SystemProcessInformation)` call returns name,
pid and handle count for every process without opening any, in 2.2 ms,
and its figures cross-check against psutil's to the row. The mandate
was right; the mechanism it named could not satisfy the criterion the
mandate exists to protect.

## 2. Decision

**One enumeration of the process table per tick. Every process-derived
metric is computed from that one stream. Nothing else may enumerate or
independently query the process list.**

Precisely:

1. **The sweep** is a single
   `NtQuerySystemInformation(SystemProcessInformation)` call per tick,
   made through `ctypes`, whose returned block is walked once. Each
   entry yields the row's image name, pid and `HandleCount`. Per-row
   attribute reads on rows the walk identified (§2.5) are part of the
   one iteration — the mandate forbids additional walks and independent
   queries, never the attribute reads the single walk is for.
2. **Process count** is the number of rows the sweep yielded. Never
   `len(psutil.pids())`, never `psutil.process_iter`, never a
   `Get-Process` subprocess — each is an independent query against the
   OS process list.
3. **ConPTY count** is the number of console-host rows observed in the
   sweep (`name` in {`conhost.exe`, `OpenConsole.exe`},
   case-insensitive). This is a documented proxy: each ConPTY allocation
   is hosted by such a process.
4. **Handle count** is the sum of `HandleCount` across the sweep's rows.
   The sweep reports it for every row, including rows the process
   cannot open, so it is complete where psutil's `num_handles` sum was
   not.
5. **Unleashed session count** is the number of rows that are Python
   interpreter processes (`name` is a Python executable, e.g.
   `python.exe` / `pythonw.exe`, case-insensitive) AND whose `cmdline`
   matches the unleashed signature (`unleashed-c-*.py`). `cmdline` is
   read per row, for exactly the rows the sweep identified as Python
   interpreters, via `psutil.Process(pid).cmdline()` — about twenty rows
   on the operator's machine, measured at well under a millisecond in
   total. Both conditions are predicates over the same sweep's rows. A
   non-Python process carrying the filename in its command line — an
   editor, a grep, a shell — is not a session (ruling #239, 2026-08-10).
6. **Non-process metrics are outside the mandate.** System memory comes
   from `psutil.virtual_memory()` — a single direct call that enumerates
   nothing. The mandate governs the process table, not every syscall.
7. A row that dies between the sweep and its per-row `cmdline` read
   (`NoSuchProcess`, `AccessDenied`) is skipped, not retried — a retry is
   a second query.

## 3. Consequences

- The collector's cost per tick is one system call plus a handful of
  per-row reads, whatever the metric count. Adding a future
  process-derived metric means reading another field of the block the
  sweep already returned, or a computation over its rows, never a walk.
  That is the test of any future collector change: if it enumerates, it
  is wrong.
- ConPTY counting by host-process proxy trades exactness for cost. If
  the proxy ever proves too loose, the remedy is a better predicate over
  the SAME sweep (for example, filtering by parent pid, which the block
  also carries), not a second enumeration.
- The sweep is Windows-only by construction, which is what
  `WindowsCollector` is for. A future `LinuxCollector` or
  `MacCollector` supplies its own one-enumeration sweep and must meet
  the same criterion; `psutil.process_iter` is not automatically it.
- `psutil` remains a dependency for `virtual_memory()` and for the
  per-row `cmdline` read. It is not the sweep. Any change that makes
  psutil enumerate the process table reintroduces the 21 %.
- The struct layout the sweep parses is the x64
  `SYSTEM_PROCESS_INFORMATION` header (104 bytes to `SessionId`). A wrong
  offset would miscount silently, so the parse is pinned by a test that
  cross-checks its row count and console-host count against
  `psutil.process_iter` on the running machine (§4).

## 4. Test hooks

- A unit test stubs the system call and asserts all four
  process-derived metrics derive from one call (call count == 1 per
  tick).
- A test pins that no collector module references `psutil.pids`,
  `psutil.process_iter`, `Get-Process`, or a second
  `NtQuerySystemInformation` per tick (source-level pin, same style as
  the no-force sweep pin in AssemblyZero).
- A live cross-check (Windows only): the sweep's row count and
  console-host count equal `psutil.process_iter`'s ±1, and its handle
  total is within 1 % of psutil's `num_handles` sum.
- A benchmark: the sweep's mean `process_time` over eight ticks is under
  20 ms — the `< 1% CPU at 2 s` criterion stated as a number the test
  can fail on.

## 5. References

- #224 — the cadence ruling (drop per-metric frequencies; collect once).
- #233 / #234 — the gate-caught contradictions this ADR retires.
- #239 — the session-count predicate ruling (Python interpreter AND
  cmdline signature, both over the one sweep).
- #405 — the measurement that replaced `process_iter` with the one
  system call (422 ms vs 2.2 ms per tick).
- `docs/design/0001-test-strategy.md` — test tiers the hooks above land in.
