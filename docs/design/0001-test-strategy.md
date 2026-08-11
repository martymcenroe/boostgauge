# 0001 — Test Strategy

**Status:** Active
**Created:** 2026-05-11
**Owner:** boostgauge project
**Supersedes:** —

---

## Purpose

This document is the canonical test strategy for boostgauge. Every LLD's "Test Plan" section references it; every new feature inherits its conventions unless the LLD explicitly overrides a section with rationale. It exists because tkinter + Pillow + Windows is a famously awkward stack to test, and ad-hoc per-feature decisions would burn the 42-run budget the AssemblyZero workflow allots before the speedrun could land anything.

---

## 1. Test Pyramid

| Tier | Directory | What lives here | Coverage target | Speed budget |
|---|---|---|---|---|
| Unit | `tests/unit/` | Pure logic with no I/O — math, state machines, parsers, data transforms. The `Telltale` peak-hold logic (issue #41) is the canonical example. | 100% line + branch on touched files | < 1 s for full suite |
| Render (pixel) | `tests/visual/` | Image-output comparisons. Renderer produces a `PIL.Image`; tests pixel-diff it against a committed baseline. | Every distinct render path covered by at least one fixture | < 5 s per test |
| Contract | `tests/contract/` | Data-shape and API-surface guards. e.g., the `Collector` protocol's methods + return types. | Every public interface | < 1 s per test |
| Integration | `tests/integration/` | Multiple internal modules wired together, no external processes. e.g., `Collector` → `Telltale` → renderer producing an image. | Happy path + one failure path per integration point | < 10 s per test |
| Smoke | `tests/smoke/` | "Does the package install and import." One test, runs in CI gate. | N/A — pass/fail signal | < 30 s |
| E2E | `tests/e2e/` | Spawn the app as a subprocess, verify it stays alive, send shutdown. | One healthcheck path | < 90 s |
| Benchmark | `tests/benchmark/` | Microbenchmarks. Run on demand, not gated. | N/A — perf regressions surfaced manually | N/A |
| Accessibility, compliance, harness, fixtures | their dirs | Reserved for later. No content yet. | N/A | N/A |

**Where the weight goes.** The unit and render tiers together carry ~90% of coverage. Integration and contract gate the seams. Smoke + E2E gate release. Everything else is advisory until a concrete need surfaces.

---

## 2. Tkinter Test Mode — Decision

**Chosen: Option C — render to off-screen `PIL.Image` first; tkinter Canvas is a display surface only.**

The gauge renderer is a pure function: state → `PIL.Image`. The tkinter Canvas receives that image and displays it. Tests exercise the renderer; they never instantiate `tkinter.Tk()`.

| | Option A (real Tk) | Option B (mock Canvas API) | **Option C (off-screen PIL)** |
|---|---|---|---|
| Headless | No (needs display) | Yes | **Yes** |
| Catches rendering bugs | Yes | No | **Yes** |
| Speed | Slow (Tk init + screenshot) | Fast | **Fast** |
| Stability | Flaky on Windows | Stable | **Stable** |
| Implementation cost | Low | Medium (mocks drift) | **Low once renderer is PIL-first** |
| Architectural debt | Couples tests to Tk | Tests stop catching real bugs | **Forces clean separation; reusable for export-PNG features** |

The Option C requirement is a load-bearing architectural constraint: **renderers MUST produce a `PIL.Image` they can return without ever calling a `tkinter` API.** The Tk Canvas is told to display the image via `PhotoImage`, but the renderer doesn't know about it. Any LLD that proposes drawing primitives onto a Canvas directly is rejected before review on this basis.

Rejected: Option A on flakiness + headless. Option B because the gauge's correctness IS the pixel output, and a mocked Canvas API silently passes when the renderer draws to the wrong coordinates.

---

## 3. Visual Regression Baseline

### Where baselines live

`tests/visual/baselines/{test_id}.png` — one image per fixture. Checked into git as binary blobs. Expected size: ~1–10 KB per baseline at gauge resolution (256×256).

### How baselines are generated

A test that fails for a missing baseline writes the candidate image to `tests/visual/baselines/{test_id}.png` *only* when invoked with `pytest --generate-baselines`. Otherwise a missing baseline is a hard fail. This forces an explicit human-in-the-loop step for new baselines; drift is impossible without an intentional regeneration command.

**The flag is registered in `tests/conftest.py`** via `pytest_addoption`, and is read with `request.config.getoption("--generate-baselines")`. It is stated here because it was mandated by this section for three months while nothing registered it: `pytest --generate-baselines` exited with "unrecognized arguments", and any test reading the option raised — making every spec that honoured this section unrunnable (ruling #271).

Baselines are **self-generated** from the first accepted render, never compared against the canonical photograph (aesthetic doc ruling #262). They guard against unintended drift from a render a human accepted.

### How a test fails

Pixel-diff with a tolerance band:

- **Identical bytes** → pass.
- **Byte-different but pixel-RMS ≤ 1.0 / 255** → pass with a warning (anti-aliasing noise; harmless).
- **Pixel-RMS > 1.0 / 255** → fail. Diff image written to `tests/visual/diffs/{test_id}.png` for triage.

Implementation: `PIL.ImageChops.difference()` + `ImageStat.Stat(diff).rms`.

### Curation workflow

When a render-tier test fails on intentional change:

1. Run `pytest tests/visual/ --generate-baselines` to overwrite the failing baselines.
2. Visually inspect the new baselines in the diff (git's image diff or a manual eyeball).
3. Commit the new baselines as part of the same PR that changed the renderer.

No automatic baseline acceptance. No CI-bot-fixes-baselines flow.

---

## 4. Install Smoke

One test, in `tests/smoke/test_install.py`:

```python
import subprocess
import sys
import venv
from pathlib import Path

def test_pip_install_smoke(tmp_path):
    """Fresh venv + pip install + import. Gates release."""
    venv_dir = tmp_path / "venv"
    venv.create(venv_dir, with_pip=True)
    pip = venv_dir / "Scripts" / "pip.exe"  # Windows; adapt path on POSIX
    subprocess.run([pip, "install", str(Path.cwd())], check=True)
    py = venv_dir / "Scripts" / "python.exe"
    subprocess.run([py, "-c", "import boostgauge"], check=True)
```

Runs in CI on release-tag pushes, not on every PR (it's slow). Failure blocks the tag.

---

## 5. E2E Healthcheck

One test, in `tests/e2e/test_healthcheck.py`:

```python
import subprocess
import sys
import time

def test_app_stays_alive_60_seconds():
    proc = subprocess.Popen([sys.executable, "-m", "boostgauge"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        time.sleep(60)
        assert proc.poll() is None, f"App died after {60} s: {proc.communicate()}"
    finally:
        proc.terminate()
        proc.wait(timeout=10)
```

Runs on release-tag, not on every PR. Failure blocks the tag. Future iterations may add a programmatic shutdown signal (e.g., named pipe, signal handler).

---

## 6. CI Integration

| Trigger | Tiers run | Gates |
|---|---|---|
| Every PR push | unit, render, contract, integration | Required check — blocks merge if any fails |
| Push to `main` | unit, render, contract, integration | Required (already gated upstream, but re-runs for safety) |
| Tag push (release) | All of the above + smoke + e2e | Required — blocks the release |
| Manual workflow dispatch | benchmark | Advisory; perf regressions surface in run log |

Coverage report (pytest-cov) on every PR. Threshold: 100% on touched files, no overall-repo gate (don't punish people working on un-instrumented modules).

The actual `.github/workflows/` YAML to enforce this is **out of scope for this strategy doc** — it lives in the auto-reviewer/CI deployment issue (#33). This doc defines what the workflows MUST enforce; the YAML is the implementation.

---

## 7. Spike commits — deferred

Issue #36's acceptance lists "a spike commit exists: one example test for each tier (unit, render-pixel, install-smoke, e2e), passing locally." Spike commits require minimal stubs of the renderer, package entry point, and app — none of which exist yet (greenfield repo). The spikes are filed as a follow-up so they land alongside the first real feature implementation rather than as standalone scaffolding that may drift before it has a consumer.

Follow-up: #42 — test: spike commits per test-strategy 0001 — one example per tier.

---

## 8. How LLDs reference this doc

Every LLD's "Test Plan" section MUST:

1. Reference this doc by path: `docs/design/0001-test-strategy.md`.
2. State which tiers from §1 apply to the feature.
3. List the specific test cases (file paths + behavior) for each applicable tier.
4. Note any overrides of §3 (visual baseline policy) — and the rationale.
5. **Carry the literal value of every quantity its pass criteria assert** (ruling #270). A pass criterion may cite the doc that binds a value, but it must also carry the value: `"needle pixels classify as candy-apple #F73923 (aesthetic doc §palette)"`, never `"correct color"` or `"per the aesthetic doc"`.

If an LLD's Test Plan does any of (a) skip mentioning this doc, (b) propose `tkinter.Tk()` in tests, (c) propose baseline auto-acceptance, (d) state a pass criterion in placeholder words — "correct", "appropriate", "expected", "proper", "as specified", "per the design doc" — where a value belongs — it is rejected without further review.

### Why (d) exists — a pointer is not a value

The spec stage is drafted from the LLD, not from the design docs. An LLD that points at a binding doc instead of quoting its numbers leaves the spec writer with nothing to assert, and the only test it can then write is one that verifies nothing (`assert isinstance(img, Image.Image)`), which the spec reviewer correctly rejects. That deadlock consumed seven spec-stage halts on issue #1 across 2026-08-10/11 — the numbers existed in the aesthetic doc the whole time and never reached the test writer.

The control case, from the same drafts: the needle-angle formula reached the LLD as literal numbers, because the LLD needed them to describe behaviour — and the spec immediately wrote five real assertions on it. Colours and sizes were referenced rather than carried, and produced placeholders.
