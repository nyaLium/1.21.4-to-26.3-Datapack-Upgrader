"""Upgrade pipeline: copy the pack, rewrite it registry by registry, verify."""

from __future__ import annotations

import json
import os
import shutil
from typing import Any

from . import advancement, item_modifier, loot_table, nbt_rewrite, predicate, snbt
from . import integrity
from . import text_component
from .commands import process_text
from .jsonio import dump_like, load
from .report import Report
from .tags import rename_tag
from .textio import rel, walk, write_text, read_text
from .verify import lint_pack
from .version import TARGET_PACK_VERSION

# registries/data folders that a 1.21.4 data pack actually loads
LIVE_REGISTRIES = {
    "advancement", "banner_pattern", "cat_variant", "chat_type", "chicken_variant",
    "cow_variant", "damage_type", "dimension", "dimension_type", "enchantment",
    "enchantment_provider", "frog_variant", "function", "instrument",
    "item_modifier", "jukebox_song", "loot_table", "painting_variant",
    "pig_variant", "predicate", "recipe", "structure", "test_environment",
    "test_instance", "trim_material", "trim_pattern", "wolf_sound_variant",
    "wolf_variant", "worldgen",
}

LIVE_TAG_TYPES = {
    "function", "item", "block", "entity_type", "damage_type", "fluid",
    "game_event", "banner_pattern", "instrument", "painting_variant",
    "enchantment", "point_of_interest_type", "worldgen/biome", "dialog",
    "timeline", "trade_set", "villager_trade", "potion",
}

IGNORED_TOP_LEVEL = {
    "dist", "_upgrade", "_analysis", "__pycache__", ".git", ".idea", ".vscode",
    "node_modules", "upgrader", "upgrader2", "tests",
}

COOKING_TYPES = {"minecraft:smoking", "minecraft:blasting"}


def upgrade_pack(src: str, dst: str, force: bool = False, *, do_copy: bool = True,
                 prune_refs: bool = True) -> tuple[Report, list[str], dict[str, int]]:
    src = os.path.abspath(src)
    dst = os.path.abspath(dst)
    if not os.path.isdir(os.path.join(src, "data")):
        raise SystemExit(f"not a data pack (no data/ directory): {src}")
    if do_copy:
        if os.path.exists(dst):
            if not force:
                raise SystemExit(f"destination already exists: {dst} (use --force)")
            shutil.rmtree(dst)
        _copy_tree(src, dst)

    report = Report()
    dead = _dead_content(dst)
    dead_prefixes = tuple(f"data/{ns}/{sub}/" for ns, sub, _count in dead)
    removed: list[tuple[str, str]] = []

    _upgrade_mcmeta(dst, report)

    data_dir = os.path.join(dst, "data")
    for path in walk(data_dir, ".json"):
        rp = rel(dst, path)
        if rp.startswith(dead_prefixes):
            continue
        registry = _registry_of(rp)
        if registry is None:
            continue
        report.files_scanned += 1
        try:
            node = load(path)
        except Exception as exc:  # noqa: BLE001 - report instead of crashing
            if registry == "function":
                report.warn(f"inert JSON inside function/ is not loaded: {exc}", rp)
            elif prune_refs and integrity.is_strict(registry):
                try:
                    os.remove(path)
                except OSError as err:  # noqa: BLE001
                    report.error(f"cannot delete unparseable JSON {rp}: {err}")
                else:
                    reason = f"unparseable JSON in a strict registry: {exc}"
                    removed.append((rp, reason))
                    report.change("json.invalid_deleted", rp, reason)
            else:
                report.error(f"invalid JSON ({exc}) - 26.3 fails the whole pack on this", rp)
            continue
        try:
            new_node, changed = upgrade_json(node, registry, report, rp)
        except Exception as exc:  # noqa: BLE001
            report.error(f"transform failed: {exc}", rp)
            continue
        if changed:
            _save_json(path, new_node)
            report.change("json.file_rewritten", rp, "")

    for path in walk(data_dir, ".mcfunction"):
        rp = rel(dst, path)
        if rp.startswith(dead_prefixes):
            continue
        report.files_scanned += 1
        doc = read_text(path)
        report.function_lines += doc.text.count("\n") + 1
        try:
            new_text, count = process_text(doc.text, rp, report)
        except Exception as exc:  # noqa: BLE001
            report.error(f"transform failed: {exc}", rp)
            continue
        if count:
            write_text(doc, new_text)

    pruned, repaired = integrity.prune(dst, report) if prune_refs else ([], [])
    removed.extend(pruned)

    issues, stats = lint_pack(dst)
    for issue in issues:
        if issue.startswith("invalid JSON"):
            report.error(issue)
        else:
            report.warn(issue)
    _write_report(dst, src, report, dead, issues, stats, removed, repaired)
    return report, issues, stats


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _copy_tree(src: str, dst: str) -> None:
    def ignore(dirpath: str, names: list[str]) -> set[str]:
        if os.path.abspath(dirpath) == src:
            return {name for name in names if name in IGNORED_TOP_LEVEL}
        return {name for name in names if name == "__pycache__"}

    shutil.copytree(src, dst, ignore=ignore)


