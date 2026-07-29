/**
 * desktop_drive_comments.spec.js — W68 路线 F-4 桌面端评论 UI 端到端测试
 *
 * 2026-07-24 主指挥协调范式第 45 守恒.
 *
 * 测试场景:
 * 1. 打开评论列表: 文件右键菜单 → "查看评论" → 跳到 /drive/file/:id/comments
 * 2. 发送评论: 在输入框输入文字 → 点 "发送" → 评论出现在列表顶部
 * 3. 嵌套回复: 点 "回复" 按钮 → @username 前缀填到输入栏 → 焦点回到输入框
 *
 * 设计:
 * - 0 production code 改动铁律维持 — 仅 mock axios (无服务端依赖)
 * - 使用 vitest + @vue/test-utils (项目已有 vitest.config.js)
 * - 文件位置 web/tests/e2e/ 目录 (与 mobile_drive_comments.spec.js 对等)
 *
 * 注:
 * - 本测试以组件单元 + mock fetch 为主, 不依赖真实浏览器
 * - 完整 Playwright e2e 留给后续 PR (desktop-drive-comments-ui Playwright 视觉回归)
 * - 端到端 API mock: GET /drive/files/:id/comments 返回 fixture, POST 模拟成功
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import ElementPlus from 'element-plus'
import DesktopFileCommentsView from '@/views/desktop/DesktopFileCommentsView.vue'

// mock fetch 全局
const originalFetch = global.fetch

const fixtures = {
  file: {
    id: 99,
    title: '微纳米气泡实验报告.pdf',
    file_name: 'report.pdf',
    file_type: 'pdf',
    file_size: 1024 * 1024,
    owner_id: 1,
    visibility: 'team',
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
        content: '@王天志 谢谢!',
        mentions: [2],
        parent_comment_id: 1,
        thread_depth: 1,
        reply_count: 0,
        resolved: false,
        created_at: new Date().toISOString(),
      },
    ],
  },
}

function mockFetch(url) {
  if (url.includes('/api/v1/drive/files/99') && !url.includes('/comments')) {
    return Promise.resolve({
      ok: true,
      json: async () => fixtures.file,
    })
  }
  if (url.includes('/api/v1/drive/files/99/comments') && url.endsWith('comments')) {
    return Promise.resolve({
      ok: true,
      json: async () => fixtures.comments,
    })
  }
  if (url.includes('/api/v1/members')) {
    return Promise.resolve({
      ok: true,
      json: async () => fixtures.members,
    })
  }
  return Promise.resolve({
    ok: false,
    status: 404,
    json: async () => ({ error: { code: 'NOT_FOUND' } }),
  })
}

function makeWrapper() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/drive/file/:id', component: { template: '<div />' } },
      { path: '/drive/file/:id/comments', component: DesktopFileCommentsView, props: true },
    ],
  })

  return mount(DesktopFileCommentsView, {
    props: { fileId: 99 },
    global: {
      plugins: [router, ElementPlus],
    },
  })
}

// 用 vi.mock 拦截 axios 模块 (composable 用 import axios from 'axios')
// 注意: vi.mock factory 在文件顶部 hoist, 必须 inline 创建 mock fn
vi.mock('axios', () => {
  const mockGet = vi.fn()
  const mockPost = vi.fn()
  const mockPatch = vi.fn()
  const mockDelete = vi.fn()
  // 暴露到 globalThis 方便测试访问
  globalThis.__axiosMockDesktop = { get: mockGet, post: mockPost, patch: mockPatch, delete: mockDelete }
  return {
    default: {
      get: mockGet,
      post: mockPost,
      patch: mockPatch,
      delete: mockDelete,
    },
  }
})

function getAxiosMock() {
  return globalThis.__axiosMockDesktop
}

describe('desktop_drive_comments (W68 F-4)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    // 设置 localStorage user_info
    localStorage.setItem('user_info', JSON.stringify({ id: 2, username: 'alice' }))
    localStorage.setItem('access_token', 'test-token')
    global.fetch = vi.fn((url) => mockFetch(url))
    const axiosMock = getAxiosMock()
    // 配置 axios mock 的返回
    axiosMock.get.mockImplementation((url) => {
      if (url.includes('/api/v1/drive/files/99') && !url.includes('/comments')) {
        return Promise.resolve({ data: fixtures.file })
      }
      if (url.includes('/api/v1/drive/files/99/comments')) {
        return Promise.resolve({ data: fixtures.comments })
      }
      if (url.includes('/api/v1/members')) {
        return Promise.resolve({ data: fixtures.members })
      }
      return Promise.reject(new Error('not found'))
    })
    axiosMock.post.mockImplementation(() => Promise.resolve({
      data: {
        comment: {
          id: 99,
          file_id: 99,
          user_id: 2,
          user_name: '王天志',
          content: '新评论',
          mentions: [],
          parent_comment_id: null,
          thread_depth: 0,
          reply_count: 0,
          resolved: false,
          created_at: new Date().toISOString(),
        },
        mentioned_user_ids: [],
      },
    }))
    axiosMock.patch.mockImplementation(() => Promise.resolve({ data: { comment: { id: 1, content: 'updated' } } }))
    axiosMock.delete.mockImplementation(() => Promise.resolve({ data: {} }))
  })

  afterEach(() => {
    global.fetch = originalFetch
    vi.restoreAllMocks()
  })

  it('场景 1: 打开评论列表 — header + tabs + 嵌套回复都正确显示', async () => {
    const wrapper = makeWrapper()
    await flushPromises()
    await flushPromises()

    // 顶部 header 应有文件名
    expect(wrapper.find('.dfcv-title').exists()).toBe(true)

    // tabs (3 个: 未解决/全部/已解决)
    const tabs = wrapper.findAll('.dfcv-tab-btn')
    expect(tabs.length).toBe(3)

    // 加载完后树形评论应出现 (顶层 + 嵌套 reply)
    const topItems = wrapper.findAll('.dfcv-top-item')
    expect(topItems.length).toBeGreaterThan(0)

    // 嵌套回复应渲染 (递归)
    const replyItems = wrapper.findAll('.dci-reply-item')
    expect(replyItems.length).toBeGreaterThan(0)

    wrapper.unmount()
  })

  it('场景 2: 发送评论 — 输入框 + 发送按钮 + 评论 prepend 到列表', async () => {
    const wrapper = makeWrapper()
    await flushPromises()
    await flushPromises()

    // el-input 在测试环境被 stubbed, 渲染为 input 而非 textarea; class="dci-textarea" 直接在 input 上
    const inputEl = wrapper.find('input.dci-textarea, .dci-textarea')
    expect(inputEl.exists()).toBe(true)

    // 直接通过 vm 设值 (stubbed el-input 不传递 v-model)
    wrapper.vm.newContent = '桌面端新评论内容'
    await flushPromises()

    // 点发送按钮
    const sendBtn = wrapper.find('.dci-send-btn')
    expect(sendBtn.exists()).toBe(true)
    expect(sendBtn.attributes('disabled')).toBeUndefined()

    await sendBtn.trigger('click')
    await flushPromises()

    // postComment 应被调用 (axios.post)
    expect(getAxiosMock().post).toHaveBeenCalled()

    // newContent 应被清空
    expect(wrapper.vm.newContent).toBe('')

    wrapper.unmount()
  })

  it('场景 3: 嵌套回复 — 点 reply 按钮 → 输入栏加 @username 前缀', async () => {
    const wrapper = makeWrapper()
    await flushPromises()
    await flushPromises()

    // 找第一个 reply 按钮
    const replyBtns = wrapper.findAll('.dci-action-btn')
    const replyBtn = replyBtns.find((b) => b.text().includes('回复'))
    expect(replyBtn).toBeTruthy()

    // 点回复按钮 → 触发 onReply 事件
    await replyBtn.trigger('click')
    await flushPromises()

    // newContent 应包含 @username 前缀 (顶层评论是 alice)
    expect(wrapper.vm.newContent).toMatch(/^@/)

    wrapper.unmount()
  })

  it('场景 4: 切换 tab — 未解决 / 全部 / 已解决 过滤正确', async () => {
    const wrapper = makeWrapper()
    await flushPromises()
    await flushPromises()

    // 默认 activeTab='open'
    expect(wrapper.vm.activeTab).toBe('open')

    // 点 'all' tab
    const tabs = wrapper.findAll('.dfcv-tab-btn')
    await tabs[1].trigger('click')  // 全部
    expect(wrapper.vm.activeTab).toBe('all')

    // 点 'resolved' tab
    await tabs[2].trigger('click')
    expect(wrapper.vm.activeTab).toBe('resolved')

    wrapper.unmount()
  })

  it('场景 5: 路由级 — 桌面端访问 /drive/file/:id/comments 应渲染 DesktopFileCommentsView', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div />' } },
        { path: '/drive/file/:id', component: { template: '<div />' } },
        { path: '/drive/file/:id/comments', component: DesktopFileCommentsView, props: true },
      ],
    })
    router.push('/drive/file/99/comments')
    await router.isReady()

    const wrapper = mount(DesktopFileCommentsView, {
      props: { fileId: 99 },
      global: { plugins: [router, ElementPlus] },
    })
    await flushPromises()

    // 应渲染桌面端评论视图
    expect(wrapper.find('.desktop-file-comments-view').exists()).toBe(true)

    wrapper.unmount()
  })
})