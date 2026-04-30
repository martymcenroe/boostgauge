import sys
import re

file_path = 'C:/Users/mcwiz/Projects/AssemblyZero-825/assemblyzero/core/llm_provider.py'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

old_re = r'_PYDANTIC_WARNING_RE = re\.compile\(\n\s+r".*?",\n\s+re\.IGNORECASE,\n\)'
new_re = '_PYDANTIC_WARNING_RE = re.compile(\n    r".*PydanticDeprecatedSince\d+.*|.*pydantic.*(DeprecationWarning|UserWarning).*|.*Core Pydantic V1.*",\n    re.IGNORECASE,\n)'

content = re.sub(old_re, new_re, content, flags=re.DOTALL)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
