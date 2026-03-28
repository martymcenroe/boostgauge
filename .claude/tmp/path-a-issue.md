### Objective
Enable AssemblyZero to operate completely offline or against a local specification file instead of requiring a live GitHub repository and issue tracker.

### Motivation
To prove AssemblyZero is a functioning, idempotent software factory, we need the ability to run the entire pipeline (Requirements -> LLD -> Implementation) repeatedly from a pristine starting state. Relying on live GitHub issues makes idempotency impossible because a single run mutates the issue state, creates PRs, and leaves the repository dirty. A "Local Forge" mode allows us to point AssemblyZero at a `blueprint/issues.json` file to generate a project locally without hitting GitHub APIs or needing a remote repo.

### Proposed Changes
1. Modify `tools/run_requirements_workflow.py` and `tools/run_implement_from_lld.py` to accept a `--local-spec <path/to/issues.json>` argument.
2. Abstract the GitHub issue fetching logic so it can cleanly fall back to reading from the local JSON file.
3. Handle state transitions locally (e.g., updating a local `.assemblyzero-state.json`) instead of commenting on/closing live GitHub issues.