"""
Profile Manager - 多 profile 隔离 + 端口分配持久化

OpenClaw 参考：
- 端口范围 18800-18899（100 个 profile 上限）
- profile 名字持久化在配置里
- profile 之间完全隔离（独立 user_data_dir + 独立 CDP 端口 + 独立 fingerprint）

用法：
    mgr = ProfileManager(config_path="~/.hyperbrowser/profiles.json")
    profile = mgr.create("work")  # 自动分配端口 18801
    mgr.list()
"""

import json
import re
import socket
from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass, asdict


PROFILE_NAME_REGEX = re.compile(r"^[a-zA-Z0-9_\-]{1,32}$")
CDP_PORT_RANGE_START = 18800
CDP_PORT_RANGE_END = 18899
DEFAULT_PROFILE = "default"
DEFAULT_PROFILE_PORT = 18800


@dataclass
class Profile:
    name: str
    user_data_dir: str
    cdp_port: int
    cdp_url: Optional[str] = None
    color: str = "#888888"
    stealth_level: str = "maximum"
    created_at: float = 0.0


class ProfileManager:
    """
    管理多个隔离的 browser profile

    每个 profile：
    - 独立 user_data_dir（独立指纹 + 独立 cookie）
    - 独立 CDP 端口（可同时跑多个 Chrome 实例）
    - 独立 stealth_level
    """

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_path = str(Path.home() / ".hyperbrowser" / "profiles.json")
        self.config_path = Path(config_path)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.profiles: Dict[str, Profile] = {}
        self._load()

    def _load(self):
        if not self.config_path.exists():
            self.profiles[DEFAULT_PROFILE] = Profile(
                name=DEFAULT_PROFILE,
                user_data_dir=str(Path.home() / ".hyperbrowser" / "profiles" / DEFAULT_PROFILE),
                cdp_port=DEFAULT_PROFILE_PORT,
                created_at=_now(),
            )
            self._save()
            return
        try:
            data = json.loads(self.config_path.read_text(encoding="utf-8"))
            for name, p in data.get("profiles", {}).items():
                self.profiles[name] = Profile(**p)
        except Exception:
            self.profiles = {}

    def _save(self):
        data = {
            "profiles": {name: asdict(p) for name, p in self.profiles.items()},
        }
        self.config_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    @staticmethod
    def _is_valid_name(name: str) -> bool:
        return bool(PROFILE_NAME_REGEX.match(name))

    def _allocate_port(self) -> Optional[int]:
        used = {p.cdp_port for p in self.profiles.values()}
        for port in range(CDP_PORT_RANGE_START, CDP_PORT_RANGE_END + 1):
            if port in used:
                continue
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(("127.0.0.1", port))
                    return port
            except OSError:
                continue
        return None

    def get(self, name: str) -> Optional[Profile]:
        return self.profiles.get(name)

    def list(self) -> List[Profile]:
        return list(self.profiles.values())

    def create(
        self,
        name: str,
        stealth_level: str = "maximum",
    ) -> Profile:
        if not self._is_valid_name(name):
            raise ValueError(
                f"Invalid profile name {name!r}: must match {PROFILE_NAME_REGEX.pattern}"
            )
        if name in self.profiles:
            raise ValueError(f"Profile {name!r} already exists")

        port = self._allocate_port()
        if port is None:
            raise RuntimeError(
                f"No free CDP port in range {CDP_PORT_RANGE_START}-{CDP_PORT_RANGE_END}"
            )

        profile = Profile(
            name=name,
            user_data_dir=str(Path.home() / ".hyperbrowser" / "profiles" / name),
            cdp_port=port,
            cdp_url=f"http://127.0.0.1:{port}",
            stealth_level=stealth_level,
            created_at=_now(),
        )
        Path(profile.user_data_dir).mkdir(parents=True, exist_ok=True)
        self.profiles[name] = profile
        self._save()
        return profile

    def delete(self, name: str) -> bool:
        if name == DEFAULT_PROFILE:
            raise ValueError("Cannot delete the default profile")
        if name not in self.profiles:
            return False
        del self.profiles[name]
        self._save()
        return True


def _now() -> float:
    import time
    return time.time()

