# 规则对照表：1.21.4 → 26.3

每条规则都给出旧写法、新写法和依据。依据均为 **英文 Minecraft Wiki** 的版本页
“Changes → General / Data pack” 或专门的技术页面（`?action=raw` 读取的 wikitext），
快照号来自 Wiki 历史章节。中文 Wiki 只用于结构交叉核对。

---

## 1. `pack.mcmeta`

| 旧 | 新 |
| --- | --- |
| `{"pack":{"pack_format":61,"description":"..."}}` | `{"pack":{"description":"...","min_format":[121,0],"max_format":[121,0]}}` |

- 1.21.9（25w31a）起 `min_format` / `max_format` 为必填；`pack_format` 变为可选，
  `supported_formats` 被移除。只有还需要兼容 ≤1.21.8（数据包格式 < 82）时才保留旧字段。
- 单个整数 `121` 等价于 `[121, 0]`；`max_format` 用单个整数表示“任意次版本”，
  因此这里显式写成 `[121, 0]` 以精确锁定 121.0。
- 依据：Wiki `pack.mcmeta` §Format 与 §History（1.21.9 / 25w31a）；
  `Java Edition 26.3` §Changes>General>Data pack（“The pack format version is now 121.0”）。

## 2. 文本组件（1.21.5）

组件不再以 JSON 字符串存储，直接内联为 NBT；命令参数也改为 SNBT。

| 旧 | 新 |
| --- | --- |
| `CustomName:'{"text":"Boss"}'` | `CustomName:{text:"Boss"}` |
| `lore:['{"text":"x"}']` | `lore:[{text:"x"}]` |
| `components:{"minecraft:custom_name":'{"text":"x"}'}` | `components:{"minecraft:custom_name":{text:"x"}}` |
| `text:'{"translate":"..."}'`（text_display） | `text:{translate:"..."}` |
| `pages:[{raw:'{"translate":"..."}'}]` | `pages:[{raw:{translate:"..."}}]` |
| `data modify ... set value '{"text":"x"}'` | `data modify ... set value {text:"x"}` |

事件字段（1.21.5 / 25w02a、25w03a）：

| 旧 | 新 |
| --- | --- |
| `clickEvent` / `hoverEvent` | `click_event` / `hover_event` |
| click `run_command` / `suggest_command` 的 `value` | `command` |
| click `open_url` 的 `value` | `url` |
| click `open_file` 的 `value` | `path` |
| click `change_page` 的 `value`（字符串） | `page`（正整数） |
| hover `show_text` 的 `contents` | `value`（25w02a 曾改名为 `text`，25w03a 再改为 `value`） |
| hover `show_item` 的 `contents:{id,count,components}` | 内联为 `id` / `count` / `components` |
| hover `show_entity` 的 `contents:{type,id}` | `id`（实体类型）/ `uuid`（旧 `id`） |

- 依据：Wiki `Text component format` §History 1.21.5（25w02a、25w03a）；
  `Java Edition 1.21.5` §Technical>Changes>General>Text component format。

## 3. 物品组件（1.21.5 / 26.3）

| 旧 | 新 |
| --- | --- |
| `hide_tooltip={}` / `hide_additional_tooltip={}` | `tooltip_display={hide_tooltip:true}` / `hidden_components:[...]` |
| 组件内的 `show_in_tooltip:false` | 删除该字段，组件 ID 加入 `tooltip_display.hidden_components` |
| `enchantments={levels:{id:1}}` | `enchantments={id:1}` |
| `attribute_modifiers={modifiers:[...]}` | `attribute_modifiers=[...]` |
| `dyed_color={rgb:12345}` | `dyed_color=12345` |
| `can_place_on={predicates:[...]}` | `can_place_on=[...]` |
| `minecraft:swing_animation`（26.3） | `minecraft:attack_animation` + `minecraft:interact_animation` |
| `minecraft:map_color`（26.3） | 删除 |

- 依据：Wiki `Java Edition 1.21.5` §Technical>Changes>General>Data components；
  `Java Edition 26.3` §Changes>General>Data component format。

## 4. 方块状态编解码（26.3）

| 旧 | 新 |
| --- | --- |
| `block_state:{Name:"minecraft:tnt",Properties:{unstable:true}}` | `block_state:{id:"minecraft:tnt",properties:{unstable:true}}` |
| `BlockState:{Name:...}` / `carriedBlockState:{Name:...}` | 同上 |

