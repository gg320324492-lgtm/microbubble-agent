// @vitest-environment happy-dom
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import LoginView from '@/views/LoginView.vue'
import { useAuthStore } from '@/stores/auth'
import type { AuthErrorPayload } from '@shared/auth-types'

async function mountLogin() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/login', name: 'login', component: LoginView },
      { path: '/', name: 'home', component: { template: '<main />' } }
    ]
  })
  const pinia = createPinia()
  setActivePinia(pinia)
  await router.push('/login')
  await router.isReady()
  return mount(LoginView, { global: { plugins: [pinia, router] } })
}

beforeEach(() => {
  vi.restoreAllMocks()
  document.body.innerHTML = ''
})

describe('科研登录页', () => {
  it('展示 Scientific Research OS 身份区和本地账号说明', async () => {
    const wrapper = await mountLogin()

    expect(wrapper.get('[data-testid="login-identity"]').text()).toContain('Scientific Research OS')
    expect(wrapper.text()).toContain('进入科研工作台')
    expect(wrapper.text()).toContain('账号和实验数据仅保存在本机')
  })

  it('为账号与密码提供关联 label 和正确的 autocomplete', async () => {
    const wrapper = await mountLogin()
    const username = wrapper.get<HTMLInputElement>('#login-username')
    const password = wrapper.get<HTMLInputElement>('#login-password')

    expect(wrapper.get('label[for="login-username"]').text()).toBe('用户名')
    expect(wrapper.get('label[for="login-password"]').text()).toBe('密码')
    expect(username.attributes('autocomplete')).toBe('username')
    expect(password.attributes('autocomplete')).toBe('current-password')
  })

  it('空表单提交时以 alert 呈现中文错误', async () => {
    const wrapper = await mountLogin()

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toBe('请输入用户名和密码')
  })

  it('提交期间禁用输入与登录按钮', async () => {
    const wrapper = await mountLogin()
    const authStore = useAuthStore()
    type FailedLogin = { success: false; error: AuthErrorPayload }
    let finish: (value: FailedLogin) => void = () => {}
    vi.spyOn(authStore, 'login').mockImplementation(
      () => new Promise<FailedLogin>((resolve) => { finish = resolve })
    )

    await wrapper.get('#login-username').setValue('researcher_01')
    await wrapper.get('#login-password').setValue('password')
    await wrapper.get('form').trigger('submit')

    expect(wrapper.get('#login-username').attributes('disabled')).toBeDefined()
    expect(wrapper.get('#login-password').attributes('disabled')).toBeDefined()
    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('button[type="submit"]').text()).toBe('登录中…')

    finish({ success: false, error: { code: 'NETWORK_ERROR', message: '测试结束' } })
    await flushPromises()
  })

  it('消费科研设计令牌并在窄窗口堆叠双栏布局', () => {
    const source = readFileSync(resolve(process.cwd(), 'src/renderer/src/views/LoginView.vue'), 'utf8')

    expect(source).toContain('var(--research-instrument-950)')
    expect(source).toContain('var(--research-teal-700)')
    expect(source).toContain('@media (max-width: 760px)')
  })
})
