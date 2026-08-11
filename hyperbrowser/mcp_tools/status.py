"""
browser_status - 浏览器状态查询
"""
from mcp.types import Tool, ToolAnnotations


TOOL = Tool(
    name="browser_status",
    description="READ-ONLY. 浏览器状态查询: URL/Title/反检测/dialog handler/SSRF 状态。",
    inputSchema={
        "type": "object",
        "properties": {
            "include_stealth": {"type": "boolean", "default": True},
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
    result = {
        "url": page.url,
        "title": await page.title(),
        "browser_started": True,
    }

    if args.get("include_stealth", True):
        try:
            result["stealth"] = await agent.check_stealth_status()
        except Exception as e:
            result["stealth"] = {"error": str(e)}

    if agent.dialog_handler:
        result["dialog_handler"] = {
            "mode": agent.dialog_handler.mode,
            "stats": agent.dialog_handler.stats.to_dict(),
        }
    else:
        result["dialog_handler"] = None

    if agent.ssrf_guard:
        result["ssrf_guard"] = {
            "blocked_count": agent.ssrf_guard.blocked_count,
            "allow_private_network": agent.ssrf_guard.allow_private_network,
        }
    else:
        result["ssrf_guard"] = None

    if agent.hostname_allowlist:
        result["hostname_allowlist"] = agent.hostname_allowlist.list()
    else:
        result["hostname_allowlist"] = None

    return result

