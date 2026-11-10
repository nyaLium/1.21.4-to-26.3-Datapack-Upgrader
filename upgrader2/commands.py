"""Line-level command surgery.

A 1.21.4 ``.mcfunction`` file is a list of command lines.  Each line may carry
several kinds of payload that changed between 1.21.4 and 26.3:

* game rule names (``/gamerule``),
* item component lists (``give @s stone_sword[unbreakable={}]``),
* inline predicates (``execute if predicate {...}``),
* text components (``tellraw``, ``title``, ``bossbar`` ...),
* entity/block NBT (``summon``, ``data merge``, ``setblock`` ...).

The rewriter is deliberately span based: only the payload that actually changed
is replaced, so untouched commands keep byte-identical formatting.
"""

from __future__ import annotations

from typing import Any, Iterator

from . import gamerule
from . import item_modifier
from . import nbt_rewrite
from . import particles
from . import predicate as predicates
from . import snbt
from . import text_component
from .item_components import clean_components

# Item components that exist in 1.21.4 and may appear in ``item[...]`` syntax.
# Used to tell an item component list from a block state list (``stone[facing=east]``).
ITEM_COMPONENT_IDS = {
    "unbreakable", "custom_name", "item_name", "lore", "enchantments",
    "stored_enchantments", "dyed_color", "custom_data", "item_model", "trim",
    "attribute_modifiers", "tooltip_display", "hide_tooltip",
    "hide_additional_tooltip", "damage", "max_damage", "max_stack_size",
    "enchantment_glint_override", "equippable", "food", "consumable",
    "potion_contents", "written_book_content", "writable_book_content",
    "block_state", "block_entity_data", "container", "charged_projectiles",
    "bundle_contents", "rarity", "repair_cost", "custom_model_data",
    "enchantment_glint_override", "profile", "fireworks", "firework_explosion",
    "banner_patterns", "bees", "instrument", "map_id", "pot_decorations",
    "tropical_fish/pattern", "swing_animation", "attack_animation",
    "interact_animation", "map_color", "jukebox_playable", "can_place_on",
    "can_break",
}

COMPONENT_COMMANDS = (
    "tellraw", "title", "bossbar", "team", "scoreboard", "dialog", "waypoint",
)


def process_text(text: str, path: str, ctx) -> tuple[str, int]:
    lines = text.split("\n")
    out: list[str] = []
    changed = 0
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.rstrip().endswith("\\") and not line.lstrip().startswith("#"):
            start = index
            logical = line.rstrip()
            while logical.endswith("\\") and index + 1 < len(lines):
                logical = logical[:-1].rstrip() + " " + lines[index + 1].strip()
                index += 1
            new_line = process_line(logical, path, ctx)
            if new_line == logical:
                out.extend(lines[start:index + 1])
            else:
                out.append(new_line)
                changed += 1
        else:
            new_line = process_line(line, path, ctx)
            if new_line != line:
                changed += 1
            out.append(new_line)
        index += 1
    return "\n".join(out), changed


def process_line(line: str, path: str, ctx) -> str:
    stripped = line.lstrip()
    if not stripped or stripped.startswith("#"):
        return line
    original = line

    line = gamerule.rewrite(line, ctx, path)
    line = particles.upgrade(line, ctx, path)
    line = _rewrite_team_color(line, ctx, path)
    line = _rewrite_nbt_paths(line, ctx, path)
    line = _rewrite_selector_nbt(line, ctx, path)
    line = _rewrite_data_value(line, ctx, path)
    line = _rewrite_item_brackets(line, ctx, path)
    line = _rewrite_regions(line, ctx, path)

    if line != original:
        ctx.change("function.line", path, "")
    return line


# ---------------------------------------------------------------------------
# NBT paths that address the old equipment lists
# ---------------------------------------------------------------------------

_PATH_ITEM = None
_PATH_INVENTORY = None


def _rewrite_nbt_paths(line: str, ctx, path: str) -> str:
    global _PATH_ITEM, _PATH_INVENTORY
    import re

    if _PATH_ITEM is None:
        _PATH_ITEM = re.compile(r"(?<![A-Za-z0-9_])(HandItems|ArmorItems)\[([0-3])\]")
    if _PATH_INVENTORY is None:
        # 1.21.5 moved the worn armour/off-hand item stacks to the equipment
        # map, so ``Inventory[{Slot:-106b}].components`` addresses nothing.
        _PATH_INVENTORY = re.compile(
            r"(?<![A-Za-z0-9_])Inventory\[\{Slot:\s*(-?\d+)[bBsSlL]?\}\]"
        )
    slots = {
        "HandItems": ["mainhand", "offhand"],
        "ArmorItems": ["feet", "legs", "chest", "head"],
    }

    def repl(match: "re.Match[str]") -> str:
        field, index = match.group(1), int(match.group(2))
        table = slots[field]
        if index >= len(table):
            return match.group(0)
        ctx.change("entity_nbt.equipment_map", path, f"{field}[{index}] -> equipment.{table[index]}")
        return f"equipment.{table[index]}"

    def repl_inventory(match: "re.Match[str]") -> str:
        slot = int(match.group(1))
        name = nbt_rewrite.INVENTORY_EQUIPMENT_SLOTS.get(slot)
        if name is None:
            return match.group(0)
        ctx.change("entity_nbt.equipment_map", path,
                   f"Inventory[{{Slot:{slot}}}] -> equipment.{name}")
        return f"equipment.{name}"

    line = _PATH_ITEM.sub(repl, line)
    return _PATH_INVENTORY.sub(repl_inventory, line)


