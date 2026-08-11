"""
browser_hover - 悬停元素
"""
from mcp.types import Tool, ToolAnnotations


TOOL = Tool(
    name="browser_hover",
    description="悬停元素。触发 hover 态样式。返回新快照。",
    inputSchema={
        "type": "object",
        "properties": {
            "ref": {"type": "string"},
            "selector": {"type": "string"},
            "element": {"type": "string"},
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
    request = {
        "ref": args.get("ref"),
        "selector": args.get("selector"),
        "element": args.get("element"),
    }
    result = await agent.action_dispatcher.hover(request)
    snapshot = await agent.get_snapshot()
    return {
        "action": "hover",
        "ok": result["ok"],
        "snapshot": snapshot.to_dict(),
    }

