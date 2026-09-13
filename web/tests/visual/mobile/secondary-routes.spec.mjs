/**
 * tests/visual/mobile/secondary-routes.spec.mjs
 *
 * 移动端二级页面视觉回归 (2026-09-01 收编自一次性 E:/tmp 截图脚本)
 *
 * 与 visual-regression.spec.mjs (9 个一级路由) 互补, 覆盖二级/覆盖层页面:
 *   01 home-bell        /dashboard                首页 PageHeader 铃铛入口 (badge)
 *   02 cmd-palette      /drive + ⌘                命令面板覆盖层 (元素截图, 隔离背景)
 *   03 meeting-room     /meetings/room            开始听会
 *   04 meeting-detail   /meetings/:id             听会详情 (mock)
 *   05 knowledge-detail /knowledge/:id            知识详情 (mock)
 *   06 agent-traces     /admin/agent-traces       Agent Trace 监控 (mock)
 *   07 file-detail      /drive/file/:id           文件详情 (mock, 个人盘为空也能真渲染)
 *   08 file-comments    /drive/file/:id/comments  文件评论 (mock, 同上)
 *
 * 设计纪律:
 *   - 二级页数据全部 page.route mock → 基线与 dev DB 状态解耦, 确定性渲染
 *     (旧一次性脚本依赖真库: 个人盘为空时 file-detail/comments 双双 fallback
 *      到 /drive 空态, 两张基线字节完全相同 — 本 spec 用 fixture 根治)
 *   - 基线走 toHaveScreenshot → 落在本目录 secondary-routes.spec.mjs-snapshots/,
 *     严禁把基线截图写进 OS tmp (Windows 假 /tmp = E:\tmp, CLAUDE.md 类 20 记录过)
 *   - 登录态: router 守卫只查 localStorage truthiness (router/index.js L278),
 *     全 mock 后无需真 token; 沿用双注入模式与一级 spec 一致
 *   - 首页 hero 问候语/日期随墙钟漂移 (晚上好/2026年X月X日), 文本面积小,
 *     在 0.2% diff 阈值内; 跨天大漂移时 --update-snapshots 刷新即可
 *
 * 用法:
 *   cd web && npm run dev                          # :3000, /api 代理到 :8000
 *   npx playwright test tests/visual/mobile/secondary-routes.spec.mjs --update-snapshots
 *   npx playwright test tests/visual/mobile/secondary-routes.spec.mjs            # 对比
 *
 * 前置: dev server 起着即可, 后端不要求有数据 (mock 表兜底, 未 mock 的 /api
 *       请求会在 console 打 [visual] unmocked 并回 404 — 看到就先补 fixture)
 */

import { test, expect } from '@playwright/test'

const BASE_URL = process.env.BASE_URL || 'http://localhost:3000'
const VIEWPORT = { width: 390, height: 844 } // iPhone 14

// ============================================================
// Fixtures (单源: 本文件顶部, 改这里 → --update-snapshots 重建基线)
// ============================================================

const ME_FIXTURE = {
  id: 1,
  username: 'wangtianzhi',
  name: '王天志',
  role: 'admin',
  avatar: null,
  wechat_id: 'wangtianzhi',
}

const HOME_SUMMARY_FIXTURE = {
  in_progress_tasks: 19,
  done_tasks: 75,
  overdue_tasks: 7,
  meetings_this_week: 3,
  knowledge_count: 531,
}

const HOME_TASKS_FIXTURE = {
  items: [
    {
      id: 901,
      title: '正式实验',
      assignee_id: null,
      priority: 'medium',
      status: 'in_progress',
      due_date: null,
    },
    {
      id: 902,
      title: '搭建膜法、电化学、超声及容器试剂等实验平台',
      assignee_id: null,
      priority: 'high',
      status: 'in_progress',
      due_date: '2026-09-15',
    },
  ],
  total: 2,
}

