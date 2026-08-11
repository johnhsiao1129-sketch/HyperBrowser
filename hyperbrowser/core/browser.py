"""
HyperBrowser 隐形浏览器管理器
使用 Patchright 实现反检测浏览器自动化
"""

import asyncio
from typing import Optional, Dict, List, Any

try:
    from patchright.async_api import async_playwright, Page, BrowserContext, Browser
except ImportError:
    from playwright.async_api import async_playwright, Page, BrowserContext, Browser


class StealthBrowserManager:
    """
    隐形浏览器管理器

    核心反检测配置：
    - 使用 Patchright（Playwright 补丁版）代替原生 Playwright
    - 使用真实 Chrome 而非 Chromium
    - 持久化用户数据目录，保留浏览器指纹的一致性
    - 禁用自动化控制标志
    """

    STEALTH_LEVELS = ["standard", "maximum", "paranoid"]

    def __init__(
        self,
        user_data_dir: str = "./hyperbrowser_profile",
        headless: bool = False,
        viewport: Optional[Dict[str, int]] = None,
        stealth_level: str = "maximum",
        cdp_endpoint: Optional[str] = None,
        channel: Optional[str] = None,
        verbose: bool = True,
    ):
        self.user_data_dir = user_data_dir
        self.headless = headless
        self.viewport = viewport or {"width": 1920, "height": 1080}
        self.stealth_level = stealth_level
        self.cdp_endpoint = cdp_endpoint
        self.channel = channel
        self.verbose = verbose

        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._connected = False

    async def _get_stealth_launch_args(self) -> List[str]:
        """获取反检测启动参数"""
        args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-automation",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-web-security",
            "--disable-features=IsolateOrigins,site-per-process",
            "--disable-component-extensions-with-background-pages",
            "--disable-default-apps",
            "--disable-extensions",
            "--disable-sync",
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--disable-ipc-flooding-protection",
        ]

        if self.headless:
            args.extend([
                "--headless=new",
                "--window-size=1920,1080",
            ])

        if self.stealth_level in ["maximum", "paranoid"]:
            args.extend([
                "--disable-features=VizDisplayCompositor",
                "--disable-gpu",
                "--hide-scrollbars",
                "--mute-audio",
                "--no-first-run",
                "--disable-infobars",
                "--disable-breakpad",
            ])

        return args

    async def _inject_stealth_scripts(self):
        """注入隐形 JavaScript 脚本，修补指纹泄漏点"""
        stealth_scripts = [
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});",
            "window.chrome = {runtime: {}, loadTimes: function(){}, csi: function(){}, app: {}};",
            """
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                Promise.resolve({state: Notification.permission}) :
                originalQuery(parameters)
            );
            """,
            """
            Object.defineProperty(navigator, 'plugins', {
                get: () => {
                    const plugins = [];
                    for (let i = 0; i < 5; i++) {
                        plugins.push({
                            name: `Plugin ${i}`,
                            filename: `plugin${i}.dll`,
                            description: `Plugin ${i} description`,
                            length: 1,
                            item: () => null,
                            namedItem: () => null
                        });
                    }
                    plugins.length = 5;
                    return plugins;
                }
            });
            """,
            "Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en-US', 'en']});",
        ]

        for script in stealth_scripts:
            await self._page.add_init_script(script)

    async def start(self) -> Page:
        """启动隐形浏览器"""
        self._playwright = await async_playwright().start()

        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=self.user_data_dir,
            channel=self.channel or "chrome",
            headless=self.headless,
            viewport=self.viewport,
            args=await self._get_stealth_launch_args(),
            accept_downloads=True,
            java_script_enabled=True,
            bypass_csp=True,
            ignore_https_errors=True,
        )

        self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()
        await self._inject_stealth_scripts()
        self._page.set_default_timeout(30000)

        return self._page

    async def close(self):
        """关闭浏览器"""
        # 修复转圈根因 (2026-08-12): CDP 模式 (连接外部 Chrome) 下
        # 不能调用 self._context.close() —— context 属于外部浏览器进程，
        # 调用会触发 "BrowserContext.close: 'NoneType' object has no attribute
        # 'send'" (patchright 1.58.2 长 CDP session RPC hang)，子进程不退出
        # → CDP 连接不释放 → 浏览器 tab 冻结一直转圈。
        # CDP 模式只 stop playwright driver 干净断开即可。
        if self._context and not self._connected:
            await self._context.close()
        if self._playwright:
            try:
                # stop() 也是 RPC 调用，长 CDP session 后 driver RPC 可能已坏
                # 同样会 hang → 子进程不退出 → CDP 不释放 → tab 冻结。
                # 加 10s 超时: 卡住就放弃，进程退出时 OS 终止 driver。
                await asyncio.wait_for(self._playwright.stop(), timeout=10)
            except Exception:
                pass
            self._playwright = None

    @property
    def page(self) -> Page:
        """获取当前页面"""
        if not self._page:
            raise RuntimeError("Browser not started. Call start() first.")
        return self._page

    async def new_page(self) -> Page:
        """创建新页面"""
        if not self._context:
            raise RuntimeError("Browser not started. Call start() first.")
        self._page = await self._context.new_page()
        await self._inject_stealth_scripts()
        return self._page

    async def check_stealth_status(self) -> Dict:
        """检查当前浏览器的隐形状态"""
        if not self._page:
            return {"error": "Browser not started"}

        return await self._page.evaluate("""
        () => ({
            webdriver: navigator.webdriver,
            chrome_exists: typeof window.chrome !== 'undefined',
            chrome_runtime: typeof window.chrome?.runtime !== 'undefined',
            plugins_length: navigator.plugins.length,
            languages: navigator.languages,
            user_agent: navigator.userAgent,
        })
        """)

    async def _cdp_connect(self, cdp_url: str, timeout: float = 30.0, operation: str = "connect_over_cdp") -> Browser:
        """
        连接外部 Chrome（CDP），带超时保护。

        上一个子进程刚退出时 CDP websocket 可能半关闭（连接未完全释放），
        connect_over_cdp() 内部无超时会无限等待 → 浏览器 tab 冻结转圈。
        统一走本 helper：start() 与 connect_over_cdp() 均用 asyncio.wait_for
        包裹；超时抛 TimeoutError（带操作名 + cdp_url），并清理半初始化现场。
        """
        try:
            self._playwright = await asyncio.wait_for(
                async_playwright().start(), timeout=timeout
            )
            browser = await asyncio.wait_for(
                self._playwright.chromium.connect_over_cdp(cdp_url), timeout=timeout
            )
        except (asyncio.TimeoutError, TimeoutError):
            await self._reset_after_cdp_failure()
            raise TimeoutError(f"{operation} timeout after {timeout:g}s: {cdp_url}")
        except Exception:
            await self._reset_after_cdp_failure()
            raise
        return browser

    async def _reset_after_cdp_failure(self):
        """CDP 连接失败/超时后清理现场，避免半初始化状态污染后续重试。"""
        pw = self._playwright
        self._playwright = None
        self._connected = False
        self._context = None
        self._page = None
        if pw is not None:
            try:
                await asyncio.wait_for(pw.stop(), timeout=5)
            except Exception:
                pass

    async def connect_over_cdp(self, cdp_url: str) -> Page:
        """
        连接到已存在的浏览器（通过 CDP）

        用法：
        manager = StealthBrowserManager()
        await manager.connect_over_cdp("http://127.0.0.1:9222")

        Args:
            cdp_url: CDP 端点 URL，如 "http://127.0.0.1:9222"

        Returns:
            Page: 连接后的页面对象
        """
        browser = await self._cdp_connect(cdp_url)
        self._context = browser.contexts[0] if browser.contexts else await browser.new_context()
        self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()

        await self._inject_stealth_scripts()
        self._page.set_default_timeout(30000)
        self._connected = True

        if self.verbose:
            print(f"[HyperBrowser] Connected to existing browser at {cdp_url}")
            print(f"[HyperBrowser] Page URL: {self._page.url}")

        return self._page

    async def list_tabs(self) -> List[Dict[str, Any]]:
        """
        列出所有浏览器标签页。

        优先使用当前 context（launch_persistent_context 模式）。
        若未启动过浏览器，回退到 CDP 9222（外部 Chrome --remote-debugging-port）。

        Returns:
            List[Dict]: 标签页列表，每项包含 url, title
        """
        # 优先使用当前 context
        if self._context is not None:
            tabs = []
            for i, page in enumerate(self._context.pages):
                try:
                    title = await page.title()
                except Exception:
                    title = None
                tabs.append({
                    "index": i,
                    "url": page.url,
                    "title": title,
                })
            return tabs

        # 回退：外部 CDP
        browser = await self._cdp_connect("http://127.0.0.1:9222", operation="list_tabs")

        tabs = []
        pages = browser.contexts[0].pages if browser.contexts else []
        for i, page in enumerate(pages):
            try:
                tabs.append({
                    "index": i,
                    "url": page.url,
                    "title": await page.title() if page else None,
                })
            except Exception:
                tabs.append({"index": i, "url": page.url, "title": None})

        await browser.close()
        if self._playwright is not None:
            await self._playwright.stop()
        self._playwright = None

        return tabs

    async def attach_to_tab(self, url_contains: Optional[str] = None, index: Optional[int] = None) -> Page:
        """
        附加到已存在的浏览器标签页（通过 CDP）

        通过 CDP 连接到本地 Chrome (http://127.0.0.1:9222)，
        使用 Target.attachToTarget 真正附加到目标标签页。

        用法：
        # 方式1：通过 URL 包含的字符串查找
        page = await manager.attach_to_tab(url_contains="liepin.com")

        # 方式2：通过索引直接指定
        page = await manager.attach_to_tab(index=2)

        Args:
            url_contains: URL 包含的字符串，用于匹配标签页
            index: 直接指定标签页索引（0-based）

        Returns:
            Page: 附加后的页面对象

        Raises:
            ValueError: 未找到匹配的标签页
        """
        browser = await self._cdp_connect("http://127.0.0.1:9222", operation="attach_to_tab")
        context = browser.contexts[0] if browser.contexts else await browser.new_context()

        # FIX (v2): Bypass Target.attachToTarget entirely. The previous
        # `Target.attachToTarget` + `contexts[0].pages[0]` combination returned
        # a Page whose internal CDP channel was a different object than the one
        # used by connect_over_cdp, causing navigate() to fail with
        # 'NoneType' object has no attribute 'send'.
        # We now use the page directly from browser.contexts — patchright wires
        # the CDP channel correctly when we use these page objects.

        page_url = None
        if index is not None:
            page_targets = list(context.pages)
            if index < 0 or index >= len(page_targets):
                raise ValueError(
                    f"Tab index {index} out of range (found {len(page_targets)} tabs)"
                )
            self._page = page_targets[index]
            page_url = self._page.url
        elif url_contains:
            for page in context.pages:
                if url_contains in page.url:
                    self._page = page
                    page_url = page.url
                    break
            if not self._page:
                available = [p.url for p in context.pages]
                raise ValueError(
                    f"No tab found containing '{url_contains}'. Available: {available}"
                )
        else:
            # No filter: pick the first page (the one Chrome opened by default).
            if context.pages:
                self._page = context.pages[0]
                page_url = self._page.url
            else:
                self._page = await context.new_page()
                page_url = self._page.url

        self._browser = browser
        self._context = context
        self._connected = True
        self._cdp_session = None
        self._target_session_id = None

        if self._page:
            await self._inject_stealth_scripts()
            self._page.set_default_timeout(30000)

        if self.verbose:
            print(f"[HyperBrowser] Attached to tab: {page_url}")

        return self._page

    async def connect_over_cdp_with_context(self, cdp_url: str, context_id: str = None) -> tuple:
        """
        连接到已存在的浏览器上下文（通过 CDP）

        用法：
        manager = StealthBrowserManager()
        context, page = await manager.connect_over_cdp_with_context("http://127.0.0.1:9222")

        Args:
            cdp_url: CDP 端点 URL
            context_id: 可选的上下文 ID

        Returns:
            tuple: (BrowserContext, Page)
        """
        browser = await self._cdp_connect(cdp_url, operation="connect_over_cdp_with_context")

        self._context = browser.contexts[0] if browser.contexts else await browser.new_context()
        self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()

        await self._inject_stealth_scripts()
        self._page.set_default_timeout(30000)
        self._connected = True

        if self.verbose:
            print(f"[HyperBrowser] Connected to browser context at {cdp_url}")
            print(f"[HyperBrowser] Page URL: {self._page.url}")

        return self._context, self._page

    async def get_content_after_render(self, selector: str = None, timeout: int = 10000) -> str:
        """
        获取页面内容（等待 JavaScript 渲染完成后）

        用法：
        # 等待特定元素出现
        content = await browser_manager.get_content_after_render('.job-card-box')

        # 等待网络空闲
        content = await browser_manager.get_content_after_render()

        Args:
            selector: 等待的元素选择器（可选）。如果指定，会等待该元素出现。
            timeout: 超时时间（毫秒）

        Returns:
            str: 页面 HTML 内容
        """
        if not self._page:
            raise RuntimeError("Browser not started. Call start() or connect_over_cdp() first.")

        if selector:
            try:
                await self._page.wait_for_selector(selector, timeout=timeout)
            except Exception:
                pass  # 元素没出现也继续获取内容
        else:
            try:
                await self._page.wait_for_load_state('networkidle', timeout=timeout)
            except Exception:
                pass  # 网络没空闲也继续获取内容

        return await self._page.content()

