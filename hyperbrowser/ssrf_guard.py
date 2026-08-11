"""
SsrfGuard - SSRF 防护
拦截私网 / loopback / link-local / 云元数据地址的请求

用法：
    guard = SsrfGuard(allow_private_network=False, allowed_hosts={"localhost"})
    await guard.install(page)
    guard.check_url("http://169.254.169.254/latest/meta-data")  # raises
"""

import ipaddress
import socket
from typing import Optional, Set
from urllib.parse import urlparse

# 常见私网 / 保留网段前缀（避免逐个 ipaddress 判断的开销）
_PRIVATE_NETWORKS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),   # CGNAT
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),        # ULA
    ipaddress.ip_network("fe80::/10"),       # link-local v6
)

# 云元数据端点
_METADATA_HOSTS = {
    "169.254.169.254",          # AWS / GCP / Aliyun
    "metadata.google.internal", # GCP
    "metadata",                 # 常见别名
}


class SsrfGuard:
    """拦截私网 / 元数据请求的 SSRF 防护器"""

    def __init__(
        self,
        allow_private_network: bool = False,
        allowed_hosts: Optional[Set[str]] = None,
    ):
        self.allow_private_network = allow_private_network
        self.allowed_hosts: Set[str] = set(allowed_hosts or [])
        self.blocked_count: int = 0

    async def install(self, page) -> None:
        """安装请求拦截（page.route 钩子）"""

        async def _intercept(route, request):
            try:
                self.check_url(request.url)
            except Exception:
                self.blocked_count += 1
                await route.abort("blockedbyclient")
                return
            await route.continue_()

        try:
            await page.route("**/*", _intercept)
        except Exception:
            # 某些 CDP 端点不支持 route，静默降级
            pass

    def check_url(self, url: str) -> None:
        """
        校验 URL 是否安全。不安全时抛 ValueError。
        """
        parsed = urlparse(url)
        host = parsed.hostname
        if not host:
            return  # 无 hostname（data: 等）放行

        # 白名单直接放行
        if host in self.allowed_hosts:
            return

        # 云元数据端点一律拦截
        if host in _METADATA_HOSTS:
            raise ValueError(f"SSRF blocked: {host} is a cloud metadata endpoint")

        # 字面 IP 判断
        ip: Optional[ipaddress._BaseAddress] = None
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            pass

        if ip is None:
            try:
                ip = ipaddress.ip_address(socket.gethostbyname(host))
            except Exception:
                # DNS 解析失败：保守拦截（无法确认是公网）
                raise ValueError(f"SSRF blocked: cannot resolve host '{host}'")

        if self._is_private(ip) and not self.allow_private_network:
            raise ValueError(
                f"SSRF blocked: {host} resolves to private address {ip}"
            )

    def _is_private(self, ip: ipaddress._BaseAddress) -> bool:
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return True
        for net in _PRIVATE_NETWORKS:
            if ip in net:
                return True
        return False

    def __repr__(self) -> str:
        return (
            f"<SsrfGuard allow_private_network={self.allow_private_network} "
            f"blocked={self.blocked_count}>"
        )


__all__ = ["SsrfGuard"]
