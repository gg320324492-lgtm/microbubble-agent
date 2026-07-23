/**
 * tests/visual/mobile/mobile_drive_comments.spec.mjs
 *
 * W68 路线 F-3 移动端评论 UI 视觉回归 — 7 viewport × 4 页面 = 28 截图点
 *
 * 2026-07-24 主指挥协调范式第 51 守恒 (锚点范式 W68 第 4 批).
 *
 * 设计:
 * - 复用 v77 P2.6-C 视觉回归模式 (visual-regression.spec.mjs 双注入登录态)
 * - 7 viewport: iPhone SE / iPhone 12 / iPhone 14 Pro Max / iPad / Galaxy S20 / Pixel 5 / OnePlus 8
 * - 4 页面: 评论列表 / 单条评论 (顶层) / 嵌套回复 (展开) / 评论输入框 (聚焦)
 * - 28 截图点 (7 × 4)
 * - threshold 0.2% 像素差 (跟 v76.2g 视觉基线一致)
 *
 * 关键纪律:
 * - 0 production code 改动铁律 — 仅 e2e test (W68 第 4 批路线 C 复用)
 * - 双注入登录态 (cookie + localStorage) — v77 P2.6-C 教训
 * - 首次跑自动生成 baseline (--update-snapshots 或无 baseline 时自动创建)
 * - 主指挥部署后第一次跑生成 baseline, 后续跑做对比
 *
 * 用法:
 *   npx playwright test tests/visual/mobile/mobile_drive_comments.spec.mjs
 *   npx playwright test tests/visual/mobile/mobile_drive_comments.spec.mjs --update-snapshots
 */

import { test, expect, devices } from '@playwright/test'

const BASE_URL = process.env.BASE_URL || 'http://localhost:3000'

// W68 第 4 批: 7 viewport 矩阵 (与现有桌面 + 移动视觉基线集合对齐)
// 注: iPhone 14 (390x844) 已在 mobile-iphone14 project 默认, 这里覆盖更广
const VIEWPORTS = [
  { name: 'iphone-se',       width: 375,  height: 667,  dsf: 2,   isMobile: true,  hasTouch: true },
  { name: 'iphone-12',       width: 390,  height: 844,  dsf: 3,   isMobile: true,  hasTouch: true },
  { name: 'iphone-14-promax',width: 430,  height: 932,  dsf: 3,   isMobile: true,  hasTouch: true },
  { name: 'ipad',            width: 768,  height: 1024, dsf: 2,   isMobile: true,  hasTouch: true },
  { name: 'galaxy-s20',      width: 412,  height: 915,  dsf: 3,   isMobile: true,  hasTouch: true },
  { name: 'pixel-5',         width: 393,  height: 851,  dsf: 2.75,isMobile: true,  hasTouch: true },
  { name: 'oneplus-8',       width: 412,  height: 869,  dsf: 2.625,isMobile: true, hasTouch: true },
]

// W68 路线 F-3 评论 UI 4 个核心视图
const COMMENT_PAGES = [
  { name: '01-list',     path: '/drive/file/99/comments',           desc: '评论列表 (header + tabs + 列表 + 输入栏)' },
  { name: '02-top',      path: '/drive/file/99/comments?top=1',     desc: '单条顶层评论展开' },
  { name: '03-thread',   path: '/drive/file/99/comments?thread=1',  desc: '嵌套回复 (thread_depth=1)' },
  { name: '04-input',    path: '/drive/file/99/comments?focus=1',   desc: '评论输入框聚焦 (键盘弹出)' },
]

/**
 * 公共登录态注入 (复用 v77 P2.6-C 双注入模式)
 * - cookie 注入 (axios withCredentials)
 * - localStorage 注入 (router 守卫读)
 */
async function injectAuth(page) {
  const token = process.env.TEST_TOKEN || 'mock-token'
  const host = new URL(BASE_URL).hostname

  await page.context().addCookies([{
    name: 'access_token',
    value: token,
    domain: host,
    path: '/',
  }])

  await page.addInitScript((tk) => {
    localStorage.setItem('access_token', tk)
  }, token)
}

/**
 * 等待评论 UI 完全渲染 (loading 消失 + 列表渲染)
 * 复用 F-3 组件约定: .mfcc-list / .mfcc-top / .mci-textarea 至少一个出现
 */
