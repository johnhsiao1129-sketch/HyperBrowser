"""
browser_scan - 扫描本地 CDP 端口，探测已启动的浏览器及其标签页

扫描端口范围 9222-9230，对每个端口：
1. GET /json/version → 浏览器名称、版本、WebSocket 调试地址
2. GET /json         → 标签页列表（URL、标题、id）

返回结构供 agent 决策连接到哪个浏览器。
"""
import asyncio
import json
import urllib.request

from mcp.types import Tool, ToolAnnotations


# 默认扫描端口范围
SCAN_PORTS = list(range(9222, 9231))

# 超时（秒）
SCAN_TIMEOUT = 2


TOOL = Tool(
    name="browser_scan",
    description="READ-ONLY. 扫描本地 9222-9230 端口上的 CDP 端点。返回浏览器身份+标签页列表。调 browser_connect 前先用这个发现可用浏览器。",
    inputSchema={
        "type": "object",
        "properties": {
            "ports": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "扫描端口列表（默认 9222~9230）",
            },
            "timeout": {
                "type": "number",
                "description": "每个端口的超时秒数（默认 2）",
            },
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
    """运行扫描，不需要 agent — 直接 HTTP 探测"""
    ports = args.get("ports", SCAN_PORTS)
    timeout = args.get("timeout", SCAN_TIMEOUT)

    results: list[dict] = []
    scanned = 0

    async def _http_get_json(url: str, timeout: float) -> dict | list | None:
        """线程池内执行阻塞 HTTP GET，返回解析后的 JSON"""
        def _fetch():
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        try:
            return await asyncio.to_thread(_fetch)
        except Exception:
            return None

    async def probe_port(port: int) -> dict | None:
        """探测单个端口，返回浏览器信息 + 标签页，或 None（无响应）"""
        version_url = f"http://127.0.0.1:{port}/json/version"

        version_data = await _http_get_json(version_url, timeout)
        if not isinstance(version_data, dict):
            return None

        browser = version_data.get("Browser", "unknown")
        webSocketDebuggerUrl = version_data.get("webSocketDebuggerUrl", "")

        # GET /json → 标签页列表
        tabs: list[dict] = []
        tabs_url = f"http://127.0.0.1:{port}/json"
        raw_tabs = await _http_get_json(tabs_url, timeout)
        if isinstance(raw_tabs, list):
            for t in raw_tabs:
                if t.get("type") == "page":
                    tabs.append({
                        "id": t.get("id", ""),
                        "title": t.get("title", ""),
                        "url": t.get("url", ""),
                        "webSocketDebuggerUrl": t.get("webSocketDebuggerUrl", ""),
                    })

        return {
            "port": port,
            "browser": browser,
            "webSocketDebuggerUrl": webSocketDebuggerUrl,
            "tabs": tabs,
            "tab_count": len(tabs),
        }

    tasks = [probe_port(port) for port in ports]
    for coro in asyncio.as_completed(tasks):
        result = await coro
        scanned += 1
        if result is not None:
            results.append(result)

    return {
        "ok": True,
        "scanned": scanned,
        "found": len(results),
        "browsers": results,
    }

