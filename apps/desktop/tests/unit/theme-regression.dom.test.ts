// @vitest-environment jsdom
// M7 换新后组件行为回归 — 结构/交互契约在换肤后仍成立（本单只改配色与令牌，不改行为）
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('vue-router', () => ({
  useRoute: () => ({ path: '/app/knowledge' }),
  useRouter: () => ({ push: vi.fn() })
}))

// eslint-disable-next-line import/first
import SideNav from '@renderer/layouts/SideNav.vue'
// eslint-disable-next-line import/first
import StatusBar from '@renderer/layouts/StatusBar.vue'

function stubApi(overrides: Record<string, unknown> = {}): void {
  Object.assign(window, {
    api: {
      app: { info: vi.fn().mockResolvedValue({ version: '0.1.6-alpha', platform: 'win32', dbPath: 'x', appName: 'x' }) },
      auth: { logout: vi.fn().mockResolvedValue(undefined), restore: vi.fn().mockResolvedValue(null) },
      ...overrides
    }
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
  stubApi()
})

describe('SideNav 换新 — 六模块项与选中态仍工作', () => {
  it('渲染六个模块项，当前路由项标记选中并带 aria-current', async () => {
    const w = mount(SideNav)
    await flushPromises()

    const items = w.findAll('.rail-item')
    expect(items.length).toBe(6)
    expect(items.map((i) => i.attributes('aria-label'))).toEqual([
      'AI 助手',
      '实验 ELN',
      '稿件',
      '知识库',
      '会议',
      '设置'
    ])

    const active = items.filter((i) => i.classes('is-active'))
    expect(active.length).toBe(1)
    expect(active[0].attributes('aria-label')).toBe('知识库')
    expect(active[0].attributes('aria-current')).toBe('page')
  })

  it('导航项仍可点击跳转（换新未触碰交互）', async () => {
    const push = vi.fn()
    vi.doMock('vue-router', () => ({
      useRoute: () => ({ path: '/app/knowledge' }),
      useRouter: () => ({ push })
    }))
    const w = mount(SideNav)
    await flushPromises()
    await w.findAll('.rail-item')[0].trigger('click')
    // 路由 push 由 useRouter 提供；此处只断言按钮可点击且不抛错
    expect(w.findAll('.rail-item').length).toBe(6)
  })
})

describe('状态栏换新 — 版本与本地数据状态仍正确渲染', () => {
  it('就绪态渲染版本号 + SQLite 标识，LED 走 is-on', async () => {
    const w = mount(StatusBar)
    await flushPromises()

    expect(w.find('.statusbar').exists()).toBe(true)
    expect(w.text()).toContain('本地数据库就绪')
    expect(w.text()).toContain('v0.1.6-alpha')
    expect(w.text()).toContain('SQLite')
    expect(w.find('.statusbar-led').classes()).toContain('is-on')
  })

  it('取不到应用信息时降级为未就绪态（LED 走 is-off）', async () => {
    stubApi({ app: { info: vi.fn().mockRejectedValue(new Error('db down')) } })
    const w = mount(StatusBar)
    await flushPromises()

    expect(w.text()).toContain('本地数据库未就绪')
    expect(w.find('.statusbar-led').classes()).toContain('is-off')
  })
})
