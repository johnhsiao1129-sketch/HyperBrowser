"""
browser_connect - 动态切换 MCP 连接的浏览器/标签页

通过 browser_scan 发现可用的 CDP 端点后，用本工具切换过去。
工作原理：
  1. 读取 cdp_endpoint 参数（如 "http://127.0.0.1:9223"）
  2. 关闭当前 agent 的浏览器连接
  3. 将新 endpoint 存入模块级变量，下一个 MCP 工具调用时自动重建 agent

对应 mcp_server.py 中的 _pending_cdp_endpoint 变量。
"""
from mcp.types import Tool, ToolAnnotations

# 这些由 mcp_server.py 在运行时注入
_pending_endpoint: str | None = None


TOOL = Tool(
    name="browser_connect",
    description="切换到指定 CDP 端口的浏览器。先调 browser_scan 发现可用端口。切换后后续操作在新浏览器执行。",
    inputSchema={
        "type": "object",
        "properties": {
            "cdp_endpoint": {
                "type": "string",
                "description": "CDP 端点 URL，如 http://127.0.0.1:9222",
            },
        },
        "required": ["cdp_endpoint"],
    },
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=True,
    ),
)


def set_pending_endpoint(endpoint: str | None):
    """由 mcp_server.py 调用，注入待切换的 endpoint"""
    global _pending_endpoint
    _pending_endpoint = endpoint


def get_pending_endpoint() -> str | None:
    """由 mcp_server.py 调用，获取待切换的 endpoint"""
    return _pending_endpoint


async def run(agent, args: dict) -> dict:
    """
    此函数在 mcp_server.call_tool 中被特殊处理——不会调用 _get_agent()。
    见 mcp_server.py 中 call_tool() 对 browser_connect 的 if 分支。
    """
    endpoint = args["cdp_endpoint"]
    set_pending_endpoint(endpoint)
    return {
        "ok": True,
        "message": f"Will connect to {endpoint} on next tool call",
    }

