"""
SnapshotExtractor - 轻量快照提取器
只提取交互元素，节省 90% token（对比全文本快照）
"""

import time
from typing import Any, Dict, List

from ..models.schemas import PageSnapshot

# JS 脚本：提取可交互元素并打上 data-hyperbrowser-ref
_EXTRACT_INTERACTIVE_JS = """
() => {
    const selectors = [
        'a', 'button', 'input', 'select', 'textarea',
        '[role="button"]', '[role="link"]', '[role="checkbox"]',
        '[role="radio"]', '[role="tab"]', '[onclick]'
    ];
    const seen = new Set();
    const results = [];
    let refCounter = 0;

    for (const sel of selectors) {
        const nodes = document.querySelectorAll(sel);
        for (const el of nodes) {
            if (seen.has(el)) continue;
            seen.add(el);

            const rect = el.getBoundingClientRect();
            if (rect.width < 2 || rect.height < 2) continue;

            const ref = 'ref_' + refCounter++;
            el.setAttribute('data-hyperbrowser-ref', ref);

            const tag = el.tagName.toLowerCase();
            const text = (
                (el.innerText || el.value || el.getAttribute('placeholder')
                 || el.getAttribute('aria-label') || '').trim().slice(0, 120)
            );
            const type = el.getAttribute('type') || '';
            const role = el.getAttribute('role') || '';
            const href = el.getAttribute('href') || '';
            const cls = el.getAttribute('class') || '';
            const aria_disabled = el.getAttribute('aria-disabled') || '';

            results.push({
                ref: ref,
                tag: tag,
                text: text,
                type: type,
                role: role,
                href: href,
                class: cls,
                aria_disabled: aria_disabled
            });
        }
    }
    return results;
}
"""

_TEXT_SUMMARY_JS = """
() => {
    if (!document.body) return '';
    const text = document.body.innerText || '';
    return text.replace(/\\s+/g, ' ').trim().slice(0, 2000);
}
"""


class SnapshotExtractor:
    """提取页面交互元素快照（供 LLM 定位元素）"""

    def __init__(self, page):
        self.page = page

    async def extract(self) -> PageSnapshot:
        """提取当前页面快照"""
        url = self.page.url
        title = ""
        try:
            title = await self.page.title()
        except Exception:
            title = ""

        interactive_elements: List[Dict[str, Any]] = []
        try:
            interactive_elements = await self.page.evaluate(_EXTRACT_INTERACTIVE_JS)
        except Exception:
            interactive_elements = []

        visible_text_summary = ""
        try:
            visible_text_summary = await self.page.evaluate(_TEXT_SUMMARY_JS)
        except Exception:
            visible_text_summary = ""

        return PageSnapshot(
            url=url,
            title=title,
            interactive_elements=interactive_elements,
            visible_text_summary=visible_text_summary,
            timestamp=time.time(),
        )

    def format_for_llm(self, snapshot: PageSnapshot) -> str:
        """格式化快照，供 LLM 生成操作序列"""
        lines: List[str] = []
        lines.append(f"URL: {snapshot.url}")
        if snapshot.title:
            lines.append(f"Title: {snapshot.title}")
        lines.append("")

        if snapshot.interactive_elements:
            lines.append("Interactive elements:")
            for el in snapshot.interactive_elements:
                parts = [f"[{el.get('ref')}] <{el.get('tag')}>"]
                if el.get("text"):
                    parts.append(f"\"{el['text']}\"")
                if el.get("type"):
                    parts.append(f"type={el.get('type')}")
                if el.get("role"):
                    parts.append(f"role={el.get('role')}")
                lines.append(" ".join(parts))
        else:
            lines.append("(no interactive elements found)")

        if snapshot.visible_text_summary:
            lines.append("")
            lines.append(f"Text: {snapshot.visible_text_summary[:500]}")

        return "\n".join(lines)


__all__ = ["SnapshotExtractor"]
