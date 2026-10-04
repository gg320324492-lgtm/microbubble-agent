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
 */

import { test, expect } from '@playwright/test'

const BASE_URL = process.env.BASE_URL || 'http://localhost:3000'
const VIEWPORT = { width: 390, height: 844 } // iPhone 14

// v77 P2.6-C: 从 3 路由扩到 6 路由 (与 desktop 对齐)
// v77 P2.6-D.4: 扩到 9 路由 (+projects /members /project-stats)
// v78: /projects /members 合并到 /workspace, 仍 9 路由
const CORE_ROUTES = [
  { path: '/dashboard', name: '01-dashboard' },
  { path: '/knowledge', name: '06-knowledge' },
  { path: '/chat', name: '03-chat' },
  // v77 P2.6-C 新增
  { path: '/tasks', name: '04-tasks' },
  { path: '/meetings', name: '05-meetings' },
  { path: '/settings', name: '07-settings' },
  // v78: 项目/成员合并到 /workspace, 声纹也包含在 workspace 第 3 个 tab
  { path: '/workspace?tab=projects', name: '08-workspace-projects' },
  { path: '/workspace?tab=members', name: '09-workspace-members' },
  { path: '/project-stats', name: '10-project-stats' },
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

  // 2026-10-05 S3.13: 给**数据依赖**的路由补 mock fixture (决策 1: 补 mock 不剔除)。
  //
  // 背景 (实测, 非推断):
  //   04-tasks / 05-meetings / 06-knowledge 三张基线**字节完全相同** (各 2743B),
  //   开图确认是**纯白页**。追查根因:
  //     DOM: .mobile-meeting-view 渲染了 (display:flex, visibility:visible),
  //          但 390x844 内无任何子元素 —— app html 12606B, body text 仅 51 字符
  //     API: GET /api/v1/meetings → 200, items 为空 (测试库没有会议数据)
  //     mock 掉数据后: body 立即变成 "会议管理🔍+全部今天本周本月8月2023:00例行组会已完成..."
  //   ⇒ 根因是**测试库无数据**, 不是渲染 bug。所以修法是补 fixture 让它渲染
  //     确定态, 而不是剔除用例 (剔除会让这三个页面永久失去视觉覆盖)。
  //
  // 为什么必须 mock 而不是靠 seed 数据:
  //   seed 写进 DB 的数据会随 init_db.py 的演进漂移, 且 CI 与本机 seed 内容
  //   可能不同 ⇒ 基线再次不稳定。page.route mock 把数据钉在 spec 里,
  //   与 DB 完全解耦 —— 与 secondary-routes.spec.mjs 已有模式一致。
  //
  // ⚠️ 只 mock 这三个路由需要的端点, 不做全量接管:
  //   未 mock 的请求会打到真后端, 若因此导致页面不稳定, 那本身就是需要修的
  //   真问题, 不该被 mock 掩盖 (fail-loud 原则)。
  async function installDataMocks(page, routePath) {
    const rx = (re) => (p) => re.test(p)
    const table = []

    if (routePath.startsWith('/tasks')) {
      table.push([
        rx(/^\/api\/v1\/tasks$/),
        () => ({
          items: [
            { id: 901, title: '正式实验', assignee_id: null, priority: 'medium', status: 'in_progress', due_date: null },
            { id: 902, title: '搭建膜法、电化学、超声及容器试剂等实验平台', assignee_id: null, priority: 'high', status: 'in_progress', due_date: '2026-09-15' },
          ],
          total: 2,
        }),
      ])
      table.push([
        rx(/^\/api\/v1\/tasks\/stats\/overview$/),
        () => ({ total: 2, in_progress: 2, done: 0, overdue: 0 }),
      ])
    }

    if (routePath.startsWith('/meetings')) {
      table.push([
        rx(/^\/api\/v1\/meetings$/),
        () => ({
          items: [
            { id: 248, title: '例行组会', status: 'completed', start_time: '2026-08-20T15:00:00', end_time: '2026-08-20T16:10:00', location: '主楼 305' },
            { id: 249, title: '超声功率对照组评审', status: 'recording', start_time: '2026-08-21T09:30:00', end_time: '2026-08-21T10:30:00', location: '实验楼 201' },
            { id: 250, title: '月度组会 (8月)', status: 'scheduled', start_time: '2026-08-28T14:00:00', end_time: '2026-08-28T15:30:00', location: '主楼 305' },
          ],
          total: 3,
        }),
      ])
      // ⚠️ 顶栏"正在听会"指示灯用的是**同一个** 路径 + 不同 query
      //   (`/api/v1/meetings?status=recording&page_size=1`), 所以上面的 matcher
      //   (只看 pathname) 已经覆盖它, 不能再加一条同名 matcher ——
      //   table 是顺序匹配, 后加的那条永远不会被命中 (死代码)。
      //   上面那条返回的 items 里含 status=recording 的会议, 顶栏会显示"正在听会"。
    }

    if (routePath.startsWith('/knowledge')) {
      table.push([
        rx(/^\/api\/v1\/knowledge$/),
        () => ({
          items: [
            { id: 999001, title: '微纳米气泡稳定性影响因素综述', category: '文献笔记', knowledge_type: 'note', summary: '综述 ζ 电位、溶解气过饱和度等四条主因素', tags: ['气泡稳定性'], created_at: '2026-08-18T09:30:00', updated_at: '2026-08-18T09:30:00' },
            { id: 999002, title: 'ζ 电位测量方法对比', category: '实验方法', knowledge_type: 'note', summary: '对比电泳法与电位法在微纳米气泡体系下的适用边界', tags: ['ζ电位'], created_at: '2026-08-19T10:00:00', updated_at: '2026-08-19T10:00:00' },
            { id: 999003, title: '超声空化阈值实验记录', category: '实验记录', knowledge_type: 'note', summary: '40 kHz / 15 W 组产泡粒径 D50 稳定在 480 nm', tags: ['超声空化'], created_at: '2026-08-20T14:00:00', updated_at: '2026-08-20T14:00:00' },
          ],
          total: 3,
        }),
      ])
      table.push([rx(/^\/api\/v1\/knowledge\/stats$/), () => ({ total: 3 })])
    }

    // 2026-10-05 S3.13 (第二轮): /workspace?tab=projects 与 /project-stats 同为数据依赖。
    //   实测 /project-stats 无 mock 时 body text 只有 45 字符:
    //     "‹项目动态0进行中0已完成0已暂停0总计🚀 活跃项目📁暂无活跃项目首页听会对话任务我的"
    //   即"暂无活跃项目"空态。补 mock 让它渲染确定态。
    if (routePath.startsWith('/workspace') || routePath.startsWith('/project-stats')) {
      table.push([
        rx(/^\/api\/v1\/projects$/),
        () => ({
          // ⚠️ status 必须是 'active' —— 实测踩坑: 我一开始写 'in_progress',
          //   MobileProjectStatsView.vue:87 的 activeProjects 是
          //     projects.filter(p => p.status === 'active')
          //   于是"总计"变成 1 但"活跃项目"仍是空态, body text 只有 54 字符。
          //   ⇒ fixture 必须照抄**视图真实期望的枚举**, 不能自造。
          items: [
            { id: 701, name: '微纳米气泡发生装置', status: 'active', owner: '王天志', progress: 62, due_date: '2026-09-30', members: ['王天志', '胡小琪'] },
            { id: 702, name: '膜法分离工艺验证', status: 'active', owner: '胡小琪', progress: 35, due_date: '2026-10-15', members: ['胡小琪'] },
            { id: 703, name: '电化学阻抗谱采集', status: 'completed', owner: '王天志', progress: 100, due_date: '2026-08-20', members: ['王天志'] },
            { id: 704, name: '容器试剂采购', status: 'paused', owner: '胡小琪', progress: 10, due_date: '2026-11-01', members: ['胡小琪'] },
          ],
          total: 3,
        }),
      ])
      table.push([
        rx(/^\/api\/v1\/members$/),
        () => ({
          items: [
            { id: 1, username: 'wangtianzhi', name: '王天志', role: 'admin', avatar: null },
            { id: 2, username: 'huxiaoqi', name: '胡小琪', role: 'member', avatar: null },
          ],
          total: 2,
        }),
      ])
      // 顶栏 tasks/stats/overview 也被 MainLayout 拉, 给确定值
      table.push([
        rx(/^\/api\/v1\/tasks\/stats\/overview$/),
        () => ({ total: 2, in_progress: 2, done: 0, overdue: 0 }),
      ])
    }

    if (table.length === 0) return
    await page.route('**/api/v1/**', (route) => {
      const url = new URL(route.request().url())
      for (const [matcher, body] of table) {
        if (matcher(url.pathname)) {
          return route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify(body(url)),
          })
        }
      }
      // 未 mock 的请求**放行**到真后端, 不 404 —— 让它保持与真实环境的连接,
      // 出问题时能看出是数据缺而不是 mock 缺。
      return route.fallback()
    })
  }

  for (const route of CORE_ROUTES) {
    test(`${route.name} 截图对比 baseline`, async ({ page }) => {
      await injectAuth(page)
      await installDataMocks(page, route.path)
      await page.goto(`${BASE_URL}${route.path}`, { waitUntil: 'networkidle' })

      // 等动画/异步数据加载完成
      await page.waitForTimeout(800)

      // v77 P2.6-C: baseline 对比
      // 首次跑会自动生成 tests/visual/mobile/visual-regression.spec.mjs-snapshots/{name}-iphone14.png
      await expect(page).toHaveScreenshot(`${route.name}.png`, {
        fullPage: true,
        animations: 'disabled',
        maxDiffPixelRatio: 0.002,
      })

      // 验证页面真的渲染了内容 (避免空白页通过 baseline 对比)
      //
      // 2026-10-05 S3.13: 阈值从 >10 提到 >=80, 并说明它是**实测标定**的。
      //
      //   原断言 `> 10` 太弱: 那三张纯白页的 body text 恰好是 **51 字符, 能过**
      //   —— 断言形同虚设, 这正是"空态混进基线"没被拦住的最后一道缺口。
      //
      //   阈值怎么定的 (实测标定, 不是拍脑袋 —— 我先试了 120, 被 meetings 打脸):
      //     纯白页 (mock 前)          body text = 51 字符
      //     /meetings (mock 后, 真实) body text = 119 字符
      //       "会议管理🔍+全部今天本周本月8月2023:00例行组会已完成📍 主楼 305
      //        8月2117:30超声功率对照组评审录制中📍 实验楼 201
      //        8月2822:00月度组会 (8月)已预约📍 主楼 305正在听会..."
      //     ⇒ 真实最小值 119, 纯白 51。取 **80** = 两者之间的宽裕中点:
      //       离纯白页 +29 字符余量, 离真实最小值 -39 字符余量。
      //   另一条独立防线 (不靠字符数): toHaveScreenshot 本身在纯色页上
      //   什么都不剩, 但那正是我们**要拦住**的 —— 所以字符数断言是必要的。
      const bodyText = (await page.textContent('body')) ?? ''
      expect(
        bodyText.trim().length,
        `${route.name} 页面应渲染内容 (阈值 80 由实测标定: 纯白页 51 / 真实最小 119)`,
      ).toBeGreaterThanOrEqual(80)
    })
  }

  // v76.2h: PWA manifest 测试不属于视觉回归范畴, 移到独立 spec
  // (dev server 上 /manifest.webmanifest 404, 仅 build 产物有效)
  // 视觉回归 spec 应只关注截图 baseline 对比
})