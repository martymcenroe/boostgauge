import json

try:
    with open('blueprint/issues.json', 'r', encoding='utf-8') as f:
        data = f.read()
        # Handle potential encoding weirdness (e.g. if one of the agents wrote UTF-16 again)
        if data.startswith('\x00') or '\x00' in data[:100]:
            with open('blueprint/issues.json', 'r', encoding='utf-16') as f2:
                issues = json.load(f2)
        else:
            issues = json.loads(data)
            
    for i in issues:
        print(f"ID: {i.get('number', 'N/A')} - {i.get('title', 'N/A')}")
except Exception as e:
    print(f"Error: {e}")
