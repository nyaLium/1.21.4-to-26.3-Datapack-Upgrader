# Minecraft Data Pack Upgrader — 1.21.4 → 26.3

Upgrade a **Minecraft Java Edition data pack** from **1.21.4** (pack format 61) to **26.3**
(data pack format 121.0), across the six breaking releases in between, and get a
per-rule / per-file change report you can audit.

* **No dependencies.** Pure Python standard library, nothing to `pip install`.
* **Deterministic.** The same input produces byte-identical output every time.
* **Idempotent.** Running the tool on its own output fires zero rules.
* **Surgical.** Only the SNBT fragments that actually change are replaced — comments,
  macros, CRLF, BOM and untouched files stay byte-identical.
* **Traceable.** Every rule carries the Minecraft Wiki section it was derived from, and
  the report cites it next to each hit.

中文说明：[README-CN.md](README-CN.md) · 中文规则表：[RULES-CN.md](RULES-CN.md)

---

## Why this exists

The road from 1.21.4 to 26.3 is paved with breaking changes that are easy to miss:

| Release | What broke |
| --- | --- |
| 1.21.5 | Text components became NBT; `ArmorItems` / `HandItems` became `equipment`; item components gained simplified forms |
| 1.21.9 | `pack.mcmeta` needs `min_format` / `max_format`; `particle flash` requires a colour |
| 1.21.11 | Game rules became namespaced registry ids |
| 26.2 | Entity predicates use namespaced keys |
| 26.3 | `condition` → `type`, `function` → `type`, `functions` → `modifier`, block states `Name` → `id`, advancement background rules… |

And since 26.3, **one unparseable or dangling JSON file makes the game refuse to load the
whole world** (Mojira MC-310325, closed as "works as intended"). Fixing a large pack by
hand is not really an option.

## Requirements

* **Python 3.10 or newer** (tested on 3.12) — nothing else.
* Windows, macOS or Linux.

## Quick start

```bash
git clone https://github.com/<user>/<repo>.git
cd <repo>

python -m upgrader2 "path/to/MyPack"
# => ./dist/MyPack-26.3/
```

On Windows you can also drag the pack folder onto **`run_upgrade.cmd`**, or run it with
arguments:

```bat
run_upgrade.cmd "D:\packs\MyPack"
run_upgrade.cmd "D:\packs\MyPack" "D:\out\MyPack-26.3"
```

Always upgrade a **copy**. The tool never writes into the source directory, but keeping
your original untouched is the point of a repeatable conversion.

## Command line

```
python -m upgrader2 SOURCE [-o OUTPUT] [--force] [--quiet] [--keep-dangling]
```

| Option | Meaning |
| --- | --- |
| `SOURCE` | Data pack directory — must contain `pack.mcmeta` and `data/` |
| `-o, --output` | Destination directory. Default: `./dist/<pack-name>-26.3` |
| `--force` | Overwrite the destination if it already exists (it is deleted first) |
| `--quiet` | Only print errors |
| `--keep-dangling` | Keep JSON files whose cross-file references do not resolve, instead of deleting them (see below) |

The tool exits with `0` when it finished without errors and `1` when the report contains
errors (for example a `pack.mcmeta` that is not valid JSON), so it can be used in a
script. `--quiet` does not change the exit code.

Typical console output:

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

## What you get

The output is a **full copy of the pack** with the converted files in place:

```
MyPack-26.3/
├─ pack.mcmeta              # rewritten: min_format / max_format = [121, 0]
├─ data/                    # converted data files (untouched ones copied verbatim)
└─ _upgrade/
   ├─ report.md             # human-readable report (Chinese)
   ├─ report.en.md          # the same report in English
   └─ report.json           # machine-readable: rule × file × sample
```

`report.json` is machine-readable and stable:

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

The same report is written twice — `report.md` in Chinese and `report.en.md` in English —
so no flag is needed and nobody has to read a second language. `report.json` holds the
same data; the rule ids and the file paths are language-neutral.

## What it upgrades

34 rules, each anchored to the release that introduced the change. Full before/after
tables with Wiki citations: **[RULES.md](RULES.md)** (English) /
**[RULES-CN.md](RULES-CN.md)** (Chinese); raw research log, including the parts marked
*UNVERIFIED*: **[docs/RESEARCH-NOTES.md](docs/RESEARCH-NOTES.md)**.

