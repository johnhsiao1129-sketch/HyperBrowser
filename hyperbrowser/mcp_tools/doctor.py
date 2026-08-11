"""
browser_doctor - 浏览器健康自检
"""
from mcp.types import Tool, ToolAnnotations


TOOL = Tool(
    name="browser_doctor",
    description="READ-ONLY. 浏览器健康自检。返回结构化报告: CDP/可达性/指纹/handler 状态。",
    inputSchema={
        "type": "object",
        "properties": {
            "deep": {"type": "boolean", "default": False},
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
    return await agent.doctor()

