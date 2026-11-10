"""Predicate migration for 26.3.

* the discriminator ``condition`` was renamed to ``type`` and is mandatory
  (it used to default to ``minecraft:entity_properties``);
* a JSON list of predicates is no longer accepted anywhere - it must be an
  explicit ``minecraft:all_of``;
* ``minecraft:reference`` was removed (use the referenced id directly);
* ``minecraft:block_state_property`` was replaced by ``minecraft:match_block``;
* ``minecraft:value_check`` was split into ``int_value_check`` and
  ``float_value_check``;
* ``damage_source_properties.tags[].id`` now takes ids *and* ``#tag`` ids.
"""

from __future__ import annotations

from typing import Any

from . import entity_predicate as ep

PREDICATE_TYPES = {
    "minecraft:all_of", "minecraft:any_of", "minecraft:inverted",
    "minecraft:entity_properties", "minecraft:entity_scores",
    "minecraft:environment_attribute_check", "minecraft:damage_source_properties",
    "minecraft:killed_by_player", "minecraft:location_check",
    "minecraft:match_tool", "minecraft:match_block", "minecraft:random_chance",
    "minecraft:random_chance_with_enchanted_bonus", "minecraft:enchantment_active_check",
    "minecraft:table_bonus", "minecraft:survives_explosion", "minecraft:time_check",
    "minecraft:int_value_check", "minecraft:float_value_check",
    "minecraft:weather_check",
}


def is_predicate(node: Any) -> bool:
    if isinstance(node, list):
        return all(is_predicate(item) for item in node) and bool(node)
    if not isinstance(node, dict):
        return False
    kind = node.get("condition") or node.get("type")
    return isinstance(kind, str) and kind in PREDICATE_TYPES


def condition_from_list(value: Any, ctx, path: str = "") -> Any:
    """Old ``conditions: [p1, p2]`` -> new single ``condition`` value."""
    if not isinstance(value, list):
        return rewrite(value, ctx, path)[0]
    if len(value) == 1:
        return rewrite(value[0], ctx, path)[0]
    terms = [rewrite(item, ctx, path)[0] for item in value]
    return {"type": "minecraft:all_of", "terms": terms}


def rewrite(node: Any, ctx, path: str = "") -> tuple[Any, bool]:
    if isinstance(node, str):
        return node, False
    if isinstance(node, list):
        terms = [rewrite(item, ctx, path)[0] for item in node]
        if len(terms) == 1:
            ctx.change("predicate.discriminator", path, "single-element predicate list unwrapped")
            return terms[0], True
        ctx.change("predicate.discriminator", path, "predicate list -> all_of")
        return {"type": "minecraft:all_of", "terms": terms}, True
    if not isinstance(node, dict):
        return node, False

    has_condition = "condition" in node
    kind = node.get("condition") if has_condition else node.get("type")
    if not isinstance(kind, str):
        return node, False

    if kind in ("minecraft:reference", "reference"):
        ref = node.get("name") or node.get("value")
        if isinstance(ref, str):
            ctx.change("predicate.removed_types", path, f"reference {ref} -> direct id")
            return ref, True
        return node, False

    body = {key: value for key, value in node.items() if key not in ("condition", "type")}
    changed = has_condition

    if kind in ("minecraft:entity_properties", "entity_properties"):
        if isinstance(body.get("predicate"), dict):
            new_predicate = ep.normalize(body["predicate"], ctx, path)
            if new_predicate != body["predicate"]:
                body["predicate"] = new_predicate
                changed = True
        elif "predicate" not in body:
            # Old shorthand: the predicate object itself was the entity predicate.
            body = {"entity": "this", "predicate": ep.normalize(body, ctx, path)}
            changed = True

    elif kind in ("minecraft:all_of", "minecraft:any_of"):
        terms = body.get("terms")
        if isinstance(terms, list):
            new_terms = []
            for term in terms:
                new_term, _ = rewrite(term, ctx, path)
                new_terms.append(new_term)
            if new_terms != terms:
                body["terms"] = new_terms
                changed = True
        elif isinstance(terms, dict):
            new_term, _ = rewrite(terms, ctx, path)
            if new_term != terms:
                body["terms"] = new_term
                changed = True

    elif kind == "minecraft:inverted":
        if "term" in body:
            new_term, _ = rewrite(body["term"], ctx, path)
            if new_term != body["term"]:
                body["term"] = new_term
                changed = True

    elif kind == "minecraft:block_state_property":
        body = _block_state_property_to_match_block(body, ctx, path)
        kind = "minecraft:match_block"
        ctx.change("predicate.removed_types", path, "block_state_property -> match_block")
        changed = True

    elif kind == "minecraft:value_check":
        kind = _value_check_kind(body)
        if "range" in body:
            body["test"] = body.pop("range")
        ctx.change("predicate.removed_types", path, f"value_check -> {kind}")
        changed = True

    elif kind == "minecraft:damage_source_properties":
        if _prefix_damage_tags(body):
            changed = True
        for key in ("source", "source_entity", "direct_entity", "causing_entity"):
            value = body.get(key)
            if isinstance(value, dict):
                new_value = ep.normalize(value, ctx, path)
                if new_value != value:
                    body[key] = new_value
                    changed = True

    elif kind == "minecraft:location_check":
        if isinstance(body.get("predicate"), dict):
            new_predicate = _location_predicate(body["predicate"], ctx, path)
            if new_predicate != body["predicate"]:
                body["predicate"] = new_predicate
                changed = True

    elif kind == "minecraft:match_tool":
        if isinstance(body.get("predicate"), dict):
            new_predicate = ep.rewrite_item_predicate(body["predicate"], ctx, path)
            if new_predicate != body["predicate"]:
                body["predicate"] = new_predicate
                changed = True

    result: dict[str, Any] = {"type": kind}
    result.update(body)
    if changed:
        return result, True
    return node, False


def _location_predicate(node: dict, ctx, path: str) -> dict:
    out = dict(node)
    block = out.get("block")
    if isinstance(block, dict):
        out["block"] = ep.rewrite_item_predicate(block, ctx, path)
    return out


def _block_state_property_to_match_block(body: dict, ctx, path: str) -> dict:
    out: dict[str, Any] = {}
    block = body.get("block")
    if block is not None:
        out["blocks"] = block
    properties = body.get("properties")
    if properties is not None:
        out["state"] = properties
    for key, value in body.items():
        if key in ("block", "properties"):
            continue
        out[key] = value
    return out


def _value_check_kind(body: dict) -> str:
    def is_int(value: Any) -> bool:
        if isinstance(value, bool):
            return False
        if isinstance(value, int):
            return True
        if isinstance(value, dict):
            return all(is_int(v) for k, v in value.items() if k in ("min", "max"))
        return False

    if is_int(body.get("value")) and is_int(body.get("range")):
        return "minecraft:int_value_check"
    return "minecraft:float_value_check"


def _prefix_damage_tags(body: dict) -> bool:
    """``tags[].id`` used to hold damage type *tags* without ``#``."""
    tags = body.get("tags")
    changed = False
    if isinstance(tags, list):
        for entry in tags:
            if isinstance(entry, dict):
                ident = entry.get("id")
                if isinstance(ident, str) and not ident.startswith("#"):
                    entry["id"] = "#" + ident
                    changed = True
    return changed
