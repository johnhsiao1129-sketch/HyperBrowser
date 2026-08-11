"""
browser_press - 按键
"""
from mcp.types import Tool, ToolAnnotations


TOOL = Tool(
    name="browser_press",
    description="按键盘按键。支持 modifiers 组合(Ctrl+Shift+P)。返回新快照。",
    inputSchema={
        "type": "object",
        "properties": {
            "key": {"type": "string", "description": "按键名（Enter/Escape/Tab/...）"},
            "modifiers": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["key"],
    },
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)


async def run(agent, args: dict) -> dict:
    request = {"key": args["key"], "modifiers": args.get("modifiers", [])}
    result = await agent.action_dispatcher.press(request)
    snapshot = await agent.get_snapshot()
    return {
        "action": "press",
        "ok": result["ok"],
        "key": result.get("key"),
        "snapshot": snapshot.to_dict(),
    }

