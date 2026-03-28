import sys
import os

file_path = 'C:/Users/mcwiz/Projects/AssemblyZero-825/assemblyzero/core/llm_provider.py'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Issue #826: Filter Pydantic warnings from stderr by setting PYTHONWARNINGS=ignore in the subprocess environment.
# This ensures that these warnings don't leak into the LLM provider's error detection.

# 1. Update subprocess.Popen calls in ClaudeCLIProvider.invoke
old_popen = 'proc = subprocess.Popen(\n                    cmd,\n                    stdin=subprocess.PIPE,\n                    stdout=subprocess.PIPE,\n                    stderr=subprocess.PIPE,\n                    text=True,\n                    encoding="utf-8",\n                    cwd=temp_path,  # None when not using temp dir (= inherit)\n                    creationflags=creation_flags,\n                )'

new_popen = 'env = os.environ.copy()\n                env["PYTHONWARNINGS"] = "ignore"\n\n                proc = subprocess.Popen(\n                    cmd,\n                    stdin=subprocess.PIPE,\n                    stdout=subprocess.PIPE,\n                    stderr=subprocess.PIPE,\n                    text=True,\n                    encoding="utf-8",\n                    cwd=temp_path,  # None when not using temp dir (= inherit)\n                    creationflags=creation_flags,\n                    env=env,\n                )'

content = content.replace(old_popen, new_popen)

# 2. Update subprocess.run in _kill_process_tree (just to be safe)
old_kill = 'subprocess.run(\n                ["taskkill", "/F", "/T", "/PID", str(pid)],\n                capture_output=True,\n                timeout=10,\n            )'

new_kill = 'env = os.environ.copy()\n            env["PYTHONWARNINGS"] = "ignore"\n            subprocess.run(\n                ["taskkill", "/F", "/T", "/PID", str(pid)],\n                capture_output=True,\n                timeout=10,\n                env=env,\n            )'

content = content.replace(old_kill, new_kill)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
