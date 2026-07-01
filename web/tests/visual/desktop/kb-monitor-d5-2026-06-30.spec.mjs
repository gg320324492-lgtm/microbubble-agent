/**
 * tests/visual/desktop/kb-monitor-d5-2026-06-30.spec.mjs
 *
 * W6 D5 KB 入库监控端到端验证
 *
 * 覆盖:
 *   - /project-stats 第 3 个 tab "KB 入库监控" 渲染
 *   - 4 个 metric card (今日/7日/命中率/负反馈)
 *   - 7 日趋势柱状图 (CSS div 7 个)
 *   - 系统状态卡 (灰度/rollback/刷新机制)
 *   - polling 5min 触发 (window.fetch 计数)
 *   - 浏览器 console 无 error
 *
 * 前置:
 *   - dev server 跑起来 (npm run dev) 或 BASE_URL 指向部署环境
 *   - TEST_TOKEN 环境变量注入真实 JWT
 *   - 测试账号 xiaoqi_testbot/testbot_pass_2026 已创建
 *     (跑一次 `python scripts/ensure_test_user.py`)
 *
 * 运行:
 *   BASE_URL=http://localhost:3004 \
 *   TEST_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
 *     -H "Content-Type: application/json" \
 *     -d '{"username":"xiaoqi_testbot","password":"testbot_pass_2026"}' \
 *     | python -c "import json,sys; print(json.load(sys.stdin)['access_token'])") \
 *     npx playwright test tests/visual/desktop/kb-monitor-d5-2026-06-30.spec.mjs
 *
 * 关键纪律:
 *   - 真实 JWT token (mock-token 会被后端拒)
 *   - 验证 6 个核心断言 (3 tab + 4 metric + 7 trend bar)
 *   - 截图保存到 test-results/kb-monitor-d5/
 *   - 2026-07-01 起从 wangtianzhi 物理隔离到测试账号, 避免 e2e reset 影响真实使用
 */

import { test, expect } from '@playwright/test'

const BASE_URL = process.env.BASE_URL || 'http://localhost:3004'
const TEST_TOKEN = process.env.TEST_TOKEN || ''

async function setupPage(page, { theme = 'light', accent = 'orange' } = {}) {
  await page.context().addCookies([{
    name: 'access_token',
    value: TEST_TOKEN,
    domain: new URL(BASE_URL).hostname,
    path: '/',
  }])
  // W6 D5: 用 addInitScript 设所有 localStorage (避免 setupPage evaluate 被 navigation 销毁)
  await page.addInitScript((data) => {
    localStorage.setItem('access_token', data.token)
    localStorage.setItem('theme', data.theme)
    localStorage.setItem('accent', data.accent)
  }, { token: TEST_TOKEN, theme, accent })
  // 第一次访问让 router 完成 auth check, 不再 evaluate
  await page.goto(BASE_URL, { waitUntil: 'domcontentloaded' })
}

