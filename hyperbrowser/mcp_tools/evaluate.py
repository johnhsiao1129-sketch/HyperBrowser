"""
browser_evaluate - 执行 JS
"""
from mcp.types import Tool, ToolAnnotations


TOOL = Tool(
    name="browser_evaluate",
    description="执行 JavaScript 并返回结果。可读写页面状态。推荐 () => ... 箭头函数形式。",
    inputSchema={
        "type": "object",
        "properties": {
            "fn": {
                "type": "string",
                "description": "JS 函数体或表达式（推荐 () => ... 形式）",
            },
        },
        "required": ["fn"],
    },
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)


async def run(agent, args: dict) -> dict:
    result = await agent.action_dispatcher.evaluate({"fn": args["fn"]})
    return {
        "action": "evaluate",
        "ok": result.get("ok"),
        "result": result.get("result"),
        "error": result.get("error"),
    }

