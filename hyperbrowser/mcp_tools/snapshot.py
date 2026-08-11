"""
browser_snapshot - 获取当前页面快照（多种格式可选）
"""
from mcp.types import Tool, ToolAnnotations


TOOL = Tool(
    name="browser_snapshot",
    description="READ-ONLY. 获取当前页面快照。用 ref 定位元素。格式: interactive(默认)/compact/aria/ai",
    inputSchema={
        "type": "object",
        "properties": {
            "format": {
                "type": "string",
                "enum": ["interactive", "compact", "aria", "ai"],
                "default": "interactive",
            },
            "max_chars": {"type": "integer", "default": 50000},
            "include_stealth_status": {"type": "boolean", "default": False},
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
    from ..snapshot_formats import FormatOptions, format_snapshot

    fmt = args.get("format", "interactive")
    max_chars = args.get("max_chars", 50000)

    snapshot = await agent.get_snapshot()
    snapshot_data = snapshot.to_dict()

    options = FormatOptions(format=fmt, max_chars=max_chars)
    formatted_text = format_snapshot(snapshot_data, options)

    result = {
        "format": fmt,
        "url": snapshot.url,
        "title": snapshot.title,
        "text": formatted_text,
        "interactive_count": len(snapshot.interactive_elements),
    }

    if args.get("include_stealth_status"):
        try:
            result["stealth_status"] = await agent.check_stealth_status()
        except Exception as e:
            result["stealth_status"] = {"error": str(e)}

    return result

