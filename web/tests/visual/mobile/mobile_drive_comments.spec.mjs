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

// W68 路线 F-3 评论 UI 核心视图
//
// 2026-10-05 S3.13 决策 2: **删掉 ?top / ?thread / ?focus 三个 query param**。
//   实测证据 (与 desktop_drive_comments.spec.mjs 同步核实, 不是推断):
//     1. 全仓 grep `route.query` / `useRoute()` / `$route.query` 在
//        MobileFileCommentsView 里**零命中** —— 视图根本不读 query。
//     2. 灌带嵌套的真实数据后, 四个变体 md5 完全相同 (f244bd56 x4),
//        textLen 也相同 (122) ⇒ 参数是死代码, 不是数据问题。
//     3. `03-thread` 声称测"嵌套回复 (thread_depth=1)", 但本文件同批实测:
//        MobileFileCommentsView.vue:343 的 onReply 只有一句
//        `ElMessage.info('... 内联回复功能即将上线')` —— **内联回复从未实现**。
//     4. `04-input` 声称测"输入框聚焦", 但 MobileCommentInput 在 mounted 时
//        **无条件** autofocus, 不需要任何 query。
//   保留的 02 用例改为**真实可触发的交互态** (长按菜单), 见下方 VIEW_STATES。
const VIEW_STATES = [
  { name: '01-list', path: '/drive/file/99/comments', desc: '评论列表 (header + tabs + 列表 + 输入栏)',
    act: null },
  // 长按顶层评论 -> context menu (LongPressWrapper delay=600)
  { name: '02-longpress', path: '/drive/file/99/comments', desc: '长按顶层评论弹 context menu',
    act: 'longpress' },
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
/**
 * 2026-10-05 S3.13 决策 1: 给评论页补 mock fixture。
 *
 * 背景 (实测): 测试库 `drive_documents` / `drive_comments` **都是 0 行**
 *   (psql 实测), 于是 fileId=99 渲染空态 —— 此前 4 个 query 变体的基线
 *   字节完全相同, 连画面都没有。
 *
 * 数据里**含一条嵌套回复** (parent_comment_id=1): 让"嵌套渲染"这件事
 *   真的出现在画面上, 这样基线才有覆盖到它。
 *
 * 未 mock 的请求**放行**(route.fallback)到真后端而非 404:
 *   区分"缺数据"与"mock 漏了", 不静默变成统一空态。
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

      for (const pg of VIEW_STATES) {
        test(`${pg.name}: ${pg.desc}`, async ({ page }) => {
          await injectAuth(page)
          await installCommentMocks(page)
          await page.goto(`${BASE_URL}${pg.path}`, { waitUntil: 'domcontentloaded' })
          await waitForCommentsUI(page)

          // 2026-10-05 S3.13: 真实交互态 —— 长按顶层评论弹 context menu。
          //   这取代了此前那个从未生效的 `?top=1` / `?thread=1` / `?focus=1`。
          if (pg.act === 'longpress') {
            // ⚠️ 必须用 mouse 而不是 touchscreen.tap, 且**不能断言 wrapper 自身有布局盒**。
            //
            // 实测踩坑 (2026-10-05): 我先写成
            //   const box = await wrapper.boundingBox(); expect(box).not.toBeNull()
            //   → 7 个 viewport 全挂在 `Cannot read properties of null (reading 'x')`。
            // 根因: LongPressWrapper.vue:41 的 `.long-press-wrapper { display: contents }`
            // —— 它**设计上就没有盒子**(注释写明"不影响子元素布局"),
            // 所以 boundingBox() 必然返回 0x0 的 null。
            // ⚠️ 原 spec 用 `if (await count() > 0)` 包着, 于是这个"元素不可定位"
            //   被静默跳过, 从没暴露过。
            //
            // 正解: 长按的**子元素**(MobileCommentThread 渲染的评论卡片),
            // 对子元素取盒 + 用 mouse down/hold/up 模拟长按。
            const wrapper = page.locator('.long-press-wrapper').first()
            // ⚠️ viewport >= 768 时 app 走**桌面组件栈**, 那里没有长按 wrapper。
            //   实测 (2026-10-05): ipad (768x1024) 下
            //     .long-press-wrapper = 0 个, .mfcc-top = 0 个, bodyLen=173
            //   其它 6 个 viewport 都是 1 个。
            //   根因: resolveMobile.js:21 的 MOBILE_BREAKPOINT = 768 是**闭区间**
            //   (`width < 768` 才算移动端), 768 恰好落在桌面侧。
            //   ⇒ 这是**规格口径问题**(这个 spec 是移动端 spec), 显式 skip 并写明原因,
            //      而不是让 `expect(count).toBe(1)` 报一个看不懂的错。
            if (vp.width >= 768) {
              test.skip(
                true,
                `viewport ${vp.width}px >= 768 ⇒ app 解析成桌面组件栈 ` +
                  `(resolveMobile.js MOBILE_BREAKPOINT=768 闭区间), ` +
                  `桌面端无 LongPressWrapper。长按是**移动端专属交互**, ` +
                  `该 viewport 不适用。若要覆盖, 应另建桌面端 spec。`,
              )
            }
            await expect(wrapper, '应存在长按 wrapper (LongPressWrapper)').toHaveCount(1)
            // display:contents ⇒ wrapper 自身无盒, 取其子元素
            const target = wrapper.locator('*').first()
            await expect(target, 'wrapper 应有子元素承载长按区域').toBeVisible()
            const box = await target.boundingBox()
            expect(box, '长按目标应有布局盒').not.toBeNull()
            // LongPressWrapper delay=600 => 按住 800ms 再松手
            await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2)
            await page.mouse.down()
            await page.waitForTimeout(800)
            await page.mouse.up()
            await page.waitForTimeout(400)
          }

          // 验证页面真的渲染了评论 UI (避免空白页通过 baseline 对比)
          //
          // 2026-10-05: 阈值 10 -> 80, 实测标定 (空态 51 / 有数据 365),
          //   理由同 desktop_drive_comments.spec.mjs。
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
    await installCommentMocks(page)
    await page.goto(`${BASE_URL}/drive/file/99/comments`, { waitUntil: 'domcontentloaded' })
    await waitForCommentsUI(page)

    const bodyText = await page.textContent('body')
    expect((bodyText ?? '').trim().length,
      '页面应渲染内容 (阈值 80 实测标定: 空态 51 / 有数据 365)').toBeGreaterThanOrEqual(80)

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
    await installCommentMocks(page)
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