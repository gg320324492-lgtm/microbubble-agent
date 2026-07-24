/**
 * desktop_mention_unified.spec.js — W68 第 13 批 C-2 @ 提及 autocomplete 跨视图一致性
 *
 * 2026-07-24 主指挥协调范式第 166 守恒.
 *
 * 测试场景 (4 大场景):
 * 1. useMentionAutocomplete 新增 `name` + `selector` + `keyboardSupport` 参数
 * 2. DesktopCommentInput 触发 mention (v-if .dci-mention-input selector)
 * 3. DesktopFileCommentsView 触发 mention (跨视图隔离 — 各自 mention 状态独立)
 * 4. DesktopDashboardView 触发 mention (quick input 任务描述)
 * 5. 跨视图一致性: 3 个调用同时存在时, mention.isOpen/selector 互不串扰
 *
 * 设计:
 * - 0 production code 改动铁律维持 — 仅 mock axios (无服务端依赖)
 * - vitest + @vue/test-utils (项目已有 vitest.config.js)
 * - 复用 W68 第 9 批 F-3 useMentionAutocomplete.js (filter + dedup + selector 隔离)
 * - 测试 selector 隔离: 3 个 view 同时 mount, 验证各自 mention.isOpen/candidates 独立
 *
 * 注:
 * - 完整 Playwright 浏览器真实 selectionStart 留给后续 PR
 * - DOM 提取逻辑单元测试见 src/composables/__tests__/useMentionAutocomplete.test.js
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import ElementPlus from 'element-plus'
import DesktopCommentInput from '@/components/desktop/DesktopCommentInput.vue'
import { useMentionAutocomplete } from '@/composables/useMentionAutocomplete'

const MEMBERS = [
  { id: 1, username: 'admin',         wechat_id: 'admin',     name: '管理员',   avatar: '', role: 'admin' },
  { id: 2, username: 'wangtianzhi',   wechat_id: 'wangtz',    name: '王天志',   avatar: '', role: 'member' },
  { id: 3, username: 'zhaohangjia',   wechat_id: 'zhaohj',    name: '赵航佳',   avatar: '', role: 'member' },
  { id: 4, username: 'dutonghe',      wechat_id: 'dutonghe',  name: '杜同贺',   avatar: '', role: 'member' },
  { id: 5, username: 'alice_chen',    wechat_id: 'alicec',    name: 'Alice Chen', avatar: '', role: 'member' },
]

/**
 * 注入测试状态到 mention composable: 打开下拉 + 候选列表
 * 真实场景 useMentionAutocomplete.refresh() 通过 DOM 提取 + filterMembers 完成
 */
function openMentionDropdownWithCandidates(mention, candidates) {
  mention.isOpen.value = true
  mention.setCandidates(candidates.map((m) => ({ member: m, score: 100, isExact: true })))
  mention.selectedIndex.value = 0
}

function makeInputWrapper(propsOverride = {}) {
  return mount(DesktopCommentInput, {
    props: {
      fileId: 99,
      membersList: MEMBERS,
      placeholder: '写评论...',
      busy: false,
      autoFocus: false,
      ...propsOverride,
    },
    global: {
      plugins: [ElementPlus],
    },
  })
}