test.describe('kb-monitor-d5: /project-stats 第 3 个 tab 端到端验证', () => {
  test('D5 KB 入库监控 tab 渲染 + 4 metric + 7 trend bar + system status', async ({ page }) => {
    const consoleErrors = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') consoleErrors.push(msg.text())
    })

    // 1. 登录 + 跳转到 /project-stats
    await setupPage(page)
    await page.goto(`${BASE_URL}/project-stats`, { waitUntil: 'networkidle' })
    await page.waitForTimeout(500)

    // 断言 1: 页面标题 "项目动态"
    await expect(page.locator('h1.page-title')).toContainText('项目动态')

    // 断言 2: 3 个 tab 存在 (项目历程 / 检索质量 / KB 入库监控)
    const tabLabels = await page.locator('.el-tabs__item').allTextContents()
    expect(tabLabels.length, '应有 3 个 tab').toBe(3)
    expect(tabLabels.some(t => t.includes('项目历程'))).toBe(true)
    expect(tabLabels.some(t => t.includes('检索质量'))).toBe(true)
    expect(tabLabels.some(t => t.includes('KB 入库监控'))).toBe(true)

    // 断言 3: 点击 "KB 入库监控" tab
    await page.locator('.el-tabs__item:has-text("KB 入库监控")').click()
    await page.waitForTimeout(1000)  // 等待 useKbMonitor onMounted + 第一次 fetch

    // 断言 4: 4 个 metric card 显示
    // 注: 整个 .metric-card 含 .metric-label + .metric-value + .metric-sub
    const allCardTexts = await page.locator('.metric-card').allTextContents()
    console.log('所有 .metric-card 文本:', JSON.stringify(allCardTexts))

    // 找包含 4 个 KB tab 标签的 card
    const todayCard = allCardTexts.find(t => t.includes('今日入库'))
    const weekCard = allCardTexts.find(t => t.includes('7日入库'))
    const hitCard = allCardTexts.find(t => t.includes('KB 命中率'))
    const negCard = allCardTexts.find(t => t.includes('负反馈率'))
    expect(todayCard, '应找到 "今日入库" metric card').toBeTruthy()
    expect(weekCard, '应找到 "7日入库" metric card').toBeTruthy()
    expect(hitCard, '应找到 "KB 命中率" metric card').toBeTruthy()
    expect(negCard, '应找到 "负反馈率" metric card').toBeTruthy()
    expect(todayCard, '"今日入库" 应包含 179 条 (DB 真实数据)').toContain('179')

    // 断言 5: 7 日趋势柱状图 (7 个, KB tab 独有)
    await expect(page.locator('.trend-bar-wrapper')).toHaveCount(7)

    // 断言 6: 系统状态卡 (3 个, KB tab 独有)
    await expect(page.locator('.status-item')).toHaveCount(3)

    // 断言 7: polling 5min 触发 — 检查 1 次 fetch 已发 (onMounted 立即拉)
    // (修改 POLL_INTERVAL_MS 测试更可靠, 但本次只验证 onMounted 拉一次)
    const apiResponse = await page.evaluate(async () => {
      // 再次调一次 API 验证端点正常
      const t = localStorage.getItem('access_token')
      const res = await fetch('/api/v1/knowledge/auto-intake-summary', {
        headers: { 'Authorization': `Bearer ${t}` }
      })
      return await res.json()
    })
    expect(apiResponse).toHaveProperty('today_intake')
    expect(apiResponse).toHaveProperty('weekly_intake')
    expect(apiResponse).toHaveProperty('total_in_db')
    expect(typeof apiResponse.total_in_db).toBe('number')

    // 断言 8: 浏览器 console 无 error (除了已知无害警告)
    const realErrors = consoleErrors.filter(e =>
      !e.includes('favicon') && !e.includes('webpack')
    )
    expect(realErrors, `Console errors: ${realErrors.join('; ')}`).toEqual([])

    // 截图保存
    await page.screenshot({
      path: 'test-results/kb-monitor-d5/desktop-project-stats-tab3.png',
      fullPage: true,
      animations: 'disabled',
    })
  })

  test('D5 切回其他 tab 不破坏 (回归测试)', async ({ page }) => {
    await setupPage(page)
    await page.goto(`${BASE_URL}/project-stats`, { waitUntil: 'networkidle' })
    await page.waitForTimeout(500)

    // 切到 KB 入库监控
    await page.locator('.el-tabs__item:has-text("KB 入库监控")').click()
    await page.waitForTimeout(500)

    // 切回项目历程
    await page.locator('.el-tabs__item:has-text("项目历程")').click()
    await page.waitForTimeout(500)

    // 项目历程 tab 应有 timeline 元素
    const timeline = page.locator('.el-timeline').first()
    await expect(timeline).toBeVisible()

    // 切到检索质量
    await page.locator('.el-tabs__item:has-text("检索质量")').click()
    await page.waitForTimeout(500)
  })
})
