# Rule reference: 1.21.4 → 26.3

Every rule below lists the old form, the new form and the source it was derived from.
Sources are the **English Minecraft Wiki** release pages ("Changes → General / Data
pack") or dedicated technical pages read as wikitext (`?action=raw`); snapshot numbers
come from the Wiki history sections. The Chinese Wiki was only used to cross-check
structure.

中文版：[RULES-CN.md](RULES-CN.md)

---

## 1. `pack.mcmeta`

| Old | New |
| --- | --- |
| `{"pack":{"pack_format":61,"description":"..."}}` | `{"pack":{"description":"...","min_format":[121,0],"max_format":[121,0]}}` |

- Since 1.21.9 (25w31a), `min_format` / `max_format` are required; `pack_format` became
  optional and `supported_formats` was removed. Keep the old field only if the pack still
  has to support ≤1.21.8 (data pack format < 82).
- A bare integer `121` equals `[121, 0]`. For `max_format` a bare integer means "any minor
  version", so it is written explicitly as `[121, 0]` to pin 121.0.
- Source: Wiki `pack.mcmeta` §Format and §History (1.21.9 / 25w31a);
  `Java Edition 26.3` §Changes>General>Data pack ("The pack format version is now 121.0").

## 2. Text components (1.21.5)

Components are no longer stored as JSON strings but inlined as NBT; command arguments use
SNBT as well.

| Old | New |
| --- | --- |
| `CustomName:'{"text":"Boss"}'` | `CustomName:{text:"Boss"}` |
| `lore:['{"text":"x"}']` | `lore:[{text:"x"}]` |
| `components:{"minecraft:custom_name":'{"text":"x"}'}` | `components:{"minecraft:custom_name":{text:"x"}}` |
| `text:'{"translate":"..."}'` (text_display) | `text:{translate:"..."}` |
| `pages:[{raw:'{"translate":"..."}'}]` | `pages:[{raw:{translate:"..."}}]` |
| `data modify ... set value '{"text":"x"}'` | `data modify ... set value {text:"x"}` |

Event fields (1.21.5 / 25w02a, 25w03a):

| Old | New |
| --- | --- |
| `clickEvent` / `hoverEvent` | `click_event` / `hover_event` |
| click `run_command` / `suggest_command` `value` | `command` |
| click `open_url` `value` | `url` |
| click `open_file` `value` | `path` |
| click `change_page` `value` (string) | `page` (positive int) |
| hover `show_text` `contents` | `value` (renamed to `text` in 25w02a, back to `value` in 25w03a) |
| hover `show_item` `contents:{id,count,components}` | inlined as `id` / `count` / `components` |
| hover `show_entity` `contents:{type,id}` | `id` (entity type) / `uuid` (old `id`) |

- Source: Wiki `Text component format` §History 1.21.5 (25w02a, 25w03a);
  `Java Edition 1.21.5` §Technical>Changes>General>Text component format.

## 3. Item components (1.21.5 / 26.3)

| Old | New |
| --- | --- |
| `hide_tooltip={}` / `hide_additional_tooltip={}` | `tooltip_display={hide_tooltip:true}` / `hidden_components:[...]` |
| `show_in_tooltip:false` inside a component | drop the field, add the component id to `tooltip_display.hidden_components` |
| `enchantments={levels:{id:1}}` | `enchantments={id:1}` |
| `attribute_modifiers={modifiers:[...]}` | `attribute_modifiers=[...]` |
| `dyed_color={rgb:12345}` | `dyed_color=12345` |
| `can_place_on={predicates:[...]}` | `can_place_on=[...]` |
| `minecraft:swing_animation` (26.3) | `minecraft:attack_animation` + `minecraft:interact_animation` |
| `minecraft:map_color` (26.3) | removed |

- Source: Wiki `Java Edition 1.21.5` §Technical>Changes>General>Data components;
  `Java Edition 26.3` §Changes>General>Data component format.

## 4. Block state codec (26.3)

| Old | New |
| --- | --- |
| `block_state:{Name:"minecraft:tnt",Properties:{unstable:true}}` | `block_state:{id:"minecraft:tnt",properties:{unstable:true}}` |
| `BlockState:{Name:...}` / `carriedBlockState:{Name:...}` | same as above |

- Also covers `inBlockState`, `DisplayState` (minecarts) and other block-state compounds.
- The **command argument** syntax (`stone[facing=east]`) is unaffected.
- Source: `Java Edition 26.3` §Changes>General>Block states
  ("Name is now id / Properties is now properties").

## 5. Entity predicates (26.2)

The old shape (optional fields plus a `type_specific` discriminator) becomes a map of
namespaced id → sub-predicate:

```json
// old
{"condition":"minecraft:entity_properties","entity":"this",
 "predicate":{"type":"minecraft:player","team":"red",
              "type_specific":{"type":"minecraft:player","input":{"jump":true}}}}
// new
{"type":"minecraft:entity_properties","entity":"this",
 "predicate":{"minecraft:entity_type":"minecraft:player",
              "minecraft:team":"red",
              "minecraft:type_specific/player":{"input":{"jump":true}}}}
```

- Every key becomes a namespaced id; `type` → `minecraft:entity_type`;
  `type_specific.{type_specific/<kind>}` is lifted to a top-level
  `minecraft:type_specific/<kind>`.
- `slime` → `cube_mob` (26.2 snap4).
- The variant sub-predicates removed in 1.21.5 (`axolotl`, `fox`, `villager`, …) cannot be
  converted automatically: the entry is dropped with a warning.
- Source: Wiki `Entity predicate` §Data format; `Java Edition 26.2`
  §Changes>General (snapshot 3/4).

## 6. Predicates (26.3)

| Old | New |
| --- | --- |
| `{"condition":"minecraft:random_chance","chance":0.5}` | `{"type":"minecraft:random_chance","chance":0.5}` (`condition` is mandatory) |
| root is a list of predicates / several conditions | explicit `{"type":"minecraft:all_of","terms":[...]}` |
| `{"condition":"minecraft:reference","name":"x:y"}` | `"x:y"` |
| `block_state_property` (`block`/`properties`) | `match_block` (`blocks`/`state`) |
| `value_check` (`range`) | `int_value_check` / `float_value_check` (`test`) |
| `damage_source_properties.tags[].id` (tag without `#`) | add `#` to all of them |

- Source: `Java Edition 26.3` §Changes>General>Predicate; Wiki `Predicate` §History.

## 7. Item modifiers (26.3)

| Old | New |
| --- | --- |
| `"function":"minecraft:set_count"` | `"type":"minecraft:set_count"` |
| file root is an array `[{...},{...}]` | `{"type":"minecraft:sequence","functions":[...]}` (a single element is unwrapped) |
| `"conditions":[...]` | `"condition":<predicate>` (several conditions wrapped in `all_of`) |
| `filtered` `modifier` | `on_pass` (`on_fail` omitted means "do nothing") |
| `set_loot_table` `name` / `type` | `loot_table_id` / removed |
| `exploration_map` `destination` (optional) | required; `map_color` removed |

- The `sequence` list field is still called `functions` — from the English 26.3 changelog:
  "Changed minecraft:sequence — The `functions` field now accepts … of a
  `minecraft:item_modifier` type".
- Source: `Java Edition 26.3` §Changes>General>Loot functions;
  Wiki `Item modifier` §History 26.3 (snap4/snap9/snap10).

## 8. Loot tables (26.3)

| Old | New |
| --- | --- |
| pool / entry `functions` | `modifier` |
| pool / entry `conditions` (list) | `condition` (a single predicate; several conditions → `all_of`) |
| `tag` entry `name` | `items` |
| inline number provider without `type` (default uniform) | add `type:"minecraft:uniform"` |

- Source: `Java Edition 26.3` §Changes>General>Loot table; Wiki `Loot table` §History.

## 9. Advancements (26.3 + 1.21.5)

| Old | New |
| --- | --- |
| displayed root advancement without `background` | add `minecraft:gui/advancements/backgrounds/stone` |
| non-root advancement with `background` | removed |
| `background: "minecraft:textures/gui/advancements/backgrounds/x.png"` | `"minecraft:gui/advancements/backgrounds/x"` |
| `recipe_unlocked.recipe` / `recipe_crafted.recipe_id` | `recipes` |
| `slide_down_block.block` / `bee_nest_destroyed.block` / `enter_block.block` | `blocks` |
| `player_generates_container_loot.loot_table` | `loot_tables` |
| trigger `player` (list of predicates / bare entity predicate) | a single predicate (a bare entity predicate is wrapped in `entity_properties`) |
| `location` (location predicate) | wrapped in `{"type":"minecraft:location_check","predicate":{...}}` |

- Source: `Java Edition 26.3` §Changes>General>Advancement;
  Wiki `Advancement definition` §History (1.21.5 / 25w04a background path).

## 10. Game rules (1.21.11)

Registry ids: camelCase → `minecraft:snake_case`, with three inverted meanings:

| Old | New | Inverted |
| --- | --- | --- |
| `disableElytraMovementCheck` | `minecraft:elytra_movement_check` | yes |
| `disablePlayerMovementCheck` | `minecraft:player_movement_check` | yes |
| `disableRaids` | `minecraft:raids` | yes |
| `doTileDrops` | `minecraft:block_drops` | no |
| `doMobLoot` | `minecraft:mob_drops` | no |
| `doDaylightCycle` | `minecraft:advance_time` | no |
| `doWeatherCycle` | `minecraft:advance_weather` | no |
| `maxCommandChainLength` | `minecraft:max_command_sequence_length` | no |
| `commandModificationBlockLimit` | `minecraft:max_block_modifications` | no |
| `naturalRegeneration` | `minecraft:natural_health_regeneration` | no |
| `doImmediateRespawn` | `minecraft:immediate_respawn` | no |
| `mobGriefing` | `minecraft:mob_griefing` | no |
| `fallDamage` / `fireDamage` / `drowningDamage` / `freezeDamage` | `minecraft:fall_damage` / `fire_damage` / … | no |
| `sendCommandFeedback` / `commandBlockOutput` | `minecraft:send_command_feedback` / `command_block_output` | no |
| `projectilesCanBreakBlocks` / `universalAnger` | `minecraft:projectiles_can_break_blocks` / `universal_anger` | no |

Any other camelCase rule is converted by the generic `camelCase → snake_case` rule; an
unknown rule produces a warning.

- Source: Wiki `Game rule` §History (the rename table from 1.21.11 / 25w44a).

## 11. Entity NBT (1.21.5 / 1.21.11 / 26.2)

| Old | New |
| --- | --- |
| `HandItems:[mainhand,offhand]` | `equipment:{mainhand:…,offhand:…}` |
| `ArmorItems:[feet,legs,chest,head]` | `equipment:{feet:…,legs:…,chest:…,head:…}` |
| `body_armor_item` / `SaddleItem` / `Saddle:1b` | `equipment.body` / `equipment.saddle` |
| `ArmorDropChances` / `HandDropChances` / `body_armor_drop_chance` | `drop_chances:{…}` |
| `FallDistance` | `fall_distance` (double) |
| `TileX/TileY/TileZ` | `block_pos:[I;x,y,z]` |
| `SleepingX/Y/Z` | `sleeping_pos:[I;x,y,z]` |
| `BoundX/Y/Z` / `HomePosX/Y/Z` | `bound_pos` / `home_pos` |
| `SpawnX/Y/Z/SpawnAngle/SpawnDimension/SpawnForced` | `respawn:{pos,dimension,angle,forced}` |
| `AngryAT` | `angry_at` |
| `AngerTime` (countdown) | `anger_end_time` (absolute game time) ⚠️ semantic change, see README |
| `HurtByTimestamp` (26.2) | `ticks_since_last_hurt_by_mob` ⚠️ semantic change |
| `LifeTicks` / `HasEgg` / `enteredNetherPosition` | `life_ticks` / `has_egg` / `entered_nether_pos` |
| `HandItems[0]` / `ArmorItems[3]` in an NBT path | `equipment.mainhand` / `equipment.head` |
| predicate `Inventory:[{Slot:-106b,…}]` / `Slot:100b–103b` | `equipment:{offhand:…}` / `feet`·`legs`·`chest`·`head` (see §17) |

- Source: `Java Edition 1.21.5` §Technical>Changes>General>Entity format;
  `Java Edition 1.21.11`, `Java Edition 26.2` §Changes>General.

## 12. Renamed tags

| Old | New |
| --- | --- |
| `#minecraft:dead_bush_may_place_on` | `#minecraft:supports_dry_vegetation` (renamed twice: 1.21.5 → 26.1) |
| `#minecraft:convertable_to_mud` | `#minecraft:convertible_to_mud` |
| `#minecraft:dowses_campfires` | `#minecraft:douses_campfires` |
| `#minecraft:concrete_powder` | `#minecraft:concrete_powders` |
| `#on_*_explorer_maps` | `#on_*_mansion/monument/pyramid/hut/buried_trial_chambers_maps` |
| `#minecraft:enchantable/sword` | `#minecraft:enchantable/sweeping` |

- Source: `Java Edition 26.3` §Changes>General>Tags; `Java Edition 1.21.5` / `1.21.11`.

## 13. Miscellaneous

| Change | Detail |
| --- | --- |
| recipe `cookingtime` | unified to 200 ticks in 26.3; smoker / blast furnace recipes double |
| block or item id `minecraft:chain` | → `minecraft:iron_chain` (1.21.9) |
| team colours | 26.2 only accepts lowercase snake_case (`dark_purple`) |
| strict JSON | since 26.3 a single unparseable JSON file fails the whole pack |

## 14. What the program does not convert

- the relative → absolute semantics of `AngerTime` (a sentinel value is written and every
  occurrence reported);
- the time semantics of `HurtByTimestamp` (writes `0` and reports);
- variant entity sub-predicates removed in 1.21.5 (`axolotl`, `villager`, …) — these need
  a manual rewrite to `minecraft:components` plus the variant component;
- the confirmation dialog of `run_command` on chat commands since 1.21.9 (a behaviour
  change, not syntax);
- the 26.3 "no-op commands now fail" and "return values report affected count" changes;
- `allow_op_features` on 26.3 signs (the field defaults to `false`; old signs migrate
  automatically, but signs created through `setblock`/`data` and meant to support click
  events need an explicit `allow_op_features:1b`);
- anything outside the data pack (world saves, resource packs, NBT already stored in
  command blocks).

## 15. Rules added in v2.1

| Rule id | Change | Detail |
| --- | --- | --- |
| `advancement.unknown_field` | drop fields 26.3 does not define | only the four levels whose schema is fully known: the root object (`criteria`/`display`/`parent`/`requirements`/`rewards`/`sends_telemetry_event`), `display`, `display.icon` and `rewards` |
| `item_component.namespace` | add the namespace to resource-location components | if the value of `minecraft:item_model` / `minecraft:tooltip_style` has no `:`, it becomes `minecraft:<value>` |
| `item_component.simplified_form` | advancement icon components are flattened too | previously only command SNBT and predicates; now `display.icon.components` is simplified as well (`dyed_color.rgb`, `enchantments.levels`, `show_in_tooltip`, …) |
| `json.tab_indent` | output format | rewritten JSON uses tab indentation, LF newlines, a trailing newline and no BOM |

- Source: `Advancement definition` §JSON format (field set), `Data component format`
  (`item_model` / `tooltip_style` are resource locations),
  `Java Edition 1.21.5` §Data components (simplified forms).
- Why unknown fields are not dropped at criterion level: `_criterion` may have just
  migrated a mis-placed `recipe`/`loot_table`/`block` there, so dropping first would lose
  data. Deletion only happens where the schema is certain.

## 16. Rules added in v2.2

| Rule id | Change | Detail |
| --- | --- | --- |
| `particle.flash_color` | add `color` to `particle flash` | since 1.21.9 (25w36a) `flash` requires `color` (ARGB: four 0.0–1.0 floats or a packed int). In 1.21.4 `flash` had no options and always rendered white, so `{color:[1.0,1.0,1.0,1.0]}` preserves the look |
| `json.dangling_reference` | delete JSON files whose references are broken | since 26.3 a bad file in `advancement`/`loot_table`/`recipe`/`predicate`/`item_modifier`/`number_provider`/`slot_source` makes the **whole world fail to load** (MC-310325) instead of skipping that file. The program resolves `parent`, `rewards.function/loot/recipes`, `criteria.*.conditions.recipes/loot_table`, `minecraft:reference`, nested `loot_table`, recipe and icon item ids and function tag values; when the target does not exist inside the pack the file is deleted and reported |
| `json.reward_dropped` | keep the advancement, drop the broken reward | an advancement whose only problem is `rewards.function/loot/recipes` is still useful (functions grant it with `advancement grant`); dropping that one entry makes the file loadable, so the file is kept |
| `json.invalid_deleted` | delete unparseable JSON | a file that fails to parse in a strict registry also fails the whole world; deleting it keeps the rest usable (`--keep-dangling` turns this into an error and keeps the file) |

- Source: `Particle format` §History (1.21.9 / 25w36a: "`flash` now requires a `color`
  parameter (argb)"), `Java Edition 1.21.9` §Particles.
- Only `flash` is touched: `dust`, `block`, `item` already required options in 1.21.4, and
  `tinted_leaves` (optional `color` since 1.21.5) is not handled.
- When options are already present only the missing key is added
  (`flash{scale:2.0}` → `flash{color:[1.0,1.0,1.0,1.0],scale:2.0}`), and comments or
  quoted strings containing the same text are skipped.
- Full research: `docs/RESEARCH-NOTES.md`.
- Why deletion: Mojira [MC-310325](https://mojira.dev/MC-310325) (26.3-snapshot-3, marked
  Works As Intended) and [MC-311918](https://mojira.dev/MC-311918) (a recipe referencing a
  missing item is equally fatal). References into `minecraft:` or a namespace outside the
  pack are always allowed (vanilla, or another data pack loaded alongside).
- Deletion is **cascading**: after an advancement is deleted, advancements that used it as
  `parent` are deleted in the next pass, up to 10 passes.
- Only-broken-`rewards` advancements are kept: for example an advancement that is missing
  its reward function but is granted from a function with `advancement grant` — deleting
  it would break a quest line, so the file stays and only the broken
  `rewards.function` is removed.
- Audit without deleting: `python tools/check_references.py <pack-dir>` (add `--delete` to
  actually delete/prune); pass `--keep-dangling` to the upgrader to disable automatic
  handling.

## 17. Rule added in v2.3: player equipment slot detection

| Old (1.21.4) | New (1.21.5 / 26.3) |
| --- | --- |
| `nbt={Inventory:[{Slot:-106b,…}]}` | `nbt={equipment:{offhand:{…}}}` |
| `nbt={Inventory:[{Slot:100b,…}]}` | `nbt={equipment:{feet:{…}}}` |
| `nbt={Inventory:[{Slot:101b,…}]}` | `nbt={equipment:{legs:{…}}}` |
| `nbt={Inventory:[{Slot:102b,…}]}` | `nbt={equipment:{chest:{…}}}` |
| `nbt={Inventory:[{Slot:103b,…}]}` | `nbt={equipment:{head:{…}}}` |
| `Inventory[{Slot:102b}].components…` (NBT path) | `equipment.chest.components…` |

- Slot mapping: `100→feet`, `101→legs`, `102→chest`, `103→head`, `-106→offhand`.
- Since 1.21.5 (25w03a) the player's helmet, chestplate, leggings, boots and offhand item
  live in `equipment`; `Inventory` keeps only main-inventory slots 0–35. The old form
  **never matches** in 26.3 (it does not error, it silently fails), so such features
  simply stop responding.
- Only those five slots are rewritten. `Slot:0b..35b` (hotbar / main inventory) is left
  untouched: in a 26.3 save the main inventory still uses a byte `Slot`, so predicates
  keep working.
- The main hand is still `SelectedItem` and is unaffected; command paths such as
  `weapon.offhand` / `armor.head` are unaffected too (writing always worked).
- Handles `nbt={…}`, negated `nbt=!{…}` and `Inventory[{Slot:…}]` paths inside
  `tellraw`/`data`.
- Source: `player.dat format` §Inventory slot numbers ("In versions prior to 25w03a
  (including 1.21.4), the head, chest, legs, feet, and offhand slots were stored in the
  Inventory tag"), the 1.21.5 changelog and [MC-296199](https://mojira.dev/MC-296199);
  verified against a 26.3 save's `players/data/<uuid>.dat`, where `Inventory` holds only
  main-inventory items and boots are in `equipment.feet`.
- In the production pack this tool was developed against: 1745 equipment-slot `Inventory`
  checks in the source, 4 left after the upgrade (3 in comment lines, 1 under a pre-1.21
  legacy folder that the game no longer loads).