- 同时覆盖 `inBlockState`、`DisplayState`（矿车）等方块状态复合标签。
- 方块状态的 **命令参数** 语法（`stone[facing=east]`）不受影响。
- 依据：`Java Edition 26.3` §Changes>General>Block states
  （“Name is now id / Properties is now properties”）。

## 5. 实体谓词（26.2）

旧结构（可选字段 + `type_specific` 判别）改为“命名空间 ID → 子谓词”的映射：

```json
// 旧
{"condition":"minecraft:entity_properties","entity":"this",
 "predicate":{"type":"minecraft:player","team":"red",
              "type_specific":{"type":"minecraft:player","input":{"jump":true}}}}
// 新
{"type":"minecraft:entity_properties","entity":"this",
 "predicate":{"minecraft:entity_type":"minecraft:player",
              "minecraft:team":"red",
              "minecraft:type_specific/player":{"input":{"jump":true}}}}
```

- 所有键名改为命名空间 ID；`type` → `minecraft:entity_type`；
  `type_specific.{type_specific/<kind>}` 提升为顶层 `minecraft:type_specific/<kind>`。
- `slime` → `cube_mob`（26.2 snap4）。
- 1.21.5 删除的变种子谓词（`axolotl`、`fox`、`villager` …）无法自动转换，
  程序会删除并写警告（本包未使用）。
- 依据：Wiki `Entity predicate` §Data format；`Java Edition 26.2`
  §Changes>General（snapshot 3/4）。

## 6. 谓词（26.3）

| 旧 | 新 |
| --- | --- |
| `{"condition":"minecraft:random_chance","chance":0.5}` | `{"type":"minecraft:random_chance","chance":0.5}`（`condition` 必填化） |
| 根为谓词数组 / 多条件列表 | 显式 `{"type":"minecraft:all_of","terms":[...]}` |
| `{"condition":"minecraft:reference","name":"x:y"}` | `"x:y"` |
| `block_state_property`（`block`/`properties`） | `match_block`（`blocks`/`state`） |
| `value_check`（`range`） | `int_value_check` / `float_value_check`（`test`） |
| `damage_source_properties.tags[].id`（标签无 `#`） | 全部加 `#` |

- 依据：`Java Edition 26.3` §Changes>General>Predicate；Wiki `Predicate` §History。

## 7. 物品修饰器（26.3）

| 旧 | 新 |
| --- | --- |
| `"function":"minecraft:set_count"` | `"type":"minecraft:set_count"` |
| 文件根为数组 `[{...},{...}]` | `{"type":"minecraft:sequence","functions":[...]}`（单元素时直接展开） |
| `"conditions":[...]` | `"condition":<谓词>`（多条件包成 `all_of`） |
| `filtered` 的 `modifier` | `on_pass`（`on_fail` 省略即不处理） |
| `set_loot_table` 的 `name` / `type` | `loot_table_id` / 删除 |
| `exploration_map` 的 `destination`（可省略） | 必填；`map_color` 删除 |

- `sequence` 的列表字段仍是 `functions`（英文 26.3 更新日志原文：
  “Changed minecraft:sequence — The `functions` field now accepts … of a
  `minecraft:item_modifier` type”）。
- 依据：`Java Edition 26.3` §Changes>General>Loot functions；
  Wiki `Item modifier` §History 26.3（snap4/snap9/snap10）。

## 8. 战利品表（26.3）

| 旧 | 新 |
| --- | --- |
| 池/抽取项的 `functions` | `modifier` |
| 池/抽取项的 `conditions`（列表） | `condition`（单个谓词，多条件 `all_of`） |
| `tag` 抽取项的 `name` | `items` |
| 没有 `type` 的内联数值提供器（默认 uniform） | 补 `type:"minecraft:uniform"` |

- 依据：`Java Edition 26.3` §Changes>General>Loot table；Wiki `Loot table` §History。

## 9. 进度（26.3 + 1.21.5）

| 旧 | 新 |
| --- | --- |
| 有 `display` 的根进度缺少 `background` | 补 `minecraft:gui/advancements/backgrounds/stone` |
| 非根进度带 `background` | 删除 |
| `background: "minecraft:textures/gui/advancements/backgrounds/x.png"` | `"minecraft:gui/advancements/backgrounds/x"` |
| `recipe_unlocked.recipe` / `recipe_crafted.recipe_id` | `recipes` |
| `slide_down_block.block` / `bee_nest_destroyed.block` / `enter_block.block` | `blocks` |
| `player_generates_container_loot.loot_table` | `loot_tables` |
| 触发器的 `player`（谓词列表 / 裸实体谓词） | 单个谓词（裸实体谓词包成 `entity_properties`） |
| `location`（位置谓词） | 包成 `{"type":"minecraft:location_check","predicate":{...}}` |

