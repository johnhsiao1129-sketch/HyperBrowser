"""
browser_navigate - 导航到 URL，返回页面快照
"""
from mcp.types import Tool, ToolAnnotations


TOOL = Tool(
    name="browser_navigate",
    description="导航到 URL。必须先导航才能操作页面。返回 PageSnapshot 含 ref。",
    inputSchema={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "目标 URL（必须 http/https）"},
            "wait_until": {
                "type": "string",
                "enum": ["load", "domcontentloaded", "networkidle"],
                "default": "domcontentloaded",
            },
            "timeout_ms": {"type": "integer", "default": 30000},
        },
        "required": ["url"],
    },
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=True,
    ),
)


async def run(agent, args: dict) -> dict:
    from ..models.schemas import Action, ActionType, BatchPlan

    url = args["url"]

    # Pre-check: SSRF guard + hostname allowlist
    if getattr(agent, "ssrf_guard", None):
        try:
            agent.ssrf_guard.check_url(url)
        except Exception as e:
            return {
                "success": False,
                "url": url,
                "title": None,
                "snapshot": {},
                "error_message": f"SSRF pre-check failed: {e}",
            }
    if getattr(agent, "hostname_allowlist", None):
        try:
            agent.hostname_allowlist.check(url)
        except Exception as e:
            return {
                "success": False,
                "url": url,
                "title": None,
                "snapshot": {},
                "error_message": f"Hostname not in allowlist: {e}",
            }

    plan = BatchPlan(
        actions=[Action(type=ActionType.NAVIGATE, value=url, wait_after=1000)]
    )
    result = await agent.executor.execute_batch(plan)
    snapshot = await agent.get_snapshot()
    return {
        "success": result.success,
        "url": snapshot.url,
        "title": snapshot.title,
        "snapshot": snapshot.to_dict(),
        "error_message": result.error_message,
    }

