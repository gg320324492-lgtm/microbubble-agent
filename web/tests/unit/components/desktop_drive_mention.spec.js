/**
 * desktop_drive_mention.spec.js — W68 第 5 批 #11 桌面端评论 @mention 自动补全端到端测试
 *
 * 2026-07-24 主指挥协调范式第 68 守恒.
 *
 * 测试场景:
 * 1. 下拉渲染: mention.isOpen=true + candidates 有值 → 模板渲染下拉 + 候选项
 * 2. active 高亮: mention.selectedIndex=2 → 第 3 项 .active 类
 * 3. 点击候选项: mousedown 触发 onMentionItemClick → onSelect 回调 → text 更新
 * 4. keyboard: ArrowDown/Up 切换 selectedIndex (moveDown/moveUp)
 * 5. Enter 选中: handleKeydown(Enter) → selectCandidate → text 更新
 * 6. Esc 关闭: handleKeydown(Esc) → close → isOpen=false
 * 7. v-model 双向绑定: text 变化 → emit update:modelValue
 * 8. mention.isOpen + candidates 为空 → 下拉不显示
 *
 * 设计:
 * - 0 production code 改动铁律维持 — 仅 mock axios (无服务端依赖)
 * - 复用 W68 第 3 批 useMentionAutocomplete.js (filter + dedup)
 * - 复用 W68 第 4 批 DesktopCommentInput.vue 模板 + script
 * - el-input 在 vitest jsdom 环境被 stub 为 <input /> (项目 setup.js 铁律)
 * - 真实 DOM extraction (textarea + selectionStart) 在 useMentionAutocomplete 单测已覆盖
 *   这里直接通过 mention.isOpen.value / mention.candidates.value 注入测试状态
 *   验证 DesktopCommentInput 模板 + 回调绑定的集成
 *
 * 注:
 * - 完整 Playwright e2e 留给后续 PR (Playwright 浏览器真实 selectionStart)
 * - DOM 提取逻辑单元测试见 src/composables/__tests__/useMentionAutocomplete.test.js (P1-8 修复)
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ElementPlus from 'element-plus'
import DesktopCommentInput from '@/components/desktop/DesktopCommentInput.vue'

const MEMBERS = [
  { id: 1, username: 'admin',         wechat_id: 'admin',     name: '管理员',   avatar: '', role: 'admin' },
  { id: 2, username: 'wangtianzhi',   wechat_id: 'wangtz',    name: '王天志',   avatar: '', role: 'member' },
  { id: 3, username: 'zhaohangjia',   wechat_id: 'zhaohj',    name: '赵航佳',   avatar: '', role: 'member' },
  { id: 4, username: 'dutonghe',      wechat_id: 'dutonghe',  name: '杜同贺',   avatar: '', role: 'member' },
  { id: 5, username: 'alice_chen',    wechat_id: 'alicec',    name: 'Alice Chen', avatar: '', role: 'member' },
]

/**
 * 把 mention composable 状态设为"下拉打开 + 候选列表" 以便模板渲染
 * - 真实场景由 useMentionAutocomplete 的 refresh() 从 DOM 提取 + filterMembers 完成
 * - 这里直接注入测试状态验证 DesktopCommentInput 的模板渲染 + 回调
 */
function openMentionDropdownWithCandidates(wrapper, candidates) {
  const mention = wrapper.vm.mention
  mention.isOpen.value = true
  mention.setCandidates(candidates.map((m) => ({ member: m, score: 100, isExact: true })))
  mention.selectedIndex.value = 0
}

