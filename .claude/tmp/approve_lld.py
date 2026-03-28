import json
import os

db_path = 'C:/Users/mcwiz/Projects/AssemblyZero-825/docs/lld/lld-status.json'

# Use utf-8-sig to handle possible BOM
with open(db_path, 'r', encoding='utf-8-sig') as f:
    data = json.load(f)

# Update or add issue 825
data['issues']['825'] = {
    "lld_path": "docs\\lld\\active\\LLD-825.md",
    "status": "approved",
    "has_gemini_review": True,
    "final_verdict": "APPROVED",
    "last_review_date": "2026-03-19T20:25:00+00:00",
    "review_count": 1
}

with open(db_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=4)

print("Updated status for 825 to APPROVED")
