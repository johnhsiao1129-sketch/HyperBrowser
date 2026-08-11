"""
HyperBrowser - 面向 AI Agent 的高效反检测浏览器自动化框架
========================================================
解决 OpenClaw/OpenCode 浏览器操作的三大痛点：
1. 反自动化检测（Patchright 隐形配置）
2. 反复工具调用（批处理执行 + 零状态调用）
3. Token 消耗高（轻量快照）

三层架构：
  第1层：声明式 API - plan().navigate().click().execute()
  第2层：操作模板 - use_template("Baidu_search", keyword="xxx")
  第3层：批处理执行器 - execute_actions([...])
"""

from .agent import HyperBrowserAgent
from .mcp_tool import HyperBrowserMCPTool
from .models.schemas import (
    ActionType,
    LocatorType,
    Action,
    BatchPlan,
    PageSnapshot,
    BatchResult,
)
from .core.browser import StealthBrowserManager
from .core.executor import BatchExecutor
from .core.snapshot import SnapshotExtractor
from .plan import OperationPlan, ExecutionResult
from .templates import OperationTemplate, TemplateRegistry, registry

__version__ = "2.0.0"
__author__ = "HyperBrowser Team"

__all__ = [
    # 核心 Agent
    "HyperBrowserAgent",
    "HyperBrowserMCPTool",
    # 数据模型
    "ActionType",
    "LocatorType",
    "Action",
    "BatchPlan",
    "PageSnapshot",
    "BatchResult",
    # 底层组件
    "StealthBrowserManager",
    "BatchExecutor",
    "SnapshotExtractor",
    # 声明式 API
    "OperationPlan",
    "ExecutionResult",
    # 模板系统
    "OperationTemplate",
    "TemplateRegistry",
    "registry",
]

