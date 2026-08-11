"""Minimal patchright test."""
import asyncio
from patchright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=r"D:\AI\my_programs\HyperBrowser\test_profile_minimal",
            channel="chrome",
            headless=False,
            viewport={"width": 1280, "height": 720},
        )
        page = browser.pages[0] if browser.pages else await browser.new_page()
        print(f"Got page: {page}, url={page.url}")
        await page.goto("https://example.com", wait_until="domcontentloaded")
        print(f"After goto: url={page.url}")
        title = await page.title()
        print(f"Title: {title}")
        await browser.close()

asyncio.run(main())
print("Done")
