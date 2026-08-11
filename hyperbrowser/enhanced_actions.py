"""
Enhanced Actions - 扩展的交互动作类型

参考 OpenClaw `act` 子命令的 11 种动作 + 多种修饰参数。

新增 ActionType 值（在 schemas.py 加）：
- DOUBLE_CLICK = "double_click"
- DRAG         = "drag"
- FILL         = "fill"   (多字段批量填表)
- UPLOAD       = "upload" (文件上传)
- DIALOG       = "dialog" (主动 dialog 操作)

这些 action 不修改原 executor.py，而是通过 EnhancedActionDispatcher 调度。
这样保持核心 executor.py 干净，扩展功能独立。

用法：
    dispatcher = EnhancedActionDispatcher(page)
    await dispatcher.double_click({"ref": "ref_abc"})
    await dispatcher.drag({"startRef": "ref_a", "endRef": "ref_b"})
    await dispatcher.fill({"fields": [...]})
"""

import asyncio
from typing import Any, Dict, List, Optional, Union

try:
    from patchright.async_api import Page, Locator
except ImportError:
    from playwright.async_api import Page, Locator


class EnhancedActionError(Exception):
    """增强动作执行错误"""
    pass


class EnhancedActionDispatcher:
    """
    扩展动作调度器 - 提供 OpenClaw 风格的细粒度交互

    所有方法接收 dict 参数（类似 OpenClaw `request` 对象），
    返回 dict 包含执行结果。
    """

    def __init__(self, page: Page):
        self.page = page

    async def click(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """点击，支持 ref / selector / element / button / modifiers / doubleClick"""
        locator = self._resolve_locator(request)
        button = request.get("button", "left")
        modifiers = request.get("modifiers", [])
        double_click = request.get("doubleClick", False)

        kwargs: Dict[str, Any] = {"button": button, "force": request.get("force", False)}
        if modifiers:
            kwargs["modifiers"] = modifiers

        if double_click:
            await locator.dblclick(**kwargs)
            action = "doubleClick"
        else:
            await locator.click(**kwargs)
            action = "click"

        return {"action": action, "ok": True}

    async def type(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """输入文本，支持 slowly / delayMs / submit"""
        locator = self._resolve_locator(request)
        text = request.get("text", "")
        slowly = request.get("slowly", False)
        delay_ms = request.get("delayMs", 0)
        submit = request.get("submit", False)

        if slowly:
            await locator.press_sequentially(text, delay=80)
        elif delay_ms > 0:
            await locator.press_sequentially(text, delay=delay_ms)
        else:
            await locator.fill(text)

        if submit:
            await locator.press("Enter")

        return {"action": "type", "ok": True, "text": text, "submit": submit}

    async def fill(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        批量填表：一次性填多个字段

        request:
            fields: [{"ref": "ref_x", "value": "foo"}, ...]
        """
        fields = request.get("fields", [])
        if not fields:
            raise EnhancedActionError("fill requires 'fields' parameter (list)")
        results = []
        for field in fields:
            locator = self._resolve_locator({"ref": field.get("ref")})
            value = field.get("value", "")
            await locator.fill(value)
            results.append({"ref": field.get("ref"), "value": value, "ok": True})
        return {"action": "fill", "ok": True, "count": len(results), "fields": results}

    async def hover(self, request: Dict[str, Any]) -> Dict[str, Any]:
        locator = self._resolve_locator(request)
        await locator.hover()
        return {"action": "hover", "ok": True}

    async def press(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """按键，支持 modifiers 组合"""
        key = request.get("key", "")
        if not key:
            raise EnhancedActionError("press requires 'key' parameter")
        modifiers = request.get("modifiers", [])
        if modifiers:
            combo = "+".join(modifiers) + "+" + key
            await self.page.keyboard.press(combo)
        else:
            await self.page.keyboard.press(key)
        return {"action": "press", "ok": True, "key": key}

    async def select(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """下拉选择，支持单值 / 多值"""
        locator = self._resolve_locator(request)
        values = request.get("values")
        value = request.get("value")
        if values:
            await locator.select_option(values)
            chosen = values
        elif value is not None:
            await locator.select_option(value)
            chosen = value
        else:
            raise EnhancedActionError("select requires 'value' or 'values' parameter")
        return {"action": "select", "ok": True, "value": chosen}

    async def drag(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """拖拽：startRef → endRef"""
        start_ref = request.get("startRef")
        end_ref = request.get("endRef")
        if not start_ref or not end_ref:
            raise EnhancedActionError("drag requires 'startRef' and 'endRef' parameters")
        start = self._resolve_locator({"ref": start_ref})
        end = self._resolve_locator({"ref": end_ref})
        await start.drag_to(end)
        return {"action": "drag", "ok": True, "startRef": start_ref, "endRef": end_ref}

    async def resize(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """调整浏览器视口大小"""
        width = request.get("width")
        height = request.get("height")
        if not width or not height:
            raise EnhancedActionError("resize requires 'width' and 'height' parameters")
        await self.page.set_viewport_size({"width": int(width), "height": int(height)})
        return {"action": "resize", "ok": True, "width": width, "height": height}

    async def scroll(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """滚动页面。pixels=0 等于 1 个视口高度"""
        pixels = request.get("pixels", 0)
        direction = request.get("direction", "down")
        if pixels == 0:
            actual = await self.page.evaluate("() => window.innerHeight")
        else:
            actual = int(pixels)
        if direction == "up":
            actual = -actual
        await self.page.evaluate(f"() => window.scrollBy(0, {actual})")
        return {"action": "scroll", "ok": True, "pixels": actual, "direction": direction}

    async def navigate(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """导航到 URL"""
        url = request.get("url")
        if not url:
            raise EnhancedActionError("navigate requires 'url' parameter")
        await self.page.goto(url, wait_until="domcontentloaded")
        return {"action": "navigate", "ok": True, "url": url}

    async def screenshot(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """截图。返回 base64"""
        import base64
        full_page = request.get("fullPage", request.get("full_page", False))
        fmt = request.get("format", "png")
        path = request.get("path")
        kwargs = {"full_page": full_page, "type": fmt}
        if path:
            kwargs["path"] = path
        data = await self.page.screenshot(**kwargs)
        if isinstance(data, bytes):
            b64 = base64.b64encode(data).decode("ascii")
        else:
            b64 = data  # already base64 if path used
        return {"action": "screenshot", "ok": True, "format": fmt, "size_bytes": len(data) if isinstance(data, bytes) else 0, "data_base64": b64}

    async def wait(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        多种等待策略：
        - timeMs: 等待 N 毫秒
        - text: 等待文本出现
        - textGone: 等待文本消失
        - loadState: 等待指定 load state (load/domcontentloaded/networkidle)
        """
        if "timeMs" in request:
            await asyncio.sleep(int(request["timeMs"]) / 1000)
            return {"action": "wait", "ok": True, "mode": "time", "timeMs": request["timeMs"]}

        if "text" in request:
            await self.page.get_by_text(request["text"]).first.wait_for(
                timeout=request.get("timeoutMs", 10000)
            )
            return {"action": "wait", "ok": True, "mode": "text", "text": request["text"]}

        if "textGone" in request:
            await self.page.get_by_text(request["textGone"]).first.wait_for(
                state="hidden", timeout=request.get("timeoutMs", 10000)
            )
            return {"action": "wait", "ok": True, "mode": "textGone", "textGone": request["textGone"]}

        if "loadState" in request:
            await self.page.wait_for_load_state(request["loadState"])
            return {"action": "wait", "ok": True, "mode": "loadState", "state": request["loadState"]}

        raise EnhancedActionError("wait requires one of: timeMs, text, textGone, loadState")

    async def evaluate(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """执行 JS，fn 是函数体字符串，返回原始结果"""
        fn = request.get("fn", "")
        if not fn:
            raise EnhancedActionError("evaluate requires 'fn' parameter")
        # 如果 fn 形如 "() => ..." 直接执行；否则包成箭头函数
        script = fn if "=>" in fn or "function" in fn else f"() => ({fn})"
        try:
            result = await self.page.evaluate(script)
        except Exception as e:
            return {"action": "evaluate", "ok": False, "error": str(e)}
        return {"action": "evaluate", "ok": True, "result": _safe_json(result)}

    async def upload(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """文件上传"""
        selector = request.get("selector")
        paths = request.get("paths", [])
        ref = request.get("ref")
        if paths and not selector and not ref:
            raise EnhancedActionError("upload requires 'paths' and one of 'selector' or 'ref'")
        if selector:
            locator = self.page.locator(selector)
        else:
            locator = self._resolve_locator({"ref": ref})
        await locator.set_input_files(paths)
        return {"action": "upload", "ok": True, "count": len(paths)}

    def _resolve_locator(self, request: Dict[str, Any]) -> Locator:
        """根据 ref / selector / element 解析 locator"""
        ref = request.get("ref")
        if ref:
            return self.page.locator(f"[data-hyperbrowser-ref='{ref}']")

        selector = request.get("selector")
        if selector:
            return self.page.locator(selector)

        element = request.get("element")
        if element:
            return self.page.get_by_text(element).first

        raise EnhancedActionError(
            "Locator required: one of ref / selector / element"
        )


def _safe_json(obj: Any) -> Any:
    """把 evaluate 结果转成 JSON-safe 类型"""
    try:
        import json
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        return str(obj)

