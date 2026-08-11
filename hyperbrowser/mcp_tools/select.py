"""
browser_select - 下拉选择
"""
from mcp.types import Tool, ToolAnnotations


TOOL = Tool(
    name="browser_select",
    description="下拉框选择。单选传 value，多选传 values。返回新快照。",
    inputSchema={
        "type": "object",
        "properties": {
            "ref": {"type": "string"},
            "selector": {"type": "string"},
            "element": {"type": "string"},
            "value": {"type": "string", "description": "单选 value"},
            "values": {"type": "array", "items": {"type": "string"}, "description": "多选 values"},
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
    request = {
        "ref": args.get("ref"),
        "selector": args.get("selector"),
        "element": args.get("element"),
    }
    if "value" in args:
        request["value"] = args["value"]
    if "values" in args:
        request["values"] = args["values"]
    result = await agent.action_dispatcher.select(request)
    snapshot = await agent.get_snapshot()
    return {
        "action": "select",
        "ok": result["ok"],
        "value": result.get("value"),
        "snapshot": snapshot.to_dict(),
    }

