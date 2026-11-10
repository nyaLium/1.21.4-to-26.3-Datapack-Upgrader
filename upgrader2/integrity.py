"""Cross-file reference integrity for 26.3 data packages.

As of 26.3-snapshot-3 an error inside *any* file of the following registries
makes the game refuse to load the whole world instead of skipping that one
file (Mojira MC-310325, resolved as "Works As Intended"; MC-311918 is the same
problem for recipes with unknown items):

    advancement, loot_table, recipe, number_provider, slot_source,
    predicate, item_modifier

A file can be syntactically valid and still be fatal: an advancement whose
``rewards.function`` points at a function that does not exist, a parent that
was never shipped, a criteria recipe that was renamed, ... .  Such a file
cannot be repaired by adding data (the target content is simply gone), so the
safest migration is to delete it and record exactly why.

This module only resolves references that are answerable from the pack itself.
A reference into a namespace that the pack does not define is left alone: it
belongs to vanilla or to another data pack that may be loaded alongside.
``minecraft:`` references are never checked for the same reason.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

#: Registries whose load errors are fatal for the whole pack in 26.3.
STRICT_REGISTRIES = (
    "advancement", "loot_table", "recipe", "number_provider",
    "slot_source", "predicate", "item_modifier",
)

#: How many passes of "delete -> re-scan" to run (deleting an advancement can
#: orphan the advancements whose ``parent`` pointed at it).
MAX_ROUNDS = 10


def is_strict(registry: str) -> bool:
    """True when a load error in *registry* blocks the whole pack in 26.3."""
    return registry in STRICT_REGISTRIES

#: 26.3 item registry (bare ids, one per line).  Datapacks cannot add items, so
#: a recipe or advancement icon that names an item outside this list is a
#: load error as well (MC-311918 reports exactly that for recipes).
_ITEM_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vanilla_items_26.3.txt")


def _load_items() -> frozenset[str]:
    try:
        with open(_ITEM_FILE, encoding="utf-8") as handle:
            return frozenset(line.strip() for line in handle if line.strip())
    except OSError:
        return frozenset()


VANILLA_ITEMS = _load_items()


@dataclass(frozen=True)
class Dangling:
    """One reference that cannot be resolved inside the pack."""

    path: str        # pack-relative path, '/'-separated
    registry: str    # registry of the file that contains the reference
    label: str       # where in the file the reference sits
    ref: str         # the unresolved id
    kind: str        # target registry (function, recipe, ...)


def scan(root: str) -> list[Dangling]:
    """Return every dangling reference found in *root* (a data pack folder)."""
    data = os.path.join(root, "data")
    if not os.path.isdir(data):
        return []

    namespaces = {name for name in os.listdir(data) if os.path.isdir(os.path.join(data, name))}
    index = {
        "function": _index(root, "function", ".mcfunction"),
        "recipe": _index(root, "recipe", ".json"),
        "loot_table": _index(root, "loot_table", ".json"),
        "predicate": _index(root, "predicate", ".json"),
        "item_modifier": _index(root, "item_modifier", ".json"),
        "advancement": _index(root, "advancement", ".json"),
        "function_tag": _tag_index(root, "function"),
    }

    out: list[Dangling] = []
    for registry in ("advancement", "loot_table", "recipe", "predicate", "item_modifier"):
        for _ident, path in index[registry].items():
            try:
                with open(path, encoding="utf-8-sig") as handle:
                    node = json.load(handle)
            except Exception:  # noqa: BLE001 - invalid JSON is reported elsewhere
                continue
            rp = os.path.relpath(path, root).replace("\\", "/")
            for label, kind, ref in _refs_of(registry, node):
                if not isinstance(ref, str) or not ref:
                    continue
                if _resolvable(ref, kind, index, namespaces):
                    continue
                out.append(Dangling(rp, registry, label, ref, kind))
    return out


def prune(root: str, report) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Repair or delete files with dangling references until the pack is clean.

    A dangling ``rewards.*`` entry is dropped instead of deleting the whole
    advancement: the advancement itself is still valid (and may be granted by
    functions), only the reward is lost.  Anything else - a missing parent, a
    criteria recipe that does not exist, ... - leaves the file meaningless, so
    the file is removed.

    Returns ``(deleted, repaired)`` as ``(pack-relative path, reason)`` pairs.
    """
    removed: list[tuple[str, str]] = []
    repaired: list[tuple[str, str]] = []
    for _round in range(MAX_ROUNDS):
        issues = scan(root)
        if not issues:
            break
        by_path: dict[str, list[Dangling]] = {}
        for issue in issues:
            by_path.setdefault(issue.path, []).append(issue)
        progress = False
        for rp, items in sorted(by_path.items()):
            target = os.path.join(root, *rp.split("/"))
            rewards = [item for item in items if _is_reward(item)]
            rest = [item for item in items if not _is_reward(item)]
            if rewards and not rest and _drop_rewards(target, rewards, report, rp):
                repaired.append((rp, "; ".join(f"{i.label} -> {i.ref}" for i in rewards)))
                progress = True
                continue
            reason = "; ".join(f"{item.label} -> {item.ref}" for item in items[:4])
            try:
                os.remove(target)
            except OSError as exc:  # noqa: BLE001
                report.error(f"cannot delete broken JSON {rp}: {exc}")
                continue
            removed.append((rp, reason))
            report.change("json.dangling_reference", rp, reason)
            progress = True
        if not progress:
            break
    return removed, repaired


