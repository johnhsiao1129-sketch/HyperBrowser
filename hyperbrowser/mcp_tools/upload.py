"""
browser_upload - 文件上传
"""
from mcp.types import Tool, ToolAnnotations


TOOL = Tool(
    name="browser_upload",
    description="触发文件选择器，上传本地文件。paths 数组指定文件路径。返回新快照。",
    inputSchema={
        "type": "object",
        "properties": {
            "ref": {"type": "string"},
            "selector": {"type": "string"},
            "paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "要上传的本地文件路径列表",
            },
        },
        "required": ["paths"],
    },
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=True,
    ),
)


async def run(agent, args: dict) -> dict:
    request = {
        "ref": args.get("ref"),
        "selector": args.get("selector"),
        "paths": args["paths"],
    }
    result = await agent.action_dispatcher.upload(request)
    snapshot = await agent.get_snapshot()
    return {
        "action": "upload",
        "ok": result["ok"],
        "count": result.get("count"),
        "snapshot": snapshot.to_dict(),
    }

