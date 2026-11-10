# Datapack upgrade notes: 1.21.4 → 26.3 (data pack format 121.0)

Scope: only what appears inside `.mcfunction` files and `pack.mcmeta`.
Sources: English Minecraft Wiki (`minecraft.wiki`, `?action=raw&section=N`) + curated list
`https://vanillalibrary.mcfpp.top/datapack-index/en/index/changelog_breaking.html`.
Everything not explicitly stated by those two is marked **UNVERIFIED**.

Format version anchors (Template:Data pack format): `71` = 1.21.5, `88.0` = 1.21.9, `94.1` = 1.21.11,
`101.1` = 26.1, `107.1` = 26.2, **`121.0` = 26.3** (row `121.0 | dev 26.3 Pre-Release 3 … 26.3`).

---

## 1. pack.mcmeta for data pack format 121.0

**New shape** (since 1.21.9 / 25w31a, major+minor versions introduced at 82.0):

```json
{
  "pack": {
    "description": "My Pack",
    "min_format": [121, 0],
    "max_format": [121, 0]
  }
}
```

* `min_format` / `max_format` — **required**. Value is an int or `[major, minor]`.
  `121` ≡ `[121, 0]` for `min_format`; for `max_format` a bare int means “any minor version”
  (`0x7fffffff`), so pin with `[121, 0]`.
* `pack_format` — **now optional / deprecated**. Required only if the pack also supports data pack
  format < 82. For a 26.3-only pack it should be omitted.
* `supported_formats` — **removed**. “must be absent if the pack does not support old versions, but
  must be present if the pack does support old versions”.
* `overlays[].formats` — removed; overlays now take `min_format` / `max_format`.
* 26.3: “只要有任意无法解析的JSON文件就会导致整个数据包加载失败” (“a single unparseable JSON
  file now makes the whole data pack fail to load”) — any unparseable JSON file now
  fails the whole pack load instead of silently failing (curated list, 26.3).

Old (1.21.4, valid up to 1.21.8):
```json
{ "pack": { "pack_format": 61, "description": "My Pack" } }
```

Source: *Pack.mcmeta* §Format (“`{{Nbt|integer|min_format}}`: Specifies the minimum version supported…”);
§History 1.21.9/25w31a: “The `supported_formats` field has been removed. … Added required field
`min_format` … The `pack_format` field is now optional.”

---

## 2. Text components: NBT/SNBT, not JSON strings (1.21.5+, 25w02a)

Rule: components are stored as NBT objects and typed into commands as **SNBT**; JSON text is only
for `.json` files. A bare NBT string is *plain text*, it is no longer parsed as JSON.

| Context | 1.21.4 | 26.3 |
|---|---|---|
| entity/block-entity `CustomName` | `CustomName:'{"text":"x"}'` | `CustomName:{text:"x"}` |
| item `lore` | `lore:['{"text":"x"}']` | `lore:[{text:"x"}]` |
| component inside stack NBT | `components:{"minecraft:custom_name":'{"text":"x"}'}` | `components:{"minecraft:custom_name":{text:"x"}}` |
| bracket component syntax | `give @s stick[custom_name='{"text":"x"}']` | `give @s stick[custom_name={text:"x"}]` |
| `tellraw` | `tellraw @a '{"text":"hi","color":"red"}'` | `tellraw @a {text:"hi",color:"red"}` (or `"hi"`) |

Notes for the converter:
* Keep `"minecraft:custom_name"` quoted when it is an NBT **key** — SNBT unquoted keys cannot contain
  `:`; unquoted `custom_name` is fine inside the `item[...]` component bracket syntax.
* `CustomName:"x"` is now literal text `x`, not JSON. Old JSON must be re-parsed and re-emitted as SNBT.
* A quoted JSON string that is *not* re-parsed becomes visible garbage (`{"text":"x"}` shown literally).

