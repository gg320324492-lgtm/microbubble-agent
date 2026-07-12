import { test, expect } from '@playwright/test'

const BASE = 'https://agent.mnb-lab.cn'

test('P0-#2 真实用户流程: 不清状态, hard-reload + 模拟用户视角', async ({ page }) => {
  test.setTimeout(120000)
  // 注意: **不清** localStorage / SW / IDB, 模拟真实用户视角
  await page.goto(`${BASE}/login`)
  await page.waitForTimeout(2000)

  // 登录
  await page.fill('input[placeholder*="用户名"], input[name="username"]', 'dutonghe')
  await page.fill('input[type=password]', '123456')
  await page.locator('button').filter({ hasText: /登录/ }).first().click()
  await page.waitForURL(/dashboard|chat/, { timeout: 10000 })

  await page.goto(`${BASE}/chat`)
  await page.waitForTimeout(4000)

  // 直接点 你好 session
  const target = page.locator('.session-item').filter({ hasText: /你好/ }).first()
  await target.waitFor({ state: 'visible', timeout: 5000 })
  await target.click()
  // 给足时间等 server fetch + render + autoStick
  await page.waitForTimeout(10000)

  console.log('\n========== A. 初始状态 (autoStick 到底) ==========')
  const initial = await page.evaluate(() => {
    const m = document.querySelector('.messages')
    return {
      totalBubbles: document.querySelectorAll('.bubble').length,
      scrollTop: m?.scrollTop,
      scrollHeight: m?.scrollHeight,
      clientHeight: m?.clientHeight,
      jumpTopVisible: !!document.querySelector('#chat-jump-to-top'),
      jumpTopRect: document.querySelector('#chat-jump-to-top')?.getBoundingClientRect(),
      jumpBottomVisible: !!document.querySelector('.jump-to-bottom'),
    }
  })
  console.log(`  total .bubble: ${initial.totalBubbles}`)
  console.log(`  scrollTop: ${initial.scrollTop} / height: ${initial.scrollHeight} (client: ${initial.clientHeight})`)
  console.log(`  ↑ 跳到最早 可见: ${initial.jumpTopVisible}`)
  console.log(`  ↑ 按钮 rect: ${JSON.stringify(initial.jumpTopRect)}`)
  console.log(`  ↓ 跳到最新 可见: ${initial.jumpBottomVisible}`)

  // 截图: 初始 (autoStick 到底)
  await page.screenshot({ path: 'tests/visual/desktop/screenshots/real-1-initial-bottom.png', fullPage: false })

  console.log('\n========== B. 点击 ↑ 跳到最早 ==========')
  if (initial.jumpTopVisible) {
    await page.locator('#chat-jump-to-top').click()
    await page.waitForTimeout(1500)
  } else {
    console.log('  ! ↑ 不可见, 尝试强制 scrollTop=0')
    await page.evaluate(() => {
      const m = document.querySelector('.messages')
      if (m) m.scrollTop = 0
    })
    await page.waitForTimeout(1500)
  }
  const afterClick = await page.evaluate(() => {
    const m = document.querySelector('.messages')
    return {
      scrollTop: m?.scrollTop,
      jumpTopVisible: !!document.querySelector('#chat-jump-to-top'),
      jumpBottomVisible: !!document.querySelector('.jump-to-bottom'),
      firstBubbleContent: document.querySelector('.bubble')?.textContent?.slice(0, 50),
      firstBubbleTop: document.querySelector('.bubble')?.getBoundingClientRect()?.top,
    }
  })
  console.log(`  scrollTop: ${afterClick.scrollTop}`)
  console.log(`  ↑ 可见: ${afterClick.jumpTopVisible}`)
  console.log(`  ↓ 可见: ${afterClick.jumpBottomVisible}`)
  console.log(`  第 1 条 bubble: "${afterClick.firstBubbleContent}"`)
  console.log(`  第 1 条 rect top: ${afterClick.firstBubbleTop}`)

  // 截图: 滚到顶后
  await page.screenshot({ path: 'tests/visual/desktop/screenshots/real-2-after-jump-top.png', fullPage: false })

  console.log('\n========== C. 中间滚动 (验证两个按钮都显示) ==========')
  await page.evaluate(() => {
    const m = document.querySelector('.messages')
    if (m) m.scrollTop = (m.scrollHeight - m.clientHeight) / 2
  })
  await page.waitForTimeout(1500)
  const middle = await page.evaluate(() => {
    const m = document.querySelector('.messages')
    return {
      scrollTop: m?.scrollTop,
      jumpTopVisible: !!document.querySelector('#chat-jump-to-top'),
      jumpBottomVisible: !!document.querySelector('.jump-to-bottom'),
    }
  })
  console.log(`  scrollTop: ${middle.scrollTop}`)
  console.log(`  ↑ 可见: ${middle.jumpTopVisible}`)
  console.log(`  ↓ 可见: ${middle.jumpBottomVisible}`)
  await page.screenshot({ path: 'tests/visual/desktop/screenshots/real-3-middle.png', fullPage: false })

  console.log('\n========== D. 最终全页 + chat 区域独立截图 ==========')
  await page.evaluate(() => {
    const m = document.querySelector('.messages')
    if (m) m.scrollTop = 0
  })
  await page.waitForTimeout(1000)
  await page.screenshot({ path: 'tests/visual/desktop/screenshots/real-4-top-fullpage.png', fullPage: true })
})
