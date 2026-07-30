/**
 * tests/visual/mobile/visual-regression.spec.mjs
 *
 * Playwright 视觉回归 — v77 P2.6-C 扩展到 6 路由 (与 desktop 对齐)
 *
 * 用法:
 *   npx playwright test                                    # 对比 baseline
 *   npx playwright test --update-snapshots                # 更新 baseline
 *   BASE_URL=https://staging npx playwright test          # 跑 staging 环境
 *   TEST_TOKEN=<jwt> npx playwright test                   # 注入登录态
 *
 * 前置:
 *   - dev server 跑起来 (npm run dev) 或用 BASE_URL 指向部署环境
 *   - 登录态: TEST_TOKEN 注入 cookie + localStorage (双注入, v77 P2.6-C 修复)
 *   - 第一次跑必须带 --update-snapshots 生成 baseline
 *
 * 关键纪律:
 *   - 视觉差异 > 0.2% 才 fail (配置在 playwright.config.js)
 *   - 不要手动改 baseline/*.png (用 --update-snapshots)
 *   - baseline 必须跟代码一起 commit (跟 dist 一样, git add -f)
 *   - 登录态必须双注入: cookie (axios withCredentials) + localStorage (router 守卫读)
 *   - 仅 cookie 注入会导致 router 守卫拦截重定向 /login (历史踩坑, 3 张旧 baseline 字节数完全相同 = 登录页)
 *   - **W89-X-24 (派工 v6 §5 反馈 类 20.79)**: 必用 waitForSelector(state: 'visible')
 *     等明确 UI locator (mobile 页面根 class 如 .mobile-XXX), 禁 networkidle
 *     或裸 timeout。空态 vs 已加载数据竞态 → diff 3-6% > 门禁 0.2%。
 */

import { test, expect } from '@playwright/test'

const BASE_URL = process.env.BASE_URL || 'http://localhost:3000'
const VIEWPORT = { width: 390, height: 844 } // iPhone 14

// v77 P2.6-C: 从 3 路由扩到 6 路由 (与 desktop 对齐)
// v77 P2.6-D.4: 扩到 9 路由 (+projects /members /project-stats)
// v78: /projects /members 合并到 /workspace, 仍 9 路由
//
// W89-X-24 (2026-07-30): 每条路由配 1 个稳定 root selector, 用于
// waitForSelector(state: 'visible') 替代 networkidle + 裸 timeout.
// 真因: 空态 vs 已加载数据竞态 — networkidle 触发时机早于 React/Vue
// 实际渲染 + 子组件 mount,导致截图时 DOM 处于半挂载/空态。
// 修法 (派工 v6 §5 反馈 类 20.79 沉淀): 必等明确 UI locator / data-testid,
// 禁 networkidle 或裸 timeout。
const CORE_ROUTES = [
  // 优先 mobile selector, 退到 desktop selector (兼容 prod build 路由回退)
  {
    path: '/dashboard',
    name: '01-dashboard',
    selector: '.mobile-dashboard, .dashboard-view, .dashboard',
  },
  {
    path: '/knowledge',
    name: '06-knowledge',
    selector: '.mobile-knowledge-view, .knowledge-view',
  },
  {
    path: '/chat',
    name: '03-chat',
    selector: '.mobile-chat-root, .chat-view, .chat-main',
  },
  {
    path: '/tasks',
    name: '04-tasks',
    selector: '.mobile-task-view, .task-view, .tasks-view',
  },
  {
    path: '/meetings',
    name: '05-meetings',
    selector: '.mobile-meeting-view, .mobile-meeting-detail, .meeting-view',
  },
  {
    path: '/settings',
    name: '07-settings',
    selector: '.mobile-settings-view, .settings-view',
  },
  {
    path: '/workspace?tab=projects',
    name: '08-workspace-projects',
    selector: '.mobile-workspace-view, .workspace-view',
  },
  {
    path: '/workspace?tab=members',
    name: '09-workspace-members',
    selector: '.mobile-workspace-view, .workspace-view',
  },
  {
    path: '/project-stats',
    name: '10-project-stats',
    selector: '.mobile-project-stats, .project-stats, .stats-view',
  },
]

test.describe('Mobile 核心页面视觉回归 (v77 P2.6-C 6 路由 baseline 对比)', () => {
  test.use({ viewport: VIEWPORT })

  // 公共登录态注入 helper (v77 P2.6-C 双注入修复)
  async function injectAuth(page) {
    const token = process.env.TEST_TOKEN || 'mock-token'

    // 1. Cookie 注入 (兼容 axios withCredentials)
    await page.context().addCookies([{
      name: 'access_token',
      value: token,
      domain: new URL(BASE_URL).hostname,
      path: '/',
    }])

    // 2. localStorage 注入 (关键！router 守卫读 localStorage.getItem('access_token') 校验)
    // addInitScript 在每个 page navigation 前注入，刷新页面也保留
    await page.addInitScript((tk) => {
      localStorage.setItem('access_token', tk)
    }, token)
  }

  for (const route of CORE_ROUTES) {
    test(`${route.name} 截图对比 baseline`, async ({ page }) => {
      await injectAuth(page)
      // W89-X-24 (派工 v6 §5 反馈 类 20.79):
      //   弃用 waitUntil: 'networkidle' (空态 vs 已加载数据竞态, 触发早于
      //   Vue 子组件 mount, diff 3-6% > 门禁 0.2%)。
      //   改用 waitForSelector(state: 'visible') 等明确 UI locator,
      //   触发时机 = DOM 已 layout + 元素已渲染 = 真正的"已就绪"快照点。
      await page.goto(`${BASE_URL}${route.path}`, { waitUntil: 'domcontentloaded' })
      await page.waitForSelector(route.selector, { state: 'visible', timeout: 10_000 })
      // 等动画/异步数据加载完成 (从 800ms 收紧到 300ms,
      // 关键 UI locator 已 visible 后,剩余主要是 transition 收尾)
      await page.waitForTimeout(300)

      // v77 P2.6-C: baseline 对比
      // 首次跑会自动生成 tests/visual/mobile/visual-regression.spec.mjs-snapshots/{name}-iphone14.png
      await expect(page).toHaveScreenshot(`${route.name}.png`, {
        fullPage: true,
        animations: 'disabled',
        maxDiffPixelRatio: 0.002,
      })

      // 验证页面真的渲染了内容 (避免空白页通过 baseline 对比)
      // W89-X-24: 用 root selector 替代 body text 长度, 更精准反映
      // "组件实际已 mount" 而非 "<body>...</body>" 任意 10 字符。
      // 注: waitForSelector 已断言 visible, count() 仅作二次确认。
      // 逗号分隔多 selector 时 count() 算全部匹配, 只要 ≥ 1 即可。
      const rootCount = await page.locator(route.selector).count()
      expect(
        rootCount,
        `${route.name} 根 selector ${route.selector} 应至少 1 个`
      ).toBeGreaterThanOrEqual(1)
    })
  }

  // v76.2h: PWA manifest 测试不属于视觉回归范畴, 移到独立 spec
  // (dev server 上 /manifest.webmanifest 404, 仅 build 产物有效)
  // 视觉回归 spec 应只关注截图 baseline 对比
})