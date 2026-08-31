/**
 * mobile-baseline.spec.mjs — 移动端 6 屏基线渲染 spec (page.route mock, 确定性强)
 *
 * 2026-09-01 创建.
 *
 * 背景:
 * 之前截图 /drive/file/99/comments 落到 fallback /drive 空态 — 根因是 spec 依赖
 * dev DB 真数据, fileId 无效时 MobileFileCommentsView 静默渲染空评论页, 或路由守卫
 * / MainLayout 请求失败导致白屏. 本 spec 用 page.route 拦截全部后端 API, 返回
 * 固定 fixture, 不依赖 dev DB / 登录态 / 网络 (类 20.213 全链路验证思路的前端版).
 *
 * 覆盖 6 屏 (每屏断言真实渲染内容, 不只是 body.length > 10):
 * 1. /dashboard         — 欢迎卡 + 统计 3 卡 + 待办任务行 + 头部铃铛 badge
 * 2. /drive             — 文件 grid 卡片 (dashboard 聚合预拉路径)
 * 3. /drive/file/301    — 文件详情 (info card + 评论区)
 * 4. /drive/file/301/comments — 评论独立页 (tab 计数 + 评论列表 + 输入栏)
 * 5. /meetings/21       — 会议详情 (hero + 摘要 + 转录分页)
 * 6. /knowledge/55      — 知识详情 (分类/标签/三元组/摘要)
 * 7. /admin/agent-traces — Trace 卡片列表 (全绿 happy path + error 兜底态)
 *
 * 登录态: router.beforeEach 只查 localStorage.access_token → addInitScript 注入.
 * MainLayout onMounted 会打 /auth/me + /members + /meetings?status=recording —
 * 全部 mock 掉避免 401 噪音.
 *
 * 运行:
 *   npx playwright test tests/e2e/mobile-baseline.spec.js
 *
 * 注意: 本 spec 挂在 tests/e2e/ 下 (vitest 不扫, playwright 默认 testDir 是
 * tests/visual — 需显式 --config 或用 playwright.config 的 e2e project 跑).
 * 本仓库 playwright.config.js testDir=./tests/visual, 所以用
 *   npx playwright test tests/e2e/mobile-baseline.spec.js --config=playwright.config.js
 * 时会被 testDir 过滤 — 直接用 CLI 位置参数指定文件 + testDir 内路径匹配即可:
 *   npx playwright test --config playwright.e2e.config.js
 * (见 playwright.e2e.config.js, 本 spec 配套的极简 config)
 */

import { test, expect } from '@playwright/test'

const TOKEN = 'e2e-mock-token'

// ---- 固定 fixtures (与后端 schema 对齐, 字段名照抄视图实际消费的 key) ----

const ME = {
  id: 1, username: 'wangtianzhi', name: '王天志', role: 'admin',
  avatar: null, wechat_id: 'wtz',
}

const MEMBERS = {
  items: [
    { id: 1, username: 'wangtianzhi', name: '王天志', wechat_id: 'wtz', avatar: null, role: 'admin' },
    { id: 2, username: 'dutonghe', name: '杜桐禾', wechat_id: 'dth', avatar: null, role: 'member' },
    { id: 3, username: 'yangxue', name: '杨雪', wechat_id: 'yx', avatar: null, role: 'leader' },
  ],
}

const DASHBOARD_SUMMARY = {
  in_progress_tasks: 4, done_tasks: 12, overdue_tasks: 2,
}

const RECENT_TASKS = {
  items: [
    { id: 901, title: '制备 CaCO3 微纳米气泡水样', assignee_id: 2, priority: 'high', status: 'in_progress', due_date: '2026-09-03T18:00:00Z' },
    { id: 902, title: '激光粒度仪校准', assignee_id: 1, priority: 'medium', status: 'in_progress', due_date: null },
  ],
}

// /api/v1/mobile/dashboard 聚合 (MobileDriveView 5 sections)
const MOBILE_DASHBOARD = {
  starred_files: [],
  team_root_files: [],
  my_uploads: [],
  recent_activities: [],
  notification_unread_count: 3,
}