- 依据：`Java Edition 26.3` §Changes>General>Advancement；
  Wiki `Advancement definition` §History（1.21.5 / 25w04a 背景路径）。

## 10. 游戏规则（1.21.11）

注册表化，驼峰 → `minecraft:snake_case`，其中三条语义取反：

| 旧 | 新 | 取反 |
| --- | --- | --- |
| `disableElytraMovementCheck` | `minecraft:elytra_movement_check` | 是 |
| `disablePlayerMovementCheck` | `minecraft:player_movement_check` | 是 |
| `disableRaids` | `minecraft:raids` | 是 |
| `doTileDrops` | `minecraft:block_drops` | 否 |
| `doMobLoot` | `minecraft:mob_drops` | 否 |
| `doDaylightCycle` | `minecraft:advance_time` | 否 |
| `doWeatherCycle` | `minecraft:advance_weather` | 否 |
| `maxCommandChainLength` | `minecraft:max_command_sequence_length` | 否 |
| `commandModificationBlockLimit` | `minecraft:max_block_modifications` | 否 |
| `naturalRegeneration` | `minecraft:natural_health_regeneration` | 否 |
| `doImmediateRespawn` | `minecraft:immediate_respawn` | 否 |
| `mobGriefing` | `minecraft:mob_griefing` | 否 |
| `fallDamage` / `fireDamage` / `drowningDamage` / `freezeDamage` | `minecraft:fall_damage` / `fire_damage` / … | 否 |
| `sendCommandFeedback` / `commandBlockOutput` | `minecraft:send_command_feedback` / `command_block_output` | 否 |
| `projectilesCanBreakBlocks` / `universalAnger` | `minecraft:projectiles_can_break_blocks` / `universal_anger` | 否 |

其余驼峰规则按 `camelCase → snake_case` 自动转换；未收录的规则会给出警告。

- 依据：Wiki `Game rule` §History（1.21.11 / 25w44a 的改名表）。

## 11. 实体 NBT（1.21.5 / 1.21.11 / 26.2）

| 旧 | 新 |
| --- | --- |
| `HandItems:[主手,副手]` | `equipment:{mainhand:…,offhand:…}` |
| `ArmorItems:[脚,腿,胸,头]` | `equipment:{feet:…,legs:…,chest:…,head:…}` |
| `body_armor_item` / `SaddleItem` / `Saddle:1b` | `equipment.body` / `equipment.saddle` |
| `ArmorDropChances` / `HandDropChances` / `body_armor_drop_chance` | `drop_chances:{…}` |
| `FallDistance` | `fall_distance`（double） |
| `TileX/TileY/TileZ` | `block_pos:[I;x,y,z]` |
| `SleepingX/Y/Z` | `sleeping_pos:[I;x,y,z]` |
| `BoundX/Y/Z` / `HomePosX/Y/Z` | `bound_pos` / `home_pos` |
| `SpawnX/Y/Z/SpawnAngle/SpawnDimension/SpawnForced` | `respawn:{pos,dimension,angle,forced}` |
| `AngryAT` | `angry_at` |
| `AngerTime`（剩余刻数） | `anger_end_time`（绝对游戏时间）⚠️ 语义变化，见 README |
| `HurtByTimestamp`（26.2） | `ticks_since_last_hurt_by_mob` ⚠️ 语义变化 |
| `LifeTicks` / `HasEgg` / `enteredNetherPosition` | `life_ticks` / `has_egg` / `entered_nether_pos` |
| NBT 路径里的 `HandItems[0]` / `ArmorItems[3]` | `equipment.mainhand` / `equipment.head` |
| 谓词 `Inventory:[{Slot:-106b,…}]` / `Slot:100b–103b` | `equipment:{offhand:…}` / `feet`·`legs`·`chest`·`head`（见 §17） |

- 依据：`Java Edition 1.21.5` §Technical>Changes>General>Entity format；
  `Java Edition 1.21.11`、`Java Edition 26.2` §Changes>General。

## 12. 标签改名

