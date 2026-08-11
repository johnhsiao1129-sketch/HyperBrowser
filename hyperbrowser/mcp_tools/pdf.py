"""
browser_pdf - 导出 PDF
"""
import base64
from mcp.types import Tool, ToolAnnotations


TOOL = Tool(
    name="browser_pdf",
    description="READ-ONLY. 导出页面为 PDF。支持 A4/Letter/A3/A5/Legal 格式。返回 base64。",
    inputSchema={
        "type": "object",
        "properties": {
            "format": {"type": "string", "enum": ["Letter", "A4", "A3", "A5", "Legal"], "default": "A4"},
            "landscape": {"type": "boolean", "default": False},
            "print_background": {"type": "boolean", "default": True},
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
    page = agent.page
    pdf_bytes = await page.pdf(
        format=args.get("format", "A4"),
        landscape=args.get("landscape", False),
        print_background=args.get("print_background", True),
    )
    return {
        "format": args.get("format", "A4"),
        "size_bytes": len(pdf_bytes),
        "data_base64": base64.b64encode(pdf_bytes).decode("ascii"),
        "url": page.url,
    }

