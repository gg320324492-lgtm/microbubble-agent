"""Verify SessionSidebar scroll on REMOTE production server (旧 dist, 测 fix 必要)."""
import asyncio
from playwright.async_api import async_playwright

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={'width': 1280, 'height': 800})
        await page.goto('https://agent.mnb-lab.cn/login', wait_until='domcontentloaded')
        await page.wait_for_timeout(2000)
        try:
            await page.fill('input[name="login-username"]', 'wangtianzhi')
            await page.fill('input[name="login-password"]', '123456')
            await page.click('button[type="submit"], button:has-text("登录")')
            await page.wait_for_timeout(4000)
        except Exception as e:
            print(f'login: {e}')
        await page.goto('https://agent.mnb-lab.cn/chat', wait_until='domcontentloaded')
        await page.wait_for_timeout(5000)
        sidebar = page.locator('.session-sidebar')
        count = await sidebar.count()
        print(f'SessionSidebar count: {count}')
        if count > 0:
            box = await sidebar.bounding_box()
            print(f'Sidebar: {box["width"]}x{box["height"]}px @ ({box["x"]},{box["y"]})')
            sl = page.locator('.session-list')
            sl_count = await sl.count()
            if sl_count > 0:
                sl_box = await sl.bounding_box()
                print(f'SessionList: {sl_box["width"]}x{sl_box["height"]}px')
                if sl_box['height'] > 0:
                    print("\n=== 滚轮测试 ===")
                    await sl.evaluate('el => { el.scrollTop = 0 }')
                    before = await sl.evaluate('el => el.scrollTop')
                    await page.mouse.move(sl_box['x'] + sl_box['width']/2, sl_box['y'] + sl_box['height']/2)
                    await page.mouse.wheel(0, 200)
                    await page.wait_for_timeout(500)
                    after = await sl.evaluate('el => el.scrollTop')
                    after = int(after)
                    before = int(before)
                    print(f'scrollTop: before={before} -> after={after}')
                    if after > before:
                        print(f'OK 滚轮有效, 移动 {after-before}px (无需修)')
                    else:
                        print(f'BUG 滚轮失效, scrollTop 没变 (确认需修)')
                    sh = await sl.evaluate('el => el.scrollHeight')
                    ch = await sl.evaluate('el => el.clientHeight')
                    print(f'scrollHeight={int(sh)}px, clientHeight={int(ch)}px ({(int(sh)-int(ch))}px overflow)')
                else:
                    print('SessionList 高度=0 (BUG 确认)')
        await page.screenshot(path='/tmp/remote-sidebar.png', full_page=True)
        await browser.close()

asyncio.run(test())
