"""Post-upgrade linter.

The linter is the safety net: it re-reads the produced pack and looks for any
syntax that 26.3 rejects.  It deliberately checks the *output* only, so it also
catches bugs in the converters themselves.
"""

from __future__ import annotations

import json
import os
import re

from .textio import rel, walk

FUNC_LEFTOVERS = {
    "text.clickEvent": re.compile(r"\bclickEvent\b"),
    "text.hoverEvent": re.compile(r"\bhoverEvent\b"),
    "text.show_item_contents": re.compile(r"\bshow_item\b[^}]*\bcontents\s*:"),
    "block_state.Name": re.compile(r"\b(?:block_state|BlockState|carriedBlockState)\s*:\s*\{[^{}]*\bName\s*:"),
    "nbt.HandItems": re.compile(r"(?<![A-Za-z0-9_])HandItems\s*:"),
    "nbt.ArmorItems": re.compile(r"(?<![A-Za-z0-9_])ArmorItems\s*:"),
    "nbt.HurtByTimestamp": re.compile(r"(?<![A-Za-z0-9_])HurtByTimestamp\b"),
    "nbt.AngerTime": re.compile(r"(?<![A-Za-z0-9_])AngerTime\s*:"),
    "nbt.FallDistance": re.compile(r"(?<![A-Za-z0-9_])FallDistance\s*:"),
    "item.show_in_tooltip": re.compile(r"\bshow_in_tooltip\s*:"),
    "item.enchantments_levels": re.compile(r"\benchantments\s*=\s*\{\s*levels\s*:"),
    "gamerule.camelCase": re.compile(r"\bgamerule\s+[a-z]+[A-Z][A-Za-z]*\b"),
    "predicate.condition": re.compile(r"\bpredicate\s*\{\s*condition\s*:"),
    "item_modifier.function": re.compile(r"\{\s*\"?function\"?\s*:"),
    "text.component_json_string": re.compile(
        r"['\"]\{\\?\"(?:text|translate|score|selector|nbt|keybind|extra)\\?\""
    ),
}

JSON_LEFTOVERS = {
    "item_modifier.function": re.compile(r'"function"\s*:'),
    "item_modifier.conditions": re.compile(r'"conditions"\s*:'),
    "predicate.condition": re.compile(r'"condition"\s*:'),
    "loot_table.functions": re.compile(r'"functions"\s*:'),
}

# directories that 1.21.4 never loaded - the linter ignores them
DEAD_SEGMENTS = {
    "functions", "advancements", "predicates", "recipes", "loot_tables",
    "item_modifiers", "damage_types", "enchantments", "dimensions",
    "structures", "items", "entity_types", "blocks", "fluids", "tags/items",
    "tags/entity_types", "tags/functions", "sounds.json",
}

LOADED_REGISTRIES = {
    "advancement", "banner_pattern", "cat_variant", "chat_type", "chicken_variant",
    "cow_variant", "damage_type", "dimension", "dimension_type", "enchantment",
    "enchantment_provider", "frog_variant", "instrument", "item_modifier",
    "jukebox_song", "loot_table", "painting_variant", "pig_variant", "predicate",
    "recipe", "structure", "test_environment", "test_instance", "trim_material",
    "trim_pattern", "wolf_sound_variant", "wolf_variant", "worldgen",
}

LOADED_TAG_TYPES = {
    "function", "item", "block", "entity_type", "damage_type", "fluid",
    "game_event", "banner_pattern", "instrument", "painting_variant",
    "enchantment", "point_of_interest_type", "worldgen/biome", "dialog",
    "timeline", "trade_set", "villager_trade", "potion",
}


def is_dead(rp: str) -> bool:
    parts = rp.split("/")
    if len(parts) < 3 or parts[0] != "data":
        return False
    if parts[2] == "tags":
        if len(parts) < 4:
            return True
        return parts[3] not in LOADED_TAG_TYPES
    return parts[2] not in LOADED_REGISTRIES


def is_dead_function(rp: str) -> bool:
    parts = rp.split("/")
    if len(parts) < 3 or parts[0] != "data":
        return False
    return parts[2] != "function"


def registry_of(rp: str) -> str:
    parts = rp.split("/")
    if len(parts) < 3:
        return ""
    if parts[2] == "tags" and len(parts) >= 4:
        return "tags/" + parts[3]
    return parts[2]


def lint_pack(root: str) -> tuple[list[str], dict[str, int]]:
    issues: list[str] = []
    stats: dict[str, int] = {}

    def bump(name: str) -> None:
        stats[name] = stats.get(name, 0) + 1

    meta_path = os.path.join(root, "pack.mcmeta")
    try:
        with open(meta_path, encoding="utf-8-sig") as handle:
            meta = json.load(handle)
        pack = meta.get("pack", {})
        if "min_format" not in pack or "max_format" not in pack:
            issues.append("pack.mcmeta: missing min_format/max_format")
            bump("packmeta.missing_range")
        if "pack_format" in pack:
            issues.append("pack.mcmeta: deprecated pack_format still present")
            bump("packmeta.pack_format")
        if "supported_formats" in pack:
            issues.append("pack.mcmeta: removed supported_formats still present")
            bump("packmeta.supported_formats")
    except Exception as exc:  # noqa: BLE001
        issues.append(f"pack.mcmeta: invalid JSON ({exc})")
        bump("packmeta.invalid")

    data = os.path.join(root, "data")
    for path in walk(data, ".json"):
        rp = rel(root, path)
        if is_dead(rp):
            continue
        registry = registry_of(rp)
        try:
            with open(path, encoding="utf-8-sig") as handle:
                text = handle.read()
            node = json.loads(text)
        except Exception as exc:  # noqa: BLE001
            issues.append(f"invalid JSON: {rp} ({exc})")
            bump("json.invalid")
            continue

        for name, rx in JSON_LEFTOVERS.items():
            if not rx.search(text):
                continue
            if name == "predicate.condition" and registry != "predicate":
                continue
            if name == "item_modifier.function" and registry != "item_modifier":
                continue
            if name == "item_modifier.conditions" and registry != "item_modifier":
                continue
            if name == "loot_table.functions" and registry != "loot_table":
                continue
            issues.append(f"{name} left in {rp}")
            bump(name)

        if registry == "item_modifier" and isinstance(node, list):
            issues.append(f"item modifier root is still a list: {rp}")
            bump("item_modifier.root_list")
        if registry == "predicate" and isinstance(node, list):
            issues.append(f"predicate root is still a list: {rp}")
            bump("predicate.root_list")
        if registry == "advancement" and isinstance(node, dict):
            display = node.get("display")
            if isinstance(display, dict):
                if node.get("parent") is None and "background" not in display:
                    issues.append(f"displayed root advancement without background: {rp}")
                    bump("advancement.background_missing")
                if node.get("parent") is not None and "background" in display:
                    issues.append(f"non-root advancement has a background: {rp}")
                    bump("advancement.background_nonroot")

    for path in walk(data, ".mcfunction"):
        rp = rel(root, path)
        if is_dead_function(rp):
            continue
        with open(path, encoding="utf-8-sig", errors="replace") as handle:
            text = handle.read()
        for lineno, line in enumerate(text.split("\n"), 1):
            stripped = line.lstrip()
            if not stripped or stripped.startswith("#"):
                continue
            for name, rx in FUNC_LEFTOVERS.items():
                if rx.search(line):
                    issues.append(f"{name} left at {rp}:{lineno}")
                    bump(name)

    return issues, stats
