/**
 * tests/visual/route-warm.mjs — 预热脚本 (不是门禁用例)
 *
 * 2026-10-05 (S3.18) 新增。跑门禁前由 run-visual.sh 调用, 目的只有一个:
 *   把 vite 的**懒发现**依赖预构建在"门禁开始之前"全部触发完, 使门禁
 *   跑测试的过程中不再出现 `optimized dependencies changed. reloading`。
 *
 * ⚠️ 为什么是**独立脚本**而不是一个 spec:
 *   视觉门禁 config (playwright.visual.config.mjs) 的 3 个 project 各带
 *   testMatch, 只认那 5 个做像素比对的 spec。实测把预热当 spec 传进去:
 *     npx playwright test -c ...visual.config.mjs tests/visual/_route-warm.spec.mjs --list
 *     => Total: 0 tests in 0 files
 *   （config 的 testMatch 把它排除了, 传文件名也救不回来）
 *   改成放宽 config 会把预热混进 49 个门禁用例里, 稀释门禁含义。
 *   故直接用 playwright 的 chromium 起真实浏览器走一遍, 不经 test-runner。
 *
 * 它为什么能消除 flaky (实测, 钉死镜像 + run-visual.sh 唯一入口):
 *   vite dev 的预构建是懒发现的 —— 只有被请求到的依赖才纳入优化集。
 *   触发新依赖时 vite 给**已打开的页面**发 HMR 指令强制整页 reload,
 *   组件被卸载重挂 ⇒ spec 的 waitFor / 断言正好落在 reload 窗口里就报
 *   "element(s) not found"。实测被打中的是 secondary-routes 的
 *   `07 file-detail` (`.mfd-title` not found), 冷依赖下 3/3 次复现,
 *   热依赖下 0 次。
 *
 * ── 判据: 依赖优化指纹 (`?v=`) 的集合 ──────────────────────────────
 *   vite 给预构建产物打一个内容哈希, 请求形如
 *       /node_modules/.vite/deps/chunk-ABC.js?v=<hash>
 *   **重新优化必然换 hash**。所以"连续两轮扫完全部路由, 指纹集合逐字相同"
 *   就等价于"这一轮没有任何重新优化", 即依赖集已收敛, 门禁可以开始。
 *   run-visual.sh 用它判稳定; 若 N 轮仍不一致就 fail-loud。
 *
 * ⚠️ 四种错判据都实测踩过, 别退回去 (每一版都留在 git log 里):
 *   (a) vite deps 目录**文件数** —— 重新优化时经常**不新增文件、只改写已有
 *       chunk**, 文件数不变但 reload 照发。实测门禁阶段两轮都报
 *       "deps=156 已稳定", 实际仍触发 7 次 reload, file-detail 照样 flaky。
 *   (b) framenavigated **总数** 减自己 goto 的次数 —— 数不清。
 *   (c) "goto 之后主框架又被导航" —— 同样数不清: **每页加载时 vite 的 HMR
 *       client 都会重连并把当前页再导航一次**, Playwright 把它记成一次
 *       同 URL 的 framenavigated。实测热依赖下也稳定报 31 次, 全是噪声。
 *       （想区分它与真 reload, 得去读 vite 客户端 console 里那条
 *       `optimized dependencies changed` —— 但那是**服务端**日志, 实测
 *       不进页面 console; 且 CI 里 vite 跑在 workflow 另起的 visual-vite
 *       容器, 本脚本读不到它的 stdout。页面侧拿不到该信号。）
 *   (d) 指纹取**全路径** (pathname + ?v=) —— 过严: vite 按加载顺序重排 /
 *       合并 chunk, chunk **文件名**逐轮会变 (实测 chunk-FCNBG3HL.js →
 *       chunk-ICFPP3CZ.js), 但 `?v=` 内容哈希不变。全路径会让"已收敛"
 *       永远判不出来 ⇒ 门禁永远 fail-loud, 那是误报。
 *   ⇒ 只有 `?v=` 版本向量是页面侧可见、且与"是否重新优化"严格一一对应的。
 *
 * ⚠️ ROUTES 必须覆盖**全部** 5 个门禁 spec 实际 goto 的路由:
 *   只热一条链 (如只跑 /chat) 只是把 reload 事件**推迟**到别的路由, 不消除它
 *   —— 这正是原"单用例 warm-up"没能修掉本 flaky 的原因。
 *   改那 5 个 spec 的 goto 目标时, 必须同步改这里的 ROUTES。
 */
