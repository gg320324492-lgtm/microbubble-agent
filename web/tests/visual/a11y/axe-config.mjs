/**
 * tests/visual/a11y/axe-config.mjs — W87-G-1 axe-core/playwright 共用配置
 *
 * 为什么是 .mjs 而不是派工 brief 写的 .ts:
 *   本仓库 playwright testMatch 是 /\.spec\.mjs$/ (playwright.config.js:35),
 *   spec 走原生 ESM 不过 ts 转译. 一个 .ts helper 被 .spec.mjs import 会直接
 *   报 "Unknown file extension .ts". 故用 .mjs 保持与既有 spec 一致.
 *
 * WCAG 2.1 AA 门禁 = withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa'])
 *
 * exclude 的三类是 Element Plus / NutUI 内部噪声, 不是本项目可修的代码:
 *   .el-popper   — EP teleport 出去的浮层, 常在 DOM 里但视觉不可见
 *   .el-overlay  — EP dialog/drawer 遮罩
 *   [aria-hidden="true"] — 已显式标注对 AT 隐藏的装饰节点
 */

import AxeBuilder from '@axe-core/playwright'

/** WCAG 2.1 AA 标签集 (本项目 a11y 门禁口径) */
export const WCAG_21_AA_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']

/**
 * 5 个核心页面 — axe 扫的是 URL 不是 .vue 文件, 故把派工 brief 给的组件路径
 * 按 web/src/router/index.js 实测映射成路由:
 *   ChatViewSSE.vue          → /chat                      (router:41-44 resolveMobileComponent)
 *   drive-view.css 引用页    → /drive                     (router:122-125, css 被 12 个 drive 组件引用)
 *   MobileChatView.vue       → /chat + mobile project     (同一路由, resolveMobile 按 UA/viewport 切组件)
 *   MobileTaskTrash.vue      → /tasks/trash               (router:55-57 resolveMobileOnly)
 *   DesktopCommentThread.vue → /drive/file/:id/comments   (被 DesktopFileCommentsView 引用)
 */
export const A11Y_PAGES = [
  { name: '01-chat', path: '/chat', target: 'ChatViewSSE.vue' },
  { name: '02-drive', path: '/drive', target: 'drive-view.css 引用页 (DesktopDriveView/MobileDriveView)' },
  { name: '03-mobile-chat', path: '/chat', target: 'MobileChatView.vue (mobile project 下解析)' },
  { name: '04-task-trash', path: '/tasks/trash', target: 'MobileTaskTrash.vue (8 裸 button)' },
  { name: '05-file-comments', path: '/drive/file/1/comments', target: 'DesktopCommentThread.vue (22 aria 对照)' },
]

/**
 * 构造标准 AxeBuilder (WCAG 2.1 AA + EP 噪声排除)
 * @param {import('@playwright/test').Page} page
 */
export function axeBuilder(page) {
  return new AxeBuilder({ page })
    .withTags(WCAG_21_AA_TAGS)
    .exclude('.el-popper')
    .exclude('.el-overlay')
    .exclude('[aria-hidden="true"]')
}

/**
 * 登录态双注入 (v77 P2.6-C 既有纪律, 见 tests/visual/mobile/visual-regression.spec.mjs:60-78)
 *   1. cookie   — axios withCredentials 读
 *   2. localStorage — router 守卫读 access_token 校验
 * 仅注 cookie 会被 router 守卫重定向到 /login (历史踩坑).
 */
export async function injectAuth(page, baseUrl) {
  const token = process.env.TEST_TOKEN
  if (!token) return false

  await page.context().addCookies([
    { name: 'access_token', value: token, domain: new URL(baseUrl).hostname, path: '/' },
  ])
  await page.addInitScript((tk) => {
    localStorage.setItem('access_token', tk)
  }, token)
  return true
}

/**
 * 真启环境走 /api/v1/auth/login 拿一次 token.
 * W89-P-2 实战: 5 case 各自调 login 触发 5 次/分/IP 限流 (429), 故整 spec 共享一次 token.
 *
 * 用法:
 *   let sharedAuthInfo
 *   test.beforeAll(async ({ request }) => {
 *     sharedAuthInfo = await getAuthToken(request, {
 *       baseUrl: 'http://localhost:8000',
 *       username: 'xiaoqi_testbot',
 *       password: 'testbot_pass_2026',
 *     })
 *   })
 *   test.beforeEach(async ({ page }) => {
 *     await injectAuth(page, 'http://localhost')
 *     // 注入 sharedAuthInfo.token 到 cookie/localStorage
 *   })
 *
 * @param {import('@playwright/test').APIRequestContext} request - Playwright request fixture
 * @param {object} opts
 * @param {string} [opts.baseUrl] - API base (默认 http://localhost:8000)
 * @param {string} [opts.username] - 默认 xiaoqi_testbot (tests/conftest.py:139-141 既有纪律)
 * @param {string} [opts.password] - 默认 testbot_pass_2026
 * @returns {Promise<{ token: string, username: string, baseUrl: string }>}
 */
export async function getAuthToken(request, opts = {}) {
  const baseUrl = opts.baseUrl || 'http://localhost:8000'
  const username = opts.username || 'xiaoqi_testbot'
  const password = opts.password || 'testbot_pass_2026'

  const res = await request.post(`${baseUrl}/api/v1/auth/login`, {
    data: { username, password },
  })
  if (res.status() !== 200) {
    throw new Error(
      `login 失败: status=${res.status()} body=${(await res.text()).slice(0, 200)}`,
    )
  }
  const body = await res.json()
  if (!body.access_token) {
    throw new Error(`login 响应无 access_token: ${JSON.stringify(body).slice(0, 200)}`)
  }
  return { token: body.access_token, username, baseUrl }
}

/**
 * 把 axe violations 压成稳定可 diff 的 baseline 形状.
 * 丢掉 node.html / screenshot 等每次跑都抖的字段, 只留 id + impact + 命中数.
 */
export function toBaseline(results) {
  return results.violations
    .map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.length }))
    .sort((a, b) => a.id.localeCompare(b.id))
}