# ---------------------------------------------------------------------------
# team colours: 26.2 only accepts lowercase snake_case
# ---------------------------------------------------------------------------

_TEAM_COLOR = None


def _rewrite_team_color(line: str, ctx, path: str) -> str:
    global _TEAM_COLOR
    import re

    if _TEAM_COLOR is None:
        _TEAM_COLOR = re.compile(r"\b(team\s+modify\s+\S+\s+color|waypoint\s+\S+\s+modify\s+\S+\s+color)\s+([A-Za-z_]+)")
    def repl(match: "re.Match[str]") -> str:
        name = match.group(2)
        snake = _snake(name)
        if snake == name:
            return match.group(0)
        ctx.change("command.team_color", path, f"{name} -> {snake}")
        return f"{match.group(1)} {snake}"

    return _TEAM_COLOR.sub(repl, line)


def _snake(name: str) -> str:
    import re

    out = re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", name)
    return out.lower().replace("purple", "purple")


# ---------------------------------------------------------------------------
# data ... value <literal>
# ---------------------------------------------------------------------------

_DATA_VALUE = None


def _rewrite_data_value(line: str, ctx, path: str) -> str:
    global _DATA_VALUE
    import re

    if _DATA_VALUE is None:
        _DATA_VALUE = re.compile(r"\bdata\s+(?:modify|merge)\b.*?\bvalue\s+(?=['\"])")
    match = _DATA_VALUE.search(line)
    if not match:
        return line
    start = match.end()
    node = snbt.try_parse(line, start, allow_bare=True)
    if node is None or node.end > len(line):
        return line
    value = node.to_py()
    if not isinstance(value, (str, list, dict)):
        return line
    new = text_component.inline_value(value)
    if new == value:
        return line
    ctx.change("text.component_inline", path, "data value JSON string -> inline")
    return line[:start] + snbt.dumps(new) + line[node.end:]


# ---------------------------------------------------------------------------
# selector NBT:  @e[nbt={CustomName:'...'}, ...]
# ---------------------------------------------------------------------------

_NBT_ARG = None


def _rewrite_selector_nbt(line: str, ctx, path: str) -> str:
    global _NBT_ARG
    import re

    if _NBT_ARG is None:
        # ``nbt={...}`` and the negated ``nbt=!{...}`` form both carry payload
        # that needs rewriting; the ``!`` sits between ``=`` and ``{``.
        _NBT_ARG = re.compile(r"(?<![A-Za-z0-9_])nbt\s*=\s*!?\s*\{")
    positions = [match.end() - 1 for match in _NBT_ARG.finditer(line)]
    for start in reversed(positions):
        end = _matching(line, start)
        if end is None:
            continue
        node = snbt.try_parse(line, start, allow_bare=True)
        if node is None or node.end != end + 1:
            continue
        value = node.to_py()
        if not isinstance(value, dict):
            continue
        if nbt_rewrite.rewrite_compound(value, ctx, path):
            line = line[:start] + snbt.dumps(value) + line[end + 1:]
    return line


# ---------------------------------------------------------------------------
# item component lists:  give @s stone_sword[unbreakable={}]
# ---------------------------------------------------------------------------

def _rewrite_item_brackets(line: str, ctx, path: str) -> str:
    positions = []
    i, n = 0, len(line)
    while i < n:
        char = line[i]
        if char in "'\"":
            i = _skip_string(line, i)
            continue
        if char == "[" and i > 0 and (line[i - 1].isalnum() or line[i - 1] in "_:"):
            end = _matching(line, i)
            if end is None:
                break
            j = i - 1
            while j >= 0 and (line[j].isalnum() or line[j] in "_:/.-"):
                j -= 1
            if j < 0 or line[j] != "@":
                positions.append((j + 1, i, end + 1))
            i = end + 1
            continue
        i += 1

    for start, bracket, end in reversed(positions):
        body = line[bracket + 1:end - 1]
        pairs = _parse_component_pairs(body)
        if pairs is None:
            continue
        keys = {key.split(":")[-1] for key, _value, _raw in pairs}
        if not (keys & ITEM_COMPONENT_IDS):
            continue
        mapping = {key: value for key, value, _raw in pairs}
        cleaned = clean_components(mapping, ctx, path)
        new_body = ",".join(f"{key}={snbt.dumps(value)}" for key, value in cleaned.items())
        if new_body != body:
            line = line[:bracket + 1] + new_body + line[end - 1:]
    return line


