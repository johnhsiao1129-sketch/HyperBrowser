"""
HyperBrowser MCP Server - 真正的 MCP 协议实现

启动方式：
    python -m hyperbrowser.mcp_server

或通过 opencode.jsonc 配置：
    {
      "mcp": {
        "hyperbrowser": {
          "command": "python",
          "args": ["-m", "hyperbrowser.mcp_server"],
          "env": {
            "HYPERBROWSER_STEALTH_LEVEL": "maximum",
            "HYPERBROWSER_AUTO_DIALOG_HANDLER": "1",
            "HYPERBROWSER_AUTO_SSRF_GUARD": "1"
          }
        }
      }
    }
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .agent import HyperBrowserAgent
from .dialog_handler import DialogHandler
from .ssrf_guard import SsrfGuard
from .server_instructions import SERVER_INSTRUCTIONS
from . import mcp_tools


logger = logging.getLogger("hyperbrowser.mcp")
logger.setLevel(logging.INFO)

app = Server("hyperbrowser", instructions=SERVER_INSTRUCTIONS)
_agent: HyperBrowserAgent | None = None
_pending_cdp_endpoint: str | None = None  # browser_connect 注入，下次 tool call 时切换


_CONFIG_PATH = Path.home() / ".config" / "opencode" / "hyperbrowser-config.json"


def _default_user_data_dir() -> str:
    """默认 profile 路径. XDG 风格, 跨平台, 不依赖 opencode."""
    return str(Path.home() / ".config" / "hyperbrowser" / "profile")


def _load_config() -> dict:
    """加载配置. 优先级: env var > user config file > defaults.

    默认路径是绝对路径 (Path.home()/.config/hyperbrowser/profile),
    与用户在 config 文件里写的绝对路径行为一致 — 都用 Path.resolve() 规范化.

    注意: 把 user_data_dir 设为默认 Chrome profile (AppData\\Local\\Google\\Chrome\\User_Data)
    是合法的 — agent 可以借此操作用户的日常浏览器, 但需要在启动 agent 前关闭日常 Chrome.
    """
    cfg: dict = {}
    if _CONFIG_PATH.exists():
        try:
            with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                raw = json.load(f)
            cfg = {k: v for k, v in raw.items() if not k.startswith("_")}
            logger.info(f"Config loaded from {_CONFIG_PATH}: {len(cfg)} keys")
        except json.JSONDecodeError as e:
            logger.error(
                f"Config JSON syntax error at line {e.lineno} col {e.colno}: {e.msg}\n"
                f"  file: {_CONFIG_PATH}\n"
                f"  using built-in defaults — fix the file and restart opencode"
            )
        except Exception as e:
            logger.error(f"Failed to load {_CONFIG_PATH}: {type(e).__name__}: {e}")

    # Tip: 用默认 Chrome profile 时, agent 启动 Chrome 会和正在运行的 Chrome 抢 lockfile.
    # 解决方案: 启动 agent 前先关闭日常 Chrome, agent 接管后再用.
    if cfg.get("user_data_dir"):
        ud = str(cfg["user_data_dir"]).replace("/", "\\").lower()
        is_chrome_default = (
            ud.endswith("\\appdata\\local\\google\\chrome\\user_data")
            or ud.endswith("\\appdata\\local\\google\\chrome\\user data")
        )
        if is_chrome_default:
            logger.info(
                f"user_data_dir is the default Chrome profile. "
                f"If Chrome is already running, agent launch will fail (lockfile). "
                f"Close Chrome before using HyperBrowser."
            )

    if "HYPERBROWSER_USER_DATA_DIR" in os.environ:
        cfg["user_data_dir"] = os.environ["HYPERBROWSER_USER_DATA_DIR"]
    if "HYPERBROWSER_STEALTH_LEVEL" in os.environ:
        cfg["stealth_level"] = os.environ["HYPERBROWSER_STEALTH_LEVEL"]
    if "HYPERBROWSER_AUTO_DIALOG_HANDLER" in os.environ:
        cfg["auto_dialog_handler"] = os.environ["HYPERBROWSER_AUTO_DIALOG_HANDLER"] == "1"
    if "HYPERBROWSER_AUTO_SSRF_GUARD" in os.environ:
        cfg["auto_ssrf_guard"] = os.environ["HYPERBROWSER_AUTO_SSRF_GUARD"] == "1"
    if "HYPERBROWSER_CDP_ENDPOINT" in os.environ:
        cfg["cdp_endpoint"] = os.environ["HYPERBROWSER_CDP_ENDPOINT"]
    if "HYPERBROWSER_CHANNEL" in os.environ:
        cfg["channel"] = os.environ["HYPERBROWSER_CHANNEL"]
    if "HYPERBROWSER_SSRF_ALLOWED_HOSTS" in os.environ:
        cfg["ssrf_allowed_hosts"] = [
            h.strip() for h in os.environ["HYPERBROWSER_SSRF_ALLOWED_HOSTS"].split(",") if h.strip()
        ]

    cfg.setdefault("user_data_dir", _default_user_data_dir())
    cfg.setdefault("stealth_level", "maximum")
    cfg.setdefault("auto_dialog_handler", True)
    cfg.setdefault("auto_ssrf_guard", True)
    cfg.setdefault("default_timeout_ms", 30000)

    cfg["user_data_dir"] = str(Path(cfg["user_data_dir"]).expanduser().resolve())

    return cfg


async def _get_agent() -> HyperBrowserAgent:
    """懒加载 + 单例 agent. 检测浏览器是否还活着, 死了自动重建.

    支持 browser_connect 动态切换 CDP endpoint:
    - _pending_cdp_endpoint 非空 → 强制重建 agent 连新端点
    - agent 浏览器进程挂了 → 自动重建
    """
    global _agent, _pending_cdp_endpoint

    # 有待切换的 endpoint，强制重建
    if _pending_cdp_endpoint is not None:
        if _agent is not None:
            try:
                await _agent.close()
            except Exception:
                pass
            _agent = None

    # 现有 agent 心跳检查
    if _agent is not None:
        try:
            page = _agent._browser_manager._page if _agent._browser_manager else None
            if page is not None:
                _ = page.url
            return _agent
        except Exception:
            logger.warning("Cached agent's browser died, rebuilding")
            try:
                await _agent.close()
            except Exception:
                pass
            _agent = None

    cfg = _load_config()

    # 优先使用 browser_connect 注入的待切换 endpoint
    consumed_endpoint = None
    if _pending_cdp_endpoint is not None:
        cfg["cdp_endpoint"] = _pending_cdp_endpoint
        consumed_endpoint = _pending_cdp_endpoint
        _pending_cdp_endpoint = None  # 消费掉

    dh = DialogHandler(mode="accept", log=False) if cfg["auto_dialog_handler"] else None
    sg = SsrfGuard(
        allow_private_network=False,
        allowed_hosts=set(cfg.get("ssrf_allowed_hosts", [])),
    ) if cfg["auto_ssrf_guard"] else None

    _agent = HyperBrowserAgent(
        user_data_dir=cfg["user_data_dir"],
        stealth_level=cfg["stealth_level"],
        cdp_endpoint=cfg.get("cdp_endpoint"),
        channel=cfg.get("channel"),
        dialog_handler=dh,
        ssrf_guard=sg,
        auto_install_dialog_handler=False,
        auto_install_ssrf_guard=False,
        verbose=False,
    )
    await _agent.start()
    if consumed_endpoint:
        logger.info(
            f"Agent reconnected via browser_connect "
            f"(cdp={consumed_endpoint})"
        )
    else:
        logger.info(
            f"Agent started (stealth={cfg['stealth_level']}, "
            f"profile={cfg['user_data_dir']}, cdp={cfg.get('cdp_endpoint')})"
        )
    return _agent


@app.list_tools()
async def list_tools() -> list[Tool]:
    return mcp_tools.TOOLS


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    global _agent, _pending_cdp_endpoint

    handler = mcp_tools.REGISTRY.get(name)
    if handler is None:
        return [TextContent(
            type="text",
            text=json.dumps({"ok": False, "error": f"Unknown tool: {name}"}, ensure_ascii=False),
        )]

    try:
        if name == "browser_scan":
            # 纯 HTTP 探测，不需要浏览器 agent
            result = await handler(None, arguments)
        elif name == "browser_connect":
            # 关闭当前 agent，设置待切换 endpoint
            if _agent is not None:
                try:
                    await _agent.close()
                except Exception:
                    pass
                _agent = None
            _pending_cdp_endpoint = arguments["cdp_endpoint"]
            result = await handler(None, arguments)
        else:
            agent = await _get_agent()
            result = await handler(agent, arguments)
    except Exception as e:
        logger.exception(f"Tool {name} failed")
        result = {"ok": False, "error": str(e)}

    return [TextContent(
        type="text",
        text=json.dumps(result, ensure_ascii=False, default=str),
    )]


async def _cleanup():
    global _agent
    if _agent is not None:
        try:
            await _agent.close()
        except Exception:
            pass
        _agent = None


async def main():
    async with stdio_server() as (read_stream, write_stream):
        try:
            await app.run(
                read_stream,
                write_stream,
                app.create_initialization_options(),
            )
        finally:
            await _cleanup()


if __name__ == "__main__":
    asyncio.run(main())

