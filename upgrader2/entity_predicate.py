"""Entity predicate migration (26.2 rewrite).

Before 26.2 an entity predicate was a compound with a fixed set of optional
fields (``type``, ``nbt``, ``team`` ...) plus a ``type_specific`` compound that
carried a discriminated sub-predicate.  26.2 turned it into a map of namespaced
sub-predicate ids:

    {"type": "minecraft:player", "team": "red",
     "type_specific": {"type": "minecraft:player", "input": {"jump": true}}}

becomes

    {"minecraft:entity_type": "minecraft:player", "minecraft:team": "red",
     "minecraft:type_specific/player": {"input": {"jump": true}}}

Unknown keys are a hard error in 26.3, so old sub-predicates that were removed in
1.21.5 (``axolotl``, ``fox``, ``villager`` ...) cannot be converted automatically;
they are dropped and reported for manual review.
"""

from __future__ import annotations

from typing import Any

# sub-predicates that exist in 26.3 (after the "minecraft:" prefix)
SUBPREDICATES = {
    "entity_type", "location", "stepping_on", "movement_affected_by", "distance",
    "movement", "effects", "nbt", "flags", "equipment", "periodic_tick", "vehicle",
    "passenger", "targeted_entity", "team", "slots", "components", "predicates",
    "entity_tags",
}

TYPE_SPECIFIC = {
    "lightning", "fishing_hook", "player", "cube_mob", "raider", "sheep",
}

# 1.21.4 sub-predicates that were deleted in 1.21.5
REMOVED_SUBPREDICATES = {
    "axolotl", "fox", "mooshroom", "rabbit", "horse", "llama", "villager",
    "parrot", "salmon", "tropical_fish", "painting", "cat", "frog", "wolf", "pig",
    "boat", "any",
}

TYPE_ALIASES = {
    "slime": "cube_mob",
    "lightning_bolt": "lightning",
}

# nested entity predicates (recursed into)
NESTED = {"vehicle", "passenger", "targeted_entity", "looking_at"}


def short_id(value: str) -> str:
    return value[len("minecraft:"):] if value.startswith("minecraft:") else value


def _split(key: str) -> tuple[str, str]:
    if ":" in key:
        namespace, path = key.split(":", 1)
        return namespace, path
    return "minecraft", key


def normalize(node: Any, ctx, path: str = "") -> Any:
    """Return the 26.2-shaped entity predicate for *node*."""
    if not isinstance(node, dict):
        return node

    out: dict[str, Any] = {}
    for key, value in node.items():
        if key == "type":
            out["minecraft:entity_type"] = value
            continue
        if key == "type_specific":
            if not isinstance(value, dict):
                continue
            sub_type = value.get("type")
            rest = {k: v for k, v in value.items() if k != "type"}
            if not isinstance(sub_type, str):
                ctx.warn("entity predicate has type_specific without type", path)
                continue
            name = TYPE_ALIASES.get(short_id(sub_type), short_id(sub_type))
            if name not in TYPE_SPECIFIC:
                ctx.warn(
                    f"entity predicate type_specific/{name} does not exist in 26.3; dropped",
                    path,
                )
                continue
            out[f"minecraft:type_specific/{name}"] = rest
            continue

        namespace, field = _split(key)
        field = TYPE_ALIASES.get(field, field)
        if namespace == "minecraft" and field in REMOVED_SUBPREDICATES:
            ctx.warn(
                f"entity predicate sub-predicate '{key}' was removed in 1.21.5; dropped "
                f"(needs a 'minecraft:components' replacement by hand)",
                path,
            )
            continue
        if namespace == "minecraft" and field in TYPE_SPECIFIC:
            out[f"minecraft:type_specific/{field}"] = value
            continue
        if namespace == "minecraft" and field == "nbt":
            out["minecraft:nbt"] = value
            continue
        if namespace == "minecraft" and field in NESTED and isinstance(value, dict):
            out[f"minecraft:{field}"] = normalize(value, ctx, path)
            continue
        if namespace == "minecraft" and field == "equipment" and isinstance(value, dict):
            out["minecraft:equipment"] = {
                slot: (rewrite_item_predicate(slot_value, ctx, path) if isinstance(slot_value, dict) else slot_value)
                for slot, slot_value in value.items()
            }
            continue
        if namespace == "minecraft" and field == "slots" and isinstance(value, dict):
            out["minecraft:slots"] = {
                slot_range: (rewrite_item_predicate(pred, ctx, path) if isinstance(pred, dict) else pred)
                for slot_range, pred in value.items()
            }
            continue
        if namespace == "minecraft" and field == "effects" and isinstance(value, dict):
            out["minecraft:effects"] = value
            continue
        if namespace == "minecraft" and field in SUBPREDICATES:
            out[f"minecraft:{field}"] = value
            continue
        if namespace != "minecraft":
            out[key] = value
            continue
        ctx.warn(f"unknown entity predicate field '{key}' in 26.3; kept as 'minecraft:{field}'", path)
        out[f"minecraft:{field}"] = value
    return out


def rewrite_item_predicate(node: Any, ctx, path: str = "") -> Any:
    """Item predicates are unchanged structurally; still recurse for components."""
    from .item_components import clean_components

    if not isinstance(node, dict):
        return node
    out = dict(node)
    comps = out.get("components")
    if isinstance(comps, dict):
        out["components"] = clean_components(comps, ctx, path)
    return out
