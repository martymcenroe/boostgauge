import sys

file_path = 'C:/Users/mcwiz/Projects/AssemblyZero-825/assemblyzero/core/llm_provider.py'

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if '_PYDANTIC_WARNING_RE' in line and 'r".*PydanticDeprecatedSince' in line:
        new_lines.append('    r".*PydanticDeprecatedSince\d+.*|.*pydantic.*(DeprecationWarning|UserWarning).*|.*Core Pydantic V1.*",\n')
    else:
        new_lines.append(line)

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
