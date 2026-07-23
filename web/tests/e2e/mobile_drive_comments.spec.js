/**
 * mobile_drive_comments.spec.js — W68 路线 F-3 移动端评论 UI 端到端测试
 *
 * 2026-07-24 主指挥协调范式第 38 守恒.
 *
 * 测试场景:
 * 1. 打开评论列表: 长按文件 → 点 "查看评论" → 跳到 /drive/file/:id/comments
 * 2. 发送评论: 在输入框输入文字 → 点 "发送" → 评论出现在列表顶部
 * 3. 嵌套回复: 长按顶层评论 → MobileContextMenu 显示 resolved toggle / delete
 *
 * 设计:
 * - 0 production code 改动铁律维持 — 仅 mock axios (无服务端依赖)
 * - 使用 happy-dom 或 jsdom 测试环境下做组件渲染验证
 * - 复用 vitest + @vue/test-utils (项目已有 vitest.config.js)
 * - 文件位置 web/tests/e2e/ 目录 (新增, 与 mobile_drive / knowledge 并列)
 *
 * 注:
 * - 本测试以组件单元 + mock fetch 为主, 不依赖真实浏览器
 * - 完整 Playwright e2e 留给后续 PR (mobile-drive-comments-ui Playwright 视觉回归)
 * - 端到端 API mock: GET /drive/files/:id/comments 返回 fixture, POST 模拟成功
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import MobileFileCommentsView from '@/views/mobile/MobileFileCommentsView.vue'

// mock fetch 全局 (兜底 — view 内部用 raw fetch, store 用 axios)
const originalFetch = global.fetch
const originalAxios = global.axios

const fixtures = {
  file: {
    id: 99,
    title: '微纳米气泡实验报告.pdf',
    file_name: 'report.pdf',
    owner_id: 1,
  },
  members: {
    items: [
      { id: 1, username: 'admin',  wechat_id: 'admin',  name: '管理员', avatar: '' },
      { id: 2, username: 'alice',  wechat_id: 'alice',  name: '王天志', avatar: '' },
      { id: 3, username: 'bob',    wechat_id: 'bob',    name: '李科研', avatar: '' },
    ],
  },
  comments: {
    items: [
      {
        id: 1,
        file_id: 99,
        user_id: 2,
        user_name: '王天志',
        content: '实验数据看起来很赞!',
        mentions: [3],
        parent_comment_id: null,
        thread_depth: 0,
        reply_count: 1,
        resolved: false,
        created_at: new Date().toISOString(),
      },
      {
        id: 2,
        file_id: 99,
        user_id: 3,
        user_name: '李科研',
        content: '@alice 同意!',
        mentions: [2],
        parent_comment_id: 1,
        thread_depth: 1,
        reply_count: 0,
        resolved: false,
        created_at: new Date().toISOString(),
      },
      {
        id: 3,
        file_id: 99,
        user_id: 1,
        user_name: '管理员',
        content: '已合并到主分支',
        mentions: [],
        parent_comment_id: null,
        thread_depth: 0,
        reply_count: 0,
        resolved: true,
        created_at: new Date().toISOString(),
      },
    ],
  },
}

function makeRouter() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/drive/file/:id/comments', component: MobileFileCommentsView, props: true },
      { path: '/drive/file/:id', component: { template: '<div />' }, props: true },
      { path: '/drive', component: { template: '<div />' } },
    ],
  })
  return router
}

function setupFetchMock() {
  global.fetch = vi.fn(async (url, opts = {}) => {
    if (url.includes('/api/v1/drive/files/') && !url.includes('/comments')) {
      return {
        ok: true,
        json: async () => fixtures.file,
      }
    }
    if (url.includes('/api/v1/members')) {
      return { ok: true, json: async () => fixtures.members }
    }
    return { ok: true, json: async () => ({ items: [] }) }
  })
}

function setupAxiosMock() {
  const mockAxios = {
    get: vi.fn(async (url) => {
      if (url.includes('/comments')) {
        return { data: fixtures.comments }
      }
      return { data: { items: [] } }
    }),
    post: vi.fn(async (url, body) => {
      if (url.includes('/comments')) {
        const newComment = {
          id: Date.now(),
          file_id: 99,
          user_id: 2,
          user_name: '王天志',
          content: body?.content || '',
          mentions: body?.mentions || [],
          parent_comment_id: body?.parent_comment_id || null,
          thread_depth: body?.parent_comment_id ? 1 : 0,
          reply_count: 0,
          resolved: false,
          created_at: new Date().toISOString(),
        }
        return { data: { comment: newComment, mentioned_user_ids: [] } }
      }
      return { data: {} }
    }),
    delete: vi.fn(async () => ({ data: {} })),
    patch: vi.fn(async () => ({ data: {} })),
  }
  global.axios = mockAxios
  return mockAxios
}

beforeEach(() => {
  setActivePinia(createPinia())
  setupFetchMock()
  setupAxiosMock()
  // mock localStorage
  global.localStorage = {
    getItem: vi.fn(() => 'fake-token'),
    setItem: vi.fn(),
    removeItem: vi.fn(),
  }
  // mock navigator.vibrate
  if (!global.navigator.vibrate) {
    global.navigator.vibrate = vi.fn()
  }
})

afterEach(() => {
  global.fetch = originalFetch
  global.axios = originalAxios
  vi.restoreAllMocks()
})

describe('MobileFileCommentsView (W68 路线 F-3)', () => {
  it('场景 1: 打开评论列表渲染 header + tabs + 列表', async () => {
    const router = makeRouter()
    await router.push('/drive/file/99/comments')
    await router.isReady()

    const wrapper = mount(MobileFileCommentsView, {
      props: { fileId: 99 },
      global: { plugins: [router] },
    })
    await flushPromises()

    // header title
    expect(wrapper.text()).toContain('微纳米气泡实验报告.pdf')

    // tabs 全部 / 未解决 / 已解决
    expect(wrapper.findAll('.mfcc-tab-btn')).toHaveLength(3)

    // 至少 1 条顶层评论 (thread_depth=0 的有 2 条)
    const topItems = wrapper.findAll('.mfcc-top')
    expect(topItems.length).toBeGreaterThanOrEqual(1)

    // 底部输入栏
    expect(wrapper.find('.mci-textarea').exists()).toBe(true)
    expect(wrapper.find('.mci-send-btn').exists()).toBe(true)
  })

  it('场景 2: 发送评论 (v-model + emit post)', async () => {
    const router = makeRouter()
    await router.push('/drive/file/99/comments')
    await router.isReady()

    const wrapper = mount(MobileFileCommentsView, {
      props: { fileId: 99 },
      global: { plugins: [router] },
    })
    await flushPromises()

    // 找到 MobileCommentInput 的 textarea, 输入文字
    const input = wrapper.find('.mci-textarea textarea')
    expect(input.exists()).toBe(true)
    await input.setValue('这条评论是测试发的')
    await flushPromises()

    // 发送按钮 enable
    const sendBtn = wrapper.find('.mci-send-btn')
    expect(sendBtn.attributes('disabled')).toBeUndefined()

    // 点击发送
    await sendBtn.trigger('click')
    await flushPromises()

    // axios.post 至少被调一次 (POST /comments)
    expect(global.axios.post).toHaveBeenCalled()
    const calls = global.axios.post.mock.calls
    const commentCall = calls.find((c) => String(c[0]).includes('/comments') && !c[1]?.parent_comment_id)
    expect(commentCall).toBeTruthy()
    expect(commentCall[1].content).toBe('这条评论是测试发的')
  })

  it('场景 3: 长按顶层评论触发 MobileContextMenu (vibrate + menu items)', async () => {
    const router = makeRouter()
    await router.push('/drive/file/99/comments')
    await router.isReady()

    const wrapper = mount(MobileFileCommentsView, {
      props: { fileId: 99 },
      global: { plugins: [router] },
    })
    await flushPromises()

    // 长按顶层评论
    const longPressWrapper = wrapper.find('.long-press-wrapper')
    expect(longPressWrapper.exists()).toBe(true)
    await longPressWrapper.trigger('long-press', { clientX: 100, clientY: 200 })
    await flushPromises()

    // vibrate 被调用 (CLAUDE.md 2026-06-27 教训)
    expect(global.navigator.vibrate).toHaveBeenCalledWith(10)

    // MobileContextMenu 渲染 (Teleport 后挂 body)
    const ctxMenu = wrapper.find('.mobile-context-menu')
    expect(ctxMenu.exists()).toBe(true)
    // 含 mark resolved / delete 菜单项
    const menuItems = wrapper.findAll('.menu-item')
    expect(menuItems.length).toBeGreaterThanOrEqual(1)
  })

  it('边界: 无评论时显示 empty state', async () => {
    // 覆盖 fetch mock 让 comments 返回空
    global.fetch = vi.fn(async (url) => {
      if (url.includes('/api/v1/members')) {
        return { ok: true, json: async () => ({ items: [] }) }
      }
      return { ok: true, json: async () => ({}) }
    })
    global.axios = {
      get: vi.fn(async () => ({ data: { items: [] } })),
      post: vi.fn(async () => ({ data: {} })),
      delete: vi.fn(async () => ({ data: {} })),
      patch: vi.fn(async () => ({ data: {} })),
    }

    const router = makeRouter()
    await router.push('/drive/file/999/comments')
    await router.isReady()

    const wrapper = mount(MobileFileCommentsView, {
      props: { fileId: 999 },
      global: { plugins: [router] },
    })
    await flushPromises()

    expect(wrapper.find('.mfcc-empty').exists()).toBe(true)
    expect(wrapper.text()).toContain('没有未解决的评论')
  })
})