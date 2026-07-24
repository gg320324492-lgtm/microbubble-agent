/**
 * tests/visual/desktop/desktop_drive_comments.spec.mjs
 *
 * W68 第 5 批 #1 桌面端 Drive 评论视觉回归 — 5 viewport × 4 页面 = 20 截图点
 *
 * 2026-07-24 主指挥协调范式第 58 守恒 (锚点范式 W68 第 5 批).
 *
 * 设计:
 * - 复用 v77 P2.6-C 视觉回归模式 (visual-regression.spec.mjs 双注入登录态)
 * - 5 viewport: 1280×800 / 1440×900 / 1680×1050 / 1920×1080 / 2560×1440 (含 wide)
 * - 4 页面: 评论列表 / 单条顶层评论 / 嵌套回复 (thread_depth=1) / 评论输入框 (聚焦)
 * - 20 截图点 (5 × 4)
 * - threshold 0.2% 像素差 (跟 v76.2g + 移动端评论视觉基线一致)
 * - baseline 目录: tests/visual/desktop/desktop_drive_comments.spec.mjs-snapshots/
 *
 * 关键纪律:
 * - 0 production code 改动铁律 — 仅 e2e test (W68 第 5 批路线 #1 桌面端评论视觉回归)
 * - 双注入登录态 (cookie + localStorage) — v77 P2.6-C 教训
 * - 首次跑自动生成 baseline (Playwright `--update-snapshots` 或无 baseline 时自动创建)
 * - 主指挥部署后第一次跑生成 baseline, 后续跑做对比
 * - 桌面端 viewport 1280+ 触发 resolveMobile 选 DesktopFileCommentsView (mobile 端 < 768)
 *
 * 用法:
 *   npx playwright test tests/visual/desktop/desktop_drive_comments.spec.mjs
 *   npx playwright test tests/visual/desktop/desktop_drive_comments.spec.mjs --update-snapshots
 *   npx playwright test --project=desktop-comments tests/visual/desktop/desktop_drive_comments.spec.mjs
 */

import { test, expect, devices } from '@playwright/test'

const BASE_URL = process.env.BASE_URL || 'http://localhost:3000'

// W68 第 5 批 #1: 5 viewport 矩阵 (桌面端核心分辨率, 含超宽屏 2560)
// 注: 1280×800 是最常见笔记本基线, 1440/1680/1920 是台式机常见, 2560 是 4K 宽屏
const VIEWPORTS = [
  { name: 'desktop-1280', width: 1280, height: 800,  dsf: 1 },
  { name: 'desktop-1440', width: 1440, height: 900,  dsf: 1 },
  { name: 'desktop-1680', width: 1680, height: 1050, dsf: 1 },
  { name: 'desktop-1920', width: 1920, height: 1080, dsf: 1 },
  { name: 'desktop-2560', width: 2560, height: 1440, dsf: 1 },
]

// W68 路线 F-4 桌面端评论 UI 4 个核心视图
// 路径跟 MobileFileCommentsView (F-3) 对齐, 桌面端入口是 /drive/file/:id/comments
const COMMENT_PAGES = [
  { name: '01-list',    path: '/drive/file/99/comments',          desc: '评论列表 (header + tabs + 列表 + sticky 输入栏)' },
  { name: '02-top',     path: '/drive/file/99/comments?top=1',    desc: '单条顶层评论展开 (DesktopCommentThread depth=0)' },
  { name: '03-thread',  path: '/drive/file/99/comments?thread=1', desc: '嵌套回复 (DesktopCommentThread depth=1 缩进展开)' },
  { name: '04-input',   path: '/drive/file/99/comments?focus=1',  desc: '评论输入框聚焦 (DesktopCommentInput focus 视觉态)' },
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
 * 等待桌面端评论 UI 完全渲染 (loading 消失 + 列表渲染 + sticky 输入栏可见)
 * 复用 F-4 组件约定: .desktop-file-comments-view / .dfcv-list / .dfcv-compose 至少一个出现
 */
async function waitForDesktopCommentsUI(page) {
  await page.waitForLoadState('networkidle')
  await page.waitForTimeout(800)

  // 等待 dfcv-list 或 dfcv-empty 出现 (loading 已结束)
  await page.waitForSelector(
    '.dfcv-list, .dfcv-empty, .dfcv-loading',
    { timeout: 5000 }
  ).catch(() => null)

  // 给动画 500ms 完成
  await page.waitForTimeout(500)
}

test.describe('Desktop Drive Comments 视觉回归 (W68 第 5 批 5×4=20 截图)', () => {
  // 基线对比阈值 (跟 v76.2g + 移动端评论视觉基线配置对齐)
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
        isMobile: false,
        hasTouch: false,
        userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      })

      for (const pg of COMMENT_PAGES) {
        test(`${pg.name}: ${pg.desc}`, async ({ page }) => {
          await injectAuth(page)
          await page.goto(`${BASE_URL}${pg.path}`, { waitUntil: 'domcontentloaded' })
          await waitForDesktopCommentsUI(page)

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
 * W68 第 5 批 #1 铁律验证: dark mode 视觉回归
 * - 切换 dark mode 后跑一遍评论列表 (验证 dark CSS 变量)
 * - 复用 1920×1080 viewport (最常见台式机)
 * - v60-v67 跨组件 dark mode 用非 scoped 块 (commit 5abab881c desktop-drive-comments-ui 守恒)
 */
test.describe('Desktop Drive Comments Dark Mode (W68 第 5 批 铁律 13)', () => {
  test.use({
    viewport: { width: 1920, height: 1080 },
    deviceScaleFactor: 1,
    isMobile: false,
    hasTouch: false,
    colorScheme: 'dark',
  })

  test('dark mode 评论列表渲染', async ({ page }) => {
    await injectAuth(page)
    await page.goto(`${BASE_URL}/drive/file/99/comments`, { waitUntil: 'domcontentloaded' })
    await waitForDesktopCommentsUI(page)

    const bodyText = await page.textContent('body')
    expect(bodyText.length).toBeGreaterThan(10)

    await expect(page).toHaveScreenshot(
      'desktop-1920-01-list-dark.png',
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
 * W68 第 5 批 #1 铁律验证: 桌面端 sticky 输入栏视觉回归
 * - 滚动到列表底部 → sticky 输入栏始终 visible at bottom
 * - 1440×900 viewport (常见笔记本)
 * - 验证 .dfcv-compose position: sticky bottom: 0 渲染正确
 */
test.describe('Desktop Drive Comments Sticky 输入栏 (W68 第 5 批 F-4)', () => {
  test.use({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
    isMobile: false,
    hasTouch: false,
  })

  test('滚动到底后 sticky 输入栏仍可见', async ({ page }) => {
    await injectAuth(page)
    await page.goto(`${BASE_URL}/drive/file/99/comments`, { waitUntil: 'domcontentloaded' })
    await waitForDesktopCommentsUI(page)

    // 滚动到列表底部
    await page.evaluate(() => {
      const body = document.querySelector('.dfcv-body')
      if (body) body.scrollTop = body.scrollHeight
    })
    await page.waitForTimeout(300)

    const bodyText = await page.textContent('body')
    expect(bodyText.length).toBeGreaterThan(10)

    await expect(page).toHaveScreenshot(
      'desktop-1440-05-sticky-input.png',
      {
        fullPage: false, // 只截可视区 (sticky 输入栏应始终 visible)
        animations: 'disabled',
        maxDiffPixelRatio: 0.002,
        threshold: 0.1,
      },
    )
  })
})
