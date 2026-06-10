import json
from datetime import datetime
from pathlib import Path


class AuditLogAgent:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def list(self, limit=50):
        try:
            records = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            records = []
        return list(reversed(records[-limit:]))

    def record(self, **values):
        records = list(reversed(self.list(limit=1000)))
        entry = {
            "id": f"run-{len(records) + 1:04d}",
            "timestamp": datetime.now().astimezone().isoformat(),
            **values,
        }
        records.append(entry)
        self.path.write_text(json.dumps(records, indent=2), encoding="utf-8")
        return entry

