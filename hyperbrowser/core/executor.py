"""
BatchExecutor - 批处理执行器（第3层核心引擎）
执行 Action 序列，支持 humanize 延迟与逐动作错误处理
"""

import asyncio
import random
import time
from typing import Any, Dict, List, Optional

from ..models.schemas import (
    Action,
    ActionType,
    BatchPlan,
    BatchResult,
    LocatorType,
)


class BatchExecutor:
    """批量执行操作序列，返回 BatchResult"""

    def __init__(self, page, humanize: bool = True):
        self.page = page
        self.humanize = humanize

    # ========================================================================
    # 主入口
    # ========================================================================

    async def execute_batch(self, plan: BatchPlan) -> BatchResult:
        """执行计划中的所有操作"""
        start = time.time()
        result = BatchResult()
        actions = plan.actions or []

        for index, action in enumerate(actions):
            try:
                await self._execute_action(action)
                result.completed_actions.append(
                    {
                        "index": index,
                        "type": self._action_type_str(action),
                        "description": action.description,
                    }
                )
            except Exception as exc:
                error_info = {
                    "index": index,
                    "type": self._action_type_str(action),
                    "description": action.description,
                    "error": str(exc),
                }
                if plan.stop_on_error:
                    result.success = False
                    result.failed_action = error_info
                    result.error_message = str(exc)
                    break
                result.completed_actions.append(error_info)

            if action.wait_after and action.wait_after > 0:
                await asyncio.sleep(action.wait_after / 1000)
            elif self.humanize:
                # 模拟人类操作节奏：随机 80-300ms
                await asyncio.sleep(random.uniform(0.08, 0.3))

        result.execution_time_ms = (time.time() - start) * 1000

        # 零状态调用：批处理结束后自动回填最终页面快照
        try:
            from .snapshot import SnapshotExtractor

            extractor = SnapshotExtractor(self.page)
            result.final_snapshot = await extractor.extract()
        except Exception:
            result.final_snapshot = None

        return result

    # ========================================================================
    # 单动作执行
    # ========================================================================

    async def _execute_action(self, action: Action) -> None:
        """执行单个操作（核心分发）"""
        atype = action.type
        if atype == ActionType.NAVIGATE:
            await self._do_navigate(action)
        elif atype == ActionType.CLICK:
            await self._do_click(action)
        elif atype == ActionType.TYPE:
            await self._do_type(action)
        elif atype == ActionType.WAIT:
            await self._do_wait(action)
        elif atype == ActionType.SCROLL:
            await self._do_scroll(action)
        elif atype == ActionType.HOVER:
            await self._do_hover(action)
        elif atype == ActionType.PRESS:
            await self._do_press(action)
        elif atype == ActionType.SELECT:
            await self._do_select(action)
        elif atype == ActionType.EXECUTE_JS:
            await self._do_execute_js(action)
        else:
            raise ValueError(f"Unsupported action type: {atype}")

    async def _do_navigate(self, action: Action) -> None:
        url = action.value or ""
        if not url:
            raise ValueError("navigate requires 'value' (URL)")
        await self.page.goto(url, wait_until="domcontentloaded")

    async def _do_click(self, action: Action) -> None:
        locator = self._resolve_locator(action.locator)
        await locator.click()

    async def _do_type(self, action: Action) -> None:
        locator = self._resolve_locator(action.locator)
        text = action.value or ""
        await locator.fill(text)

    async def _do_wait(self, action: Action) -> None:
        try:
            ms = int(action.value or 0)
        except (TypeError, ValueError):
            ms = 0
        if ms > 0:
            await asyncio.sleep(ms / 1000)

    async def _do_scroll(self, action: Action) -> None:
        value = action.value
        if value:
            pixels = int(value)
            await self.page.evaluate(f"window.scrollBy(0, {pixels})")
        else:
            # 滚动一屏
            await self.page.evaluate("window.scrollBy(0, window.innerHeight)")

    async def _do_hover(self, action: Action) -> None:
        locator = self._resolve_locator(action.locator)
        await locator.hover()

    async def _do_press(self, action: Action) -> None:
        key = action.value or ""
        if not key:
            raise ValueError("press requires 'value' (key name)")
        await self.page.keyboard.press(key)

    async def _do_select(self, action: Action) -> None:
        locator = self._resolve_locator(action.locator)
        value = action.value or ""
        await locator.select_option(value)

    async def _do_execute_js(self, action: Action) -> None:
        script = action.value or ""
        if not script:
            raise ValueError("execute_js requires 'value' (script)")
        await self.page.evaluate(script)

    # ========================================================================
    # 工具方法
    # ========================================================================

    def _resolve_locator(self, locator: Optional[Dict[str, Any]]):
        """
        根据 locator dict 解析元素
        支持: {"type": "css"|"text"|"ref"|"placeholder", "value": ...}
        """
        if not locator:
            raise ValueError("locator required")

        ltype = locator.get("type", LocatorType.CSS.value)
        value = locator.get("value", "")

        if ltype in (LocatorType.REF.value, "ref"):
            return self.page.locator(f"[data-hyperbrowser-ref='{value}']")
        if ltype in (LocatorType.TEXT.value, "text"):
            return self.page.get_by_text(value).first
        if ltype in (LocatorType.PLACEHOLDER.value, "placeholder"):
            return self.page.get_by_placeholder(value).first

        # 默认 CSS selector
        return self.page.locator(value)

    @staticmethod
    def _action_type_str(action: Action) -> str:
        if isinstance(action.type, ActionType):
            return action.type.value
        return str(action.type)


__all__ = ["BatchExecutor"]