// /drive 首页聚合接口 (mobile/dashboard): notification_unread_count 供 Drive 顶栏 badge
const DRIVE_AGG_FIXTURE = {
  notification_unread_count: 3,
  recent_files: [],
  recent_activities: [],
}

const UNREAD_FIXTURE = { unread_count: 3 }

const MEETING_ID = 248
const MEETING_FIXTURE = {
  id: MEETING_ID,
  title: '例行组会 (fixture)',
  status: 'completed',
  location: '主楼 305',
  start_time: '2026-08-20T15:00:00',
  end_time: '2026-08-20T16:10:00',
  summary:
    '本次组会围绕微纳米气泡发生装置的对照实验展开: 王天志汇报了超声功率 40 kHz/15 W 组的产泡粒径分布, 胡小琪补充了电化学阻抗谱的初步结果。全组一致同意下周前完成三组重复实验, 并将原始数据同步到网盘实验目录。',
  key_points: [
    '【王天志】超声组气泡 D50 稳定在 480 nm, 浓度较对照组高 2.3 倍',
    '【胡小琪】EIS 谱显示膜电位随气泡吸附出现可复现漂移',
    '【全组】下周完成三组重复实验, 数据入网盘实验目录',
  ],
  decisions: [
    '【全组】统一采用 40 kHz/15 W 作为超声组标准参数',
    '【王天志/胡小琪】重复实验分工本周五前确认排期',
  ],
  participants: [],
  audio_url: '/api/v1/meetings/248/audio',
  error_reason: null,
}

const KNOWLEDGE_ID = 999001
const KNOWLEDGE_FIXTURE = {
  id: KNOWLEDGE_ID,
  title: '微纳米气泡稳定性影响因素综述 (fixture)',
  category: '文献笔记',
  knowledge_type: 'note',
  source: '课题组内部整理',
  content:
    '气液界面电荷密度ζ电位绝对值越高, 泡壁双电层排斥越强, 气泡聚并受阻; 水中溶解气过饱和度决定气泡 Ostwald 熟化速率, 温度升高会加速气泡溶解; 表面活性剂在 ppm 级浓度即可显著延长气泡寿命半衰期。',
  summary:
    '综述 ζ 电位、溶解气过饱和度、温度与表面活性剂浓度四条主因素对微纳米气泡寿命的影响机制, 给出课题组实验设计建议。',
  tags: ['气泡稳定性', 'ζ电位', '实验设计'],
  key_concepts: ['双电层排斥', 'Ostwald 熟化', '表面活性剂'],
  related_topics: ['超声空化阈值', '气泡粒径测量方法'],
  entities: [],
  created_at: '2026-08-18T09:30:00',
  updated_at: '2026-08-18T09:30:00',
}

const TRACES_FIXTURE = {
  items: [
    {
      id: 9003,
      trace_type: 'agent',
      action: 'Agent 调用',
      status: 'success',
      tool_name: null,
      session_id: 'sess-248c',
      duration_ms: 3120,
      created_at: '2026-08-31T19:58:00',
    },
    {
      id: 9002,
      trace_type: 'tool',
      action: '工具调用 knowledge_search',
      status: 'success',
      tool_name: 'knowledge_search',
      session_id: 'sess-248c',
      duration_ms: 410,
      created_at: '2026-08-31T19:57:00',
    },
    {
      id: 9001,
      trace_type: 'llm',
      action: 'LLM 调用',
      status: 'error',
      tool_name: null,
      session_id: 'sess-248b',
      duration_ms: 8020,
      created_at: '2026-08-31T19:50:00',
    },
  ],
  total: 3,
}

const FILE_ID = 999001
const FILE_FIXTURE = {
  id: FILE_ID,
  file_name: '2026-08-30 超声对照组实验记录.pdf',
  title: null,
  file_size: 245760,
  file_type: 'pdf',
  visibility: 'team',
  is_starred: true,
  created_by: '王天志',
  created_at: '2026-08-30T10:24:00',
  updated_at: '2026-08-30T15:02:00',
  folder_id: 42,
  version_number: 3,
  download_count: 7,
  file_hash: '9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08',
}

