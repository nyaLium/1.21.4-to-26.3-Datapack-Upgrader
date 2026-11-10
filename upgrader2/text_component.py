"""Text component migration (1.21.5).

From 1.21.5 text components are stored as NBT and the interactive fields were
renamed.  The same component tree appears in JSON data files (advancement
titles, item modifier ``set_name`` payloads, ...) and in command SNBT, so the
rewriter works on plain Python values and both callers share it.

Renames (English wiki, Text component format §History, 25w02a/25w03a):

* ``clickEvent`` -> ``click_event``; ``hoverEvent`` -> ``hover_event``
* click payload ``value`` -> ``command`` / ``url`` / ``path`` / ``page``
* hover ``show_text.contents`` -> ``value``
* hover ``show_item.contents`` inlined (``id``, ``count``, ``components``)
* hover ``show_entity.contents`` inlined (``id`` -> ``uuid``, ``type`` -> ``id``)
"""

from __future__ import annotations

import json
from typing import Any

COMPONENT_KEYS = {
    "text", "translate", "keybind", "score", "selector", "nbt", "extra",
    "clickEvent", "click_event", "hoverEvent", "hover_event", "insertion", "font",
}
CHILD_KEYS = {"extra", "with", "separator"}


def looks_like_component(value: Any) -> bool:
    if isinstance(value, list):
        return any(isinstance(item, dict) and looks_like_component(item) for item in value)
    if isinstance(value, dict):
        return bool(set(value) & COMPONENT_KEYS)
    return False


def rewrite(node: Any) -> tuple[Any, bool]:
    """Rewrite one component subtree."""
    if isinstance(node, list):
        changed = False
        out = []
        for item in node:
            new, ch = rewrite(item)
            out.append(new)
            changed = changed or ch
        return (out, True) if changed else (node, False)

    if not isinstance(node, dict):
        return node, False

    changed = False
    out: dict[str, Any] = {}
    for key, value in node.items():
        if key == "clickEvent":
            out["click_event"], ch = _click(value)
            changed = True
        elif key == "hoverEvent":
            out["hover_event"], ch = _hover(value)
            changed = True
        elif key in ("click_event", "hover_event"):
            fn = _click if key == "click_event" else _hover
            out[key], ch = fn(value)
            changed = changed or ch
        elif key in CHILD_KEYS:
            out[key], ch = rewrite(value)
            changed = changed or ch
        else:
            out[key] = value
    return (out, True) if changed else (node, False)


def rewrite_tree(node: Any) -> tuple[Any, bool]:
    """Rewrite components anywhere inside an arbitrary JSON document."""
    if isinstance(node, dict):
        current, changed = rewrite(node)
        out: dict[str, Any] = {}
        for key, value in current.items():
            if isinstance(value, (dict, list)):
                new, ch = rewrite_tree(value)
                out[key] = new
                changed = changed or ch
            else:
                out[key] = value
        return (out, True) if changed else (node, False)
    if isinstance(node, list):
        changed = False
        out = []
        for item in node:
            new, ch = rewrite_tree(item)
            out.append(new)
            changed = changed or ch
        return (out, True) if changed else (node, False)
    return node, False


def _click(event: Any) -> tuple[Any, bool]:
    if not isinstance(event, dict):
        return event, False
    action = event.get("action")
    out = dict(event)
    changed = False
    if "value" in out:
        value = out.pop("value")
        if action in ("run_command", "suggest_command"):
            out["command"] = value
        elif action == "open_url":
            out["url"] = value
        elif action == "open_file":
            out["path"] = value
        elif action == "change_page":
            if isinstance(value, str) and value.strip().lstrip("-").isdigit():
                value = int(value.strip())
            out["page"] = value
        else:
            out["value"] = value
            return event, False
        changed = True
    if action == "change_page" and isinstance(out.get("page"), str):
        page = out["page"].strip()
        if page.lstrip("-").isdigit():
            out["page"] = int(page)
            changed = True
    return (out, True) if changed else (event, False)


