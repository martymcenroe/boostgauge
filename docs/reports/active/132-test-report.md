# 132 — Test Report (Issue #32)

**Issue:** [#32 — chore: bootstrap Python project — initialize Poetry + pytest](https://github.com/martymcenroe/boostgauge/issues/32)
**Branch:** `32-bootstrap-poetry`
**Author:** Claude Opus 4.7 (1M context)
**Date:** 2026-05-11

## Scope

Project bootstrap; no application code, no tests authored. Acceptance is "test runner installed and discoverable, zero tests collected cleanly." That is the entire test surface for this issue.

## Verification

```
$ cd /c/Users/mcwiz/Projects/boostgauge-32
$ poetry run pytest --version
pytest 9.0.3

$ poetry run pytest --collect-only
============================= test session starts =============================
platform win32 -- Python 3.14.0, pytest-9.0.3, pluggy-1.6.0
rootdir: C:\Users\mcwiz\Projects\boostgauge-32
configfile: pyproject.toml
testpaths: tests
plugins: cov-7.1.0
collected 0 items

========================= no tests collected in 0.03s =========================
$ echo $?
5
```

| Check | Method | Expected | Actual |
|---|---|---|---|
| pytest installed in project venv | `poetry run pytest --version` | non-error output | ✓ `pytest 9.0.3` |
| pytest reads `[tool.pytest.ini_options]` | "configfile: pyproject.toml" in output | present | ✓ |
| testpaths honored | "testpaths: tests" in output | present | ✓ |
| Collection runs without errors | exit code 0 or 5 (no tests is fine) | exit 5 | ✓ — pytest's documented behavior for "zero tests collected, no errors" |
| `src/` on sys.path via conftest | `python -c "import sys; print('src' in str(sys.path))"` (via venv) | True once `src/boostgauge/` lands | conftest written; verifiable when first source module lands |

## Notes on Exit Code 5

`pytest` returns exit code 5 specifically when no tests are collected. This is distinct from exit code 1 (failures), 2 (interrupted), 3 (internal error), or 4 (usage error). The acceptance criterion "runs cleanly (zero tests collected, no errors)" maps to exit 5.

The AssemblyZero workflow's red/green phase gates should be aware of this convention — if `verify_red_phase` expects exit 0 with zero tests, it may misread exit 5 as failure. Not in scope for this issue, flagging here for downstream observers.

## Regression Risk

Bootstrap only. No code changed, no behavior altered, no public surface added. Risk: none.