const COMMENTS_FIXTURE = {
  items: [
    {
      id: 1,
      file_id: FILE_ID,
      user_id: 1,
      user_name: '王天志',
      content: '对照组超声功率按 40 kHz / 15 W 记录, 请核对第 3 节数据。',
      mentions: [2],
      parent_comment_id: null,
      thread_depth: 0,
      reply_count: 1,
      resolved: false,
      created_at: '2026-08-30T11:02:00',
    },
    {
      id: 2,
      file_id: FILE_ID,
      user_id: 2,
      user_name: '胡小琪',
      content: '已核对, 第 3 节与原始导出一致。',
      mentions: [],
      parent_comment_id: null,
      thread_depth: 0,
      reply_count: 0,
      resolved: true,
      created_at: '2026-08-30T13:40:00',
    },
  ],
  total: 2,
}

const MEMBERS_FIXTURE = {
  items: [
    { id: 1, username: 'wangtianzhi', name: '王天志', wechat_id: null, avatar: null, role: 'admin' },
    { id: 2, username: 'huxiaoqi', name: '胡小琪', wechat_id: null, avatar: null, role: 'member' },
  ],
  total: 2,
}

// ============================================================
// Mock 基建
// ============================================================

const rx = (re) => (path) => re.test(path)

/**
 * 全量接管 /api/v1: 命中 mock 表 → 200 fixture; 未命中 → console warn + 404。
 * fail-loud 原则: 未 mock 请求必须可见, 不允许静默打到真后端拿随机数据。
 */
async function installApiMocks(page, extra = []) {
  const table = [
    [rx(/^\/api\/v1\/auth\/me$/), () => ME_FIXTURE],
    [rx(/^\/api\/v1\/notifications\/unread-count$/), () => UNREAD_FIXTURE],
    ...extra,
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
    console.warn(`[visual] unmocked API: ${route.request().method()} ${url.pathname}${url.search}`)
    return route.fulfill({
      status: 404,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'visual-regression: endpoint not mocked' }),
    })
  })
}

// 双注入登录态 (与 visual-regression.spec.mjs 同纪律; 守卫只查 truthy)
async function injectAuth(page) {
  const token = 'visual-regression-mock-token'
  await page.context().addCookies([{
    name: 'access_token',
    value: token,
    domain: new URL(BASE_URL).hostname,
    path: '/',
  }])
  await page.addInitScript((tk) => {
    localStorage.setItem('access_token', tk)
  }, token)
}

async function shot(page, name) {
  await page.waitForLoadState('networkidle')
  await expect(page).toHaveScreenshot(`${name}.png`, {
    fullPage: true,
    animations: 'disabled',
    maxDiffPixelRatio: 0.002,
  })
}