def _hover(event: Any) -> tuple[Any, bool]:
    if not isinstance(event, dict):
        return event, False
    action = event.get("action")
    out = dict(event)
    changed = False

    if action == "show_text" and "contents" in out:
        out["value"] = out.pop("contents")
        changed = True
    elif action == "show_item" and "contents" in out:
        contents = out.pop("contents")
        if isinstance(contents, dict):
            for key in ("id", "count", "components"):
                if key in contents:
                    out[key] = contents[key]
            if "tag" in contents:  # pre-1.20.5 spelling
                out["components"] = contents["tag"]
        elif isinstance(contents, str):
            out["id"] = contents
        changed = True
    elif action == "show_entity" and "contents" in out:
        contents = out.pop("contents")
        if isinstance(contents, dict):
            # old: {type: <entity type>, id: <uuid>} -> {id: <entity type>, uuid: <uuid>}
            if "id" in contents:
                out["uuid"] = contents["id"]
            if "type" in contents:
                out["id"] = contents["type"]
            elif "id" in contents and "uuid" not in contents:
                out["uuid"] = contents["id"]
            if "name" in contents:
                out["name"] = contents["name"]
        changed = True

    # show_entity pre-1.21.5 spelling living directly on the event
    if action == "show_entity":
        if "type" in out and "id" not in out:
            out["id"] = out.pop("type")
            changed = True
        if "id" in out and "uuid" not in out and isinstance(out["id"], list):
            out["uuid"] = out.pop("id")
            changed = True
    return (out, True) if changed else (event, False)


# ---------------------------------------------------------------------------
# JSON-string components (the pre-1.21.5 storage form)
# ---------------------------------------------------------------------------

def from_json_string(value: Any) -> tuple[Any, bool]:
    """``'{"text":"Hi"}'`` -> ``{"text":"Hi"}`` (rewritten), else unchanged."""
    if not isinstance(value, str):
        return value, False
    text = value.strip()
    if not (text.startswith("{") or text.startswith("[")):
        return value, False
    try:
        parsed = json.loads(text)
    except Exception:
        return value, False
    if not looks_like_component(parsed):
        return value, False
    new, _ = rewrite(parsed)
    return new, True


def convert_strings(node: Any) -> tuple[Any, bool]:
    """Inline JSON-string components anywhere in a JSON document."""
    if isinstance(node, dict):
        changed = False
        out: dict[str, Any] = {}
        for key, value in node.items():
            if isinstance(value, str):
                new, ch = from_json_string(value)
                if ch:
                    new, _ = rewrite_tree(new)
                    out[key] = new
                    changed = True
                else:
                    out[key] = value
            else:
                new, ch = convert_strings(value)
                out[key] = new
                changed = changed or ch
        return (out, True) if changed else (node, False)
    if isinstance(node, list):
        changed = False
        out = []
        for value in node:
            new, ch = convert_strings(value)
            out.append(new)
            changed = changed or ch
        return (out, True) if changed else (node, False)
    return node, False

def inline_value(value: Any) -> Any:
    """Deep-convert JSON-string components inside a component-valued field.

    Handles ``'{"text":"x"}'``, ``['{"text":"a"}', ...]``, book pages
    (``{raw: '{"translate": ...}'}``) and plain JSON strings (``'""'``).
    """
    if isinstance(value, str):
        new, changed = from_json_string(value)
        if changed:
            return rewrite_tree(new)[0]
        stripped = value.strip()
        if stripped[:1] == '"':
            parsed = _json_loads(stripped)
            if isinstance(parsed, str):
                return parsed
        return value
    if isinstance(value, list):
        return [inline_value(item) for item in value]
    if isinstance(value, dict):
        out = {key: inline_value(item) for key, item in value.items()}
        return rewrite_tree(out)[0]
    return value

def _json_loads(text: str) -> Any:
    try:
        return json.loads(text)
    except Exception:
        return None

