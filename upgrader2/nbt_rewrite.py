"""NBT surgery for in-command data (``summon``, ``data merge``, ``give`` ...).

Most of this pack's content is entity NBT, and 1.21.5 reshuffled a lot of it:
equipment lists became an ``equipment`` map, drop chance lists became a
``drop_chances`` map, several fields were renamed, and text components stopped
being JSON strings.  26.x adds a few more renames.

The rewriter walks a decoded compound (plain dicts/lists) and mutates it.
"""

from __future__ import annotations

import json
from typing import Any

from . import text_component
from .item_components import clean_components
from .snbt import Array

# 1.21.5: ArmorItems / HandItems / body_armor_item -> equipment map
EQUIPMENT_LISTS = {
    "HandItems": ["mainhand", "offhand"],
    "ArmorItems": ["feet", "legs", "chest", "head"],
}
EQUIPMENT_SINGLE = {
    "body_armor_item": "body",
    "SaddleItem": "saddle",
}
DROP_CHANCE_LISTS = {
    "HandDropChances": ["mainhand", "offhand"],
    "ArmorDropChances": ["feet", "legs", "chest", "head"],
}
DROP_CHANCE_SINGLE = {"body_armor_drop_chance": "body"}

# 1.21.5 (25w03a) also pulled the player's worn armour and off-hand out of the
# ``Inventory`` list and into the ``equipment`` map.  These are the flat slot
# numbers 1.21.4 used inside ``Inventory`` item stacks; a predicate written as
# ``nbt={Inventory:[{Slot:-106b,...}]}`` matches nothing on 26.3 because the
# list only holds the 36 main slots any more.
INVENTORY_EQUIPMENT_SLOTS = {
    100: "feet",
    101: "legs",
    102: "chest",
    103: "head",
    -106: "offhand",
}

# 1.21.5 / 1.21.11 / 26.2 straight field renames
SIMPLE_RENAMES = {
    "FallDistance": "fall_distance",
    "LifeTicks": "life_ticks",
    "HasEgg": "has_egg",
    "enteredNetherPosition": "entered_nether_pos",
    "AngryAT": "angry_at",
}

# fields holding a text component
COMPONENT_FIELDS = {
    "CustomName", "custom_name", "item_name", "lore", "messages", "pages",
    "title", "display_name", "LastOutput", "text",
}

# block-state compounds (Name/Properties -> id/properties)
BLOCK_STATE_FIELDS = {
    "block_state", "BlockState", "carriedBlockState", "inBlockState", "DisplayState",
}

# 1.21.9 renamed the chain block/item
ID_RENAMES = {"minecraft:chain": "minecraft:iron_chain"}

ANGER_SENTINEL = 2147483647


