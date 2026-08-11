"""
browser_scroll - 滚动页面
"""
from mcp.types import Tool, ToolAnnotations


TOOL = Tool(
    name="browser_scroll",
    description="滚动页面。默认一个屏幕高度。返回新快照。",
    inputSchema={
        "type": "object",
        "properties": {
            "pixels": {"type": "integer", "default": 0, "description": "滚动像素（0 = 一个屏幕）"},
            "direction": {"type": "string", "enum": ["down", "up"], "default": "down"},
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
    pixels = args.get("pixels", 0)
    direction = args.get("direction", "down")

    actual = pixels if pixels != 0 else 720  # 默认一屏高度
    if direction == "up":
        actual = -actual

    await agent.action_dispatcher.evaluate({"fn": f"() => window.scrollBy(0, {actual})"})
    snapshot = await agent.get_snapshot()
    return {
        "action": "scroll",
        "ok": True,
        "scrolled_pixels": actual,
        "snapshot": snapshot.to_dict(),
    }

