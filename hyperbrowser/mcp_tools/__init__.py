"""
HyperBrowser MCP Tools Package

每个 MCP tool 一个文件，按功能拆分（一个功能一个文件）。

tool 文件结构：
    TOOL = Tool(name=..., description=..., inputSchema={...})
    async def run(agent, args: dict) -> dict: ...

本包对外暴露：
    TOOLS: list[Tool]  所有 Tool 定义（给 mcp_server 用 list_tools）
    REGISTRY: dict[str, callable]  name → run 函数
"""

from typing import Callable, Awaitable, Any

from . import (
    navigate,
    snapshot,
    click,
    input_text,
    scroll,
    wait,
    press,
    hover,
    select,
    upload,
    screenshot,
    pdf,
    console,
    evaluate,
    act,
    doctor,
    tabs,
    status,
    profiles,
    scan,
    connect,
)


TOOLS = [
    navigate.TOOL,
    snapshot.TOOL,
    click.TOOL,
    input_text.TOOL,
    scroll.TOOL,
    wait.TOOL,
    press.TOOL,
    hover.TOOL,
    select.TOOL,
    upload.TOOL,
    screenshot.TOOL,
    pdf.TOOL,
    console.TOOL,
    evaluate.TOOL,
    act.TOOL,
    doctor.TOOL,
    tabs.TOOL,
    status.TOOL,
    profiles.TOOL,
    scan.TOOL,
    connect.TOOL,
]


REGISTRY: dict[str, Callable[[Any, dict], Awaitable[dict]]] = {
    "browser_navigate": navigate.run,
    "browser_snapshot": snapshot.run,
    "browser_click": click.run,
    "browser_input": input_text.run,
    "browser_scroll": scroll.run,
    "browser_wait": wait.run,
    "browser_press": press.run,
    "browser_hover": hover.run,
    "browser_select": select.run,
    "browser_upload": upload.run,
    "browser_screenshot": screenshot.run,
    "browser_pdf": pdf.run,
    "browser_console": console.run,
    "browser_evaluate": evaluate.run,
    "browser_act": act.run,
    "browser_doctor": doctor.run,
    "browser_tabs": tabs.run,
    "browser_status": status.run,
    "browser_profiles": profiles.run,
    "browser_scan": scan.run,
    "browser_connect": connect.run,
}

