"""
browser_input - 输入文本
"""
from mcp.types import Tool, ToolAnnotations


TOOL = Tool(
    name="browser_input",
    description="在输入框输入文本。支持逐字符慢速输入和 Enter 提交。优先用 ref。返回新快照。",
    inputSchema={
        "type": "object",
        "properties": {
            "ref": {"type": "string"},
            "selector": {"type": "string"},
            "element": {"type": "string"},
            "text": {"type": "string"},
            "slowly": {"type": "boolean", "default": False, "description": "逐字符慢速输入（80ms/字）"},
            "delay_ms": {"type": "integer", "default": 0, "description": "字符间延迟毫秒"},
            "submit": {"type": "boolean", "default": False, "description": "输入后按 Enter"},
        },
        "required": ["text"],
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
        "text": args["text"],
        "slowly": args.get("slowly", False),
        "delayMs": args.get("delay_ms", 0),
        "submit": args.get("submit", False),
    }
    result = await agent.action_dispatcher.type(request)
    snapshot = await agent.get_snapshot()
    return {
        "action": "input",
        "ok": result["ok"],
        "text": result.get("text"),
        "submit": result.get("submit"),
        "snapshot": snapshot.to_dict(),
    }

