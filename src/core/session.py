from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path


class SessionJournal:
    def __init__(self, path: Path, max_lines: int = 1000) -> None:
        self.path = path
        self.max_lines = max_lines

    def append_add(self, paths: Sequence[Path | str]) -> None:
        self._append("add", [str(path) for path in paths])

    def append_remove(self, paths: Sequence[Path | str]) -> None:
        self._append("remove", [str(path) for path in paths])

    def append_reorder(self, paths: Sequence[Path | str]) -> None:
        self._append("reorder", [str(path) for path in paths])

    def append_clear(self) -> None:
        self._append("clear", [])

    def snapshot(self, paths: Sequence[Path | str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"op": "snapshot", "paths": [str(path) for path in paths]}) + "\n",
            encoding="utf-8",
        )

    def load(self) -> list[str]:
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        ordered: list[str] = []
        for line in lines:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            op = event.get("op")
            paths = event.get("paths", [])
            if not isinstance(paths, list) or not all(isinstance(item, str) for item in paths):
                continue
            if op in ("reorder", "snapshot"):
                ordered = list(paths)
            elif op == "add":
                ordered.extend(path for path in paths if path not in ordered)
            elif op == "remove":
                removed = set(paths)
                ordered = [path for path in ordered if path not in removed]
            elif op == "clear":
                ordered = []
        return ordered

    def _append(self, op: str, paths: list[str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        event = {"op": op, "paths": paths, "ts": datetime.now(timezone.utc).isoformat()}
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event) + "\n")
        self._compact_if_needed()

    def _compact_if_needed(self) -> None:
        try:
            with self.path.open("r", encoding="utf-8") as stream:
                count = sum(1 for _ in stream)
            if count > self.max_lines:
                self.snapshot(self.load())
        except OSError:
            pass