| 旧 | 新 |
| --- | --- |
| `#minecraft:dead_bush_may_place_on` | `#minecraft:supports_dry_vegetation`（1.21.5 → 26.1 连续改名） |
| `#minecraft:convertable_to_mud` | `#minecraft:convertible_to_mud` |
| `#minecraft:dowses_campfires` | `#minecraft:douses_campfires` |
| `#minecraft:concrete_powder` | `#minecraft:concrete_powders` |
| `#on_*_explorer_maps` | `#on_*_mansion/monument/pyramid/hut/buried_trial_chambers_maps` |
| `#minecraft:enchantable/sword` | `#minecraft:enchantable/sweeping` |

- 依据：`Java Edition 26.3` §Changes>General>Tags；`Java Edition 1.21.5/1.21.11`。

## 13. 其他

| 改动 | 说明 |
| --- | --- |
| 配方 `cookingtime` | 26.3 统一为 200 刻，烟熏炉/高炉配方时间翻倍 |
| 方块/物品 ID `minecraft:chain` | → `minecraft:iron_chain`（1.21.9） |
| 队伍颜色 | 26.2 起只接受小写蛇形名（`dark_purple`） |
| 严格 JSON | 26.3 中任意一个无法解析的 JSON 文件都会导致整个数据包加载失败 |

## 14. 程序不自动转换的内容

- `AngerTime` 的“相对 → 绝对”时间语义（写入哨兵值并逐条报告）；
- `HurtByTimestamp` 的时间语义（写入 `0` 并报告）；
- 1.21.5 删除的变种实体子谓词（`axolotl`、`villager` …）→ 需要手工改成
  `minecraft:components` + 变种组件；
- 1.21.9 起 `run_command` 对聊天命令的确认框（行为变化，不是语法）；
- 26.3 的“空操作即失败”和返回值为“实际受影响数量”（行为变化）；
- 26.3 告示牌的 `allow_op_features`（新字段默认 `false`，旧告示牌会自动迁移；
  通过 `setblock`/`data` 新建的告示牌若需要点击事件，需显式写 `allow_op_features:1b`）；
- 数据包之外的内容（世界存档、资源包、命令方块里已保存的 NBT）。

## 15. v2.1 新增规则

| 规则 id | 改动 | 说明 |
| --- | --- | --- |
| `advancement.unknown_field` | 删除 26.3 未定义的字段 | 只处理模式完全确定的四层：根对象（`criteria`/`display`/`parent`/`requirements`/`rewards`/`sends_telemetry_event`）、`display`、`display.icon`、`rewards` |
| `item_component.namespace` | 资源位置组件补命名空间 | `minecraft:item_model` / `minecraft:tooltip_style` 的值若不含 `:`，补成 `minecraft:<值>` |
| `item_component.simplified_form` | 进度图标组件也参与扁平化 | 以前只处理命令 SNBT 与谓词里的组件；现在 `display.icon.components` 同样扁平化（`dyed_color.rgb`、`enchantments.levels`、`show_in_tooltip`…） |
| `json.tab_indent` | 输出格式 | 被重写的 JSON 统一 Tab 缩进、LF 换行、末尾换行、去 BOM |

- 依据：`Advancement definition` §JSON format（字段集合）、`Data component format`（`item_model` / `tooltip_style` 是资源位置）、`Java Edition 1.21.5` §Data components（组件简化形式）。
- 为什么准则层不删未知字段：`_criterion` 会把误写在准则层的 `recipe`/`loot_table`/`block` 迁移到正确位置，先删未知字段会丢数据，所以删除只发生在模式完全确定的层级。

## 16. v2.2 新增规则

| 规则 id | 改动 | 说明 |
| --- | --- | --- |
| `particle.flash_color` | `particle flash` 补 `color` | 1.21.9（25w36a）起 `flash` 必须带 `color`（ARGB：4 个 0.0–1.0 的 float，或打包 int）。1.21.4 的 `flash` 没有任何选项、固定渲染成白色，因此补 `{color:[1.0,1.0,1.0,1.0]}`，保持原观感 |
| `json.dangling_reference` | 删除引用失效的 JSON | 26.3 起 `advancement`/`loot_table`/`recipe`/`predicate`/`item_modifier`/`number_provider`/`slot_source` 中任一文件出错会让**整个世界拒绝加载**（MC-310325），不再只是跳过该文件。程序解析 `parent`、`rewards.function/loot/recipes`、`criteria.*.conditions.recipes/loot_table`、`minecraft:reference`、嵌套 `loot_table`、配方与图标物品 ID、函数标签值；目标在包内不存在时删除该文件并写入报告 |
| `json.reward_dropped` | 保留 advancement，移除失效奖励 | 只坏了 `rewards.function/loot/recipes` 的进度仍有意义（常被函数用 `advancement grant` 授予），删掉出错的那一项即可加载，文件保留 |
| `json.invalid_deleted` | 删除无法解析的 JSON | 严格注册表里解析失败的文件同样会让整个世界加载失败；删掉它让其余内容可用（`--keep-dangling` 时改为报错保留） |

