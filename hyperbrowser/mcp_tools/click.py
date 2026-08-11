"""
browser_click - 点击元素
"""
from mcp.types import Tool, ToolAnnotations


TOOL = Tool(
    name="browser_click",
    description="点击元素。三种定位: ref/selector/element。优先用 ref。返回新快照。",
    inputSchema={
        "type": "object",
        "properties": {
            "ref": {"type": "string", "description": "snapshot 返回的 ref id"},
            "selector": {"type": "string", "description": "CSS selector"},
            "element": {"type": "string", "description": "元素文本"},
            "button": {"type": "string", "enum": ["left", "right", "middle"], "default": "left"},
            "modifiers": {"type": "array", "items": {"type": "string"}},
            "double_click": {"type": "boolean", "default": False},
            "timeout_ms": {"type": "integer", "default": 5000},
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
        "button": args.get("button", "left"),
        "modifiers": args.get("modifiers", []),
        "doubleClick": args.get("double_click", False),
    }
    result = await agent.action_dispatcher.click(request)
    snapshot = await agent.get_snapshot()
    return {
        "action": result["action"],
        "ok": result["ok"],
        "snapshot": snapshot.to_dict(),
    }

