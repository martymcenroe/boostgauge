# CLAUDE.md - boostgauge Project

You are a team member on the boostgauge project, not a tool.

## Project Identifiers

- **Repository:** `martymcenroe/boostgauge`
- **Project Root (Windows):** `C:\Users\mcwiz\Projects\boostgauge`
- **Project Root (Unix):** `/c/Users/mcwiz/Projects/boostgauge`
- **Worktree Pattern:** `boostgauge-{IssueID}` (e.g., `boostgauge-45`)

## Project-Specific Context

**Stack:** Python (Poetry), published to PyPI. Source under `src/boostgauge/`,
entry points in `[tool.poetry.scripts]`, release via
`.github/workflows/release.yml` on tag push. Pending-publisher registration
on PyPI documented in runbook 0934.

**What this is:** lightweight, always-on-top system monitor styled like a
racing tachometer. Tracks ConPTY allocations, memory, process counts, and
handles — composite gauge with peak-hold (telltale) needles at 1m, 10m, 1h,
and all-time windows. Built for developers running multiple concurrent AI
coding sessions who need real-time visibility into invisible resource
pressure.

**GUI / packaging stack:**

- GUI: `tkinter` + `PIL`/`Pillow` — render gauge face as image, overlay
  dynamic needles
- System metrics: `psutil` (cross-platform) + Win32 API (ConPTY-specific)
- Tray icon: `pystray`
- Standalone packaging: `PyInstaller` (`.exe` / `.app`)

**Key modules:**

- `src/boostgauge/app.py` — main entry point
- `src/boostgauge/gauge.py` — tachometer renderer
- `src/boostgauge/telltale.py` — peak-hold needle logic
- `src/boostgauge/collector.py` — abstract data collector + platform detection
- `src/boostgauge/collectors/windows.py` — Windows-specific metrics
- `src/boostgauge/config.py` — configuration management

## Workflow Override — GUI Testing Strategy

The universal CLAUDE.md covers fleet-wide test rules. boostgauge **overrides**
those with a stricter GUI-testing contract documented at
`docs/design/0001-test-strategy.md`:

- **Option C** is the canonical GUI testing approach: the renderer produces
  a `PIL.Image`; `tkinter.Tk()` is never instantiated in tests.
- **Visual regression baselines** under `tests/visual/baselines/` require an
  explicit `--generate-baselines` flag — no implicit auto-accept.

Per strategy doc §8, an LLD whose Test Plan does any of:

1. skips mentioning `docs/design/0001-test-strategy.md`,
2. proposes `tkinter.Tk()` in tests, or
3. proposes baseline auto-acceptance

is **rejected at review without further analysis**. Keep this rule and §8 of
the strategy doc in sync — if one changes, change the other.
