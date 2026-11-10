"""Advancement migration for 26.3.

* a root advancement with ``display`` must have ``display.background``, every
  other advancement must not have one;
* ``background`` no longer carries a ``textures/`` prefix or a ``.png`` suffix
  (1.21.5);
* trigger fields renamed: ``recipe``/``recipe_id`` -> ``recipes``,
  ``block`` -> ``blocks``, ``loot_table`` -> ``loot_tables``;
* trigger condition fields that used to take an inline entity / location
  predicate or a list of predicates now take exactly one loot predicate.
"""

from __future__ import annotations

from typing import Any

from . import entity_predicate as ep
from . import predicate as predicates
from . import text_component
from .item_components import clean_components

DEFAULT_BACKGROUND = "minecraft:gui/advancements/backgrounds/stone"

# 26.3 field sets; anything else at these levels is dropped (2.1).
ROOT_FIELDS = {"criteria", "display", "parent", "requirements", "rewards",
               "sends_telemetry_event"}
DISPLAY_FIELDS = {"title", "description", "icon", "background", "frame",
                  "show_toast", "announce_to_chat", "hidden"}
ICON_FIELDS = {"id", "count", "components"}
CRITERION_FIELDS = {"trigger", "conditions"}
REWARD_FIELDS = {"experience", "recipes", "loot", "function"}

RECIPE_TRIGGERS = {
    "minecraft:recipe_unlocked": "recipe",
    "minecraft:recipe_crafted": "recipe_id",
    "minecraft:crafter_recipe_crafted": "recipe_id",
}

ENTITY_FIELDS = {
    "entity", "killer", "victim", "owner", "source", "direct_entity",
    "causing_entity", "projectile", "target_entity", "interacting_entity",
    "child", "parent", "partner", "villager", "zombie", "bystander",
    "lightning", "shooter", "player",
}
LOCATION_FIELDS = {"location"}
BLOCK_FIELDS = {"minecraft:enter_block", "minecraft:slide_down_block",
                "minecraft:bee_nest_destroyed"}


