import sys
import os

file_path = 'C:/Users/mcwiz/Projects/AssemblyZero-825/tools/run_requirements_workflow.py'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add --no-worktree to parse_args
old_arg = '        dest="yes",\n        help="Auto-confirm regeneration prompts (shifts existing lineage to n-1)",\n    )'
new_arg = old_arg + '\n\n    # Issue #825: Worktree isolation\n    parser.add_argument(\n        "--no-worktree",\n        action="store_true",\n        help="Allow running in the AssemblyZero root directory (not recommended)",\n    )'

content = content.replace(old_arg, new_arg)

# 2. Add worktree check to resolve_roots
old_resolve = '        # Fall back to CWD detection\n        target_repo = _detect_repo_from_cwd()\n\n    return assemblyzero_root, target_repo'
new_resolve = '        # Fall back to CWD detection\n        target_repo = _detect_repo_from_cwd()\n\n    # Issue #825: Enforce worktree isolation for AssemblyZero itself\n    if target_repo.resolve() == assemblyzero_root.resolve():\n        if not getattr(args, "no_worktree", False):\n            print()\n            print("=" * 60)\n            print("ERROR: Refusing to run in the AssemblyZero root directory.")\n            print("=" * 60)\n            print("To prevent branch pollution, you must run in an isolated worktree.")\n            print()\n            print("1. Create a worktree:")\n            print("   git worktree add ../AssemblyZero-ISSUE -b branch-name")\n            print()\n            print("2. Run the workflow pointing to the worktree:")\n            print("   python tools/run_requirements_workflow.py ... --repo ../AssemblyZero-ISSUE")\n            print()\n            print("If you MUST run on main, use the --no-worktree escape hatch.")\n            print("=" * 60)\n            sys.exit(1)\n\n    return assemblyzero_root, target_repo'

content = content.replace(old_resolve, new_resolve)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