def rewrite_compound(node: dict, ctx, path: str = "") -> bool:
    """Rewrite one compound in place; returns True if anything changed."""
    if not isinstance(node, dict):
        return False
    changed = False

    if _merge_equipment(node, ctx, path):
        changed = True
    if _merge_inventory_equipment(node, ctx, path):
        changed = True
    if _merge_drop_chances(node, ctx, path):
        changed = True

    for key in list(node.keys()):
        value = node[key]

        if key in BLOCK_STATE_FIELDS and isinstance(value, dict):
            if _block_state(value, ctx, path):
                changed = True
            if rewrite_compound(value, ctx, path):
                changed = True
            continue

        if key == "HurtByTimestamp":
            old = node.pop(key)
            node["ticks_since_last_hurt_by_mob"] = 0
            ctx.change("entity_nbt.renamed_fields", path, "HurtByTimestamp -> ticks_since_last_hurt_by_mob")
            if old not in (0, 0.0, None):
                ctx.warn(
                    "HurtByTimestamp is an absolute game time, ticks_since_last_hurt_by_mob is an "
                    f"elapsed tick count; old value {old} cannot be converted (wrote 0).",
                    path,
                )
            changed = True
            continue

        if key == "AngerTime":
            old = node.pop(key)
            node["anger_end_time"] = ANGER_SENTINEL if isinstance(old, int) and old > 0 else 0
            ctx.change("entity_nbt.renamed_fields", path, "AngerTime -> anger_end_time (absolute)")
            ctx.warn(
                "AngerTime was 'ticks remaining', anger_end_time is an absolute game time. "
                f"Wrote {ANGER_SENTINEL} (effectively permanent anger) for the old value {old}.",
                path,
            )
            changed = True
            continue

        if key in SIMPLE_RENAMES:
            new_key = SIMPLE_RENAMES[key]
            node.pop(key)
            node[new_key] = value
            ctx.change("entity_nbt.renamed_fields", path, f"{key} -> {new_key}")
            changed = True
            continue

        if key == "Saddle" and isinstance(value, (bool, int)) and value:
            equipment = node.setdefault("equipment", {})
            equipment.setdefault("saddle", {"id": "minecraft:saddle", "count": 1})
            node.pop(key)
            ctx.change("entity_nbt.renamed_fields", path, "Saddle -> equipment.saddle")
            changed = True
            continue

        if key in COMPONENT_FIELDS:
            new_value, ch = _component_field(value, ctx, path, key)
            if ch:
                node[key] = new_value
                changed = True
            continue

        if key == "components" and isinstance(value, dict):
            new_comps = clean_components(value, ctx, path)
            new_comps = _convert_component_payloads(new_comps, ctx, path)
            if new_comps != value:
                node[key] = new_comps
                changed = True
            continue

        if key == "id" and isinstance(value, str) and value in ID_RENAMES:
            node[key] = ID_RENAMES[value]
            ctx.change("id.renamed", path, f"{value} -> {ID_RENAMES[value]}")
            changed = True
            continue

        if isinstance(value, dict):
            if rewrite_compound(value, ctx, path):
                changed = True
        elif isinstance(value, list):
            for position, item in enumerate(value):
                if isinstance(item, dict) and rewrite_compound(item, ctx, path):
                    changed = True
                elif isinstance(item, str):
                    new, ch = text_component.from_json_string(item)
                    if ch:
                        value[position] = text_component.rewrite_tree(new)[0]
                        changed = True
                        ctx.change("text.component_inline", path, f"{key}[] JSON string -> inline")
        elif isinstance(value, str):
            new, ch = text_component.from_json_string(value)
            if ch:
                node[key] = text_component.rewrite_tree(new)[0]
                ctx.change("text.component_inline", path, f"{key} JSON string -> inline")
                changed = True

    for prefix, target in (("Tile", "block_pos"), ("Sleeping", "sleeping_pos"),
                           ("Bound", "bound_pos"), ("HomePos", "home_pos")):
        coords = [f"{prefix}{axis}" for axis in ("X", "Y", "Z")]
        if all(name in node for name in coords):
            values = [node.pop(name) for name in coords]
            node[target] = Array(values, "int")
            ctx.change("entity_nbt.renamed_fields", path, f"{','.join(coords)} -> {target}")
            changed = True

    if all(name in node for name in ("SpawnX", "SpawnY", "SpawnZ")):
        pos = [node.pop("SpawnX"), node.pop("SpawnY"), node.pop("SpawnZ")]
        respawn: dict[str, Any] = {
            "pos": Array(pos, "int"),
            "dimension": "minecraft:overworld",
            "angle": 0.0,
            "forced": True,
        }
        if "SpawnAngle" in node:
            respawn["angle"] = node.pop("SpawnAngle")
        if "SpawnDimension" in node:
            respawn["dimension"] = node.pop("SpawnDimension")
        if "SpawnForced" in node:
            respawn["forced"] = bool(node.pop("SpawnForced"))
        node["respawn"] = respawn
        ctx.change("entity_nbt.renamed_fields", path, "Spawn* -> respawn")
        changed = True

    return changed


def _merge_equipment(node: dict, ctx, path: str) -> bool:
    present = [key for key in list(EQUIPMENT_LISTS) + list(EQUIPMENT_SINGLE) if key in node]
    if not present:
        return False
    equipment = dict(node.get("equipment") or {})
    for field in present:
        value = node.pop(field)
        if field in EQUIPMENT_LISTS:
            if not isinstance(value, list):
                continue
            for slot, item in zip(EQUIPMENT_LISTS[field], value):
                if _is_empty_stack(item):
                    equipment.pop(slot, None)
                else:
                    equipment[slot] = item
        else:
            slot = EQUIPMENT_SINGLE[field]
            if _is_empty_stack(value):
                equipment.pop(slot, None)
            else:
                equipment[slot] = value
    if equipment:
        node["equipment"] = equipment
    else:
        node.pop("equipment", None)
    ctx.change("entity_nbt.equipment_map", path, f"{', '.join(present)} -> equipment")
    return True