def normalize_background(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    if ":" in value:
        namespace, path = value.split(":", 1)
    else:
        namespace, path = "minecraft", value
    if path.startswith("textures/"):
        path = path[len("textures/"):]
    if path.endswith(".png"):
        path = path[:-4]
    return f"{namespace}:{path}"


def upgrade(node: Any, ctx, path: str = "") -> tuple[Any, bool]:
    if not isinstance(node, dict):
        return node, False

    changed = False
    display = node.get("display")
    parent = node.get("parent")

    if isinstance(display, dict):
        if parent is None and "background" not in display:
            display["background"] = DEFAULT_BACKGROUND
            changed = True
            ctx.change("advancement.background", path, "gold root background added")
        if parent is not None and "background" in display:
            display.pop("background")
            changed = True
            ctx.change("advancement.background", path, "non-root background removed")
        if "background" in display:
            new_background = normalize_background(display["background"])
            if new_background != display["background"]:
                display["background"] = new_background
                changed = True
                ctx.change("advancement.background", path, "background path form")
        for key in ("title", "description"):
            if isinstance(display.get(key), (dict, list)):
                new_value, ch = text_component.rewrite_tree(display[key])
                if ch:
                    display[key] = new_value
                    changed = True
        icon = display.get("icon")
        if isinstance(icon, dict):
            new_icon, ch = text_component.convert_strings(icon)
            if ch and new_icon != icon:
                icon.clear()
                icon.update(new_icon)
                changed = True
            comps = icon.get("components")
            if isinstance(comps, dict):
                cleaned = clean_components(comps, ctx, path)
                if cleaned != comps:
                    icon["components"] = cleaned
                    changed = True

    criteria = node.get("criteria")
    if isinstance(criteria, dict):
        for criterion in criteria.values():
            if not isinstance(criterion, dict):
                continue
            if _criterion(criterion, ctx, path):
                changed = True

    rewards = node.get("rewards")
    if isinstance(rewards, dict):
        loot = rewards.get("loot")
        if isinstance(loot, list):
            new_loot = []
            for item in loot:
                if isinstance(item, dict) and "condition" in item:
                    new_loot.append(predicates.rewrite(item, ctx, path)[0])
                else:
                    new_loot.append(item)
            if new_loot != loot:
                rewards["loot"] = new_loot
                changed = True

    if _drop_unknown(node, ctx, path):
        changed = True
    return (node, True) if changed else (node, False)


def _drop_unknown(node: dict, ctx, path: str) -> bool:
    """Remove fields 26.3 does not define (the game ignores them silently).

    Only the levels whose schema is fully known are cleaned: root, ``display``,
    ``display.icon`` and ``rewards``.  Criterion-level payloads are left alone
    because ``_criterion`` may have just migrated a mis-placed trigger field
    there.
    """
    changed = False

    def drop(mapping: dict, allowed: set[str], where: str) -> None:
        nonlocal changed
        for key in list(mapping):
            if key not in allowed:
                mapping.pop(key)
                changed = True
                ctx.change("advancement.unknown_field", path,
                           f"{where}{key} removed (not defined in 26.3)")

    drop(node, ROOT_FIELDS, "root field ")
    display = node.get("display")
    if isinstance(display, dict):
        drop(display, DISPLAY_FIELDS, "display.")
        icon = display.get("icon")
        if isinstance(icon, dict):
            drop(icon, ICON_FIELDS, "display.icon.")
    rewards = node.get("rewards")
    if isinstance(rewards, dict):
        drop(rewards, REWARD_FIELDS, "rewards.")
    return changed


def _criterion(criterion: dict, ctx, path: str) -> bool:
    changed = False
    trigger = criterion.get("trigger", "")

    conditions = criterion.get("conditions")
    if not isinstance(conditions, dict):
        conditions = None

    # 26.3 moved several trigger payload fields (they live in "conditions")
    for target, old in (
        (conditions, RECIPE_TRIGGERS.get(trigger)),
        (conditions, "loot_table" if trigger == "minecraft:player_generates_container_loot" else None),
        (conditions, "block" if trigger in BLOCK_FIELDS else None),
    ):
        if target is not None and old and old in target:
            new_key = "blocks" if old == "block" else ("loot_tables" if old == "loot_table" else "recipes")
            target[new_key] = target.pop(old)
            changed = True
            ctx.change("advancement.trigger_fields", path, f"{old} -> {new_key}")

    # tolerate the field having been written at criterion level
    old = RECIPE_TRIGGERS.get(trigger)
    if old and old in criterion:
        criterion["recipes"] = criterion.pop(old)
        changed = True
        ctx.change("advancement.trigger_fields", path, f"{old} -> recipes")
    if trigger == "minecraft:player_generates_container_loot" and "loot_table" in criterion:
        criterion["loot_tables"] = criterion.pop("loot_table")
        changed = True
        ctx.change("advancement.trigger_fields", path, "loot_table -> loot_tables")
    if trigger in BLOCK_FIELDS and "block" in criterion:
        criterion["blocks"] = criterion.pop("block")
        changed = True
        ctx.change("advancement.trigger_fields", path, "block -> blocks")

    if conditions is None:
        return changed

    for key in list(conditions):
        value = conditions[key]
        if key in ENTITY_FIELDS and isinstance(value, (dict, list)):
            new_value = _as_entity_predicate(value, ctx, path)
            if new_value != value:
                conditions[key] = new_value
                changed = True
                ctx.change("advancement.trigger_fields", path, f"{key} -> single predicate")
        elif key in LOCATION_FIELDS and isinstance(value, (dict, list)):
            new_value = _as_location_predicate(value, ctx, path)
            if new_value != value:
                conditions[key] = new_value
                changed = True
                ctx.change("advancement.trigger_fields", path, "location -> location_check predicate")
        elif key == "item" and isinstance(value, dict):
            comps = value.get("components")
            if isinstance(comps, dict):
                from .item_components import clean_components

                cleaned = clean_components(comps, ctx, path)
                if cleaned != comps:
                    value["components"] = cleaned
                    changed = True

    return changed


def _as_entity_predicate(value: Any, ctx, path: str) -> Any:
    if isinstance(value, list):
        terms = [_as_entity_predicate(item, ctx, path) for item in value]
        if len(terms) == 1:
            return terms[0]
        return {"type": "minecraft:all_of", "terms": terms}
    if not isinstance(value, dict):
        return value
    if "condition" in value:
        return predicates.rewrite(value, ctx, path)[0]
    kind = value.get("type")
    if isinstance(kind, str) and kind in predicates.PREDICATE_TYPES:
        return predicates.rewrite(value, ctx, path)[0]
    return {
        "type": "minecraft:entity_properties",
        "entity": "this",
        "predicate": ep.normalize(value, ctx, path),
    }


def _as_location_predicate(value: Any, ctx, path: str) -> Any:
    if isinstance(value, list):
        terms = [_as_location_predicate(item, ctx, path) for item in value]
        if len(terms) == 1:
            return terms[0]
        return {"type": "minecraft:all_of", "terms": terms}
    if not isinstance(value, dict):
        return value
    if value.get("condition") or value.get("type"):
        return predicates.rewrite(value, ctx, path)[0]
    return {"type": "minecraft:location_check", "predicate": value}