| Release | Area | What changes |
| --- | --- | --- |
| 1.21.5 | Text components | JSON strings inside NBT/commands become inline NBT; `clickEvent`/`hoverEvent` renamed, payload fields renamed, `contents` inlined |
| 1.21.5 | Entity NBT | `ArmorItems`, `HandItems`, `body_armor_item` → `equipment`; drop chances → `drop_chances`; `Inventory[{Slot:100b…}]` → equipment slots |
| 1.21.5 | Item components | Simplified forms (`enchantments.levels`, `attribute_modifiers.modifiers`, `dyed_color.rgb`, `can_place_on.predicates`…), `hide_tooltip`/`show_in_tooltip` → `tooltip_display` |
| 1.21.9 | `pack.mcmeta` | `pack_format` → `min_format` / `max_format` (`[121, 0]`) |
| 1.21.9 | Particles | `particle flash` requires `color`; opaque white is inserted |
| 1.21.9 | Ids | Renamed block/item ids (`minecraft:chain` → `minecraft:iron_chain`) |
| 1.21.11 | Game rules | camelCase → namespaced ids (`doMobLoot` → `minecraft:mob_drops`, three rules inverted) |
| 26.2 | Entity predicates | Namespaced keys, `type` → `minecraft:entity_type`, `type_specific/<kind>` flattened |
| 26.2 | Entity NBT | Renamed fields (`HurtByTimestamp` → `ticks_since_last_hurt_by_mob`, …) |
| 26.3 | Predicates | `condition` → `type`, predicate lists → `all_of`, `block_state_property` → `match_block` |
| 26.3 | Item modifiers | `function` → `type`, root arrays → `minecraft:sequence` |
| 26.3 | Loot tables | `functions` → `modifier`, `conditions` → `condition`, tag entries `name` → `items` |
| 26.3 | Advancements | Background rules (required on displayed roots, forbidden elsewhere, `textures/` and `.png` dropped), trigger fields (`recipe` → `recipes`, …), `player` as a single predicate |
| 26.3 | Block states | `{Name, Properties}` → `{id, properties}` |
| 26.3 | Recipes | Cooking times no longer differ per block (smoker/blast furnace doubled) |
| 26.3 | Strictness | Unparseable JSON in a strict registry is deleted; dangling references are deleted (or their reward entry trimmed); unknown advancement fields removed |

## What it does not do

* **It is not a datapack linter.** It converts, it does not judge your design.
* **Behavioural changes are out of reach.** `clickEvent` → `run_command` now asks for
  confirmation on `/say`-style commands; `AngerTime` is a countdown while
  `anger_end_time` is an absolute tick, so the tool writes `2147483647` and records every
  occurrence; `/time`, `/item`, `/fillbiome` now fail when nothing changes, which breaks
  `execute store result` chains that relied on the old return value. These are listed in
  the report for manual review.
* **Legacy content is left alone.** Directories with pre-1.21 plural names (`functions/`,
  `advancements/`, `loot_tables/`…) were already ignored by 1.21.4; they are copied as-is
  and listed in the report.
* **Custom namespaces are assumed to exist.** Reference checking resolves what the pack
  itself can answer; anything in `minecraft:` or a namespace outside the pack is trusted.

## How it works

1. **Copy** the pack, skipping `dist/`, `_upgrade/`, `_analysis/`, `__pycache__/`, `.git/`,
   `.idea/`, `.vscode/`, `node_modules/`, `upgrader*/`, `tests/`.
2. **Dispatch by registry** — every `.json` file is routed by its path
   (`data/<ns>/<registry>/…`) to a dedicated converter; function lines go through a
   command-level rewriter.
3. **Replace spans, not files** — `snbt.py` parses SNBT while recording the source span of
   every value, so a rewrite replaces only the bytes whose value actually changed.
4. **Verify** — `verify.py` re-reads the output on its own (it does not reuse the rewrite
   logic) and reports anything the converter could not safely convert.
5. **Report** — rule hits, files, samples, warnings, errors.

## Tests

```bash
python -m unittest discover -s tests -v      # 89 tests, ~1 s, no fixtures on disk
python tools/check_repeatability.py <pack>   # determinism + idempotency on a real pack
python tools/check_references.py <pack>      # dangling-reference audit, optional --delete
```

The suite covers the SNBT round-trip, every converter, the JSON formatting contract and an
end-to-end pipeline run on a synthetic pack.

## Repository layout

```
.
├─ upgrader2/               # the package
│  ├─ cli.py                #   argument parsing
│  ├─ pipeline.py           #   walk + dispatch + report
│  ├─ version.py            #   target version and the rule table (with sources)
│  ├─ snbt.py               #   span-preserving SNBT parser/serialiser
│  ├─ commands.py           #   line-level command rewriting
│  ├─ nbt_rewrite.py        #   NBT payload rewriting
│  ├─ text_component.py     #   JSON text components → NBT
│  ├─ entity_predicate.py   #   entity predicates          (26.2)
│  ├─ predicate.py          #   predicates                (26.3)
│  ├─ item_modifier.py      #   item modifiers            (26.3)
│  ├─ loot_table.py         #   loot tables               (26.3)
│  ├─ advancement.py        #   advancements              (26.3)
│  ├─ item_components.py    #   item components           (1.21.5 / 26.3)
│  ├─ integrity.py          #   cross-file reference checks
│  ├─ verify.py             #   independent output lint
│  ├─ docs.py               #   report rendering
│  └─ vanilla_items_26.3.txt#   26.3 item registry (id sanity checks)
├─ tools/                   # standalone audits
├─ tests/                   # unittest suite
├─ docs/RESEARCH-NOTES.md   # per-release research log with Wiki quotes
├─ RULES.md / RULES-CN.md   # full before/after rule reference (English / Chinese)
├─ run_upgrade.cmd          # Windows convenience wrapper
└─ README.md / README-CN.md
```

## License

MIT — see [LICENSE](LICENSE).