const DRIVE_FILES = {
  items: [
    {
      id: 301, title: '气泡粒径分布实验数据 v2.xlsx', file_name: '气泡粒径分布实验数据 v2.xlsx',
      file_type: 'application/vnd.ms-excel', file_size: 48213, visibility: 'team',
      is_starred: true, created_by: '王天志', created_at: '2026-08-30T09:12:00Z',
      updated_at: '2026-08-31T14:00:00Z', storage_mode: 'drive',
    },
    {
      id: 302, title: '组会汇报-微纳米气泡.pdf', file_name: '组会汇报-微纳米气泡.pdf',
      file_type: 'application/pdf', file_size: 1820000, visibility: 'team',
      is_starred: false, created_by: '杨雪', created_at: '2026-08-29T10:00:00Z',
      updated_at: '2026-08-29T10:00:00Z', storage_mode: 'drive',
    },
  ],
  total: 2,
}

const FILE_301 = {
  id: 301, title: '气泡粒径分布实验数据 v2', file_name: '气泡粒径分布实验数据 v2.xlsx',
  file_type: 'excel', file_size: 48213, visibility: 'team', is_starred: true,
  owner_id: 1, created_by: '王天志', created_at: '2026-08-30T09:12:00Z',
  updated_at: '2026-08-31T14:00:00Z', version_number: 2, download_count: 5,
  file_hash: 'e3b0c44298fc1c149afbf4c8996fb924', folder_id: null,
}

// /api/v1/drive/files/{id}/comments — useNotifications.fetchComments 消费 resp.data.items
const COMMENTS_301 = {
  items: [
    {
      id: 8801, content: '第 3 组数据 @杨雪 麻烦复核一下粒径峰位', user_id: 1, user_name: '王天志',
      mentions: [3], parent_comment_id: null, thread_depth: 0, reply_count: 1, resolved: false,
      created_at: '2026-08-31T14:05:00Z',
    },
    {
      id: 8802, content: '收到, 明天上午反馈', user_id: 3, user_name: '杨雪',
      mentions: [], parent_comment_id: 8801, thread_depth: 1, reply_count: 0, resolved: false,
      created_at: '2026-08-31T15:00:00Z',
    },
    {
      id: 8803, content: '样品 A 与 B 的对比结论已同步进知识库', user_id: 2, user_name: '杜桐禾',
      mentions: [], parent_comment_id: null, thread_depth: 0, reply_count: 0, resolved: true,
      created_at: '2026-08-30T11:00:00Z',
    },
  ],
}

const MEETING_21 = {
  id: 21, title: '2026.8.30 例行例会', status: 'completed',
  start_time: '2026-08-30T02:00:00Z', location: '316 实验室',
  summary: '讨论了气泡粒径分布实验进展, 杨雪汇报了激光粒度仪校准结果, 全组确认下周开展水样制备对比实验。',
  key_points: [
    '【王天志】CaCO3 水样制备流程需要统一搅拌转速',
    '【杨雪】粒度仪校准完成, 偏差在 2% 以内',
    '【杜桐禾】建议补充对照样品的溶解氧数据',
  ],
  decisions: ['【全组】下周三前完成 3 组水样制备'],
  transcript_polished: [
    { ts: 0, speaker: '王天志', text: '开始例会, 先过一下上周任务。' },
    { ts: 35, speaker: '杨雪', text: '粒度仪校准完成, 偏差 2% 以内。' },
    { ts: 95, speaker: '杜桐禾', text: '对照样品建议补溶解氧。' },
  ],
  audio_url: '/api/v1/meetings/21/audio',
}

const KNOWLEDGE_55 = {
  id: 55, title: '微纳米气泡粒径与界面吸附关系', category: 'microbubble',
  knowledge_type: 'research_note', created_at: '2026-08-28T08:00:00Z',
  tags: ['气泡', '吸附', '粒径'],
  key_concepts: ['界面吸附', 'Young-Laplace', '粒径分布'],
  related_topics: ['水处理', '气浮'],
  entities: [
    { subject: '微纳米气泡', predicate: '表现出', object: '界面吸附增强', condition: '粒径 < 50μm', confidence: 0.86 },
  ],
  summary: '微纳米气泡粒径越小, 比表面积越大, 界面吸附能力随粒径减小而增强, 在 50μm 以下尤为显著。',
  content: '## 原理\n\nYoung-Laplace 方程给出附加压强与半径的反比关系...\n\n## 实验证据\n\n三组对照实验显示...',
  source: '组会讨论 + 文献 Smith 2024',
}

