# HyperBrowser

面向 AI Agent 的高效反检测浏览器自动化框架。

解决浏览器操作的三大痛点：

1. **反自动化检测** — 基于 Patchright 的隐形配置，绕过常见反爬指纹
2. **反复工具调用** — 批处理执行 + 零状态调用，一次调用完成多步操作
3. **Token 消耗高** — 轻量快照，只提取交互元素，节省约 90% 上下文

## 特性

- **三层架构**
  - 第 1 层：声明式 API — `plan().navigate().click().execute()`
  - 第 2 层：操作模板 — `use_template("Baidu_search", keyword="xxx")`
  - 第 3 层：批处理执行器 — `execute_actions([...])`
- **隐身模式**（Stealth）— Patchright 隐形配置，三种级别：`standard` / `maximum` / `paranoid`
- **浏览器 Profile 管理** — 独立的用户数据目录，登录态持久化
- **CDP 连接** — 支持接入已运行的浏览器（`browser_connect` / `browser_scan`）
- **安全防护** — 自动对话框处理（DialogHandler）、SSRF 防护（SsrfGuard）
- **MCP Server** — 完整 MCP 协议实现，20+ 个工具，可直接接入 OpenClaw / OpenCode / Claude 等

## 安装

```bash
pip install -r requirements.txt
# 或
pip install -e .
```

依赖：Python >= 3.9，patchright >= 1.0.0，playwright >= 1.40.0，openai >= 1.0.0，pydantic >= 2.0.0

## 快速开始

### 作为库使用

```python
import asyncio
from hyperbrowser import HyperBrowserAgent

async def main():
    agent = HyperBrowserAgent(user_data_dir="~/.config/hyperbrowser/profile")
    await agent.start()

    # 第 1 层：声明式链式调用
    result = await agent.plan()\
        .navigate("https://www.baidu.com")\
        .input("#kw", "HyperBrowser")\
        .click("#su")\
        .execute()

    print("success:", result.success)
    await agent.close()

asyncio.run(main())
```

### 第 2 层：操作模板

```python
plan = agent.use_template("Baidu_search", keyword="反检测浏览器")
result = await plan.execute()
links = result.get_links()  # 快速提取结果链接
```

### 第 3 层：批处理执行

```python
actions = [
    {"type": "navigate", "value": "https://example.com"},
    {"type": "wait", "value": "1000"},
    {"type": "click", "locator": {"type": "css", "value": "#submit"}},
]
result = await agent.execute_actions(actions)
```

## 作为 MCP Server 使用

启动方式：

```bash
python -m hyperbrowser.mcp_server
```

或通过 `opencode.jsonc` 配置接入：

```json
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
```

### 内置工具

| 类别 | 工具 |
|---|---|
| 导航 | `browser_navigate` |
| 页面快照 | `browser_snapshot`（轻量，省 token） |
| 交互 | `browser_click` / `browser_input` / `browser_hover` / `browser_select` / `browser_press` |
| 滚动 | `browser_scroll` |
| 等待 | `browser_wait` |
| 文件 | `browser_upload` / `browser_screenshot` / `browser_pdf` |
| 调试 | `browser_console` / `browser_evaluate` / `browser_act` / `browser_doctor` |
| 标签页 | `browser_tabs` / `browser_status` |
| Profile | `browser_profiles` |
| 接入已有浏览器 | `browser_scan` / `browser_connect` |

## 配置

配置优先级：环境变量 > 用户配置文件 > 默认值。

配置文件路径：`~/.config/opencode/hyperbrowser-config.json`

| 配置项 | 环境变量 | 默认值 | 说明 |
|---|---|---|---|
| `user_data_dir` | `HYPERBROWSER_USER_DATA_DIR` | `~/.config/hyperbrowser/profile` | 浏览器 profile 目录 |
| `stealth_level` | `HYPERBROWSER_STEALTH_LEVEL` | `maximum` | 隐身级别 |
| `auto_dialog_handler` | `HYPERBROWSER_AUTO_DIALOG_HANDLER` | `true` | 自动处理对话框 |
| `auto_ssrf_guard` | `HYPERBROWSER_AUTO_SSRF_GUARD` | `true` | SSRF 防护 |
| `cdp_endpoint` | `HYPERBROWSER_CDP_ENDPOINT` | 无 | 连接已有浏览器 |
| `channel` | `HYPERBROWSER_CHANNEL` | 无 | 浏览器渠道（如 `chrome`） |
| `default_timeout_ms` | — | `30000` | 默认超时 |

> 提示：把 `user_data_dir` 设为日常 Chrome 的 User Data 目录时，需先关闭日常 Chrome（lockfile 冲突），启动 HyperBrowser 接管后再使用。

## 测试

```bash
python tests/test_minimal_patchright.py   # 验证 patchright 启动
python tests/test_minimal_stealth.py      # 验证反检测/隐身模式
```

## 许可证

MIT
