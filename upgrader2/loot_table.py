"""Loot table migration for 26.3.

* ``functions`` -> ``modifier``, ``conditions`` -> ``condition`` (table, pool and
  entry level);
* the ``tag`` entry type's ``name`` -> ``items``;
* inline item modifiers inside ``modifier`` are upgraded recursively.
"""

from __future__ import annotations

from typing import Any

from . import item_modifier
from . import predicate as predicates

NUMBER_FIELDS = {"rolls", "bonus_rolls"}


def upgrade(node: Any, ctx, path: str = "") -> tuple[Any, bool]:
    if not isinstance(node, dict):
        return node, False
    changed = False

    if "functions" in node:
        node["modifier"] = _modifiers(node.pop("functions"), ctx, path)
        changed = True
        ctx.change("loot_table.renames", path, "functions -> modifier")
    if "conditions" in node:
        node["condition"] = predicates.condition_from_list(node.pop("conditions"), ctx, path)
        changed = True
        ctx.change("loot_table.renames", path, "conditions -> condition")

    for field in NUMBER_FIELDS:
        if field in node:
            new_value, ch = _number_provider(node[field], ctx, path)
            if ch:
                node[field] = new_value
                changed = True

    pools = node.get("pools")
    if isinstance(pools, list):
        for pool in pools:
            if upgrade(pool, ctx, path)[1]:
                changed = True

    entries = node.get("entries")
    if isinstance(entries, list):
        for entry in entries:
            if _entry(entry, ctx, path):
                changed = True

    children = node.get("children")
    if isinstance(children, list):
        for child in children:
            if _entry(child, ctx, path):
                changed = True

    return (node, True) if changed else (node, False)


def _entry(entry: Any, ctx, path: str) -> bool:
    if not isinstance(entry, dict):
        return False
    changed = False
    if "functions" in entry:
        entry["modifier"] = _modifiers(entry.pop("functions"), ctx, path)
        changed = True
        ctx.change("loot_table.renames", path, "entry functions -> modifier")
    if "conditions" in entry:
        entry["condition"] = predicates.condition_from_list(entry.pop("conditions"), ctx, path)
        changed = True
        ctx.change("loot_table.renames", path, "entry conditions -> condition")
    if entry.get("type") in ("tag", "minecraft:tag") and "name" in entry:
        entry["items"] = entry.pop("name")
        changed = True
        ctx.change("loot_table.renames", path, "tag entry name -> items")
    for child in entry.get("children", []) or []:
        if _entry(child, ctx, path):
            changed = True
    if isinstance(entry.get("pools"), list):
        for pool in entry["pools"]:
            if upgrade(pool, ctx, path)[1]:
                changed = True
    return changed


def _modifiers(value: Any, ctx, path: str) -> Any:
    if isinstance(value, list):
        return [item_modifier.upgrade(item, ctx, path, top_level=False)[0] for item in value]
    return item_modifier.upgrade(value, ctx, path, top_level=False)[0]


def _number_provider(value: Any, ctx, path: str) -> tuple[Any, bool]:
    if isinstance(value, dict) and "type" not in value:
        # 1.21.4 defaulted a missing provider type to "uniform".
        provider = {"type": "minecraft:uniform"}
        provider.update(value)
        ctx.warn("number provider without type; assumed minecraft:uniform", path)
        return provider, True
    return value, False
