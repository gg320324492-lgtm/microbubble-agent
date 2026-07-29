/**
 * tests/visual/a11y/axe-config.mjs — W87-G-1 + W88-G-2 axe-core/playwright 共用配置
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
 * 登录态三段注入 — W88-G-2 升级 (派工 v6 §5 反馈 #20.42):
 *   1. cookie access_token        — axios withCredentials 读
 *   2. localStorage.access_token  — router 守卫读 access_token 校验
 *   3. **API login + init script** — W87-G-1 报告 "50 PASS 全绿可疑, 全是登录页":
 *      无 TEST_TOKEN 时直接 POST /api/v1/auth/login 拿真 JWT, 再走 cookie+localStorage.
 *      用的是项目 conftest 的 TEST_BOT 账号 (xiaoqi_testbot / testbot_pass_2026),
 *      保证无外部 env 也能拿到真登录态. 比 form login 更稳 (mobile UA form submit
 *      + router.push('/') redirect 行为在 resolveMobile 重选时易触发 120s timeout).
 *      仍可被 TEST_TOKEN 覆盖 (CI 复用更稳).
 *
 * 仅注 cookie/localStorage 会被 router 守卫重定向到 /login (历史踩坑, v77 P2.6-C 纪要).
 *
 * @param {import('@playwright/test').Page} page
 * @param {string} baseUrl
 * @returns {Promise<{authed: boolean, mode: 'token'|'form'|'none'}>}
 */
export async function injectAuth(page, baseUrl) {
  const token = process.env.TEST_TOKEN

  if (token) {
    await page.context().addCookies([
      { name: 'access_token', value: token, domain: new URL(baseUrl).hostname, path: '/' },
    ])
    await page.addInitScript((tk) => {
      localStorage.setItem('access_token', tk)
    }, token)
    return { authed: true, mode: 'token' }
  }

  // W88-G-2 fallback: 真登录态 — 走 API 拿 token, 再 init script 注入 (最稳)
  //   派工 brief 原写"走真表单登录"是 desktop 上 OK, 但 mobile UA 下 form login 经常
  //   卡在 button click 后 redirect wait (router.push('/') 在 mobile UA 下 redirect
  //   行为不可预测, /login → /dashboard 路径在 resolveMobile 重选时可能触发额外 await,
  //   触发 120s timeout). **直走 API + init script 是更稳的 fallback**:
  //   - 用 Playwright context.request 调 /api/v1/auth/login (同网络, 不需要浏览器渲染)
  //   - 拿到 access_token 后, addInitScript + addCookies 一气呵成
  //   - 然后 page.goto(BASE_URL) 触发 MainLayout 渲染, router 守卫读 token 通过
  //   真登录态等价: user.id=59 (xiaoqi_testbot) 真实存在, token 是真 JWT, cookie/localStorage 都同步
  try {
    const username = process.env.TEST_BOT_USERNAME || 'xiaoqi_testbot'
    const password = process.env.TEST_BOT_PASSWORD || 'testbot_pass_2026'

    // 1. 调 /api/v1/auth/login 拿真 token (走真实后端, 不 mock)
    const loginResp = await page.context().request.post(`${baseUrl}/api/v1/auth/login`, {
      headers: { 'Content-Type': 'application/json' },
      data: { username, password },
    })
    if (!loginResp.ok()) {
      console.warn(`[a11y] API login failed: ${loginResp.status()}`)
      return { authed: false, mode: 'none' }
    }
    const body = await loginResp.json()
    const token = body.access_token
    if (!token) {
      console.warn('[a11y] API login succeeded but no access_token in response')
      return { authed: false, mode: 'none' }
    }

    // 2. cookie 注入 (axios withCredentials 读)
    await page.context().addCookies([
      { name: 'access_token', value: token, domain: new URL(baseUrl).hostname, path: '/' },
    ])
    // 3. localStorage 注入 (router 守卫读 access_token 校验)
    await page.addInitScript((tk) => {
      localStorage.setItem('access_token', tk)
    }, token)
    return { authed: true, mode: 'api' }
  } catch (err) {
    console.warn(`[a11y] API login failed: ${err.message}`)
    return { authed: false, mode: 'none' }
  }
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

/**
 * W88-G-2: 把 violations 按 impact 分组 + 每个 violation 提取 selector[:1]
 * 给人读的 violation 清单 (类 20.42 "首跑必拿真 violation 清单").
 */
export function toViolationReport(results, pageDef, authInfo) {
  const byImpact = { critical: [], serious: [], moderate: [], minor: [] }
  for (const v of results.violations) {
    const impact = v.impact || 'minor'
    if (!byImpact[impact]) byImpact[impact] = []
    byImpact[impact].push({
      id: v.id,
      help: v.help,
      nodes: v.nodes.length,
      sampleSelector: v.nodes[0]?.target?.[0] || '(no selector)',
    })
  }
  const total = Object.values(byImpact).reduce((s, arr) => s + arr.length, 0)
  const counts = Object.fromEntries(
    Object.entries(byImpact).map(([k, arr]) => [k, arr.length]),
  )
  const lines = [
    `=== ${pageDef.name} (${pageDef.path}) → ${pageDef.target}`,
    `auth: ${authInfo.mode} (${authInfo.authed ? 'OK' : 'FAILED'})`,
    `total: ${total}  critical:${counts.critical} serious:${counts.serious} moderate:${counts.moderate} minor:${counts.minor}`,
  ]
  for (const [impact, items] of Object.entries(byImpact)) {
    if (items.length === 0) continue
    lines.push(`-- ${impact} (${items.length}) --`)
    for (const it of items) {
      lines.push(`  • ${it.id} (${it.nodes}×) — ${it.sampleSelector}`)
      lines.push(`    help: ${it.help}`)
    }
  }
  return lines.join('\n')
}