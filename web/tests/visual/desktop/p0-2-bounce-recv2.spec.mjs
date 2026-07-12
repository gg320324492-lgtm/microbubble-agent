import { test, expect } from '@playwright/test'

const BASE = 'https://agent.mnb-lab.cn'

test('P0-#2 v3 实际用户视角: 精密集采按钮点击时的 rect 变化', async ({ page }) => {
  test.setTimeout(120000)
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

  // Login as dutonghe
  await page.fill('input[placeholder*="用户名"], input[name="username"]', 'dutonghe')
  await page.fill('input[type=password]', '123456')
  await page.locator('button').filter({ hasText: /登录/ }).first().click()
  await page.waitForURL(/dashboard|chat/, { timeout: 10000 })
  await page.goto(`${BASE}/chat`)
  await page.waitForTimeout(4000)

  // Open 你好 session
  const target = page.locator('.session-item').filter({ hasText: /你好/ }).first()
  await target.waitFor({ state: 'visible', timeout: 5000 })
  await target.click()
  await page.waitForTimeout(8000)

  // ===== 测试 1: 不点击前, hover 按钮前后 + mousedown + mousemove 看 rect 变化 =====
  console.log('\n========== Test 1: hover 影响 (用户鼠标进入会触发) ==========')
  // 把鼠标从别处移到按钮上, 每 30ms 采一次 rect
  await page.mouse.move(10, 10)  // 离开按钮区域
  await page.waitForTimeout(300)

  const btn = page.locator('#chat-jump-to-top')
  const btnBox = await btn.boundingBox()
  if (!btnBox) throw new Error('btn not found')
  console.log(`btn 位置: x=${btnBox.x + btnBox.width/2}, y=${btnBox.y + btnBox.height/2}`)

  const transition = await page.evaluate(() => {
    const b = document.querySelector('#chat-jump-to-top')
    return b ? getComputedStyle(b).transition : 'no btn'
  })
  console.log(`btn transition: ${transition}`)

  // 鼠标从远处移到按钮 (100ms 内) 看 rect 变化
  const moveStart = Date.now()
  const samples = []
  await page.mouse.move(100, 100)
  await page.waitForTimeout(50)
  // 8 次采样, 间隔 50ms, 鼠标 hover 过程中
  for (let i = 0; i < 12; i++) {
    const data = await page.evaluate((targetX) => {
      const b = document.querySelector('#chat-jump-to-top')
      const r = b?.getBoundingClientRect()
      return {
        y: r?.y,
        height: r?.height,
        computedTransform: b ? getComputedStyle(b).transform : '',
      }
    }, btnBox.x + btnBox.width / 2)
    samples.push({ t: Date.now() - moveStart, ...data })
    await page.waitForTimeout(50)
  }
  console.log('鼠标移到按钮上方过程中:')
  for (const s of samples) console.log(`  +${s.t}ms y=${s.y} transform=${s.computedTransform}`)

  // 现在让鼠标真的 enter 按钮 (移到按钮中心)
  await page.mouse.move(btnBox.x + btnBox.width / 2, btnBox.y + btnBox.height / 2)
  await page.waitForTimeout(50)

  console.log('\n========== Test 2: 鼠标 hover 在按钮上时 (用户能看到的"跳动"时间点) ==========')
  const hoverSamples = []
  for (let i = 0; i < 10; i++) {
    const data = await page.evaluate(() => {
      const b = document.querySelector('#chat-jump-to-top')
      const r = b?.getBoundingClientRect()
      return {
        y: r?.y,
        transform: b ? getComputedStyle(b).transform : '',
        // 检查动画相关 CSS
        cssTransition: b ? getComputedStyle(b).transition : '',
      }
    })
    hoverSamples.push({ t: Date.now() - moveStart, ...data })
    await page.waitForTimeout(30)
  }
  for (const s of hoverSamples) console.log(`  +${s.t}ms y=${s.y} transform=${s.transform}`)

  // ===== 测试 3: 真正 click + 每 16ms 采集 (60fps 模拟) =====
  console.log('\n========== Test 3: 真实 click (鼠标按下 + 弹起), 60fps 采样 ==========')
  const clickStartTime = Date.now()
  const cx = btnBox.x + btnBox.width / 2
  const cy = btnBox.y + btnBox.height / 2

  // Use page.mouse.down + up (不直接 .click() 因为后者太快)
  const clickPromise = page.mouse.down()
  const clickSamples = []
  for (let i = 0; i < 12; i++) {
    const data = await page.evaluate(() => {
      const b = document.querySelector('#chat-jump-to-top')
      const r = b?.getBoundingClientRect()
      const m = document.querySelector('.messages')
      return {
        btnY: r?.y,
        scrollTop: m?.scrollTop,
        transform: b ? getComputedStyle(b).transform : '',
        opacity: b ? getComputedStyle(b).opacity : '',
        display: b ? getComputedStyle(b).display : 'none',
        activeClass: b?.className.match(/active|focus|hover/g),
        activeState: b?.matches(':hover') + '/' + b?.matches(':active'),
      }
    })
    clickSamples.push({ t: Date.now() - clickStartTime, ...data })
    await page.waitForTimeout(16)
  }
  await clickPromise
  await page.mouse.up()

  console.log('click 全过程 (60fps):')
  for (const s of clickSamples) console.log(`  +${s.t}ms y=${s.btnY} scrollTop=${s.scrollTop} transform=${s.transform} display=${s.display} active=${s.activeState}`)

  // 截图最后状态
  await page.screenshot({ path: 'tests/visual/desktop/screenshots/bounce-v3-after-click.png', fullPage: false })

  console.log('\n========== Test 4: 全场景汇总 ==========')
  // y 值变化范围
  const allYs = clickSamples.map(s => s.btnY).filter(y => y != null)
  if (allYs.length > 0) {
    const minY = Math.min(...allYs)
    const maxY = Math.max(...allYs)
    console.log(`btn y 范围: min=${minY}, max=${maxY}, delta=${maxY - minY}`)
    if (maxY - minY > 4) {
      console.log('❌ 检测到按钮 y 位置异常跳动 (>4px)')
    } else {
      console.log('✅ 按钮 y 位置稳定 (±0px 或 ±1px)')
    }
  }
})
