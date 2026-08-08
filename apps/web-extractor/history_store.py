from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class HistoryStore:
    """Persist a small, local extraction history grouped by workflow."""

    def __init__(self, path: str | Path, max_per_mode: int = 50) -> None:
        self.path = Path(path)
        self.max_per_mode = max_per_mode
        self.lock = threading.Lock()

    def list(self, mode: str) -> list[dict[str, Any]]:
        with self.lock:
            entries = self._read()
        return [entry for entry in entries if entry.get("mode") == mode][: self.max_per_mode]

    def record(
        self,
        *,
        mode: str,
        source: str,
        path: str,
        label: str = "",
    ) -> dict[str, Any]:
        output_path = Path(path).expanduser()
        entry = {
            "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
            "mode": mode,
            "source": source,
            "path": str(output_path),
            "label": label.strip() or output_path.stem,
        }
        with self.lock:
            entries = [
                item
                for item in self._read()
                if not (item.get("mode") == mode and item.get("path") == str(output_path))
            ]
            entries.insert(0, entry)
            retained: list[dict[str, Any]] = []
            mode_counts: dict[str, int] = {}
            for item in entries:
                item_mode = str(item.get("mode", ""))
                count = mode_counts.get(item_mode, 0)
                if count >= self.max_per_mode:
                    continue
                retained.append(item)
                mode_counts[item_mode] = count + 1
            self._write(retained)
        return entry

    def _read(self) -> list[dict[str, Any]]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return []
        if not isinstance(data, list):
            return []
        return [item for item in data if isinstance(item, dict)]

    def _write(self, entries: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temp_file:
                temp_name = temp_file.name
                json.dump(entries, temp_file, ensure_ascii=False, indent=2)
                temp_file.write("\n")
            os.replace(temp_name, self.path)
            temp_name = None
        finally:
            if temp_name:
                Path(temp_name).unlink(missing_ok=True)
