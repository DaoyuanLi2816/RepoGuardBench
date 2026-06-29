"""Tiny structured logger so we never depend on a heavy logging stack."""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Dict


class JsonLogger:
    def __init__(self, path: str | Path | None = None, echo: bool = True) -> None:
        self.path = Path(path) if path else None
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.echo = echo

    def log(self, level: str, event: str, **fields: Any) -> None:
        import json
        rec: Dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "level": level,
            "event": event,
        }
        rec.update(fields)
        line = json.dumps(rec, ensure_ascii=False)
        if self.path is not None:
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        if self.echo:
            print(line, file=sys.stderr, flush=True)

    def info(self, event: str, **fields: Any) -> None:
        self.log("INFO", event, **fields)

    def warn(self, event: str, **fields: Any) -> None:
        self.log("WARN", event, **fields)

    def error(self, event: str, **fields: Any) -> None:
        self.log("ERROR", event, **fields)