- 依据：`Particle format` §History（1.21.9 / 25w36a：“`flash` now requires a `color` parameter (argb)”）、`Java Edition 1.21.9` §Particles。
- 只改 `flash`：`dust`、`block`、`item` 等类型在 1.21.4 就已要求选项，不受影响；`tinted_leaves`（1.21.5 新增可选 `color`）本包未使用。
- 已有选项时只补缺的键（`flash{scale:2.0}` → `flash{color:[1.0,1.0,1.0,1.0],scale:2.0}`），并跳过注释与引号字符串里的同名文本。
- 完整调研见 `docs/RESEARCH-NOTES.md`。
- 删除依据：Mojira [MC-310325](https://mojira.dev/MC-310325)（26.3-snapshot-3，官方标记 Works As Intended）与 [MC-311918](https://mojira.dev/MC-311918)（配方引用不存在物品同样致命）；`minecraft:` 命名空间与非本包命名空间的引用一律放行（属于原版或同载的其他数据包）。
- 删除是**级联**的：删掉一个 advancement 后，以它为 `parent` 的进度会在下一轮一并删除；最多迭代 10 轮。
- 只坏 `rewards` 的进度不删：例如 `cake_team_tower:food_for_the_people` 只缺奖励函数，但被 `shop12_petal_park.mcfunction` 用 `advancement grant` 授予，删除会打断 NPC 任务线，因此保留文件、移除失效的 `rewards.function`。
- 只想审计不删除：`python tools/check_references.py <包目录>`（加 `--delete` 才删除/修剪）；升级时加 `--keep-dangling` 关闭自动处理。

## 17. v2.3 新增规则：玩家装备槽检测

| 旧写法（1.21.4） | 新写法（1.21.5 / 26.3） |
| --- | --- |
| `nbt={Inventory:[{Slot:-106b,…}]}` | `nbt={equipment:{offhand:{…}}}` |
| `nbt={Inventory:[{Slot:100b,…}]}` | `nbt={equipment:{feet:{…}}}` |
| `nbt={Inventory:[{Slot:101b,…}]}` | `nbt={equipment:{legs:{…}}}` |
| `nbt={Inventory:[{Slot:102b,…}]}` | `nbt={equipment:{chest:{…}}}` |
| `nbt={Inventory:[{Slot:103b,…}]}` | `nbt={equipment:{head:{…}}}` |
| `Inventory[{Slot:102b}].components…`（NBT 路径） | `equipment.chest.components…` |

- 槽位映射：`100→feet`、`101→legs`、`102→chest`、`103→head`、`-106→offhand`。
- 1.21.5（25w03a）起，玩家的头盔/胸甲/护腿/靴子和副手物品改存到 `equipment`，`Inventory` 只保留 0–35 号主背包槽。旧写法在 26.3 里**永远匹配不到**（不是报错，是静默失效），所以这类功能会“看起来没反应”。
- 只改这 5 个编号。`Slot:0b..35b`（快捷栏/主背包）**保持原样**：26.3 存档里主背包物品仍然是 `Slot`（byte），谓词照旧可用。
- 主手仍用 `SelectedItem`，不受影响；命令里的 `weapon.offhand`、`armor.head` 等路径也不受影响（写入一直可用）。
- 同时处理 `nbt={…}`、取反的 `nbt=!{…}`、以及 `tellraw`/`data` 里的 `Inventory[{Slot:…}]` 路径。
- 依据：`player.dat format` §Inventory slot numbers（“In versions prior to 25w03a (including 1.21.4), the head, chest, legs, feet, and offhand slots were stored in the Inventory tag”）、1.21.5 更新日志与 [MC-296199](https://mojira.dev/MC-296199)；并在 26.3 存档的 `players/data/<uuid>.dat` 中实测：`Inventory` 只有 0/8/9/11/12 号主背包物品，靴子在 `equipment.feet`。
- 本包实测：源码里 1745 处装备槽 `Inventory` 检测，升级后剩余 4 处（3 处在注释行、1 处在 `data/mario_party/functions/`（1.21 起已失效的旧目录））。