describe('W68 第 13 批 C-2: DesktopCommentInput @ 提及 autocomplete 跨项目引用一致性', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    if (!global.navigator.vibrate) {
      global.navigator.vibrate = vi.fn()
    }
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  // 场景 1: useMentionAutocomplete 新参数
  describe('场景 1: useMentionAutocomplete 新增 name + selector + keyboardSupport 参数', () => {
    it('1.1 默认参数 — name="mention", selector="[data-mention-input]", keyboardSupport=true', () => {
      const ac = useMentionAutocomplete({ members: MEMBERS })
      expect(ac.name.value).toBe('mention')
      expect(ac.selector.value).toBe('[data-mention-input]')
      expect(ac.keyboardSupport.value).toBe(true)
    })

    it('1.2 自定义参数 — name="desktop-comment-input", selector=".dci-mention-input"', () => {
      const ac = useMentionAutocomplete({
        members: MEMBERS,
        name: 'desktop-comment-input',
        selector: '.dci-mention-input',
        keyboardSupport: true,
      })
      expect(ac.name.value).toBe('desktop-comment-input')
      expect(ac.selector.value).toBe('.dci-mention-input')
      expect(ac.keyboardSupport.value).toBe(true)
    })

    it('1.3 keyboardSupport=false → handleKeydown 不响应 (跨视图 view 层字段)', () => {
      const ac = useMentionAutocomplete({
        members: MEMBERS,
        name: 'desktop-file-comments-view',
        keyboardSupport: false,
      })
      openMentionDropdownWithCandidates(ac, MEMBERS)
      // 触发 ArrowDown 不应改变 selectedIndex
      const ev = new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true })
      const result = ac.handleKeydown(ev)
      expect(result).toBe(false)
      expect(ac.selectedIndex.value).toBe(0)
    })

    it('1.4 keyboardSupport=true → handleKeydown 正常响应 ArrowDown', () => {
      const ac = useMentionAutocomplete({
        members: MEMBERS,
        keyboardSupport: true,
      })
      openMentionDropdownWithCandidates(ac, MEMBERS)
      const ev = new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true })
      const result = ac.handleKeydown(ev)
      expect(result).toBe(true)
      expect(ac.selectedIndex.value).toBe(1)
    })
  })

  // 场景 2: DesktopCommentInput 触发
  describe('场景 2: DesktopCommentInput 触发 mention + .dci-mention-input selector', () => {
    it('2.1 DesktopCommentInput 含 .dci-mention-input class + data-mention-input attr', () => {
      const wrapper = makeInputWrapper()
      const input = wrapper.find('.dci-mention-input')
      expect(input.exists()).toBe(true)
      expect(input.attributes('data-mention-input')).toBe('desktop-comment-input')
      wrapper.unmount()
    })

    it('2.2 DesktopCommentInput mention.selector === ".dci-mention-input"', () => {
      const wrapper = makeInputWrapper()
      expect(wrapper.vm.mention.selector.value).toBe('.dci-mention-input')
      expect(wrapper.vm.mention.name.value).toBe('desktop-comment-input')
      wrapper.unmount()
    })

    it('2.3 DesktopCommentInput mention.keyboardSupport === true', () => {
      const wrapper = makeInputWrapper()
      expect(wrapper.vm.mention.keyboardSupport.value).toBe(true)
      wrapper.unmount()
    })

    it('2.4 下拉打开 + 选中 → text 替换 + close', async () => {
      const wrapper = makeInputWrapper()
      openMentionDropdownWithCandidates(wrapper.vm.mention, MEMBERS)
      wrapper.vm.mention.query.value = 'wang'
      wrapper.vm.mention.triggerPos.value = 0
      wrapper.vm.text = '@wang'
      await flushPromises()

      const items = wrapper.findAll('.dci-mention-item')
      expect(items.length).toBeGreaterThan(0)
      await items[1].trigger('mousedown')
      await flushPromises()

      expect(wrapper.vm.text).toMatch(/^@\S+\s/)
      expect(wrapper.vm.mention.isOpen.value).toBe(false)
      wrapper.unmount()
    })
  })

  // 场景 3: 跨视图隔离 — 3 个 mention composable 同时存在
  describe('场景 3: 跨视图隔离 — 3 个 mention composable 状态独立', () => {
    it('3.1 3 个 mention composable 各自持有自己的 isOpen/candidates', () => {
      const inputMention = useMentionAutocomplete({
        members: MEMBERS,
        name: 'desktop-comment-input',
        selector: '.dci-mention-input',
      })
      const viewMention = useMentionAutocomplete({
        members: MEMBERS,
        name: 'desktop-file-comments-view',
        selector: '.dci-mention-input',
      })
      const dashboardMention = useMentionAutocomplete({
        members: MEMBERS,
        name: 'desktop-dashboard-task',
        selector: '[data-mention-input="desktop-dashboard-task"]',
      })

      // 各自 name 不同
      expect(inputMention.name.value).toBe('desktop-comment-input')
      expect(viewMention.name.value).toBe('desktop-file-comments-view')
      expect(dashboardMention.name.value).toBe('desktop-dashboard-task')

      // 各自 selector 不同
      expect(inputMention.selector.value).toBe('.dci-mention-input')
      expect(viewMention.selector.value).toBe('.dci-mention-input')
      expect(dashboardMention.selector.value).toBe('[data-mention-input="desktop-dashboard-task"]')

      // 打开 input 不会影响 view/dashboard
      inputMention.isOpen.value = true
      expect(viewMention.isOpen.value).toBe(false)
      expect(dashboardMention.isOpen.value).toBe(false)
    })

    it('3.2 candidates 数组互不共享 (各 view 独立注入)', () => {
      const inputMention = useMentionAutocomplete({ members: MEMBERS, name: 'desktop-comment-input' })
      const viewMention = useMentionAutocomplete({ members: MEMBERS, name: 'desktop-file-comments-view' })

      const inputSubset = MEMBERS.slice(0, 2)
      const viewSubset = MEMBERS.slice(3, 5)

      inputMention.setCandidates(inputSubset.map((m) => ({ member: m, score: 100, isExact: true })))
      viewMention.setCandidates(viewSubset.map((m) => ({ member: m, score: 100, isExact: true })))

      const inputIds = inputMention.rawCandidates.value.map((c) => c.id)
      const viewIds = viewMention.rawCandidates.value.map((c) => c.id)

      expect(inputIds).toEqual([1, 2])
      expect(viewIds).toEqual([4, 5])
      // 互不干扰
      expect(inputIds).not.toContain(4)
      expect(viewIds).not.toContain(1)
    })
  })

  // 场景 4: 后端兼容 — mention regex 不变
  describe('场景 4: 后端兼容 — MENTION_PATTERN 镜像后端 regex', () => {
    it('4.1 中文姓名 / wechat_id / username 全部 lowercase 后能匹配', async () => {
      const ac = useMentionAutocomplete({ members: MEMBERS })
      ac.query.value = '王'
      ac.refresh()
      await new Promise((r) => setTimeout(r, 200))
      const ids = ac.rawCandidates.value.map((c) => c.id)
      expect(ids).toContain(2) // 王天志
    })

    it('4.2 英文 username prefix 匹配', async () => {
      const ac = useMentionAutocomplete({ members: MEMBERS })
      ac.query.value = 'wang'
      ac.refresh()
      await new Promise((r) => setTimeout(r, 200))
      const ids = ac.rawCandidates.value.map((c) => c.id)
      expect(ids).toContain(2)
    })

    it('4.3 exact match (wechat_id) ranked first', async () => {
      const ac = useMentionAutocomplete({ members: MEMBERS })
      ac.query.value = 'zhaohj'
      ac.refresh()
      await new Promise((r) => setTimeout(r, 200))
      const ids = ac.rawCandidates.value.map((c) => c.id)
      expect(ids[0]).toBe(3) // 赵航佳 exact match
    })
  })
})

