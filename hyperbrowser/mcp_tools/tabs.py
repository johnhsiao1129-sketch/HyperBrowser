"""
browser_tabs - 标签页管理（list/attach）
"""
from mcp.types import Tool, ToolAnnotations

from ..core.executor import BatchExecutor
from ..core.snapshot import SnapshotExtractor
from ..enhanced_actions import EnhancedActionDispatcher


TOOL = Tool(
    name="browser_tabs",
    description="标签页管理。list 列出所有标签页; attach 按 url_contains 或 index 切换到指定标签页。",
    inputSchema={
        "type": "object",
        "properties": {
            "command": {"type": "string", "enum": ["list", "attach"], "default": "list"},
            "url_contains": {"type": "string"},
            "index": {"type": "integer"},
        },
    },
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)


async def run(agent, args: dict) -> dict:
    command = args.get("command", "list")
    manager = agent._browser_manager
    if command == "list":
        tabs = await manager.list_tabs()
        return {"command": "list", "tabs": tabs, "count": len(tabs)}
    if command == "attach":
        page = await manager.attach_to_tab(
            url_contains=args.get("url_contains"),
            index=args.get("index"),
        )
        agent._executor = BatchExecutor(page, humanize=True)
        agent._snapshot_extractor = SnapshotExtractor(page)
        agent._action_dispatcher = EnhancedActionDispatcher(page)
        return {
            "command": "attach",
            "ok": True,
            "url": page.url,
        }
    return {"ok": False, "error": f"Unknown command: {command}"}

