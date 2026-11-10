"""Particle option migrations for the 1.21.4 -> 26.3 upgrade.

Only one particle type changed its *required* command options in that window:

* 1.21.9 (25w36a) made the ``flash`` particle require a ``color`` parameter
  (ARGB).  A 1.21.4 command could name the particle bare::

      particle flash ~ ~ ~ 0 0 0 0 1 force @s

  ``color`` is either a list of four floats in ``0.0..1.0`` (red, green, blue,
  alpha) or a packed ARGB integer.  In 1.21.4 ``flash`` had no option at all
  and was drawn with the default white tint, so the migration inserts opaque
  white ``color:[1.0,1.0,1.0,1.0]`` - the same look, now spelled out.

Everything else that changed is optional and therefore needs no rewrite:

* 1.21.5 (25w04a) gave ``tinted_leaves`` a ``color`` parameter - it is not
  required and the pack never uses the type.
* 1.21.9 added ``power`` to ``dragon_breath`` and optional ``power``/``color``
  to ``effect``/``instant_effect``.
* 26.2 added the ``geyser_base`` / ``geyser_poof`` / ``geyser_plume`` types.

Source: Minecraft Wiki, Particle format (History 1.21.5/25w04a and
1.21.9/25w36a) and Java Edition 1.21.9 section Particles.
"""

from __future__ import annotations

import re
from typing import Any

from . import snbt

#: particle type (short name) -> option fields that must be present, with the
#: default value used when the command omits them.
REQUIRED_OPTIONS: dict[str, dict[str, Any]] = {
    "flash": {"color": [1.0, 1.0, 1.0, 1.0]},
}

_PARTICLE = re.compile(
    r"(?<![A-Za-z0-9_:])particle\s+(?P<name>(?:[a-z0-9_.-]+:)?[a-z0-9_./-]+)"
)


def upgrade(line: str, ctx, path: str) -> str:
    """Add the mandatory 26.3 options to any ``particle`` command on *line*."""
    masked = _mask_strings(line)
    matches = list(_PARTICLE.finditer(masked))
    for match in reversed(matches):
        if not _at_command_start(line, match.start()):
            continue
        name = match.group("name")
        short = name.split(":")[-1]
        required = REQUIRED_OPTIONS.get(short)
        if required is None:
            continue
        line = _upgrade_one(line, match, short, required, ctx, path)
    return line


def _at_command_start(line: str, start: int) -> bool:
    """True when ``particle`` begins a command (start of line or after ``run``).

    Without this guard ``say particle flash`` (a chat message, not a command)
    would be rewritten.
    """
    prefix = line[:start].rstrip()
    if prefix in ("", "/", "$"):
        return True
    return prefix.rsplit(None, 1)[-1] == "run"


def _mask_strings(line: str) -> str:
    """Blank out quoted strings so ``particle`` inside text is not matched."""
    out = list(line)
    i, n = 0, len(line)
    while i < n:
        char = line[i]
        if char in "'\"":
            j = _skip_string(line, i)
            for k in range(i, min(j, n)):
                out[k] = " "
            i = j
            continue
        i += 1
    return "".join(out)


def _upgrade_one(line: str, match: "re.Match[str]", short: str,
                 required: dict[str, Any], ctx, path: str) -> str:
    name_end = match.end()
    pos = name_end
    n = len(line)
    while pos < n and line[pos] in " \t":
        pos += 1

    if pos >= n or line[pos] != "{":
        # Bare particle name: insert the whole option compound right after it.
        body = _compound(required)
        ctx.change("particle.flash_color", path,
                   f"particle {short} -> particle {short}{body}")
        return line[:name_end] + body + line[name_end:]

    end = _matching(line, pos)
    if end is None:
        return line
    node = snbt.try_parse(line, pos, allow_bare=True)
    if node is None or node.end != end + 1:
        return line
    options = node.to_py()
    if not isinstance(options, dict):
        return line
    missing = [key for key in required if key not in options]
    if not missing:
        return line

    if not options:
        # ``flash{}`` -> ``flash{color:[...]}``
        body = _compound(required)
        ctx.change("particle.flash_color", path,
                   f"particle {short}{{}} -> particle {short}{body}")
        return line[:pos] + body + line[end + 1:]

    insertion = ",".join(
        f"{key}:{snbt.dumps(required[key])}" for key in missing
    ) + ","
    ctx.change("particle.flash_color", path,
               f"particle {short} options gain {', '.join(missing)}")
    return line[:pos + 1] + insertion + line[pos + 1:]


def _compound(fields: dict[str, Any]) -> str:
    return "{" + ",".join(f"{key}:{snbt.dumps(value)}" for key, value in fields.items()) + "}"


def _matching(text: str, start: int) -> int | None:
    pairs = {"{": "}", "[": "]"}
    stack: list[str] = []
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