const AGENT_TRACES = {
  items: [
    { id: 7001, trace_type: 'tool_call', tool_name: 'run_gaussian_calculation', session_id: 'sess-abc123def456', duration_ms: 5230, status: 'ok', created_at: '2026-08-31T10:00:00Z' },
    { id: 7002, trace_type: 'llm', action: 'synthesize_stream', session_id: 'sess-abc123def456', duration_ms: 812, status: 'ok', created_at: '2026-08-31T10:01:00Z' },
    { id: 7003, trace_type: 'error', action: 'rag_retrieve', session_id: 'sess-xyz789', duration_ms: 120, status: 'error', created_at: '2026-08-31T10:02:00Z' },
  ],
}

// ---- 路由 mock 安装器 ----

/**
 * 拦截所有视图会触发的 API. 未匹配的 /api 请求 fail-loud (abort),
 * 防止 spec 悄悄打到 dev 后端产生不确定性.
 */
async function installApiMocks(page) {
  const json = (data) => ({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(data),
  })

  await page.route('**/api/**', (route) => {
    const url = new URL(route.request().url())
    const p = url.pathname

    if (p === '/api/v1/auth/me') return route.fulfill(json(ME))
    if (p === '/api/v1/members') return route.fulfill(json(MEMBERS))
    if (p === '/api/v1/dashboard/summary') return route.fulfill(json(DASHBOARD_SUMMARY))
    if (p === '/api/v1/tasks') return route.fulfill(json(RECENT_TASKS))
    if (p === '/api/v1/mobile/dashboard') return route.fulfill(json(MOBILE_DASHBOARD))

    // drive
    if (p === '/api/v1/drive/files') {
      // MobileDriveView files tab: fetchFiles; 也可能带 starred_only 等参数 — 统一返回
      return route.fulfill(json(DRIVE_FILES))
    }
    if (p === '/api/v1/drive/starred') return route.fulfill(json({ items: [], total: 0 }))
    if (p === '/api/v1/drive/trash') return route.fulfill(json({ items: [], total: 0 }))
    if (p === '/api/v1/drive/files/301') return route.fulfill(json(FILE_301))
    if (p === '/api/v1/drive/files/301/comments') return route.fulfill(json(COMMENTS_301))
    if (p === '/api/v1/folders/tree') return route.fulfill(json({ tree: [] }))

    // meetings (详情 + useRecordingState 的 status=recording 探测)
    if (p === '/api/v1/meetings/21') return route.fulfill(json(MEETING_21))
    if (p === '/api/v1/meetings') return route.fulfill(json({ items: [], total: 0 }))

    // knowledge
    if (p === '/api/v1/knowledge/55') return route.fulfill(json(KNOWLEDGE_55))

    // notifications (铃铛)
    if (p === '/api/v1/notifications/unread-count') return route.fulfill(json({ unread_count: 3 }))
    if (p === '/api/v1/notifications') return route.fulfill(json({ items: [], unread_count: 3 }))

    // admin agent traces
    if (p === '/api/v1/admin/agent-traces') return route.fulfill(json(AGENT_TRACES))

    // 未匹配的 API 一律 500 fail-loud, 让 spec 暴露新依赖而不是静默空态
    console.warn(`[mobile-baseline] unmocked API: ${route.request().method()} ${p}`)
    return route.fulfill({ status: 501, contentType: 'application/json', body: JSON.stringify({ detail: `unmocked: ${p}` }) })
  })
}

/** 注入登录态 (router 守卫 + 各视图的 Bearer header) */
async function injectAuth(page) {
  await page.addInitScript((tk) => {
    localStorage.setItem('access_token', tk)
    localStorage.setItem('user_info', JSON.stringify({
      id: 1, username: 'wangtianzhi', name: '王天志', role: 'admin', avatar: null,
    }))
  }, TOKEN)
}

async function gotoMobile(page, path) {
  await page.goto(path, { waitUntil: 'domcontentloaded' })
  // 等一轮路由 + 数据渲染
  await page.waitForLoadState('networkidle').catch(() => {})
}

