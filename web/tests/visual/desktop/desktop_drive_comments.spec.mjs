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

// W68 路线 F-4 桌面端评论 UI 核心视图
// 路径跟 MobileFileCommentsView (F-3) 对齐, 桌面端入口是 /drive/file/:id/comments
//
// 2026-10-05 S3.13 决策 2: **删掉 ?top / ?thread / ?focus 三个 query param**。
//
// 实测证据 (不是推断):
//   1. 全仓 grep `route.query` / `useRoute()` / `$route.query`
//      在 DesktopFileCommentsView 与 MobileFileCommentsView 里**零命中**
//      —— 两个视图根本不读 query, 那三个参数从来没有生效过。
//   2. 给它灌**带嵌套的真实数据**后逐个截图, 四个变体 md5 完全相同:
//        q=""        md5=f244bd56  textLen=122
//        q="?top=1"  md5=f244bd56  textLen=122
//        q="?thread=1" md5=f244bd56 textLen=122
//        q="?focus=1" md5=f244bd56  textLen=122
//      ⇒ 不是"数据没喂对", 是**参数本身是死代码**。
//   3. `03-thread` 声称测"嵌套回复 (thread_depth=1)", 但移动端
//      MobileFileCommentsView.vue:343 的 onReply 只有一句
//      `ElMessage.info('... 内联回复功能即将上线')` —— **内联回复功能根本不存在**,
//      桌面端 onReply (DesktopFileCommentsView.vue:430) 也只是"输入栏加 @user 前缀"。
//      ⇒ 03-thread 测的是一个**从未实现的功能**。
//   4. `04-input` 声称测"输入框聚焦", 但 MobileCommentInput 在 mounted 时
//      **无条件** autofocus —— 不需要任何 query 也会聚焦。
//
// 为什么"删参数"而不是"让参数生效":
//   让参数生效 = 给两个视图加 useRoute + 按 query 驱动 UI 状态, 即
//   **新造一个从未被产品定义过的 deep-link 功能** (W68 spec 里写的是
//   "测这 4 个视图", 不是"做 deep-link")。这属于 production code 改动,
//   超出"让门禁可判定"的范围。
//   而"删掉测一个不存在功能的用例"是把"没测到"记成"不需要测" ——
//   所以**只删 02-top / 03-thread / 04-input 这 3 个从未生效的 query 变体**,
//   保留真正有效的覆盖 (见下方 VIEW_STATES): 评论列表 + 真实交互态。
const VIEW_STATES = [
  { name: '01-list',    path: '/drive/file/99/comments', desc: '评论列表 (header + tabs + 列表 + sticky 输入栏)',
    act: null },
  // 真实可触发的交互态: 点"回复" → 输入栏加 @user 前缀并聚焦 (实测 md5 会变)
  { name: '02-reply-focus', path: '/drive/file/99/comments', desc: '点回复后输入栏 @user 前缀 + 聚焦态',
    act: 'reply' },
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
/**
 * 2026-10-05 S3.13 决策 1: 给评论页补 mock fixture。
 *
 * 背景 (实测): 测试库 `drive_documents` 与 `drive_comments` **都是 0 行**
 *   (psql 实测), 于是 fileId=99 渲染空态, 此前 4 个 query 变体的基线
 *   字节完全相同 —— 那不是"参数无效", 连画面都没有。
 *
 * 为什么 mock 而不是 seed:
 *   seed 写进 DB 的内容会随 init_db.py 演进漂移, 且 CI 与本机 seed 可能不同
 *   ⇒ 基线再次不稳定。page.route 把数据钉在 spec 里, 与 DB 完全解耦,
 *   与 secondary-routes.spec.mjs / visual-regression.spec.mjs 同一模式。
 *
 * 未 mock 的请求**放行**(route.fallback)到真后端而不是 404:
 *   这样"缺数据"与"mock 漏了"能区分开, 不会静默变成统一的 404 空态。
 */
async function installCommentMocks(page) {
  const rx = (re) => (p) => re.test(p)
  const table = [
    [rx(/^\/api\/v1\/drive\/files\/99$/), () => ({
      id: 99,
      file_name: '2026-08-30 超声对照组实验记录.pdf',
      title: null,
      file_size: 245760,
      file_type: 'pdf',
      visibility: 'team',
      is_starred: false,
      created_by: '王天志',
      created_at: '2026-08-30T10:24:00',
      updated_at: '2026-08-30T15:02:00',
      folder_id: 42,
      version_number: 3,
      download_count: 7,
    })],
    // 含一条嵌套回复 (parent_comment_id=1) —— 让 03-thread 想测的
    // "thread_depth=1 缩进" 真的出现在画面上
    [rx(/^\/api\/v1\/drive\/files\/99\/comments$/), () => ({
      items: [
        {
          id: 1, file_id: 99, user_id: 1, user_name: '王天志',
          content: '对照组超声功率按 40 kHz / 15 W 记录, 请核对第 3 节数据。',
          mentions: [2], parent_comment_id: null, thread_depth: 0,
          reply_count: 1, resolved: false, created_at: '2026-08-30T11:02:00',
        },
        {
          id: 2, file_id: 99, user_id: 2, user_name: '胡小琪',
          content: '已核对, 第 3 节与原始导出一致。',
          mentions: [], parent_comment_id: 1, thread_depth: 1,
          reply_count: 0, resolved: true, created_at: '2026-08-30T13:40:00',
        },
      ],
      total: 2,
    })],
    [rx(/^\/api\/v1\/members$/), () => ({
      items: [
        { id: 1, username: 'wangtianzhi', name: '王天志', wechat_id: null, avatar: null, role: 'admin' },
        { id: 2, username: 'huxiaoqi', name: '胡小琪', wechat_id: null, avatar: null, role: 'member' },
      ],
      total: 2,
    })],
  ]
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
    return route.fallback()
  })
}

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

      for (const pg of VIEW_STATES) {
        test(`${pg.name}: ${pg.desc}`, async ({ page }) => {
          await injectAuth(page)
          await installCommentMocks(page)
          await page.goto(`${BASE_URL}${pg.path}`, { waitUntil: 'domcontentloaded' })
          await waitForDesktopCommentsUI(page)

          // 2026-10-05 S3.13: 真实交互态 —— 点"回复"触发输入栏 @user 前缀 + 聚焦。
          //   实测 (mock 数据下): baseline md5=cc370417 textLen=365
          //                        点回复后  md5=1004d9cd textLen=391  ⇒ 画面真的变了
          //   这取代了此前那个从未生效的 `?top=1` / `?thread=1` / `?focus=1`。
          if (pg.act === 'reply') {
            const replyBtn = page.locator('text=回复').first()
            await expect(replyBtn, '应存在"回复"按钮 (DesktopCommentThread 交互)').toBeVisible()
            await replyBtn.click()
            // 等 onReply 的 setTimeout(focus) + 下一 tick
            await page.waitForTimeout(500)
          }

          // 验证页面真的渲染了评论 UI (避免空白页通过 baseline 对比)
          //
          // 2026-10-05: 阈值 10 -> 80。实测标定:
          //   mock 前(空态) body text ≈ 51 字符 (能过 >10, 形同虚设)
          //   mock 后(有评论) body text = 365 字符
          //   ⇒ 取 80 作中点。理由同 mobile/visual-regression.spec.mjs。
          const bodyText = (await page.textContent('body')) ?? ''
          expect(
            bodyText.trim().length,
            `${vp.name}/${pg.name} 页面应渲染内容 (阈值 80 实测标定: 空态 51 / 有数据 365)`,
          ).toBeGreaterThanOrEqual(80)

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
    await installCommentMocks(page)
    await page.goto(`${BASE_URL}/drive/file/99/comments`, { waitUntil: 'domcontentloaded' })
    await waitForDesktopCommentsUI(page)

    const bodyText = await page.textContent('body')
    expect((bodyText ?? '').trim().length,
      '页面应渲染内容 (阈值 80 实测标定: 空态 51 / 有数据 365)').toBeGreaterThanOrEqual(80)

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
    await installCommentMocks(page)
    await page.goto(`${BASE_URL}/drive/file/99/comments`, { waitUntil: 'domcontentloaded' })
    await waitForDesktopCommentsUI(page)

    // 滚动到列表底部
    await page.evaluate(() => {
      const body = document.querySelector('.dfcv-body')
      if (body) body.scrollTop = body.scrollHeight
    })
    await page.waitForTimeout(300)

    const bodyText = await page.textContent('body')
    expect((bodyText ?? '').trim().length,
      '页面应渲染内容 (阈值 80 实测标定: 空态 51 / 有数据 365)').toBeGreaterThanOrEqual(80)

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
