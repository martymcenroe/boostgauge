import sys
import os

file_path = 'C:/Users/mcwiz/Projects/AssemblyZero-825/tools/run_implementation_spec_workflow.py'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add --no-worktree to create_argument_parser
old_arg = '        help="Max API cost in USD before halting (default $3.00, 0=unlimited)",\n    )'
new_arg = old_arg + '\n\n    # Issue #825: Worktree isolation\n    parser.add_argument(\n        "--no-worktree",\n        action="store_true",\n        help="Allow running in the AssemblyZero root directory (not recommended)",\n    )'

if old_arg in content:
    content = content.replace(old_arg, new_arg)
else:
    # Fallback to after --budget
    content = content.replace('"--budget",', '"--budget",\n    parser.add_argument("--no-worktree", action="store_true"),')

# 2. Path resolution fix (ensure resolve_roots is called)
# In run_implementation_spec_workflow.py, resolve_roots IS called in main().
# But let's fix the build_initial_state LLD resolution bug.
old_lld_resolve = '    if args.lld:\n        lld_path = str(Path(args.lld).resolve())'
new_lld_resolve = '    if args.lld:\n        # Resolve relative to target_repo if not absolute\n        p = Path(args.lld)\n        if not p.is_absolute():\n            lld_path = str((target_repo / p).resolve())\n        else:\n            lld_path = str(p.resolve())'

content = content.replace(old_lld_resolve, new_lld_resolve)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
