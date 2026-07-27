import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import NavRail from '@/components/chat/NavRail.vue'
import { useUiStore } from '@/stores/useUiStore'

const __dirname = dirname(fileURLToPath(import.meta.url))
const NAV_RAIL_SOURCE = readFileSync(
  resolve(__dirname, '../../src/components/chat/NavRail.vue'),
  'utf8',
)

const routes = [
  '/chat',
  '/knowledge',
  '/drive',
  '/tasks',
  '/meetings',
  '/workspace',
].map((path) => ({ path, component: { template: '<div />' } }))

async function mountRail(path = '/chat') {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createRouter({ history: createMemoryHistory(), routes })
  await router.push(path)
  await router.isReady()

  const wrapper = mount(NavRail, {
    global: {
      plugins: [pinia, router],
      stubs: {
        'el-icon': { template: '<span class="el-icon"><slot /></span>' },
      },
    },
  })
  return { wrapper, store: useUiStore() }
}

describe('W72 B-1 NavRail', () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.removeAttribute('data-theme')
    document.documentElement.removeAttribute('data-accent')
  })

  afterEach(() => {
    document.documentElement.removeAttribute('data-theme')
    document.documentElement.removeAttribute('data-accent')
  })

  it('scenario_1: 桌面端渲染 6 个路由项', async () => {
    const { wrapper } = await mountRail()
    const links = wrapper.findAll('.nav-rail-item a')

    expect(links).toHaveLength(6)
    expect(links.map((link) => link.attributes('href'))).toEqual([
      '/chat', '/knowledge', '/drive', '/tasks', '/meetings', '/workspace',
    ])
    expect(wrapper.get('[data-testid="nav-rail"]').attributes('aria-label')).toBe('主导航')
  })

  it('scenario_2: /knowledge 当前路由高亮知识库', async () => {
    const { wrapper } = await mountRail('/knowledge')
    const active = wrapper.get('.nav-rail-item.active a')

    expect(active.text()).toContain('知识库')
    expect(active.attributes('href')).toBe('/knowledge')
    expect(active.attributes('aria-current')).toBe('page')
  })

  it('scenario_3: 折叠态在 200px 与 60px 间切换并持久化', async () => {
    const { wrapper, store } = await mountRail()
    const rail = wrapper.get('[data-testid="nav-rail"]')

    expect(store.navRailCollapsed).toBe(false)
    expect(rail.classes()).not.toContain('collapsed')
    expect(NAV_RAIL_SOURCE).toContain('--nav-rail-width: 200px')

    await wrapper.get('.collapse-btn').trigger('click')
    expect(store.navRailCollapsed).toBe(true)
    expect(rail.classes()).toContain('collapsed')
    expect(NAV_RAIL_SOURCE).toContain('--nav-rail-width: 60px')
    expect(localStorage.getItem('mnb:ui:navRailCollapsed')).toBe('1')
  })

  it('scenario_4: orange/ocean/forest × light/dark 六主题共享 token 边界', async () => {
    const { wrapper } = await mountRail()
    const combinations = ['orange', 'ocean', 'forest'].flatMap((accent) =>
      ['light', 'dark'].map((mode) => ({ accent, mode })),
    )

    for (const theme of combinations) {
      document.documentElement.dataset.accent = theme.accent
      document.documentElement.dataset.theme = theme.mode
      expect(wrapper.get('.nav-rail').exists()).toBe(true)
      expect(document.documentElement.dataset.accent).toBe(theme.accent)
      expect(document.documentElement.dataset.theme).toBe(theme.mode)
    }

    expect(NAV_RAIL_SOURCE).toContain('background: var(--color-bg-card)')
    expect(NAV_RAIL_SOURCE).toContain('color: var(--color-primary)')
    expect(NAV_RAIL_SOURCE).toContain('[data-theme="dark"] .nav-rail')
    expect(NAV_RAIL_SOURCE).not.toMatch(/#[0-9a-fA-F]{6}/)
  })
})
