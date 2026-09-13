// @vitest-environment jsdom
// 登录页 UI 契约 — 沿用归档规格的双栏/无障碍结构（骨架设计 §1.3 文案改真本地）
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import LoginView from '@renderer/views/LoginView.vue'
import { useAuthStore } from '@renderer/stores/auth'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

function stubApi(overrides: Partial<Record<string, unknown>> = {}): void {
  // 只挂 api，不替换 window 本体（window 属性在原型上，整体替换会丢 Event 构造器）
  Object.assign(window, {
    api: {
      auth: {
        status: vi.fn().mockResolvedValue({ userCount: 1 }),
        restore: vi.fn().mockResolvedValue(null),
        login: vi.fn(),
        registerAdmin: vi.fn(),
        logout: vi.fn().mockResolvedValue(undefined)
      },
      app: { info: vi.fn().mockResolvedValue({ version: '0.1.0', platform: 'win32', dbPath: 'x', appName: 'x' }) },
      settings: { get: vi.fn(), set: vi.fn() },
      window: { minimize: vi.fn(), toggleMaximize: vi.fn(), close: vi.fn() },
      ...overrides
    }
  })
}

const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    { path: '/login', name: 'login', component: LoginView },
    { path: '/app/assistant', name: 'assistant', component: { template: '<main />' } }
  ]
})

async function mountLogin() {
  setActivePinia(createPinia())
  await router.push('/login')
  await router.isReady()
  return mount(LoginView, { global: { plugins: [router] } })
}

beforeEach(() => {
  stubApi()
})

describe('登录页 UI 契约', () => {
  it('展示身份区与本地账号说明', async () => {
    const wrapper = await mountLogin()
    expect(wrapper.get('[data-testid="login-identity"]').text()).toContain('MicroBubble Lab')
    expect(wrapper.text()).toContain('进入科研工作台')
    expect(wrapper.text()).toContain('账号和数据仅保存在本机数据库')
  })

  it('用户名/密码 label + autocomplete 语义完整', async () => {
    const wrapper = await mountLogin()
    expect(wrapper.get('label[for="login-username"]').text()).toBe('用户名')
    expect(wrapper.get('label[for="login-password"]').text()).toBe('密码')
    expect(wrapper.get('#login-username').attributes('autocomplete')).toBe('username')
    expect(wrapper.get('#login-password').attributes('autocomplete')).toBe('current-password')
  })

  it('空表单提交以 alert 呈现中文错误', async () => {
    const wrapper = await mountLogin()
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toBe('请输入用户名和密码')
  })

  it('提交期间禁用输入与按钮，文案切「登录中…」', async () => {
    const wrapper = await mountLogin()
    const store = useAuthStore()
    let finish!: (v: undefined) => void
    vi.spyOn(store, 'login').mockImplementation(() => new Promise((r) => (finish = r)))
    await wrapper.get('#login-username').setValue('wang')
    await wrapper.get('#login-password').setValue('password123')
    await wrapper.get('form').trigger('submit')
    expect(wrapper.get('#login-username').attributes('disabled')).toBeDefined()
    expect(wrapper.get('#login-password').attributes('disabled')).toBeDefined()
    expect(wrapper.get('button[type="submit"]').text()).toBe('登录中…')
    finish(undefined)
    await flushPromises()
  })

  it('消费设计令牌并定义窄窗口堆叠布局（源码契约）', () => {
    const source = readFileSync(resolve(__dirname, '../../src/renderer/src/views/auth.css'), 'utf8')
    expect(source).toContain('var(--color-primary)')
    expect(source).toContain('@media (max-width: 760px)')
  })
})
