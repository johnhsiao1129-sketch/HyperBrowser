"""
HyperBrowser 隐形浏览器管理器
使用 Patchright 实现反检测浏览器自动化
"""

import asyncio
import os
import subprocess
import sys
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
        self._cdp_session = None
        self._target_session_id = None

        # Windows Job Object 句柄 (KILL_ON_JOB_CLOSE): 持有到 manager 生命周期,
        # 防止 GC 关闭句柄触发误杀; 由 _release_driver_jobs() 显式关闭 (= 杀 driver).
        self._driver_job_handles: List[int] = []

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
        self._release_driver_jobs()
        self._playwright = await async_playwright().start()
        self._bind_current_driver()

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
                # 加 10s 超时。
                await asyncio.wait_for(self._playwright.stop(), timeout=10)
            except Exception:
                # 2026-08-12 (二修): stop() 超时/失败 = driver 卡死在 CDP RPC 上，
                # 不会随 python 退出而死 (node.exe 是独立子进程)。残留 driver 占着
                # 9222 的半关闭 websocket → 下一个子进程 attach 撞上就卡 30s×2。
                # 必须强杀，否则成功路径同样污染下一个 CDP 会话。
                await asyncio.to_thread(self._kill_orphan_cdp_drivers)
            self._playwright = None
            # Job Object 兜底: 关闭 handle = 强杀 job 内仍存活的 driver (双保险,
            # 已死进程无副作用)。
            self._release_driver_jobs()

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
        连接外部 Chrome（CDP），带超时保护 + 自动重试 1 次。

        上一个子进程刚退出时 CDP websocket 可能半关闭（连接未完全释放），
        connect_over_cdp() 内部无超时会无限等待 → 浏览器 tab 冻结转圈。
        统一走本 helper：start() 与 connect_over_cdp() 均用 asyncio.wait_for
        包裹；超时抛 TimeoutError（带操作名 + cdp_url），并清理半初始化现场。

        半关闭窗口是瞬时的，超时后清理（含强杀卡死 driver）再重试 1 次，
        通常第二次即成功。
        """
        last_exc: Optional[Exception] = None
        # 清上一轮 driver: KILL_ON_JOB_CLOSE 强杀仍存活的旧 driver → CDP 连接彻底
        # 断开 → 本轮的 connect 永远不会撞上"半关闭 websocket"窗口 (根治转圈根因)。
        self._release_driver_jobs()
        for attempt in range(2):  # 首次 + 自动重试 1 次
            try:
                self._playwright = await asyncio.wait_for(
                    async_playwright().start(), timeout=timeout
                )
                # driver 已 spawn, 立刻绑进 KILL_ON_JOB_CLOSE job (python 死 → driver 必死)
                self._bind_current_driver()
                browser = await asyncio.wait_for(
                    self._playwright.chromium.connect_over_cdp(cdp_url), timeout=timeout
                )
                return browser
            except (asyncio.TimeoutError, TimeoutError):
                await self._reset_after_cdp_failure()
                last_exc = TimeoutError(f"{operation} timeout after {timeout:g}s: {cdp_url}")
                if attempt == 0:
                    await asyncio.sleep(0.5)  # 半关闭窗口瞬时，让 CDP 释放连接后重试
            except Exception:
                await self._reset_after_cdp_failure()
                raise
        raise last_exc or TimeoutError(f"{operation} timeout after {timeout:g}s: {cdp_url}")

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
                # pw.stop() 超时/失败 = driver 卡死在 CDP RPC 上，不响应退出信号。
                # 优雅关闭无效 → 强杀残留 driver（只杀孤儿 + 当前进程的，不误伤
                # MCP server / 其他存活进程的 driver）。
                await asyncio.to_thread(self._kill_orphan_cdp_drivers)

    def _kill_orphan_cdp_drivers(self) -> int:
        """强杀残留 patchright driver (node.exe run-driver)。

        只杀两类（避免误伤 MCP server / 其他并发 job 进程的正常 driver）:
        1. 孤儿: 父进程已不存在 — 上一棒子进程退出后 driver 卡在 CDP RPC 上
           不随 pipe 关闭而死，成为残留；
        2. 当前进程自己的 driver: 父进程 == os.getpid() — pw.stop() 超时 = 卡死。

        返回被杀进程数。
        """
        cur_pid = os.getpid()
        # 用 __CUR_PID__ 占位符而非 .format()：PowerShell 脚本块的 {} 会与
        # format 占位符冲突导致 ValueError。
        ps_cmd = (
            "Get-CimInstance Win32_Process -Filter \"Name='node.exe'\" | "
            "Where-Object { $_.CommandLine -match 'run-driver' -and "
            "($_.ParentProcessId -eq __CUR_PID__ -or "
            "-not (Get-Process -Id $_.ParentProcessId -ErrorAction SilentlyContinue)) } | "
            "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; "
            "$_.ProcessId }"
        ).replace("__CUR_PID__", str(cur_pid))
        try:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=15,
            )
            killed = [p for p in out.stdout.split() if p.strip().isdigit()]
            if killed and self.verbose:
                print(f"[HyperBrowser] Killed stuck CDP driver(s): {', '.join(killed)}")
            return len(killed)
        except Exception:
            return 0

    def _find_driver_pid(self) -> Optional[int]:
        """返回当前进程最新 spawn 的 patchright driver PID (node.exe run-driver)。

        仅 win32 有效; 非 Windows 或未找到返回 None。
        """
        if sys.platform != "win32":
            return None
        ps_cmd = (
            "Get-CimInstance Win32_Process -Filter \"Name='node.exe'\" | "
            "Where-Object { $_.CommandLine -match 'run-driver' -and "
            "$_.ParentProcessId -eq __CUR_PID__ } | "
            "ForEach-Object { $_.ProcessId }"
        ).replace("__CUR_PID__", str(os.getpid()))
        try:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=15,
            )
            pids = [int(p) for p in out.stdout.split() if p.strip().isdigit()]
            return max(pids) if pids else None  # PID 最大 = 最新 spawn
        except Exception:
            return None

    def _bind_driver_to_job(self, driver_pid: int) -> bool:
        """把 driver 进程绑进 KILL_ON_JOB_CLOSE 的 Windows Job Object。

        根治残留 driver 的终极方案 (2026-08-12): python 进程死亡（含崩溃、
        taskkill、sys.exit）→ OS 关闭 job 最后一个 handle → 强杀 job 内进程，
        无论 driver 卡在什么 CDP RPC 上。不再依赖 pw.stop() 优雅退出是否成功。

        handle 存进 self._driver_job_handles 持有（防 GC 误杀）；
        关闭由 _release_driver_jobs() 显式执行（关闭即杀 driver，正是兜底语义）。

        失败（进程已在别的 job 等）→ 返回 False，静默降级到孤儿清理兜底。
        """
        if sys.platform != "win32":
            return False
        try:
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.windll.kernel32
            kernel32.CreateJobObjectW.restype = wintypes.HANDLE
            kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
            kernel32.OpenProcess.restype = wintypes.HANDLE
            kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel32.SetInformationJobObject.argtypes = [
                wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD,
            ]
            kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

            class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ("PerProcessUserTimeLimit", wintypes.LARGE_INTEGER),
                    ("PerJobUserTimeLimit", wintypes.LARGE_INTEGER),
                    ("LimitFlags", wintypes.DWORD),
                    ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t),
                    ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.POINTER(ctypes.c_ulong)),
                    ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD),
                ]

            class IO_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("ReadOperationCount", ctypes.c_ulonglong),
                    ("WriteOperationCount", ctypes.c_ulonglong),
                    ("OtherOperationCount", ctypes.c_ulonglong),
                    ("ReadTransferCount", ctypes.c_ulonglong),
                    ("WriteTransferCount", ctypes.c_ulonglong),
                    ("OtherTransferCount", ctypes.c_ulonglong),
                ]

            class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                    ("IoInfo", IO_COUNTERS),
                    ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t),
                ]

            job = kernel32.CreateJobObjectW(None, None)
            if not job:
                return False
            JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
            JobObjectExtendedLimitInformation = 9
            info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
            info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not kernel32.SetInformationJobObject(
                job, JobObjectExtendedLimitInformation,
                ctypes.byref(info), ctypes.sizeof(info),
            ):
                kernel32.CloseHandle(job)
                return False
            # AssignProcessToJobObject 需要 PROCESS_SET_QUOTA | PROCESS_TERMINATE
            PROCESS_SET_QUOTA = 0x0100
            PROCESS_TERMINATE = 0x0001
            hproc = kernel32.OpenProcess(PROCESS_SET_QUOTA | PROCESS_TERMINATE, False, driver_pid)
            if not hproc:
                kernel32.CloseHandle(job)
                return False
            ok = kernel32.AssignProcessToJobObject(job, hproc)
            kernel32.CloseHandle(hproc)
            if not ok:
                # 进程已在别的 job（如 python 自身在 job 里, node driver 继承）→ 无法再分配。
                # 降级: 不阻断连接, 靠现有孤儿清理兜底。
                kernel32.CloseHandle(job)
                return False
            self._driver_job_handles.append(job)
            if self.verbose:
                print(f"[HyperBrowser] Bound driver pid={driver_pid} to KILL_ON_JOB_CLOSE job")
            return True
        except Exception:
            return False

    def _release_driver_jobs(self):
        """关闭所有持有的 job handle。

        关闭最后一个 handle → KILL_ON_JOB_CLOSE 触发 → job 内仍存活的 driver
        被 OS 强杀。这就是残留根治的兜底: 无论 driver 卡在哪个 RPC, 下一次
        连接开始前 / close() 时必然被清理。已死的进程关闭 handle 无副作用。
        """
        handles = self._driver_job_handles
        self._driver_job_handles = []
        if not handles or sys.platform != "win32":
            return
        try:
            import ctypes
            from ctypes import wintypes
            kernel32 = ctypes.windll.kernel32
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            for h in handles:
                kernel32.CloseHandle(h)
        except Exception:
            pass

    def _bind_current_driver(self):
        """start() 成功后把新 spawn 的 driver 绑进 job。失败静默降级。"""
        if sys.platform != "win32":
            return
        pid = self._find_driver_pid()
        if pid:
            self._bind_driver_to_job(pid)

    async def _guard_post_connect(self, operation: str, coro_fn, timeout: float = 30.0):
        """保护 connect 握手之后的 RPC 序列。

        connect_over_cdp() 握手成功后，browser.contexts[0] / context.pages /
        page.url / _inject_stealth_scripts() 等 RPC 同样可能撞上半关闭 websocket
        无限等待 → 也必须包超时。超时/异常统一 _reset_after_cdp_failure 清理。
        """
        try:
            return await asyncio.wait_for(coro_fn(), timeout=timeout)
        except (asyncio.TimeoutError, TimeoutError):
            await self._reset_after_cdp_failure()
            raise TimeoutError(f"{operation} post-connect RPC timeout after {timeout:g}s")
        except Exception:
            await self._reset_after_cdp_failure()
            raise

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

        async def _init():
            self._context = browser.contexts[0] if browser.contexts else await browser.new_context()
            self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()

            await self._inject_stealth_scripts()
            self._page.set_default_timeout(30000)
            self._connected = True

            if self.verbose:
                print(f"[HyperBrowser] Connected to existing browser at {cdp_url}")
                print(f"[HyperBrowser] Page URL: {self._page.url}")

            return self._page

        return await self._guard_post_connect("connect_over_cdp", _init)

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

        async def _scan():
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
            return tabs

        try:
            tabs = await self._guard_post_connect("list_tabs", _scan)
        finally:
            # 异常路径 _guard_post_connect 已 reset（pw.stop() 已调，self._playwright=None）
            if self._playwright is not None:
                try:
                    await browser.close()
                except Exception:
                    pass
                try:
                    await asyncio.wait_for(self._playwright.stop(), timeout=5)
                except Exception:
                    await asyncio.to_thread(self._kill_orphan_cdp_drivers)
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

        # FIX (v2): Bypass Target.attachToTarget entirely. The previous
        # `Target.attachToTarget` + `contexts[0].pages[0]` combination returned
        # a Page whose internal CDP channel was a different object than the one
        # used by connect_over_cdp, causing navigate() to fail with
        # 'NoneType' object has no attribute 'send'.
        # We now use the page directly from browser.contexts — patchright wires
        # the CDP channel correctly when we use these page objects.

        async def _init():
            context = browser.contexts[0] if browser.contexts else await browser.new_context()

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

        return await self._guard_post_connect("attach_to_tab", _init)

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

        async def _init():
            self._context = browser.contexts[0] if browser.contexts else await browser.new_context()
            self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()

            await self._inject_stealth_scripts()
            self._page.set_default_timeout(30000)
            self._connected = True

            if self.verbose:
                print(f"[HyperBrowser] Connected to browser context at {cdp_url}")
                print(f"[HyperBrowser] Page URL: {self._page.url}")

            return self._context, self._page

        return await self._guard_post_connect("connect_over_cdp_with_context", _init)

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