def _registry_of(rp: str) -> str | None:
    parts = rp.split("/")
    if len(parts) < 3 or parts[0] != "data":
        return None
    namespace = parts[1]
    if len(parts) < 4:
        return None
    folder = parts[2]
    if folder == "tags":
        if len(parts) < 5:
            return None
        tag_type = parts[3]
        if tag_type not in LIVE_TAG_TYPES:
            return None
        return f"tags/{tag_type}"
    if folder not in LIVE_REGISTRIES:
        return None
    return folder


def _dead_content(root: str) -> list[tuple[str, str, int]]:
    dead: list[tuple[str, str, int]] = []
    data = os.path.join(root, "data")
    if not os.path.isdir(data):
        return dead
    for namespace in sorted(os.listdir(data)):
        ns_dir = os.path.join(data, namespace)
        if not os.path.isdir(ns_dir):
            continue
        for sub in sorted(os.listdir(ns_dir)):
            sub_dir = os.path.join(ns_dir, sub)
            if not os.path.isdir(sub_dir):
                dead.append((namespace, sub, 1))
                continue
            if sub == "tags":
                for tag_type in sorted(os.listdir(sub_dir)):
                    tag_dir = os.path.join(sub_dir, tag_type)
                    if not os.path.isdir(tag_dir):
                        continue
                    if tag_type not in LIVE_TAG_TYPES:
                        dead.append((namespace, f"tags/{tag_type}", _count_files(tag_dir)))
                continue
            if sub not in LIVE_REGISTRIES:
                dead.append((namespace, sub, _count_files(sub_dir)))
    return dead


def _count_files(path: str) -> int:
    total = 0
    for _dirpath, _dirnames, filenames in os.walk(path):
        total += len(filenames)
    return total


def _upgrade_mcmeta(root: str, report: Report) -> None:
    path = os.path.join(root, "pack.mcmeta")
    if not os.path.isfile(path):
        report.error("pack.mcmeta missing")
        return
    try:
        meta = load(path)
    except Exception as exc:  # noqa: BLE001
        report.error(f"pack.mcmeta is not valid JSON ({exc})")
        return
    pack = meta.setdefault("pack", {})
    old_format = pack.get("pack_format")
    pack.pop("pack_format", None)
    pack.pop("supported_formats", None)
    pack["min_format"] = list(TARGET_PACK_VERSION)
    pack["max_format"] = list(TARGET_PACK_VERSION)
    overlays = meta.get("overlays")
    if isinstance(overlays, dict):
        for entry in overlays.get("entries", []) or []:
            if isinstance(entry, dict):
                if "formats" in entry:
                    entry["min_format"] = list(TARGET_PACK_VERSION)
                    entry["max_format"] = list(TARGET_PACK_VERSION)
                    entry.pop("formats", None)
    _save_json(path, meta)
    report.change(
        "pack_mcmeta.min_max_format", "pack.mcmeta",
        f"pack_format {old_format} -> min_format/max_format {TARGET_PACK_VERSION[0]}.{TARGET_PACK_VERSION[1]}",
    )


