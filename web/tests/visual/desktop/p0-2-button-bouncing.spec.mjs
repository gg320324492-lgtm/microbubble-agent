import { test, expect } from '@playwright/test'

const BASE = 'https://agent.mnb-lab.cn'

test('P0-#2 v2 按钮来回跳动诊断: 点击前后 rect.top 变化', async ({ page }) => {
  test.setTimeout(60000)
  await page.goto(`${BASE}/login`)
  await page.evaluate(async () => {
    localStorage.clear()
    if ('serviceWorker' in navigator) {
      const regs = await navigator.serviceWorker.getRegistrations()
      for (const r of regs) await r.unregister()
    }
    if (window.indexedDB?.databases) {
      const dbs = await window.indexedDB.databases()
      for (const db of dbs) if (db.name) window.indexedDB.deleteDatabase(db.name)
    }
  })
  await page.reload()
  await page.waitForLoadState('networkidle')

  await page.fill('input[placeholder*="用户名"], input[name="username"]', 'dutonghe')
  await page.fill('input[type=password]', '123456')
  await page.locator('button').filter({ hasText: /登录/ }).first().click()
  await page.waitForURL(/dashboard|chat/, { timeout: 10000 })
  await page.goto(`${BASE}/chat`)
  await page.waitForTimeout(4000)

  const target = page.locator('.session-item').filter({ hasText: /你好/ }).first()
  await target.waitFor({ state: 'visible', timeout: 5000 })
  await target.click()
  await page.waitForTimeout(8000)

  console.log('\n========== 1. 点击前 (autoStick 到底, ↑ visible) ==========')
  const before = await page.evaluate(() => {
    const btn = document.querySelector('#chat-jump-to-top')
    const m = document.querySelector('.messages')
    return {
      scrollTop: m?.scrollTop,
      btnExists: !!btn,
      btnRect: btn?.getBoundingClientRect(),
      btnComputed: btn ? {
        position: getComputedStyle(btn).position,
        top: getComputedStyle(btn).top,
        transform: getComputedStyle(btn).transform,
        display: getComputedStyle(btn).display,
      } : null,
    }
  })
  console.log(`  scrollTop: ${before.scrollTop}`)
  console.log(`  btn: ${JSON.stringify(before.btnRect)}`)
  console.log(`  btn computed: ${JSON.stringify(before.btnComputed)}`)
  await page.screenshot({ path: 'tests/visual/desktop/screenshots/bouncing-1-before-click.png', fullPage: false })

  console.log('\n========== 2. 模拟点击 + 立即 snapshot (捕捉 layout shift) ==========')
  const startRect = before.btnRect

  // 直接用 programmatic click 而非真实 click
  const clickResult = await page.evaluate(() => {
    const btn = document.querySelector('#chat-jump-to-top')
    if (!btn) return 'no btn'
    btn.click()
    // 立即读取 rect (无 await)
    const m = document.querySelector('.messages')
    return {
      afterClickScrollTop: m?.scrollTop,
      afterClickRect: btn.getBoundingClientRect(),
    }
  })
  console.log(`  after click: scrollTop=${clickResult.afterClickScrollTop}`)
  console.log(`  after click btn rect: ${JSON.stringify(clickResult.afterClickRect)}`)
  await page.screenshot({ path: 'tests/visual/desktop/screenshots/bouncing-2-immediate.png', fullPage: false })

  console.log('\n========== 3. 等 100ms (CSS transition 0.2s) ==========')
  await page.waitForTimeout(100)
  const after100 = await page.evaluate(() => {
    const btn = document.querySelector('#chat-jump-to-top')
    const m = document.querySelector('.messages')
    return {
      scrollTop: m?.scrollTop,
      btnVisible: btn ? getComputedStyle(btn).display !== 'none' : false,
      btnRect: btn?.getBoundingClientRect(),
    }
  })
  console.log(`  after 100ms: scrollTop=${after100.scrollTop}`)
  console.log(`  after 100ms btn visible: ${after100.btnVisible}`)
  console.log(`  after 100ms btn rect: ${JSON.stringify(after100.btnRect)}`)

  console.log('\n========== 4. 等 500ms (按钮应消失, ↓ 应出现) ==========')
  await page.waitForTimeout(400)
  const after500 = await page.evaluate(() => {
    const btn = document.querySelector('#chat-jump-to-top')
    const bottom = document.querySelector('.jump-to-bottom')
    const m = document.querySelector('.messages')
    return {
      scrollTop: m?.scrollTop,
      btnVisible: btn ? getComputedStyle(btn).display !== 'none' : false,
      bottomVisible: bottom ? getComputedStyle(bottom).display !== 'none' : false,
      bottomRect: bottom?.getBoundingClientRect(),
    }
  })
  console.log(`  after 500ms: scrollTop=${after500.scrollTop}`)
  console.log(`  ↑ visible: ${after500.btnVisible}`)
  console.log(`  ↓ visible: ${after500.bottomVisible}`)
  console.log(`  ↓ rect: ${JSON.stringify(after500.bottomRect)}`)
  await page.screenshot({ path: 'tests/visual/desktop/screenshots/bouncing-3-after-500ms.png', fullPage: false })

  console.log('\n========== 5. 用户视图 (mobile-like viewport) 模拟重复点击 ==========')
  // 模拟多次点击 ↑ 看是否每次都有"跳动"
  for (let i = 0; i < 5; i++) {
    const r = await page.evaluate(() => {
      const btn = document.querySelector('#chat-jump-to-top')
      const m = document.querySelector('.messages')
      if (!btn) return null
      btn.click()
      // 等 50ms 看是否稳定
      return new Promise(resolve => {
        setTimeout(() => {
          resolve({
            scrollTop: m?.scrollTop,
            btnRect: btn?.getBoundingClientRect(),
          })
        }, 50)
      })
    })
    console.log(`  iter ${i}: scrollTop=${r?.scrollTop}, btn y=${r?.btnRect?.y}`)
  }
})
