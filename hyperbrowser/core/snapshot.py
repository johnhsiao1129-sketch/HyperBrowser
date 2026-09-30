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
        '[role="radio"]', '[role="tab"]', '[onclick]',
        // 2026-08-12: 扩展覆盖 contenteditable/ARIA 可交互/可聚焦元素
        // 根因: Boss chat composer 是 <div contenteditable="true" class="chat-input">,
        // 旧选择器全部漏掉 → snapshot 永远不返 ref → 消费方 _boss_find_real_ref
        // 按 class_contains="chat-input" 匹配恒 False
        '[contenteditable="true"]', '[contenteditable=""]',
        '[role="textbox"]', '[role="combobox"]', '[tabindex]'
    ];

    // 2026-08-19: hasEventListener 启发式 — 通用
    // 动机: 部分平台列表项（如 Vue 2 列表 / React 列表）使用 _vei / __reactProps$
    //     内部事件对象绑定，外部观察不到 onclick / tabindex / role
    //     通过静态 on* 属性 + Vue/React 框架元数据 + 父级 3 层 ancestor 启发式
    // 验证: BOSS 平台实测 li 没有任何标记 (vue2/vue3/react/angular/on*/_)
    //     → BOSS 抓不到；Vue 2/React 平台有效
    function hasEventListener(el) {
        // 1. 静态 on* 属性 (onclick / onmousedown / onpointerdown ...)
        if (el.attributes) {
            for (const attr of el.attributes) {
                if (/^on/i.test(attr.name)) return true;
            }
        }
        // 2. 框架元数据 (Vue 2 __vueParentComponent / _vei / __vue__ /
        //                Vue 3 __vnode / __vue_app__ /
        //                React __reactProps$ / __reactInternalInstance$)
        const keys = Object.keys(el);
        for (const key of keys) {
            if (key.startsWith('__vue') || key.startsWith('_v') || key.startsWith('__react')) return true;
        }
        return false;
    }

    // 父级 3 层 ancestor 启发式 — 捕获事件委托
    function hasEventListenerInChain(el, maxDepth = 3) {
        let cur = el.parentElement;
        for (let i = 0; i < maxDepth && cur; i++) {
            if (hasEventListener(cur)) return true;
            cur = cur.parentElement;
        }
        return false;
    }

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

    // 2026-08-19: 列表项事件委托检测 — 抓 [role="listitem"] 列表项
    // 触发条件: 自身或 3 层 ancestor 有 listener（hasEventListener + hasEventListenerInChain）
    // 覆盖范围: Vue 2 _vei / React __reactProps$ 等
    // 已知缺口: BOSS 平台实测无任何标记 → 抓不到，需要其他方案（参考 BOSS 精确 selector）
    const listItems = document.querySelectorAll('[role="listitem"]');
    for (const li of listItems) {
        if (seen.has(li)) continue;
        if (!hasEventListener(li) && !hasEventListenerInChain(li, 3)) continue;

        seen.add(li);
        const rect = li.getBoundingClientRect();
        if (rect.width < 2 || rect.height < 2) continue;

        const ref = 'ref_' + refCounter++;
        li.setAttribute('data-hyperbrowser-ref', ref);

        results.push({
            ref: ref,
            tag: li.tagName.toLowerCase(),
            text: (li.innerText || '').trim().slice(0, 120),
            type: '',
            role: li.getAttribute('role') || '',
            href: '',
            class: li.getAttribute('class') || '',
            aria_disabled: li.getAttribute('aria-disabled') || ''
        });
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
