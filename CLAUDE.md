# CLAUDE.md - boostgauge Project

You are a team member on the boostgauge project, not a tool.

## FIRST: Read AssemblyZero Core Rules

**Before doing any work, read the AssemblyZero core rules:**
`C:\Users\mcwiz\Projects\AssemblyZero\CLAUDE.md`

That file contains core rules that apply to ALL projects:
- Safety rules (destructive commands, secret handling, path restrictions)
- Worktree isolation rules
- Path format rules (Windows vs Unix)
- Two-Strike Rule (loop detection)
- When Blocked or Uncertain protocol

## Security Hooks (Enforced Automatically)

This repo has a PreToolUse hook deployed in `.claude/hooks/`:
- **secret-file-guard.sh** — Blocks Read/Write/Edit/Grep/NotebookEdit on secret files (`.env`, `.dev.vars`, AWS credentials, etc.)

It is wired in `.claude/settings.json` and enforced automatically.
Do NOT modify or remove this hook.

(Two additional hooks — `secret-guard.sh` for Bash-command output guarding and `bash-gate.sh` for destructive-command gating — are planned but not yet implemented. Track via fleet tooling in `martymcenroe/AssemblyZero`.)

**This file adds boostgauge-specific rules ON TOP of those core rules.**

---

## What This Project Is

BoostGauge is a lightweight, always-on-top system monitor styled like a racing tachometer. It tracks ConPTY allocations, memory usage, process counts, and handles — collapsing them into a single composite gauge with peak-hold (telltale) needles at 1m, 10m, 1h, and all-time windows.

Built for developers running multiple concurrent AI coding sessions who need real-time visibility into invisible resource pressure.

## Tech Stack

- **Language:** Python 3.10+
- **GUI:** tkinter + PIL/Pillow (render gauge face as image, overlay dynamic needles)
- **System metrics:** psutil (cross-platform) + Win32 API (ConPTY-specific)
- **Tray icon:** pystray
- **Packaging:** PyPI (pip install boostgauge) + PyInstaller (standalone .exe/.app)
- **License:** MIT

## Key Files

- `src/boostgauge/app.py` — main entry point
- `src/boostgauge/gauge.py` — tachometer renderer
- `src/boostgauge/telltale.py` — peak-hold needle logic
- `src/boostgauge/collector.py` — abstract data collector + platform detection
- `src/boostgauge/collectors/windows.py` — Windows-specific metrics
- `src/boostgauge/config.py` — configuration management

---

## Project Identifiers

- **Repository:** `martymcenroe/boostgauge`
- **Project Root (Windows):** `C:\Users\mcwiz\Projects\boostgauge`
- **Project Root (Unix):** `/c/Users/mcwiz/Projects/boostgauge`
- **Worktree Pattern:** `boostgauge-{IssueID}` (e.g., `boostgauge-45`)

---

## Project-Specific Workflow Rules

### Required Workflow

- **Docs before Code:** Write the LLD (`docs/lld/active/`) before writing code
- **Worktree before code:** `git worktree add ../boostgauge-{ID} -b {ID}-short-desc`
- **Push immediately:** `git push -u origin HEAD`

### Reports Before Merge (PRE-MERGE GATE)

**Before ANY PR merge, you MUST:**

1. Create `docs/reports/active/1{IssueID}-implementation-report.md`
2. Create `docs/reports/active/1{IssueID}-test-report.md`
3. Wait for orchestrator review

---

## Documentation Structure

This project uses the **1xxxx numbering scheme** (project-specific implementations):

| Directory | Range | Contents |
|-----------|-------|----------|
| `docs/lld/` | 1xxxx | Low-level designs |
| `docs/reports/` | 1xxxx | Implementation & test reports |
| `docs/standards/` | 00xxx | Project-specific standards |
| `docs/adrs/` | 00xxx | Architecture Decision Records |

---

## Session Logging

At end of session, append a summary to `docs/session-logs/YYYY-MM-DD.md`.

---

## GitHub CLI Safety

- ALWAYS use `--repo martymcenroe/boostgauge` explicitly
- NEVER rely on default repo inference

---

## You Are Not Alone

Other agents may work on this project. Check `docs/session-logs/` for recent context.
