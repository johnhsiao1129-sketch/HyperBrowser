"""
browser_act - 统一动作入口（兼容 OpenClaw act 子命令风格）

支持的 kind：
- click / type / fill / hover / press / select / drag / resize / wait / evaluate / upload

所有 kind 共用 modifiers (button/modifiers/slowly/submit/delayMs/...) 参数。
"""
from mcp.types import Tool, ToolAnnotations


TOOL = Tool(
    name="browser_act",
    description="统一动作入口。kind=click|type|fill|hover|press|select|drag|resize|wait|evaluate|upload|scroll|navigate|screenshot。优先用专用 tool，browser_act 兜底。",
    inputSchema={
        "type": "object",
        "properties": {
            "kind": {
                "type": "string",
                "enum": ["click", "type", "fill", "hover", "press",
                         "select", "drag", "resize", "wait", "evaluate", "upload",
                         "scroll", "navigate", "screenshot"],
            },
            "ref": {"type": "string"},
            "selector": {"type": "string"},
            "element": {"type": "string"},
            "text": {"type": "string"},
            "slowly": {"type": "boolean"},
            "delay_ms": {"type": "integer"},
            "submit": {"type": "boolean"},
            "key": {"type": "string"},
            "modifiers": {"type": "array", "items": {"type": "string"}},
            "button": {"type": "string", "enum": ["left", "right", "middle"]},
            "double_click": {"type": "boolean"},
            "start_ref": {"type": "string"},
            "end_ref": {"type": "string"},
            "values": {"type": "array", "items": {"type": "string"}},
            "value": {"type": "string"},
            "fields": {"type": "array"},
            "width": {"type": "integer"},
            "height": {"type": "integer"},
            "time_ms": {"type": "integer"},
            "text_gone": {"type": "string"},
            "load_state": {"type": "string"},
            "fn": {"type": "string"},
            "paths": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["kind"],
    },
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=True,
    ),
)


async def run(agent, args: dict) -> dict:
    kind = args["kind"]
    request = {
        "ref": args.get("ref"),
        "selector": args.get("selector"),
        "element": args.get("element"),
        "text": args.get("text"),
        "slowly": args.get("slowly", False),
        "delayMs": args.get("delay_ms", 0),
        "submit": args.get("submit", False),
        "key": args.get("key"),
        "modifiers": args.get("modifiers", []),
        "button": args.get("button", "left"),
        "doubleClick": args.get("double_click", False),
        "startRef": args.get("start_ref"),
        "endRef": args.get("end_ref"),
        "values": args.get("values"),
        "value": args.get("value"),
        "fields": args.get("fields"),
        "width": args.get("width"),
        "height": args.get("height"),
        "timeMs": args.get("time_ms"),
        "textGone": args.get("text_gone"),
        "loadState": args.get("load_state"),
        "fn": args.get("fn"),
        "paths": args.get("paths"),
    }

    dispatcher = agent.action_dispatcher
    method = getattr(dispatcher, kind, None)
    if method is None:
        return {"ok": False, "error": f"Unknown action kind: {kind}"}

    try:
        result = await method(request)
    except Exception as e:
        return {"ok": False, "kind": kind, "error": str(e)}

    snapshot = await agent.get_snapshot()
    return {
        "ok": result.get("ok", True),
        "kind": kind,
        "result": result,
        "snapshot": snapshot.to_dict(),
    }