function makeWrapper(propsOverride = {}) {
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

describe('DesktopCommentInput @mention 自动补全 (W68 第 5 批 #11)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    if (!global.navigator.vibrate) {
      global.navigator.vibrate = vi.fn()
    }
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('场景 1: mention.isOpen + candidates → 下拉 + 候选项正确渲染', async () => {
    const wrapper = makeWrapper()

    // 初始: 下拉不显示
    expect(wrapper.find('.dci-mention-dropdown').exists()).toBe(false)

    // 注入打开状态 + 候选
    openMentionDropdownWithCandidates(wrapper, MEMBERS)
    await flushPromises()

    const dropdown = wrapper.find('.dci-mention-dropdown')
    expect(dropdown.exists()).toBe(true)

    const items = wrapper.findAll('.dci-mention-item')
    expect(items.length).toBe(MEMBERS.length)

    // 第一个候选项显示 admin
    expect(items[0].text()).toContain('管理员')
    expect(items[0].text()).toContain('@admin')

    wrapper.unmount()
  })

  it('场景 2: candidates 为空 → 下拉不渲染 (CLAUDE.md v-if 条件)', async () => {
    const wrapper = makeWrapper()

    // mention.isOpen=true 但 rawCandidates 为空
    wrapper.vm.mention.isOpen.value = true
    wrapper.vm.mention.setCandidates([])
    await flushPromises()

    expect(wrapper.find('.dci-mention-dropdown').exists()).toBe(false)

    wrapper.unmount()
  })

  it('场景 3: mention.isOpen=false → 下拉不渲染', async () => {
    const wrapper = makeWrapper()

    wrapper.vm.mention.isOpen.value = false
    wrapper.vm.mention.setCandidates([{ member: MEMBERS[0], score: 100, isExact: true }])
    await flushPromises()

    expect(wrapper.find('.dci-mention-dropdown').exists()).toBe(false)

    wrapper.unmount()
  })

  it('场景 4: selectedIndex 决定 active 高亮项', async () => {
    const wrapper = makeWrapper()

    openMentionDropdownWithCandidates(wrapper, MEMBERS)
    wrapper.vm.mention.selectedIndex.value = 2  // 第 3 项 active
    await flushPromises()

    const items = wrapper.findAll('.dci-mention-item')
    expect(items.length).toBe(5)

    // items[0] 不应 active
    expect(items[0].classes()).not.toContain('active')
    // items[2] 应 active
    expect(items[2].classes()).toContain('active')
    // aria-selected 同步
    expect(items[2].attributes('aria-selected')).toBe('true')

    wrapper.unmount()
  })

  it('场景 5: 点击候选项 → onSelect 回调 + text 替换为 @username + 空格, 下拉关闭', async () => {
    const wrapper = makeWrapper()

    openMentionDropdownWithCandidates(wrapper, MEMBERS)
    wrapper.vm.mention.query.value = 'wang'
    wrapper.vm.mention.triggerPos.value = 0
    wrapper.vm.text = '@wang'
    await flushPromises()

    const items = wrapper.findAll('.dci-mention-item')
    expect(items.length).toBeGreaterThan(0)

    // 模拟点击第 2 项 (王天志)
    await items[1].trigger('mousedown')
    await flushPromises()

    // text 应替换为 @wangtz + 空格 (fixture wechat_id='wangtz')
    expect(wrapper.vm.text).toMatch(/^@\S+\s/)

    // 下拉关闭
    expect(wrapper.find('.dci-mention-dropdown').exists()).toBe(false)

    wrapper.unmount()
  })

  it('场景 6: keyboard — ArrowDown + ArrowUp 切换 selectedIndex', async () => {
    const wrapper = makeWrapper()

    openMentionDropdownWithCandidates(wrapper, MEMBERS)
    await flushPromises()

    // 初始 selectedIndex=0
    expect(wrapper.vm.mention.selectedIndex.value).toBe(0)

    // ArrowDown → 1
    let ev = new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true })
    wrapper.vm.onKeydown(ev)
    expect(wrapper.vm.mention.selectedIndex.value).toBe(1)

    // ArrowUp → 0
    ev = new KeyboardEvent('keydown', { key: 'ArrowUp', bubbles: true })
    wrapper.vm.onKeydown(ev)
    expect(wrapper.vm.mention.selectedIndex.value).toBe(0)

    wrapper.unmount()
  })

  it('场景 7: keyboard — Enter 选中 active 项 + text 更新', async () => {
    const wrapper = makeWrapper()

    openMentionDropdownWithCandidates(wrapper, MEMBERS)
    wrapper.vm.mention.query.value = ''
    wrapper.vm.mention.triggerPos.value = 0
    wrapper.vm.text = '@'
    await flushPromises()

    // ArrowDown → 移到第 2 项
    let ev = new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true })
    wrapper.vm.onKeydown(ev)
    await flushPromises()
    expect(wrapper.vm.mention.selectedIndex.value).toBe(1)

    // Enter → 选中
    ev = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })
    wrapper.vm.onKeydown(ev)
    await flushPromises()

    // text 应为 @wechat_id + 空格
    expect(wrapper.vm.text).toMatch(/^@\S+\s/)
    expect(wrapper.vm.text.length).toBeGreaterThan(1)

    wrapper.unmount()
  })

  it('场景 8: keyboard — Esc 关闭下拉, text 保留', async () => {
    const wrapper = makeWrapper()

    openMentionDropdownWithCandidates(wrapper, MEMBERS)
    wrapper.vm.text = '@wang'
    await flushPromises()

    expect(wrapper.find('.dci-mention-dropdown').exists()).toBe(true)

    const ev = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })
    wrapper.vm.onKeydown(ev)
    await flushPromises()

    // 下拉关闭
    expect(wrapper.find('.dci-mention-dropdown').exists()).toBe(false)
    // text 保留
    expect(wrapper.vm.text).toBe('@wang')

    wrapper.unmount()
  })

  it('场景 9: v-model 双向绑定 — text 变化 emit update:modelValue', async () => {
    const wrapper = makeWrapper()

    wrapper.vm.text = '普通评论'
    await flushPromises()

    const emitted = wrapper.emitted('update:modelValue')
    expect(emitted).toBeTruthy()
    expect(emitted[emitted.length - 1][0]).toBe('普通评论')

    wrapper.unmount()
  })

  it('场景 10: mouseenter → 更新 selectedIndex (hover 高亮)', async () => {
    const wrapper = makeWrapper()

    openMentionDropdownWithCandidates(wrapper, MEMBERS)
    await flushPromises()

    const items = wrapper.findAll('.dci-mention-item')
    expect(items.length).toBe(5)

    // mouseenter 第 4 项
    await items[3].trigger('mouseenter')
    await flushPromises()

    expect(wrapper.vm.mention.selectedIndex.value).toBe(3)
    expect(items[3].classes()).toContain('active')

    wrapper.unmount()
  })

  it('场景 11: 候选 avatar 首字母来自 name 或 username', async () => {
    const wrapper = makeWrapper()

    openMentionDropdownWithCandidates(wrapper, MEMBERS.slice(0, 2))  // admin + 王天志
    await flushPromises()

    const items = wrapper.findAll('.dci-mention-item')
    // admin → "管" (name "管理员" 首字)
    expect(items[0].find('.dci-mention-avatar').text()).toBe('管')
    // 王天志 → "王"
    expect(items[1].find('.dci-mention-avatar').text()).toBe('王')

    wrapper.unmount()
  })

  it('场景 12: 键盘未打开下拉时, Enter 直接发送 (Cmd/Ctrl+Enter 桌面端快捷键)', async () => {
    const wrapper = makeWrapper()

    wrapper.vm.text = '直接发送'
    // 不开下拉
    expect(wrapper.find('.dci-mention-dropdown').exists()).toBe(false)

    const ev = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, ctrlKey: true })
    wrapper.vm.onKeydown(ev)
    await flushPromises()

    // emit 'post'
    const emitted = wrapper.emitted('post')
    expect(emitted).toBeTruthy()
    expect(emitted[0][0]).toBe('直接发送')

    wrapper.unmount()
  })
})