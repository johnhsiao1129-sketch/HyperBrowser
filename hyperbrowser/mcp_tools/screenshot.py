"""
browser_screenshot - 截图
"""
import base64
from mcp.types import Tool, ToolAnnotations


TOOL = Tool(
    name="browser_screenshot",
    description="READ-ONLY. 截取页面截图。支持 PNG/JPEG 和全页模式。返回 base64。",
    inputSchema={
        "type": "object",
        "properties": {
            "format": {"type": "string", "enum": ["png", "jpeg"], "default": "png"},
            "full_page": {"type": "boolean", "default": False},
            "quality": {"type": "integer", "default": 80, "description": "JPEG 质量（1-100）"},
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
    fmt = args.get("format", "png")
    full_page = args.get("full_page", False)
    quality = args.get("quality", 80)

    page = agent.page
    kwargs: dict = {"full_page": full_page}
    if fmt == "jpeg":
        kwargs["type"] = "jpeg"
        kwargs["quality"] = quality

    png_bytes = await page.screenshot(**kwargs)
    b64 = base64.b64encode(png_bytes).decode("ascii")

    return {
        "format": fmt,
        "full_page": full_page,
        "size_bytes": len(png_bytes),
        "data_base64": b64,
        "url": page.url,
        "title": await page.title(),
    }

