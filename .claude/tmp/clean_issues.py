import json
import re

try:
    with open('blueprint/issues.json', 'r', encoding='utf-8-sig') as f:
        issues = json.load(f)

    final_issues = []
    seen_titles = set()
    
    # We want to keep 1-29. 30-33 are Codex, the N/A are Gemini.
    for i in issues:
        num = i.get('number')
        title = i.get('title', '')
        
        # Keep 1-29 explicitly
        if num and isinstance(num, int) and num <= 29:
            final_issues.append(i)
        elif num == 24: # sometimes MVP gets re-ordered
            final_issues.append(i)
            
    # Write back the cleaned list
    with open('blueprint/issues.json', 'w', encoding='utf-8') as f:
        json.dump(final_issues, f, indent=2)
        
    print(f"Cleaned! Remaining issues: {len(final_issues)}")
    for i in final_issues:
        print(f"  {i.get('number')} - {i.get('title')}")

except Exception as e:
    print(f"Error: {e}")
