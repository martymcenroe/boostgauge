import sys

file_path = 'C:/Users/mcwiz/Projects/AssemblyZero-825/tools/run_requirements_workflow.py'

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip_until = None

for i, line in enumerate(lines):
    if 'no-worktree' in line:
        continue # skip all previous attempts
    
    if '--yes' in line:
        new_lines.append(line)
        # Add the argument after the --yes argument block
        # We need to find where the --yes argument block ends
        j = i + 1
        while j < len(lines) and ')' not in lines[j]:
            new_lines.append(lines[j])
            j += 1
        new_lines.append(lines[j]) # the ) line
        new_lines.append('\n')
        new_lines.append('    parser.add_argument(\n')
        new_lines.append('        "--no-worktree",\n')
        new_lines.append('        action="store_true",\n')
        new_lines.append('        help="Allow running in the AssemblyZero root directory (not recommended)",\n')
        new_lines.append('    )\n')
        # Skip original lines until after the next blank line or something
        # Actually, since I'm skipping 'no-worktree' lines, this should be fine
        # We need to avoid duplicating the append if multiple --yes matches
        pass 
    elif 'return assemblyzero_root, target_repo' in line:
        new_lines.append('    # Issue #825: Enforce worktree isolation for AssemblyZero itself\n')
        new_lines.append('    if target_repo.resolve() == assemblyzero_root.resolve():\n')
        new_lines.append('        if not getattr(args, "no_worktree", False):\n')
        new_lines.append('            print()\n')
        new_lines.append('            print("=" * 60)\n')
        new_lines.append('            print("ERROR: Refusing to run in the AssemblyZero root directory.")\n')
        new_lines.append('            print("=" * 60)\n')
        new_lines.append('            print("To prevent branch pollution, you must run in an isolated worktree.")\n')
        new_lines.append('            print()\n')
        new_lines.append('            print("1. Create a worktree:")\n')
        new_lines.append('            print("   git worktree add ../AssemblyZero-ISSUE -b branch-name")\n')
        new_lines.append('            print()\n')
        new_lines.append('            print("2. Run the workflow pointing to the worktree:")\n')
        new_lines.append('            print("   python tools/run_requirements_workflow.py ... --repo ../AssemblyZero-ISSUE")\n')
        new_lines.append('            print()\n')
        new_lines.append('            print("If you MUST run on main, use the --no-worktree escape hatch.")\n')
        new_lines.append('            print("=" * 60)\n')
        new_lines.append('            sys.exit(1)\n')
        new_lines.append('\n')
        new_lines.append(line)
    elif '825' in line:
        continue # skip previous attempts
    else:
        new_lines.append(line)

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
