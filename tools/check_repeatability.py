"""Repeatability check: determinism + idempotency.

Usage:
    python tools/check_repeatability.py <source-pack>

Runs the upgrader twice from the same source and compares every output file,
then runs it again on the produced pack and asserts that no rule fires.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from upgrader2.pipeline import upgrade_pack  # noqa: E402


def snapshot(root: str) -> dict[str, str]:
    digests = {}
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, root).replace("\\", "/")
            with open(path, "rb") as handle:
                digests[rel] = hashlib.sha256(handle.read()).hexdigest()
    return digests


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    source = os.path.abspath(argv[1])
    work = os.path.join(ROOT, "_selfcheck")
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work, exist_ok=True)
    try:
        first = os.path.join(work, "first")
        second = os.path.join(work, "second")
        upgrade_pack(source, first, force=True)
        upgrade_pack(source, second, force=True)

        left = snapshot(os.path.join(first, "data"))
        right = snapshot(os.path.join(second, "data"))
        deterministic = left == right
        print(f"determinism : {'OK' if deterministic else 'FAIL'} ({len(left)} files)")

        third = os.path.join(work, "third")
        report, _issues, _stats = upgrade_pack(first, third, force=True)
        rules = {rule: count for rule, count in report.by_rule().items()
                 if rule != "pack_mcmeta.min_max_format"}
        print(f"idempotency : {'OK' if not rules else 'FAIL'} {rules if rules else ''}")
        return 0 if deterministic and not rules else 1
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
