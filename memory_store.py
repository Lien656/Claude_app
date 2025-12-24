from pathlib import Path
import json
from datetime import datetime

MEMORY_FILE = Path.home() / ".claude_home" / "memory_store.json"
MEMORY_FILE.parent.mkdir(exist_ok=True)

def load_memory():
    if MEMORY_FILE.exists():
        return json.loads(MEMORY_FILE.read_text("utf-8"))
    return []

def save_memory(mem):
    MEMORY_FILE.write_text(
        json.dumps(mem, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

def add_or_update(topic, summary, keywords):
    mem = load_memory()
    for m in mem:
        if m["topic"] == topic:
            m["summary"] = summary
            m["keywords"] = keywords
            m["updated"] = datetime.now().isoformat()
            save_memory(mem)
            return
    mem.append({
        "topic": topic,
        "summary": summary,
        "keywords": keywords,
        "updated": datetime.now().isoformat()
    })
    save_memory(mem)
