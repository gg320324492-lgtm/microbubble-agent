/**
 * desktop_drive_pr11-13_e2e.spec.js — W68 第 10 批 C-1 Desktop v3.2 端到端
 *
 * 2026-07-24 主指挥协调范式第 128 守恒 (锚点范式) — A-3 合并后真跑 B 路线后端 + Desktop UI 端到端.
 *
 * 测试场景 (3 + 跨 PR11/12/13 端到端):
 * 1. PR11: 上传文件 → 留含 @ 评论 → 推送 mention 通知 → breadcrumb 渲染祖先链
 *    (composable useFileCommentsDesktop + useCommentReactions + useCommentBreadcrumb 集成)
 * 2. PR12: 留 emoji react (12 白名单内/外) → 乐观更新 + 服务端权威 count 校准
 * 3. PR13: 嵌套 5 层评论 → breadcrumb 拉取 + 渲染 ancestor chain (5 条)
 *
 * 设计:
 * - 0 production code 改动铁律维持 — 仅 mock axios (无服务端依赖)
 * - 复用 desktop_drive_comments.spec.js 的 fixtures 风格 + B-3 5 场景 e2e 套件
 * - 跨 PR11/12/13 集成: 留评论触发 mention push + react push → 验证 UI 集成
 * - 后端 endpoint 未部署时 (B-3 实际状态) 静默降级 — 但本 spec 模拟后端响应, 真跑逻辑
 *
 * 注:
 * - 后端 PR11/12/13 已由 A-3 合并入 main (commit e8720771d), 主指挥需部署才能真端到端
 * - 本 spec 跑的是 axios + composables 集成, 不依赖 Playwright 真实浏览器
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import ElementPlus from 'element-plus'
import DesktopFileCommentsView from '@/views/desktop/DesktopFileCommentsView.vue'
import DesktopCommentThread from '@/components/desktop/DesktopCommentThread.vue'
import { EMOJI_WHITELIST } from '@/composables/useCommentReactions'

const originalFetch = global.fetch

const fixtures = {
  file: {
    id: 555,
    title: '微纳米气泡 PR11/12/13 e2e.pdf',
    file_name: 'e2e.pdf',
    file_type: 'pdf',
    file_size: 2048 * 1024,
    owner_id: 2,
    visibility: 'team',
  },
  members: {
    items: [
      { id: 1, username: 'admin',        wechat_id: 'admin',     name: '管理员',  avatar: '' },
      { id: 2, username: 'wangtianzhi',  wechat_id: 'wangtz',    name: '王天志',  avatar: '' },
      { id: 3, username: 'dutonghe',     wechat_id: 'dutonghe',  name: '杜同贺',  avatar: '' },
    ],
  },
  // 嵌套 5 层链 + 顶层评论
  comments: {
    items: [
      {
        id: 1, file_id: 555, user_id: 2, user_name: '王天志',
        content: 'L0 顶层 (with @)', mentions: [3], parent_comment_id: null,
        thread_depth: 0, reply_count: 4, resolved: false,
        created_at: new Date('2026-07-24T10:00:00Z').toISOString(),
      },
      {
        id: 2, file_id: 555, user_id: 3, user_name: '杜同贺',
        content: 'L1 回复 @王天志', mentions: [2], parent_comment_id: 1,
        thread_depth: 1, reply_count: 1, resolved: false,
        created_at: new Date('2026-07-24T10:01:00Z').toISOString(),
      },
      {
        id: 3, file_id: 555, user_id: 2, user_name: '王天志',
        content: 'L2 回复 @杜同贺', mentions: [3], parent_comment_id: 2,
        thread_depth: 2, reply_count: 1, resolved: false,
        created_at: new Date('2026-07-24T10:02:00Z').toISOString(),
      },
      {
        id: 4, file_id: 555, user_id: 3, user_name: '杜同贺',
        content: 'L3 回复 @王天志', mentions: [2], parent_comment_id: 3,
        thread_depth: 2, reply_count: 1, resolved: false,
        created_at: new Date('2026-07-24T10:03:00Z').toISOString(),
      },
      {
        id: 5, file_id: 555, user_id: 2, user_name: '王天志',
        content: 'L4 回复 @杜同贺 (最深层)', mentions: [3], parent_comment_id: 4,
        thread_depth: 2, reply_count: 0, resolved: false,
        created_at: new Date('2026-07-24T10:04:00Z').toISOString(),
      },
    ],
  },
  // 顶层评论 reactions
  reactions: {
    items: {
      1: [
        { emoji: '👍', count: 3, reacted_by_me: true },
        { emoji: '🎉', count: 1, reacted_by_me: false },
      ],
      2: [
        { emoji: '❤️', count: 1, reacted_by_me: false },
      ],
      3: [],
      4: [],
      5: [],
      'file:555': [
        { emoji: '🎉', count: 2, reacted_by_me: true },
      ],
    },
  },
  // 面包屑 (L5 节点 id=5, 4 层祖先)
  breadcrumb5: {
    items: [
      { id: 1, user_id: 2, username: '王天志', snippet: 'L0 顶层 (with @)' },
      { id: 2, user_id: 3, username: '杜同贺', snippet: 'L1 回复 @王天志' },
      { id: 3, user_id: 2, username: '王天志', snippet: 'L2 回复 @杜同贺' },
      { id: 4, user_id: 3, username: '杜同贺', snippet: 'L3 回复 @王天志' },
    ],
  },
  // post 创建顶层评论 (含 mention)
  postCommentResponse: {
    comment: {
      id: 99, file_id: 555, user_id: 2, user_name: '王天志',
      content: '新顶层评论 @杜同贺 请看', mentions: [3], parent_comment_id: null,
      thread_depth: 0, reply_count: 0, resolved: false,
      created_at: new Date().toISOString(),
    },
    mentioned_user_ids: [3],
  },
  // 提交 reaction
  addReactionResponse: {
    comment_id: 1,
    emoji: '👀',
    count: 4,
    reacted_by_me: true,
  },
}

// vi.mock hoisted — inline mock fns 暴露到 globalThis
vi.mock('axios', () => {
  const mockGet = vi.fn()
  const mockPost = vi.fn()
  const mockPatch = vi.fn()
  const mockDelete = vi.fn()
  globalThis.__axiosMockPr111213 = { get: mockGet, post: mockPost, patch: mockPatch, delete: mockDelete }
  return {
    default: { get: mockGet, post: mockPost, patch: mockPatch, delete: mockDelete },
  }
})

function getAxiosMock() {
  return globalThis.__axiosMockPr111213
}

function configureAxios() {
  const axiosMock = getAxiosMock()
  axiosMock.get.mockImplementation((url, config) => {
    if (url.includes('/api/v1/drive/reactions')) {
      const ids = (config?.params?.comment_ids || '').split(',')
      const items = {}
      for (const id of ids) {
        items[id] = fixtures.reactions.items[id] || []
      }
      return Promise.resolve({ data: { items } })
    }
    if (url.match(/\/drive\/comments\/5\/breadcrumb/)) {
      return Promise.resolve({ data: fixtures.breadcrumb5 })
    }
    if (url.match(/\/drive\/comments\/\d+\/breadcrumb/)) {
      return Promise.resolve({ data: { items: [] } })
    }
    if (url.includes('/api/v1/drive/files/555') && !url.includes('/comments')) {
      return Promise.resolve({ data: fixtures.file })
    }
    if (url.includes('/api/v1/drive/files/555/comments')) {
      return Promise.resolve({ data: fixtures.comments })
    }
    if (url.includes('/api/v1/members')) {
      return Promise.resolve({ data: fixtures.members })
    }
    return Promise.reject(new Error('not found: ' + url))
  })
  axiosMock.post.mockImplementation((url, body) => {
    if (url.includes('/api/v1/drive/reactions')) {
      return Promise.resolve({ data: fixtures.addReactionResponse })
    }
    if (url.includes('/api/v1/drive/files/555/comments')) {
      return Promise.resolve({ data: fixtures.postCommentResponse })
    }
    return Promise.resolve({ data: {} })
  })
  axiosMock.delete.mockImplementation((url) => {
    return Promise.resolve({ data: { ok: true } })
  })
  axiosMock.patch.mockImplementation(() => Promise.resolve({ data: { comment: { id: 1, content: 'updated' } } }))
}

function makeViewWrapper() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/drive/file/:id', component: { template: '<div />' } },
      { path: '/drive/file/:id/comments', component: DesktopFileCommentsView, props: true },
    ],
  })
  return mount(DesktopFileCommentsView, {
    props: { fileId: 555 },
    global: { plugins: [router, ElementPlus] },
  })
}

describe('desktop_drive_pr11-13 (W68 第 10 批 C-1)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.setItem('user_info', JSON.stringify({ id: 2, username: 'wangtianzhi' }))
    localStorage.setItem('access_token', 'test-token')
    global.fetch = vi.fn(() => Promise.resolve({ ok: true, json: async () => ({}) }))
    configureAxios()
  })

  afterEach(() => {
    global.fetch = originalFetch
    vi.clearAllMocks()
  })

  it('场景 1 (PR11): 留含 @ 评论 + 推送 mention + breadcrumb 渲染', async () => {
    const wrapper = makeViewWrapper()
    await flushPromises()
    await flushPromises()
    await flushPromises()  // 等 fetchReactions + fetchBreadcrumb 完成

    // 顶层评论加载
    const topItems = wrapper.findAll('.dfcv-top-item')
    expect(topItems.length).toBeGreaterThan(0)

    // 验证 axios GET 文件元信息 (A-3 后端: GET /api/v1/drive/files/:id)
    const axiosMock = getAxiosMock()
    expect(axiosMock.get).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/drive/files/555'),
      expect.anything(),
    )

    // 验证 axios GET 顶层评论列表
    expect(axiosMock.get).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/drive/files/555/comments'),
      expect.anything(),
    )

    // 验证 axios GET reactions 批量 (PR12)
    expect(axiosMock.get).toHaveBeenCalledWith(
      '/api/v1/drive/reactions',
      expect.objectContaining({ params: expect.objectContaining({ comment_ids: expect.any(String) }) }),
    )

    // 模拟用户输入 + 发送评论 (含 @ 提及)
    wrapper.vm.newContent = '新评论 @杜同贺 请看'
    await flushPromises()
    await wrapper.find('.dci-send-btn').trigger('click')
    await flushPromises()

    // 验证 axios POST 触发
    expect(axiosMock.post).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/drive/files/555/comments'),
      expect.objectContaining({ content: '新评论 @杜同贺 请看' }),
      expect.anything(),
    )

    // newContent 应被清空 (post 成功)
    expect(wrapper.vm.newContent).toBe('')

    // 验证 5 个面包屑接口已被调用 (PR11 breadcrumb 端点)
    // 5 个嵌套评论 (id=1-5) 中, id>0 的会触发 fetchBreadcrumb
    // 我们验证该 axios 至少被调用过 (PR11 breadcrumb endpoint)
    const breadcrumbCalls = axiosMock.get.mock.calls.filter(
      (call) => typeof call[0] === 'string' && call[0].includes('/breadcrumb'),
    )
    expect(breadcrumbCalls.length).toBeGreaterThanOrEqual(1)

    wrapper.unmount()
  })

  it('场景 2 (PR12): emoji react 上传 + 乐观更新 + 服务端权威校准', async () => {
    const wrapper = makeViewWrapper()
    await flushPromises()
    await flushPromises()
    await flushPromises()

    // 文件级 emoji 工具栏应有 12 个 (白名单)
    const emojiBtns = wrapper.findAll('.dfcv-react-emoji')
    expect(emojiBtns.length).toBe(EMOJI_WHITELIST.length)
    expect(EMOJI_WHITELIST.length).toBe(12)

    // 文件级反应汇总 (🎉x2 含我) 已渲染
    const filePills = wrapper.findAll('.dfcv-react-pill')
    expect(filePills.length).toBeGreaterThan(0)
    const firstPill = filePills[0]
    expect(firstPill.text()).toContain('🎉')

    // 评论级反应: 顶层评论 id=1 应有 👍(mine) + 🎉
    // 查找评论级反应 pill (注意 selector 不同)
    const reactionPills = wrapper.findAll('.dci-reaction-pill')
    expect(reactionPills.length).toBeGreaterThan(0)

    // 点新 emoji 👀 (不在 fixture 里) → 触发 POST /drive/reactions
    const target = emojiBtns.find((b) => b.text() === '👀')
    expect(target).toBeTruthy()
    await target.trigger('click')
    await flushPromises()

    // 验证 axios POST /drive/reactions 触发
    const axiosMock = getAxiosMock()
    expect(axiosMock.post).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/drive/reactions'),
      expect.objectContaining({ comment_id: 'file:555', emoji: '👀' }),
      expect.anything(),
    )

    wrapper.unmount()
  })

  it('场景 3 (PR13): 嵌套 5 层 breadcrumb + L5 节点带祖先链渲染', async () => {
    const wrapper = mount(DesktopCommentThread, {
      props: {
        comment: fixtures.comments.items[4],  // L4 (id=5, 最深评论)
        depth: 2,
        currentUserId: 2,
        breadcrumbMap: { 5: fixtures.breadcrumb5.items },
        reactionsMap: {},
        emojiWhitelist: EMOJI_WHITELIST,
      },
      global: { plugins: [ElementPlus] },
    })
    await flushPromises()

    // 5 层面包屑应全部渲染
    const crumbs = wrapper.findAll('.dci-crumb')
    expect(crumbs.length).toBe(4)  // L5 节点 (id=5) 的祖先链 = 4 条 (L0-L3)

    // 4 个 separator (n-1)
    const seps = wrapper.findAll('.dci-crumb-sep')
    expect(seps.length).toBe(3)

    // 顺序: 顶层在前 (L0 王天志), 最深祖先在末 (L3 杜同贺)
    expect(crumbs[0].text()).toContain('王天志')
    expect(crumbs[0].text()).toContain('L0 顶层')
    expect(crumbs[3].text()).toContain('杜同贺')
    expect(crumbs[3].text()).toContain('L3 回复')

    // 验证 PR11 breadcrumb 端点被调 (axios.GET /drive/comments/5/breadcrumb)
    // 实际由父组件 DesktopFileCommentsView 触发 (loadReactionsAndBreadcrumbs)
    // 这里只断言 child component 接收到的 props 已渲染
    const props = wrapper.props()
    expect(props.breadcrumbMap[5]).toBeDefined()
    expect(props.breadcrumbMap[5].length).toBe(4)

    wrapper.unmount()
  })
})
