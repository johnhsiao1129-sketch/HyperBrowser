"""
HyperBrowser Agent 主类
提供三层架构：
第1层：声明式 API（plan.xxx().xxx().execute()）
第2层：操作图谱模板（预定义常用操作）
第3层：批处理执行器（核心引擎）
"""

import json
from typing import Optional, List, Dict, Any

try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None

from .core.browser import StealthBrowserManager
from .core.executor import BatchExecutor
from .core.snapshot import SnapshotExtractor
from .models.schemas import (
    Action,
    ActionType,
    BatchPlan,
    BatchResult,
    LocatorType,
    PageSnapshot,
)
from .plan import OperationPlan, ExecutionResult
from .templates import TemplateRegistry, registry as global_registry
from .dialog_handler import DialogHandler
from .ssrf_guard import SsrfGuard
from .hostname_allowlist import HostnameAllowlist
from .profile_manager import ProfileManager
from .browser_doctor import BrowserDoctor
from .enhanced_actions import EnhancedActionDispatcher


class HyperBrowserAgent:
    """
    HyperBrowser Agent 主类（三层架构）

    第1层 - 声明式 API：
    plan = agent.plan().navigate(url).click(btn).execute()

    第2层 - 模板系统：
    plan = agent.use_template("Baidu_search", keyword="xxx")

    第3层 - 批处理执行器：
    result = await agent.execute_actions([...])

    第4层 - 实时控制模式：
    snapshot = await agent.click(selector)  # 每步返回快照

    可以轻松集成到 OpenClaw、OpenCode 等框架中。
    """

    def __init__(
        self,
        user_data_dir: str = "./hyperbrowser_profile",
        headless: bool = False,
        stealth_level: str = "maximum",
        llm_client: Optional[Any] = None,
        verbose: bool = True,
        templates_registry: Optional[TemplateRegistry] = None,
        cdp_endpoint: Optional[str] = None,
        channel: Optional[str] = None,
        dialog_handler: Optional[DialogHandler] = None,
        ssrf_guard: Optional[SsrfGuard] = None,
        hostname_allowlist: Optional[HostnameAllowlist] = None,
        profile_manager: Optional[ProfileManager] = None,
        auto_install_dialog_handler: bool = False,
        auto_install_ssrf_guard: bool = False,
    ):
        self.user_data_dir = user_data_dir
        self.headless = headless
        self.stealth_level = stealth_level
        self.llm_client = llm_client
        self.verbose = verbose
        self._registry = templates_registry or global_registry
        self.cdp_endpoint = cdp_endpoint
        self.channel = channel

        self.dialog_handler = dialog_handler
        self.ssrf_guard = ssrf_guard
        self.hostname_allowlist = hostname_allowlist
        self.profile_manager = profile_manager or ProfileManager()
        self.auto_install_dialog_handler = auto_install_dialog_handler
        self.auto_install_ssrf_guard = auto_install_ssrf_guard

        self._browser_manager: Optional[StealthBrowserManager] = None
        self._executor: Optional[BatchExecutor] = None
        self._snapshot_extractor: Optional[SnapshotExtractor] = None
        self._action_dispatcher: Optional[EnhancedActionDispatcher] = None

    async def start(self) -> "HyperBrowserAgent":
        """启动 Agent（支持新浏览器或连接已有浏览器）"""
        self._browser_manager = StealthBrowserManager(
            user_data_dir=self.user_data_dir,
            headless=self.headless,
            stealth_level=self.stealth_level,
            cdp_endpoint=self.cdp_endpoint,
            channel=self.channel,
            verbose=self.verbose,
        )

        if self.cdp_endpoint:
            page = await self._browser_manager.connect_over_cdp(self.cdp_endpoint)
        else:
            page = await self._browser_manager.start()

        self._executor = BatchExecutor(page, humanize=True)
        self._snapshot_extractor = SnapshotExtractor(page)
        self._action_dispatcher = EnhancedActionDispatcher(page)

        if self.dialog_handler is None and self.auto_install_dialog_handler:
            self.dialog_handler = DialogHandler(mode="accept", log=self.verbose)
        if self.dialog_handler is not None:
            await self.dialog_handler.install(page)
            if self.verbose:
                print(f"[HyperBrowser] Dialog handler installed (mode={self.dialog_handler.mode})")

        if self.ssrf_guard is None and self.auto_install_ssrf_guard:
            self.ssrf_guard = SsrfGuard(allow_private_network=False)
        if self.ssrf_guard is not None:
            await self.ssrf_guard.install(page)
            if self.verbose:
                print(f"[HyperBrowser] SSRF guard installed (allow_private_network={self.ssrf_guard.allow_private_network})")

        # 提前注册 console listener（lazy 模式会漏掉前面的消息）
        try:
            self._console_messages: list = []
            self._console_event_count = 0
            def _on_console(msg):
                try:
                    self._console_event_count += 1
                    if self._console_event_count <= 3 and self.verbose:
                        print(f"[HyperBrowser] console event: {getattr(msg, 'type', '?')}: {getattr(msg, 'text', str(msg))[:80]}")
                    self._console_messages.append({
                        "type": getattr(msg, "type", "log"),
                        "text": getattr(msg, "text", str(msg)),
                        "url": page.url,
                    })
                except Exception:
                    pass
            page.on("console", _on_console)
        except Exception:
            pass

        if self.verbose:
            if self.cdp_endpoint:
                print(f"[HyperBrowser] Connected to existing browser at {self.cdp_endpoint}")
            else:
                print(f"[HyperBrowser] Browser started with stealth level: {self.stealth_level}")
                print(f"[HyperBrowser] User data directory: {self.user_data_dir}")

        return self

    async def attach_to_tab(self, url_contains: str = None, index: int = None) -> "HyperBrowserAgent":
        """
        附加到已存在的浏览器标签页（通过 CDP）

        通过 CDP 连接到本地 Chrome (http://127.0.0.1:9222)，
        遍历所有标签页，找到匹配的并附加。

        用法：
        # 方式1：通过 URL 包含的字符串查找
        await agent.attach_to_tab(url_contains="liepin.com")

        # 方式2：通过索引直接指定
        await agent.attach_to_tab(index=2)

        # 方式3：先获取所有标签页，再选择
        pages = await agent.list_tabs()
        await agent.attach_to_tab(index=0)

        Args:
            url_contains: URL 包含的字符串，用于匹配标签页
            index: 直接指定标签页索引（0-based）

        Returns:
            HyperBrowserAgent: 返回 self，支持链式调用

        Raises:
            ValueError: 未找到匹配的标签页
        """
        if self._browser_manager is None:
            self._browser_manager = StealthBrowserManager(
                user_data_dir=self.user_data_dir,
                headless=self.headless,
                stealth_level=self.stealth_level,
                verbose=self.verbose,
            )

        page = await self._browser_manager.attach_to_tab(url_contains, index)

        self._executor = BatchExecutor(page, humanize=True)
        self._snapshot_extractor = SnapshotExtractor(page)

        if self.verbose:
            print(f"[HyperBrowser] Attached to tab: {page.url}")

        return self

    async def list_tabs(self) -> List[Dict[str, Any]]:
        """
        列出所有可用的浏览器标签页（通过 CDP）

        需要先通过 CDP 连接到浏览器才能使用。
        建议配合 attach_to_tab 使用。

        用法：
        tabs = await agent.list_tabs()
        for i, tab in enumerate(tabs):
            print(f"{i}: {tab['url']}")

        # 选择第二个标签页
        await agent.attach_to_tab(index=1)

        Returns:
            List[Dict]: 标签页列表，每项包含 url, title 等信息
        """
        if self._browser_manager is None:
            self._browser_manager = StealthBrowserManager(
                user_data_dir=self.user_data_dir,
                headless=self.headless,
                stealth_level=self.stealth_level,
                verbose=False,
            )

        return await self._browser_manager.list_tabs()

    async def close(self):
        """关闭 Agent"""
        if self._browser_manager:
            await self._browser_manager.close()
        if self.verbose:
            print("[HyperBrowser] Browser closed")

    async def get_content_after_render(self, selector: str = None, timeout: int = 10000) -> str:
        """
        获取页面内容（等待 JavaScript 渲染完成后）

        用法：
        # 等待特定元素出现
        content = await agent.get_content_after_render('.job-card-box')

        # 等待网络空闲
        content = await agent.get_content_after_render()

        Args:
            selector: 等待的元素选择器（可选）
            timeout: 超时时间（毫秒）

        Returns:
            str: 页面 HTML 内容
        """
        if not self._browser_manager:
            raise RuntimeError("Agent not started. Call start() first.")
        return await self._browser_manager.get_content_after_render(selector, timeout)

    async def get_snapshot(self) -> PageSnapshot:
        """获取当前页面快照"""
        if not self._snapshot_extractor:
            raise RuntimeError("Agent not started. Call start() first.")
        return await self._snapshot_extractor.extract()

    async def navigate(self, url: str) -> BatchResult:
        """导航到指定 URL"""
        if not self._executor:
            raise RuntimeError("Agent not started. Call start() first.")

        plan = BatchPlan(
            actions=[Action(type=ActionType.NAVIGATE, value=url, wait_after=1000)],
            stop_on_error=True,
        )
        return await self._executor.execute_batch(plan)

    async def execute_actions(self, actions: List[Dict[str, Any]]) -> BatchResult:
        """
        执行操作序列（核心 API）

        Args:
            actions: 操作列表，每个操作包含 type, locator, value 等字段

        Returns:
            BatchResult: 包含执行结果和最终页面快照
        """
        if not self._executor:
            raise RuntimeError("Agent not started. Call start() first.")

        parsed_actions = []
        for action_dict in actions:
            action = Action(
                type=ActionType(action_dict["type"]),
                locator=action_dict.get("locator"),
                value=action_dict.get("value"),
                wait_after=action_dict.get("wait_after", 500),
                description=action_dict.get("description", ""),
            )
            parsed_actions.append(action)

        plan = BatchPlan(actions=parsed_actions)
        result = await self._executor.execute_batch(plan)

        if self.verbose:
            status = "✓" if result.success else "✗"
            print(f"[HyperBrowser] Batch execution {status} ({len(result.completed_actions)}/{len(parsed_actions)} actions, {result.execution_time_ms:.0f}ms)")
            if not result.success:
                print(f"[HyperBrowser] Failed: {result.failed_action} - {result.error_message}")

        return result

    # ========================================================================
    # 第4层：实时控制模式（类似 OpenClaw 单步操作）
    # 每步操作后返回快照，供 AI 实时决策
    # ========================================================================

    async def click(self, selector: Optional[str] = None, timeout: int = 5000, ref: Optional[str] = None) -> PageSnapshot:
        """
        点击元素并返回快照（实时控制模式）

        用法：
        snapshot = await agent.click("#submit")
        # 或通过快照 ref 定位（实时控制模式常用）：
        snapshot = await agent.click(ref="ref_3")

        Args:
            selector: CSS 选择器（与 ref 二选一）
            timeout: 超时时间(ms)
            ref: 快照中的元素 ref（与 selector 二选一，优先 ref）

        Returns:
            PageSnapshot: 操作后的页面快照
        """
        if not self._executor:
            raise RuntimeError("Agent not started. Call start() first.")

        if ref:
            locator = {"type": LocatorType.REF.value, "value": ref}
            description = f"点击 ref {ref}"
        else:
            locator = {"type": "css", "value": selector}
            description = f"点击 {selector}"
        action = Action(
            type=ActionType.CLICK,
            locator=locator,
            description=description
        )
        await self._executor._execute_action(action)
        return await self.get_snapshot()

    async def input(self, selector: str, text: str, timeout: int = 5000) -> PageSnapshot:
        """
        输入文本并返回快照（实时控制模式）

        用法：
        snapshot = await agent.input("#kw", "Python工程师")

        Args:
            selector: CSS 选择器
            text: 输入的文本
            timeout: 超时时间(ms)

        Returns:
            PageSnapshot: 操作后的页面快照
        """
        if not self._executor:
            raise RuntimeError("Agent not started. Call start() first.")

        action = Action(
            type=ActionType.TYPE,
            locator={"type": "css", "value": selector},
            value=text,
            description=f"输入到 {selector}"
        )
        await self._executor._execute_action(action)
        return await self.get_snapshot()

    async def wait(self, ms: int = 1000) -> PageSnapshot:
        """
        等待并返回快照（实时控制模式）

        用法：
        snapshot = await agent.wait(2000)

        Args:
            ms: 等待时间(毫秒)

        Returns:
            PageSnapshot: 等待后的页面快照
        """
        if not self._executor:
            raise RuntimeError("Agent not started. Call start() first.")

        action = Action(
            type=ActionType.WAIT,
            value=str(ms),
            description=f"等待 {ms}ms"
        )
        await self._executor._execute_action(action)
        return await self.get_snapshot()

    async def scroll(self, pixels: int = 0, timeout: int = 5000) -> PageSnapshot:
        """
        滚动页面并返回快照（实时控制模式）

        用法：
        snapshot = await agent.scroll(500) # 滚动 500px
        snapshot = await agent.scroll() # 滚动一个屏幕高度

        Args:
            pixels: 滚动像素，0 表示滚动一个屏幕高度
            timeout: 超时时间(ms)

        Returns:
            PageSnapshot: 滚动后的页面快照
        """
        if not self._executor:
            raise RuntimeError("Agent not started. Call start() first.")

        action = Action(
            type=ActionType.SCROLL,
            value=str(pixels) if pixels else "",
            description=f"滚动 {pixels or '一个屏幕'} 像素"
        )
        await self._executor._execute_action(action)
        return await self.get_snapshot()

    async def hover(self, selector: str, timeout: int = 5000) -> PageSnapshot:
        """
        悬停元素并返回快照（实时控制模式）

        用法：
        snapshot = await agent.hover(".menu-item")

        Args:
            selector: CSS 选择器
            timeout: 超时时间(ms)

        Returns:
            PageSnapshot: 悬停后的页面快照
        """
        if not self._executor:
            raise RuntimeError("Agent not started. Call start() first.")

        action = Action(
            type=ActionType.HOVER,
            locator={"type": "css", "value": selector},
            description=f"悬停 {selector}"
        )
        await self._executor._execute_action(action)
        return await self.get_snapshot()

    async def press(self, key: str, timeout: int = 5000) -> PageSnapshot:
        """
        按键并返回快照（实时控制模式）

        用法：
        snapshot = await agent.press("Enter")
        snapshot = await agent.press("Escape")

        Args:
            key: 按键名称（如 "Enter", "Escape", "Tab"）
            timeout: 超时时间(ms)

        Returns:
            PageSnapshot: 按键后的页面快照
        """
        if not self._executor:
            raise RuntimeError("Agent not started. Call start() first.")

        action = Action(
            type=ActionType.PRESS,
            value=key,
            description=f"按键 {key}"
        )
        await self._executor._execute_action(action)
        return await self.get_snapshot()

    async def select(self, selector: str, value: str, timeout: int = 5000) -> PageSnapshot:
        """
        下拉选择并返回快照（实时控制模式）

        用法：
        snapshot = await agent.select("#city", "北京")

        Args:
            selector: CSS 选择器
            value: 选项值
            timeout: 超时时间(ms)

        Returns:
            PageSnapshot: 选择后的页面快照
        """
        if not self._executor:
            raise RuntimeError("Agent not started. Call start() first.")

        action = Action(
            type=ActionType.SELECT,
            locator={"type": "css", "value": selector},
            value=value,
            description=f"选择 {selector} = {value}"
        )
        await self._executor._execute_action(action)
        return await self.get_snapshot()

    async def execute_js(self, script: str) -> PageSnapshot:
        """
        执行 JavaScript 并返回快照（实时控制模式）

        用法：
        result = await agent.execute_js("window.scrollTo(0, 500)")
        snapshot = await agent.get_snapshot()

        Args:
            script: JavaScript 代码

        Returns:
            PageSnapshot: 执行后的页面快照
        """
        if not self._executor:
            raise RuntimeError("Agent not started. Call start() first.")

        action = Action(
            type=ActionType.EXECUTE_JS,
            value=script,
            description="执行 JS"
        )
        await self._executor._execute_action(action)
        return await self.get_snapshot()

    async def evaluate_js(self, script: str) -> Any:
        """
        执行 JavaScript 并直接返回数据（用于数据提取）

        用法：
        # 获取页面标题
        title = await agent.evaluate_js("document.title")

        # 执行复杂的数据提取
        job_info = await agent.evaluate_js('''
        () => {
            const job = document.querySelector('.job-title');
            const salary = document.querySelector('.salary');
            return {
                title: job?.textContent?.trim(),
                salary: salary?.textContent?.trim()
            };
        }
        ''')

        Args:
            script: JavaScript 代码（建议使用箭头函数返回数据）

        Returns:
            Any: JavaScript 执行结果
        """
        if not self._browser_manager:
            raise RuntimeError("Agent not started. Call start() first.")

        result = await self.page.evaluate(script)
        return result

    async def evaluate_js_raw(self, script: str) -> Any:
        """
        执行原始 JavaScript 代码并返回结果

        与 evaluate_js 的区别：这个方法直接返回 JavaScript 的原始返回值，
        不做任何处理，适合返回复杂对象或需要保留原始类型的情况。

        用法：
        result = await agent.evaluate_js_raw("window.location.href")

        Args:
            script: JavaScript 代码

        Returns:
            Any: JavaScript 原始返回值
        """
        if not self._browser_manager:
            raise RuntimeError("Agent not started. Call start() first.")

        return await self.page.evaluate(script)

    async def execute_with_llm_planning(
        self,
        task: str,
        max_actions: int = 20,
    ) -> BatchResult:
        """
        使用 LLM 规划并执行任务（高级 API）

        LLM 只需要调用一次，生成完整的操作计划，然后本地执行器逐条执行。
        """
        if not self.llm_client:
            raise ValueError("LLM client is required for planning")
        if not self._snapshot_extractor or not self._executor:
            raise RuntimeError("Agent not started. Call start() first.")

        snapshot = await self.get_snapshot()
        snapshot_text = self._snapshot_extractor.format_for_llm(snapshot)

        system_prompt = """You are a browser automation agent. Given a task and the current page state,
generate a sequence of browser actions to accomplish the task.

Available action types:
- navigate: go to a URL (value: url)
- click: click an element (locator: {type: "text"/"ref"/"placeholder", value: ...})
- type: type text into an input (locator: ..., value: text)
- scroll: scroll the page (value: pixels or null for one screen)
- wait: wait for milliseconds (value: ms)
- press: press a keyboard key (value: key name)
- hover: hover over an element (locator: ...)

Respond with a JSON array of actions. Each action should have:
- "type": string
- "locator": object with "type" and "value" (optional for navigate/wait)
- "value": string (optional)
- "description": string (short description of what this action does)"""

        user_prompt = f"""Current page snapshot:
{snapshot_text}

Task: {task}

Generate a sequence of browser actions to complete this task. Maximum {max_actions} actions."""

        response = await self.llm_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )

        try:
            actions_json = json.loads(response.choices[0].message.content)
            actions = actions_json.get("actions", []) if isinstance(actions_json, dict) else actions_json
        except json.JSONDecodeError:
            raise ValueError("Failed to parse LLM response")

        if self.verbose:
            print(f"[HyperBrowser] LLM generated {len(actions)} actions for task: {task}")

        return await self.execute_actions(actions)

    async def check_stealth_status(self) -> Dict[str, Any]:
        """检查当前浏览器的隐形状态"""
        if not self._browser_manager:
            raise RuntimeError("Agent not started. Call start() first.")
        return await self._browser_manager.check_stealth_status()

    async def doctor(self) -> Dict[str, Any]:
        """
        浏览器健康自检 - 输出结构化报告

        检查项：
        - 浏览器是否启动
        - profile 目录可写性
        - dialog handler 是否安装
        - SSRF guard 是否安装
        - CDP endpoint 是否可达
        - 反检测状态（webdriver/chrome/plugins）
        - tabs 能否列出
        """
        if not self._browser_manager:
            raise RuntimeError("Agent not started. Call start() first.")
        doctor = BrowserDoctor(
            manager=self._browser_manager,
            dialog_handler=self.dialog_handler,
            ssrf_guard=self.ssrf_guard,
            profile_manager=self.profile_manager,
        )
        return await doctor.run()

    @property
    def action_dispatcher(self) -> EnhancedActionDispatcher:
        """访问增强动作调度器（drag/doubleClick/slowly/fill/upload 等）"""
        if not self._action_dispatcher:
            raise RuntimeError("Agent not started. Call start() first.")
        return self._action_dispatcher

    @property
    def page(self):
        """直接访问页面对象"""
        if not self._browser_manager:
            raise RuntimeError("Agent not started. Call start() first.")
        return self._browser_manager.page

    @property
    def executor(self) -> BatchExecutor:
        """直接访问执行器"""
        if not self._executor:
            raise RuntimeError("Agent not started. Call start() first.")
        return self._executor

    # ========================================================================
    # 第1层：声明式 API（链式调用）
    # ========================================================================

    def plan(self) -> OperationPlan:
        """
        创建操作计划（声明式 API）

        用法：
        result = await agent.plan()\\
            .navigate("https://example.com")\\
            .input("#search", "keyword")\\
            .click("#submit")\\
            .execute()

        Returns:
            OperationPlan: 可链式调用的操作计划
        """
        return OperationPlan(_agent=self)

    def do(self, url: str = None) -> OperationPlan:
        """
        快速开始操作计划

        用法：
        result = await agent.do("https://baidu.com").input("#kw", "test").execute()
        """
        plan = OperationPlan(_agent=self)
        if url:
            plan.navigate(url)
        return plan

    # ========================================================================
    # 第2层：模板系统
    # ========================================================================

    def use_template(self, template_name: str, **params) -> OperationPlan:
        """
        使用预定义模板

        用法：
        result = await agent.use_template("Baidu_search", keyword="test").execute()

        Args:
            template_name: 模板名称（如 "Baidu_search", "Google_search"）
            **params: 模板参数

        Returns:
            OperationPlan: 填充了模板步骤的操作计划
        """
        template = self._registry.get(template_name)
        if not template:
            available = [t.name for t in self._registry.list()]
            raise ValueError(f"Template '{template_name}' not found. Available: {available}")

        return template(self, **params)

    def list_templates(self, category: str = None) -> List[str]:
        """列出可用模板"""
        return [t.name for t in self._registry.list(category=category)]

    def register_template(self, template):
        """注册自定义模板"""
        self._registry.register(template)

    # ========================================================================
    # 便捷方法
    # ========================================================================

    async def quick_search(self, site: str, keyword: str) -> ExecutionResult:
        """
        快速搜索（最常用的操作）

        用法：
        result = await agent.quick_search("baidu", "测试")
        links = result.get_links()
        """
        template_map = {
            "baidu": "Baidu_search",
            "google": "Google_search",
            "bing": "Bing_search",
            "taobao": "Taobao_search",
        }

        template_name = template_map.get(site.lower())
        if not template_name:
            raise ValueError(f"Unknown site: {site}. Use: {list(template_map.keys())}")

        return await self.use_template(template_name, keyword=keyword).execute()

    async def quick_login(self, site: str, username: str, password: str) -> ExecutionResult:
        """快速登录"""
        template_name = f"{site}_login"
        return await self.use_template(template_name, username=username, password=password).execute()

