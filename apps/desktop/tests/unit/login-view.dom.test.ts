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
        // M2-3a+ 统一登录：登录窗改走 cloudLogin
        cloudLogin: vi.fn(async () => ({ firstClaim: false, summary: '', cloudUsername: 'wangtz' })),
        registerAdmin: vi.fn(),
        logout: vi.fn().mockResolvedValue(undefined)
      },
      app: { info: vi.fn().mockResolvedValue({ version: '0.1.0', platform: 'win32', dbPath: 'x', appName: 'x' }) },
      settings: { get: vi.fn(), set: vi.fn() },
      window: {
        minimize: vi.fn(),
        toggleMaximize: vi.fn(),
        close: vi.fn(),
        isMaximized: vi.fn().mockResolvedValue(false),
        onStateChange: vi.fn().mockReturnValue(() => undefined)
      },
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
    // DL-3 补完：提示性文字精简——删除的 lede/脚注不得回归
    expect(wrapper.text()).not.toContain('登录后断网也可继续使用')
    expect(wrapper.text()).not.toContain('登录凭据加密保存在本机')
    expect(wrapper.text()).not.toContain('本机加密保存')
    // 精简后保留的文案
    expect(wrapper.text()).toContain('记住账号与密码')
    expect(wrapper.text()).toContain('没有账号？请联系管理员开通')
    expect(wrapper.text()).not.toContain('还没有课题组账号')
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
    expect(wrapper.get('[role="alert"]').text()).toBe('请输入课题组账号与密码') // M2-3a+ 措辞
  })

  it('提交期间禁用输入与按钮，文案切「登录中…」', async () => {
    const wrapper = await mountLogin()
    const store = useAuthStore()
    let finish!: (v: { firstClaim: boolean; summary: string; cloudUsername: string }) => void
    // M2-3a+：登录窗改走 cloudLogin
    vi.spyOn(store, 'cloudLogin').mockImplementation(
      () => new Promise((r) => (finish = r))
    )
    await wrapper.get('#login-username').setValue('wang')
    await wrapper.get('#login-password').setValue('password123')
    await wrapper.get('form').trigger('submit')
    expect(wrapper.get('#login-username').attributes('disabled')).toBeDefined()
    expect(wrapper.get('#login-password').attributes('disabled')).toBeDefined()
    expect(wrapper.get('button[type="submit"]').text()).toBe('登录中…')
    finish({ firstClaim: false, summary: '', cloudUsername: 'wangtz' })
    await flushPromises()
  })

  it('消费设计令牌并定义窄窗口堆叠布局（源码契约）', () => {
    const source = readFileSync(resolve(__dirname, '../../src/renderer/src/views/auth.css'), 'utf8')
    expect(source).toContain('var(--color-primary)')
    expect(source).toContain('@media (max-width: 760px)')
  })
})

// ---------------------------------------------------------------- DL-3 记住凭据勾选框

describe('DL-3 记住凭据勾选框 — 唯一性 + 紧凑样式契约', () => {
  it('★ 勾选框渲染次数 = 1（回归防线：模板重复插入曾致 ×2）', async () => {
    const wrapper = await mountLogin()
    expect(wrapper.findAll('[data-testid="login-remember"]')).toHaveLength(1)
    // 文案同样只允许出现一次
    const hits = wrapper.text().match(/记住账号与密码/g) ?? []
    expect(hits).toHaveLength(1)
  })

  it('★ 紧凑行内布局契约：label.remember-row 单行排布，checkbox 小尺寸品牌色（源码契约）', async () => {
    const wrapper = await mountLogin()
    const row = wrapper.find('label.remember-row')
    expect(row.exists()).toBe(true)
    expect(row.find('input[type="checkbox"]').exists()).toBe(true)
    // 源码契约：.auth-form input 的 44px 全宽规则必须被 checkbox 规则显式还原
    const css = readFileSync(resolve(__dirname, '../../src/renderer/src/views/auth.css'), 'utf8')
    expect(css).toContain('.auth-form .remember-row')
    expect(css).toMatch(/\.auth-form \.remember-row input\[type='checkbox'\][^}]*width: 15px/)
    expect(css).toMatch(/\.auth-form \.remember-row input\[type='checkbox'\][^}]*accent-color/)
  })
})