def _is_reward(item: Dangling) -> bool:
    return item.registry == "advancement" and item.label.startswith("rewards.")


def _drop_rewards(path: str, items: list[Dangling], report, rp: str) -> bool:
    """Remove the dangling ``rewards.<key>`` fields from one advancement."""
    try:
        with open(path, encoding="utf-8-sig") as handle:
            node = json.load(handle)
    except Exception:  # noqa: BLE001
        return False
    rewards = node.get("rewards")
    if not isinstance(rewards, dict):
        return False
    changed = False
    for item in items:
        key = item.label.split(".", 1)[1]
        if key in rewards:
            del rewards[key]
            changed = True
    if not changed:
        return False
    if not rewards:
        node.pop("rewards", None)
    _write_json(path, node)
    report.change("json.reward_dropped", rp,
                  "; ".join(f"{item.label} -> {item.ref}" for item in items))
    return True


def _write_json(path: str, node) -> None:
    text = json.dumps(node, ensure_ascii=False, indent="\t")
    if not text.endswith("\n"):
        text += "\n"
    with open(path, "wb") as handle:
        handle.write(text.encode("utf-8"))


# ---------------------------------------------------------------------------
# reference extraction
# ---------------------------------------------------------------------------

def _refs_of(registry: str, node):
    """Yield ``(label, target-kind, id)`` for every reference in *node*."""
    if registry == "advancement":
        yield from _advancement_refs(node)
        yield from _icon_refs(node)
    elif registry == "loot_table":
        yield from _loot_refs(node)
    elif registry == "recipe":
        yield from _recipe_item_refs(node)
    elif registry == "predicate":
        yield from _reference_nodes(node, "predicate")
    elif registry == "item_modifier":
        yield from _reference_nodes(node, "item_modifier")


def _advancement_refs(node):
    if not isinstance(node, dict):
        return
    parent = node.get("parent")
    if isinstance(parent, str) and parent:
        yield ("parent", "advancement", parent)
    rewards = node.get("rewards")
    if isinstance(rewards, dict):
        for ref in _strings(rewards.get("function")):
            yield ("rewards.function", "function", ref)
        for ref in _strings(rewards.get("loot")):
            yield ("rewards.loot", "loot_table", ref)
        for ref in _strings(rewards.get("recipes")):
            yield ("rewards.recipes", "recipe", ref)
    criteria = node.get("criteria")
    if isinstance(criteria, dict):
        for name, body in criteria.items():
            if not isinstance(body, dict):
                continue
            conditions = body.get("conditions")
            if not isinstance(conditions, dict):
                continue
            for key in ("recipe", "recipes"):
                for ref in _strings(conditions.get(key)):
                    yield (f"criteria.{name}.conditions.{key}", "recipe", ref)
            for key in ("loot_table", "loot_tables"):
                for ref in _strings(conditions.get(key)):
                    yield (f"criteria.{name}.conditions.{key}", "loot_table", ref)
            yield from _reference_nodes(conditions, "predicate", prefix=f"criteria.{name}.conditions")


def _loot_refs(node):
    yield from _nested(node, "loot_table", ("value", "name"), "loot_table")
    yield from _nested(node, "set_loot_table", ("loot_table_id", "name"), "loot_table")
    yield from _nested(node, "minecraft:item", ("name",), "item")


def _icon_refs(node):
    if not isinstance(node, dict):
        return
    display = node.get("display")
    if not isinstance(display, dict):
        return
    icon = display.get("icon")
    if isinstance(icon, dict) and isinstance(icon.get("id"), str):
        yield ("display.icon.id", "item", icon["id"])


def _recipe_item_refs(node, prefix: str = ""):
    if isinstance(node, dict):
        for key, value in node.items():
            here = f"{prefix}.{key}" if prefix else key
            if key in ("item", "id") and isinstance(value, str):
                yield (here, "item", value)
            elif key == "items" and isinstance(value, list):
                for ref in _strings(value):
                    yield (here, "item", ref)
            yield from _recipe_item_refs(value, here)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _recipe_item_refs(value, f"{prefix}[{index}]")


