"""
snapshot_formats - 快照格式化器
把 PageSnapshot.to_dict() 数据格式化为不同风格的文本：
    interactive(默认) / compact / aria / ai
"""

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class FormatOptions:
    """格式化选项"""

    format: str = "interactive"
    max_chars: int = 50000


def format_snapshot(snapshot: Dict[str, Any], options: FormatOptions) -> str:
    """按 options.format 格式化快照 dict，返回文本"""
    fmt = options.format
    if fmt == "compact":
        text = _format_compact(snapshot)
    elif fmt == "aria":
        text = _format_aria(snapshot)
    elif fmt == "ai":
        text = _format_ai(snapshot)
    else:
        text = _format_interactive(snapshot)

    if options.max_chars and len(text) > options.max_chars:
        text = text[: options.max_chars] + "\n...[truncated]"
    return text


# ========================================================================
# 各格式实现
# ========================================================================


def _format_interactive(snapshot: Dict[str, Any]) -> str:
    """默认：可交互元素列表 + 文本摘要"""
    lines: List[str] = []
    url = snapshot.get("url", "")
    title = snapshot.get("title", "")
    if url:
        lines.append(f"URL: {url}")
    if title:
        lines.append(f"Title: {title}")
    lines.append("")

    elements = snapshot.get("interactive_elements", [])
    if elements:
        lines.append("Interactive elements:")
        for el in elements:
            parts = [f"[{el.get('ref')}] <{el.get('tag')}>"]
            if el.get("text"):
                parts.append(f'"{el["text"]}"')
            if el.get("type"):
                parts.append(f"type={el.get('type')}")
            if el.get("role"):
                parts.append(f"role={el.get('role')}")
            lines.append(" ".join(parts))
    else:
        lines.append("(no interactive elements)")

    summary = snapshot.get("visible_text_summary", "")
    if summary:
        lines.append("")
        lines.append(f"Text: {summary[:1000]}")

    return "\n".join(lines)


def _format_compact(snapshot: Dict[str, Any]) -> str:
    """紧凑：每元素一行，无空格浪费"""
    lines: List[str] = []
    url = snapshot.get("url", "")
    if url:
        lines.append(url)
    for el in snapshot.get("interactive_elements", []):
        tag = el.get("tag", "")
        text = (el.get("text") or "").replace("\n", " ")
        ref = el.get("ref", "")
        if text:
            lines.append(f"{ref}|{tag}|{text}")
        else:
            lines.append(f"{ref}|{tag}")
    return "\n".join(lines)


def _format_aria(snapshot: Dict[str, Any]) -> str:
    """ARIA 风格：带 role/label 语义树"""
    lines: List[str] = []
    url = snapshot.get("url", "")
    title = snapshot.get("title", "")
    if url:
        lines.append(f"URL: {url}")
    if title:
        lines.append(f"Title: {title}")
    lines.append("")

    for el in snapshot.get("interactive_elements", []):
        ref = el.get("ref", "")
        tag = el.get("tag", "")
        role = el.get("role") or _default_role(tag)
        label = el.get("text") or el.get("type") or ""
        lines.append(f"[{ref}] role={role} label=\"{label}\"")
    return "\n".join(lines)


def _format_ai(snapshot: Dict[str, Any]) -> str:
    """AI 风格：JSON 紧凑呈现，便于 LLM 解析"""
    elements = snapshot.get("interactive_elements", [])
    compact_elements = [
        {
            "ref": el.get("ref"),
            "tag": el.get("tag"),
            "text": el.get("text", ""),
            "type": el.get("type", ""),
            "href": el.get("href", ""),
        }
        for el in elements
    ]
    import json

    return json.dumps(
        {
            "url": snapshot.get("url", ""),
            "title": snapshot.get("title", ""),
            "elements": compact_elements,
        },
        ensure_ascii=False,
        indent=2,
    )


def _default_role(tag: str) -> str:
    """根据 tag 推断默认 role"""
    roles = {
        "a": "link",
        "button": "button",
        "input": "textbox",
        "select": "combobox",
        "textarea": "textbox",
    }
    return roles.get(tag, "widget")


__all__ = ["FormatOptions", "format_snapshot"]
