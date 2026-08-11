"""
数据模型 - HyperBrowser 核心数据结构
包含：ActionType / LocatorType / Action / BatchPlan / PageSnapshot / BatchResult
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ActionType(str, Enum):
    """批处理操作类型（第3层执行器）"""

    NAVIGATE = "navigate"
    CLICK = "click"
    TYPE = "type"
    WAIT = "wait"
    SCROLL = "scroll"
    HOVER = "hover"
    PRESS = "press"
    SELECT = "select"
    EXECUTE_JS = "execute_js"
    # 扩展动作（EnhancedActionDispatcher 支持）
    DOUBLE_CLICK = "double_click"
    DRAG = "drag"
    FILL = "fill"
    UPLOAD = "upload"
    DIALOG = "dialog"


class LocatorType(str, Enum):
    """元素定位类型"""

    CSS = "css"
    TEXT = "text"
    REF = "ref"
    PLACEHOLDER = "placeholder"
    ELEMENT = "element"


@dataclass
class Action:
    """单个批处理操作"""

    type: ActionType
    locator: Optional[Dict[str, Any]] = None
    value: Optional[str] = None
    wait_after: int = 500
    description: str = ""


@dataclass
class BatchPlan:
    """批处理计划：一系列按序执行的操作"""

    actions: List[Action] = field(default_factory=list)
    stop_on_error: bool = False


@dataclass
class PageSnapshot:
    """页面快照 - 轻量级，只含交互元素（90% token 节省）"""

    url: str = ""
    title: str = ""
    interactive_elements: List[Dict[str, Any]] = field(default_factory=list)
    visible_text_summary: str = ""
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """转 dict（供 MCP 工具序列化）"""
        return {
            "url": self.url,
            "title": self.title,
            "interactive_elements": self.interactive_elements,
            "visible_text_summary": self.visible_text_summary,
            "timestamp": self.timestamp,
        }


@dataclass
class BatchResult:
    """批处理执行结果"""

    success: bool = True
    completed_actions: List[Dict[str, Any]] = field(default_factory=list)
    failed_action: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    execution_time_ms: float = 0.0
    final_snapshot: Optional[PageSnapshot] = None


__all__ = [
    "ActionType",
    "LocatorType",
    "Action",
    "BatchPlan",
    "PageSnapshot",
    "BatchResult",
]