def _parse_component_pairs(body: str) -> list[tuple[str, Any, str]] | None:
    if not body.strip():
        return []
    parts = _split_top_level(body, ",")
    pairs = []
    for part in parts:
        if "=" not in part:
            return None
        key, _, raw = part.partition("=")
        key = key.strip()
        if not key:
            return None
        node = snbt.try_parse(raw, 0, allow_bare=True)
        if node is None:
            return None
        value = node.to_py()
        if key.split(":")[-1] in ("lore", "custom_name", "item_name", "name", "title",
                                  "description", "pages"):
            value = text_component.inline_value(value)
        pairs.append((key, value, raw))
    return pairs


def _split_top_level(text: str, sep: str) -> list[str]:
    parts = []
    depth = 0
    i = 0
    start = 0
    n = len(text)
    while i < n:
        char = text[i]
        if char in "'\"":
            i = _skip_string(text, i)
            continue
        if char in "{[":
            depth += 1
        elif char in "}]":
            depth -= 1
        elif char == sep and depth == 0:
            parts.append(text[start:i])
            start = i + 1
        i += 1
    parts.append(text[start:])
    return parts


# ---------------------------------------------------------------------------
# SNBT payload regions
# ---------------------------------------------------------------------------

def _rewrite_regions(line: str, ctx, path: str) -> str:
    regions = list(_iter_regions(line))
    if not regions:
        return line
    for start, end in reversed(regions):
        prefix = line[:start].rstrip()
        node = snbt.try_parse(line, start, allow_bare=True)
        if node is None or node.end != end:
            continue
        value = node.to_py()
        kind = _region_kind(prefix, value)
        if kind == "predicate":
            new, changed = predicates.rewrite(value, ctx, path)
        elif kind == "modifier":
            new, changed = item_modifier.upgrade(value, ctx, path)
        elif kind == "component":
            new, changed = text_component.rewrite_tree(value)
        elif kind == "nbt":
            changed = nbt_rewrite.rewrite_compound(value, ctx, path) if isinstance(value, dict) else False
            new = value
        else:
            continue
        if changed:
            replacement = snbt.dumps(new)
            line = line[:start] + replacement + line[end:]
    return line


def _region_kind(prefix: str, value: Any) -> str:
    tail = prefix.split()[-1] if prefix.split() else ""
    if tail == "predicate" or prefix.endswith("predicate "):
        return "predicate"
    if isinstance(value, dict):
        name = value.get("function") or value.get("type")
        if isinstance(name, str) and name.split(":")[-1] in item_modifier.ITEM_MODIFIER_TYPES:
            return "modifier"
    if text_component.looks_like_component(value) and _is_component_context(prefix):
        return "component"
    if isinstance(value, dict):
        return "nbt"
    return "unknown"


_COMPONENT_PREFIX = None


def _is_component_context(prefix: str) -> bool:
    global _COMPONENT_PREFIX
    import re

    if _COMPONENT_PREFIX is None:
        _COMPONENT_PREFIX = re.compile(
            r"(?:^|[;&|]|\brun\s+)\s*/?(tellraw|title|bossbar|team|scoreboard|dialog|waypoint)\b"
            r"[^;&|]*$"
        )
    stripped = prefix[1:] if prefix.lstrip().startswith("$") else prefix
    return bool(_COMPONENT_PREFIX.search(stripped))


def _iter_regions(line: str) -> Iterator[tuple[int, int]]:
    i, n = 0, len(line)
    while i < n:
        char = line[i]
        if char in "'\"":
            i = _skip_string(line, i)
            continue
        if char in "{[":
            end = _matching(line, i)
            if end is None:
                return
            yield (i, end + 1)
            i = end + 1
            continue
        i += 1


def _skip_string(text: str, start: int) -> int:
    quote = text[start]
    i = start + 1
    n = len(text)
    while i < n:
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == quote:
            return i + 1
        i += 1
    return n


def _matching(text: str, start: int) -> int | None:
    pairs = {"{": "}", "[": "]"}
    stack = []
    i, n = start, len(text)
    while i < n:
        char = text[i]
        if char in "'\"":
            i = _skip_string(text, i)
            continue
        if char in pairs:
            stack.append(pairs[char])
        elif char in "}]":
            if not stack or stack.pop() != char:
                return None
            if not stack:
                return i
        i += 1
    return None
