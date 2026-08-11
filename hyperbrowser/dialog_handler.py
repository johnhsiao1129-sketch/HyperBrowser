"""
DialogHandler - 自动处理浏览器对话框 (alert/confirm/prompt/beforeunload)

用法：
    handler = DialogHandler(mode="accept", log=False)
    await handler.install(page)
"""

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class DialogStats:
    """对话框处理统计"""

    handled: int = 0
    by_type: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"handled": self.handled, "by_type": self.by_type}


class DialogHandler:
    """自动处理页面对话框"""

    def __init__(self, mode: str = "accept", log: bool = False):
        """
        Args:
            mode: "accept" (确定) | "dismiss" (取消)
            log: 是否打印对话框内容
        """
        if mode not in ("accept", "dismiss"):
            raise ValueError(f"Unsupported mode: {mode}. Use 'accept' or 'dismiss'")
        self.mode = mode
        self.log = log
        self.stats = DialogStats()

    async def install(self, page) -> None:
        """安装 dialog 监听器"""

        async def _handle_dialog(dialog):
            self.stats.handled += 1
            dtype = str(getattr(dialog, "type", "unknown"))
            self.stats.by_type[dtype] = self.stats.by_type.get(dtype, 0) + 1

            if self.log:
                message = getattr(dialog, "message", "") or ""
                print(f"[HyperBrowser] dialog({dtype}): {message[:120]}")

            if self.mode == "accept":
                await dialog.accept()
            else:
                await dialog.dismiss()

        page.on("dialog", _handle_dialog)

    def __repr__(self) -> str:
        return f"<DialogHandler mode={self.mode} handled={self.stats.handled}>"


__all__ = ["DialogHandler", "DialogStats"]
