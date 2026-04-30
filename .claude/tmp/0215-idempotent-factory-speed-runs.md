# ADR 0215: Idempotent Factory Speed Runs

## Status
Proposed

## Context
As AssemblyZero matures into a functioning autonomous software factory, we need the ability to demonstrate and test its end-to-end capabilities without manual intervention. Currently, AssemblyZero interacts with live GitHub issues, mutating issue states, creating pull requests, and leaving the target repository in a "dirty" state. This prevents repeatable, quantitative, and qualitative "speed runs" where the system can be repeatedly executed from the exact same initial specification (the "Blueprint") to generate a finished, tested application.

To produce public demonstrations (e.g., YouTube recordings) or conduct rigorous performance testing, the factory execution must be **idempotent**. A single, unmodified specification must yield a completed software product across 5, 10, or 100 consecutive runs without requiring any human cleanup or resetting of the environment.

## Decision
We will establish an Idempotent Execution Model (the "Clean Room" architecture) composed of two strict environments:

1. **The Blueprint (Immutable Specification):** A static directory (e.g., `blueprint/`) containing pristine, code-free artifacts—`issues.json`, a foundational `README.md`, and pre-rendered assets (like Golden Images for headless UI testing). This directory is strictly read-only during the execution run.
2. **The Factory Floor (Volatile Environment):** The target environment where the code is generated. Before every execution, this environment is wiped completely clean and re-hydrated exclusively from the Blueprint.

To facilitate this execution, AssemblyZero must support disconnected or disposable workflows:
*   **The Local Forge:** AssemblyZero orchestrator scripts will bypass the GitHub API, reading requirements directly from a local flag (e.g., `--local-spec blueprint/issues.json`) and managing state entirely locally without pushing to remote.
*   **The Disposable Repository:** An orchestration wrapper script will provision a fresh, ephemeral GitHub repository for every run, seed it with issues from the Blueprint, execute AssemblyZero normally, and dispose of the repository upon completion.

## Consequences
*   **Positive:** Enables automated, highly repeatable quality assurance and benchmarking of the AssemblyZero agentic workflows (quantitative "speed runs").
*   **Positive:** Proves the viability of "zero-human" software generation strictly from static specifications.
*   **Positive:** Allows for pristine, flawless recordings of the system's capabilities for Go-To-Market (GTM) campaigns without fear of the agent getting blocked by dirty state.
*   **Negative:** Requires maintaining separate logic for interacting with local JSON specifications versus live GitHub APIs (for the Local Forge path).
*   **Negative:** Ephemeral repositories (if chosen) will increase test execution time due to API overhead, rate limits, and repository provisioning.