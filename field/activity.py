import json
import threading
from collections import deque
from datetime import datetime, timezone
from pathlib import Path


class Activity:
    """Append-only activity log for the device, kept on disk and in memory."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.lock = threading.Lock()
        self.items = deque(maxlen=400)
        if self.path.exists():
            for line in self.path.read_text().splitlines()[-400:]:
                try:
                    self.items.append(json.loads(line))
                except ValueError:
                    pass

    def log(self, kind: str, message: str, **detail):
        e = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "kind": kind, "message": message, **detail}
        with self.lock:
            self.items.append(e)
            with self.path.open("a") as f:
                f.write(json.dumps(e) + "\n")
        return e

    def recent(self, n=100):
        with self.lock:
            return list(self.items)[-n:][::-1]
