"""Small JSON preferences file (last port, baud rate, folders...)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def prefs_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    return Path(base) / "ft891prog"


class Prefs:
    def __init__(self, path: Path | None = None):
        self.path = path or (prefs_dir() / "settings.json")
        self.data: dict[str, Any] = {}
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.data = {}

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        except OSError:
            pass
