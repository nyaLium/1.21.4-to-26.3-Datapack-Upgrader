"""JSON IO that keeps a file's indentation, BOM and trailing newline."""

from __future__ import annotations

import json
import re
from typing import Any

from .textio import TextFile, read_text, write_text

_INDENT_RE = re.compile(r"\n([ \t]+)\S")


def detect_indent(text: str) -> str:
    match = _INDENT_RE.search(text)
    if not match:
        return "  "
    indent = match.group(1)
    if indent.startswith("\t"):
        return "\t"
    return indent if len(indent) <= 8 else "  "


def load(path: str) -> Any:
    doc = read_text(path)
    return json.loads(doc.text)


def dump_like(obj: Any, doc: TextFile) -> str:
    """Serialise with tab indentation (2.1: rewritten JSON is tab-indented)."""
    return json.dumps(obj, ensure_ascii=False, indent="\t")


def save(path: str, obj: Any) -> None:
    doc = read_text(path)
    text = dump_like(obj, doc)
    write_text(doc, text)


def dumps_compact(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
