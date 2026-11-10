"""Version constants and the rule catalogue for the 1.21.4 -> 26.3 upgrader.

Every rule carries the source it was derived from so the generated report can
cite it.  Sources are English Minecraft Wiki pages (raw wikitext) plus the
curated "breaking changes" log at vanillalibrary.mcfpp.top; page hashes are not
recorded because the wiki is edited continuously - the section/revision note is
enough to re-verify a rule.
"""

from __future__ import annotations

from dataclasses import dataclass


SOURCE_PACK_FORMAT = 61          # 1.21.4 data pack format
TARGET_PACK_VERSION = (121, 0)   # 26.3 data pack format


@dataclass(frozen=True)
class Rule:
    """One documented conversion rule."""

    ident: str
    title: str
    source: str
    since: str = "26.3"
    note: str = ""


RULES: tuple[Rule, ...] = (
    Rule(
        "pack_mcmeta.min_max_format",
        "pack.mcmeta: pack_format -> min_format/max_format",
        "Minecraft Wiki, pack.mcmeta §Format + §History (1.21.9, 25w31a)",
        "1.21.9",
        "min_format/max_format are the required fields; pack_format and "
        "supported_formats must be absent unless the pack also targets <=1.21.8.",
    ),
    Rule(
        "text.component_inline",
        "Text components stored as JSON strings -> inline NBT",
        "Minecraft Wiki, Text component format §History (1.21.5, 25w02a)",
        "1.21.5",
    ),
    Rule(
        "text.click_event",
        "clickEvent -> click_event, payload value -> command/url/path/page",
        "Minecraft Wiki, Text component format §History (1.21.5, 25w02a)",
        "1.21.5",
    ),
    Rule(
        "text.hover_event",
        "hoverEvent -> hover_event, contents inlined, type->id, id->uuid",
        "Minecraft Wiki, Text component format §History (1.21.5, 25w02a/25w03a)",
        "1.21.5",
    ),
    Rule(
        "item_component.tooltip_display",
        "hide_tooltip / show_in_tooltip -> minecraft:tooltip_display",
        "Minecraft Wiki, Data component format §minecraft:tooltip_display (1.21.5, 25w04a)",
        "1.21.5",
    ),
    Rule(
        "item_component.animation_split",
        "minecraft:swing_animation -> attack_animation / interact_animation",
        "Minecraft Wiki, Java Edition 26.3 §Changes>General>Data component format",
        "26.3",
    ),
    Rule(
        "item_component.map_color",
        "minecraft:map_color component removed",
        "Minecraft Wiki, Java Edition 26.3 §Changes>General>Data component format",
        "26.3",
    ),
    Rule(
        "block_state.codec",
        "Block state {Name,Properties} -> {id,properties}",
        "Minecraft Wiki, Java Edition 26.3 §Changes>General>Block states",
        "26.3",
    ),
    Rule(
        "entity_predicate.namespaced_keys",
        "Entity predicate keys are namespaced ids; type -> minecraft:entity_type; "
        "type_specific/<kind> flattened",
        "Minecraft Wiki, Entity predicate §Data format; Java Edition 26.2 (snapshot 3/4)",
        "26.2",
    ),
    Rule(
        "predicate.discriminator",
        "Predicate condition -> type (mandatory); predicate lists -> all_of",
        "Minecraft Wiki, Java Edition 26.3 §Changes>General>Predicate",
        "26.3",
    ),
    Rule(
        "predicate.removed_types",
        "reference removed, block_state_property -> match_block, "
        "value_check -> int/float_value_check",
        "Minecraft Wiki, Java Edition 26.3 §Changes>General>Predicate",
        "26.3",
    ),
    Rule(
        "item_modifier.discriminator",
        "Item modifier function -> type",
        "Minecraft Wiki, Java Edition 26.3 §Changes>General>Loot functions",
        "26.3",
    ),
    Rule(
        "item_modifier.sequence",
        "Item modifier root list -> minecraft:sequence",
        "Minecraft Wiki, Java Edition 26.3 §Changes>General>Loot functions",
        "26.3",
    ),
    Rule(
        "loot_table.renames",
        "Loot table functions -> modifier, conditions -> condition, tag name -> items",
        "Minecraft Wiki, Java Edition 26.3 §Changes>General>Loot table",
        "26.3",
    ),
    Rule(
        "advancement.background",
        "Advancement background: required on displayed roots, forbidden elsewhere, "
        "textures/ prefix and .png suffix dropped",
        "Minecraft Wiki, Advancement definition §History (1.21.5, 25w04a) + Java Edition 26.3",
        "26.3",
    ),
    Rule(
        "advancement.trigger_fields",
        "Advancement trigger fields: recipe->recipes, block->blocks, "
        "loot_table->loot_tables, player -> single predicate",
        "Minecraft Wiki, Java Edition 26.3 §Changes>General>Advancement",
        "26.3",
    ),
    Rule(
        "gamerule.registry_id",
        "Game rules are registry ids: camelCase -> minecraft:snake_case",
        "Minecraft Wiki, Game rule §List of game rules; Java Edition 1.21.11 (25w45a)",
        "1.21.11",
    ),
    Rule(
        "entity_nbt.renamed_fields",
        "Entity NBT renames (HurtByTimestamp -> ticks_since_last_hurt_by_mob, ...)",
        "Minecraft Wiki, Entity format; Java Edition 26.2 (snapshot 3)",
        "26.2",
    ),
    Rule(
        "tags.renamed",
        "Vanilla tag renames (1.21.5, 26.1, 26.3)",
        "Minecraft Wiki, Tag §History; Java Edition 26.3 §Changes>General>Tags",
        "26.3",
    ),
    Rule(
        "json.strict_parsing",
        "26.3 fails the whole pack on any unparseable JSON file",
        "Minecraft Wiki, Java Edition 26.3 §Changes>General>Data pack (MC-310325)",
        "26.3",
    ),
    # -- bookkeeping rules (no schema meaning of their own) -----------------
    Rule(
        "function.line",
        "A function line had at least one payload rewritten",
        "aggregate counter",
        "26.3",
    ),
    Rule(
        "json.file_rewritten",
        "A JSON file was rewritten (any of the rules above)",
        "aggregate counter",
        "26.3",
    ),
    Rule(
        "entity_nbt.equipment_map",
        "ArmorItems/HandItems/body_armor_item -> equipment, drop chances -> drop_chances, "
        "Inventory[{Slot:100b/101b/102b/103b/-106b}] -> equipment.feet/legs/chest/head/offhand",
        "Minecraft Wiki, Entity format §History (1.21.5, 25w03a) + player.dat format "
        "§Inventory slot numbers; MC-296199",
        "1.21.5",
        "1.21.4 kept the worn armour and the off-hand item inside the player's Inventory "
        "list with flat slot numbers.  26.3 stores them in the equipment map, so an "
        "nbt={Inventory:[{Slot:-106b,...}]} predicate never matches.  Slots 0-35 are the "
        "real main inventory and are left alone.",
    ),
    Rule(
        "item_component.simplified_form",
        "Components collapsed to their simplified form (enchantments.levels, "
        "attribute_modifiers.modifiers, dyed_color.rgb, can_place_on.predicates)",
        "Minecraft Wiki, Java Edition 1.21.5 §Technical>Changes>General>Data components",
        "1.21.5",
    ),
    Rule(
        "id.renamed",
        "Renamed block/item ids (minecraft:chain -> minecraft:iron_chain)",
        "Minecraft Wiki, Java Edition 1.21.9 §Changes>Blocks",
        "1.21.9",
    ),
    Rule(
        "recipe.cooking_time",
        "Cooking recipes no longer differ per block; smoker/blast furnace times doubled",
        "Minecraft Wiki, Java Edition 26.3 §Changes>General>Recipes",
        "26.3",
    ),
    Rule(
        "command.team_color",
        "Team colours are lowercase snake_case only",
        "Minecraft Wiki, Java Edition 26.2 §Changes>Command format",
        "26.2",
    ),
    Rule(
        "particle.flash_color",
        "particle flash requires a color (ARGB) option; opaque white is inserted",
        "Minecraft Wiki, Particle format §History (1.21.9, 25w36a) + Java Edition 1.21.9 §Particles",
        "1.21.9",
        "``color`` is a list of four floats (r, g, b, a) or a packed ARGB int. "
        "1.21.4's flash had no option and rendered white, so the default keeps "
        "the old look.",
    ),
    Rule(
        "json.dangling_reference",
        "JSON file deleted: a cross-file reference does not resolve (fatal in 26.3)",
        "Mojira MC-310325 (26.3-snapshot-3: errors in advancement/loot_table/"
        "recipe/predicate/item_modifier et al. block the whole world from loading) "
        "+ MC-311918 (recipes with unknown items)",
        "26.3",
        "The target does not exist in the pack and cannot be invented, so the "
        "file is removed instead of being left as a load-time landmine.",
    ),
    Rule(
        "json.reward_dropped",
        "Dangling advancement rewards entry removed, advancement kept",
        "Mojira MC-310325 (26.3-snapshot-3)",
        "26.3",
        "A missing rewards.function/loot/recipes would block the whole pack.  "
        "The advancement itself is still valid and may be granted by functions, "
        "so only the broken reward entry is dropped.",
    ),
    Rule(
        "json.invalid_deleted",
        "JSON file deleted: unparseable file inside a strict 26.3 registry",
        "Mojira MC-310325 (26.3-snapshot-3)",
        "26.3",
        "A parse error in one of the strict registries blocks the whole world; "
        "the broken file is removed so the rest of the pack can load.",
    ),
    # -- 2.1 additions: advancement strictness -------------------------------
    Rule(
        "advancement.unknown_field",
        "Unknown advancement / display / icon / rewards fields removed",
        "Minecraft Wiki, Advancement definition §JSON format",
        "26.3",
        "Unknown keys are ignored by the game; they are dropped so the file "
        "matches the 26.3 schema exactly.",
    ),
    Rule(
        "item_component.namespace",
        "Resource-location component values (item_model, tooltip_style) get an "
        "explicit minecraft: namespace",
        "Minecraft Wiki, Data component format (item_model / tooltip_style)",
        "26.3",
    ),
    Rule(
        "json.tab_indent",
        "Rewritten JSON uses tab indentation, LF newlines, no BOM",
        "house style",
        "26.3",
    ),
)


def rule(ident: str) -> Rule:
    for item in RULES:
        if item.ident == ident:
            return item
    raise KeyError(ident)
