"""JSON-lines audit trail: every tool call (name, args, result summary, duration)."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class Audit:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("")

    def log(self, tool: str, args: dict[str, Any], result: dict[str, Any], duration_s: float = 0.0) -> None:
        rec = {"ts": round(time.time(), 3), "tool": tool, "args": args, "result": result,
               "duration_s": round(duration_s, 3)}
        with self.path.open("a") as f:
            f.write(json.dumps(rec, default=str) + "\n")