Source: *Text component format* lead: “Text components are written in [[NBT format#SNBT format|SNBT]].
For example, `{text: "Hello world"}`.”; *Template:Data pack format* 71: “Text components are now saved
as objects in NBT rather than strings containing JSON and many commands such as `tellraw` now take SNBT
rather than JSON.”; *Data component format* §custom_name example:
`give @s stick[custom_name={text:"Magic Wand",color:"light_purple",italic:false}]`;
§lore example: `give @p stick[lore=[{text:"This Stick is very sticky."}]]`.

Related, same era (not string-vs-object but affects command text):
* 26.1: `minecraft:nbt` with `interpret:false` is now pretty-printed (colour-highlighted structure) and
  a new `plain` field removes the styling; `plain` and `interpret` are mutually exclusive. Old output
  was one flat `text` component.
* 26.3: `tellraw` resolves `nbt` components at most 64k times.

---

## 3. clickEvent / hoverEvent → click_event / hover_event (1.21.5, 25w02a–25w03a)

Field renames inside a text component:

| 1.21.4 | 26.3 |
|---|---|
| `clickEvent:{action:…,value:…}` | `click_event:{action:…,<payload>}` |
| `hoverEvent:{action:…,contents:…}` / `value:…` | `hover_event:{action:…,<payload inlined>}` |

Click payload field renames:

| action | 1.21.4 | 26.3 |
|---|---|---|
| `open_url` | `value` | `url` |
| `open_file` | `value` | `path` |
| `run_command` | `value` | `command` (leading `/` no longer required) |
| `suggest_command` | `value` | `command` |
| `change_page` | `value` (string) | `page` (**positive int**) |
| `copy_to_clipboard` | `value` | `value` (unchanged) |
| `custom` (new in 1.21.6) | — | `id` + optional `payload` |
| `show_dialog` (new in 1.21.6) | — | `dialog` |

Hover payloads (the legacy `value` field is **removed**, `contents` was inlined):

| action | 1.21.4 | 26.3 |
|---|---|---|
| `show_text` | `contents` (later renamed `text`) | `value` |
| `show_item` | `contents:{id,count,components}`, or `value:"{id:…,count:…}"` SNBT string | inlined: `id`, `count`, `components` |
| `show_entity` | `contents:{name,type,id}` (or `value` SNBT) | `name`, `id` (= entity **type**), `uuid` (= old UUID `id`) |

Examples:
```mcfunction
# 1.21.4
tellraw @a '[{"text":"Go","clickEvent":{"action":"run_command","value":"/tp @s 0 64 0"},"hoverEvent":{"action":"show_text","contents":{"text":"teleport"}}}]'
# 26.3
tellraw @a [{text:"Go",click_event:{action:"run_command",command:"tp @s 0 64 0"},hover_event:{action:"show_text",value:{text:"teleport"}}}]
```
```mcfunction
# 1.21.4
tellraw @a '{"text":"[i]","hoverEvent":{"action":"show_item","value":"{id:\"minecraft:stone\",count:1}"}}'
# 26.3
tellraw @a {text:"[i]",hover_event:{action:"show_item",id:"minecraft:stone",count:1}}
```
```mcfunction
# 1.21.4
tellraw @a '{"text":"Bob","hoverEvent":{"action":"show_entity","contents":{"type":"minecraft:player","id":"<uuid>","name":{"text":"Bob"}}}}'
# 26.3
tellraw @a {text:"Bob",hover_event:{action:"show_entity",id:"minecraft:player",uuid:"<uuid>",name:{text:"Bob"}}}
```

Source: *Text component format* §History, 1.21.5/25w02a: “The `hoverEvent` field has been renamed to
`hover_event`. * The legacy `value` field … is no longer supported. * For the `show_text` action:
`contents` field has been renamed to `text`. * For the `show_item` action: The `contents` field has been
inlined. … * For the `show_entity` action: … The `id` field has been renamed to `uuid`. The `type` field
has been renamed to `id`. The `clickEvent` field has been renamed to `click_event`. * For the `open_url`
action: The `value` field has been renamed to `url`. … For the `change_page` action: The `value` field
has been renamed to `page` … now requires a positive integer instead of a string.”; 25w03a: “The `text`
field in `show_text` action has been renamed to `value`.”
Current shapes: §Click events / §Hover events (`show_item`: `id`, `count`, `components`; `show_entity`:
`name`, `id`, `uuid`).

Runtime behaviour changes to plan for:
* 1.21.6: “Users will now be prompted for confirmation before executing a command from the
  `run_command` click action in books and chat if the command can't be parsed or requires elevated
  permissions (i.e. higher than 0).”
* 1.21.9: previously a `run_command` whose command needs a signed message (`/say`, `/me`, `/msg`,
  `/tell`, `/w`, `/teammsg`, `/tm`) “would be silently discarded. Instead, a screen will be shown that
  lets the user insert the command into the chat window or copy the command to their clipboard…”

Source: *Java Edition 1.21.6* §Technical/Changes/General (Data pack); *Java Edition 1.21.9* §Changes/General
(Attribute → `run_command` click event).

---

## 4. Game rules (1.21.11, 25w44a): registry ids, snake_case, some inverted

All game rules moved into a registry and renamed to resource locations in snake_case
(`minecraft:` prefix optional in `/gamerule`). Mechanical conversion applies to everything not in the
table below (e.g. `mobGriefing`→`mob_griefing`, `keepInventory`→`keep_inventory`,
`randomTickSpeed`→`random_tick_speed`, `fallDamage`→`fall_damage`, `pvp`→`pvp`, `raids`… ).

Non-mechanical renames (**complete list as given by the wiki**):

| 1.21.4 | 26.3 | note |
|---|---|---|
| `announceAdvancements` | `show_advancement_messages` | |
| `commandBlocksEnabled` | `command_blocks_work` | |
| `command_modification_block_limit` | `max_block_modifications` | was already snake |
| `disableElytraMovementCheck` | `elytra_movement_check` | **value inverted** |
| `disablePlayerMovementCheck` | `player_movement_check` | **value inverted** |
| `disableRaids` | `raids` | **value inverted** |
| `doDaylightCycle` | `advance_time` | |
| `doEntityDrops` | `entity_drops` | |
| `doImmediateRespawn` | `immediate_respawn` | |
| `doInsomnia` | `spawn_phantoms` | |
| `doLimitedCrafting` | `limited_crafting` | |
| `doMobLoot` | `mob_drops` | |
| `doMobSpawning` | `spawn_mobs` | |
| `doPatrolSpawning` | `spawn_patrols` | |
| `doTileDrops` | `block_drops` | |
| `doTraderSpawning` | `spawn_wandering_traders` | |
| `doVinesSpread` | `spread_vines` | |
| `doWardenSpawning` | `spawn_wardens` | |
| `doWeatherCycle` | `advance_weather` | |
| `maxCommandChainLength` | `max_command_sequence_length` | |
| `maxCommandForkCount` | `max_command_forks` | |
| `naturalRegeneration` | `natural_health_regeneration` | |
| `snowAccumulationHeight` | `max_snow_accumulation_height` | |
| `spawnRadius` | `respawn_radius` | |
| `spawnerBlocksEnabled` | `spawner_blocks_work` | |

Removed at the same time: `doFireTick`, `allowFireTicksAwayFromPlayer` (replaced by new
`fire_spread_radius_around_player`, int, `-1` = unlimited, `0` = off).
Removed in 1.21.9: `spawnChunkRadius` (spawn chunks removed). Added: `pvp`, `spawnMonsters`,
`allowEnteringNetherUsingPortals` (25w35a) — new, no migration needed.

Value range clamping added in 1.21.11 (out-of-range values now rejected): `max_block_modifications` ≥1,
`max_command_forks` ≥1, `max_command_sequence_length` ≥0, `max_entity_cramming` ≥0,
`max_snow_accumulation_height` 0–8, `players_nether_portal_creative_delay` ≥0,
`players_nether_portal_default_delay` ≥0, `players_sleeping_percentage` ≥0, `random_tick_speed` ≥0,
`respawn_radius` ≥0.

Inversion semantics for the converter: `gamerule disableElytraMovementCheck true` → `gamerule elytra_movement_check false`;
`disablePlayerMovementCheck true` → `player_movement_check false`; `disableRaids true` → `raids false`.
For `gamerule <name>` *queries* (`execute store result … run gamerule <name>`) the returned boolean is the
new (non-inverted) meaning.

Source: *Game rule* §History/Java Edition, 1.21.11/25w44a: “All game rules have now been moved into a
registry. Because of that, all game rules have been renamed to resource locations in snake case instead of
camel case… some values are also inverted.” + the “List of game rules that have been renamed” /
“List of game rules with added limited value range” collapses (quoted above verbatim). 1.21.9 removal:
*Java Edition 1.21.9* §Changes/General/Game rule: “The game rule `spawnChunkRadius` was removed.”

---

## 5. Command syntax breaks between 1.21.4 and 26.3

### 1.21.5
* **Text arguments are SNBT** — `tellraw`, `title`, `bossbar … name`, `scoreboard … displayname`,
  `team … displayName`, `scoreboard` styled `numberformat` (see §2/§3).
* **`setblock` / `fill` block-entity handling**: if block-entity NBT is omitted the existing data is
  preserved; to clear it you must pass `{}`. Old behaviour (omitting cleared/kept inconsistently).
  ```mcfunction
  setblock 0 64 0 minecraft:chest            # now keeps old chest contents
  setblock 0 64 0 minecraft:chest {}         # clears them
  ```
* **`fill` / `clone` / `setblock` / `place template` new option `strict`** and non-terminal `replace`:
  `fill <from> <to> <block> [replace <filter>] [strict|destroy|hollow|outline]`,
  `setblock <pos> <block> [destroy|keep|replace|strict]`. Existing `replace`-last forms still parse.
* **`data get`** can no longer traverse paths with an empty key (`… foo."".bar`).
* **Slot `horse.saddle` → `saddle`** (used by `item replace`, `execute if items`, loot `slot` refs).

Source: *Java Edition 1.21.5* §Technical/Changes/Command format.

### 1.21.6
* `run_command` confirmation prompt for commands that fail to parse or need permission > 0 (§3).
* `/dialog show|clear` added; `show_dialog` click action added; `custom` click action added.

### 1.21.9
* `run_command` executing `/say /me /msg /tell /w /teammsg /tm` now opens an insert/copy screen instead
  of silently discarding (§3).
* `/summon` now **fails** when trying to summon hostile mobs in Peaceful.
* `/spawnpoint` and `/setworldspawn`: `<angle>` replaced by optional `<rotation>` (now also pitch);
  `/setworldspawn` no longer limited to the Overworld.
  ```mcfunction
  # 1.21.4
  spawnpoint @s ~ ~ ~ 90
  # 26.3 (yaw only still accepted; pitch now settable)
  spawnpoint @s ~ ~ ~ 90 0
  ```
* `/particle minecraft:flash` now **requires** a `color` (argb) parameter; `dragon_breath`,
  `instant_effect`, `effect` gained optional `power`/`color`.
  ```mcfunction
  # 1.21.4
  particle minecraft:flash ~ ~1 ~ 0 0 0 0 1
  # 26.3
  particle minecraft:flash ~ ~1 ~ 0 0 0 0 1 0xFFFFFF
  ```
* Server commands now run from the **respawn dimension** by default instead of always the Overworld
  (affects relative coords / implicit dimension of console & function-tag execution context).
* World border is per-dimension (`worldborder` effects no longer global).
* Block `chain` → `iron_chain` (id used in `setblock`, `give`, predicates).

Source: *Java Edition 1.21.9* §Changes/Command format; §Changes/General (`Particles`, `Attribute`→run_command,
`World border`, `Data pack`→`chain`→`iron_chain`), §Additions/Command format.

### 1.21.11
* **`worldborder` time arguments are now in game ticks**, not seconds (`s`/`d` suffixes available).
  Silent behaviour break:
  ```mcfunction
  # 1.21.4: 10 seconds
  worldborder add 10 10
  # 26.3: 10 ticks; use a suffix for seconds/days
  worldborder add 10 10s
  ```
* Game-rule ids (§4).
* Entity NBT: `AngerTime` → `anger_end_time` (absolute end time), `AngryAT` → `angry_at` (§6).
* `execute (if|unless) stopwatch <id> <range>` added; `/stopwatch` added — no break.

Source: *Java Edition 1.21.11* §Changes/Command format; §Changes/General (game rules).

### 26.1
* **Slot `villager.*` removed** — villager/piglin inventories are now `mob.inventory.*`.
  ```mcfunction
  # 1.21.4
  item replace entity @s villager.0 with minecraft:emerald
  # 26.3
  item replace entity @s mob.inventory.0 with minecraft:emerald
  ```
* **`/time` is clock-based**: `time set <timemarker>` advances to the next occurrence of the marker;
  `set`/`add` return the clock's total elapsed ticks (not time-of-day); `time of <clock> …` optional.
  `time set day` still parses but its numeric result/`execute store` value changes.

Source: *Java Edition 26.1* §Changes/Command format (`time`); §Changes/General (Data pack: “Villager
inventory slots can now be accessed using `mob.inventory.*`; `villager.*` has been removed.”).

### 26.2
* **Team/waypoint colours must be lowercase snake_case**: “only `dark_blue` is accepted and not
  `darkpurple` or `DarkPurple`”. Affects `team modify <name> color` and `waypoint modify … color`.
* Entity predicate format change (see 26.3 predicate list; the id-ification starts here): all keys are
  identifiers, `type` → `minecraft:entity_type`, unknown keys now rejected.
  Affects inline predicates: `execute if predicate {…}`.

Source: *Java Edition 26.2* §Changes/Command format (General); §Changes/General (`Predicates`).

### 26.3
* `/publish` — `gamemode` argument **removed**; use `/defaultgamemode` / `/gamemode`.
* **Commands that change nothing now fail**: `/time`, `/item`, `/fillbiome`.
* **Return values now = actually affected count** (not selector count) for `/team`, `/tag`, `/recipe`,
  `/enchant`, `/effect`, `/clear`, and `/scoreboard players enable`. This changes
  `execute store result …` results.
* `/give`, `/unpublish`, `/tick` now signal errors; `/tick step`, `/tick step stop`, `/tick sprint stop`
  signal errors instead of returning 0.
* **`/item` now takes a slot source everywhere a slot was used**; string slot ranges
  (`armor.chest`, `container.*`, `hotbar.4`) are still accepted as shorthand for
  `{type:"minecraft:slot_range",slots:"…"}`. `replace` semantics changed (source items consumed one by
  one); new subcommands `item fill`, `item override`. `from entity` may target multiple entities.
* **`execute if|unless items` takes a slot source** instead of a slot; new
  `execute if|unless slots block|entity <…> <slot source>`.
* **`/data modify … set|merge|append|prepend|insert compute <provider>`**; `compute` is split into
  `compute <target> integer <int_provider>` / `compute <target> float <float_provider>`.
* **Predicates (also inline in `execute if predicate`)**:
  * `condition` (type field) → **`type`**, now mandatory (used to default to `minecraft:entity_properties`).
  * A list of predicates is no longer accepted; wrap in `minecraft:all_of`.
  * `minecraft:reference` predicate removed — use the id directly.
  * `minecraft:block_state_property` removed → `minecraft:match_block`.
  * `damage_source_properties.tags.id` now accepts ids too, so tags need a `#` prefix.
  ```mcfunction
  # 1.21.4
  execute if predicate {condition:"minecraft:entity_properties",entity:"this",predicate:{type:"minecraft:player"}} run say hi
  # 26.3
  execute if predicate {type:"minecraft:entity_properties",entity:"this",predicate:{"minecraft:entity_type":"minecraft:player"}} run say hi
  ```
* **Loot tables** (incl. inline tables in `/loot … loot {…}`, `/give`, advancement `rewards.loot`):
  * pool entry `conditions` → `condition` (single predicate / id, no list);
  * pool entry `functions` → `modifier`;
  * loot function `function` → `type`; loot-function `conditions` → `condition` (available on all functions);
  * `reference` condition/modifier removed (use ids/tags).
* **Item modifiers** (also inline): list-of-modifiers shorthand no longer allowed → explicit
  `{type:"minecraft:sequence",…}`; `function` → `type`; `minecraft:reference` removed;
  `minecraft:set_loot_table` drops `type` and renames `name` → `loot_table_id`;
  `minecraft:exploration_map.destination` is required and tags need `#`.
* Number providers split into `context_int_provider` / `context_float_provider`; convert with
  `from_int` / `from_float`. `score` and `binomial` exist in only one of the two.
* `/spreadplayers` block-safety now driven by `#entities_can_teleport_to`.
* `/swing` gained optional animation (`whack`|`stab`) and duration args (compatible).
* `/place feature` accepts inline feature definitions; `/locate` performance only.

Source: *Java Edition 26.3* §Changes/Command format (all bullets quoted above); §Changes/General
(`Loot functions`, `Loot tables`, `Predicate`, `Data pack`); curated list 26.3 §command.

Not changed (checked, so the converter can leave them alone):
* `attribute` ids — no rename between 1.21.4 and 26.3 (only new attributes and, in 26.2,
  `minecraft:knockback_resistance` minimum −2.0). **No id churn found.**
* Mob effect ids, enchantment ids, `effect` / `enchant` argument grammar — no renames found in the
  listed pages (**UNVERIFIED beyond “no mention in the wiki pages/changelog”**; only the `effect`
  return value changed, see above).
* `/say`, `/msg` grammar itself — unchanged; only the `run_command` click path changed (§3).

---

## 6. NBT / entity-data changes visible inside commands

### 1.21.5 (25w02a–25w07a) — biggest batch
* Equipment merged: `ArmorItems`, `HandItems`, `body_armor_item`, `SaddleItem`, `Saddle` →
  `equipment:{chest:{…},…}`; `ArmorDropChances`, `HandDropChances`, `body_armor_drop_chance` →
  `drop_chances:{…}`.
* Player spawn: `SpawnX/Y/Z`, `SpawnAngle`, `SpawnDimension`, `SpawnForced` → `respawn:{…}`.
* `FallDistance` → `fall_distance` (double).
* `Pos`, `Motion`, `Rotation` lists must have the right element count.
* Minecarts: `CustomDisplayTile` removed; `DisplayState`/`DisplayOffset` always active.
* `TileX/TileY/TileZ` → `block_pos` (item frames, glow item frames, leash knots);
  `LifeTicks`→`life_ticks`, `BoundX/Y/Z`→`bound_pos`; turtle `HasEgg`→`has_egg`,
  `HomePosX/Y/Z`→`home_pos`, `TravelPos*` removed; dolphin `TreasurePos*` removed;
  phantom `Size`→`size`, `AX/AY/AZ`→`anchor_pos`; `SleepingX/Y/Z`→`sleeping_pos`;
  `enteredNetherPosition`→`entered_nether_pos`.
* 1.21.5 also changes item component names used in commands: `hide_tooltip` / `hide_additional_tooltip`
  removed and per-component `show_in_tooltip` removed → `tooltip_display`;
  `weapon.damage_per_attack` → `item_damage_per_attack`.
* SNBT itself: heterogeneous lists (no more wrapper objects), `0x`/`0b` integers, E-notation floats,
  digit separators, `b/s/i/l` suffixes with `u`/`s` prefixes, trailing commas. Mostly permissive.

Source: *Template:Data pack format* 71 (“The `ArmorItems`, `HandItems`, `body_armor_item`, `SaddleItem`,
and `Saddle` NBT tags were removed and merged into the `equipment` field. The `SpawnX`… `SpawnForced`
NBT tags were removed and merged into the `respawn` field.”); curated list 1.21.5 §NBT/§data component.

### 1.21.6
* `area_effect_cloud`: `Particle` → `custom_particle` (no longer inherits potion colour).
* `tnt`, `vex`: new optional `owner` (UUID).
* All mobs: new `home_pos`, `home_radius`.

### 1.21.9
* Player `respawn`: `angle` → `yaw` (required), `pitch` added (required), `dimension` required.
* `minecraft:skull` block entity `profile` field now matches the `minecraft:profile` component
  (immutable/static-vs-dynamic resolution).

Source: *Java Edition 1.21.9* §Changes/General (`Entity data`, `Block entity data`).

### 1.21.11
* `AngerTime` removed → `anger_end_time` (the moment the mob stops being angry);
  `AngryAT` → `angry_at`.
* Item tag `#enchantable/sword` → `#enchantable/sweeping` (only relevant if written in commands).

Source: curated list 1.21.11 §NBT; wiki 1.21.11 §Changes (item tags).

### 26.2
* `HurtByTimestamp` removed from living entities → `ticks_since_last_hurt_by_mob` (elapsed, not a
  timestamp — the converter must rewrite values, not just the key).

Source: *Java Edition 26.2* §Changes/General/Identifiers: “Removed the `HurtByTimestamp` tag from Living
Entities, `ticks_since_last_hurt_by_mob` should be used instead.”; *Template:Data pack format* 105.0.

### 26.3
* Sign block entities (`minecraft:sign`, `minecraft:hanging_sign`): new `allow_op_features` boolean,
  default `false`. Commands/click events inside sign text are **no longer executed on click** and text
  components on newly placed signs are not resolved unless it is `true`. Pre-existing signs are migrated
  to `true`; signs created by `setblock`/`data merge`/`give` with `block_entity_data` need it set
  explicitly.
* Decorated pot `sherds`: list of 4 ids → object `{back,left,right,front}` (item stack fields);
  item component `minecraft:pot_decorations` likewise list → object.
* `minecraft:brewing_stand`: `BrewTime` short→int, `Fuel` byte→int; new `total_brew_time`,
  `total_fuel`, `speed_multiplier`.
* `minecraft:furnace` / `smoker` / `blast_furnace`: `cooking_time_spent`, `cooking_total_time`,
  `lit_time_remaining`, `lit_total_time` short→int; new `speed_multiplier`.
  (short→int matters for `data modify … set value 200s` style writes and for `execute if data` type tests.)
* Item components: `minecraft:swing_animation` removed → `minecraft:attack_animation` +
  `minecraft:interact_animation`; `minecraft:map_color` removed.
* Block state `Name`/`Properties` → `id`/`properties` (JSON/worldgen definitions; **not** the
  `setblock`/`fill` block-state argument syntax).
* `minecraft:trim_material`: `asset_name` → `palette_id`, `override_armor_assets` removed.

Source: *Java Edition 26.3* §Changes/General (`Block entity data`, `Block entity format`, `Block states`,
`Data component format`, `Environment attribute`, `Textures`→palette).

---

## 7. Conversion checklist (order of operations)

1. Rewrite `pack.mcmeta` to `min_format`/`max_format` `[121,0]`, drop `pack_format`/`supported_formats`.
2. Any NBT string that holds JSON → parse JSON, rename `clickEvent`/`hoverEvent` + payloads, re-emit SNBT.
3. Rename gamerule ids (mechanical snake_case + the 26-row table) and invert the 3 `disable*` rules.
4. Rename entity/block-entity NBT keys (§6), rewriting value semantics for `HurtByTimestamp`,
   `AngerTime`.
5. Rewrite inline predicates / loot tables / item modifiers to the 26.3 shapes (`type`, `condition`,
   `modifier`, no lists, no `reference`, no `block_state_property`).
6. Patch individual commands: `particle flash` colour, `worldborder` time units, `spawnpoint` rotation,
   `villager.*` slots, team colours, `/publish gamemode`, slot→slot-source forms.
7. Flag `execute store result` sites for the changed return values (`/time`, `/item`, `/team`, `/tag`,
   `/recipe`, `/enchant`, `/effect`, `/clear`, `/fillbiome`, `/scoreboard players enable`).