test.describe('移动端基线渲染 (mock API)', () => {
  test.beforeEach(async ({ page }) => {
    await installApiMocks(page)
    await injectAuth(page)
    await page.setViewportSize({ width: 390, height: 844 })
    await page.emulateMedia({ reducedMotion: 'reduce' })
  })

  test('dashboard: 欢迎卡 + 统计 + 待办 + 铃铛 badge', async ({ page }) => {
    await gotoMobile(page, '/dashboard')

    await expect(page.locator('.mobile-dashboard')).toBeVisible()
    await expect(page.locator('.header-title')).toHaveText('首页')

    // 头部铃铛 (本 spec 配套实装) — 未读数来自 /notifications/unread-count
    const bell = page.locator('.notif-bell')
    await expect(bell).toBeVisible()
    await expect(bell.locator('.notif-badge')).toHaveText('3')

    // 欢迎卡
    await expect(page.locator('.welcome-card .greeting')).toContainText('王天志')

    // 统计 3 卡 (in_progress / done / overdue)
    const statNums = page.locator('.stat-card .stat-num')
    await expect(statNums).toHaveText(['4', '12', '2'])

    // 待办任务 2 行
    await expect(page.locator('.task-item')).toHaveCount(2)
    await expect(page.locator('.task-item').first()).toContainText('制备 CaCO3 微纳米气泡水样')
  })

  test('dashboard: API 失败走骨架/空态不白屏', async ({ page }) => {
    // summary + tasks 双双 500 → v-if="!loading && summary" 不渲染, 空态兜底
    await page.unrouteAll()
    await page.route('**/api/**', (route) => {
      const p = new URL(route.request().url()).pathname
      if (p === '/api/v1/auth/me') return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(ME) })
      if (p === '/api/v1/members') return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MEMBERS) })
      if (p === '/api/v1/notifications/unread-count') return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ unread_count: 0 }) })
      if (p === '/api/v1/meetings') return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [], total: 0 }) })
      return route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'server error' }) })
    })

    await gotoMobile(page, '/dashboard')
    await expect(page.locator('.mobile-dashboard')).toBeVisible()
    await expect(page.locator('.empty-section .empty-title')).toHaveText('今日任务已完成！')
  })

  test('drive: 文件 grid 2 卡片 + header 渲染', async ({ page }) => {
    await gotoMobile(page, '/drive')

    await expect(page.locator('.mobile-drive-view')).toBeVisible()
    // files tab 走 fetchFiles → DRIVE_FILES
    await expect(page.locator('.drive-file-card')).toHaveCount(2)
    await expect(page.locator('.drive-file-card').first()).toContainText('气泡粒径分布实验数据 v2.xlsx')
    // tab 栏 4 项
    await expect(page.locator('.drive-tab-btn')).toHaveCount(4)
  })

  test('drive file detail: 信息卡 + 评论区渲染 (不再 fallback 到 /drive)', async ({ page }) => {
    await gotoMobile(page, '/drive/file/301')

    // 关键防回归断言: 停在 file detail 页 (之前 spec 因 fileId 无效 fallback 到 /drive)
    await expect(page).toHaveURL(/\/drive\/file\/301$/)
    await expect(page.locator('.mobile-file-detail')).toBeVisible()

    await expect(page.locator('.mfd-title')).toHaveText('气泡粒径分布实验数据 v2.xlsx')
    await expect(page.locator('.mfd-info-list')).toContainText('excel')
    // 评论 thread: 顶层 2 + 嵌套 1
    await expect(page.locator('.mobile-comment-thread')).toBeVisible()
  })

  test('drive comments: tab 计数 + 树形列表 + 输入栏真渲染', async ({ page }) => {
    await gotoMobile(page, '/drive/file/301/comments')

    await expect(page).toHaveURL(/\/drive\/file\/301\/comments$/)
    await expect(page.locator('.mobile-file-comments-view')).toBeVisible()

    // header: 文件名 + 评论计数徽章
    await expect(page.locator('.mfcc-count')).toHaveText('3')

    // 3 tab 带 badge: 未解决 2 / 全部 3 / 已解决 1
    const tabBtns = page.locator('.mfcc-tab-btn')
    await expect(tabBtns).toHaveCount(3)
    await expect(page.locator('.mfcc-tab-btn', { hasText: '未解决' })).toContainText('2')
    await expect(page.locator('.mfcc-tab-btn', { hasText: '全部' })).toContainText('3')
    await expect(page.locator('.mfcc-tab-btn', { hasText: '已解决' })).toContainText('1')

    // 默认 open tab: 只有王天志 1 条未解决顶层 (杨雪是嵌套回复, 杜桐禾已解决被过滤)
    await expect(page.locator('.mfcc-top')).toHaveCount(1)
    await expect(page.locator('.mfcc-top').first()).toContainText('麻烦复核一下粒径峰位')
    // 嵌套回复展开 (depth=1)
    await expect(page.locator('.mfcc-top').first()).toContainText('收到, 明天上午反馈')
    // resolved tag 只在已解决评论上
    await expect(page.locator('.mfcc-resolved-tag')).toHaveCount(0)

    // 底部输入栏
    await expect(page.locator('.mfcc-compose textarea')).toBeVisible()

    // 切已解决 tab → 1 条 + resolved 标签
    await page.locator('.mfcc-tab-btn', { hasText: '已解决' }).click()
    await expect(page.locator('.mfcc-top')).toHaveCount(1)
    await expect(page.locator('.mfcc-resolved-tag')).toHaveCount(1)
  })

  test('meeting detail: hero + 纪要 + 转录 tab', async ({ page }) => {
    await gotoMobile(page, '/meetings/21')

    await expect(page.locator('.mobile-meeting-detail')).toBeVisible()
    await expect(page.locator('.hero-title')).toHaveText('2026.8.30 例行例会')
    await expect(page.locator('.status-text')).toHaveText('已完成')

    // 纪要 tab 默认激活: 摘要 + 3 要点 + 1 决议
    await expect(page.locator('.minutes-tab')).toContainText('讨论了气泡粒径分布实验进展')
    await expect(page.locator('.point-item')).toHaveCount(3)
    await expect(page.locator('.decision-item')).toHaveCount(1)

    // 切转录 tab → polished 段落 (ts 字段)
    await page.locator('.tab-item', { hasText: '转录' }).click()
    await expect(page.locator('.transcript-segment')).toHaveCount(3)
    await expect(page.locator('.transcript-segment').first()).toContainText('开始例会')
  })

  test('knowledge detail: 元信息 + 三元组 + 摘要', async ({ page }) => {
    await gotoMobile(page, '/knowledge/55')

    await expect(page.locator('.mobile-knowledge-detail')).toBeVisible()
    await expect(page.locator('.detail-title')).toHaveText('微纳米气泡粒径与界面吸附关系')
    await expect(page.locator('.category-badge')).toContainText('微纳米气泡')

    // 标签 chips
    await expect(page.locator('.tag-chip')).toHaveCount(3)

    // 核心概念 chips
    await expect(page.locator('.concept-chip')).toHaveCount(3)

    // 三元组卡 + 置信度
    await expect(page.locator('.triple-card')).toHaveCount(1)
    await expect(page.locator('.triple-card')).toContainText('界面吸附增强')

    // 摘要
    await expect(page.locator('.summary-text')).toContainText('界面吸附能力随粒径减小而增强')
  })

  test('agent traces: 卡片列表 + 详情 sheet', async ({ page }) => {
    await gotoMobile(page, '/admin/agent-traces')

    await expect(page.locator('.mobile-agent-traces')).toBeVisible()

    // 3 张 trace 卡
    const cards = page.locator('.trace-card')
    await expect(cards).toHaveCount(3)
    await expect(cards.first()).toContainText('run_gaussian_calculation')
    await expect(cards.first()).toContainText('5230ms')

    // 点第一张 → 详情 sheet JSON
    await cards.first().click()
    await expect(page.locator('.sheet-title')).toHaveText('Trace 详情')
    await expect(page.locator('.json-content')).toContainText('run_gaussian_calculation')
  })

  test('agent traces: API 500 → 空态兜底不白屏', async ({ page }) => {
    await page.unrouteAll()
    await page.route('**/api/**', (route) => {
      const p = new URL(route.request().url()).pathname
      if (p === '/api/v1/auth/me') return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(ME) })
      if (p === '/api/v1/members') return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MEMBERS) })
      if (p === '/api/v1/meetings') return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [], total: 0 }) })
      return route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'server error' }) })
    })

    await gotoMobile(page, '/admin/agent-traces')
    await expect(page.locator('.mobile-agent-traces')).toBeVisible()
    await expect(page.locator('.empty-state .empty-title')).toHaveText('暂无 Trace 记录')
  })
})
