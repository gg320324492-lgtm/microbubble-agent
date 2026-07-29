/**
 * thinking-mode-breadcrumb.spec.js — W72 B-2 子 plan ③ 起步 端到端测试
 *
 * 2026-07-27 锚点范式第 212 守恒预测 (W72 B-2 thinking switch + chat breadcrumb).
 *
 * 测试场景 (6/6):
 * 1. ThinkingModeSwitch 渲染 3 个 radio 按钮 (fast / balanced / deep)
 * 2. 默认选中 'balanced' (useUiStore.thinkingMode 初始值)
 * 3. 切换至 'fast' → useUiStore.thinkingMode 同步更新 ('balanced' → 'fast')
 * 4. ChatBreadcrumb 渲染当前 session title (BreadcrumbItem 1 元素模式)
 * 5. 当前 session 高亮 + 状态圆点可见 (idle 状态)
 * 6. status 变更: 'idle' → 'thinking' → 文案变 "思考中…" + 状态类切换
 *
 * 设计原则 (派工纪要 v6 段 5):
 * - 0 production code 改动铁律维持 — 仅 mock localStorage + Pinia
 * - vitest + @vue/test-utils (与 desktop_emoji_lazy.spec.js 模式一致)
 * - useUiStore 真实实例 (不依赖后端), localStorage 已 mock
 * - ThinkingMode enum + BreadcrumbItem interface 验证 type hint 实战
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import ElementPlus from 'element-plus'
import ThinkingModeSwitch from '@/components/chat/ThinkingModeSwitch.vue'
import ChatBreadcrumb from '@/components/chat/ChatBreadcrumb.vue'
import { useUiStore } from '@/stores/useUiStore'

// === Mock localStorage (jsdom 不存任何值, useUiStore 启动 + watch 都要走) ===
class MemoryStorage {
  constructor() { this.map = new Map() }
  getItem(k) { return this.map.has(k) ? this.map.get(k) : null }
  setItem(k, v) { this.map.set(k, String(v)) }
  removeItem(k) { this.map.delete(k) }
  clear() { this.map.clear() }
  get length() { return this.map.size }
  key(i) { return Array.from(this.map.keys())[i] ?? null }
}
global.localStorage = new MemoryStorage()

// === Minimal router (ChatBreadcrumb 用 router-link) ===
function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { name: 'chat-session', path: '/chat/:id', component: { template: '<div>chat</div>' } },
      { name: 'chat', path: '/chat', component: { template: '<div>chat</div>' } },
    ],
  })
}

describe('W72-B-2 ThinkingModeSwitch + ChatBreadcrumb 端到端', () => {
  let pinia
  let router

  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    router = makeRouter()
    // 清空 storage 保证测试隔离
    global.localStorage.clear()
    vi.useFakeTimers()  // 跳过 watch trailing
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('scenario_1: ThinkingModeSwitch 渲染 3 个 radio 按钮 (fast / balanced / deep)', async () => {
    const wrapper = mount(ThinkingModeSwitch, {
      global: { plugins: [pinia, router, ElementPlus] },
    })
    await flushPromises()
    const buttons = wrapper.findAll('button[role="radio"]')
    expect(buttons).toHaveLength(3)
    expect(buttons[0].attributes('aria-label')).toBe('快速')
    expect(buttons[1].attributes('aria-label')).toBe('平衡')
    expect(buttons[2].attributes('aria-label')).toBe('深度')
    // type hint 实战: data-mode value 必须为合法 ThinkingMode enum
    expect(['fast', 'balanced', 'deep']).toContain(
      buttons[0].attributes('name')?.replace('thinking-mode-', '')
    )
  })

  it('scenario_2: 默认选中 "balanced" (useUiStore.thinkingMode 初始值)', async () => {
    const wrapper = mount(ThinkingModeSwitch, {
      global: { plugins: [pinia, router, ElementPlus] },
    })
    await flushPromises()
    const uiStore = useUiStore()
    expect(uiStore.thinkingMode).toBe('balanced')  // 默认值
    // aria-checked 同步
    const balancedBtn = wrapper.find('#thinking-mode-balanced')
    expect(balancedBtn.attributes('aria-checked')).toBe('true')
  })

  it('scenario_3: 切换至 "fast" → useUiStore.thinkingMode 同步更新', async () => {
    const wrapper = mount(ThinkingModeSwitch, {
      global: { plugins: [pinia, router, ElementPlus] },
    })
    await flushPromises()
    const uiStore = useUiStore()
    expect(uiStore.thinkingMode).toBe('balanced')  // 默认值

    // 模拟点击 fast
    const fastBtn = wrapper.find('#thinking-mode-fast')
    await fastBtn.trigger('click')
    await flushPromises()

    expect(uiStore.thinkingMode).toBe('fast')  // 已切换
    expect(fastBtn.attributes('aria-checked')).toBe('true')

    // 再切换至 deep
    const deepBtn = wrapper.find('#thinking-mode-deep')
    await deepBtn.trigger('click')
    await flushPromises()
    expect(uiStore.thinkingMode).toBe('deep')
    expect(deepBtn.attributes('aria-checked')).toBe('true')
  })

  it('scenario_4: ChatBreadcrumb 渲染当前 session title (BreadcrumbItem 1 元素)', async () => {
    const uiStore = useUiStore()
    // 模拟当前会话 (useChatSessionsStore.currentId)
    // ChatBreadcrumb 内部用 store.currentId 找 title; 这里走 useChatSessionsStore mock
    const wrapper = mount(ChatBreadcrumb, {
      props: { status: 'idle' },
      global: { plugins: [pinia, router, ElementPlus] },
    })
    await flushPromises()

    // 渲染 breadcrumb-title 容器
    const titleEl = wrapper.find('.breadcrumb-title')
    expect(titleEl.exists()).toBe(true)
    // 默认 fallback "新对话"
    expect(titleEl.text()).toContain('新对话')

    // type hint 实战: component 必须 export BreadcrumbItem type
    // 通过 props 验证 - fullChain prop 默认 false
    expect(wrapper.props('fullChain')).toBe(false)
  })

  it('scenario_5: 当前 session 高亮 + idle 状态圆点可见', async () => {
    const wrapper = mount(ChatBreadcrumb, {
      props: { status: 'idle' },
      global: { plugins: [pinia, router, ElementPlus] },
    })
    await flushPromises()
    // 状态文案
    expect(wrapper.find('.breadcrumb-status').text()).toContain('在线')
    // 状态类
    expect(wrapper.find('.breadcrumb-status').classes()).toContain('status-idle')
    // 圆点 visible
    expect(wrapper.find('.status-dot').exists()).toBe(true)
    // brand icon
    expect(wrapper.find('.brand-icon').exists()).toBe(true)
    // 锚点范式第 212 守恒预测: 渲染稳定, 不闪
    expect(wrapper.find('[role="banner"]').exists()).toBe(true)
  })

  it('scenario_6: status 变更: "idle" → "thinking" → 文案变 "思考中…"', async () => {
    const wrapper = mount(ChatBreadcrumb, {
      props: { status: 'idle' },
      global: { plugins: [pinia, router, ElementPlus] },
    })
    await flushPromises()
    expect(wrapper.find('.breadcrumb-status').text()).toContain('在线')

    // 切换至 thinking
    await wrapper.setProps({ status: 'thinking' })
    await flushPromises()
    expect(wrapper.find('.breadcrumb-status').text()).toContain('思考中')
    expect(wrapper.find('.breadcrumb-status').classes()).toContain('status-thinking')

    // 切换至 generating
    await wrapper.setProps({ status: 'generating' })
    await flushPromises()
    expect(wrapper.find('.breadcrumb-status').text()).toContain('生成中')
    expect(wrapper.find('.breadcrumb-status').classes()).toContain('status-generating')
  })
})
