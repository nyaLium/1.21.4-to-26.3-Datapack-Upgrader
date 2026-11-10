"""Item modifier migration for 26.3.

* ``function`` -> ``type`` and ``conditions`` -> ``condition`` (single);
* a root-level JSON array is no longer allowed - it becomes an explicit
  ``minecraft:sequence`` (the sequences's list field is still ``functions``);
* ``filtered.modifier`` -> ``on_pass`` (``on_fail`` defaults to a no-op);
* ``set_loot_table.name`` -> ``loot_table_id`` and its old ``type`` is dropped;
* ``exploration_map.destination`` is mandatory and ``map_color`` is gone;
* text components inside ``set_name`` / ``set_lore`` are inlined.
"""

from __future__ import annotations

from typing import Any

from . import predicate as predicates
from . import text_component
from .item_components import clean_components

# types that identify an item modifier when one appears inline in a command
ITEM_MODIFIER_TYPES = {
    "apply_bonus", "copy_components", "copy_custom_data", "copy_name", "copy_state",
    "discard", "enchant_randomly", "enchant_with_levels", "enchanted_count_increase",
    "exploration_map", "explosion_decay", "fill_player_head", "filtered",
    "furnace_smelt", "limit_count", "modify_contents", "sequence", "set_attributes",
    "set_banner_pattern", "set_book_cover", "set_components", "set_contents",
    "set_count", "set_custom_data", "set_custom_model_data", "set_damage",
    "set_enchantments", "set_firework_explosion", "set_fireworks", "set_instrument",
    "set_item", "set_loot_table", "set_lore", "set_name",
    "set_ominous_bottle_amplifier", "set_potion", "set_random_dyes",
    "set_random_potion", "set_stew_effect", "set_writable_book_pages",
    "set_written_book_pages", "toggle_tooltips",
}


def upgrade(node: Any, ctx, path: str = "", *, top_level: bool = True) -> tuple[Any, bool]:
    if isinstance(node, str):
        return node, False

    if isinstance(node, list):
        items = [upgrade(item, ctx, path, top_level=False)[0] for item in node]
        ctx.change("item_modifier.sequence", path, f"{len(items)} modifiers")
        if len(items) == 1:
            return items[0], True
        return {"type": "minecraft:sequence", "functions": items}, True

    if not isinstance(node, dict):
        return node, False

    func = node.get("function") or node.get("type")
    if not isinstance(func, str):
        if "conditions" in node or "condition" in node:
            ctx.warn("item modifier without a function/type; left as is", path)
        return node, False

    body: dict[str, Any] = {
        key: value for key, value in node.items()
        if key not in ("function", "type", "conditions", "condition")
    }
    changed = "function" in node
    if changed:
        ctx.change("item_modifier.discriminator", path, f"function -> type ({func})")

    old_conditions = node.get("conditions") if "conditions" in node else node.get("condition")
    if old_conditions is not None:
        body["condition"] = predicates.condition_from_list(old_conditions, ctx, path)
        changed = True

    handler = _HANDLERS.get(func)
    if handler is not None:
        new_body, ch = handler(body, ctx, path)
        body = new_body
        changed = changed or ch

    result: dict[str, Any] = {"type": func}
    result.update(body)
    return (result, True) if changed else (node, False)


# ---------------------------------------------------------------------------
# per-function handlers
# ---------------------------------------------------------------------------

def _set_lore(body: dict, ctx, path: str) -> tuple[dict, bool]:
    changed = False
    lore = body.get("lore")
    if isinstance(lore, list):
        out = []
        for line in lore:
            if isinstance(line, str):
                new, ch = text_component.from_json_string(line)
                if ch:
                    new, _ = text_component.rewrite_tree(new)
                    out.append(new)
                    changed = True
                    continue
            elif isinstance(line, (dict, list)):
                new, ch = text_component.rewrite_tree(line)
                out.append(new)
                changed = changed or ch
                continue
            out.append(line)
        body["lore"] = out
    return body, changed


def _set_name(body: dict, ctx, path: str) -> tuple[dict, bool]:
    changed = False
    name = body.get("name")
    if isinstance(name, str):
        new, ch = text_component.from_json_string(name)
        if ch:
            new, _ = text_component.rewrite_tree(new)
            body["name"] = new
            changed = True
    elif isinstance(name, (dict, list)):
        new, ch = text_component.rewrite_tree(name)
        if ch:
            body["name"] = new
            changed = True
    return body, changed


def _set_components(body: dict, ctx, path: str) -> tuple[dict, bool]:
    comps = body.get("components")
    if not isinstance(comps, dict):
        return body, False
    cleaned = clean_components(comps, ctx, path)
    if cleaned != comps:
        body["components"] = cleaned
        return body, True
    return body, False


def _sequence(body: dict, ctx, path: str) -> tuple[dict, bool]:
    changed = False
    functions = body.get("functions")
    if isinstance(functions, list):
        new_items = []
        for item in functions:
            new_item, ch = upgrade(item, ctx, path, top_level=False)
            new_items.append(new_item)
            changed = changed or ch
        if changed:
            body["functions"] = new_items
    elif isinstance(functions, dict):
        new_item, ch = upgrade(functions, ctx, path, top_level=False)
        if ch:
            body["functions"] = new_item
            changed = True
    return body, changed


def _filtered(body: dict, ctx, path: str) -> tuple[dict, bool]:
    if "modifier" not in body:
        return body, False
    body["on_pass"] = body.pop("modifier")
    ctx.change("item_modifier.filtered", path, "modifier -> on_pass/on_fail")
    if "on_fail" not in body:
        body["on_fail"] = []
    return body, True


def _set_loot_table(body: dict, ctx, path: str) -> tuple[dict, bool]:
    changed = False
    if "name" in body:
        body["loot_table_id"] = body.pop("name")
        changed = True
    if "type" in body:
        body.pop("type")
        changed = True
    return body, changed


def _exploration_map(body: dict, ctx, path: str) -> tuple[dict, bool]:
    changed = False
    if "destination" not in body:
        ctx.warn("exploration_map without destination (26.3 requires it)", path)
    if "map_color" in body:
        body.pop("map_color")
        changed = True
    return body, changed


def _modify_contents(body: dict, ctx, path: str) -> tuple[dict, bool]:
    modifier = body.get("modifier")
    if modifier is None:
        return body, False
    new_modifier, changed = upgrade(modifier, ctx, path, top_level=False)
    if changed:
        body["modifier"] = new_modifier
    return body, changed


def _set_attributes(body: dict, ctx, path: str) -> tuple[dict, bool]:
    changed = False
    modifiers = body.get("modifiers")
    if isinstance(modifiers, list):
        for entry in modifiers:
            if not isinstance(entry, dict):
                continue
            if "name" in entry and "id" not in entry:
                entry["id"] = entry.pop("name")
                changed = True
            if "id" not in entry:
                ctx.warn("set_attributes modifier without id (26.3 requires one)", path)
    return body, changed


_HANDLERS = {
    "minecraft:sequence": _sequence,
    "minecraft:set_lore": _set_lore,
    "minecraft:set_name": _set_name,
    "minecraft:set_components": _set_components,
    "minecraft:filtered": _filtered,
    "minecraft:modify_contents": _modify_contents,
    "minecraft:set_loot_table": _set_loot_table,
    "minecraft:exploration_map": _exploration_map,
    "minecraft:set_attributes": _set_attributes,
}