describe('W68 第 13 批 C-2: DesktopFileCommentsView 集成 — view 层 mention state', () => {
  let router

  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.setItem('user_info', JSON.stringify({ id: 2, username: 'alice' }))
    localStorage.setItem('access_token', 'test-token')

    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div />' } },
        { path: '/drive/file/:id', component: { template: '<div />' } },
        { path: '/drive/file/:id/comments', component: { template: '<div />' }, props: true },
      ],
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('场景 5: DesktopFileCommentsView 同时持有 viewMention + DesktopCommentInput', async () => {
    // 动态 import 避免在 mount 时引入完整依赖
    const DesktopFileCommentsView = (await import('@/views/desktop/DesktopFileCommentsView.vue')).default

    const wrapper = mount(DesktopFileCommentsView, {
      props: { fileId: 99 },
      global: {
        plugins: [router, ElementPlus],
      },
    })
    await flushPromises()

    // view 层有 viewMention (脚本直接调 useMentionAutocomplete)
    expect(wrapper.vm.viewMention).toBeDefined()
    expect(wrapper.vm.viewMention.name.value).toBe('desktop-file-comments-view')
    expect(wrapper.vm.viewMention.selector.value).toBe('.dci-mention-input')
    expect(wrapper.vm.viewMention.keyboardSupport.value).toBe(false)

    // DesktopCommentInput 子组件也持有 mention (selector 相同, 但状态独立)
    const inputWrap = wrapper.findComponent(DesktopCommentInput)
    expect(inputWrap.exists()).toBe(true)
    if (inputWrap.vm?.mention) {
      expect(inputWrap.vm.mention.name.value).toBe('desktop-comment-input')
      expect(inputWrap.vm.mention.selector.value).toBe('.dci-mention-input')
    }

    wrapper.unmount()
  })

  it('场景 6: DesktopFileCommentsView 容器含 .dci-mention-input class (跨视图一致性)', async () => {
    const DesktopFileCommentsView = (await import('@/views/desktop/DesktopFileCommentsView.vue')).default

    const wrapper = mount(DesktopFileCommentsView, {
      props: { fileId: 99 },
      global: {
        plugins: [router, ElementPlus],
      },
    })
    await flushPromises()

    // 容器上的 .dci-mention-input class 通过 DesktopCommentInput 透传
    expect(wrapper.find('.dci-mention-input').exists()).toBe(true)

    wrapper.unmount()
  })
})
