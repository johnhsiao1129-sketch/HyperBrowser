"""Test minimal + stealth injection."""
import asyncio
from patchright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=r"D:\AI\my_programs\HyperBrowser\test_profile_real2",
            channel="chrome",
            headless=False,
            viewport={"width": 1920, "height": 1080},
            args=[
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
            ],
            accept_downloads=True,
            java_script_enabled=True,
            bypass_csp=True,
            ignore_https_errors=True,
        )
        page = browser.pages[0] if browser.pages else await browser.new_page()
        print(f"Got page: {page}")

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
            await page.add_init_script(script)
            print(f"  added init script ({len(script)} chars)")

        page.set_default_timeout(30000)
        print(f"set_default_timeout OK")

        print(f"Trying goto...")
        await page.goto("https://example.com", wait_until="domcontentloaded")
        print(f"After goto: url={page.url}")
        title = await page.title()
        print(f"Title: {title}")

        await browser.close()

asyncio.run(main())
print("Done")
