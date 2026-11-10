"""Markdown report rendering (English and Chinese).

The pipeline writes both `report.md` (Chinese) and `report.en.md` (English) from the
same `Report`, so a reader picks whichever they prefer and no extra flag is needed.
"""

from __future__ import annotations

from .report import Report
from .version import RULES, TARGET_PACK_VERSION

MESSAGES: dict[str, dict[str, str]] = {
    "zh": {
        "title": "# 数据包升级报告：1.21.4 → 26.3\n",
        "source": "- 源目录：`{}`",
        "destination": "- 目标目录：`{}`",
        "target": ("- 目标数据包版本：`{}`"
                   "（`pack.mcmeta` 的 `min_format` / `max_format`）"),
        "scanned": "- 扫描文件：{}，函数行：{}\n",
        "rules_heading": "\n## 规则命中统计\n",
        "rules_header": "| 规则 | 说明 | 次数 | 文件数 | 依据 |",
        "paren_l": "（",
        "paren_r": "）",
        "lint_heading": "\n## 升级后自检\n",
        "lint_some": ("自检发现 **{}** 处未自动转换、需要人工确认的位置"
                      "（通常是源文件里本来就无法解析的命令，程序无法安全改写）：\n"),
        "lint_ok": "未发现 26.3 会拒绝的残留语法。\n",
        "lint_stats": "自检统计：",
        "removed_heading": "\n## 因引用失效/无法解析而删除的 JSON\n",
        "removed_intro": (
            "26.3 起，`advancement`、`loot_table`、`recipe`、`predicate`、`item_modifier`、"
            "`number_provider`、`slot_source` 中任意一个文件出错，游戏会**拒绝加载整个世界**"
            "（Mojira MC-310325，官方标记为“按设计如此”），而不是像旧版本那样只跳过该文件。"
            "下列文件内部的引用在包内找不到目标（或文件无法解析），又无法凭空补出对应内容，"
            "因此已删除：\n"),
        "repaired_heading": "\n## 保留但移除了失效奖励的 JSON\n",
        "repaired_intro": (
            "这些 advancement 仍有意义（例如被函数用 `advancement grant` 授予），"
            "只是 `rewards` 里指向了不存在的目标；程序删掉出错的那一项，文件本身保留：\n"),
        "warn_heading": "\n## 需要人工复核的警告\n",
        "error_heading": "\n## 错误\n",
        "dead_heading": "\n## 未被 1.21.4 加载的历史内容（原样保留）\n",
        "dead_intro": (
            "这些目录使用 1.21 之前的复数目录名或未知注册表，1.21.4 本来就不会加载；"
            "升级程序保留原文件，不做转换。\n"),
        "limits_heading": "\n## 已知无法自动转换的内容\n",
        "limit_1": ("- `AngerTime` 是「剩余刻数」，26.x 的 `anger_end_time` 是「绝对游戏时间」；"
                    "静态转换无法得知世界时间，程序写入 2147483647（近似永久愤怒）并逐条记录。"),
        "limit_2": ("- 1.21.9 起 `clickEvent` 的 `run_command` 对 `/say`、`/msg` 等聊天命令会先弹确认框；"
                    "这是行为变化，语法转换无法规避。"),
        "limit_3": ("- 26.3 起 `/time`、`/item`、`/fillbiome` 在「没有产生实际变化」时会执行失败；"
                    "依赖这些命令返回值的 `execute store result` 需要复核。"),
        "limit_4": ("- `execute if entity` / `execute store result` 等命令的返回值语义在 26.3 有变化"
                    "（部分命令改为返回实际受影响数量）。"),
    },
    "en": {
        "title": "# Data pack upgrade report: 1.21.4 -> 26.3\n",
        "source": "- Source: `{}`",
        "destination": "- Destination: `{}`",
        "target": "- Target data pack format: `{}` (`min_format` / `max_format` in `pack.mcmeta`)",
        "scanned": "- Files scanned: {}, function lines: {}\n",
        "rules_heading": "\n## Rule hits\n",
        "rules_header": "| Rule | Description | Hits | Files | Source |",
        "paren_l": " (",
        "paren_r": ")",
        "lint_heading": "\n## Post-upgrade self-check\n",
        "lint_some": ("The self-check found **{}** place(s) that were not converted automatically "
                      "and need a human (usually commands the program cannot rewrite safely):\n"),
        "lint_ok": "No syntax that 26.3 would reject was found.\n",
        "lint_stats": "Self-check counters: ",
        "removed_heading": "\n## JSON files deleted because a reference is broken or the file does not parse\n",
        "removed_intro": (
            "Since 26.3 a single bad file in `advancement`, `loot_table`, `recipe`, `predicate`, "
            "`item_modifier`, `number_provider` or `slot_source` makes the game **refuse to load the "
            "whole world** (Mojira MC-310325, closed as \"works as intended\") instead of skipping just "
            "that file. The files below point at targets that do not exist inside the pack (or cannot "
            "be parsed) and cannot be repaired automatically, so they were deleted:\n"),
        "repaired_heading": "\n## JSON files kept, with the broken reward entry removed\n",
        "repaired_intro": (
            "These advancements still serve a purpose (functions often grant them with "
            "`advancement grant`); only an entry in `rewards` pointed at a missing target, so that "
            "entry was dropped and the file kept:\n"),
        "warn_heading": "\n## Warnings that need a human\n",
        "error_heading": "\n## Errors\n",
        "dead_heading": "\n## Historical content that 1.21.4 never loaded (copied verbatim)\n",
        "dead_intro": (
            "These directories use pre-1.21 plural folder names or unknown registries, which 1.21.4 "
            "already ignored. The upgrader copies them unchanged.\n"),
        "limits_heading": "\n## Known limits of the automatic conversion\n",
        "limit_1": ("- `AngerTime` is a countdown while 26.x `anger_end_time` is an absolute game "
                    "time. A static conversion cannot know the world time, so the program writes "
                    "2147483647 (effectively permanent anger) and records every occurrence."),
        "limit_2": ("- Since 1.21.9, `clickEvent` `run_command` asks for confirmation on chat "
                    "commands such as `/say` and `/msg`. That is a behaviour change no syntax "
                    "rewrite can avoid."),
        "limit_3": ("- Since 26.3, `/time`, `/item` and `/fillbiome` fail when they change nothing, "
                    "which breaks `execute store result` chains that relied on the old return value. "
                    "Review those by hand."),
        "limit_4": ("- Return values of commands such as `execute if entity` / `execute store result` "
                    "changed in 26.3 (several commands now report the affected count)."),
    },
}