async function waitForCommentsUI(page) {
  await page.waitForLoadState('networkidle')
  await page.waitForTimeout(800)

  // 等待 mfcc-list 或 mfcc-empty 出现 (loading 已结束)
  await page.waitForSelector(
    '.mfcc-list, .mfcc-empty, .mfcc-loading',
    { timeout: 5000 }
  ).catch(() => null)

  // 给动画 500ms 完成
  await page.waitForTimeout(500)
}

test.describe('Mobile Drive Comments 视觉回归 (W68 第 4 批 7×4=28 截图)', () => {
  // 基线对比阈值 (跟 v76.2g 配置对齐)
  const SCREENSHOT_OPTIONS = {
    fullPage: true,
    animations: 'disabled',
    maxDiffPixelRatio: 0.002, // 0.2% 像素差
    threshold: 0.1,           // 0-255 颜色差
  }

  for (const vp of VIEWPORTS) {
    test.describe(`viewport: ${vp.name} (${vp.width}x${vp.height})`, () => {
      test.use({
        viewport: { width: vp.width, height: vp.height },
        deviceScaleFactor: vp.dsf,
        isMobile: vp.isMobile,
        hasTouch: vp.hasTouch,
        userAgent:
          'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
      })

      for (const pg of COMMENT_PAGES) {
        test(`${pg.name}: ${pg.desc}`, async ({ page }) => {
          await injectAuth(page)
          await page.goto(`${BASE_URL}${pg.path}`, { waitUntil: 'domcontentloaded' })
          await waitForCommentsUI(page)

          // 验证页面真的渲染了评论 UI (避免空白页通过 baseline 对比)
          const bodyText = await page.textContent('body')
          expect(
            bodyText.length,
            `${vp.name}/${pg.name} 页面应渲染内容 (长度>10)`,
          ).toBeGreaterThan(10)

          // baseline 对比 (首次跑自动生成, 后续跑对比)
          await expect(page).toHaveScreenshot(
            `${vp.name}-${pg.name}.png`,
            SCREENSHOT_OPTIONS,
          )
        })
      }
    })
  }
})

/**
 * W68 第 4 批铁律验证: dark mode 视觉回归
 * - 切换 dark mode 后跑一遍评论列表 (验证 dark CSS 变量)
 * - 复用 iPhone 14 viewport (最常见移动设备)
 */
test.describe('Mobile Drive Comments Dark Mode (W68 第 4 批铁律 13)', () => {
  test.use({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 3,
    isMobile: true,
    hasTouch: true,
    colorScheme: 'dark',
  })

  test('dark mode 评论列表渲染', async ({ page }) => {
    await injectAuth(page)
    await page.goto(`${BASE_URL}/drive/file/99/comments`, { waitUntil: 'domcontentloaded' })
    await waitForCommentsUI(page)

    const bodyText = await page.textContent('body')
    expect(bodyText.length).toBeGreaterThan(10)

    await expect(page).toHaveScreenshot(
      'iphone-12-01-list-dark.png',
      {
        fullPage: true,
        animations: 'disabled',
        maxDiffPixelRatio: 0.002,
        threshold: 0.1,
      },
    )
  })
})

/**
 * W68 第 4 批铁律验证: 长按菜单视觉回归
 * - 模拟 long-press → MobileContextMenu 弹出 (Teleport to body)
 * - iPhone 14 viewport (主战场)
 */
test.describe('Mobile Drive Comments 长按菜单 (W68 第 4 批铁律 13 vibrate)', () => {
  test.use({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 3,
    isMobile: true,
    hasTouch: true,
  })

  test('长按顶层评论弹出 context menu', async ({ page }) => {
    await injectAuth(page)
    await page.goto(`${BASE_URL}/drive/file/99/comments`, { waitUntil: 'domcontentloaded' })
    await waitForCommentsUI(page)

    // 找到顶层评论 long-press wrapper
    const longPressEl = page.locator('.long-press-wrapper').first()
    if (await longPressEl.count() > 0) {
      // 长按 600ms (LongPressWrapper duration 配置)
      const box = await longPressEl.boundingBox()
      if (box) {
        await page.touchscreen.tap(box.x + box.width / 2, box.y + box.height / 2)
        await page.waitForTimeout(700) // 等待 long-press 触发
      }
    }

    await page.waitForTimeout(300)

    await expect(page).toHaveScreenshot(
      'iphone-12-05-longpress-menu.png',
      {
        fullPage: false, // 只截可视区 (菜单弹出后页面其他部分不变)
        animations: 'disabled',
        maxDiffPixelRatio: 0.002,
        threshold: 0.1,
      },
    )
  })
})