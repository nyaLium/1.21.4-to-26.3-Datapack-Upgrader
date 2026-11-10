# Minecraft 数据包升级器 — 1.21.4 → 26.3

把 **Minecraft Java 版数据包**从 **1.21.4**（数据包格式 61）升级到 **26.3**
（数据包格式 121.0），跨越中间的 6 个破坏性版本，并生成可逐条核查的变更报告。

* **零依赖**：纯 Python 标准库，不需要 `pip install` 任何东西。
* **确定性**：同一份输入运行两次，产物逐字节相同。
* **幂等**：对产物再跑一次，命中规则为 0。
* **外科手术式改写**：只替换真正改动的 SNBT 片段——注释、宏、CRLF、BOM
  以及没有命中的文件都保持字节不变。
* **可溯源**：每条规则都标注它来自 Minecraft Wiki 的哪一节，报告里逐条引用。

English: [README.md](README.md)

---

## 为什么需要它

从 1.21.4 到 26.3 之间的破坏性改动又多又散：

| 版本 | 破坏点 |
| --- | --- |
| 1.21.5 | 文本组件改为 NBT；`ArmorItems` / `HandItems` 改为 `equipment`；物品组件出现简化形式 |
| 1.21.9 | `pack.mcmeta` 必须写 `min_format` / `max_format`；`particle flash` 必须带颜色 |
| 1.21.11 | 游戏规则改为带命名空间的注册表 ID |
| 26.2 | 实体谓词改用命名空间键 |
| 26.3 | `condition` → `type`、`function` → `type`、`functions` → `modifier`、方块状态 `Name` → `id`、进度背景规则…… |

而且从 26.3 起，**只要有一个 JSON 无法解析或引用失效，游戏就会拒绝加载整个世界**
（Mojira MC-310325，官方标记为"按设计如此"），大包靠手改基本不可行。

## 环境要求

* **Python 3.10 或更新**（在 3.12 上验证）——不需要别的。
* Windows / macOS / Linux。

## 快速开始

```bash
git clone https://github.com/<user>/<repo>.git
cd <repo>

python -m upgrader2 "路径/MyPack"
# => ./dist/MyPack-26.3/
```

Windows 下也可以把包文件夹直接拖到 **`run_upgrade.cmd`** 上，或者带参数运行：

```bat
run_upgrade.cmd "D:\packs\MyPack"
run_upgrade.cmd "D:\packs\MyPack" "D:\out\MyPack-26.3"
```

**一定要在副本上升级**。工具不会往源目录写东西，但保留一份原样才是可重复转换的意义。

## 命令行

```
python -m upgrader2 SOURCE [-o OUTPUT] [--force] [--quiet] [--keep-dangling]
```

| 参数 | 说明 |
| --- | --- |
| `SOURCE` | 数据包目录，必须含 `pack.mcmeta` 和 `data/` |
| `-o, --output` | 输出目录，默认 `./dist/<包名>-26.3` |
| `--force` | 目标已存在时覆盖（会先整个删掉） |
| `--quiet` | 只打印错误 |
| `--keep-dangling` | 保留引用失效的 JSON（默认会删除，见下） |

退出码：`0` 表示没有错误，`1` 表示报告里有错误（例如 `pack.mcmeta` 不是合法 JSON），
可以放进脚本里用。`--quiet` 不改变退出码。

典型输出：

```
source      : C:\packs\MyPack
destination : C:\packs\MyPack-26.3
files       : 4213

rules:
      1204  function.line
       311  json.file_rewritten
        98  text.component_inline
         …
total changes: 2011
deleted      : 0 broken JSON file(s)
lint issues  : 0

report : C:\packs\MyPack-26.3\_upgrade\report.md
         C:\packs\MyPack-26.3\_upgrade\report.en.md
```

## 产物

输出是**整包的副本**，转换结果就地替换：

