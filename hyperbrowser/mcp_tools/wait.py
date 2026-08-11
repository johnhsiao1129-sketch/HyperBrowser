"""
browser_wait - 等待
"""
from mcp.types import Tool, ToolAnnotations


TOOL = Tool(
    name="browser_wait",
    description="等待条件满足: time_ms(毫秒) / text(出现) / text_gone(消失) / load_state(网络空闲)。返回新快照。",
    inputSchema={
        "type": "object",
        "properties": {
            "time_ms": {"type": "integer"},
            "text": {"type": "string"},
            "text_gone": {"type": "string"},
            "load_state": {"type": "string", "enum": ["load", "domcontentloaded", "networkidle"]},
            "timeout_ms": {"type": "integer", "default": 10000},
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
    request: dict = {"timeoutMs": args.get("timeout_ms", 10000)}
    if "time_ms" in args:
        request["timeMs"] = args["time_ms"]
    if "text" in args:
        request["text"] = args["text"]
    if "text_gone" in args:
        request["textGone"] = args["text_gone"]
    if "load_state" in args:
        request["loadState"] = args["load_state"]
    result = await agent.action_dispatcher.wait(request)
    snapshot = await agent.get_snapshot()
    return {
        "action": "wait",
        "ok": result.get("ok"),
        "mode": result.get("mode"),
        "snapshot": snapshot.to_dict(),
    }