def _save_json(path: str, node: Any) -> None:
    """Write JSON with tab indentation and LF newlines (2.1).

    A rewritten file is normalised: no BOM (26.3 strict parsing rejects it),
    ``\\n`` line endings and a trailing newline, so repeated runs are stable.
    """
    doc = read_text(path)
    text = dump_like(node, doc)
    if not text.endswith("\n"):
        text += "\n"
    with open(path, "wb") as handle:
        handle.write(text.encode("utf-8"))


def upgrade_json(node: Any, registry: str, report: Report, rp: str) -> tuple[Any, bool]:
    if registry == "advancement":
        return advancement.upgrade(node, report, rp)
    if registry == "predicate":
        return predicate.rewrite(node, report, rp)
    if registry == "item_modifier":
        return item_modifier.upgrade(node, report, rp)
    if registry == "loot_table":
        return loot_table.upgrade(node, report, rp)
    if registry.startswith("tags/"):
        return _upgrade_tag(node, report, rp)
    if registry == "recipe":
        return _upgrade_recipe(node, report, rp)
    return _upgrade_other(node, report, rp)


def _upgrade_tag(node: Any, report: Report, rp: str) -> tuple[Any, bool]:
    if not isinstance(node, dict):
        return node, False
    changed = False
    values = node.get("values")
    if isinstance(values, list):
        out = []
        for value in values:
            if isinstance(value, str):
                new_value = rename_tag(value)
                if new_value != value:
                    changed = True
                    report.change("tags.renamed", rp, f"{value} -> {new_value}")
                out.append(new_value)
            elif isinstance(value, dict) and isinstance(value.get("id"), str):
                new_id = rename_tag(value["id"])
                if new_id != value["id"]:
                    value = dict(value, id=new_id)
                    changed = True
                    report.change("tags.renamed", rp, f"{value['id']}")
                out.append(value)
            else:
                out.append(value)
        if changed:
            node["values"] = out
    return node, changed


def _upgrade_recipe(node: Any, report: Report, rp: str) -> tuple[Any, bool]:
    if not isinstance(node, dict):
        return node, False
    rtype = node.get("type")
    if rtype in COOKING_TYPES and isinstance(node.get("cookingtime"), int):
        # 26.3 unifies cooking time across furnace blocks (200 ticks at 1x speed)
        node["cookingtime"] = node["cookingtime"] * 2
        report.change("recipe.cooking_time", rp, f"{rtype} cookingtime doubled")
        return node, True
    return node, False


def _upgrade_other(node: Any, report: Report, rp: str) -> tuple[Any, bool]:
    """Generic pass: inline JSON-string components in text-component fields."""
    return text_component.convert_strings(node)


def _write_report(dst: str, src: str, report: Report, dead, issues, stats,
                  removed=None, repaired=None) -> None:
    from .docs import render_markdown

    out_dir = os.path.join(dst, "_upgrade")
    os.makedirs(out_dir, exist_ok=True)
    for name, lang in (("report.md", "zh"), ("report.en.md", "en")):
        markdown = render_markdown(src, dst, report, dead, issues, stats,
                                   removed or [], repaired or [], lang=lang)
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as handle:
            handle.write(markdown)
    payload = {
        "source": src,
        "destination": dst,
        "target_data_pack_version": f"{TARGET_PACK_VERSION[0]}.{TARGET_PACK_VERSION[1]}",
        "dead_content": [
            {"namespace": ns, "path": sub, "files": count} for ns, sub, count in dead
        ],
        "removed_files": [
            {"path": path, "reason": reason} for path, reason in (removed or [])
        ],
        "repaired_files": [
            {"path": path, "reason": reason} for path, reason in (repaired or [])
        ],
        "lint_issues": issues,
        "lint_stats": stats,
    }
    payload.update(report.to_json())
    with open(os.path.join(out_dir, "report.json"), "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
