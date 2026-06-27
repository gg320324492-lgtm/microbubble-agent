/**
 * tests/visual/desktop/visual-regression.spec.mjs
 *
 * Playwright 视觉回归 — Desktop baseline 对比 (v77 P2.6-B)
 *
 * 与 mobile spec 平行：同一 cookie 注入模式 + baseline 对比 + body 文本断言。
 * 路由数 6（与 mobile 对齐：dashboard/chat/knowledge/tasks/meetings/settings）。
 *
 * 用法:
 *   npx playwright test --project=desktop-chrome                  # 对比 baseline
 *   npx playwright test --project=desktop-chrome --update-snapshots  # 更新 baseline
 *   BASE_URL=https://staging npx playwright test --project=desktop-chrome
 *   TEST_TOKEN=<jwt> npx playwright test --project=desktop-chrome
 *
 * 前置:
 *   - dev server 跑起来 (npm run dev) 或用 BASE_URL 指向部署环境
 *   - 登录态: 通过 TEST_TOKEN 环境变量注入 access_token cookie
 *   - 第一次跑必须带 --update-snapshots 生成 baseline
 *
 * 关键纪律:
 *   - 视觉差异 > 0.2% 才 fail (配置在 playwright.config.js)
 *   - 不要手动改 baseline/*.png (用 --update-snapshots)
 *   - baseline 必须跟代码一起 commit (snapshots 目录不在 .gitignore, 正常 git add)
 *   - 本地 Windows 跑出来是 -windows.png 后缀, CI Linux runner 会重写为 -linux.png
 *     接受这个机制 (v76 教训: "不要本地 commit baseline" 是为避免平台差异,
 *     desktop 是首次建立 baseline, 必须本地 commit 一次让 CI 后续能对比)
 */

import { test, expect } from '@playwright/test'

const BASE_URL = process.env.BASE_URL || 'http://localhost:3000'
const VIEWPORT = { width: 1280, height: 720 } // Desktop Chrome default

// v77 P2.6-B: 6 路由（与 mobile 3 路由对齐 + 桌面 3 新增）
// tasks/meetings/settings 是首次纳入 baseline
const CORE_ROUTES = [
  { path: '/dashboard', name: '01-dashboard' },
  { path: '/chat', name: '03-chat' },
  { path: '/knowledge', name: '06-knowledge' },
  // v77 P2.6-B 新增
  { path: '/tasks', name: '04-tasks' },
  { path: '/meetings', name: '05-meetings' },
  { path: '/settings', name: '07-settings' },
]

test.describe('Desktop 核心页面视觉回归 (v77 P2.6-B baseline 对比)', () => {
  test.use({ viewport: VIEWPORT })

  // 公共登录态注入 helper（v77 P2.6-C 双注入修复，与 mobile spec 同步）
  async function injectAuth(page) {
    const token = process.env.TEST_TOKEN || 'mock-token'

    // 1. Cookie 注入（兼容 axios withCredentials）
    await page.context().addCookies([{
      name: 'access_token',
      value: token,
      domain: new URL(BASE_URL).hostname,
      path: '/',
    }])

    // 2. localStorage 注入（关键！router 守卫读 localStorage.getItem('access_token') 校验）
    await page.addInitScript((tk) => {
      localStorage.setItem('access_token', tk)
    }, token)
  }

  for (const route of CORE_ROUTES) {
    test(`${route.name} 截图对比 baseline`, async ({ page }) => {
      await injectAuth(page)
      await page.goto(`${BASE_URL}${route.path}`, { waitUntil: 'networkidle' })

      // 等动画/异步数据加载完成
      await page.waitForTimeout(800)

      // baseline 对比: 首次跑生成 baseline 到
      // tests/visual/desktop/visual-regression.spec.mjs-snapshots/{name}-desktop-chrome-*.png
      await expect(page).toHaveScreenshot(`${route.name}.png`, {
        fullPage: true,
        animations: 'disabled',
        maxDiffPixelRatio: 0.002,
      })

      // 验证页面真的渲染了内容 (避免空白页通过 baseline 对比)
      const bodyText = await page.textContent('body')
      expect(bodyText.length, `${route.name} 页面应渲染内容`).toBeGreaterThan(10)
    })
  }
})