```
MyPack-26.3/
├─ pack.mcmeta              # 已重写：min_format / max_format = [121, 0]
├─ data/                    # 转换后的数据文件（没改动的原样复制）
└─ _upgrade/
   ├─ report.md             # 中文升级报告
   ├─ report.en.md          # 同一份报告的英文版
   └─ report.json           # 机器可读：规则 × 文件 × 样例
```

`report.json` 结构稳定：

```json
{
  "target_data_pack_version": "121.0",
  "files_scanned": 4213,
  "function_lines": 88104,
  "rules": { "function.line": 1204, "loot_table.renames": 3 },
  "files_by_rule": { "function.line": 731, "loot_table.renames": 2 },
  "entries": [
    {
      "rule": "loot_table.renames",
      "path": "data/mypack/loot_table/chest.json",
      "count": 1,
      "samples": ["entry functions -> modifier"]
    }
  ],
  "removed_files": [],
  "repaired_files": [],
  "lint_issues": [],
  "warnings": [],
  "errors": []
}
```

`report.md`（中文）和 `report.en.md`（英文）内容一致，不用加任何参数就会同时生成；
`report.json` 是同一份数据的机器可读版，规则 ID 和文件路径与语言无关。

## 覆盖了哪些改动

共 34 条规则，每条都锚定到引入它的版本。完整的新旧写法对照与 Wiki 出处见
**[RULES-CN.md](RULES-CN.md)**（中文）/ **[RULES.md](RULES.md)**（英文）；逐版本调研笔记
（含标注 *UNVERIFIED* 的部分）见 **[docs/RESEARCH-NOTES.md](docs/RESEARCH-NOTES.md)**。

| 版本 | 领域 | 改动 |
| --- | --- | --- |
| 1.21.5 | 文本组件 | NBT/命令里的 JSON 字符串改为内联 NBT；`clickEvent`/`hoverEvent` 改名、payload 字段改名、`contents` 内联 |
| 1.21.5 | 实体 NBT | `ArmorItems`、`HandItems`、`body_armor_item` → `equipment`；掉落概率 → `drop_chances`；`Inventory[{Slot:100b…}]` → 装备槽 |
| 1.21.5 | 物品组件 | 简化形式（`enchantments.levels`、`attribute_modifiers.modifiers`、`dyed_color.rgb`、`can_place_on.predicates`…）、`hide_tooltip`/`show_in_tooltip` → `tooltip_display` |
| 1.21.9 | `pack.mcmeta` | `pack_format` → `min_format` / `max_format`（`[121, 0]`） |
| 1.21.9 | 粒子 | `particle flash` 必须带 `color`，自动补不透明白 |
| 1.21.9 | ID | 改名方块/物品（`minecraft:chain` → `minecraft:iron_chain`） |
| 1.21.11 | 游戏规则 | 驼峰 → 命名空间 ID（`doMobLoot` → `minecraft:mob_drops`，含 3 条取反） |
| 26.2 | 实体谓词 | 命名空间键、`type` → `minecraft:entity_type`、`type_specific/<kind>` 扁平化 |
| 26.2 | 实体 NBT | 字段改名（`HurtByTimestamp` → `ticks_since_last_hurt_by_mob` 等） |
| 26.3 | 谓词 | `condition` → `type`、谓词列表 → `all_of`、`block_state_property` → `match_block` |
| 26.3 | 物品修饰器 | `function` → `type`、根数组 → `minecraft:sequence` |
| 26.3 | 战利品表 | `functions` → `modifier`、`conditions` → `condition`、tag 项 `name` → `items` |
| 26.3 | 进度 | 背景规则（显示的根必须有、非根禁止、去掉 `textures/` 与 `.png`）、触发器字段（`recipe` → `recipes`…）、`player` 改为单个谓词 |
| 26.3 | 方块状态 | `{Name, Properties}` → `{id, properties}` |
| 26.3 | 配方 | 烹饪时间不再按方块区分（烟熏炉/高炉时间翻倍） |
| 26.3 | 严格加载 | 严格注册表里无法解析的 JSON 删除；引用失效的删除（或只剪掉奖励项）；进度里的未知字段移除 |

