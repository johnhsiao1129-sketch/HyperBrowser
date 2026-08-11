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

### 运行前提

- **必须安装 Google Chrome**（代码通过 `channel="chrome"` 启动真实 Chrome，不是 Chromium）

### 作为库

```bash
pip install -r requirements.txt
# 或安装为可编辑包（推荐，会同时装齐全部依赖）
pip install -e .
```

依赖：Python >= 3.9，patchright >= 1.0.0，playwright >= 1.40.0，openai >= 1.0.0，pydantic >= 2.0.0

### 作为 MCP Server

```bash
# 需额外安装 mcp 协议库（requirements.txt 未包含，setup.py 已声明）
pip install "mcp>=1.0.0,<2.0.0"
# 推荐：直接 pip install -e . 一次装齐
```

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

### 第 4 层：实时控制模式（每步返回快照）

适合 AI Agent 逐步决策：每次操作都返回页面快照（含交互元素 ref），供下一步定位。

```python
snapshot = await agent.navigate("https://example.com")
snapshot = await agent.click(selector="#submit")        # 或 ref="..."
snapshot = await agent.input_text(selector="#kw", text="hello")
snapshot = await agent.wait(ms=1000)
snapshot = await agent.snapshot()                       # 主动取快照
links = snapshot.get_links()                            # 提取页面链接
```

### HyperBrowserAgent 参数

| 参数 | 默认值 | 说明 |
|---|---|---|
| `user_data_dir` | `./hyperbrowser_profile` | 浏览器 profile 目录（登录态持久化） |
| `headless` | `False` | 无头模式 |
| `stealth_level` | `maximum` | 隐身级别：`standard` / `maximum` / `paranoid` |
| `cdp_endpoint` | 无 | CDP 端点，连接已有浏览器 |
| `channel` | `chrome` | 浏览器渠道（本机 Chrome / Edge） |
| `llm_client` | 无 | 可选 LLM 客户端 |
| `verbose` | `True` | 详细日志 |

## 作为 MCP Server 使用

### 启动方式

```bash
python -m hyperbrowser.mcp_server
```

### 接入 OpenCode / OpenClaw 等宿主

MCP 协议通过 stdio 通信，任何支持 MCP 的宿主都可用相同方式接入，只需配置 `command` + `args`：

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

各宿主写法略有差异：

- **OpenCode**：放在项目根 `opencode.jsonc` 的 `"mcp"` 字段（如上）
- **OpenClaw**：在 `claw_config.json` 中注册 MCP server（同样配置 `command`/`args`）
- **Claude Desktop**：在 `claude_desktop_config.json` 的 `"mcpServers"` 字段中注册

### MCP 工作流

```
browser_navigate → browser_snapshot（拿 ref）→ browser_click / browser_input ...
                 → browser_snapshot（拿新 ref）→ ...
```

**始终用 ref 定位元素。每步后调 `browser_snapshot` 确认状态**（DOM 更新后 ref 会失效，需重新 snapshot）。

### 接入已有浏览器

```bash
# 1. 用 --remote-debugging-port 启动日常 Chrome
chrome --remote-debugging-port=9222 --user-data-dir=D:\chrome-debug-profile

# 2. 在 MCP 里扫描并连接
browser_scan      # 探测 9222-9230 端口，发现可用浏览器
browser_connect   # 传入 cdp_endpoint 如 http://127.0.0.1:9222，切换过去
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

```json
{
  "user_data_dir": "~/.config/hyperbrowser/profile",
  "stealth_level": "maximum",
  "channel": "chrome",
  "auto_dialog_handler": true,
  "auto_ssrf_guard": true,
  "ssrf_allowed_hosts": ["example.com"],
  "default_timeout_ms": 30000
}
```

| 配置项 | 环境变量 | 默认值 | 说明 |
|---|---|---|---|
| `user_data_dir` | `HYPERBROWSER_USER_DATA_DIR` | `~/.config/hyperbrowser/profile` | 浏览器 profile 目录 |
| `stealth_level` | `HYPERBROWSER_STEALTH_LEVEL` | `maximum` | 隐身级别 |
| `channel` | `HYPERBROWSER_CHANNEL` | `chrome` | 浏览器渠道 |
| `auto_dialog_handler` | `HYPERBROWSER_AUTO_DIALOG_HANDLER` | `true` | 自动处理对话框 |
| `auto_ssrf_guard` | `HYPERBROWSER_AUTO_SSRF_GUARD` | `true` | SSRF 防护 |
| `ssrf_allowed_hosts` | `HYPERBROWSER_SSRF_ALLOWED_HOSTS` | 无 | SSRF 白名单（逗号分隔） |
| `cdp_endpoint` | `HYPERBROWSER_CDP_ENDPOINT` | 无 | 连接已有浏览器 |
| `default_timeout_ms` | — | `30000` | 默认超时 |

> 提示：把 `user_data_dir` 设为日常 Chrome 的 User Data 目录时，需先关闭日常 Chrome（lockfile 冲突），启动 HyperBrowser 接管后再使用。

## 测试

```bash
python tests/test_minimal_patchright.py   # 验证 patchright 启动
python tests/test_minimal_stealth.py      # 验证反检测/隐身模式
```

## 许可证

MIT
