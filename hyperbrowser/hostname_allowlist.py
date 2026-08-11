"""
HostnameAllowlist - 域名白名单
限制可访问的 hostname（配合 SSRF 防护使用）

用法：
    allowlist = HostnameAllowlist({"example.com"})
    allowlist.check("https://example.com/x")  # OK
    allowlist.check("https://evil.com/x")     # raises ValueError
"""

from typing import List, Optional, Set
from urllib.parse import urlparse


class HostnameAllowlist:
    """hostname 白名单校验器"""

    def __init__(self, allowed_hosts: Optional[Set[str]] = None):
        self._hosts: Set[str] = set(allowed_hosts or [])

    def add(self, host: str) -> None:
        self._hosts.add(host)

    def check(self, url: str) -> None:
        """
        校验 URL 的 hostname 是否在白名单内。不在则抛 ValueError。
        空白名单 = 不限制（放行所有）。
        """
        if not self._hosts:
            return

        host = urlparse(url).hostname
        if not host:
            raise ValueError(f"Invalid URL (no hostname): {url}")
        if host not in self._hosts:
            raise ValueError(
                f"Hostname '{host}' not in allowlist. "
                f"Allowed: {sorted(self._hosts)}"
            )

    def list(self) -> List[str]:
        """返回白名单列表（排序）"""
        return sorted(self._hosts)

    def __repr__(self) -> str:
        return f"<HostnameAllowlist hosts={sorted(self._hosts)}>"


__all__ = ["HostnameAllowlist"]
