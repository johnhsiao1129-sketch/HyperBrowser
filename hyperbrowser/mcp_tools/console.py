"""
browser_console - 抓取浏览器控制台日志
"""
from mcp.types import Tool, ToolAnnotations


TOOL = Tool(
    name="browser_console",
    description="READ-ONLY. 获取浏览器控制台日志。only_errors=true 只返回 error 级别。",
    inputSchema={
        "type": "object",
        "properties": {
            "only_errors": {"type": "boolean", "default": False},
            "limit": {"type": "integer", "default": 100},
        },
    },
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)


async def run(agent, args: dict) -> dict:
    only_errors = args.get("only_errors", False)
    limit = args.get("limit", 100)

    msgs = getattr(agent, "_console_messages", None)
    if msgs is None:
        msgs = []
        agent._console_messages = msgs

    filtered = [m for m in msgs if m.get("type") == "error"] if only_errors else list(msgs)
    return {
        "total": len(filtered),
        "messages": filtered[-limit:],
    }

