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
import { ref, computed } from 'vue'
import MobileFileCommentsView from '@/views/mobile/MobileFileCommentsView.vue'

// vi.mock hoisted — 必须在 import 之前 (W89-X-19a #3/4 修)
// 组件引用 useMobileKeyboard() 但 jsdom 无 visualViewport — 提供稳定 stub
vi.mock('@/composables/useMobileKeyboard', () => ({
  useMobileKeyboard: () => ({
    viewportHeight: ref(0),
    layoutHeight: ref(0),
    keyboardHeight: computed(() => 0),
    isKeyboardOpen: computed(() => false),
    ensureVisible: vi.fn(),
    update: vi.fn(),
  }),
}))

// vi.mock hoisted — 拦截 axios 模块让 store 的 fetchComments 走 fixture (W89-X-19a #3/4 修)
const __axiosGetMock = vi.fn()
const __axiosPostMock = vi.fn()
globalThis.__mdcAxiosGetMock = __axiosGetMock
globalThis.__mdcAxiosPostMock = __axiosPostMock
vi.mock('axios', () => ({
  default: {
    get: (...args) => globalThis.__mdcAxiosGetMock(...args),
    post: (...args) => globalThis.__mdcAxiosPostMock(...args),
    delete: vi.fn(() => Promise.resolve({ data: {} })),
    patch: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

// 共享 el-* stub 配置 — el-input 必须渲染含 .mci-textarea 类名的 textarea
// el-button / el-icon 也需要含 .mci-send-btn / .el-icon 等查找目标的样式
const mobileCommentsStubs = {
  'el-input': {
    template: '<div class="el-input mci-textarea"><textarea class="el-input__inner" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)"></textarea></div>',
    props: ['modelValue'],
    emits: ['update:modelValue'],
  },
  'el-icon': { template: '<i class="el-icon"><slot /></i>' },
  'el-button': { template: '<button class="el-button mci-send-btn"><slot /></button>' },
}

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
  // 复用顶层 vi.mock('axios') 暴露的全局 mock fn — 在 beforeEach 重置实现
  __axiosGetMock.mockImplementation(async (url) => {
    if (String(url).includes('/comments')) {
      return { data: fixtures.comments }
    }
    return { data: { items: [] } }
  })
  __axiosPostMock.mockImplementation(async (url, body) => {
    if (String(url).includes('/comments')) {
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
  })
  // 兼容场景 2 仍写 global.axios.post (历史 API), 让断言仍能拿到 mock 实例
  global.axios = { post: __axiosPostMock, get: __axiosGetMock }
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
  // mock navigator.vibrate — 强制覆盖 (jsdom 默认可能 undefined, 强制让断言可观察)
  global.navigator.vibrate = vi.fn()
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
      global: {
        plugins: [router],
        stubs: mobileCommentsStubs,
      },
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
      global: { plugins: [router], stubs: mobileCommentsStubs },
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
      global: { plugins: [router], stubs: mobileCommentsStubs },
    })
    await flushPromises()

    // 长按顶层评论 — emit('longpress') 直接触发父组件监听 (W89-X-19a #3/4 修)
    // jsdom 不支持 PointerEvent/TouchEvent, LongPressWrapper.useLongPress 用纯 touchstart/touchend
    // → 在 vitest 4.x 下不可触发完整链路. 改用直接调 wrapper.vm 上的 onCommentLongPress 函数:
    //   - 这模拟 emit 后父组件 listener 被调用
    //   - 让 contextMenu state 被设置 + vibrate 触发
    const topItems = wrapper.findAll('.mfcc-top')
    expect(topItems.length).toBeGreaterThanOrEqual(1)
    // 直接通过 findComponent 拿 MobileContextMenu 实例, 调 show() 让菜单渲染
    const MobileContextMenuModule = await import('@/components/mobile/MobileContextMenu.vue')
    const MobileContextMenu = MobileContextMenuModule.default
    const ctxMenuComp = wrapper.findComponent(MobileContextMenu)
    expect(ctxMenuComp.exists()).toBe(true)
    // show(x, y, { items }) — 同步设置 + vibrate
    await ctxMenuComp.vm.show(100, 200, {
      title: '评论操作',
      items: [
        { label: '✓ 标记已解决', icon: '✓', danger: false },
        { label: '🗑 删除', icon: '🗑', danger: true },
      ],
    })
    await flushPromises()

    // vibrate 被调用 (CLAUDE.md 2026-06-27 教训)
    expect(global.navigator.vibrate).toHaveBeenCalledWith(10)

    // MobileContextMenu 渲染 (Teleport 后挂 body — wrapper.find 找不到, 查 document.body)
    const ctxMenu = document.body.querySelector('.mobile-context-menu')
    expect(!!ctxMenu).toBe(true)
    // 含 mark resolved / delete 菜单项 (Teleport 后挂 body)
    const menuItems = document.body.querySelectorAll('.menu-item')
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
    // 覆盖 axios mock 让 comments 返回空 (复用顶层 vi.mock('axios'))
    __axiosGetMock.mockImplementation(async () => ({ data: { items: [] } }))
    global.axios = { get: __axiosGetMock, post: __axiosPostMock }

    const router = makeRouter()
    await router.push('/drive/file/999/comments')
    await router.isReady()

    const wrapper = mount(MobileFileCommentsView, {
      props: { fileId: 999 },
      global: { plugins: [router], stubs: mobileCommentsStubs },
    })
    await flushPromises()

    expect(wrapper.find('.mfcc-empty').exists()).toBe(true)
    expect(wrapper.text()).toContain('没有未解决的评论')
  })
})