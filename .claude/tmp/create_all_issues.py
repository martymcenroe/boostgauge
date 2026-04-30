import subprocess
import json
import time

issues = [
    {
        "title": "[High] fix: enforce worktree isolation in run_requirements_workflow.py",
        "body": "resolve_roots() should detect if the target repo is the AssemblyZero root and refuse to run without a worktree (unless --no-worktree is present). This prevents accidental pollution of the main branch."
    },
    {
        "title": "[Critical] fix: filter LangChain Pydantic warnings from stderr to prevent workflow crashes",
        "body": "LangChain Pydantic V1 warnings in stderr cause CLI providers to report 'Unknown error' and crash. Use PYTHONWARNINGS='ignore' or filter stderr in subprocess.run wrappers."
    },
    {
        "title": "[Low] refactor: eliminate brittle sys.path hacks in CLI runners",
        "body": "Replace sys.path.insert(0, ...) with a proper editable install (pip install -e .) and standard imports."
    },
    {
        "title": "[Medium] refactor: decouple SQLite checkpoint logic from CLI runners",
        "body": "Move SqliteSaver and checkpoint logic from run_requirements_workflow.py into a core CheckpointManager."
    },
    {
        "title": "[Low] feat: non-blocking interactive selection with timeouts in CLI",
        "body": "Interactive input() calls can hang headless factory runs. Add timeouts or enforce TTY checks for --select."
    },
    {
        "title": "[Low] refactor: consolidate redundant git repository detection logic",
        "body": "Merge _detect_repo_from_path and _detect_repo_from_cwd into a unified GitProvider utility."
    },
    {
        "title": "[Low] ui: synchronize header timeout display with --timeout parameter",
        "body": "Ensure the printed header correctly reflects the value passed via --timeout (currently hardcoded to 30 mins)."
    },
    {
        "title": "[High] refactor: simplify workflow resumption using LangGraph native checkpoints",
        "body": "Replace the 130-line manual subgraph reconstruction for --resume-review (Issue #536) with native LangGraph resumption."
    },
    {
        "title": "[Medium] feat: comprehensive dry-run mode for requirements workflow",
        "body": "The --dry-run flag should execute the graph in a mock/dry mode to verify prompt generation and paths without LLM calls."
    },
    {
        "title": "[Medium] refactor: extract lineage version shifting to dedicated LineageManager",
        "body": "Move Standard 0012 lineage versioning (shifting to -n1) out of CLI scripts and into a LineageManager class."
    },
    {
        "title": "[Low] refactor: move string-based gate configuration to Pydantic models",
        "body": "Replace 'none'/'all'/'draft' string parsing with formal Enums or Pydantic models for GateConfig."
    },
    {
        "title": "[Low] docs: rename N_PONDER (Ponder Stibbons) to N_THOUGHT_REFINEMENT",
        "body": "Improve codebase clarity for contributors by removing obscure literary references in node naming."
    },
    {
        "title": "[Medium] fix: robust subprocess encoding handling for Windows (UTF-8/CP1252)",
        "body": "Use errors='replace' and dynamic encoding detection in subprocess.run to prevent UnicodeDecodeError on Windows machines."
    },
    {
        "title": "[High] refactor: implement WorkspaceContext to eliminate path prop-drilling",
        "body": "Create a unified WorkspaceContext object to manage assemblyzero_root and target_repo instead of passing Path objects through every function."
    },
    {
        "title": "[High] refactor: decompose run_requirements_workflow.py into modular components",
        "body": "Split the 1,200-line script into ui.py, batch.py, resumption.py, and a thin runner.py."
    }
]

for issue in issues:
    print(f"Creating issue: {issue['title']}...")
    try:
        cmd = [
            "gh", "issue", "create",
            "--repo", "martymcenroe/AssemblyZero",
            "--title", issue["title"],
            "--body", issue["body"]
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"  Success: {result.stdout.strip()}")
        time.sleep(1) # Prevent rate limiting
    except subprocess.CalledProcessError as e:
        print(f"  Error: {e.stderr.strip()}")
