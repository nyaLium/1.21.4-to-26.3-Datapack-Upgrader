"""Vanilla tag renames between 1.21.4 and 26.3."""

from __future__ import annotations

TAG_RENAMES = {
    # 1.21.5 -> 1.21.6
    "#minecraft:dead_bush_may_place_on": "#minecraft:dry_vegetation_may_place_on",
    "#minecraft:plays_ambient_desert_block_sounds":
        "#minecraft:triggers_ambient_desert_dry_vegetation_block_sounds",
    # 26.1
    "#minecraft:dry_vegetation_may_place_on": "#minecraft:supports_dry_vegetation",
    "#minecraft:bamboo_plantable_on": "#minecraft:supports_bamboo",
    "#minecraft:small_dripleaf_placeable": "#minecraft:supports_small_dripleaf",
    "#minecraft:big_dripleaf_placeable": "#minecraft:supports_big_dripleaf",
    "#minecraft:mushroom_grow_block": "#minecraft:overrides_mushroom_light_requirement",
    "#minecraft:snow_layer_can_survive_on": "#minecraft:support_override_snow_layer",
    "#minecraft:snow_layer_cannot_survive_on": "#minecraft:cannot_support_snow_layer",
    # 26.2
    "#minecraft:concrete_powder": "#minecraft:concrete_powders",
    # 26.3
    "#minecraft:convertable_to_mud": "#minecraft:convertible_to_mud",
    "#minecraft:dowses_campfires": "#minecraft:douses_campfires",
    "#on_woodland_explorer_maps": "#on_woodland_mansion_maps",
    "#on_ocean_explorer_maps": "#on_ocean_monument_maps",
    "#on_jungle_explorer_maps": "#on_jungle_pyramid_maps",
    "#on_swamp_explorer_maps": "#on_swamp_hut_maps",
    "#on_trial_explorer_maps": "#on_buried_trial_chambers_maps",
    "#on_trial_explorer_map": "#on_buried_trial_chambers_map",
    # 1.21.11
    "#minecraft:enchantable/sword": "#minecraft:enchantable/sweeping",
}


def rename_tag(value: str) -> str:
    """Apply renames transitively (dead_bush -> dry_vegetation -> supports_...)."""
    seen = set()
    while value in TAG_RENAMES and value not in seen:
        seen.add(value)
        value = TAG_RENAMES[value]
    return value