def _merge_inventory_equipment(node: dict, ctx, path: str) -> bool:
    """Move player armour/off-hand item stacks out of ``Inventory``.

    Only the five flat slot numbers 1.21.4 used are touched; slots 0-35 are the
    real main inventory and stay where they are.
    """
    inventory = node.get("Inventory")
    if not isinstance(inventory, list):
        return False
    moved: dict[str, Any] = {}
    kept: list[Any] = []
    for entry in inventory:
        if not isinstance(entry, dict):
            kept.append(entry)
            continue
        slot = entry.get("Slot")
        nested = False
        if slot is None:
            # A few pack lines put Slot inside ``components`` by mistake; the
            # component is invalid there, so hoist it onto the item stack.
            components = entry.get("components")
            if isinstance(components, dict) and "Slot" in components:
                slot = components["Slot"]
                nested = True
        name = INVENTORY_EQUIPMENT_SLOTS.get(slot) if isinstance(slot, int) and not isinstance(slot, bool) else None
        if name is None:
            kept.append(entry)
            continue
        item = dict(entry)
        if nested:
            components = dict(item["components"])
            components.pop("Slot", None)
            item["components"] = components
            ctx.warn(
                "Inventory item stack had Slot nested inside components; "
                "treated it as the item slot and removed the bogus component",
                path,
            )
        else:
            item.pop("Slot", None)
        if name in moved:
            ctx.warn(
                f"Inventory lists Slot {slot} more than once; kept the last item for equipment.{name}",
                path,
            )
        moved[name] = item
    if not moved:
        return False
    if kept:
        node["Inventory"] = kept
    else:
        node.pop("Inventory", None)
    equipment = node.get("equipment")
    if not isinstance(equipment, dict):
        equipment = {}
    for name, item in moved.items():
        if name in equipment:
            ctx.warn(
                f"both equipment.{name} and Inventory[Slot:...] were given; kept equipment.{name}",
                path,
            )
            continue
        equipment[name] = item
    node["equipment"] = equipment
    slots = ", ".join(str(entry) for entry in INVENTORY_EQUIPMENT_SLOTS if INVENTORY_EQUIPMENT_SLOTS[entry] in moved)
    ctx.change(
        "entity_nbt.equipment_map", path,
        f"Inventory[Slot:{slots}] -> equipment.{{{', '.join(moved)}}}",
    )
    return True


def _merge_drop_chances(node: dict, ctx, path: str) -> bool:
    present = [key for key in list(DROP_CHANCE_LISTS) + list(DROP_CHANCE_SINGLE) if key in node]
    if not present:
        return False
    chances = dict(node.get("drop_chances") or {})
    for field in present:
        value = node.pop(field)
        if field in DROP_CHANCE_LISTS:
            if not isinstance(value, list):
                continue
            for slot, chance in zip(DROP_CHANCE_LISTS[field], value):
                chances[slot] = chance
        else:
            chances[DROP_CHANCE_SINGLE[field]] = value
    node["drop_chances"] = chances
    ctx.change("entity_nbt.equipment_map", path, f"{', '.join(present)} -> drop_chances")
    return True


def _is_empty_stack(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, dict):
        return not value
    return False


def _block_state(node: dict, ctx, path: str) -> bool:
    changed = False
    if "Name" in node:
        node["id"] = node.pop("Name")
        changed = True
    if "Properties" in node:
        node["properties"] = node.pop("Properties")
        changed = True
    if isinstance(node.get("id"), str) and node["id"] in ID_RENAMES:
        node["id"] = ID_RENAMES[node["id"]]
        changed = True
    if changed:
        ctx.change("block_state.codec", path, "Name/Properties -> id/properties")
    return changed


def _component_field(value: Any, ctx, path: str, key: str) -> tuple[Any, bool]:
    new = text_component.inline_value(value)
    if new != value:
        ctx.change("text.component_inline", path, f"{key} JSON string -> inline component")
        return new, True
    return value, False

class _Missing:
    pass


_MISSING = _Missing()


def _json_string(text: str) -> Any:
    stripped = text.strip()
    if stripped[:1] not in ('"', "[", "{"):
        return _MISSING
    try:
        return json.loads(stripped)
    except Exception:
        return _MISSING


def _convert_component_payloads(comps: dict, ctx, path: str) -> dict:
    out = {}
    for cid, value in comps.items():
        field = cid.split(":")[-1]
        if field in ("lore", "custom_name", "item_name", "written_book_content",
                     "writable_book_content"):
            new = text_component.inline_value(value)
            out[cid] = new
            continue
        if isinstance(value, str):
            new, ch = text_component.from_json_string(value)
            out[cid] = new if ch else value
        elif isinstance(value, (dict, list)):
            new, ch = text_component.rewrite_tree(value)
            out[cid] = new if ch else value
        else:
            out[cid] = value
    return out



