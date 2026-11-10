"""Item data-component migrations (1.21.5 and 26.3).

Three independent changes affect component maps:

* 1.21.5 removed the ``hide_tooltip`` and ``hide_additional_tooltip``
  components and the per-component ``show_in_tooltip`` field; both are replaced
  by ``minecraft:tooltip_display`` (``hide_tooltip`` / ``hidden_components``).
* 26.3 split ``minecraft:swing_animation`` into ``attack_animation`` and
  ``interact_animation``.
* 26.3 removed ``minecraft:map_color``.

Component maps appear both in JSON files (``set_components`` modifiers, item
predicates) and inside command SNBT (``give @s stone_sword[...]``), so the
helpers here operate on plain ordered dicts and are shared by both.
"""

from __future__ import annotations

from typing import Any

TOOLTIP_DISPLAY = "minecraft:tooltip_display"
REMOVED_TOOLTIP_COMPONENTS = {"minecraft:hide_tooltip", "minecraft:hide_additional_tooltip"}
ANIMATION = "minecraft:swing_animation"
MAP_COLOR = "minecraft:map_color"

# String components whose value is a resource location.  A missing namespace
# defaults to minecraft:, but writing it out is stricter and survives tooling
# that does not apply the default.
NAMESPACED_VALUES = {"item_model", "tooltip_style"}


def _split(cid: str) -> tuple[str, str]:
    if ":" in cid:
        return tuple(cid.split(":", 1))  # type: ignore[return-value]
    return "minecraft", cid


def _join(namespace: str, path: str, like: str) -> str:
    return f"{namespace}:{path}" if ":" in like else path


def clean_components(comps: dict[str, Any], ctx, path: str = "") -> dict[str, Any]:
    """Rewrite one data-component map for 26.3."""
    if not isinstance(comps, dict):
        return comps

    out: dict[str, Any] = {}
    hidden: list[str] = []
    hide_tooltip = False

    existing_tooltip = None
    for key, value in comps.items():
        namespace, field = _split(key)
        if namespace == "minecraft" and field == "tooltip_display" and isinstance(value, dict):
            existing_tooltip = dict(value)

    for cid, value in comps.items():
        namespace, field = _split(cid)
        if namespace == "minecraft" and field in ("hide_tooltip", "hide_additional_tooltip"):
            hide_tooltip = True
            ctx.change("item_component.tooltip_display", path, f"{cid} -> tooltip_display")
            continue
        if namespace == "minecraft" and field == "map_color":
            ctx.change("item_component.map_color", path, "map_color removed")
            continue
        if namespace == "minecraft" and field == "swing_animation":
            payload = value if isinstance(value, dict) else {}
            out["minecraft:attack_animation"] = dict(payload)
            out["minecraft:interact_animation"] = dict(payload)
            ctx.change("item_component.animation_split", path, "swing_animation -> attack/interact_animation")
            continue

        if isinstance(value, dict) and "show_in_tooltip" in value:
            payload = dict(value)
            visible = payload.pop("show_in_tooltip")
            if visible is False:
                hidden.append(cid if ":" in cid else f"minecraft:{cid}")
            ctx.change("item_component.tooltip_display", path, f"{cid}.show_in_tooltip removed")
            value = payload

        flattened = _flatten_component(namespace, field, value, ctx, path)
        if (namespace == "minecraft" and field in NAMESPACED_VALUES
                and isinstance(flattened, str) and ":" not in flattened):
            ctx.change("item_component.namespace", path,
                       f"{field}: {flattened} -> minecraft:{flattened}")
            flattened = f"minecraft:{flattened}"
        out[cid] = flattened

    tooltip = existing_tooltip or {}
    if hide_tooltip:
        tooltip["hide_tooltip"] = True
    if hidden:
        current = tooltip.get("hidden_components")
        merged = list(current) if isinstance(current, list) else []
        for cid in hidden:
            if cid not in merged:
                merged.append(cid)
        tooltip["hidden_components"] = merged

    if tooltip:
        # ``tooltip_display`` itself must not carry show_in_tooltip.
        out[TOOLTIP_DISPLAY] = tooltip
    return out


def clean_component_list(pairs: list[tuple[str, Any]], ctx, path: str = "") -> list[tuple[str, Any]]:
    """Same as :func:`clean_components` but for command SNBT ordered pairs."""
    mapping = dict(pairs)
    cleaned = clean_components(mapping, ctx, path)
    return list(cleaned.items())


# 1.21.5 collapsed several components into their "simplified" form.
_FLATTEN_KEYS = {
    "enchantments": ("levels", None),
    "stored_enchantments": ("levels", None),
    "attribute_modifiers": ("modifiers", list),
    "dyed_color": ("rgb", None),
    "can_place_on": ("predicates", "one_or_many"),
    "can_break": ("predicates", "one_or_many"),
}


def _flatten_component(namespace: str, field: str, value: Any, ctx, path: str) -> Any:
    if namespace != "minecraft" or not isinstance(value, dict):
        return value
    spec = _FLATTEN_KEYS.get(field)
    if spec is None:
        return value
    inner_key, mode = spec
    if inner_key not in value:
        return value
    inner = value[inner_key]
    rest = {key: item for key, item in value.items() if key != inner_key}
    if rest:
        # unexpected extra fields: keep the full object rather than losing data
        return value
    if mode == "one_or_many" and isinstance(inner, list):
        if len(inner) == 1:
            ctx.change("item_component.simplified_form", path, f"{field}.predicates inlined")
            return inner[0]
        ctx.change("item_component.simplified_form", path, f"{field}.predicates inlined")
        return inner
    ctx.change("item_component.simplified_form", path, f"{field}.{inner_key} inlined")
    return inner
