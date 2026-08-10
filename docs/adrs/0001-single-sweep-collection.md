# ADR 0001: All Process-Derived Metrics Come From One Sweep Per Tick

**Status:** Accepted
**Date:** 2026-08-09
**Issues:** #224 (the cadence ruling this completes), #233 and #234 (the
conflicts that forced it to be written down as architecture)

## 1. Context

The collector reads four metrics that require knowledge of the process
table: process count, ConPTY count, total handle count, and unleashed
session count. Walking the process table is the expensive operation in
this program — `cmdline` in particular forces the OS to open every
process — and the monitor exists to watch a machine under load, so the
monitor being a load is self-defeating. The `< 1% CPU` acceptance
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

## 2. Decision

**One enumeration of the process table per tick. Every process-derived
metric is computed from that one stream. Nothing else may enumerate or
independently query the process list.**

Precisely:

1. **The sweep** is a single `psutil.process_iter(attrs=["name",
   "num_handles", "cmdline"])` enumeration per tick. Per-process
   attribute fetches performed by the iterator DURING the walk are part
   of the one iteration — the mandate forbids additional walks and
   independent queries, never the attribute reads the single walk is
   for.
2. **Process count** is the number of rows the sweep yielded. Never
   `len(psutil.pids())`, never a `Get-Process` subprocess — each is an
   independent query against the OS process list.
3. **ConPTY count** is the number of console-host processes observed in
   the sweep (`name` in {`conhost.exe`, `OpenConsole.exe`},
   case-insensitive). This is a documented proxy: each ConPTY allocation
   is hosted by such a process. The previously recommended direct Win32
   enumeration is rejected — it was the second walk #233 caught.
4. **Handle count** is the sum of `num_handles` across the sweep's rows.
5. **Unleashed session count** is the number of rows that are Python
   interpreter processes (`name` is a Python executable, e.g.
   `python.exe` / `pythonw.exe`, case-insensitive) AND whose `cmdline`
   matches the unleashed signature (`unleashed-c-*.py`). Both conditions
   are predicates over the same sweep's rows. A non-Python process
   carrying the filename in its command line — an editor, a grep, a
   shell — is not a session (ruling #239, 2026-08-10).
6. **Non-process metrics are outside the mandate.** System memory comes
   from `psutil.virtual_memory()` — a single direct call that enumerates
   nothing. The mandate governs the process table, not every syscall.
7. A row that dies mid-walk (`NoSuchProcess`, `AccessDenied` on an
   attribute) is skipped, not retried — a retry is a second query.

## 3. Consequences

- The collector's cost per tick is one walk, whatever the metric count.
  Adding a future process-derived metric means adding an attribute to
  the sweep or a computation over its rows, never a walk. That is the
  test of any future collector change: if it enumerates, it is wrong.
- ConPTY counting by host-process proxy trades exactness for cost. If
  the proxy ever proves too loose, the remedy is a better predicate over
  the SAME sweep (for example, filtering by parent), not a second
  enumeration.
- `psutil` is the sole process-table dependency. The Win32/ctypes route
  survives only as a fallback strategy if psutil itself proves
  unavailable, and any such fallback must preserve the one-sweep rule.

## 4. Test hooks

- A unit test stubs `process_iter` and asserts all four metrics derive
  from one call (call count == 1 per tick).
- A test pins that no collector module references `psutil.pids`,
  `Get-Process`, or a second `process_iter` per tick (source-level pin,
  same style as the no-force sweep pin in AssemblyZero).

## 5. References

- #224 — the cadence ruling (drop per-metric frequencies; collect once).
- #233 / #234 — the gate-caught contradictions this ADR retires.
- #239 — the session-count predicate ruling (Python interpreter AND
  cmdline signature, both over the one sweep).
- `docs/design/0001-test-strategy.md` — test tiers the hooks above land in.
