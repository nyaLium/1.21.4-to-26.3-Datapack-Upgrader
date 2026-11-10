"""Audit (and optionally prune) dangling cross-file references in a 26.3 pack.

Usage:
    python tools/check_references.py <pack-dir>            # report only
    python tools/check_references.py <pack-dir> --delete   # delete broken JSON

26.3 makes a load error in advancement / loot_table / recipe / predicate /
item_modifier (and number_provider / slot_source) fatal for the whole world
(Mojira MC-310325), so a JSON file whose internal references cannot be
resolved is a landmine.  This tool resolves references that are answerable from
the pack itself; ``minecraft:`` and foreign namespaces are assumed to exist.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from upgrader2 import integrity  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    root = os.path.abspath(argv[1])
    delete = "--delete" in argv[2:]

    issues = integrity.scan(root)
    extra = integrity.scan_function_tags(root)
    for item in issues:
        print(f"FATAL  {item.path}: {item.label} -> {item.ref} (missing {item.kind})")
    for item in extra:
        print(f"AUDIT  {item.path}: {item.label} -> {item.ref} (missing {item.kind}; tags are not fatal)")

    if not issues:
        print("no dangling references in strict registries")
    if delete and issues:
        removed, repaired = integrity.prune(root, _Report())
        for path, reason in repaired:
            print(f"repaired {path}: dropped {reason}")
        for path, reason in removed:
            print(f"deleted {path}: {reason}")
    return 1 if issues else 0


class _Report:
    """Minimal stand-in for upgrader2.report.Report."""

    def change(self, *_args, **_kwargs) -> None:
        pass

    def error(self, message: str) -> None:
        print(f"error: {message}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
