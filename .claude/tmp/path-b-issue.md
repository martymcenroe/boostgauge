### Objective
Create an end-to-end orchestration script that spins up ephemeral GitHub repositories to run the full AssemblyZero pipeline without mutating the original repository.

### Motivation
To prove AssemblyZero works seamlessly with real GitHub infrastructure, we need a way to run idempotent demonstration loops ("The Disposable Repository" approach). This script should automate the creation of a temporary repository, populate it with issues from a local blueprint (`blueprint/issues.json`), run the existing AssemblyZero workflows against it, and then cleanly tear it down. This proves the full E2E Git-Ops lifecycle of the software factory without requiring local hacks to the workflow scripts.

### Proposed Architecture
1. Add a master script `tools/build_disposable_factory.ps1` (or bash equivalent).
2. Uses the `gh` CLI to `repo create <name> --private`.
3. Parses `blueprint/issues.json` and uses `gh issue create` to populate the new repo's backlog.
4. Executes the standard `run_requirements_workflow.py` and `run_implement_from_lld.py` pointing to the ephemeral repo.
5. Cleans up by deleting the repository at the end or on failure.