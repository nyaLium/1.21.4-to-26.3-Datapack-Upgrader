"""Byte-faithful text IO.

A data pack is a source tree authored by many people over years: some files are
UTF-8 with BOM, some use CRLF, some have no trailing newline.  Rewriting a file
must not churn those details, otherwise the change report turns into noise.
"""

from __future__ import annotations

import io
import os
from dataclasses import dataclass

BOM = b"\xef\xbb\xbf"


@dataclass
class TextFile:
    path: str
    text: str        # normalised to "\n"
    bom: bool
    newline: str     # "\n" or "\r\n"
    final_newline: bool

    def render(self) -> bytes:
        body = self.text
        if self.newline != "\n":
            body = body.replace("\n", self.newline)
        data = body.encode("utf-8")
        if self.bom:
            data = BOM + data
        return data

    def encode_like(self, text: str) -> bytes:
        body = text
        if self.newline != "\n":
            body = body.replace("\n", self.newline)
        data = body.encode("utf-8")
        return (BOM + data) if self.bom else data


def read_text(path: str) -> TextFile:
    with open(path, "rb") as handle:
        raw = handle.read()
    bom = raw.startswith(BOM)
    if bom:
        raw = raw[len(BOM):]
    text = raw.decode("utf-8", errors="strict")
    newline = "\r\n" if "\r\n" in text else "\n"
    final_newline = text.endswith(("\n", "\r"))
    normalised = text.replace("\r\n", "\n").replace("\r", "\n")
    return TextFile(path, normalised, bom, newline, final_newline)


def write_text(doc: TextFile, text: str | None = None) -> None:
    body = doc.text if text is None else text
    if doc.final_newline and not body.endswith("\n"):
        body += "\n"
    if not doc.final_newline:
        body = body.rstrip("\n")
    with open(doc.path, "wb") as handle:
        handle.write(doc.encode_like(body))


def sha256_file(path: str) -> str:
    import hashlib

    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def walk(root: str, *exts: str):
    lowered = tuple(e.lower() for e in exts)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            if name.lower().endswith(lowered):
                yield os.path.join(dirpath, name)


def rel(root: str, path: str) -> str:
    return os.path.relpath(path, root).replace("\\", "/")


class TextReader(io.TextIOBase):  # pragma: no cover - convenience for scripts
    def __init__(self, doc: TextFile) -> None:
        self._doc = doc

    def read(self) -> str:  # type: ignore[override]
        return self._doc.text
