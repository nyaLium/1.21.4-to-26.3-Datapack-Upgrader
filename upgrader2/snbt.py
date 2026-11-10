"""A small, span-aware SNBT reader/writer.

Minecraft 1.21.5 turned every in-command data structure into NBT, so command
surgery means SNBT surgery.  This module parses an SNBT value while recording
the source span it came from, which lets the converters replace exactly the
region they changed instead of rewriting whole lines.

Supported grammar (1.21.5+): compounds, lists, typed arrays, quoted strings
with escape sequences, typed number literals (b/s/l/f/d, signedness suffixes,
hex/binary, underscores, free-form decimals), booleans, and the ``bool()`` /
``uuid()`` operations (kept verbatim).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_STRING_SAFE = set("0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_-+.")
_KEY_SAFE = set("0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_-+.")
_ESCAPES = {
    "n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "s": " ",
    "\\": "\\", "'": "'", '"': '"',
}


class SnbtError(ValueError):
    pass


class Byte(int):
    suffix = "b"


class Short(int):
    suffix = "s"


class Long(int):
    suffix = "l"


class Float(float):
    suffix = "f"


class Double(float):
    suffix = "d"


class Str(str):
    """A string that remembers which quote character it used."""

    quote = '"'

    def __new__(cls, value: str, quote: str = '"'):
        obj = super().__new__(cls, value)
        obj.quote = quote
        return obj


class Raw(str):
    """An expression kept verbatim (bool(...), uuid(...), ...)."""


class Array(list):
    def __init__(self, values=(), kind: str = "int"):
        super().__init__(values)
        self.kind = kind


@dataclass
class Node:
    kind: str
    start: int
    end: int
    value: Any = None
    text: str = ""
    pairs: list[tuple[str, "Node"]] = field(default_factory=list)
    items: list["Node"] = field(default_factory=list)

    def to_py(self) -> Any:
        if self.kind == "compound":
            return {key: value.to_py() for key, value in self.pairs}
        if self.kind == "list":
            return [item.to_py() for item in self.items]
        if self.kind == "array":
            return Array([item.to_py() for item in self.items], self.value)
        return self.value


def parse(text: str, pos: int = 0, *, allow_bare: bool = False) -> Node:
    parser = _Parser(text, allow_bare=allow_bare)
    node = parser.value(pos)
    parser.skip_ws()
    return node


def parse_value(text: str, pos: int = 0, *, allow_bare: bool = False) -> tuple[Any, Node]:
    node = parse(text, pos, allow_bare=allow_bare)
    return node.to_py(), node


def try_parse(text: str, pos: int = 0, *, allow_bare: bool = False) -> Node | None:
    try:
        return parse(text, pos, allow_bare=allow_bare)
    except SnbtError:
        return None


class _Parser:
    def __init__(self, text: str, *, allow_bare: bool = False) -> None:
        self.text = text
        self.n = len(text)
        self.allow_bare = allow_bare

    # -- helpers -----------------------------------------------------------
    def skip_ws(self) -> None:
        text, n = self.text, self.n
        pos = getattr(self, "pos", 0)
        while pos < n and text[pos] in " \t\r\n":
            pos += 1
        self.pos = pos

    def peek(self) -> str:
        self.skip_ws()
        return self.text[self.pos] if self.pos < self.n else ""

    def expect(self, char: str) -> None:
        self.skip_ws()
        if self.pos >= self.n or self.text[self.pos] != char:
            raise SnbtError(f"expected {char!r} at {self.pos}")
        self.pos += 1

    # -- values ------------------------------------------------------------
    def value(self, pos: int | None = None) -> Node:
        if pos is not None:
            self.pos = pos
        self.skip_ws()
        start = self.pos
        if start >= self.n:
            raise SnbtError("unexpected end of input")
        char = self.text[start]
        if char == "{":
            return self.compound(start)
        if char == "[":
            return self.list_or_array(start)
        if char in "\"'":
            return self.quoted(start)
        return self.bare(start)

    def compound(self, start: int) -> Node:
        self.pos = start + 1
        pairs: list[tuple[str, Node]] = []
        while True:
            self.skip_ws()
            if self.pos >= self.n:
                raise SnbtError("unterminated compound")
            if self.text[self.pos] == "}":
                self.pos += 1
                break
            key, key_node = self.key()
            self.expect(":")
            value = self.value()
            pairs.append((key, value))
            self.skip_ws()
            if self.pos < self.n and self.text[self.pos] == ",":
                self.pos += 1
                continue
            if self.pos < self.n and self.text[self.pos] == "}":
                self.pos += 1
                break
            raise SnbtError(f"expected ',' or '}}' at {self.pos}")
        return Node("compound", start, self.pos, pairs=pairs,
                    text=self.text[start:self.pos])

    def key(self) -> tuple[str, Node]:
        self.skip_ws()
        char = self.text[self.pos] if self.pos < self.n else ""
        if char in "\"'":
            node = self.quoted(self.pos)
            return str(node.value), node
        start = self.pos
        while self.pos < self.n and self.text[self.pos] in _KEY_SAFE:
            self.pos += 1
        if start == self.pos:
            raise SnbtError(f"bad key at {start}")
        raw = self.text[start:self.pos]
        return raw, Node("string", start, self.pos, Str(raw), raw)

    def list_or_array(self, start: int) -> Node:
        self.pos = start + 1
        self.skip_ws()
        if self.pos + 1 < self.n and self.text[self.pos] in "BIL" and self.text[self.pos + 1] == ";":
            kind = {"B": "byte", "I": "int", "L": "long"}[self.text[self.pos]]
            self.pos += 2
            items: list[Node] = []
            while True:
                self.skip_ws()
                if self.pos >= self.n:
                    raise SnbtError("unterminated array")
                if self.text[self.pos] == "]":
                    self.pos += 1
                    break
                items.append(self.value())
                self.skip_ws()
                if self.pos < self.n and self.text[self.pos] == ",":
                    self.pos += 1
                    continue
                if self.pos < self.n and self.text[self.pos] == "]":
                    self.pos += 1
                    break
                raise SnbtError(f"expected ',' or ']' at {self.pos}")
            return Node("array", start, self.pos, value=kind, items=items,
                        text=self.text[start:self.pos])
        items = []
        while True:
            self.skip_ws()
            if self.pos >= self.n:
                raise SnbtError("unterminated list")
            if self.text[self.pos] == "]":
                self.pos += 1
                break
            items.append(self.value())
            self.skip_ws()
            if self.pos < self.n and self.text[self.pos] == ",":
                self.pos += 1
                continue
            if self.pos < self.n and self.text[self.pos] == "]":
                self.pos += 1
                break
            raise SnbtError(f"expected ',' or ']' at {self.pos}")
        return Node("list", start, self.pos, items=items, text=self.text[start:self.pos])

    def quoted(self, start: int) -> Node:
        quote = self.text[start]
        i = start + 1
        out: list[str] = []
        text, n = self.text, self.n
        while i < n:
            char = text[i]
            if char == "\\":
                if i + 1 >= n:
                    raise SnbtError("dangling escape")
                nxt = text[i + 1]
                if nxt in _ESCAPES:
                    out.append(_ESCAPES[nxt])
                    i += 2
                    continue
                if nxt == "x":
                    code = int(text[i + 2:i + 4], 16)
                    out.append(chr(code))
                    i += 4
                    continue
                if nxt == "u":
                    code = int(text[i + 2:i + 6], 16)
                    out.append(chr(code))
                    i += 6
                    continue
                if nxt == "U":
                    code = int(text[i + 2:i + 10], 16)
                    out.append(chr(code))
                    i += 10
                    continue
                if nxt == "N" and i + 2 < n and text[i + 2] == "{":
                    close = text.find("}", i + 3)
                    if close == -1:
                        raise SnbtError("bad \\N escape")
                    out.append(text[i:close + 1])
                    i = close + 1
                    continue
                # unknown escape: keep the character itself
                out.append(nxt)
                i += 2
                continue
            if char == quote:
                self.pos = i + 1
                value = "".join(out)
                return Node("string", start, self.pos, Str(value, quote),
                            text[start:self.pos])
            out.append(char)
            i += 1
        raise SnbtError("unterminated string")

    def bare(self, start: int) -> Node:
        text, n = self.text, self.n
        i = start
        while i < n and text[i] not in " ,]}":
            i += 1
        token = text[start:i]
        if not token:
            raise SnbtError(f"empty token at {start}")
        if token in ("true", "false"):
            self.pos = i
            return Node("bool", start, i, token == "true", token)
        if i < n and text[i] == "(" and token.isidentifier():
            depth = 0
            while i < n:
                if text[i] == "(":
                    depth += 1
                elif text[i] == ")":
                    depth -= 1
                    if depth == 0:
                        i += 1
                        break
                i += 1
            self.pos = i
            raw = text[start:i]
            return Node("raw", start, i, Raw(raw), raw)
        number = _parse_number(token)
        if number is not None:
            self.pos = i
            return Node("number", start, i, number, token)
        if self.allow_bare:
            self.pos = i
            return Node("string", start, i, Str(token, ""), token)
        raise SnbtError(f"not SNBT at {start}: {token[:20]!r}")


def _parse_number(token: str) -> Any | None:
    if not token:
        return None
    body = token
    suffix = ""
    if body[-1] in "bBsSlLfFdD":
        suffix = body[-1].lower()
        body = body[:-1]
        if body and body[-1] in "uU":
            body = body[:-1]
    if not body:
        return None
    lowered = body.lower()
    try:
        if lowered.startswith(("0x", "-0x", "+0x")):
            value = int(body, 16)
            return _typed(value, suffix)
        if lowered.startswith(("0b", "-0b", "+0b")):
            value = int(body, 2)
            return _typed(value, suffix)
        if suffix in ("f", "d") or any(ch in body for ch in ".eE"):
            value = float(body.replace("_", ""))
            if suffix == "f":
                return Float(value)
            if suffix == "d":
                return Double(value)
            return value
        value = int(body.replace("_", ""), 10)
        return _typed(value, suffix)
    except ValueError:
        return None


def _typed(value: int, suffix: str) -> Any:
    if suffix == "b":
        return Byte(value)
    if suffix == "s":
        return Short(value)
    if suffix == "l":
        return Long(value)
    return value


# ---------------------------------------------------------------------------
# serialisation
# ---------------------------------------------------------------------------

def dumps(value: Any) -> str:
    if isinstance(value, Raw):
        return str(value)
    if isinstance(value, Str):
        return _quote(str(value), value.quote)
    if isinstance(value, str):
        return _quote(value, '"')
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Array):
        prefix = {"byte": "B;", "int": "I;", "long": "L;"}[value.kind]
        return "[" + prefix + ",".join(dumps(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{" + ",".join(f"{_dump_key(key)}:{dumps(val)}" for key, val in value.items()) + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(dumps(item) for item in value) + "]"
    if isinstance(value, Byte):
        return f"{int(value)}b"
    if isinstance(value, Short):
        return f"{int(value)}s"
    if isinstance(value, Long):
        return f"{int(value)}l"
    if isinstance(value, Float):
        return f"{_float_text(value)}f"
    if isinstance(value, Double):
        return f"{_float_text(value)}d"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return _float_text(value)
    raise TypeError(f"cannot serialise {type(value)!r}")


def _float_text(value: float) -> str:
    if value != value or value in (float("inf"), float("-inf")):
        return repr(value)
    text = repr(float(value))
    return text


def _dump_key(key: str) -> str:
    if key and all(ch in _KEY_SAFE for ch in key) and key[0].isdigit() is False:
        return key
    return _quote(key, '"')


def _quote(text: str, quote: str) -> str:
    if not quote:
        quote = '"'
    out = [quote]
    for char in text:
        if char == "\\":
            out.append("\\\\")
        elif char == quote:
            out.append("\\" + char)
        elif char == "\n":
            out.append("\\n")
        elif char == "\t":
            out.append("\\t")
        elif char == "\r":
            out.append("\\r")
        else:
            out.append(char)
    out.append(quote)
    return "".join(out)


def dump_node(node: Node, prefer_original: bool = True) -> str:
    return node.text if prefer_original else dumps(node.to_py())
