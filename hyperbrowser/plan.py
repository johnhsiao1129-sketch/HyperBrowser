"""
OperationPlan / ExecutionResult - 第1层声明式 API
用法：
    result = await agent.plan()\\
        .navigate("https://example.com")\\
        .input("#search", "keyword")\\
        .click("#submit")\\
        .execute()

    links = result.get_links()
"""

from typing import Any, Dict, List, Optional

from .models.schemas import Action, ActionType


class OperationPlan:
    """可链式调用的操作计划"""

    def __init__(self, _agent=None, steps: Optional[List[Action]] = None):
        self._agent = _agent
        self._steps: List[Action] = steps or []

    # ========================================================================
    # 链式方法（每个返回 self）
    # ========================================================================

    def navigate(self, url: str) -> "OperationPlan":
        self._steps.append(
            Action(type=ActionType.NAVIGATE, value=url, wait_after=1000,
                   description=f"navigate to {url}")
        )
        return self

    def click(self, selector: str) -> "OperationPlan":
        self._steps.append(
            Action(type=ActionType.CLICK,
                   locator={"type": "css", "value": selector},
                   description=f"click {selector}")
        )
        return self

    def input(self, selector: str, text: str) -> "OperationPlan":
        self._steps.append(
            Action(type=ActionType.TYPE,
                   locator={"type": "css", "value": selector},
                   value=text,
                   description=f"type into {selector}")
        )
        return self

    def wait(self, ms: int = 1000) -> "OperationPlan":
        self._steps.append(
            Action(type=ActionType.WAIT, value=str(ms),
                   description=f"wait {ms}ms")
        )
        return self

    def scroll(self, pixels: Optional[int] = None) -> "OperationPlan":
        self._steps.append(
            Action(type=ActionType.SCROLL,
                   value=str(pixels) if pixels is not None else None,
                   description="scroll page")
        )
        return self

    def hover(self, selector: str) -> "OperationPlan":
        self._steps.append(
            Action(type=ActionType.HOVER,
                   locator={"type": "css", "value": selector},
                   description=f"hover {selector}")
        )
        return self

    def press(self, key: str) -> "OperationPlan":
        self._steps.append(
            Action(type=ActionType.PRESS, value=key,
                   description=f"press {key}")
        )
        return self

    def select(self, selector: str, value: str) -> "OperationPlan":
        self._steps.append(
            Action(type=ActionType.SELECT,
                   locator={"type": "css", "value": selector},
                   value=value,
                   description=f"select {value} in {selector}")
        )
        return self

    def execute_js(self, script: str) -> "OperationPlan":
        self._steps.append(
            Action(type=ActionType.EXECUTE_JS, value=script,
                   description="execute javascript")
        )
        return self

    # ========================================================================
    # 执行
    # ========================================================================

    async def execute(self) -> "ExecutionResult":
        """执行计划，返回 ExecutionResult"""
        if self._agent is None:
            raise RuntimeError(
                "OperationPlan has no agent. Use agent.plan() or agent.do()."
            )
        actions: List[Dict[str, Any]] = []
        for step in self._steps:
            actions.append(
                {
                    "type": step.type.value
                    if isinstance(step.type, ActionType)
                    else str(step.type),
                    "locator": step.locator,
                    "value": step.value,
                    "wait_after": step.wait_after,
                    "description": step.description,
                }
            )
        batch_result = await self._agent.execute_actions(actions)
        return ExecutionResult(batch_result)


class ExecutionResult:
    """操作计划执行结果包装器"""

    def __init__(self, batch_result):
        self._result = batch_result

    @property
    def success(self) -> bool:
        return bool(self._result.success)

    @property
    def completed_actions(self) -> List[Dict[str, Any]]:
        return self._result.completed_actions

    @property
    def failed_action(self) -> Optional[Dict[str, Any]]:
        return self._result.failed_action

    @property
    def error_message(self) -> Optional[str]:
        return self._result.error_message

    @property
    def execution_time_ms(self) -> float:
        return self._result.execution_time_ms

    def get_links(self) -> List[str]:
        """从最终快照提取链接（快速搜索常用）"""
        snapshot = getattr(self._result, "final_snapshot", None)
        if snapshot is None or not snapshot.interactive_elements:
            return []
        links = []
        for el in snapshot.interactive_elements:
            href = el.get("href") or ""
            if href:
                links.append(href)
        return links

    def __repr__(self) -> str:
        return (
            f"<ExecutionResult success={self.success} "
            f"completed={len(self.completed_actions)} "
            f"time={self.execution_time_ms:.0f}ms>"
        )


__all__ = ["OperationPlan", "ExecutionResult"]
