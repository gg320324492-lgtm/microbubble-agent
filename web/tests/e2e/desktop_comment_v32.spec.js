/**
 * desktop_comment_v32.spec.js — W68 第 9 批 B-3 桌面端评论 v3.2 收口 端到端测试
 *
 * 2026-07-24 主指挥协调范式第 110 守恒 (桌面端 emoji + @mention + breadcrumb 集成).
 *
 * 测试场景 (5):
 * 1. emoji react 上传: 文件级工具栏点 emoji → POST /drive/reactions → summary bar 出现
 * 2. mention autocomplete: DesktopCommentInput 输入 @ → 已 mention 用户预览渲染
 * 3. breadcrumb 渲染: 嵌套评论顶部展示 ancestor chain
 * 4. reaction summary 聚合: 多 emoji count 汇总正确, 自己 react 高亮
 * 5. 嵌套 5 层 breadcrumb: 深链祖先链全量渲染 (性能: 只对 nested 拉)
 *
 * 设计:
 * - 0 production code 改动铁律维持 — 仅 mock axios (无服务端依赖)
 * - vitest + @vue/test-utils (与 desktop_drive_comments.spec.js 对等)
 * - 后端 reactions/breadcrumb API 由 axios mock 提供 fixture
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import ElementPlus from 'element-plus'
import DesktopFileCommentsView from '@/views/desktop/DesktopFileCommentsView.vue'
import DesktopCommentInput from '@/components/desktop/DesktopCommentInput.vue'
import DesktopCommentThread from '@/components/desktop/DesktopCommentThread.vue'
import { EMOJI_WHITELIST } from '@/composables/useCommentReactions'

const originalFetch = global.fetch

const fixtures = {
  file: {
    id: 77,
    title: '气泡协作文档.pdf',
    file_name: 'collab.pdf',
    file_type: 'pdf',
    file_size: 2048 * 1024,
    owner_id: 1,
    visibility: 'team',
  },
  members: {
    items: [
      { id: 1, username: 'admin', wechat_id: 'admin', name: '管理员', avatar: '' },
      { id: 2, username: 'alice', wechat_id: 'alice', name: '王天志', avatar: '' },
      { id: 3, username: 'bob', wechat_id: 'bob', name: '李科研', avatar: '' },
    ],
  },
  comments: {
    items: [
      {
        id: 1, file_id: 77, user_id: 2, user_name: '王天志',
        content: '顶层评论', mentions: [], parent_comment_id: null,
        thread_depth: 0, reply_count: 1, resolved: false,
        created_at: new Date().toISOString(),
      },
      {
        id: 2, file_id: 77, user_id: 3, user_name: '李科研',
        content: '嵌套回复', mentions: [2], parent_comment_id: 1,
        thread_depth: 1, reply_count: 0, resolved: false,
        created_at: new Date().toISOString(),
      },
    ],
  },
  // reactions: comment 1 有 👍x2(含我) + ❤️x1; 文件级 🎉x1(含我)
  reactions: {
    items: {
      1: [
        { emoji: '👍', count: 2, reacted_by_me: true },
        { emoji: '❤️', count: 1, reacted_by_me: false },
      ],
      2: [],
      'file:77': [{ emoji: '🎉', count: 1, reacted_by_me: true }],
    },
  },
  breadcrumb2: {
    items: [
      { id: 1, user_id: 2, username: '王天志', snippet: '顶层评论' },
    ],
  },
}

// vi.mock hoisted — inline mock fns 暴露到 globalThis
vi.mock('axios', () => {
  const mockGet = vi.fn()
  const mockPost = vi.fn()
  const mockPatch = vi.fn()
  const mockDelete = vi.fn()
  globalThis.__axiosMockV32 = { get: mockGet, post: mockPost, patch: mockPatch, delete: mockDelete }
  return {
    default: { get: mockGet, post: mockPost, patch: mockPatch, delete: mockDelete },
  }
})

function getAxiosMock() {
  return globalThis.__axiosMockV32
}

function configureAxios() {
  const axiosMock = getAxiosMock()
  axiosMock.get.mockImplementation((url, config) => {
    if (url.includes('/drive/reactions')) {
      const ids = (config?.params?.comment_ids || '').split(',')
      const items = {}
      for (const id of ids) {
        items[id] = fixtures.reactions.items[id] || []
      }
      return Promise.resolve({ data: { items } })
    }
    if (url.match(/\/drive\/comments\/2\/breadcrumb/)) {
      return Promise.resolve({ data: fixtures.breadcrumb2 })
    }
    if (url.match(/\/drive\/comments\/\d+\/breadcrumb/)) {
      return Promise.resolve({ data: { items: [] } })
    }
    if (url.includes('/drive/files/77') && !url.includes('/comments')) {
      return Promise.resolve({ data: fixtures.file })
    }
    if (url.includes('/drive/files/77/comments')) {
      return Promise.resolve({ data: fixtures.comments })
    }
    if (url.includes('/members')) {
      return Promise.resolve({ data: fixtures.members })
    }
    return Promise.reject(new Error('not found: ' + url))
  })
  axiosMock.post.mockImplementation((url, body) => {
    if (url.includes('/drive/reactions')) {
      // 添加反应 → 权威 count
      return Promise.resolve({ data: { comment_id: body.comment_id, emoji: body.emoji, count: 1, reacted_by_me: true } })
    }
    return Promise.resolve({
      data: {
        comment: {
          id: 99, file_id: 77, user_id: 2, user_name: '王天志',
          content: '新评论', mentions: [], parent_comment_id: null,
          thread_depth: 0, reply_count: 0, resolved: false,
          created_at: new Date().toISOString(),
        },
        mentioned_user_ids: [],
      },
    })
  })
  axiosMock.delete.mockImplementation((url, config) => {
    if (url.includes('/drive/reactions')) {
      const emoji = config?.data?.emoji
      return Promise.resolve({ data: { comment_id: config?.data?.comment_id, emoji, count: 0, reacted_by_me: false } })
    }
    return Promise.resolve({ data: {} })
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
    props: { fileId: 77 },
    global: { plugins: [router, ElementPlus] },
  })
}

describe('desktop_comment_v32 (W68 第 9 批 B-3)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.setItem('user_info', JSON.stringify({ id: 2, username: 'alice' }))
    localStorage.setItem('access_token', 'test-token')
    global.fetch = vi.fn(() => Promise.resolve({ ok: true, json: async () => ({}) }))
    configureAxios()
  })

  afterEach(() => {
    global.fetch = originalFetch
    vi.clearAllMocks()
  })

  it('场景 1: emoji react 上传 — 文件工具栏 12 emoji + summary bar 聚合', async () => {
    const wrapper = makeViewWrapper()
    await flushPromises()
    await flushPromises()

    // 文件级 emoji 工具栏应有 12 个 emoji
    const emojiBtns = wrapper.findAll('.dfcv-react-emoji')
    expect(emojiBtns.length).toBe(EMOJI_WHITELIST.length)
    expect(EMOJI_WHITELIST.length).toBe(12)

    // 文件级反应汇总 (🎉x1 含我) 已从 fixture 拉到
    const pills = wrapper.findAll('.dfcv-react-pill')
    expect(pills.length).toBeGreaterThan(0)
    expect(pills[0].text()).toContain('🎉')

    // 点一个新 emoji → 触发 POST /drive/reactions
    const target = emojiBtns.find((b) => b.text() === '👀')
    await target.trigger('click')
    await flushPromises()
    expect(getAxiosMock().post).toHaveBeenCalledWith(
      expect.stringContaining('/drive/reactions'),
      expect.objectContaining({ emoji: '👀' }),
      expect.anything(),
    )

    wrapper.unmount()
  })

  it('场景 2: mention autocomplete — 输入 @ 触发已 mention 用户预览', async () => {
    const wrapper = mount(DesktopCommentInput, {
      props: {
        modelValue: '你好 @alice 请看',
        fileId: 77,
        membersList: fixtures.members.items,
      },
      global: { plugins: [ElementPlus] },
    })
    await flushPromises()

    // 已 mention 预览应渲染 alice (王天志)
    const preview = wrapper.find('.dci-mentioned-preview')
    expect(preview.exists()).toBe(true)
    const chips = wrapper.findAll('.dci-mentioned-chip')
    expect(chips.length).toBe(1)
    expect(chips[0].text()).toContain('王天志')

    wrapper.unmount()
  })

  it('场景 3: breadcrumb 渲染 — 嵌套评论顶部展示祖先链', async () => {
    const wrapper = mount(DesktopCommentThread, {
      props: {
        comment: fixtures.comments.items[1],  // 嵌套评论 id=2
        depth: 1,
        currentUserId: 2,
        breadcrumbMap: { 2: fixtures.breadcrumb2.items },
        reactionsMap: {},
        emojiWhitelist: EMOJI_WHITELIST,
      },
      global: { plugins: [ElementPlus] },
    })
    await flushPromises()

    const crumb = wrapper.find('.dci-breadcrumb')
    expect(crumb.exists()).toBe(true)
    const crumbs = wrapper.findAll('.dci-crumb')
    expect(crumbs.length).toBe(1)
    expect(crumbs[0].text()).toContain('王天志')
    expect(crumbs[0].text()).toContain('顶层评论')

    wrapper.unmount()
  })

  it('场景 4: reaction summary 聚合 — 多 emoji count + 自己 react 高亮', async () => {
    const wrapper = mount(DesktopCommentThread, {
      props: {
        comment: fixtures.comments.items[0],  // 顶层 id=1: 👍x2(mine) + ❤️x1
        depth: 0,
        currentUserId: 2,
        reactionsMap: { 1: fixtures.reactions.items[1] },
        breadcrumbMap: {},
        emojiWhitelist: EMOJI_WHITELIST,
      },
      global: { plugins: [ElementPlus] },
    })
    await flushPromises()

    const pills = wrapper.findAll('.dci-reaction-pill')
    expect(pills.length).toBe(2)
    // 👍 是 mine → 有 .mine class
    const thumbPill = pills.find((p) => p.text().includes('👍'))
    expect(thumbPill.classes()).toContain('mine')
    expect(thumbPill.text()).toContain('2')
    // ❤️ 非 mine
    const heartPill = pills.find((p) => p.text().includes('❤️'))
    expect(heartPill.classes()).not.toContain('mine')

    // 点 👍 pill → emit toggle-reaction
    await thumbPill.trigger('click')
    expect(wrapper.emitted('toggle-reaction')).toBeTruthy()
    expect(wrapper.emitted('toggle-reaction')[0]).toEqual([1, '👍'])

    wrapper.unmount()
  })

  it('场景 5: 嵌套 5 层 breadcrumb — 深链祖先链全量渲染', async () => {
    const deepChain = [
      { id: 1, user_id: 2, username: '王天志', snippet: 'L0 顶层' },
      { id: 2, user_id: 3, username: '李科研', snippet: 'L1 回复' },
      { id: 3, user_id: 1, username: '管理员', snippet: 'L2 回复' },
      { id: 4, user_id: 2, username: '王天志', snippet: 'L3 回复' },
      { id: 5, user_id: 3, username: '李科研', snippet: 'L4 回复' },
    ]
    const deepComment = {
      id: 6, file_id: 77, user_id: 1, user_name: '管理员',
      content: 'L5 最深评论', mentions: [], parent_comment_id: 5,
      thread_depth: 2, reply_count: 0, resolved: false,
      created_at: new Date().toISOString(),
    }
    const wrapper = mount(DesktopCommentThread, {
      props: {
        comment: deepComment,
        depth: 2,
        currentUserId: 2,
        breadcrumbMap: { 6: deepChain },
        reactionsMap: {},
        emojiWhitelist: EMOJI_WHITELIST,
      },
      global: { plugins: [ElementPlus] },
    })
    await flushPromises()

    const crumbs = wrapper.findAll('.dci-crumb')
    expect(crumbs.length).toBe(5)
    // 分隔符应有 4 个 (n-1)
    const seps = wrapper.findAll('.dci-crumb-sep')
    expect(seps.length).toBe(4)
    // 顺序: 顶层在前
    expect(crumbs[0].text()).toContain('L0')
    expect(crumbs[4].text()).toContain('L4')

    wrapper.unmount()
  })
})