test.describe('移动端二级页面视觉回归 (全 mock, 与 dev DB 解耦)', () => {
  test.use({ viewport: VIEWPORT })

  test('01 home-bell: 首页铃铛入口 + 未读 badge', async ({ page }) => {
    await installApiMocks(page, [
      [rx(/^\/api\/v1\/dashboard\/summary$/), () => HOME_SUMMARY_FIXTURE],
      [rx(/^\/api\/v1\/tasks$/), () => HOME_TASKS_FIXTURE],
    ])
    await injectAuth(page)
    await page.goto(`${BASE_URL}/dashboard`)

    // 行为断言先于像素: 铃铛在 + badge 数字来自 store
    const bell = page.locator('.home-bell-btn')
    await expect(bell).toBeVisible()
    await expect(bell.locator('.home-bell-badge')).toHaveText('3')
    await shot(page, '01-home-bell')
  })

  test('02 cmd-palette: Drive ⌘ 命令面板覆盖层', async ({ page }) => {
    await installApiMocks(page, [
      [rx(/^\/api\/v1\/mobile\/dashboard$/), () => DRIVE_AGG_FIXTURE],
    ])
    await injectAuth(page)
    await page.goto(`${BASE_URL}/drive`)
    await page.click('button[aria-label="命令面板 (Ctrl+K)"]')
    const modal = page.locator('.command-palette-modal')
    await expect(modal).toBeVisible()
    await page.waitForLoadState('networkidle')
    // 元素截图隔离背景 (drive 页内容不参与 diff)
    await expect(modal).toHaveScreenshot('02-cmd-palette.png', { animations: 'disabled' })
  })

  test('03 meeting-room: 开始听会', async ({ page }) => {
    await installApiMocks(page)
    await injectAuth(page)
    await page.goto(`${BASE_URL}/meetings/room`)
    await expect(page.getByRole('button', { name: '开始听会' })).toBeVisible()
    await shot(page, '03-meeting-room')
  })

  test('04 meeting-detail: 听会详情 (fixture)', async ({ page }) => {
    await installApiMocks(page, [
      [rx(new RegExp(`^/api/v1/meetings/${MEETING_ID}$`)), () => MEETING_FIXTURE],
    ])
    await injectAuth(page)
    await page.goto(`${BASE_URL}/meetings/${MEETING_ID}`)
    await expect(page.getByRole('heading', { name: /例行组会 \(fixture\)/ })).toBeVisible()
    await shot(page, '04-meeting-detail')
  })

  test('05 knowledge-detail: 知识详情 (fixture)', async ({ page }) => {
    await installApiMocks(page, [
      [rx(new RegExp(`^/api/v1/knowledge/${KNOWLEDGE_ID}$`)), () => KNOWLEDGE_FIXTURE],
    ])
    await injectAuth(page)
    await page.goto(`${BASE_URL}/knowledge/${KNOWLEDGE_ID}`)
    await expect(page.getByRole('heading', { name: /微纳米气泡稳定性影响因素综述/ }).first()).toBeVisible()
    await shot(page, '05-knowledge-detail')
  })

  test('06 agent-traces: 监控列表 (fixture)', async ({ page }) => {
    await installApiMocks(page, [
      [rx(/^\/api\/v1\/admin\/agent-traces$/), () => TRACES_FIXTURE],
    ])
    await injectAuth(page)
    await page.goto(`${BASE_URL}/admin/agent-traces`)
    await expect(page.getByText('工具调用 knowledge_search')).toBeVisible()
    await shot(page, '06-agent-traces')
  })

  test('07 file-detail: 网盘文件详情渲染真页面, 不 fallback /drive', async ({ page }) => {
    await installApiMocks(page, [
      [rx(new RegExp(`^/api/v1/drive/files/${FILE_ID}$`)), () => FILE_FIXTURE],
    ])
    await injectAuth(page)
    await page.goto(`${BASE_URL}/drive/file/${FILE_ID}`)
    // 关键行为断言 (本次修复目标): 渲染的是文件详情, 而非网盘空态 fallback
    await expect(page.getByText(FILE_FIXTURE.file_name)).toBeVisible()
    await expect(page.getByText('当前文件夹暂无文件')).toHaveCount(0)
    await expect(page.locator('.mfd-info-card')).toBeVisible()
    await shot(page, '07-file-detail')
  })

  test('08 file-comments: 文件评论渲染真页面 (fixture)', async ({ page }) => {
    await installApiMocks(page, [
      [rx(new RegExp(`^/api/v1/drive/files/${FILE_ID}$`)), () => FILE_FIXTURE],
      [rx(new RegExp(`^/api/v1/drive/files/${FILE_ID}/comments$`)), () => COMMENTS_FIXTURE],
      [rx(/^\/api\/v1\/members$/), () => MEMBERS_FIXTURE],
    ])
    await injectAuth(page)
    await page.goto(`${BASE_URL}/drive/file/${FILE_ID}/comments`)
    await expect(page.getByText('对照组超声功率按 40 kHz / 15 W 记录')).toBeVisible()
    await expect(page.getByText('当前文件夹暂无文件')).toHaveCount(0)
    await shot(page, '08-file-comments')
  })
})
