"""Change report: aggregates rule hits, warnings and errors."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

MAX_SAMPLES = 3


@dataclass
class Entry:
    rule: str
    path: str
    count: int = 0
    samples: list[str] = field(default_factory=list)


class Report:
    def __init__(self) -> None:
        self._entries: dict[tuple[str, str], Entry] = {}
        self.warnings: list[str] = []
        self.errors: list[str] = []
        self.files_scanned = 0
        self.function_lines = 0
        self._warn_seen: set[str] = set()

    # -- mutation ----------------------------------------------------------
    def change(self, rule: str, path: str, detail: str = "", n: int = 1) -> None:
        key = (rule, path)
        entry = self._entries.get(key)
        if entry is None:
            entry = Entry(rule, path)
            self._entries[key] = entry
        entry.count += n
        if detail and len(entry.samples) < MAX_SAMPLES:
            entry.samples.append(detail)

    def warn(self, message: str, path: str = "") -> None:
        text = f"{path}: {message}" if path else message
        if text in self._warn_seen:
            return
        self._warn_seen.add(text)
        self.warnings.append(text)

    def error(self, message: str, path: str = "") -> None:
        text = f"{path}: {message}" if path else message
        if text not in self.errors:
            self.errors.append(text)

    # -- views -------------------------------------------------------------
    def by_rule(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for entry in self._entries.values():
            out[entry.rule] = out.get(entry.rule, 0) + entry.count
        return dict(sorted(out.items(), key=lambda kv: (-kv[1], kv[0])))

    def files_by_rule(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for entry in self._entries.values():
            out[entry.rule] = out.get(entry.rule, 0) + 1
        return dict(sorted(out.items(), key=lambda kv: (-kv[1], kv[0])))

    def rules_with_samples(self) -> list[Entry]:
        return sorted(self._entries.values(), key=lambda e: (e.rule, e.path))

    def touched_files(self) -> set[str]:
        return {entry.path for entry in self._entries.values()}

    def to_json(self) -> dict[str, Any]:
        return {
            "rules": self.by_rule(),
            "files_by_rule": self.files_by_rule(),
            "entries": [
                {
                    "rule": entry.rule,
                    "path": entry.path,
                    "count": entry.count,
                    "samples": entry.samples,
                }
                for entry in self.rules_with_samples()
            ],
            "warnings": self.warnings,
            "errors": self.errors,
            "files_scanned": self.files_scanned,
            "function_lines": self.function_lines,
        }