import { chromium } from '@playwright/test'
import { writeFileSync } from 'node:fs'

const BASE_URL = process.env.BASE_URL || 'http://localhost:3000'

/**
 * 5 个门禁 spec 实际 goto 的路由全集。
 * 逐条 grep 各 spec 的 `page.goto(\`${BASE_URL}...\`)` / `path:` 得出,
 * 并与 web/src/router/index.js 的 path 定义核对。
 *
 * :id 用各 spec 的 fixture id (secondary-routes 用 MEETING_ID=248 /
 * KNOWLEDGE_ID=999001 / FILE_ID=999001, 评论 spec 用 99), 保证命中的
 * 是同一批动态 import chunk。
 */
const ROUTES = [
  '/dashboard',
  '/drive',
  '/drive/file/99/comments',
  '/drive/file/999001',
  '/drive/file/999001/comments',
  '/knowledge',
  '/knowledge/999001',
  '/chat',
  '/meetings',
  '/meetings/room',
  '/meetings/248',
  '/settings',
  '/workspace',
  '/project-stats',
  '/admin/agent-traces',
  '/knowledge/graph',
  '/memory',
]

// 桌面端 + 移动端都要热: 组件选择是 useIsMobile 驱动的动态 import,
// 只跑一种 viewport 会漏掉另一半组件树的依赖。
const VIEWPORTS = [
  { name: 'desktop', width: 1280, height: 800 },
  { name: 'mobile', width: 390, height: 844 },
]

const REPORT_FILE = process.env.VIZ_WARM_REPORT || '/tmp/route-warm-fingerprint'

// 登录态: 与各 spec 同口径 (双注入 cookie + localStorage)。
// ⚠️ 少了 cookie 那一半会被打回 /login: axios 401 触发 router 跳转,
//    页面停在登录页 ⇒ 一条组件依赖都热不到, 等于白跑 (实测探针复现)。
const TOKEN = process.env.TEST_TOKEN || 'mock-token'

// 本轮观察到的依赖优化版本向量。
const fingerprints = new Set()

for (const vp of VIEWPORTS) {
  const browser = await chromium.launch()
  const context = await browser.newContext({
    viewport: { width: vp.width, height: vp.height },
  })
  const host = new URL(BASE_URL).hostname
  await context.addCookies([{ name: 'access_token', value: TOKEN, domain: host, path: '/' }])
  await context.addInitScript((tk) => {
    localStorage.setItem('access_token', tk)
  }, TOKEN)
  const page = await context.newPage()

  page.on('request', (req) => {
    try {
      const u = new URL(req.url())
      if (!u.pathname.includes('/node_modules/.vite/deps/')) return
      const v = u.searchParams.get('v')
      if (v) fingerprints.add(v)
    } catch {
      /* ignore */
    }
  })

  for (const route of ROUTES) {
    // 单条路由失败不阻断预热: 404 / 空态也是**真实**的预热信号 (组件链已加载);
    // 硬失败反而会让预热半途而废, 留下冷依赖。
    await page
      .goto(`${BASE_URL}${route}`, { waitUntil: 'domcontentloaded', timeout: 30_000 })
      .catch(() => null)
    // 条件式等待: 等 app 外壳挂上。固定 sleep 会成为新的时序 flaky 源。
    await page
      .waitForFunction(() => !!document.querySelector('#app'), null, { timeout: 15_000 })
      .catch(() => null)
  }

  await browser.close()
}

const sorted = [...fingerprints].sort()
writeFileSync(REPORT_FILE, sorted.join('\n'), 'utf8')
console.log(
  `[route-warm] routes=${ROUTES.length} x viewports=${VIEWPORTS.length} ` +
  `deps_versions=[${sorted.join(',')}]`,
)
