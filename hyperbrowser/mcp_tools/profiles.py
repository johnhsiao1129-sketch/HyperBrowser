"""
browser_profiles - profile 管理（list/create/get/delete）
"""
from mcp.types import Tool, ToolAnnotations


TOOL = Tool(
    name="browser_profiles",
    description="profile 管理。list/create/get/delete。每个 profile 有独立 user_data_dir。",
    inputSchema={
        "type": "object",
        "properties": {
            "command": {"type": "string", "enum": ["list", "create", "get", "delete"], "default": "list"},
            "name": {"type": "string"},
            "stealth_level": {"type": "string", "enum": ["standard", "maximum", "paranoid"], "default": "maximum"},
        },
        "required": ["command"],
    },
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=True,
    ),
)


async def run(agent, args: dict) -> dict:
    command = args["command"]
    pm = agent.profile_manager

    if command == "list":
        profiles = [
            {
                "name": p.name,
                "user_data_dir": p.user_data_dir,
                "cdp_port": p.cdp_port,
                "stealth_level": p.stealth_level,
            }
            for p in pm.list()
        ]
        return {"command": "list", "profiles": profiles, "count": len(profiles)}

    if command == "create":
        try:
            p = pm.create(args["name"], stealth_level=args.get("stealth_level", "maximum"))
        except Exception as e:
            return {"command": "create", "ok": False, "error": str(e)}
        return {
            "command": "create",
            "ok": True,
            "profile": {
                "name": p.name,
                "user_data_dir": p.user_data_dir,
                "cdp_port": p.cdp_port,
                "stealth_level": p.stealth_level,
            },
        }

    if command == "get":
        p = pm.get(args["name"])
        if not p:
            return {"command": "get", "ok": False, "error": f"Profile not found: {args['name']}"}
        return {
            "command": "get",
            "profile": {
                "name": p.name,
                "user_data_dir": p.user_data_dir,
                "cdp_port": p.cdp_port,
                "stealth_level": p.stealth_level,
            },
        }

    if command == "delete":
        try:
            ok = pm.delete(args["name"])
        except Exception as e:
            return {"command": "delete", "ok": False, "error": str(e)}
        return {"command": "delete", "ok": ok}

    return {"ok": False, "error": f"Unknown command: {command}"}