## 它不做什么

* **它不是数据包检查器**——只负责转换，不评价你的设计。
* **行为层面的变化它管不了**：`clickEvent` 的 `run_command` 对 `/say` 之类命令现在会弹确认框；
  `AngerTime` 是"剩余刻数"而 `anger_end_time` 是"绝对游戏时间"，程序只能写入
  `2147483647` 并逐条记录；`/time`、`/item`、`/fillbiome` 在"没有实际变化"时会失败，
  依赖其返回值的 `execute store result` 需要人工复核。这些都会列进报告。
* **历史遗留内容不动**：1.21 之前的复数目录名（`functions/`、`advancements/`、
  `loot_tables/`…）在 1.21.4 本来就不会被加载，程序原样保留并写进报告。
* **假设外来命名空间存在**：引用检查只解决包内能回答的问题，`minecraft:` 和包外命名空间一律视为存在。

## 工作方式

1. **复制**整包，跳过 `dist/`、`_upgrade/`、`_analysis/`、`__pycache__/`、`.git/`、
   `.idea/`、`.vscode/`、`node_modules/`、`upgrader*/`、`tests/`。
2. **按注册表分发**：每个 `.json` 按路径 `data/<命名空间>/<注册表>/…` 路由到对应转换器，
   `.mcfunction` 逐行走命令改写。
3. **替换区间而非整文件**：`snbt.py` 解析时记录每个值的源码区间，只改写真正变化的字节。
4. **独立自检**：`verify.py` 只读产物、不复用改写逻辑，专门发现转换器自身的错误。
5. **报告**：规则命中、文件、样例、警告、错误。

## 测试

```bash
python -m unittest discover -s tests -v      # 89 个测试，约 1 秒，无需磁盘夹具
python tools/check_repeatability.py <pack>   # 在真实包上验证确定性 + 幂等性
python tools/check_references.py <pack>      # 引用失效审计，可加 --delete
```

测试覆盖 SNBT 往返、每个转换器、JSON 格式契约，以及一个合成包的端到端流程。

## 仓库结构

```
.
├─ upgrader2/               # 主包
│  ├─ cli.py                #   参数解析
│  ├─ pipeline.py           #   遍历 + 分发 + 报告
│  ├─ version.py            #   目标版本与规则表（含出处）
│  ├─ snbt.py               #   保留源码区间的 SNBT 解析/序列化
│  ├─ commands.py           #   行级命令改写
│  ├─ nbt_rewrite.py        #   NBT 负载改写
│  ├─ text_component.py     #   JSON 文本组件 → NBT
│  ├─ entity_predicate.py   #   实体谓词              (26.2)
│  ├─ predicate.py          #   谓词                  (26.3)
│  ├─ item_modifier.py      #   物品修饰器            (26.3)
│  ├─ loot_table.py         #   战利品表              (26.3)
│  ├─ advancement.py        #   进度                  (26.3)
│  ├─ item_components.py    #   物品组件              (1.21.5 / 26.3)
│  ├─ integrity.py          #   跨文件引用检查
│  ├─ verify.py             #   独立自检
│  ├─ docs.py               #   报告渲染
│  └─ vanilla_items_26.3.txt#   26.3 物品注册表（ID 校验）
├─ tools/                   # 独立审计脚本
├─ tests/                   # unittest 测试集
├─ docs/RESEARCH-NOTES.md   # 逐版本调研笔记（含 Wiki 原文引用）
├─ RULES.md / RULES-CN.md   # 完整规则对照表（英文 / 中文）
├─ run_upgrade.cmd          # Windows 便捷入口
└─ README.md / README-CN.md
```

## 许可

MIT，见 [LICENSE](LICENSE)。
