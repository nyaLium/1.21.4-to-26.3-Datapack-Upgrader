"""Unit and end-to-end tests for the 1.21.4 -> 26.3 data pack upgrader.

Run with:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from upgrader2 import advancement, commands, integrity, item_modifier, jsonio, loot_table, predicate, snbt, tags, text_component
from upgrader2.pipeline import _save_json, upgrade_pack
from upgrader2.report import Report


class SnbtTests(unittest.TestCase):
    def test_roundtrip_preserves_types(self) -> None:
        text = "{a:1,b:[1b,2b],c:'{d:1}',e:0.5f,g:true}"
        value = snbt.parse(text).to_py()
        self.assertEqual(snbt.dumps(value), text.replace(" ", ""))

    def test_escaped_json_string(self) -> None:
        node = snbt.parse(r"""{CustomName:'{"text":"Hi"}'}""")
        self.assertEqual(node.to_py()["CustomName"], '{"text":"Hi"}')

    def test_heterogeneous_list(self) -> None:
        node = snbt.parse('[{"text":"a"},"b",1]')
        self.assertEqual(len(node.to_py()), 3)

    def test_bare_token_lenient_mode(self) -> None:
        node = snbt.parse('{Tags:["E",FuryVersion]}', allow_bare=True)
        self.assertEqual(node.to_py()["Tags"], ["E", "FuryVersion"])

    def test_rejects_garbage(self) -> None:
        with self.assertRaises(snbt.SnbtError):
            snbt.parse("not snbt at all")


class TextComponentTests(unittest.TestCase):
    def test_click_event(self) -> None:
        new, _ = text_component.rewrite(
            {"text": "x", "clickEvent": {"action": "run_command", "value": "/say hi"}}
        )
        self.assertEqual(new["click_event"], {"action": "run_command", "command": "/say hi"})

    def test_change_page_to_int(self) -> None:
        new, _ = text_component.rewrite(
            {"text": "x", "clickEvent": {"action": "change_page", "value": "3"}}
        )
        self.assertEqual(new["click_event"]["page"], 3)

    def test_hover_show_item_inline(self) -> None:
        new, _ = text_component.rewrite(
            {"hoverEvent": {"action": "show_item", "contents": {"id": "minecraft:stick", "count": 2}}}
        )
        self.assertEqual(new["hover_event"], {"action": "show_item", "id": "minecraft:stick", "count": 2})

    def test_hover_show_entity_id_and_uuid(self) -> None:
        new, _ = text_component.rewrite(
            {"hoverEvent": {"action": "show_entity", "contents": {"type": "minecraft:pig", "id": "uuid"}}}
        )
        self.assertEqual(new["hover_event"], {"action": "show_entity", "id": "minecraft:pig", "uuid": "uuid"})

    def test_show_text_contents_to_value(self) -> None:
        new, _ = text_component.rewrite({"hoverEvent": {"action": "show_text", "contents": "hi"}})
        self.assertEqual(new["hover_event"]["value"], "hi")

    def test_nested_extra(self) -> None:
        new, _ = text_component.rewrite(
            {"text": "", "extra": [{"text": "a", "clickEvent": {"action": "open_url", "value": "https://x"}}]}
        )
        self.assertEqual(new["extra"][0]["click_event"], {"action": "open_url", "url": "https://x"})


class PredicateTests(unittest.TestCase):
    def test_condition_to_type_and_entity_predicate(self) -> None:
        report = Report()
        new, _ = predicate.rewrite(
            {
                "condition": "minecraft:entity_properties",
                "entity": "this",
                "predicate": {"type": "minecraft:player", "team": "red",
                              "type_specific": {"type": "minecraft:player", "input": {"jump": True}}},
            },
            report,
        )
        self.assertEqual(new["type"], "minecraft:entity_properties")
        self.assertEqual(new["predicate"]["minecraft:entity_type"], "minecraft:player")
        self.assertEqual(new["predicate"]["minecraft:team"], "red")
        self.assertEqual(new["predicate"]["minecraft:type_specific/player"], {"input": {"jump": True}})

    def test_predicate_list_becomes_all_of(self) -> None:
        report = Report()
        new, _ = predicate.rewrite(
            [{"condition": "minecraft:killed_by_player"}, {"condition": "minecraft:survives_explosion"}],
            report,
        )
        self.assertEqual(new["type"], "minecraft:all_of")
        self.assertEqual([term["type"] for term in new["terms"]],
                         ["minecraft:killed_by_player", "minecraft:survives_explosion"])

    def test_reference_inlined(self) -> None:
        report = Report()
        new, _ = predicate.rewrite({"condition": "minecraft:reference", "name": "pack:sub"}, report)
        self.assertEqual(new, "pack:sub")

    def test_block_state_property_to_match_block(self) -> None:
        report = Report()
        new, _ = predicate.rewrite(
            {"condition": "minecraft:block_state_property", "block": "minecraft:oak_door",
             "properties": {"open": "true"}},
            report,
        )
        self.assertEqual(new, {"type": "minecraft:match_block", "blocks": "minecraft:oak_door",
                               "state": {"open": "true"}})

    def test_slime_becomes_cube_mob(self) -> None:
        report = Report()
        new, _ = predicate.rewrite(
            {"type": "minecraft:entity_properties", "entity": "this",
             "predicate": {"type_specific": {"type": "minecraft:slime", "size": {"min": 2}}}},
            report,
        )
        self.assertIn("minecraft:type_specific/cube_mob", new["predicate"])

    def test_rewrite_is_idempotent(self) -> None:
        node = {"type": "minecraft:entity_properties", "entity": "this",
                "predicate": {"minecraft:entity_type": "minecraft:player",
                              "minecraft:team": "red"}}
        once, _ = predicate.rewrite(node, Report())
        twice, changed = predicate.rewrite(once, Report())
        self.assertFalse(changed)
        self.assertEqual(once, twice)


class ItemModifierTests(unittest.TestCase):
    def test_root_list_becomes_sequence(self) -> None:
        report = Report()
        new, _ = item_modifier.upgrade(
            [{"function": "minecraft:set_count", "count": 2},
             {"function": "minecraft:set_custom_data", "tag": "{A:1b}"}],
            report,
        )
        self.assertEqual(new["type"], "minecraft:sequence")
        self.assertEqual(new["functions"][0], {"type": "minecraft:set_count", "count": 2})
        self.assertEqual(new["functions"][1]["type"], "minecraft:set_custom_data")

    def test_single_root_list_unwrapped(self) -> None:
        report = Report()
        new, _ = item_modifier.upgrade([{"function": "minecraft:set_count", "count": 2}], report)
        self.assertEqual(new, {"type": "minecraft:set_count", "count": 2})

    def test_set_loot_table_rename(self) -> None:
        report = Report()
        new, _ = item_modifier.upgrade(
            {"function": "minecraft:set_loot_table", "name": "minecraft:chests/simple", "type": "minecraft:chest"},
            report,
        )
        self.assertEqual(new["loot_table_id"], "minecraft:chests/simple")
        self.assertNotIn("name", new)
        # the old block-entity "type" is gone; the discriminator is what remains
        self.assertEqual(new["type"], "minecraft:set_loot_table")

    def test_conditions_to_condition(self) -> None:
        report = Report()
        new, _ = item_modifier.upgrade(
            {"function": "minecraft:set_count", "count": 1,
             "conditions": [{"condition": "minecraft:killed_by_player"}]},
            report,
        )
        self.assertEqual(new["condition"], {"type": "minecraft:killed_by_player"})
        self.assertNotIn("conditions", new)

    def test_set_components_tooltip(self) -> None:
        report = Report()
        new, _ = item_modifier.upgrade(
            {"function": "minecraft:set_components",
             "components": {"minecraft:enchantments": {"levels": {"minecraft:sharpness": 2},
                                                       "show_in_tooltip": False},
                            "minecraft:hide_tooltip": {}}},
            report,
        )
        comps = new["components"]
        self.assertEqual(comps["minecraft:enchantments"], {"minecraft:sharpness": 2})
        self.assertEqual(comps["minecraft:tooltip_display"],
                         {"hide_tooltip": True, "hidden_components": ["minecraft:enchantments"]})


class LootTableTests(unittest.TestCase):
    def test_pool_and_entry_renames(self) -> None:
        report = Report()
        table = {
            "pools": [{
                "rolls": 1,
                "conditions": [{"condition": "minecraft:survives_explosion"}],
                "functions": [{"function": "minecraft:set_count", "count": 2}],
                "entries": [{"type": "tag", "name": "minecraft:logs", "weight": 1,
                             "conditions": [{"condition": "minecraft:killed_by_player"}]}],
            }]
        }
        new, _ = loot_table.upgrade(table, report)
        pool = new["pools"][0]
        self.assertEqual(pool["condition"], {"type": "minecraft:survives_explosion"})
        self.assertEqual(pool["modifier"][0]["type"], "minecraft:set_count")
        self.assertEqual(pool["entries"][0]["items"], "minecraft:logs")
        self.assertIn("condition", pool["entries"][0])


class AdvancementTests(unittest.TestCase):
    def test_root_background_added_and_normalised(self) -> None:
        report = Report()
        new, _ = advancement.upgrade(
            {"display": {"title": {"text": "t"}, "description": {"text": "d"},
                         "icon": {"id": "minecraft:stone"}}},
            report,
        )
        self.assertEqual(new["display"]["background"], "minecraft:gui/advancements/backgrounds/stone")

    def test_non_root_background_removed(self) -> None:
        report = Report()
        new, _ = advancement.upgrade(
            {"parent": "x:y", "display": {"title": "t", "description": "d",
                                          "icon": {"id": "minecraft:stone"},
                                          "background": "minecraft:textures/gui/advancements/backgrounds/stone.png"}},
            report,
        )
        self.assertNotIn("background", new["display"])

    def test_trigger_renames(self) -> None:
        report = Report()
        new, _ = advancement.upgrade(
            {"criteria": {"1": {"trigger": "minecraft:recipe_unlocked", "recipe": "x:y"}}},
            report,
        )
        self.assertEqual(new["criteria"]["1"]["recipes"], "x:y")

    def test_tick_player_list_to_single_predicate(self) -> None:
        report = Report()
        new, _ = advancement.upgrade(
            {"criteria": {"1": {"trigger": "minecraft:tick", "conditions": {
                "player": [{"condition": "minecraft:killed_by_player"}]}}}},
            report,
        )
        self.assertEqual(new["criteria"]["1"]["conditions"]["player"],
                         {"type": "minecraft:killed_by_player"})

    def test_recipe_field_lives_in_conditions(self) -> None:
        report = Report()
        new, _ = advancement.upgrade(
            {"criteria": {"1": {"trigger": "minecraft:recipe_unlocked",
                                "conditions": {"recipe": "pack:thing"}}}},
            report,
        )
        self.assertEqual(new["criteria"]["1"]["conditions"]["recipes"], "pack:thing")

    def test_trigger_rename_is_idempotent(self) -> None:
        report = Report()
        node = {"criteria": {"1": {"trigger": "minecraft:recipe_crafted",
                                   "conditions": {"recipe_id": "pack:thing"}}}}
        once, _ = advancement.upgrade(node, report)
        twice, changed = advancement.upgrade(once, Report())
        self.assertFalse(changed)
        self.assertEqual(once, twice)

    def test_icon_dyed_color_object_flattened(self) -> None:
        report = Report()
        new, _ = advancement.upgrade(
            {"display": {"title": "t", "description": "d",
                         "icon": {"id": "minecraft:leather_chestplate",
                                  "components": {"minecraft:dyed_color": {"rgb": 16773360}}}}},
            report,
        )
        self.assertEqual(new["display"]["icon"]["components"]["minecraft:dyed_color"], 16773360)

    def test_icon_enchantments_levels_flattened(self) -> None:
        report = Report()
        new, _ = advancement.upgrade(
            {"display": {"title": "t", "description": "d",
                         "icon": {"id": "minecraft:book",
                                  "components": {"minecraft:enchantments": {
                                      "levels": {"minecraft:mending": 1}}}}}},
            report,
        )
        self.assertEqual(new["display"]["icon"]["components"]["minecraft:enchantments"],
                         {"minecraft:mending": 1})

    def test_icon_item_model_namespace_completed(self) -> None:
        report = Report()
        new, _ = advancement.upgrade(
            {"display": {"title": "t", "description": "d",
                         "icon": {"id": "minecraft:leather_chestplate",
                                  "components": {"minecraft:item_model": "champions_belt"}}}},
            report,
        )
        self.assertEqual(new["display"]["icon"]["components"]["minecraft:item_model"],
                         "minecraft:champions_belt")

    def test_unknown_fields_removed(self) -> None:
        report = Report()
        new, _ = advancement.upgrade(
            {"__comment": "made by a generator",
             "display": {"title": "t", "description": "d",
                         "icon": {"id": "minecraft:stone", "tag": "x"},
                         "generator": "x", "frame": "task"},
             "criteria": {"1": {"trigger": "minecraft:impossible"}},
             "rewards": {"function": "ns:f", "unknown": 1}},
            report,
        )
        self.assertNotIn("__comment", new)
        self.assertNotIn("generator", new["display"])
        self.assertNotIn("tag", new["display"]["icon"])
        self.assertNotIn("unknown", new["rewards"])
        self.assertEqual(new["display"]["frame"], "task")

    def test_unknown_field_removal_is_idempotent(self) -> None:
        node = {"__comment": "x", "criteria": {"1": {"trigger": "minecraft:tick"}}}
        once, _ = advancement.upgrade(node, Report())
        twice, changed = advancement.upgrade(once, Report())
        self.assertFalse(changed)
        self.assertEqual(once, twice)


class JsonFormatTests(unittest.TestCase):
    def setUp(self) -> None:
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_work")
        os.makedirs(base, exist_ok=True)
        self.path = os.path.join(base, "format.json")

    def read(self) -> bytes:
        with open(self.path, "rb") as handle:
            return handle.read()

    def test_tab_indent_lf_and_trailing_newline(self) -> None:
        with open(self.path, "wb") as handle:
            handle.write(b'{\r\n    "a": 1\r\n}')
        _save_json(self.path, {"a": {"b": [1, 2]}})
        raw = self.read()
        self.assertNotIn(b"\r\n", raw)
        self.assertTrue(raw.startswith(b'{\n\t"a": {\n\t\t"b"'), raw[:40])
        self.assertTrue(raw.endswith(b"\n"))

    def test_bom_dropped(self) -> None:
        with open(self.path, "wb") as handle:
            handle.write(b'\xef\xbb\xbf{"a": 1}')
        _save_json(self.path, {"a": 1})
        self.assertFalse(self.read().startswith(b"\xef\xbb\xbf"))


class CommandTests(unittest.TestCase):
    def process(self, line: str) -> str:
        return commands.process_line(line, "test.mcfunction", Report())

    def test_gamerule_rename_and_inversion(self) -> None:
        self.assertEqual(self.process("gamerule doMobLoot true"), "gamerule minecraft:mob_drops true")
        self.assertEqual(
            self.process("gamerule disableElytraMovementCheck true"),
            "gamerule minecraft:elytra_movement_check false",
        )

    def test_summon_equipment_and_component(self) -> None:
        out = self.process(
            'summon zombie ~ ~ ~ {Tags:["E"],CustomName:\'{"text":"Boss"}\','
            'HandItems:[{id:"minecraft:iron_sword",count:1},{}],'
            'ArmorItems:[{},{},{},{id:"minecraft:iron_helmet",count:1}]}'
        )
        self.assertNotIn("HandItems", out)
        self.assertIn('equipment:{mainhand:{id:"minecraft:iron_sword",count:1},'
                      'head:{id:"minecraft:iron_helmet",count:1}}', out)
        self.assertIn('CustomName:{text:"Boss"}', out)

    def test_item_components(self) -> None:
        out = self.process('give @s stone_sword[enchantments={levels:{"minecraft:power":1}},'
                           'hide_tooltip={}] 1')
        self.assertIn('enchantments={"minecraft:power":1}', out)
        self.assertIn('tooltip_display={hide_tooltip:true}', out)
        self.assertNotIn("levels", out)

    def test_selector_nbt(self) -> None:
        out = self.process('tag @e[nbt={HandItems:[{id:"minecraft:stick",count:1},{}]}] add Marked')
        self.assertIn("equipment:{mainhand:", out)
        self.assertNotIn("HandItems", out)

    def test_inline_predicate(self) -> None:
        out = self.process(
            'execute if predicate {condition:"minecraft:entity_properties",entity:"this",'
            'predicate:{type:"minecraft:player"}} run say hi'
        )
        self.assertIn('predicate {type:"minecraft:entity_properties"', out)
        self.assertIn('"minecraft:entity_type":"minecraft:player"', out)

    def test_tellraw_component(self) -> None:
        out = self.process('tellraw @a [{"text":"hi","clickEvent":{"action":"run_command","value":"/say x"}}]')
        self.assertIn("click_event:", out)
        self.assertIn('command:"/say x"', out)

    def test_data_value_component(self) -> None:
        out = self.process(
            "data modify entity @s CustomName set value '{\"text\":\"Bob\"}'"
        )
        self.assertEqual(out, 'data modify entity @s CustomName set value {text:"Bob"}')

    def test_block_state_codec(self) -> None:
        out = self.process('summon block_display ~ ~ ~ {block_state:{Name:"minecraft:tnt",Properties:{unstable:true}}}')
        self.assertIn('block_state:{id:"minecraft:tnt",properties:{unstable:true}}', out)

    def test_nbt_path(self) -> None:
        out = self.process("data modify entity @s ArmorItems[3].count set value 1")
        self.assertEqual(out, "data modify entity @s equipment.head.count set value 1")

    def test_chain_rename(self) -> None:
        out = self.process('summon item ~ ~ ~ {Item:{id:"minecraft:chain",count:1}}')
        self.assertIn('id:"minecraft:iron_chain"', out)

    def test_comment_untouched(self) -> None:
        line = '# summon zombie ~ ~ ~ {HandItems:[{id:"minecraft:stick"}]}'
        self.assertEqual(self.process(line), line)

    def test_particle_flash_gains_color(self) -> None:
        self.assertEqual(
            self.process("particle flash ~ ~ ~ 0 0 0 0 1 force @s"),
            "particle flash{color:[1.0,1.0,1.0,1.0]} ~ ~ ~ 0 0 0 0 1 force @s",
        )

    def test_particle_flash_bare_name(self) -> None:
        self.assertEqual(self.process("particle flash"),
                         "particle flash{color:[1.0,1.0,1.0,1.0]}")

    def test_particle_flash_inside_execute(self) -> None:
        line = ("execute if score #4Tick CTT matches 1 as @e[tag=JusticeSpikesHold] "
                "at @e[tag=JusticeParticle] if score @e[tag=JusticeParticle,limit=1,sort=nearest] "
                "PlayerID = @s PlayerID run particle flash ~ ~ ~ 0 0 0 0 1 force @s")
        self.assertIn("run particle flash{color:[1.0,1.0,1.0,1.0]} ~ ~ ~", self.process(line))

    def test_particle_flash_namespaced(self) -> None:
        out = self.process("particle minecraft:flash ~ ~ ~ 0 0 0 0 3 force @a")
        self.assertIn("particle minecraft:flash{color:[1.0,1.0,1.0,1.0]}", out)

    def test_particle_flash_keeps_explicit_color(self) -> None:
        line = "particle flash{color:[0.2,0.4,0.6,1.0]} ~ ~ ~ 0 0 0 0 1"
        self.assertEqual(self.process(line), line)

    def test_particle_flash_fills_empty_options(self) -> None:
        self.assertEqual(self.process("particle flash{} ~ ~ ~ 0 0 0 0 1"),
                         "particle flash{color:[1.0,1.0,1.0,1.0]} ~ ~ ~ 0 0 0 0 1")

    def test_particle_flash_adds_color_to_other_options(self) -> None:
        out = self.process("particle flash{scale:2.0} ~ ~ ~ 0 0 0 0 1")
        self.assertIn("flash{color:[1.0,1.0,1.0,1.0],scale:2.0}", out)

    def test_particle_other_types_untouched(self) -> None:
        line = 'particle dust{color:[0.027,0.659,0.039],scale:3} ~ ~ ~ 0.3 1 0.3 0 5'
        self.assertEqual(self.process(line), line)

    def test_particle_string_content_untouched(self) -> None:
        line = 'tellraw @a {"text":"run particle flash now"}'
        self.assertEqual(self.process(line), line)

    def test_particle_chat_argument_untouched(self) -> None:
        line = "say particle flash"
        self.assertEqual(self.process(line), line)

    def test_particle_flash_is_idempotent(self) -> None:
        once = self.process("particle flash ~ ~ ~ 0 0 0 0 1")
        self.assertEqual(self.process(once), once)


class EquipmentSlotTests(unittest.TestCase):
    """1.21.5 moved worn armour / off-hand out of Inventory into equipment.

    1.21.4 serialised them as flat Inventory slot numbers 100-103 / -106, so
    every ``nbt={Inventory:[{Slot:-106b,...}]}`` predicate on 26.3 matches
    nothing.  The upgrader has to move the item stack to ``equipment.<slot>``.
    """

    def process(self, line: str) -> str:
        return commands.process_line(line, "test.mcfunction", Report())

    def test_offhand_predicate(self) -> None:
        out = self.process(
            'tag @a[tag=UpdateMe,nbt={Inventory:[{Slot:-106b,components:'
            '{"minecraft:custom_data":{shield:1b}}}]}] add ShieldHold'
        )
        self.assertEqual(
            out,
            'tag @a[tag=UpdateMe,nbt={equipment:{offhand:{components:'
            '{"minecraft:custom_data":{shield:1b}}}}}] add ShieldHold',
        )

    def test_armor_slot_names(self) -> None:
        expected = {100: "feet", 101: "legs", 102: "chest", 103: "head"}
        for slot, name in expected.items():
            out = self.process(
                'tag @a[nbt={Inventory:[{Slot:%db,components:{"minecraft:custom_data":{hev:1b}}}]}] add X'
                % slot
            )
            self.assertIn(f'equipment:{{{name}:{{components:{{"minecraft:custom_data":{{hev:1b}}}}}}}}', out)
            self.assertNotIn("Inventory", out)

    def test_offhand_bare_slot_is_any_item(self) -> None:
        out = self.process("tag @a[nbt={Inventory:[{Slot:-106b}]}] add HasOffhand")
        self.assertEqual(out, "tag @a[nbt={equipment:{offhand:{}}}] add HasOffhand")

    def test_negated_nbt_argument(self) -> None:
        out = self.process(
            "tellraw @a[tag=ButterUse,nbt={Inventory:[{Slot:-106b}]},"
            "nbt=!{Inventory:[{count:1,Slot:-106b}]}] {\"translate\":\"x\"}"
        )
        self.assertIn("nbt={equipment:{offhand:{}}}", out)
        self.assertIn("nbt=!{equipment:{offhand:{count:1}}}", out)

    def test_several_negated_armor_checks(self) -> None:
        out = self.process(
            "execute as @a[nbt=!{Inventory:[{Slot:103b}]},nbt=!{Inventory:[{Slot:102b}]},"
            "nbt=!{Inventory:[{Slot:101b}]},nbt=!{Inventory:[{Slot:100b}]}] run tag @s add NoArmorCheck"
        )
        self.assertIn("nbt=!{equipment:{head:{}}}", out)
        self.assertIn("nbt=!{equipment:{chest:{}}}", out)
        self.assertIn("nbt=!{equipment:{legs:{}}}", out)
        self.assertIn("nbt=!{equipment:{feet:{}}}", out)

    def test_two_equipment_entries_in_one_list(self) -> None:
        out = self.process("execute if entity @s[nbt={Inventory:[{Slot:100b},{Slot:101b}]}] run say both")
        self.assertEqual(out, "execute if entity @s[nbt={equipment:{feet:{},legs:{}}}] run say both")

    def test_main_inventory_slots_untouched(self) -> None:
        for slot in (0, 8, 35):
            line = 'tag @a[nbt={Inventory:[{Slot:%db,id:"minecraft:lime_dye"}]}] add X' % slot
            self.assertEqual(self.process(line), line)

    def test_main_inventory_entry_kept_beside_equipment(self) -> None:
        out = self.process(
            'tag @a[nbt={Inventory:[{Slot:9b,id:"minecraft:diamond"},'
            '{Slot:-106b,components:{"minecraft:custom_data":{a:1b}}}]}] add X'
        )
        self.assertIn('Inventory:[{Slot:9b,id:"minecraft:diamond"}]', out)
        self.assertIn('equipment:{offhand:{components:{"minecraft:custom_data":{a:1b}}}}', out)

    def test_selected_item_kept(self) -> None:
        out = self.process(
            'tag @a[nbt={SelectedItem:{components:{"minecraft:custom_data":{a:1b}}},'
            'Inventory:[{Slot:-106b,components:{"minecraft:custom_data":{b:1b}}}]}] add X'
        )
        self.assertIn('SelectedItem:{components:{"minecraft:custom_data":{a:1b}}}', out)
        self.assertIn('equipment:{offhand:{components:{"minecraft:custom_data":{b:1b}}}}', out)

    def test_slot_key_is_dropped(self) -> None:
        out = self.process("summon armor_stand ~ ~ ~ {Inventory:[{Slot:103b,id:\"minecraft:leather_helmet\",count:1}]}")
        self.assertEqual(
            out,
            'summon armor_stand ~ ~ ~ {equipment:{head:{id:"minecraft:leather_helmet",count:1}}}',
        )

    def test_tellraw_nbt_path(self) -> None:
        out = self.process(
            'execute if score #PickThisSlot DungeonScores matches 36 run tellraw @s '
            '["",{"nbt": "Inventory[{Slot: -106b}].components.minecraft:custom_name", '
            '"entity": "@s", "interpret": true}]'
        )
        self.assertIn('"nbt": "equipment.offhand.components.minecraft:custom_name"', out)

    def test_data_command_path(self) -> None:
        out = self.process("execute store result score @s StackCount run data get entity @s Inventory[{Slot: 102b}].count")
        self.assertEqual(
            out, "execute store result score @s StackCount run data get entity @s equipment.chest.count"
        )

    def test_data_command_main_slot_untouched(self) -> None:
        line = "execute store result score @s StackCount run data get entity @s Inventory[{Slot: 9b}].count"
        self.assertEqual(self.process(line), line)

    def test_existing_equipment_predicate_untouched(self) -> None:
        line = ('tag @a[nbt={equipment:{offhand:{components:'
                '{"minecraft:custom_data":{shield:1b}}}}}] add X')
        self.assertEqual(self.process(line), line)

    def test_slot_nested_in_components_is_hoisted(self) -> None:
        out = self.process(
            'scoreboard players set @a[nbt={Inventory:[{components:'
            '{"minecraft:custom_data":{Ouroboros:1b},Slot:-106b}}]}] OuroborosEnchantID 2'
        )
        self.assertEqual(
            out,
            'scoreboard players set @a[nbt={equipment:{offhand:{components:'
            '{"minecraft:custom_data":{Ouroboros:1b}}}}}] OuroborosEnchantID 2',
        )

    def test_idempotent(self) -> None:
        once = self.process(
            'tag @a[nbt={Inventory:[{Slot:-106b,components:{"minecraft:custom_data":{a:1b}}}]}] add X'
        )
        self.assertEqual(self.process(once), once)


class TagTests(unittest.TestCase):
    def test_transitive_rename(self) -> None:
        self.assertEqual(tags.rename_tag("#minecraft:dead_bush_may_place_on"),
                         "#minecraft:supports_dry_vegetation")
        self.assertEqual(tags.rename_tag("#minecraft:convertable_to_mud"),
                         "#minecraft:convertible_to_mud")


class IntegrityTests(unittest.TestCase):
    """26.3 fails the whole world on a broken file in a strict registry."""

    def setUp(self) -> None:
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        for sub in ("function", "advancement", "recipe", "tags/function"):
            os.makedirs(os.path.join(self.root, "data", "demo", sub), exist_ok=True)

    def write_json(self, rel: str, node) -> str:
        path = os.path.join(self.root, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(node, handle)
        return path

    def write_text(self, rel: str, text: str) -> str:
        path = os.path.join(self.root, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def test_missing_reward_function_is_dangling(self) -> None:
        self.write_json("data/demo/advancement/broken.json", {
            "criteria": {"1": {"trigger": "minecraft:impossible"}},
            "rewards": {"function": "demo:nope"},
        })
        issues = integrity.scan(self.root)
        self.assertEqual([(i.path, i.label, i.ref) for i in issues],
                         [("data/demo/advancement/broken.json", "rewards.function", "demo:nope")])

    def test_missing_recipe_in_criteria_is_dangling(self) -> None:
        self.write_json("data/demo/advancement/broken.json", {
            "criteria": {"1": {"trigger": "minecraft:recipe_unlocked",
                               "conditions": {"recipes": "demo:nope"}}},
        })
        issues = integrity.scan(self.root)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].ref, "demo:nope")

    def test_existing_targets_are_fine(self) -> None:
        self.write_text("data/demo/function/reward.mcfunction", "say hi\n")
        self.write_json("data/demo/recipe/r.json", {"type": "minecraft:crafting_shapeless"})
        self.write_json("data/demo/advancement/ok.json", {
            "criteria": {"1": {"trigger": "minecraft:recipe_unlocked",
                               "conditions": {"recipes": ["demo:r"]}}},
            "rewards": {"function": "demo:reward"},
        })
        self.assertEqual(integrity.scan(self.root), [])

    def test_vanilla_and_foreign_namespaces_are_ignored(self) -> None:
        self.write_json("data/demo/advancement/ok.json", {
            "criteria": {"1": {"trigger": "minecraft:impossible"}},
            "rewards": {"function": "minecraft:say_hi", "loot": ["other:table"]},
        })
        self.assertEqual(integrity.scan(self.root), [])

    def test_prune_deletes_and_cascades(self) -> None:
        self.write_json("data/demo/advancement/parent.json", {
            "parent": "demo:missing",
            "criteria": {"1": {"trigger": "minecraft:impossible"}},
        })
        self.write_json("data/demo/advancement/child.json", {
            "parent": "demo:parent",
            "criteria": {"1": {"trigger": "minecraft:impossible"}},
        })
        report = Report()
        removed, repaired = integrity.prune(self.root, report)
        self.assertEqual([path for path, _ in removed],
                         ["data/demo/advancement/parent.json",
                          "data/demo/advancement/child.json"])
        self.assertEqual(repaired, [])
        self.assertFalse(os.path.exists(os.path.join(self.root, "data", "demo", "advancement", "parent.json")))
        self.assertFalse(os.path.exists(os.path.join(self.root, "data", "demo", "advancement", "child.json")))
        self.assertEqual(report.by_rule()["json.dangling_reference"], 2)

    def test_prune_repairs_dangling_reward_only(self) -> None:
        path = self.write_json("data/demo/advancement/quest.json", {
            "criteria": {"1": {"trigger": "minecraft:impossible"}},
            "rewards": {"function": "demo:gone", "loot": ["demo:missing"]},
        })
        report = Report()
        removed, repaired = integrity.prune(self.root, report)
        self.assertEqual(removed, [])
        self.assertEqual([item[0] for item in repaired], ["data/demo/advancement/quest.json"])
        self.assertTrue(os.path.exists(path))
        with open(path, encoding="utf-8") as handle:
            node = json.load(handle)
        self.assertNotIn("rewards", node)
        self.assertEqual(report.by_rule()["json.reward_dropped"], 1)

    def test_function_tag_audit(self) -> None:
        self.write_json("data/demo/tags/function/t.json", {"values": ["demo:nope", "minecraft:load"]})
        issues = integrity.scan_function_tags(self.root)
        self.assertEqual([i.ref for i in issues], ["demo:nope"])

    def test_unknown_item_in_recipe_is_dangling(self) -> None:
        self.write_json("data/demo/recipe/bad.json", {
            "type": "minecraft:crafting_shapeless",
            "ingredients": [{"item": "minecraft:not_a_real_item"}],
            "result": {"id": "minecraft:stone", "count": 1},
        })
        issues = integrity.scan(self.root)
        self.assertEqual([(i.label, i.ref) for i in issues],
                         [("ingredients[0].item", "minecraft:not_a_real_item")])

    def test_unknown_item_in_advancement_icon_is_dangling(self) -> None:
        self.write_json("data/demo/advancement/icon.json", {
            "criteria": {"1": {"trigger": "minecraft:impossible"}},
            "display": {"icon": {"id": "minecraft:not_a_real_item"},
                        "title": "t", "description": "d"},
        })
        issues = integrity.scan(self.root)
        self.assertEqual([(i.label, i.ref) for i in issues],
                         [("display.icon.id", "minecraft:not_a_real_item")])


def make_pack(root: str) -> None:
    os.makedirs(os.path.join(root, "data", "demo", "function"))
    os.makedirs(os.path.join(root, "data", "demo", "item_modifier"))
    os.makedirs(os.path.join(root, "data", "demo", "advancement"))
    with open(os.path.join(root, "pack.mcmeta"), "w", encoding="utf-8") as handle:
        json.dump({"pack": {"pack_format": 61, "description": "demo"}}, handle)
    with open(os.path.join(root, "data", "demo", "function", "test.mcfunction"), "w", encoding="utf-8") as handle:
        handle.write(
            "gamerule doTileDrops false\n"
            "summon zombie ~ ~ ~ {HandItems:[{id:\"minecraft:stick\",count:1},{}]}\n"
        )
    with open(os.path.join(root, "data", "demo", "item_modifier", "mod.json"), "w", encoding="utf-8") as handle:
        json.dump([{"function": "minecraft:set_count", "count": 1}], handle, indent=2)
    with open(os.path.join(root, "data", "demo", "advancement", "root.json"), "w", encoding="utf-8") as handle:
        json.dump({"display": {"title": "t", "description": "d", "icon": {"id": "minecraft:stone"}}}, handle, indent=2)


class PipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_work")
        os.makedirs(base, exist_ok=True)
        self.tmp = os.path.join(base, self._testMethodName)
        shutil.rmtree(self.tmp, ignore_errors=True)
        os.makedirs(self.tmp)
        self.src = os.path.join(self.tmp, "pack")
        self.dst = os.path.join(self.tmp, "out")
        make_pack(self.src)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_end_to_end(self) -> None:
        report, issues, _stats = upgrade_pack(self.src, self.dst, force=True)
        self.assertEqual(report.errors, [])
        with open(os.path.join(self.dst, "pack.mcmeta"), encoding="utf-8") as handle:
            meta = json.load(handle)
        self.assertEqual(meta["pack"]["min_format"], [121, 0])
        self.assertNotIn("pack_format", meta["pack"])
        with open(os.path.join(self.dst, "data", "demo", "item_modifier", "mod.json"), encoding="utf-8") as handle:
            modifier = json.load(handle)
        self.assertEqual(modifier["type"], "minecraft:set_count")
        with open(os.path.join(self.dst, "data", "demo", "advancement", "root.json"), encoding="utf-8") as handle:
            root = json.load(handle)
        self.assertIn("background", root["display"])
        with open(os.path.join(self.dst, "data", "demo", "function", "test.mcfunction"), encoding="utf-8") as handle:
            function = handle.read()
        self.assertIn("gamerule minecraft:block_drops false", function)
        self.assertIn("equipment:{mainhand:", function)

    def test_broken_json_is_deleted(self) -> None:
        path = os.path.join(self.src, "data", "demo", "advancement", "broken.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"criteria": {"1": {"trigger": "minecraft:impossible"}},
                       "rewards": {"function": "demo:missing"}}, handle)
        report, _issues, _stats = upgrade_pack(self.src, self.dst, force=True)
        kept = os.path.join(self.dst, "data", "demo", "advancement", "broken.json")
        self.assertTrue(os.path.exists(kept))
        with open(kept, encoding="utf-8") as handle:
            self.assertNotIn("rewards", json.load(handle))
        self.assertEqual(report.by_rule().get("json.reward_dropped"), 1)

    def test_parentless_chain_is_deleted(self) -> None:
        with open(os.path.join(self.src, "data", "demo", "advancement", "orphan.json"),
                  "w", encoding="utf-8") as handle:
            json.dump({"parent": "demo:missing",
                       "criteria": {"1": {"trigger": "minecraft:impossible"}}}, handle)
        report, _issues, _stats = upgrade_pack(self.src, self.dst, force=True)
        self.assertFalse(os.path.exists(
            os.path.join(self.dst, "data", "demo", "advancement", "orphan.json")))
        self.assertEqual(report.by_rule().get("json.dangling_reference"), 1)

    def test_unparseable_json_is_deleted(self) -> None:
        path = os.path.join(self.src, "data", "demo", "advancement", "bad.json")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("{not json")
        report, _issues, _stats = upgrade_pack(self.src, self.dst, force=True)
        self.assertFalse(os.path.exists(
            os.path.join(self.dst, "data", "demo", "advancement", "bad.json")))
        self.assertEqual(report.by_rule().get("json.invalid_deleted"), 1)

    def test_idempotent(self) -> None:
        upgrade_pack(self.src, self.dst, force=True)
        second = os.path.join(self.tmp, "out2")
        report, _issues, _stats = upgrade_pack(self.dst, second, force=True)
        rules = {rule for rule in report.by_rule() if rule != "pack_mcmeta.min_max_format"}
        self.assertEqual(rules, set())


if __name__ == "__main__":
    unittest.main()
