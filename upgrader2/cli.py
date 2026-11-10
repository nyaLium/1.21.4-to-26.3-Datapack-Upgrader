"""Command line interface."""

from __future__ import annotations

import argparse
import os
import sys

from .pipeline import upgrade_pack
from .version import TARGET_PACK_VERSION


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m upgrader2",
        description=(
            "Upgrade a Minecraft Java data pack from 1.21.4 (pack format 61) to "
            f"26.3 (data pack format {TARGET_PACK_VERSION[0]}.{TARGET_PACK_VERSION[1]})."
        ),
    )
    parser.add_argument("source", help="source data pack directory (contains pack.mcmeta)")
    parser.add_argument("-o", "--output", help="destination directory (default: <source>-26.3)")
    parser.add_argument("--force", action="store_true", help="overwrite an existing destination")
    parser.add_argument("--quiet", action="store_true", help="only print errors")
    parser.add_argument(
        "--keep-dangling",
        action="store_true",
        help="do not delete JSON files whose cross-file references do not resolve "
             "(26.3 fails to load the whole world for those)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    src = os.path.abspath(args.source)
    dst = args.output or os.path.join(
        os.getcwd(), "dist", os.path.basename(src.rstrip("\\/")) + "-26.3"
    )

    report, issues, stats = upgrade_pack(src, dst, force=args.force,
                                         prune_refs=not args.keep_dangling)

    if not args.quiet:
        print(f"source      : {src}")
        print(f"destination : {os.path.abspath(dst)}")
        print(f"files       : {report.files_scanned}")
        print("\nrules:")
        for rule, count in report.by_rule().items():
            print(f"  {count:8d}  {rule}")
        print(f"\ntotal changes: {sum(report.by_rule().values())}")
        print(f"deleted      : {report.by_rule().get('json.dangling_reference', 0)} broken JSON file(s)")
        print(f"lint issues  : {len(issues)}")
        for name, value in sorted(stats.items(), key=lambda kv: -kv[1])[:15]:
            print(f"  {value:8d}  {name}")
        base = os.path.join(os.path.abspath(dst), "_upgrade")
        print(f"\nreport : {os.path.join(base, 'report.md')}")
        print(f"         {os.path.join(base, 'report.en.md')}")

    return 1 if report.errors else 0
