"""
Browser Doctor - 浏览器健康自检

检查项：
- CDP 连接状态（已连接？URL 可达？）
- 浏览器可达性（list_tabs 能拿到？）
- 反检测状态（navigator.webdriver / chrome / plugins / languages）
- 对话框 handler 是否安装
- profile 目录可写性
- 端口冲突（CDP 端口是否被占用）

输出结构化报告（dict），方便 LLM/MCP 调用方诊断

用法：
    doctor = BrowserDoctor(manager=stealth_manager, dialog_handler=dh, ssrf_guard=sg)
    report = await doctor.run()
"""

import asyncio
import socket
from pathlib import Path
from typing import Any, Dict, Optional, List


class BrowserDoctor:
    """
    自检工具，输出结构化健康报告

    每项检查返回 {ok: bool, severity: "info"|"warn"|"error", message: str, detail?: Any}
    """

    def __init__(
        self,
        manager=None,
        dialog_handler=None,
        ssrf_guard=None,
        profile_manager=None,
    ):
        self.manager = manager
        self.dialog_handler = dialog_handler
        self.ssrf_guard = ssrf_guard
        self.profile_manager = profile_manager

    async def run(self) -> Dict[str, Any]:
        """执行所有检查，返回报告"""
        checks: List[Dict[str, Any]] = []

        checks.append(await self._check_browser_started())
        checks.append(self._check_profile_dir())
        checks.append(self._check_dialog_handler())
        checks.append(self._check_ssrf_guard())
        checks.append(await self._check_cdp_reachable())
        checks.append(await self._check_stealth_status())
        checks.append(await self._check_tabs_listable())

        errors = sum(1 for c in checks if not c["ok"] and c.get("severity") == "error")
        warnings = sum(1 for c in checks if not c["ok"] and c.get("severity") == "warn")

        return {
            "healthy": errors == 0,
            "summary": {
                "total": len(checks),
                "ok": sum(1 for c in checks if c["ok"]),
                "warnings": warnings,
                "errors": errors,
            },
            "checks": checks,
        }

    async def _check_browser_started(self) -> Dict[str, Any]:
        if not self.manager or not getattr(self.manager, "_page", None):
            return {
                "name": "browser_started",
                "ok": False,
                "severity": "error",
                "message": "Browser not started. Call start() or connect_over_cdp() first.",
            }
        try:
            url = self.manager._page.url
            return {
                "name": "browser_started",
                "ok": True,
                "severity": "info",
                "message": f"Browser running, current URL: {url}",
                "detail": {"url": url},
            }
        except Exception as e:
            return {
                "name": "browser_started",
                "ok": False,
                "severity": "error",
                "message": f"Cannot read page.url: {e}",
            }

    def _check_profile_dir(self) -> Dict[str, Any]:
        if not self.manager:
            return {
                "name": "profile_dir",
                "ok": True,
                "severity": "info",
                "message": "No manager attached, skipping",
            }
        p = Path(self.manager.user_data_dir)
        if not p.exists():
            return {
                "name": "profile_dir",
                "ok": False,
                "severity": "warn",
                "message": f"Profile dir does not exist: {p}",
            }
        if not p.is_dir():
            return {
                "name": "profile_dir",
                "ok": False,
                "severity": "error",
                "message": f"Profile path is not a directory: {p}",
            }
        try:
            test = p / ".hyperbrowser_write_test"
            test.write_text("ok")
            test.unlink()
        except Exception as e:
            return {
                "name": "profile_dir",
                "ok": False,
                "severity": "error",
                "message": f"Profile dir not writable: {e}",
                "detail": {"path": str(p)},
            }
        return {
            "name": "profile_dir",
            "ok": True,
            "severity": "info",
            "message": f"Profile dir OK: {p}",
        }

    def _check_dialog_handler(self) -> Dict[str, Any]:
        if not self.dialog_handler:
            return {
                "name": "dialog_handler",
                "ok": False,
                "severity": "warn",
                "message": "No dialog handler installed. Page may hang on alert/confirm/prompt.",
            }
        stats = self.dialog_handler.stats
        return {
            "name": "dialog_handler",
            "ok": True,
            "severity": "info",
            "message": f"Dialog handler active ({self.dialog_handler.mode})",
            "detail": stats.to_dict(),
        }

    def _check_ssrf_guard(self) -> Dict[str, Any]:
        if not self.ssrf_guard:
            return {
                "name": "ssrf_guard",
                "ok": False,
                "severity": "warn",
                "message": "No SSRF guard installed. Navigation to private networks is unrestricted.",
            }
        return {
            "name": "ssrf_guard",
            "ok": True,
            "severity": "info",
            "message": f"SSRF guard active (blocked {self.ssrf_guard.blocked_count} so far)",
            "detail": {
                "allow_private_network": self.ssrf_guard.allow_private_network,
                "allowed_hosts": sorted(self.ssrf_guard.allowed_hosts),
            },
        }

    async def _check_cdp_reachable(self) -> Dict[str, Any]:
        if not self.manager:
            return {
                "name": "cdp_reachable",
                "ok": True,
                "severity": "info",
                "message": "No manager, skipping",
            }
        url = getattr(self.manager, "cdp_endpoint", None)
        if not url:
            return {
                "name": "cdp_reachable",
                "ok": True,
                "severity": "info",
                "message": "Managed by Patchright, CDP endpoint not externally exposed",
            }
        host = url.replace("http://", "").replace("https://", "").split(":")[0]
        port = int(url.split(":")[-1].rstrip("/"))
        try:
            with socket.create_connection((host, port), timeout=2):
                return {
                    "name": "cdp_reachable",
                    "ok": True,
                    "severity": "info",
                    "message": f"CDP endpoint reachable: {url}",
                }
        except Exception as e:
            return {
                "name": "cdp_reachable",
                "ok": False,
                "severity": "error",
                "message": f"CDP endpoint unreachable: {e}",
                "detail": {"url": url},
            }

    async def _check_stealth_status(self) -> Dict[str, Any]:
        if not self.manager or not getattr(self.manager, "_page", None):
            return {
                "name": "stealth_status",
                "ok": True,
                "severity": "info",
                "message": "No page, skipping",
            }
        try:
            status = await self.manager.check_stealth_status()
            webdriver = status.get("webdriver", True)
            chrome_exists = status.get("chrome_exists", False)
            plugins_len = status.get("plugins_length", 0)
            issues = []
            if webdriver:
                issues.append("navigator.webdriver is true (leak)")
            if not chrome_exists:
                issues.append("window.chrome missing")
            if plugins_len < 3:
                issues.append(f"plugins.length={plugins_len} (too low)")
            return {
                "name": "stealth_status",
                "ok": not issues,
                "severity": "warn" if issues else "info",
                "message": "Stealth OK" if not issues else f"Stealth issues: {'; '.join(issues)}",
                "detail": status,
            }
        except Exception as e:
            return {
                "name": "stealth_status",
                "ok": False,
                "severity": "error",
                "message": f"Cannot check stealth: {e}",
            }

    async def _check_tabs_listable(self) -> Dict[str, Any]:
        if not self.manager:
            return {
                "name": "tabs_listable",
                "ok": True,
                "severity": "info",
                "message": "No manager, skipping",
            }
        try:
            tabs = await self.manager.list_tabs()
            return {
                "name": "tabs_listable",
                "ok": True,
                "severity": "info",
                "message": f"{len(tabs)} tab(s) visible",
                "detail": {"count": len(tabs)},
            }
        except Exception as e:
            return {
                "name": "tabs_listable",
                "ok": False,
                "severity": "warn",
                "message": f"Cannot list tabs: {e}",
            }

