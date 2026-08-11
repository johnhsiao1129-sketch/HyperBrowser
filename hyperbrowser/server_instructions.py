"""
HyperBrowser MCP server instructions
注入到 Server 的 instructions 字段，agent 每 session 读一次。
单文件 = single source of truth。

内容原则：<200 词，5 段，只放跨 tool 关系 + 硬约束。
"""
# 计数验证：人工数 < 200 词
SERVER_INSTRUCTIONS = """# HyperBrowser — 反检测浏览器自动化

真实 Chrome/Edge/Patchright Chromium，绕过 Cloudflare/反爬。

## 核心工作流

`browser_navigate` → `browser_snapshot`（拿 ref）→ `browser_click`/`browser_input`... → `browser_snapshot`（拿新 ref）→ ...

**始终用 ref 定位元素。每步后调 browser_snapshot 确认状态。**

## 接入已有浏览器

`browser_scan`（探测 9222-9230 端口）→ `browser_connect`（选端点）→ 后续操作在新浏览器执行

## 意图 → 工具

| 意图 | 工具 |
|---|---|
| 导航到页面 | browser_navigate |
| 获取快照、定位元素 | browser_snapshot |
| 点击/输入/滚动/按键/悬停/选择 | browser_click / browser_input / browser_scroll / browser_press / browser_hover / browser_select |
| 等待条件 | browser_wait |
| 截图/导出 PDF | browser_screenshot / browser_pdf |
| 执行 JS / 查 console 日志 | browser_evaluate / browser_console |
| 切换标签页 / 查浏览器状态 | browser_tabs / browser_status |
| 健康自检 | browser_doctor |
| 上传文件 / profile 管理 | browser_upload / browser_profiles |

## 反模式

- **连续 click 不 snapshot** — DOM 更新后 ref 失效，拿不到最新状态。
- **同一 ref 反复用** — DOM 变化后 ref 过期，调 browser_snapshot 取新 ref。
- **evaluate 跑耗时 JS** — 30s 超时，拆小段执行。
- **浏览器启动失败** — 关掉已打开的同 profile Chrome（lockfile 冲突）。

## 配置

`~/.config/opencode/hyperbrowser-config.json`: user_data_dir / stealth_level / channel / auto_dialog_handler / auto_ssrf_guard / default_timeout_ms
`HYPERBROWSER_*` env var 优先级更高。
"""
