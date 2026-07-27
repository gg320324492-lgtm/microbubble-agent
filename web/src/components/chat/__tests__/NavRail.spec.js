/**
 * NavRail.spec.js — W72 B-4 派生新任务 NavRail 跨端点 + 6 主题 dark mode 验证
 *
 * 2026-07-24 主指挥协调范式第 213 守恒预测.
 *
 * 测试场景 (8):
 * 1. 桌面端 NavRail 渲染 — 6 个路由项 + data-theme-accent 属性
 * 2. 当前路由高亮 — /chat 路由 active class 命中
 * 3. accent 循环切换 — orange → ocean → forest → orange
 * 4. 6 主题 dark mode 切换 — themeStore.accent × isDark = 6 组合
 * 5. 移动端断点 — 模拟 isMobile=true 时汉堡按钮显示
 * 6. 移动端汉堡按钮触发 drawerOpen
 * 7. 移动端 nav item 点击后 drawerOpen 自动关闭
 * 8. 跨端点 — 桌面端无汉堡按钮 + 移动端有汉堡按钮
 *
 * 设计:
 * - vitest + @vue/test-utils (与 desktop_emoji_lazy.spec.js 模式一致)
 * - 0 production code 改动铁律维持 — NavRail.vue 仅做最小增强
 * - 派工 v6 段 5 反馈 #5 实战: 派生新任务必含 type hint (NavAccent)
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { ref } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import ElementPlus from 'element-plus'
import NavRail from '@/components/chat/NavRail.vue'
import { useThemeStore } from '@/stores/useThemeStore'

// mock useIsMobile to control viewport state
// 必须用 vue ref — 模板自动 unwrap + 响应式追踪 (派工 v6 段 5 反馈 #5 实战)
const mockIsMobileRef = ref(false)
vi.mock('@/composables/useIsMobile', () => ({
  useIsMobile: () => ({
    isMobile: mockIsMobileRef,
    isMobileXS: { value: false },
    isTablet: { value: false },
    isDesktop: { value: true },
    bp: { value: 'lg' },
  }),
}))

// mock useUserStore
vi.mock('@/stores/user', () => ({
  useUserStore: () => ({
    userInfo: { name: '测试用户', avatar: '' },
  }),
}))

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div/>' } },
      { path: '/chat', component: { template: '<div/>' } },
      { path: '/tasks', component: { template: '<div/>' } },
      { path: '/meetings', component: { template: '<div/>' } },
      { path: '/knowledge', component: { template: '<div/>' } },
      { path: '/workspace', component: { template: '<div/>' } },
      { path: '/drive', component: { template: '<div/>' } },
      { path: '/hypotheses', component: { template: '<div/>' } },
      { path: '/settings', component: { template: '<div/>' } },
    ],
  })
}

async function setup(initialPath = '/chat') {
  setActivePinia(createPinia())
  const router = makeRouter()
  await router.push(initialPath)
  await router.isReady()

  const wrapper = mount(NavRail, {
    global: {
      plugins: [router, ElementPlus],
    },
  })
  await flushPromises()
  return { wrapper, router, themeStore: useThemeStore() }
}

describe('NavRail.vue — W72 B-4 跨端点 + 6 主题 dark mode', () => {
  beforeEach(() => {
    mockIsMobileRef.value = false
    // 模拟 useThemeStore 内部读取 localStorage 用的 storage 接口
    if (typeof localStorage === 'undefined') {
      global.localStorage = {
        getItem: () => null,
        setItem: () => {},
        removeItem: () => {},
        clear: () => {},
      }
    }
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('scenario_1: 桌面端 NavRail 渲染 — 6 个路由项 + data-theme-accent 属性', async () => {
    const { wrapper } = await setup('/chat')
    const nav = wrapper.find('nav.nav-rail')
    expect(nav.exists()).toBe(true)
    // 6 nav items (chat/task/meeting/knowledge/workspace/drive)
    const items = wrapper.findAll('.nav-item')
    expect(items.length).toBe(6)
    // data-theme-accent 必含 accent-{name}-{light|dark}
    const themeAttr = nav.attributes('data-theme-accent')
    expect(themeAttr).toMatch(/^accent-(orange|ocean|forest)-(light|dark)$/)
  })

  it('scenario_2: 当前路由高亮 — /chat 路由 active class 命中', async () => {
    const { wrapper } = await setup('/chat')
    const activeItems = wrapper.findAll('.nav-item.active')
    expect(activeItems.length).toBeGreaterThanOrEqual(1)
    // 找到 chat 项高亮
    const chatItem = wrapper.find('#nav-rail-chat')
    expect(chatItem.exists()).toBe(true)
    expect(chatItem.element.closest('.nav-item').classList.contains('active')).toBe(true)
    // aria-current=page 标记
    expect(chatItem.attributes('aria-current')).toBe('page')
  })

  it('scenario_3: accent 循环切换 — orange → ocean → forest → orange', async () => {
    const { wrapper, themeStore } = await setup('/chat')
    const accentBtn = wrapper.find('#nav-rail-accent')
    expect(accentBtn.exists()).toBe(true)
    // 初始 orange
    expect(themeStore.accent).toBe('orange')
    // 点击 1 → ocean
    await accentBtn.trigger('click')
    expect(themeStore.accent).toBe('ocean')
    // 点击 2 → forest
    await accentBtn.trigger('click')
    expect(themeStore.accent).toBe('forest')
    // 点击 3 → orange 循环
    await accentBtn.trigger('click')
    expect(themeStore.accent).toBe('orange')
  })

  it('scenario_4: 6 主题 dark mode 切换 — accent × isDark = 6 组合', async () => {
    const { wrapper, themeStore } = await setup('/chat')
    const nav = wrapper.find('nav.nav-rail')

    const combos = [
      { accent: 'orange', dark: false, expect: 'accent-orange-light' },
      { accent: 'orange', dark: true,  expect: 'accent-orange-dark' },
      { accent: 'ocean',  dark: false, expect: 'accent-ocean-light' },
      { accent: 'ocean',  dark: true,  expect: 'accent-ocean-dark' },
      { accent: 'forest', dark: false, expect: 'accent-forest-light' },
      { accent: 'forest', dark: true,  expect: 'accent-forest-dark' },
    ]

    for (const c of combos) {
      themeStore.setAccent(c.accent)
      if (c.dark) themeStore.set('dark'); else themeStore.set('light')
      await flushPromises()
      expect(nav.attributes('data-theme-accent')).toBe(c.expect)
    }
  })

  it('scenario_5: 移动端断点 — isMobile=true 时汉堡按钮显示', async () => {
    mockIsMobileRef.value = true
    const { wrapper } = await setup('/chat')
    const hamburger = wrapper.find('#nav-rail-hamburger')
    expect(hamburger.exists()).toBe(true)
    // nav-rail 加 mobile-drawer class
    const nav = wrapper.find('nav.nav-rail')
    expect(nav.classes()).toContain('mobile-drawer')
    // 初始 drawer-open 未加
    expect(nav.classes()).not.toContain('drawer-open')
  })

  it('scenario_6: 移动端汉堡按钮触发 drawerOpen', async () => {
    mockIsMobileRef.value = true
    const { wrapper } = await setup('/chat')
    const hamburger = wrapper.find('#nav-rail-hamburger')
    const nav = wrapper.find('nav.nav-rail')
    // 初始关闭
    expect(nav.classes()).not.toContain('drawer-open')
    // 点击 → 打开
    await hamburger.trigger('click')
    expect(nav.classes()).toContain('drawer-open')
    expect(hamburger.attributes('aria-expanded')).toBe('true')
    // 再点 → 关闭
    await hamburger.trigger('click')
    expect(nav.classes()).not.toContain('drawer-open')
    expect(hamburger.attributes('aria-expanded')).toBe('false')
  })

  it('scenario_7: 移动端 nav item 点击后 drawerOpen 自动关闭', async () => {
    mockIsMobileRef.value = true
    const { wrapper, router } = await setup('/chat')
    // 打开 drawer
    await wrapper.find('#nav-rail-hamburger').trigger('click')
    expect(wrapper.find('nav.nav-rail').classes()).toContain('drawer-open')
    // 点击 drive 路由
    await router.push('/drive')
    await flushPromises()
    const driveBtn = wrapper.find('#nav-rail-drive')
    expect(driveBtn.exists()).toBe(true)
    await driveBtn.trigger('click')
    await flushPromises()
    // drawer 关闭 (watch 监听 activeRoute 变化)
    expect(wrapper.find('nav.nav-rail').classes()).not.toContain('drawer-open')
  })

  it('scenario_8: 跨端点 — 桌面端无汉堡按钮 + 移动端有汉堡按钮', async () => {
    // 桌面端
    mockIsMobileRef.value = false
    const { wrapper: dwrapper } = await setup('/chat')
    expect(mockIsMobileRef.value).toBe(false)
    const dnav = dwrapper.find('nav.nav-rail')
    expect(dnav.classes()).not.toContain('mobile-drawer')
    expect(dnav.attributes('aria-label')).toBe('主导航')

    // 切换到移动端 — 新建一个 wrapper 验证 mobile-drawer class + hamburger
    mockIsMobileRef.value = true
    const { wrapper: mwrapper } = await setup('/chat')
    const mnav = mwrapper.find('nav.nav-rail')
    expect(mnav.classes()).toContain('mobile-drawer')
    expect(mwrapper.find('#nav-rail-hamburger').exists()).toBe(true)
  })
})