def _reference_nodes(node, kind: str, prefix: str = ""):
    if isinstance(node, dict):
        if node.get("type") == "minecraft:reference" and isinstance(node.get("name"), str):
            yield (f"{prefix}.reference" if prefix else "reference", kind, node["name"])
        for key, value in node.items():
            yield from _reference_nodes(value, kind, f"{prefix}.{key}" if prefix else key)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _reference_nodes(value, kind, f"{prefix}[{index}]")


def _nested(node, node_type: str, keys: tuple[str, ...], kind: str):
    if isinstance(node, dict):
        if node.get("type") == node_type:
            for key in keys:
                value = node.get(key)
                if isinstance(value, str) and value:
                    yield (key, kind, value)
                    break
        for value in node.values():
            yield from _nested(value, node_type, keys, kind)
    elif isinstance(node, list):
        for value in node:
            yield from _nested(value, node_type, keys, kind)


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


# ---------------------------------------------------------------------------
# resolution
# ---------------------------------------------------------------------------

def _resolvable(ref: str, kind: str, index: dict, namespaces: set[str]) -> bool:
    if kind == "item":
        if ":" in ref:
            namespace, bare = ref.split(":", 1)
            if namespace != "minecraft":
                return True
        else:
            bare = ref
        return bare in VANILLA_ITEMS
    if ref.startswith("#"):
        if kind != "function_tag":
            return True  # item/block tags: not verifiable from this pack
        if _foreign(ref[1:], namespaces):
            return True
        return ref in index["function_tag"]
    if ":" not in ref:
        return True  # implicit minecraft: -> vanilla
    namespace = ref.split(":", 1)[0]
    if namespace not in namespaces or namespace == "minecraft":
        return True
    table = index.get("function" if kind == "function_tag" else kind)
    return table is not None and ref in table


def _foreign(ident: str, namespaces: set[str]) -> bool:
    namespace = ident.split(":", 1)[0] if ":" in ident else "minecraft"
    return namespace not in namespaces or namespace == "minecraft"


# ---------------------------------------------------------------------------
# indexes
# ---------------------------------------------------------------------------

def _index(root: str, sub: str, suffix: str) -> dict[str, str]:
    out: dict[str, str] = {}
    data = os.path.join(root, "data")
    if not os.path.isdir(data):
        return out
    for namespace in sorted(os.listdir(data)):
        base = os.path.join(data, namespace, sub)
        if not os.path.isdir(base):
            continue
        for dirpath, _dirnames, filenames in os.walk(base):
            for name in filenames:
                if not name.endswith(suffix):
                    continue
                path = os.path.join(dirpath, name)
                rel = os.path.relpath(path, base)[: -len(suffix)].replace("\\", "/")
                out[f"{namespace}:{rel}"] = path
    return out


def _tag_index(root: str, tag_type: str) -> dict[str, str]:
    out: dict[str, str] = {}
    data = os.path.join(root, "data")
    if not os.path.isdir(data):
        return out
    for namespace in sorted(os.listdir(data)):
        base = os.path.join(data, namespace, "tags", tag_type)
        if not os.path.isdir(base):
            continue
        for dirpath, _dirnames, filenames in os.walk(base):
            for name in filenames:
                if not name.endswith(".json"):
                    continue
                path = os.path.join(dirpath, name)
                rel = os.path.relpath(path, base)[:-5].replace("\\", "/")
                out[f"#{namespace}:{rel}"] = path
    return out


# ---------------------------------------------------------------------------
# function tags
# ---------------------------------------------------------------------------

def scan_function_tags(root: str) -> list[Dangling]:
    """Function-tag values that point at functions which do not exist.

    Tags are *not* fatal in 26.3, so this is audit-only; the upgrader reports
    it but does not delete anything.
    """
    data = os.path.join(root, "data")
    if not os.path.isdir(data):
        return []
    namespaces = {name for name in os.listdir(data) if os.path.isdir(os.path.join(data, name))}
    index = {
        "function": _index(root, "function", ".mcfunction"),
        "function_tag": _tag_index(root, "function"),
    }
    out: list[Dangling] = []
    for ident, path in index["function_tag"].items():
        try:
            with open(path, encoding="utf-8-sig") as handle:
                node = json.load(handle)
        except Exception:  # noqa: BLE001
            continue
        values = node.get("values") if isinstance(node, dict) else None
        for value in values or []:
            if isinstance(value, dict):
                value = value.get("id")
            if not isinstance(value, str) or not value:
                continue
            ok = _resolvable(value, "function_tag", index, namespaces)
            if not ok:
                out.append(Dangling(os.path.relpath(path, root).replace("\\", "/"),
                                    "tags/function", "values", value, "function"))
    return out
