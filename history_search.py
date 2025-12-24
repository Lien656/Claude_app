from pathlib import Path
import json

HISTORY_FILE = Path.home() / ".claude_home" / "history.json"

def search(query, limit=20):
    if not HISTORY_FILE.exists():
        return []

    data = json.loads(HISTORY_FILE.read_text("utf-8"))
    q = query.lower()

    results = []
    for msg in data:
        if q in msg["content"].lower():
            results.append(msg)
        if len(results) >= limit:
            break
    return results