def render_markdown(src: str, dst: str, report: Report, dead, issues, stats,
                    removed=(), repaired=(), lang: str = "zh") -> str:
    msg = MESSAGES.get(lang, MESSAGES["zh"])
    rules = {rule.ident: rule for rule in RULES}
    by_rule = report.by_rule()
    files_by_rule = report.files_by_rule()

    lines: list[str] = []
    lines.append(msg["title"].rstrip("\n"))
    lines.append("")
    lines.append(msg["source"].format(src))
    lines.append(msg["destination"].format(dst))
    lines.append(msg["target"].format(f"{TARGET_PACK_VERSION[0]}.{TARGET_PACK_VERSION[1]}"))
    lines.append(msg["scanned"].format(report.files_scanned, report.function_lines).rstrip("\n"))

    lines.append(msg["rules_heading"].rstrip("\n"))
    lines.append("")
    lines.append(msg["rules_header"])
    lines.append("| --- | --- | ---: | ---: | --- |")
    for ident, count in by_rule.items():
        rule = rules.get(ident)
        title = rule.title if rule else ident
        source = rule.source if rule else ""
        since = rule.since if rule else ""
        lines.append(
            f"| `{ident}` | {title} | {count} | {files_by_rule.get(ident, 0)} | "
            f"{source}{msg['paren_l']}{since}{msg['paren_r']} |"
        )

    lines.append(msg["lint_heading"].rstrip("\n"))
    if issues:
        lines.append(msg["lint_some"].format(len(issues)).rstrip("\n"))
        for issue in issues[:200]:
            lines.append(f"- {issue}")
        if len(issues) > 200:
            lines.append(f"- ... {len(issues) - 200} more, see `report.json`")
    else:
        lines.append(msg["lint_ok"].rstrip("\n"))
    if stats:
        lines.append(msg["lint_stats"] + "、".join(
            f"`{key}`={value}" for key, value in sorted(stats.items())))

    if removed:
        lines.append(msg["removed_heading"].rstrip("\n"))
        lines.append(msg["removed_intro"].rstrip("\n"))
        for path, reason in removed:
            lines.append(f"- `{path}` - {reason}")

    if repaired:
        lines.append(msg["repaired_heading"].rstrip("\n"))
        lines.append(msg["repaired_intro"].rstrip("\n"))
        for path, reason in repaired:
            lines.append(f"- `{path}` - {reason}")

    if report.warnings:
        lines.append(msg["warn_heading"].rstrip("\n"))
        for warning in report.warnings[:300]:
            lines.append(f"- {warning}")
        if len(report.warnings) > 300:
            lines.append(f"- ... {len(report.warnings) - 300} more, see `report.json`")

    if report.errors:
        lines.append(msg["error_heading"].rstrip("\n"))
        for error in report.errors:
            lines.append(f"- {error}")

    if dead:
        lines.append(msg["dead_heading"].rstrip("\n"))
        lines.append(msg["dead_intro"].rstrip("\n"))
        for namespace, sub, count in dead:
            lines.append(f"- `data/{namespace}/{sub}` ({count} files)")

    lines.append(msg["limits_heading"].rstrip("\n"))
    for key in ("limit_1", "limit_2", "limit_3", "limit_4"):
        lines.append(msg[key])
    lines.append("")
    return "\n".join(lines)
