import sys
import os

file_path = 'C:/Users/mcwiz/Projects/AssemblyZero-825/tools/run_implementation_spec_workflow.py'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add --no-worktree to parse_args
old_arg = '        dest="human_gate_enabled",\n        help="Enable manual approval for spec drafting and review results",\n    )'
new_arg = old_arg + '\n\n    # Issue #825: Worktree isolation\n    parser.add_argument(\n        "--no-worktree",\n        action="store_true",\n        help="Allow running in the AssemblyZero root directory (not recommended)",\n    )'

content = content.replace(old_arg, new_arg)

# 2. Add worktree check to resolve_roots
old_resolve = '        target_repo = _detect_repo_from_cwd()\n\n    return assemblyzero_root, target_repo'
new_resolve = '        target_repo = _detect_repo_from_cwd()\n\n    # Issue #825: Enforce worktree isolation for AssemblyZero itself\n    if target_repo.resolve() == assemblyzero_root.resolve():\n        if not getattr(args, "no_worktree", False):\n            print()\n            print("=" * 60)\n            print("ERROR: Refusing to run in the AssemblyZero root directory.")\n            print("=" * 60)\n            print("To prevent branch pollution, you must run in an isolated worktree.")\n            print()\n            print("1. Create a worktree:")\n            print("   git worktree add ../AssemblyZero-ISSUE -b branch-name")\n            print()\n            print("2. Run the workflow pointing to the worktree:")\n            print("   python tools/run_implementation_spec_workflow.py ... --repo ../AssemblyZero-ISSUE")\n            print()\n            print("If you MUST run on main, use the --no-worktree escape hatch.")\n            print("=" * 60)\n            sys.exit(1)\n\n    return assemblyzero_root, target_repo'

content = content.replace(old_resolve, new_resolve)

# 3. Fix relative LLD path resolution bug
old_lld_resolve = '    if args.lld:\n        lld_path = str(Path(args.lld).resolve())'
new_lld_resolve = '    if args.lld:\n        # Resolve relative to target_repo if not absolute\n        p = Path(args.lld)\n        if not p.is_absolute():\n            lld_path = str((target_repo / p).resolve())\n        else:\n            lld_path = str(p.resolve())'

content = content.replace(old_lld_resolve, new_lld_resolve)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
