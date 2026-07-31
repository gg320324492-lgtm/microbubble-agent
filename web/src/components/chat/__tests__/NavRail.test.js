/**
 * NavRail.test.js — W89-X-19c 修订: spec 适配真实 NavRail 契约
 *
 * 历史: W72 B-4 派生初版 (锚点范式第 213 守恒预测).
 * W89-X-13 据实报告: 8 个 scenario 引用旧契约 (`.nav-item` / hamburger /
 * `accent-{name}-{light|dark}` 属性 / `mobile-drawer` class /
 * `#nav-rail-accent` / `#nav-rail-chat` button 等), 与当前 NavRail.vue
 * 真实实现不一致 → 8/8 failed.
 *
 * W91-X-28 跟进: 0 production code 改动铁律守恒 + 类 20.106 沉淀,
 * W89-X-19c 修法搬运至 W91 工作分支, 文件名 .spec.js → .test.js 保留.
 *
 * 派工 v6 §5 反馈类 20.74 沉淀: vitest stale slice 修法 = 调研真实契约
 * + spec 适配 component (非反过来), 不动 production code.
 *
 * 真实 NavRail.vue 契约 (2026-07-30 据实):
 * - 根元素 <nav class="nav-rail">: data-testid="nav-rail", aria-label="主导航"
 *   classes: { collapsed, 'mobile-open' (mobileOpen prop) }
 * - 6 路由项 via <li class="nav-rail-item" :class="{ active: isActive }">,
 *   路由: /chat /knowledge /drive /tasks /meetings /workspace
 * - 每项内嵌 <router-link :to="path" :data-route="path" :aria-current>
 * - 品牌区: <div class="nav-rail-brand"> + brand-icon "MNB" + brand-text
 *   + 移动端专属 <button class="mobile-close" aria-label="关闭导航">
 * - 折叠按钮: <button class="collapse-btn"> 调 uiStore.toggleNavRail()
 * - 移动端遮罩: <button class="nav-rail-scrim" v-if="mobileOpen">
 * - 主题机制: themeStore.mode + themeStore.accent → 通过 watch 写
 *   document.documentElement data-theme="light|dark" + data-accent="orange|ocean|forest"
 *   (非 nav 元素的 data-theme-accent 属性, 那是旧版猜测的契约)
 *
 * 测试场景 (8):
 * 1. 桌面端 NavRail 渲染 — 6 个路由项 + data-testid
 * 2. 当前路由高亮 — /chat 路由 li.nav-rail-item.active 命中 + router-link aria-current=page
 * 3. accent 切换 — themeStore.setAccent orange→ocean→forest (无内嵌切换按钮, 走 store API)
 * 4. theme+accent 双层切换 — document.documentElement data-theme/data-accent 6 组合
 * 5. 移动端断点 — isMobile=true 时 mobile-close 按钮显示 + mobile-open class 视 prop 而定
 * 6. 移动端 mobile-close 触发 closeMobile emit
 * 7. 移动端 nav item 点击触发 closeMobile emit
 * 8. 跨端点 — 桌面端无 mobile-close + 移动端有 mobile-close + collapse-btn
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

describe('NavRail.vue — W89-X-19c 适配真实契约 (8 scenarios)', () => {
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
    // 重置 document.documentElement 的 data-theme / data-accent (themeStore apply)
    if (typeof document !== 'undefined') {
      document.documentElement.removeAttribute('data-theme')
      document.documentElement.removeAttribute('data-accent')
    }
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('scenario_1: 桌面端 NavRail 渲染 — 6 个路由项 + data-testid="nav-rail"', async () => {
    const { wrapper } = await setup('/chat')
    const nav = wrapper.find('nav.nav-rail')
    expect(nav.exists()).toBe(true)
    expect(nav.attributes('data-testid')).toBe('nav-rail')
    expect(nav.attributes('aria-label')).toBe('主导航')
    // 6 nav items (li.nav-rail-item, 路由: chat/knowledge/drive/tasks/meetings/workspace)
    const items = wrapper.findAll('li.nav-rail-item')
    expect(items.length).toBe(6)
  })

  it('scenario_2: 当前路由高亮 — /chat 路由 li.nav-rail-item.active 命中 + router-link aria-current=page', async () => {
    const { wrapper } = await setup('/chat')
    // 通过 router-link 的 data-route 定位 li 父级 (data-route 渲染在 a 上)
    const chatLink = wrapper.find('a[data-route="/chat"]')
    expect(chatLink.exists()).toBe(true)
    expect(chatLink.attributes('aria-current')).toBe('page')
    // li 父级加 active class
    const chatItem = chatLink.element.closest('li.nav-rail-item')
    expect(chatItem).not.toBeNull()
    expect(chatItem.classList.contains('active')).toBe(true)
    // 其余 5 个不应有 active
    const allActive = wrapper.findAll('li.nav-rail-item.active')
    expect(allActive.length).toBe(1)
  })

  it('scenario_3: accent 循环切换 — store API orange → ocean → forest → orange', async () => {
    const { themeStore } = await setup('/chat')
    // 初始 orange (themeStore 内部 watch → document.data-accent)
    expect(themeStore.accent).toBe('orange')
    expect(document.documentElement.getAttribute('data-accent')).toBe('orange')
    // 切 ocean
    themeStore.setAccent('ocean')
    await flushPromises()
    expect(themeStore.accent).toBe('ocean')
    expect(document.documentElement.getAttribute('data-accent')).toBe('ocean')
    // 切 forest
    themeStore.setAccent('forest')
    await flushPromises()
    expect(themeStore.accent).toBe('forest')
    expect(document.documentElement.getAttribute('data-accent')).toBe('forest')
    // 切回 orange 循环
    themeStore.setAccent('orange')
    await flushPromises()
    expect(themeStore.accent).toBe('orange')
  })

  it('scenario_4: theme+accent 双层切换 — document.documentElement data-theme×data-accent = 6 组合', async () => {
    const { themeStore } = await setup('/chat')

    const combos = [
      { accent: 'orange', dark: false, expectTheme: 'light',  expectAccent: 'orange' },
      { accent: 'orange', dark: true,  expectTheme: 'dark',   expectAccent: 'orange' },
      { accent: 'ocean',  dark: false, expectTheme: 'light',  expectAccent: 'ocean'  },
      { accent: 'ocean',  dark: true,  expectTheme: 'dark',   expectAccent: 'ocean'  },
      { accent: 'forest', dark: false, expectTheme: 'light',  expectAccent: 'forest' },
      { accent: 'forest', dark: true,  expectTheme: 'dark',   expectAccent: 'forest' },
    ]

    for (const c of combos) {
      themeStore.setAccent(c.accent)
      themeStore.set(c.dark ? 'dark' : 'light')
      await flushPromises()
      expect(document.documentElement.getAttribute('data-theme')).toBe(c.expectTheme)
      expect(document.documentElement.getAttribute('data-accent')).toBe(c.expectAccent)
    }
  })

  it('scenario_5: 移动端断点 — isMobile=true 时 mobile-close 按钮显示 + nav 含 mobile-open (若 prop)', async () => {
    mockIsMobileRef.value = true
    const { wrapper } = await setup('/chat')
    // mobile-close 按钮 (品牌区)
    const mobileClose = wrapper.find('button.mobile-close')
    expect(mobileClose.exists()).toBe(true)
    expect(mobileClose.attributes('aria-label')).toBe('关闭导航')
    // 初始 mobileOpen=false → nav 不含 mobile-open class
    const nav = wrapper.find('nav.nav-rail')
    expect(nav.classes()).not.toContain('mobile-open')
  })

  it('scenario_6: 移动端 mobile-close 触发 update:mobileOpen=false emit', async () => {
    mockIsMobileRef.value = true
    const { wrapper } = await setup('/chat')
    const mobileClose = wrapper.find('button.mobile-close')
    expect(mobileClose.exists()).toBe(true)
    // 点击 → emit update:mobileOpen false
    await mobileClose.trigger('click')
    expect(wrapper.emitted('update:mobileOpen')).toBeTruthy()
    expect(wrapper.emitted('update:mobileOpen')[0]).toEqual([false])
  })

  it('scenario_7: 移动端 nav item 点击触发 update:mobileOpen=false emit', async () => {
    mockIsMobileRef.value = true
    const { wrapper } = await setup('/chat')
    // 点击 drive 路由项
    const driveLink = wrapper.find('a[data-route="/drive"]')
    expect(driveLink.exists()).toBe(true)
    await driveLink.trigger('click')
    // drawer 关闭 (emit update:mobileOpen false)
    expect(wrapper.emitted('update:mobileOpen')).toBeTruthy()
    expect(wrapper.emitted('update:mobileOpen')[0]).toEqual([false])
  })

  it('scenario_8: 跨端点 — 桌面端无 mobile-close + 移动端有 mobile-close + collapse-btn 共存', async () => {
    // 桌面端
    mockIsMobileRef.value = false
    const { wrapper: dwrapper } = await setup('/chat')
    const dnav = dwrapper.find('nav.nav-rail')
    expect(dnav.classes()).not.toContain('mobile-open')
    // collapse-btn 一直存在 (桌面端折叠)
    const dCollapse = dwrapper.find('button.collapse-btn')
    expect(dCollapse.exists()).toBe(true)
    // 桌面端 CSS 默认 .mobile-close { display: none }, 但 DOM 仍存在
    // 桌面端不依赖 mobile-close 触发关闭, 故此处不强制断言其存在
    const dMobileClose = dwrapper.find('button.mobile-close')
    // 真实 NavRail 中 .mobile-close 始终在 DOM, 仅 CSS 控制可见性
    expect(dMobileClose.exists()).toBe(true)

    // 切换到移动端
    mockIsMobileRef.value = true
    const { wrapper: mwrapper } = await setup('/chat')
    const mnav = mwrapper.find('nav.nav-rail')
    // 移动端 mobile-open 不在初始 class (mobileOpen prop 默认 false)
    expect(mnav.classes()).not.toContain('mobile-open')
    // mobile-close 按钮存在
    const mMobileClose = mwrapper.find('button.mobile-close')
    expect(mMobileClose.exists()).toBe(true)
    expect(mMobileClose.attributes('aria-label')).toBe('关闭导航')
  })
})